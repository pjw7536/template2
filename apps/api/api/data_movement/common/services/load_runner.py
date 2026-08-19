"""Data Movement 파일 적재의 공통 실행 순서를 제공합니다."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from api.data_movement.common.services.file_loader import (
    ClaimedDataFile,
    claim_incoming_file,
    list_incoming_files,
)


Outcome = TypeVar("Outcome")


def run_incoming_file_load(
    *,
    table_dir: Path,
    pattern: str,
    limit: int | None,
    dry_run: bool,
    validate_file: Callable[..., Outcome],
    load_claimed_file: Callable[..., Outcome],
) -> list[Outcome]:
    """목록 조회와 파일 선점을 표준 순서로 수행해 결과를 반환합니다.

    표별 parser, job 상태, transaction, cleanup 정책은 전달받은 callable이
    소유합니다. dry-run은 파일을 선점하지 않는 기존 계약을 유지합니다.
    """

    files = list_incoming_files(table_dir=table_dir, pattern=pattern, limit=limit)
    outcomes: list[Outcome] = []
    for file_path in files:
        if dry_run:
            outcomes.append(validate_file(file_path=file_path))
            continue
        claimed_file: ClaimedDataFile = claim_incoming_file(
            file_path=file_path,
            table_dir=table_dir,
        )
        outcomes.append(load_claimed_file(claimed_file=claimed_file))
    return outcomes


__all__ = ["run_incoming_file_load"]
