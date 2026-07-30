"""m_interlock deflate CSV 파일을 interlock_no 기준으로 upsert하는 서비스입니다."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from django.db import connection, transaction
from django.utils import timezone

from api.data_movement.common.services.deflate_csv import read_deflate_csv_file
from api.data_movement.common.services.file_loader import (
    ClaimedDataFile,
    claim_incoming_file,
    delete_claimed_file,
    list_incoming_files,
)
from api.data_movement.common.services.postgres_copy import copy_append_rows
from api.data_movement.m_interlock.models import MInterlockLoadJob
from api.data_movement.m_interlock.services import spec


@dataclass(frozen=True)
class SourceFileInfo:
    """m_interlock 원천 파일명에서 추출한 정보입니다."""

    line_id: str
    file_timestamp: str


@dataclass(frozen=True)
class LoadFileOutcome:
    """단일 파일 처리 결과입니다."""

    file_name: str
    status: str
    row_count: int
    error_message: str | None = None


@dataclass(frozen=True)
class LoadRunSummary:
    """m_interlock 적재 실행 요약입니다."""

    outcomes: list[LoadFileOutcome]

    @property
    def processed_count(self) -> int:
        """처리한 파일 수를 반환합니다."""

        return len(self.outcomes)

    @property
    def success_count(self) -> int:
        """성공한 파일 수를 반환합니다."""

        return sum(1 for outcome in self.outcomes if outcome.status == MInterlockLoadJob.Status.SUCCESS)

    @property
    def failure_count(self) -> int:
        """실패한 파일 수를 반환합니다."""

        return sum(1 for outcome in self.outcomes if outcome.status == MInterlockLoadJob.Status.FAILED)


def parse_source_file_name(*, file_name: str) -> SourceFileInfo:
    """파일명에서 LineID와 파일 timestamp를 추출하고 날짜를 검증합니다."""

    match = re.match(spec.SOURCE_FILE_PATTERN, file_name, flags=re.IGNORECASE)
    if not match:
        raise ValueError(f"지원하지 않는 파일명입니다: {file_name}")

    file_timestamp = match.group("file_timestamp")
    try:
        datetime.strptime(file_timestamp, "%Y%m%d_%H%M")
    except ValueError as exc:
        raise ValueError(f"지원하지 않는 파일 timestamp입니다: {file_timestamp}") from exc

    return SourceFileInfo(
        line_id=match.group("line_id"),
        file_timestamp=file_timestamp,
    )


def _finish_job(
    *,
    job: MInterlockLoadJob,
    status: str,
    row_count: int,
    error_message: str | None = None,
) -> None:
    """적재 이력 row를 최종 상태로 갱신합니다."""

    job.status = status
    job.row_count = row_count
    job.error_message = error_message
    job.finished_at = timezone.now()
    job.save(update_fields=["status", "row_count", "error_message", "finished_at"])


def _create_job(*, file_name: str, file_path: Path) -> MInterlockLoadJob:
    """원천 파일 기준으로 적재 이력 row를 생성합니다."""

    return MInterlockLoadJob.objects.create(
        file_name=file_name,
        file_path=str(file_path),
        status=MInterlockLoadJob.Status.RUNNING,
        started_at=timezone.now(),
    )


def _read_interlock_frame(*, file_path: Path):
    """m_interlock 파일을 원천 precision을 보존하는 DataFrame으로 읽습니다."""

    return read_deflate_csv_file(
        file_path=file_path,
        columns=spec.COLUMNS,
        datetime_columns=spec.DATETIME_COLUMNS,
        float_columns=spec.FLOAT_COLUMNS,
        separator=spec.FILE_SEPARATOR,
        strict_column_count=True,
    )


def _prepare_interlock_frame(frame):
    """빈 interlock_no를 제외하고 파일 내 마지막 key row만 남깁니다."""

    key_values = frame[spec.UPSERT_KEY]
    prepared_frame = frame.filter(
        key_values.is_not_null() & (key_values.str.strip_chars() != "")
    ).unique(
        subset=[spec.UPSERT_KEY],
        keep="last",
        maintain_order=True,
    )
    if prepared_frame.shape[0] == 0:
        raise ValueError("interlock_no 값이 있는 row가 없습니다.")
    return prepared_frame


def _upsert_rows(*, frame) -> int:
    """임시 테이블 COPY 후 interlock_no 기준으로 원천 컬럼을 upsert합니다."""

    quoted_table = connection.ops.quote_name(spec.TABLE_NAME)
    quoted_temp_table = connection.ops.quote_name(spec.TEMP_TABLE_NAME)
    quoted_columns = [
        connection.ops.quote_name(column)
        for column in spec.COLUMNS
    ]
    columns_sql = ", ".join(quoted_columns)
    update_columns = [
        column
        for column in spec.COLUMNS
        if column != spec.UPSERT_KEY
    ]
    update_assignments = ",\n".join(
        (
            f"{connection.ops.quote_name(column)} = "
            f"EXCLUDED.{connection.ops.quote_name(column)}"
        )
        for column in update_columns
    )
    quoted_upsert_key = connection.ops.quote_name(spec.UPSERT_KEY)

    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(f"DROP TABLE IF EXISTS {quoted_temp_table}")
            cursor.execute(
                f"""
                CREATE TEMP TABLE {quoted_temp_table}
                ON COMMIT DROP
                AS
                SELECT {columns_sql}
                FROM {quoted_table}
                WITH NO DATA
                """
            )

        copy_append_rows(
            frame=frame,
            table_name=spec.TEMP_TABLE_NAME,
            columns=spec.COLUMNS,
        )

        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO {quoted_table} AS target ({columns_sql})
                SELECT {columns_sql}
                FROM {quoted_temp_table}
                ON CONFLICT ({quoted_upsert_key})
                DO UPDATE SET
                    {update_assignments}
                """
            )
            return cursor.rowcount


def _load_claimed_file(*, claimed_file: ClaimedDataFile) -> LoadFileOutcome:
    """processing으로 선점한 m_interlock 파일을 transaction 단위로 upsert합니다."""

    job = _create_job(file_name=claimed_file.original_name, file_path=claimed_file.original_path)

    try:
        parse_source_file_name(file_name=claimed_file.original_name)
        frame = _read_interlock_frame(file_path=claimed_file.working_path)
        if frame.shape[0] == 0:
            raise ValueError(f"empty dataframe: {claimed_file.original_path}")
        prepared_frame = _prepare_interlock_frame(frame)
        row_count = _upsert_rows(frame=prepared_frame)

        _finish_job(
            job=job,
            status=MInterlockLoadJob.Status.SUCCESS,
            row_count=row_count,
        )
        return LoadFileOutcome(
            file_name=claimed_file.original_name,
            status=MInterlockLoadJob.Status.SUCCESS,
            row_count=row_count,
        )
    except Exception as exc:
        error_message = str(exc)
        _finish_job(
            job=job,
            status=MInterlockLoadJob.Status.FAILED,
            row_count=0,
            error_message=error_message,
        )
        return LoadFileOutcome(
            file_name=claimed_file.original_name,
            status=MInterlockLoadJob.Status.FAILED,
            row_count=0,
            error_message=error_message,
        )
    finally:
        delete_claimed_file(claimed_file=claimed_file)


def _dry_run_one_file(*, file_path: Path) -> LoadFileOutcome:
    """파일 이동과 대상 테이블 반영 없이 m_interlock 파일을 검증합니다."""

    job = _create_job(file_name=file_path.name, file_path=file_path)

    try:
        parse_source_file_name(file_name=file_path.name)
        frame = _read_interlock_frame(file_path=file_path)
        if frame.shape[0] == 0:
            raise ValueError(f"empty dataframe: {file_path}")
        row_count = _prepare_interlock_frame(frame).shape[0]

        _finish_job(job=job, status=MInterlockLoadJob.Status.DRY_RUN, row_count=row_count)
        return LoadFileOutcome(
            file_name=file_path.name,
            status=MInterlockLoadJob.Status.DRY_RUN,
            row_count=row_count,
        )
    except Exception as exc:
        error_message = str(exc)
        _finish_job(
            job=job,
            status=MInterlockLoadJob.Status.FAILED,
            row_count=0,
            error_message=error_message,
        )
        return LoadFileOutcome(
            file_name=file_path.name,
            status=MInterlockLoadJob.Status.FAILED,
            row_count=0,
            error_message=error_message,
        )


def load_m_interlock_files(
    *,
    data_dir: Path | str | None = None,
    dry_run: bool = False,
    limit: int | None = None,
) -> LoadRunSummary:
    """m_interlock incoming 파일들을 이름순으로 incremental upsert합니다."""

    resolved_table_dir = Path(data_dir) if data_dir is not None else spec.DEFAULT_TABLE_DIR
    files = list_incoming_files(table_dir=resolved_table_dir, pattern=spec.FILE_PATTERN, limit=limit)
    outcomes = []
    for file_path in files:
        if dry_run:
            outcomes.append(_dry_run_one_file(file_path=file_path))
            continue
        claimed_file = claim_incoming_file(file_path=file_path, table_dir=resolved_table_dir)
        outcomes.append(_load_claimed_file(claimed_file=claimed_file))
    return LoadRunSummary(outcomes=outcomes)
