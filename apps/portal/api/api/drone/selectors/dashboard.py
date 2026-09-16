# =============================================================================
# 모듈 설명: Line Dashboard·Drone 읽기 전용 selector 책임 모듈입니다.
# =============================================================================
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Sequence

from django.db import connection
from django.db.models import Count, Exists, OuterRef, Q, QuerySet, Subquery
from django.db.models.functions import Lower, TruncDate
from django.utils import timezone
from django.utils.dateparse import parse_datetime

import api.account.selectors as account_selectors
from api.common.services.db import run_query
from api.data_movement.station_master import selectors as station_master_selectors

from ..models import (
    DroneEarlyInform,
    DroneSOP,
    DroneSopDelivery,
    DroneSopNeedToSendRule,
    DroneSopTarget,
    DroneSopTargetChannelConfig,
    DroneSopTargetMapping,
    DroneSopTargetRecipient,
)
from ..serializers import (
    collapse_display_values,
    display_delivery_target,
    normalize_chatroom_id,
    normalize_lookup_text,
    normalize_lookup_text_list,
    normalize_line_dashboard_assistant_options,
    normalize_text,
    normalize_text_list,
    serialize_line_dashboard_assistant_snapshot,
)
from ..services.table_schema import (
    DEFAULT_TABLE,
    LINE_FILTER_MODE_SDWT,
    LINE_FILTER_MODE_TARGET_USER_SDWT,
    LINE_FILTER_MODE_USER_SDWT,
    build_line_filters,
    ensure_date_bounds,
    find_column,
    normalize_date_only,
    normalize_line_id,
    resolve_table_schema,
    sanitize_identifier,
)
from ..services.history.payload import (
    build_breakdown_query,
    build_totals_query,
    build_where_clause,
    normalize_breakdown_row,
    normalize_daily_row,
)
from ..services.shared.delivery_snapshot import build_sop_delivery_eligible_q

_DRONE_SOP_COMMON_CANDIDATE_FIELDS = (
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
    "target_user_sdwt_prod",
    "comment",
    "defect_url",
    "ctttm_urls",
    "needtosend",
    "instant_inform",
    "custom_end_step",
)
_DRONE_SOP_JIRA_CANDIDATE_FIELDS = _DRONE_SOP_COMMON_CANDIDATE_FIELDS
_DRONE_SOP_PIPELINE_CANDIDATE_FIELDS = _DRONE_SOP_COMMON_CANDIDATE_FIELDS

_DIMENSION_CANDIDATES = [
    "sdwt_prod",
    "proc_id",
    "ppid",
    "user_sdwt_prod",
    "eqp_id",
    "main_step",
    "sample_type",
    "line_id",
]

LINE_DASHBOARD_ASSISTANT_RECENT_ROWS = 20
def list_distinct_line_ids() -> list[str]:
    """사이드바 필터용 Drone target line_id 고유값 목록을 조회합니다.

    반환:
        line_id 문자열 리스트.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    values = (
        DroneSopTarget.objects.exclude(line_id__isnull=True)
        .exclude(line_id__exact="")
        .values_list("line_id", flat=True)
        .distinct()
    )
    return collapse_display_values(values)


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

    인자:
        table_param: 테이블 파라미터.
        line_id_param: 라인 ID 파라미터.
        from_param: 시작 날짜 파라미터.
        to_param: 종료 날짜 파라미터.
        range_days_param: 기간 일수 파라미터.
        default_range_days: 기본 기간 일수.

    반환:
        라인 히스토리 집계 payload dict.

    부작용:
        없음. 읽기 전용 조회입니다.

    오류:
        테이블/컬럼 검증 실패 시 ValueError/LookupError가 발생할 수 있습니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 날짜/라인 파라미터 정규화
    # -----------------------------------------------------------------------------
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

    # -----------------------------------------------------------------------------
    # 2) 테이블 스키마/컬럼 해석
    # -----------------------------------------------------------------------------
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
        for candidate in _DIMENSION_CANDIDATES
        if (resolved := find_column(column_names, candidate))
    }

    # -----------------------------------------------------------------------------
    # 3) WHERE 절 구성
    # -----------------------------------------------------------------------------
    line_filter_result = build_line_filters(column_names, normalized_line_id)
    where_clause, query_params = build_where_clause(
        timestamp_column=timestamp_column,
        line_filters=line_filter_result["filters"],
        line_params=line_filter_result["params"],
        from_value=from_value,
        to_value=to_value,
    )

    # -----------------------------------------------------------------------------
    # 4) 합계(총합) 조회
    # -----------------------------------------------------------------------------
    totals_rows = run_query(
        build_totals_query(
            table_name=table_name,
            timestamp_column=timestamp_column,
            send_jira_column=send_jira_column,
            where_clause=where_clause,
        ),
        query_params,
    )
    totals = [normalize_daily_row(row) for row in totals_rows]

    # -----------------------------------------------------------------------------
    # 5) 분해(차원별) 조회
    # -----------------------------------------------------------------------------
    breakdowns: Dict[str, List[Dict[str, Any]]] = {}
    for dimension_key, column_name in dimension_columns.items():
        rows = run_query(
            build_breakdown_query(
                table_name=table_name,
                timestamp_column=timestamp_column,
                dimension_column=column_name,
                send_jira_column=send_jira_column,
                where_clause=where_clause,
            ),
            query_params,
        )
        breakdowns[dimension_key] = [normalize_breakdown_row(row) for row in rows]

    # -----------------------------------------------------------------------------
    # 6) 응답 payload 구성
    # -----------------------------------------------------------------------------
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
