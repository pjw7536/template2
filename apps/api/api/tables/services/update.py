from __future__ import annotations

from typing import Any, Mapping

from api.common.constants import DEFAULT_TABLE
from api.common.utils import find_column, sanitize_identifier

from .. import selectors
from .types import TableRecordNotFoundError, TableUpdateResult
from .utils import _raise_if_table_missing


def update_table_record(*, payload: Mapping[str, Any]) -> TableUpdateResult:
    """테이블 레코드를 부분 업데이트합니다.

    Args:
        payload: request body 기반 데이터.

    Returns:
        업데이트 전/후 row 정보를 포함한 결과.

    Side effects:
        Executes UPDATE on the target table.
    """

    table_name = sanitize_identifier(payload.get("table"), DEFAULT_TABLE)
    if not table_name:
        raise ValueError("Invalid table name")

    record_id = payload.get("id")
    if record_id in (None, ""):
        raise ValueError("Record id is required")

    updates = payload.get("updates")
    if not isinstance(updates, dict):
        raise ValueError("Updates must be an object")

    allowed_update_columns = {"comment", "needtosend", "instant_inform", "status"}
    filtered = [
        (key, value)
        for key, value in updates.items()
        if key in allowed_update_columns and value is not None
    ]
    if not filtered:
        raise ValueError("No valid updates provided")

    try:
        column_names = selectors.list_columns(table_name=table_name)
    except Exception as exc:  # pragma: no cover - defensive handling
        _raise_if_table_missing(exc, table_name)
        raise

    id_column = find_column(column_names, "id")
    if not id_column:
        raise ValueError(f'Table "{table_name}" does not expose an id column')

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

    from api.tables import services as table_services

    try:
        affected, _ = table_services.execute(sql, params)
    except Exception as exc:  # pragma: no cover - defensive handling
        _raise_if_table_missing(exc, table_name)
        raise

    if affected == 0:
        raise TableRecordNotFoundError("Record not found")

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
    """컬럼별 업데이트 값 정규화."""

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
    """다양한 입력을 tinyint 스타일(0~127) 정수로 변환."""

    tiny_min, tiny_max = 0, 127

    def clamp(numeric: int) -> int:
        return max(tiny_min, min(tiny_max, int(numeric)))

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
    try:
        coerced = int(value)
        return clamp(coerced)
    except (TypeError, ValueError):
        return 0
