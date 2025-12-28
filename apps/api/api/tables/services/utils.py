# =============================================================================
# 모듈 설명: tables 서비스용 예외 보정 유틸을 제공합니다.
# - 주요 함수: _raise_if_table_missing
# - 불변 조건: DB 오류 코드를 기반으로 테이블 누락 여부를 판별합니다.
# =============================================================================

from __future__ import annotations

from .types import TableNotFoundError


def _raise_if_table_missing(exc: Exception, table_name: str) -> None:
    """테이블 누락 오류를 감지해 TableNotFoundError로 변환합니다.

    입력:
    - exc: 발생한 예외
    - table_name: 대상 테이블 이름

    반환:
    - 없음

    부작용:
    - TableNotFoundError를 발생시킬 수 있음

    오류:
    - TableNotFoundError: 테이블이 없을 때
    """
    # -----------------------------------------------------------------------------
    # 1) DB 오류 코드 확인
    # -----------------------------------------------------------------------------
    error_code = getattr(exc, "code", None) or getattr(exc, "pgcode", None)
    # -----------------------------------------------------------------------------
    # 2) 테이블 누락 예외 변환
    # -----------------------------------------------------------------------------
    if error_code in {"ER_NO_SUCH_TABLE", "42P01"}:
        raise TableNotFoundError(table_name=table_name) from exc
