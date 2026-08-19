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
def _drone_sop_eligible_filter() -> Q:
    """Drone SOP 후보 공통 적합 조건 필터를 반환합니다."""

    return build_sop_delivery_eligible_q()


def list_early_inform_entries(*, line_id: str) -> QuerySet[DroneEarlyInform]:
    """조기 알림 설정을 라인 기준으로 조회합니다.

    인자:
        line_id: 라인 ID.

    반환:
        DroneEarlyInform QuerySet(조기 알림 목록).

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    return DroneEarlyInform.objects.filter(line_id=line_id).order_by("main_step", "id")


def get_early_inform_entry_for_update(*, entry_id: int) -> DroneEarlyInform | None:
    """조기 알림 엔트리를 행 잠금(select_for_update)으로 조회합니다.

    인자:
        entry_id: DroneEarlyInform ID.

    반환:
        DroneEarlyInform 인스턴스 또는 None.

    부작용:
        없음. 호출 측 트랜잭션에서 행 잠금이 발생합니다.

    오류:
        없음.
    """

    if entry_id <= 0:
        return None
    return DroneEarlyInform.objects.select_for_update().filter(id=entry_id).first()


def get_drone_sop_for_update(*, sop_id: int) -> DroneSOP | None:
    """DroneSOP 엔트리를 행 잠금(select_for_update)으로 조회합니다.

    인자:
        sop_id: DroneSOP ID.

    반환:
        DroneSOP 인스턴스 또는 None.

    부작용:
        없음. 호출 측 트랜잭션에서 행 잠금이 발생합니다.

    오류:
        없음.
    """

    if sop_id <= 0:
        return None
    return DroneSOP.objects.select_for_update().filter(id=sop_id).first()
