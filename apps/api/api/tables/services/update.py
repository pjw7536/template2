# =============================================================================
# 모듈 설명: tables 레코드 부분 업데이트 로직을 제공합니다.
# - 주요 함수: update_table_record, _normalize_update_value, _coerce_smallint_flag
# - 불변 조건: 허용된 컬럼만 업데이트하며 id 컬럼이 존재해야 합니다.
# =============================================================================

from __future__ import annotations

from typing import Any, Mapping

from api.common.constants import DEFAULT_TABLE
from api.common.utils import find_column, sanitize_identifier

from .. import selectors
from .types import TableRecordNotFoundError, TableUpdateResult
from .utils import _raise_if_table_missing

# =============================================================================
# 상수: 업데이트 허용 컬럼
# =============================================================================
ALLOWED_UPDATE_COLUMNS = {"comment", "needtosend", "instant_inform", "status"}


def update_table_record(*, payload: Mapping[str, Any]) -> TableUpdateResult:
    """테이블 레코드를 부분 업데이트합니다.

    입력:
    - payload: 요청 바디 기반 데이터(table, id, updates 포함)

    반환:
    - TableUpdateResult: 업데이트 전/후 row 정보를 포함한 결과

    부작용:
    - 대상 테이블 UPDATE 수행

    오류:
    - ValueError: 입력 값/컬럼 조건이 유효하지 않을 때
    - TableRecordNotFoundError: 대상 레코드가 없을 때
    - TableNotFoundError: 테이블이 존재하지 않을 때
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 파싱 및 기본 검증
    # -----------------------------------------------------------------------------
    table_name = sanitize_identifier(payload.get("table"), DEFAULT_TABLE)
    if not table_name:
        raise ValueError("Invalid table name")

    record_id = payload.get("id")
    if record_id in (None, ""):
        raise ValueError("Record id is required")

    updates = payload.get("updates")
    if not isinstance(updates, dict):
        raise ValueError("Updates must be an object")

    filtered = [
        (key, value)
        for key, value in updates.items()
        if key in ALLOWED_UPDATE_COLUMNS and value is not None
    ]
    if not filtered:
        raise ValueError("No valid updates provided")

    # -----------------------------------------------------------------------------
    # 2) 컬럼 스키마 확인
    # -----------------------------------------------------------------------------
    try:
        column_names = selectors.list_columns(table_name=table_name)
    except Exception as exc:  # 방어적 처리: pragma: no cover
        _raise_if_table_missing(exc, table_name)
        raise

    id_column = find_column(column_names, "id")
    if not id_column:
        raise ValueError(f'Table "{table_name}" does not expose an id column')

    # -----------------------------------------------------------------------------
    # 3) 기존 레코드 조회
    # -----------------------------------------------------------------------------
    previous_row = selectors.fetch_row(
        sql=(
            """
            SELECT *
            FROM {table}
            WHERE {id_column} = %s
            LIMIT 1
            """
        ).format(table=table_name, id_column=id_column),
        params=[record_id],
    )

    # -----------------------------------------------------------------------------
    # 4) UPDATE 구문 구성
    # -----------------------------------------------------------------------------
    assignments: list[str] = []
    params: list[Any] = []

    for key, value in filtered:
        column_name = find_column(column_names, key)
        if not column_name:
            continue
        assignments.append(f"{column_name} = %s")
        params.append(_normalize_update_value(key, value))

    if not assignments:
        raise ValueError("No matching columns to update")

    params.append(record_id)
    sql = (
        """
        UPDATE {table}
        SET {assignments}
        WHERE {id_column} = %s
        """
    ).format(table=table_name, assignments=", ".join(assignments), id_column=id_column)

    # -----------------------------------------------------------------------------
    # 5) UPDATE 실행
    # -----------------------------------------------------------------------------
    from api.tables import services as table_services

    try:
        affected, _ = table_services.execute(sql, params)
    except Exception as exc:  # 방어적 처리: pragma: no cover
        _raise_if_table_missing(exc, table_name)
        raise

    if affected == 0:
        raise TableRecordNotFoundError("Record not found")

    # -----------------------------------------------------------------------------
    # 6) 갱신 결과 조회 및 반환
    # -----------------------------------------------------------------------------
    updated_row = selectors.fetch_row(
        sql=(
            """
            SELECT *
            FROM {table}
            WHERE {id_column} = %s
            LIMIT 1
            """
        ).format(table=table_name, id_column=id_column),
        params=[record_id],
    )

    return TableUpdateResult(
        table_name=table_name,
        previous_row=previous_row,
        updated_row=updated_row,
    )


def _normalize_update_value(key: str, value: Any) -> Any:
    """컬럼별 업데이트 값을 정규화합니다.

    입력:
    - key: 업데이트 대상 컬럼 키
    - value: 원본 입력 값

    반환:
    - Any: 정규화된 값

    부작용:
    - 없음

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 컬럼 키별 값 변환 규칙 적용
    # -----------------------------------------------------------------------------
    if key == "comment":
        return "" if value is None else str(value)
    if key == "needtosend":
        return _coerce_smallint_flag(value)
    if key == "instant_inform":
        return _coerce_smallint_flag(value)
    if key == "status":
        return "" if value is None else str(value)
    return value


def _coerce_smallint_flag(value: Any) -> int:
    """다양한 입력을 tinyint 스타일(0~127) 정수로 변환합니다.

    입력:
    - value: 변환 대상 값

    반환:
    - int: 0~127 범위의 정수

    부작용:
    - 없음

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 범위 상수 정의
    # -----------------------------------------------------------------------------
    tiny_min, tiny_max = 0, 127

    def clamp(numeric: int) -> int:
        return max(tiny_min, min(tiny_max, int(numeric)))

    # -----------------------------------------------------------------------------
    # 2) 입력 타입별 변환
    # -----------------------------------------------------------------------------
    if isinstance(value, bool):
        return 1 if value else 0
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return clamp(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "t", "y", "yes"}:
            return 1
        if normalized in {"0", "false", "f", "n", "no", ""}:
            return 0
        try:
            parsed = int(float(normalized))
            return clamp(parsed)
        except (TypeError, ValueError):
            return 0
    # -----------------------------------------------------------------------------
    # 3) 기타 타입 최종 캐스팅
    # -----------------------------------------------------------------------------
    try:
        coerced = int(value)
        return clamp(coerced)
    except (TypeError, ValueError):
        return 0
