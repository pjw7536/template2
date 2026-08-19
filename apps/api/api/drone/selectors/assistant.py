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
def _filter_assistant_line_scope(
    queryset: QuerySet[DroneSOP],
    *,
    line_id: str,
    line_filter_mode: str,
) -> QuerySet[DroneSOP]:
    """표 API와 동일한 line 직접 소속·target 매핑 범위를 적용합니다."""

    direct_line_filter = Q(line_id__iexact=line_id)
    if line_filter_mode == LINE_FILTER_MODE_TARGET_USER_SDWT:
        target_values = (
            DroneSopTarget.objects.filter(line_id__iexact=line_id)
            .exclude(target_user_sdwt_prod="")
            .annotate(assistant_target_value=Lower("target_user_sdwt_prod"))
            .values("assistant_target_value")
        )
        return queryset.annotate(assistant_row_target=Lower("target_user_sdwt_prod")).filter(
            direct_line_filter
            | Q(assistant_row_target__in=Subquery(target_values))
        )

    mapping_field = {
        LINE_FILTER_MODE_USER_SDWT: "user_sdwt_prod",
        LINE_FILTER_MODE_SDWT: "sdwt_prod",
    }.get(line_filter_mode)
    if mapping_field is None:
        raise ValueError("지원하지 않는 ESOP line 필터 모드입니다.")
    mapping_values = (
        DroneSopTargetMapping.objects.filter(target__line_id__iexact=line_id)
        .exclude(**{f"{mapping_field}__isnull": True})
        .exclude(**{mapping_field: ""})
        .annotate(assistant_mapping_value=Lower(mapping_field))
        .values("assistant_mapping_value")
    )
    return queryset.annotate(assistant_row_mapping=Lower(mapping_field)).filter(
        direct_line_filter | Q(assistant_row_mapping__in=Subquery(mapping_values))
    )


def get_line_dashboard_assistant_snapshot(
    *,
    line_id: str,
    view: str,
    from_value: str,
    to_value: str,
    line_filter_mode: str | None,
    recent_hours_start: int | None,
    recent_hours_end: int | None,
) -> dict[str, object]:
    """ChatWidget용 ESOP 상태·이력 집계를 개인정보 없이 조회합니다.

    잘못된 화면·날짜·line·최근 시간 조건에는 ValueError를 발생시키며,
    DroneSOP를 변경하지 않고 읽기 전용으로 조회합니다.
    """

    normalized_line_id, start_date, end_date, recent_range = (
        normalize_line_dashboard_assistant_options(
            line_id=line_id,
            view=view,
            from_value=from_value,
            to_value=to_value,
            line_filter_mode=line_filter_mode,
            recent_hours_start=recent_hours_start,
            recent_hours_end=recent_hours_end,
            current_time=timezone.now() if view == "status" else None,
        )
    )

    queryset = DroneSOP.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date,
    )
    if view == "status":
        queryset = _filter_assistant_line_scope(
            queryset,
            line_id=normalized_line_id,
            line_filter_mode=line_filter_mode,
        ).filter(created_at__range=recent_range)
    else:
        queryset = queryset.filter(line_id__iexact=normalized_line_id)

    status_rows = list(
        queryset.values("status")
        .annotate(count=Count("id"))
        .order_by("-count", "status")[:20]
    )
    daily_rows = list(
        queryset.annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(
            count=Count("id"),
            need_to_send_count=Count("id", filter=Q(needtosend__gt=0)),
            instant_inform_count=Count("id", filter=Q(instant_inform__gt=0)),
        )
        .order_by("day")
    )
    recent_rows = list(
        queryset.order_by("-created_at", "-id").values(
            "id",
            "created_at",
            "line_id",
            "status",
            "eqp_id",
            "chamber_ids",
            "lot_id",
            "main_step",
            "sample_type",
            "needtosend",
            "instant_inform",
        )[:LINE_DASHBOARD_ASSISTANT_RECENT_ROWS]
    )
    return serialize_line_dashboard_assistant_snapshot(
        view=view,
        line_id=normalized_line_id,
        start_date=start_date,
        end_date=end_date,
        generated_at=timezone.now(),
        total_count=queryset.count(),
        status_rows=status_rows,
        daily_rows=daily_rows,
        recent_rows=recent_rows,
        line_filter_mode=line_filter_mode,
        recent_hours_start=recent_hours_start,
        recent_hours_end=recent_hours_end,
    )
