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
def _observer_datetime(value: object) -> object:
    """Observer 문자열 시각을 DroneSOP DateTimeField 조회값으로 정규화합니다."""

    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = parse_datetime(str(value or ""))
    if parsed is None:
        return value
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed, timezone.get_default_timezone())
    return parsed


def _resolve_observer_esop_scope(eqp_id: str) -> tuple[str, tuple[str, ...]]:
    """Observer의 설비-챔버 ID를 기본 설비와 챔버 후보로 분리합니다.

    `-`는 설비와 챔버의 경계이며, 연속된 챔버 문자열은 문자별 챔버를
    의미합니다. 예를 들어 `EQP01-ABC`는 `EQP01`과 `A`, `B`, `C`로
    해석합니다.
    """

    normalized = str(eqp_id or "").strip().upper()
    if "-" not in normalized:
        return normalized, ()

    base_eqp, chamber_suffix = normalized.split("-", 1)
    chamber_candidates = tuple(
        dict.fromkeys(
            chamber
            for chamber in chamber_suffix
            if chamber and not chamber.isspace()
        )
    )
    return base_eqp, chamber_candidates


def _filter_observer_esop_scope(
    queryset: QuerySet[DroneSOP],
    *,
    eqp_id: str,
) -> QuerySet[DroneSOP]:
    """Observer 설비-챔버 범위에 해당하는 DroneSOP queryset을 반환합니다."""

    base_eqp, chamber_candidates = _resolve_observer_esop_scope(eqp_id)
    queryset = queryset.filter(eqp_id_lookup=base_eqp)
    if not chamber_candidates:
        return queryset

    chamber_filter = Q()
    for chamber in chamber_candidates:
        chamber_filter |= Q(chamber_ids__icontains=chamber)
    return queryset.filter(chamber_filter)


def fetch_drone_sop_timeline_page(
    *,
    eqp_id: str,
    start_at: object,
    end_at: object,
    page_size: int,
    cursor_time: object | None = None,
    cursor_id: int | None = None,
) -> tuple[list[dict[str, object]], bool]:
    """Observer ESOP compact log 한 페이지를 keyset 방식으로 반환합니다."""

    queryset = _filter_observer_esop_scope(
        DroneSOP.objects.filter(
            created_at__gte=_observer_datetime(start_at),
            created_at__lte=_observer_datetime(end_at),
        ),
        eqp_id=eqp_id,
    )
    normalized_cursor_time = (
        _observer_datetime(cursor_time) if cursor_time is not None else None
    )
    if normalized_cursor_time is not None and cursor_id is not None:
        queryset = queryset.filter(
            Q(created_at__lt=normalized_cursor_time)
            | Q(created_at=normalized_cursor_time, id__lt=cursor_id)
        )

    rows = list(
        queryset.order_by("-created_at", "-id")
        .values(
            "id",
            "sample_type",
            "created_at",
            "knox_id",
            "status",
            "comment",
            "line_id",
            "eqp_id",
            "chamber_ids",
            "lot_id",
        )[: page_size + 1]
    )
    has_more = len(rows) > page_size
    return rows[:page_size], has_more


def get_drone_sop_timeline_detail(
    *,
    eqp_id: str,
    source_id: int,
) -> dict[str, object] | None:
    """설비와 source PK가 일치하는 ESOP 상세 row를 반환합니다."""

    return (
        _filter_observer_esop_scope(
            DroneSOP.objects.filter(id=source_id),
            eqp_id=eqp_id,
        )
        .values(
            "id",
            "sample_type",
            "sample_group",
            "created_at",
            "updated_at",
            "knox_id",
            "status",
            "comment",
            "line_id",
            "sdwt_prod",
            "eqp_id",
            "chamber_ids",
            "lot_id",
            "proc_id",
            "ppid",
            "main_step",
            "metro_current_step",
            "metro_steps",
            "metro_end_step",
            "defect_url",
            "ctttm_urls",
        )
        .first()
    )
