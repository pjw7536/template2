# =============================================================================
# 모듈 설명: tables 도메인 읽기 셀렉터를 제공합니다.
# - 주요 함수: list_columns, fetch_rows, fetch_row
# - 불변 조건: 모든 조회는 읽기 전용입니다.
# =============================================================================

from __future__ import annotations

from typing import Any, Iterable

from api.common.db import run_query
from api.common.utils import list_table_columns


def list_columns(*, table_name: str) -> list[str]:
    """테이블 컬럼 목록을 반환합니다.

    입력:
    - table_name: 테이블 이름

    반환:
    - list[str]: 컬럼 이름 목록

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    return list_table_columns(table_name)


def fetch_rows(*, sql: str, params: Iterable[Any]) -> list[dict[str, Any]]:
    """SQL로 조회한 결과를 리스트로 반환합니다.

    입력:
    - sql: 실행할 SQL
    - params: 바인딩 파라미터

    반환:
    - list[dict[str, Any]]: 조회 결과 목록

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음(쿼리 실패 시 상위 예외 전파)
    """

    return run_query(sql, list(params))


def fetch_row(*, sql: str, params: Iterable[Any]) -> dict[str, Any] | None:
    """SQL 결과 중 첫 번째 row를 반환합니다.

    입력:
    - sql: 실행할 SQL
    - params: 바인딩 파라미터

    반환:
    - dict[str, Any] | None: 첫 번째 행 또는 None

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음(쿼리 실패 시 상위 예외 전파)
    """

    rows = fetch_rows(sql=sql, params=params)
    return rows[0] if rows else None


__all__ = ["fetch_row", "fetch_rows", "list_columns"]
