"""m_interlock data movement 앱 테스트입니다."""

from __future__ import annotations

import zlib
from datetime import datetime, timezone as datetime_timezone
from decimal import Decimal
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import SimpleTestCase, TestCase, override_settings

from api.data_movement.m_interlock.management.commands.load_m_interlock import services
from api.data_movement.m_interlock.models import MInterlock, MInterlockLoadJob
from api.data_movement.m_interlock import selectors
from api.data_movement.m_interlock.services import loader as loader_module
from api.data_movement.m_interlock.services import spec
from api.data_movement.m_interlock.services.loader import LoadFileOutcome, LoadRunSummary


def _write_deflate_csv(path: Path, rows: list[list[str]]) -> None:
    """테스트용 m_interlock deflate CSV 파일을 생성합니다."""

    payload = "\n".join(spec.FILE_SEPARATOR.join(row) for row in rows).encode("utf-8")
    path.write_bytes(zlib.compress(payload))


def _build_interlock_row(
    *,
    line_id: str = "LINE01",
    interlock_no: str = "INTLK-001",
    lot_id: str = "LOT-01",
    usl: str = "12345678901234567890.12345678901234567890",
    spec_target: str = "10.0001",
    last_update_date: str = "2026-07-30 11:30:00",
) -> list[str]:
    """제공된 35개 DDL 컬럼 순서로 테스트 row를 생성합니다."""

    row = [
        line_id,
        interlock_no,
        "9.9",
        "SPEC",
        "interlock comment",
        "PPID-01",
        usl,
        spec_target,
        "1.25",
        "8.75",
        "5",
        "2.5",
        "BATCH-01",
        "METRO-ITEM",
        "interlock description",
        "AREA01",
        "PROC01",
        "KIND",
        lot_id,
        "STEP-100",
        "202607301100000000",
        "EQP-TYPE",
        "BAY01",
        "CHAMBER-A",
        "MSTEP-100",
        "202607301115000000",
        "2026W31",
        "202607",
        "METRO-EQP-01",
        "PROD-EQP-01",
        last_update_date,
        "WAFER-01",
        "PHASE-01",
        "equipment detail",
        "engineer comment",
    ]
    if len(row) != len(spec.COLUMNS):
        raise AssertionError("테스트 row와 m_interlock spec 컬럼 수가 일치하지 않습니다.")
    return row


class MInterlockStructureTests(SimpleTestCase):
    """m_interlock schema, 파일명, command 경계를 검증합니다."""

    def test_model_table_names_match_expected_tables(self) -> None:
        """원천 및 load-job 테이블명이 합의한 이름과 일치합니다."""

        self.assertEqual(MInterlock._meta.db_table, "m_interlock")
        self.assertEqual(MInterlockLoadJob._meta.db_table, "m_interlock_load_job")
        source_fields = [
            field.name
            for field in MInterlock._meta.local_fields
            if field.name not in {"id", "created_at"}
        ]
        self.assertEqual(source_fields, spec.COLUMNS)

    def test_numeric_fields_use_unbounded_postgresql_numeric(self) -> None:
        """spec 상 decimal 컬럼은 precision과 scale 없는 numeric을 사용합니다."""

        for field_name in ("usl", "spec_target", "lsl", "ucl", "cl", "lcl"):
            self.assertEqual(MInterlock._meta.get_field(field_name).db_type(connection), "numeric")

    def test_lot_id_uses_unbounded_postgresql_text(self) -> None:
        """lot_id는 원천 길이를 제한하지 않는 text로 저장합니다."""

        self.assertEqual(MInterlock._meta.get_field("lot_id").db_type(connection), "text")

    def test_interlock_no_has_upsert_unique_constraint(self) -> None:
        """interlock_no upsert를 보장하는 unique constraint를 선언합니다."""

        constraint = next(
            item
            for item in MInterlock._meta.constraints
            if item.name == "uniq_m_intlk_no"
        )

        self.assertEqual(constraint.fields, ("interlock_no",))

    def test_timeline_index_matches_normalized_query_fields(self) -> None:
        """Observer 조회 인덱스 이름과 표현식 구성이 모델에 선언되어 있습니다."""

        index = next(
            item
            for item in MInterlock._meta.indexes
            if item.name == "idx_m_intlk_prd_kind_ptm"
        )

        self.assertEqual(len(index.expressions), 3)

    def test_parse_source_file_name_supports_variable_line_and_timestamp(self) -> None:
        """LineID와 날짜가 바뀌는 합의된 파일명에서 값을 추출합니다."""

        source_info = loader_module.parse_source_file_name(
            file_name="m_interlock_LINE_A_20260730_1130.csv.deflate"
        )

        self.assertEqual(source_info.line_id, "LINE_A")
        self.assertEqual(source_info.file_timestamp, "20260730_1130")

    def test_parse_source_file_name_rejects_invalid_timestamp(self) -> None:
        """실재하지 않는 날짜와 시간은 적재 전에 거절합니다."""

        with self.assertRaisesRegex(ValueError, "지원하지 않는 파일 timestamp"):
            loader_module.parse_source_file_name(
                file_name="m_interlock_LINE01_20261340_9999.csv.deflate"
            )

    @patch.object(services, "load_m_interlock_files")
    def test_command_reports_no_files(self, load_files) -> None:
        """처리 파일이 없으면 성공 메시지만 출력합니다."""

        load_files.return_value = LoadRunSummary(outcomes=[])
        stdout = StringIO()

        call_command("load_m_interlock", stdout=stdout)

        self.assertIn("처리할 파일 없음", stdout.getvalue())

    @patch.object(services, "load_m_interlock_files")
    def test_command_raises_when_any_file_failed(self, load_files) -> None:
        """실패 파일이 있으면 scheduler가 감지할 CommandError를 발생시킵니다."""

        load_files.return_value = LoadRunSummary(
            outcomes=[
                LoadFileOutcome(
                    file_name="bad.csv.deflate",
                    status=MInterlockLoadJob.Status.FAILED,
                    row_count=0,
                    error_message="invalid",
                )
            ]
        )

        with self.assertRaises(CommandError):
            call_command("load_m_interlock", stdout=StringIO())


class MInterlockSelectorTests(TestCase):
    """Observer용 m_interlock selector의 설비/종류/한국시간 계약을 검증합니다."""

    def test_selector_normalizes_keys_and_returns_seoul_event_time(self) -> None:
        """prod_eqp_id와 kind를 대소문자 무관하게 찾고 KST 시간을 반환합니다."""

        matching = MInterlock.objects.create(
            prod_eqp_id=" prod-eqp-01 ",
            interlock_kind=" spc ",
            prod_progs_time="20260728 145502",
            interlock_no="SPC-001",
            interlock_comment="SPC 발생",
        )
        MInterlock.objects.create(
            prod_eqp_id="PROD-EQP-01",
            interlock_kind="FDC",
            prod_progs_time="20260728 145503",
        )
        MInterlock.objects.create(
            prod_eqp_id="OTHER-EQP",
            interlock_kind="SPC",
            prod_progs_time="20260728 145504",
        )

        rows = selectors.fetch_interlock_timeline_rows(
            eqp_id=" prod-eqp-01 ",
            interlock_kind="spc",
            start_at="2026-07-28",
            end_at="2026-07-28",
        )

        self.assertEqual([row["id"] for row in rows], [matching.id])
        self.assertEqual(
            rows[0]["event_time"],
            datetime(2026, 7, 28, 14, 55, 2, tzinfo=ZoneInfo("Asia/Seoul")),
        )

    def test_selector_converts_offset_boundary_and_skips_invalid_source_time(self) -> None:
        """offset query는 KST로 변환하고 유효하지 않은 원천 시간은 제외합니다."""

        matching = MInterlock.objects.create(
            prod_eqp_id="PROD-EQP-01",
            interlock_kind="SPC",
            prod_progs_time="20260728 145502",
        )
        MInterlock.objects.create(
            prod_eqp_id="PROD-EQP-01",
            interlock_kind="SPC",
            prod_progs_time="20260728 996001",
        )

        rows = selectors.fetch_interlock_timeline_rows(
            eqp_id="PROD-EQP-01",
            interlock_kind="SPC",
            start_at="2026-07-28T05:55:02+00:00",
            end_at="2026-07-28T05:55:02+00:00",
            limit=10,
        )

        self.assertEqual([row["id"] for row in rows], [matching.id])


@override_settings(DATA_MOVEMENT_FILE_READY_MIN_AGE_SECONDS=0, DATA_MOVEMENT_FILE_READY_STABILITY_SECONDS=0)
class MInterlockLifecycleTests(TestCase):
    """m_interlock 파일 선점, upsert, 정밀도 보존 lifecycle을 검증합니다."""

    def test_loader_upserts_rows_and_preserves_unbounded_numeric(self) -> None:
        """backtick row를 upsert하고 numeric 소수 자릿수를 손실 없이 저장합니다."""

        expected_usl = Decimal("12345678901234567890.12345678901234567890")
        expected_lot_id = "LOT-" + ("LONG-" * 20)
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            incoming = root / "incoming"
            incoming.mkdir()
            source = incoming / "m_interlock_LINE01_20260730_1130.csv.deflate"
            _write_deflate_csv(source, [_build_interlock_row(lot_id=expected_lot_id)])

            summary = loader_module.load_m_interlock_files(data_dir=root)

            self.assertFalse(source.exists())

        self.assertEqual(summary.success_count, 1, summary.outcomes)
        self.assertEqual(summary.outcomes[0].row_count, 1)
        loaded = MInterlock.objects.get()
        self.assertEqual(loaded.lot_id, expected_lot_id)
        self.assertEqual(loaded.usl, expected_usl)
        self.assertEqual(loaded.spec_target, Decimal("10.0001"))
        self.assertEqual(
            loaded.last_update_date,
            datetime(2026, 7, 30, 11, 30, tzinfo=datetime_timezone.utc),
        )
        self.assertIsNotNone(loaded.id)
        self.assertIsNotNone(loaded.created_at)
        self.assertEqual(MInterlockLoadJob.objects.get().status, MInterlockLoadJob.Status.SUCCESS)

    def test_loader_keeps_previous_rows_for_incremental_files(self) -> None:
        """후속 파일의 interlock_no가 다르면 기존 row를 함께 유지합니다."""

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            incoming = root / "incoming"
            incoming.mkdir()

            first = incoming / "m_interlock_LINE01_20260730_1130.csv.deflate"
            _write_deflate_csv(first, [_build_interlock_row(interlock_no="INTLK-001")])
            first_summary = loader_module.load_m_interlock_files(data_dir=root)

            second = incoming / "m_interlock_LINE01_20260730_1140.csv.deflate"
            _write_deflate_csv(second, [_build_interlock_row(interlock_no="INTLK-002")])
            second_summary = loader_module.load_m_interlock_files(data_dir=root)

        self.assertEqual(first_summary.success_count, 1, first_summary.outcomes)
        self.assertEqual(second_summary.success_count, 1, second_summary.outcomes)
        self.assertEqual(
            list(MInterlock.objects.order_by("id").values_list("interlock_no", flat=True)),
            ["INTLK-001", "INTLK-002"],
        )

    def test_loader_overwrites_existing_row_by_interlock_no(self) -> None:
        """후속 파일의 동일 interlock_no는 기존 식별자를 유지하며 덮어씁니다."""

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            incoming = root / "incoming"
            incoming.mkdir()

            first = incoming / "m_interlock_LINE01_20260730_1130.csv.deflate"
            _write_deflate_csv(
                first,
                [
                    _build_interlock_row(
                        interlock_no="INTLK-001",
                        line_id="LINE01",
                        lot_id="LOT-OLD",
                    )
                ],
            )
            first_summary = loader_module.load_m_interlock_files(data_dir=root)
            original = MInterlock.objects.get(interlock_no="INTLK-001")
            original_id = original.id
            original_created_at = original.created_at

            second = incoming / "m_interlock_LINE01_20260730_1140.csv.deflate"
            _write_deflate_csv(
                second,
                [
                    _build_interlock_row(
                        interlock_no="INTLK-001",
                        line_id="LINE02",
                        lot_id="LOT-NEW",
                        last_update_date="2026-07-30 11:40:00",
                    )
                ],
            )
            second_summary = loader_module.load_m_interlock_files(data_dir=root)

        self.assertEqual(first_summary.success_count, 1, first_summary.outcomes)
        self.assertEqual(second_summary.success_count, 1, second_summary.outcomes)
        self.assertEqual(MInterlock.objects.count(), 1)
        updated = MInterlock.objects.get(interlock_no="INTLK-001")
        self.assertEqual(updated.id, original_id)
        self.assertEqual(updated.created_at, original_created_at)
        self.assertEqual(updated.line_id, "LINE02")
        self.assertEqual(updated.lot_id, "LOT-NEW")

    def test_loader_keeps_last_file_duplicate_and_skips_blank_key(self) -> None:
        """파일 내 중복은 마지막 row를 사용하고 빈 interlock_no는 제외합니다."""

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            incoming = root / "incoming"
            incoming.mkdir()
            source = incoming / "m_interlock_LINE01_20260730_1150.csv.deflate"
            _write_deflate_csv(
                source,
                [
                    _build_interlock_row(
                        interlock_no="INTLK-001",
                        lot_id="LOT-FIRST",
                    ),
                    _build_interlock_row(interlock_no="", lot_id="LOT-BLANK"),
                    _build_interlock_row(
                        interlock_no="INTLK-001",
                        lot_id="LOT-LAST",
                    ),
                ],
            )

            summary = loader_module.load_m_interlock_files(data_dir=root)

        self.assertEqual(summary.success_count, 1, summary.outcomes)
        self.assertEqual(summary.outcomes[0].row_count, 1)
        self.assertEqual(MInterlock.objects.count(), 1)
        self.assertEqual(
            MInterlock.objects.get(interlock_no="INTLK-001").lot_id,
            "LOT-LAST",
        )

    def test_loader_fails_when_all_interlock_numbers_are_blank(self) -> None:
        """유효한 interlock_no가 하나도 없으면 파일 실패로 기록합니다."""

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            incoming = root / "incoming"
            incoming.mkdir()
            source = incoming / "m_interlock_LINE01_20260730_1200.csv.deflate"
            _write_deflate_csv(
                source,
                [_build_interlock_row(interlock_no="")],
            )

            summary = loader_module.load_m_interlock_files(data_dir=root)

        self.assertEqual(summary.failure_count, 1)
        self.assertIn(
            "interlock_no 값이 있는 row가 없습니다.",
            summary.outcomes[0].error_message or "",
        )
        self.assertEqual(MInterlock.objects.count(), 0)

    def test_dry_run_validates_without_moving_or_loading_file(self) -> None:
        """dry-run은 파일과 대상 테이블을 변경하지 않고 parsing 결과만 기록합니다."""

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            incoming = root / "incoming"
            incoming.mkdir()
            source = incoming / "m_interlock_LINE02_20260730_1200.csv.deflate"
            _write_deflate_csv(source, [_build_interlock_row(line_id="LINE02")])

            summary = loader_module.load_m_interlock_files(data_dir=root, dry_run=True)

            self.assertTrue(source.exists())

        self.assertEqual(summary.processed_count, 1)
        self.assertEqual(summary.success_count, 0)
        self.assertEqual(summary.failure_count, 0)
        self.assertEqual(MInterlock.objects.count(), 0)
        self.assertEqual(MInterlockLoadJob.objects.get().status, MInterlockLoadJob.Status.DRY_RUN)

    def test_invalid_matching_file_is_recorded_as_failed_and_removed(self) -> None:
        """glob에 잡힌 잘못된 timestamp 파일은 실패 이력으로 남기고 처리 경로에서 제거합니다."""

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            incoming = root / "incoming"
            incoming.mkdir()
            source = incoming / "m_interlock_LINE01_20261340_9999.csv.deflate"
            _write_deflate_csv(source, [_build_interlock_row()])

            summary = loader_module.load_m_interlock_files(data_dir=root)

            self.assertFalse(source.exists())

        self.assertEqual(summary.failure_count, 1)
        self.assertIn("지원하지 않는 파일 timestamp", summary.outcomes[0].error_message or "")
        self.assertEqual(MInterlock.objects.count(), 0)
        self.assertEqual(MInterlockLoadJob.objects.get().status, MInterlockLoadJob.Status.FAILED)

    def test_loader_rejects_row_with_wrong_column_count(self) -> None:
        """35개 고정 컬럼보다 짧은 row는 일부 데이터로 저장하지 않습니다."""

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            incoming = root / "incoming"
            incoming.mkdir()
            source = incoming / "m_interlock_LINE01_20260730_1230.csv.deflate"
            _write_deflate_csv(source, [_build_interlock_row()[:-1]])

            summary = loader_module.load_m_interlock_files(data_dir=root)

        self.assertEqual(summary.failure_count, 1)
        self.assertIn("expected=35, actual=34", summary.outcomes[0].error_message or "")
        self.assertEqual(MInterlock.objects.count(), 0)
