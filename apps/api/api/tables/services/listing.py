from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Mapping

from api.common.constants import DEFAULT_TABLE
from api.common.utils import (
    build_date_range_filters,
    build_line_filters,
    ensure_date_bounds,
    normalize_date_only,
    normalize_line_id,
)

from .. import selectors
from .utils import _raise_if_table_missing

RECENT_HOURS_MIN = 0
RECENT_HOURS_DAY_STEP = 24
RECENT_HOURS_DAY_MODE_MIN_DAYS = 2
RECENT_HOURS_DAY_MODE_MAX_DAYS = 7
RECENT_HOURS_DAY_MODE_THRESHOLD = 24
RECENT_HOURS_MAX = RECENT_HOURS_DAY_MODE_MAX_DAYS * RECENT_HOURS_DAY_STEP
RECENT_HOURS_DEFAULT_START = 8
RECENT_HOURS_DEFAULT_END = 0
RECENT_FUTURE_TOLERANCE_MINUTES = 5


def _snap_recent_hours(value: int) -> int:
    """recentHours 값을 허용 범위/단위(일 단위)로 스냅(보정)합니다."""

    clamped = max(RECENT_HOURS_MIN, min(value, RECENT_HOURS_MAX))
    if clamped <= RECENT_HOURS_DAY_MODE_THRESHOLD:
        return clamped

    days = (clamped + RECENT_HOURS_DAY_STEP - 1) // RECENT_HOURS_DAY_STEP
    bounded_days = max(
        RECENT_HOURS_DAY_MODE_MIN_DAYS,
        min(days, RECENT_HOURS_DAY_MODE_MAX_DAYS),
    )
    return bounded_days * RECENT_HOURS_DAY_STEP


def _clamp_recent_hours(value: Any, fallback: int) -> int:
    """입력값을 정수로 파싱해 recentHours 규칙에 맞게 보정합니다."""

    try:
        numeric = int(value)
    except (TypeError, ValueError):
        numeric = fallback
    return _snap_recent_hours(numeric)


def _resolve_recent_hours_range(params: Mapping[str, Any]) -> tuple[int, int]:
    """쿼리 파라미터에서 recentHoursStart/End 범위를 계산합니다."""

    start = _clamp_recent_hours(params.get("recentHoursStart"), RECENT_HOURS_DEFAULT_START)
    end = _clamp_recent_hours(params.get("recentHoursEnd"), RECENT_HOURS_DEFAULT_END)
    if start < end:
        start = end
    return start, end


def get_table_list_payload(*, params: Mapping[str, Any]) -> dict[str, Any]:
    """테이블 조회 결과를 응답 payload로 구성합니다.

    Args:
        params: request.GET 기반 파라미터 맵.

    Returns:
        테이블 조회 응답 payload.

    Side effects:
        None. Read-only query.
    """

    from_param = normalize_date_only(params.get("from"))
    to_param = normalize_date_only(params.get("to"))
    normalized_line_id = normalize_line_id(params.get("lineId"))
    recent_hours_start, recent_hours_end = _resolve_recent_hours_range(params)

    if from_param and to_param:
        from_param, to_param = ensure_date_bounds(from_param, to_param)

    from api.tables import services as table_services

    schema = table_services.resolve_table_schema(
        params.get("table"),
        default_table=DEFAULT_TABLE,
        require_timestamp=True,
    )
    table_name = schema.name
    column_names = schema.columns
    base_ts_col = schema.timestamp_column

    line_filter_result = build_line_filters(column_names, normalized_line_id)
    where_parts = list(line_filter_result["filters"])
    query_params = list(line_filter_result["params"])

    now_utc = datetime.utcnow()
    recent_start_dt = now_utc - timedelta(hours=recent_hours_start)
    recent_end_dt = now_utc - timedelta(hours=recent_hours_end)
    recent_end_dt += timedelta(minutes=RECENT_FUTURE_TOLERANCE_MINUTES)

    where_parts.append(f"{base_ts_col} BETWEEN %s AND %s")
    query_params.append(recent_start_dt.strftime("%Y-%m-%d %H:%M:%S"))
    query_params.append(recent_end_dt.strftime("%Y-%m-%d %H:%M:%S"))

    date_conditions, date_params = build_date_range_filters(base_ts_col, from_param, to_param)
    where_parts.extend(date_conditions)
    query_params.extend(date_params)

    where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
    order_clause = f"ORDER BY {base_ts_col} DESC, id DESC"

    try:
        rows = selectors.fetch_rows(
            sql=(
                """
                SELECT *
                FROM {table}
                {where_clause}
                {order_clause}
                """
            ).format(table=table_name, where_clause=where_clause, order_clause=order_clause),
            params=query_params,
        )
    except Exception as exc:  # pragma: no cover - defensive handling
        _raise_if_table_missing(exc, table_name)
        raise

    return {
        "table": table_name,
        "cutoff": (
            "{col} BETWEEN NOW() - INTERVAL '{start} hours' AND NOW() - INTERVAL '{end} hours'"
        ).format(col=base_ts_col, start=recent_hours_start, end=recent_hours_end),
        "from": from_param or None,
        "to": to_param or None,
        "rowCount": len(rows),
        "columns": column_names,
        "rows": rows,
    }
