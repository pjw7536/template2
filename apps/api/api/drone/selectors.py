from __future__ import annotations

"""Read-only query helpers for the Drone feature (ORM + SQL mix)."""

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence

from django.db.models import QuerySet

from api.common.constants import DEFAULT_TABLE, DIMENSION_CANDIDATES, LINE_SDWT_TABLE_NAME
from api.common.db import run_query
from api.common.utils import (
    _get_user_sdwt_prod_values,
    build_date_range_filters,
    build_line_filters,
    ensure_date_bounds,
    find_column,
    normalize_date_only,
    normalize_line_id,
    resolve_table_schema,
    to_int,
)

from .models import DroneEarlyInformV3, DroneSOPV3


def list_early_inform_entries(*, line_id: str) -> QuerySet[DroneEarlyInformV3]:
    """조기 알림 설정을 라인 기준으로 조회합니다.

    Side effects:
        None. Read-only query.
    """

    return DroneEarlyInformV3.objects.filter(line_id=line_id).order_by("main_step", "id")


def get_early_inform_entry_by_id(*, entry_id: int) -> DroneEarlyInformV3 | None:
    """id로 조기 알림 설정을 조회합니다.

    Side effects:
        None. Read-only query.
    """

    return DroneEarlyInformV3.objects.filter(id=entry_id).first()


def load_drone_sop_custom_end_step_map() -> dict[tuple[str, str], str | None]:
    """(user_sdwt_prod, main_step) → custom_end_step 맵을 로드합니다.

    drone_early_inform_v3(line_id, main_step) 설정을 account_affiliation(line, user_sdwt_prod)와 조인해,
    Drone SOP 수집 시 custom_end_step 계산에 사용할 캐시 dict를 구성합니다.

    Side effects:
        None. Read-only query.
    """

    rows = run_query(
        """
        SELECT
            aff.user_sdwt_prod AS user_sdwt_prod,
            ei.main_step AS main_step,
            ei.custom_end_step AS custom_end_step
        FROM drone_early_inform_v3 AS ei
        JOIN {table} AS aff
          ON aff.line = ei.line_id
        """.format(table=LINE_SDWT_TABLE_NAME)
    )

    mapping: dict[tuple[str, str], str | None] = {}
    for row in rows:
        user_sdwt_prod = row.get("user_sdwt_prod")
        main_step = row.get("main_step")
        if not isinstance(user_sdwt_prod, str) or not isinstance(main_step, str):
            continue
        key = (user_sdwt_prod.strip(), main_step.strip())
        custom_end_step = row.get("custom_end_step")
        if custom_end_step is None:
            mapping[key] = None
        elif isinstance(custom_end_step, str):
            mapping[key] = custom_end_step.strip()
        else:
            mapping[key] = str(custom_end_step).strip()

    return mapping


def list_drone_sop_jira_candidates(*, limit: int | None = None) -> list[dict[str, Any]]:
    """Jira 전송 대상 DroneSOPV3 로우를 조회합니다.

    조건:
        - send_jira = 0
        - needtosend = 1
        - status = 'COMPLETE'

    Side effects:
        None. Read-only query.
    """

    qs = DroneSOPV3.objects.filter(send_jira=0, needtosend=1, status="COMPLETE").order_by("id")
    if isinstance(limit, int) and limit > 0:
        qs = qs[:limit]

    fields = [
        "id",
        "line_id",
        "sdwt_prod",
        "sample_type",
        "sample_group",
        "eqp_id",
        "chamber_ids",
        "lot_id",
        "proc_id",
        "ppid",
        "main_step",
        "metro_current_step",
        "metro_steps",
        "metro_end_step",
        "status",
        "knox_id",
        "user_sdwt_prod",
        "comment",
        "defect_url",
        "needtosend",
        "custom_end_step",
    ]

    return list(qs.values(*fields))


def list_user_sdwt_prod_values_for_line(*, line_id: str) -> list[str]:
    """라인 ID에 매핑되는 user_sdwt_prod 값을 조회합니다.

    Side effects:
        None. Read-only query.
    """

    return _get_user_sdwt_prod_values(line_id)


def list_line_ids_for_user_sdwt_prod(*, user_sdwt_prod: str) -> list[str]:
    """user_sdwt_prod에 매핑되는 line_id 목록을 조회합니다.

    Side effects:
        None. Read-only query.
    """

    if not isinstance(user_sdwt_prod, str) or not user_sdwt_prod.strip():
        return []

    rows = run_query(
        """
        SELECT DISTINCT line AS line_id
        FROM {table}
        WHERE user_sdwt_prod = %s
          AND line IS NOT NULL
          AND line <> ''
        ORDER BY line_id
        """.format(table=LINE_SDWT_TABLE_NAME),
        [user_sdwt_prod.strip()],
    )
    return [
        row["line_id"].strip()
        for row in rows
        if isinstance(row.get("line_id"), str) and row.get("line_id").strip()
    ]


def list_distinct_line_ids() -> list[str]:
    """사이드바 필터용 line_id 고유값 목록을 조회합니다.

    Side effects:
        None. Read-only query.
    """

    rows = run_query(
        """
        SELECT DISTINCT line AS line_id
        FROM {table}
        WHERE line IS NOT NULL AND line <> ''
        ORDER BY line_id
        """.format(table=LINE_SDWT_TABLE_NAME)
    )
    return [
        row["line_id"].strip()
        for row in rows
        if isinstance(row.get("line_id"), str) and row.get("line_id").strip()
    ]


def _normalize_bucket_value(value: Any) -> Optional[str]:
    """날짜/시간 버킷 값을 ISO-like 문자열로 정규화합니다."""

    if value is None:
        return None

    if isinstance(value, datetime):
        return value.replace(minute=0, second=0, microsecond=0).isoformat()

    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time()).isoformat()

    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None

        candidate = cleaned
        if " " in candidate and "T" not in candidate:
            candidate = candidate.replace(" ", "T")

        try:
            parsed = datetime.fromisoformat(candidate)
            return parsed.replace(minute=0, second=0, microsecond=0).isoformat()
        except ValueError:
            return cleaned

    return None


def get_line_history_payload(
    *,
    table_param: Any,
    line_id_param: Any,
    from_param: Any,
    to_param: Any,
    range_days_param: Any,
    default_range_days: int = 14,
) -> dict[str, Any]:
    """라인 대시보드 차트용 시간 단위 합계/분해 집계를 조회합니다.

    Side effects:
        None. Read-only query.
    """

    from_value = normalize_date_only(from_param)
    to_value = normalize_date_only(to_param)
    normalized_line_id = normalize_line_id(line_id_param)

    parsed_range = None
    if isinstance(range_days_param, str) and range_days_param.isdigit():
        parsed_range = int(range_days_param)
    range_days = parsed_range if parsed_range and parsed_range > 0 else default_range_days

    if not to_value:
        today = datetime.utcnow().date()
        to_value = today.isoformat()

    if not from_value and to_value:
        to_date = datetime.fromisoformat(f"{to_value}T00:00:00")
        from_date = to_date - timedelta(days=range_days - 1)
        from_value = from_date.date().isoformat()

    if from_value and to_value:
        from_value, to_value = ensure_date_bounds(from_value, to_value)

    schema = resolve_table_schema(
        table_param,
        default_table=DEFAULT_TABLE,
        require_timestamp=True,
    )
    table_name = schema.name
    column_names = schema.columns
    timestamp_column = schema.timestamp_column

    send_jira_column = find_column(column_names, "send_jira")
    dimension_columns = {
        candidate: resolved
        for candidate in DIMENSION_CANDIDATES
        if (resolved := find_column(column_names, candidate))
    }

    line_filter_result = build_line_filters(column_names, normalized_line_id)
    where_clause, query_params = _build_where_clause(
        timestamp_column,
        line_filter_result["filters"],
        line_filter_result["params"],
        from_value,
        to_value,
    )

    totals_rows = run_query(
        _build_totals_query(table_name, timestamp_column, send_jira_column, where_clause),
        query_params,
    )
    totals = [_normalize_daily_row(row) for row in totals_rows]

    breakdowns: Dict[str, List[Dict[str, Any]]] = {}
    for dimension_key, column_name in dimension_columns.items():
        rows = run_query(
            _build_breakdown_query(
                table_name,
                timestamp_column,
                column_name,
                send_jira_column,
                where_clause,
            ),
            query_params,
        )
        breakdowns[dimension_key] = [_normalize_breakdown_row(row) for row in rows]

    return {
        "table": table_name,
        "from": from_value,
        "to": to_value,
        "lineId": normalized_line_id,
        "timestampColumn": timestamp_column,
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "totals": totals,
        "breakdowns": breakdowns,
    }


def _build_where_clause(
    timestamp_column: str,
    line_filters: Sequence[str],
    line_params: Sequence[Any],
    from_value: Optional[str],
    to_value: Optional[str],
) -> tuple[str, List[Any]]:
    conditions = list(line_filters)
    params = list(line_params)

    date_conditions, date_params = build_date_range_filters(timestamp_column, from_value, to_value)
    conditions.extend(date_conditions)
    params.extend(date_params)

    clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    return clause, params


def _build_totals_query(
    table_name: str,
    timestamp_column: str,
    send_jira_column: Optional[str],
    where_clause: str,
) -> str:
    bucket_expr = f"DATE_TRUNC('hour', {timestamp_column})"
    totals_select = [f"{bucket_expr} AS bucket", "COUNT(*) AS row_count"]
    if send_jira_column:
        totals_select.append(
            "SUM(CASE WHEN {col} > 0 THEN 1 ELSE 0 END) AS send_jira_count".format(col=send_jira_column)
        )
    else:
        totals_select.append("0 AS send_jira_count")

    return """
        SELECT {select_clause}
        FROM {table}
        {where_clause}
        GROUP BY bucket
        ORDER BY bucket ASC
    """.format(
        select_clause=", ".join(totals_select),
        table=table_name,
        where_clause=where_clause,
    )


def _build_breakdown_query(
    table_name: str,
    timestamp_column: str,
    dimension_column: str,
    send_jira_column: Optional[str],
    where_clause: str,
) -> str:
    bucket_expr = f"DATE_TRUNC('hour', {timestamp_column})"
    select_parts = [
        f"{bucket_expr} AS bucket",
        f"COALESCE(CAST({dimension_column} AS TEXT), 'Unspecified') AS category",
        "COUNT(*) AS row_count",
    ]

    if send_jira_column:
        select_parts.append(
            "SUM(CASE WHEN {col} > 0 THEN 1 ELSE 0 END) AS send_jira_count".format(col=send_jira_column)
        )
    else:
        select_parts.append("0 AS send_jira_count")

    return """
        SELECT {select_clause}
        FROM {table}
        {where_clause}
        GROUP BY bucket, category
        ORDER BY bucket ASC, category ASC
    """.format(
        select_clause=", ".join(select_parts),
        table=table_name,
        where_clause=where_clause,
    )


def _normalize_daily_row(row: Dict[str, Any]) -> Dict[str, Any]:
    date_str = _normalize_bucket_value(row.get("bucket") or row.get("day") or row.get("date"))
    return {
        "date": date_str,
        "rowCount": to_int(row.get("row_count", 0)),
        "sendJiraCount": to_int(row.get("send_jira_count", 0)),
    }


def _normalize_breakdown_row(row: Dict[str, Any]) -> Dict[str, Any]:
    date_str = _normalize_bucket_value(row.get("bucket") or row.get("day") or row.get("date"))

    category = row.get("category") or row.get("dimension") or "Unspecified"
    if not isinstance(category, str) or not category.strip():
        category = "Unspecified"

    return {
        "date": date_str,
        "category": category.strip() if isinstance(category, str) else str(category),
        "rowCount": to_int(row.get("row_count", 0)),
        "sendJiraCount": to_int(row.get("send_jira_count", 0)),
    }
