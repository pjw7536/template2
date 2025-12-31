# =============================================================================
# 모듈 설명: 공용 읽기 전용 DB 조회 셀렉터를 제공합니다.
# - 주요 대상: list_table_columns, _get_user_sdwt_prod_values
# - 불변 조건: SELECT 전용 쿼리만 수행합니다.
# =============================================================================

"""공용 DB 조회 셀렉터 모음.

- 주요 대상: list_table_columns, _get_user_sdwt_prod_values
- 주요 엔드포인트/클래스: 없음(함수형 셀렉터)
- 가정/불변 조건: SELECT 전용 쿼리만 수행
"""
from __future__ import annotations

from typing import List, Optional

from api.common.services.constants import LINE_SDWT_TABLE_NAME
from api.common.services.db import run_query


def _get_user_sdwt_prod_values(line_id: str) -> List[str]:
    """affiliation 테이블에서 line에 해당하는 user_sdwt_prod 목록을 조회합니다.

    입력:
    - line_id: 라인 식별자

    반환:
    - List[str]: 사용자 SDWT 값 목록(중복 제거)

    부작용:
    - DB 읽기 쿼리 수행

    오류:
    - 없음(쿼리 실패 시 상위 예외가 전파됨)
    """

    # -----------------------------------------------------------------------------
    # 1) DB 조회
    # -----------------------------------------------------------------------------
    rows = run_query(
        """
        SELECT DISTINCT user_sdwt_prod
        FROM {table}
        WHERE line = %s
          AND user_sdwt_prod IS NOT NULL
          AND user_sdwt_prod <> ''
        """.format(table=LINE_SDWT_TABLE_NAME),
        [line_id],
    )
    # -----------------------------------------------------------------------------
    # 2) 결과 정제
    # -----------------------------------------------------------------------------
    values: List[str] = []
    for row in rows:
        raw = row.get("user_sdwt_prod")
        if isinstance(raw, str):
            trimmed = raw.strip()
            if trimmed:
                values.append(trimmed)
    # -----------------------------------------------------------------------------
    # 3) 결과 반환
    # -----------------------------------------------------------------------------
    return values


def list_table_columns(table_name: str) -> List[str]:
    """현재 스키마에서 주어진 테이블의 컬럼 목록을 조회합니다.

    입력:
    - table_name: 테이블 이름

    반환:
    - List[str]: 컬럼 이름 목록

    부작용:
    - DB 읽기 쿼리 수행

    오류:
    - 없음(쿼리 실패 시 상위 예외가 전파됨)
    """

    # -----------------------------------------------------------------------------
    # 1) 정보 스키마 조회
    # -----------------------------------------------------------------------------
    rows = run_query(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND LOWER(table_name) = %s
        ORDER BY ordinal_position
        """,
        [table_name.lower()],
    )
    # -----------------------------------------------------------------------------
    # 2) 결과 정제
    # -----------------------------------------------------------------------------
    column_names: List[str] = []
    for row in rows:
        value: Optional[str] = None
        for key in ("column_name", "COLUMN_NAME", "Field"):
            raw = row.get(key)
            if isinstance(raw, str) and raw.strip():
                value = raw.strip()
                break
        if value:
            column_names.append(value)
    # -----------------------------------------------------------------------------
    # 3) 결과 반환
    # -----------------------------------------------------------------------------
    return column_names


__all__ = ["_get_user_sdwt_prod_values", "list_table_columns"]
