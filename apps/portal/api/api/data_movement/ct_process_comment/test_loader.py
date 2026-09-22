"""ct_process_comment 파일 적재 lifecycle 테스트입니다."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.db import connection
from django.test import TestCase, override_settings

from api.data_movement.ct_process_comment.models import CtProcessComment, CtProcessCommentLoadJob
from api.data_movement.ct_process_comment.services import loader as loader_module
from api.data_movement.ct_process_comment.test_support import _build_comment_row, _write_deflate_csv


@override_settings(DATA_MOVEMENT_FILE_READY_MIN_AGE_SECONDS=0, DATA_MOVEMENT_FILE_READY_STABILITY_SECONDS=0)
class CtProcessCommentLifecycleTests(TestCase):
    """CT_PROCESS_COMMENT 파일 처리 lifecycle을 검증합니다."""

    def test_loader_upserts_existing_workorder_comment_in_database(self) -> None:
        """실제 COPY 경로로 기존 workorder comment를 새 파일 row로 갱신합니다."""

        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO ctttm_workorder_list
                    (source_type, workorder_id, line_id, eqp_id, work_type, description, inprg_date, comp_date)
                VALUES
                    ('MST', 'WO1', 'L1', 'EQP1', 'PM', 'desc', NULL, NULL),
                    ('MST', 'WO2', 'L1', 'eQP2', 'PM', 'desc', NULL, NULL)
                """
            )
        CtProcessComment.objects.create(
            workorder_id="WO1",
            line_id="OLD_LINE",
            contents="old contents",
            use_yn="Y",
        )

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            incoming = root / "incoming"
            incoming.mkdir()
            source = incoming / "65635_CT_PROCESS_COMMENT_20260529_1300.csv.deflate"
            _write_deflate_csv(
                source,
                [
                    _build_comment_row(workorder_id="WO1", line_id="NEW_LINE", contents="new contents"),
                    _build_comment_row(workorder_id="WO2", eqp_id="eQP2", contents="created contents"),
                    _build_comment_row(workorder_id="WO_MISSING", line_id="SKIP_LINE", contents="skip contents"),
                ],
            )

            summary = loader_module.load_ct_process_comment_files(data_dir=root)

        self.assertEqual(summary.success_count, 1)
        updated_row = CtProcessComment.objects.get(workorder_id="WO1")
        self.assertEqual(updated_row.line_id, "NEW_LINE")
        self.assertEqual(updated_row.contents, "new contents")
        self.assertEqual(updated_row.update_flag, "Y")
        created_row = CtProcessComment.objects.get(workorder_id="WO2")
        self.assertEqual(created_row.contents, "created contents")
        self.assertEqual(created_row.update_flag, "Y")
        self.assertFalse(CtProcessComment.objects.filter(workorder_id="WO_MISSING").exists())

    def test_loader_keeps_one_latest_row_when_file_has_duplicate_workorder_id(self) -> None:
        """같은 파일의 중복 workorder_id는 최신 update_date row 하나만 반영합니다."""

        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO ctttm_workorder_list
                    (source_type, workorder_id, line_id, eqp_id, work_type, description, inprg_date, comp_date)
                VALUES
                    ('MST', 'WO1', 'L1', 'EQP1', 'PM', 'desc', NULL, NULL)
                """
            )

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            incoming = root / "incoming"
            incoming.mkdir()
            source = incoming / "65635_CT_PROCESS_COMMENT_20260529_1300.csv.deflate"
            _write_deflate_csv(
                source,
                [
                    _build_comment_row(
                        workorder_id="WO1",
                        line_id="OLD_LINE",
                        contents="old contents",
                        update_date="2999-01-01 00:00:00",
                    ),
                    _build_comment_row(
                        workorder_id="WO1",
                        line_id="NEW_LINE",
                        contents="new contents",
                        update_date="2999-01-02 00:00:00",
                    ),
                ],
            )

            summary = loader_module.load_ct_process_comment_files(data_dir=root)

        self.assertEqual(summary.success_count, 1, summary.outcomes)
        self.assertEqual(CtProcessComment.objects.filter(workorder_id="WO1").count(), 1)
        loaded_row = CtProcessComment.objects.get(workorder_id="WO1")
        self.assertEqual(loaded_row.line_id, "NEW_LINE")
        self.assertEqual(loaded_row.contents, "new contents")

    def test_loader_keeps_update_flag_when_existing_comment_is_unchanged(self) -> None:
        """동일한 comment row 재적재는 API 요청 flag를 새로 켜지 않습니다."""

        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO ctttm_workorder_list
                    (source_type, workorder_id, line_id, eqp_id, work_type, description, inprg_date, comp_date)
                VALUES
                    ('MST', 'WO1', 'L1', 'EQP1', 'PM', 'desc', NULL, NULL)
                """
            )

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            incoming = root / "incoming"
            incoming.mkdir()
            source = incoming / "65635_CT_PROCESS_COMMENT_20260529_1300.csv.deflate"
            _write_deflate_csv(source, [_build_comment_row(workorder_id="WO1")])

            first_summary = loader_module.load_ct_process_comment_files(data_dir=root)

            self.assertEqual(first_summary.success_count, 1)
            loaded_row = CtProcessComment.objects.get(workorder_id="WO1")
            self.assertEqual(loaded_row.update_flag, "Y")

            loaded_row.update_flag = "N"
            loaded_row.save(update_fields=["update_flag"])
            source = incoming / "65635_CT_PROCESS_COMMENT_20260529_1400.csv.deflate"
            _write_deflate_csv(source, [_build_comment_row(workorder_id="WO1")])

            second_summary = loader_module.load_ct_process_comment_files(data_dir=root)

        self.assertEqual(second_summary.success_count, 1, second_summary.outcomes)
        unchanged_row = CtProcessComment.objects.get(workorder_id="WO1")
        self.assertEqual(unchanged_row.update_flag, "N")

    def test_loader_resets_llm_summary_when_contents_text_changes(self) -> None:
        """contents_text 변경 시 기존 LLM 요약을 비워 재요약 대상이 되게 합니다."""

        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO ctttm_workorder_list
                    (source_type, workorder_id, line_id, eqp_id, work_type, description, inprg_date, comp_date)
                VALUES
                    ('MST', 'WO1', 'L1', 'EQP1', 'PM', 'desc', NULL, NULL)
                """
            )
        CtProcessComment.objects.create(
            workorder_id="WO1",
            line_id="OLD_LINE",
            contents_text="old text",
            llm_core_summary="old core summary",
            llm_summary="old summary",
            summary_retry_count=2,
            summary_last_error_code="empty_content",
            summary_last_error="이전 오류",
            use_yn="Y",
        )

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            incoming = root / "incoming"
            incoming.mkdir()
            source = incoming / "65635_CT_PROCESS_COMMENT_20260529_1300.csv.deflate"
            _write_deflate_csv(source, [_build_comment_row(workorder_id="WO1")])

            summary = loader_module.load_ct_process_comment_files(data_dir=root)

        self.assertEqual(summary.success_count, 1, summary.outcomes)
        updated_row = CtProcessComment.objects.get(workorder_id="WO1")
        self.assertEqual(updated_row.contents_text, "contents text")
        self.assertIsNone(updated_row.llm_core_summary)
        self.assertIsNone(updated_row.llm_summary)
        self.assertEqual(updated_row.summary_retry_count, 0)
        self.assertIsNone(updated_row.summary_last_error_code)
        self.assertIsNone(updated_row.summary_last_error)

    @patch.object(loader_module, "_upsert_rows")
    def test_loader_upserts_and_deletes_processing_file(self, upsert_rows) -> None:
        """성공 시 upsert를 호출하고 파일을 삭제합니다."""

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            incoming = root / "incoming"
            incoming.mkdir()
            source = incoming / "65635_CT_PROCESS_COMMENT_20260529_1300.csv.deflate"
            _write_deflate_csv(source, [_build_comment_row()])

            summary = loader_module.load_ct_process_comment_files(data_dir=root)

            self.assertEqual(summary.success_count, 1)
            self.assertFalse(source.exists())
            self.assertEqual(list((root / "processing").iterdir()), [])

        upsert_rows.assert_called_once()
        self.assertEqual(CtProcessCommentLoadJob.objects.filter(status="success").count(), 1)

    @patch.object(loader_module, "_upsert_rows", side_effect=ValueError("copy failed"))
    def test_loader_deletes_file_even_when_upsert_fails(self, upsert_rows) -> None:
        """DB 반영 실패 시에도 처리 파일을 삭제하고 실패 이력을 남깁니다."""

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            incoming = root / "incoming"
            incoming.mkdir()
            source = incoming / "65635_CT_PROCESS_COMMENT_20260529_1300.csv.deflate"
            _write_deflate_csv(source, [_build_comment_row()])

            summary = loader_module.load_ct_process_comment_files(data_dir=root)

            self.assertEqual(summary.failure_count, 1)
            self.assertFalse(source.exists())
            self.assertEqual(list((root / "processing").iterdir()), [])

        upsert_rows.assert_called_once()
        self.assertEqual(CtProcessCommentLoadJob.objects.filter(status="failed").count(), 1)
