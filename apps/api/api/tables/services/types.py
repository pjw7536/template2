from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class TableNotFoundError(LookupError):
    """요청한 테이블이 존재하지 않을 때 발생합니다."""

    def __init__(self, table_name: str) -> None:
        super().__init__(f'Table "{table_name}" was not found')
        self.table_name = table_name


class TableRecordNotFoundError(LookupError):
    """요청한 레코드가 없을 때 발생합니다."""


@dataclass(frozen=True)
class TableUpdateResult:
    """테이블 업데이트 결과."""

    table_name: str
    previous_row: dict[str, Any] | None
    updated_row: dict[str, Any] | None
