from __future__ import annotations

from typing import Any, Iterable

from api.common.db import run_query
from api.common.utils import list_table_columns


def list_columns(*, table_name: str) -> list[str]:
    """테이블 컬럼 목록을 반환합니다.

    Side effects:
        None. Read-only query.
    """

    return list_table_columns(table_name)


def fetch_rows(*, sql: str, params: Iterable[Any]) -> list[dict[str, Any]]:
    """SQL로 조회한 결과를 리스트로 반환합니다.

    Side effects:
        None. Read-only query.
    """

    return run_query(sql, list(params))


def fetch_row(*, sql: str, params: Iterable[Any]) -> dict[str, Any] | None:
    """SQL 결과 중 첫 번째 row를 반환합니다.

    Side effects:
        None. Read-only query.
    """

    rows = fetch_rows(sql=sql, params=params)
    return rows[0] if rows else None


__all__ = ["fetch_row", "fetch_rows", "list_columns"]
