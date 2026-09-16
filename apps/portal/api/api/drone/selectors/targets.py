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
    serialize_drone_sop_target_configuration,
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
from ..services.shared.user_sdwt_overrides import list_engr_mapping_values_from_settings

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
def list_user_sdwt_prod_values_for_line(*, line_id: str) -> list[str]:
    """Drone 기준 line에 연결된 user_sdwt_prod 후보를 조회합니다.

    인자:
        line_id: 라인 ID.

    반환:
        user_sdwt_prod 문자열 리스트.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    normalized_line_id = normalize_text(line_id)
    if not normalized_line_id:
        return []

    values: list[Any] = []
    values.extend(
        DroneSopTarget.objects.filter(line_id__iexact=normalized_line_id)
        .exclude(target_user_sdwt_prod__isnull=True)
        .exclude(target_user_sdwt_prod__exact="")
        .values_list("target_user_sdwt_prod", flat=True)
        .distinct()
    )
    values.extend(
        DroneSopTargetMapping.objects.filter(target__line_id__iexact=normalized_line_id)
        .exclude(user_sdwt_prod__isnull=True)
        .exclude(user_sdwt_prod__exact="")
        .values_list("user_sdwt_prod", flat=True)
        .distinct()
    )
    values.extend(
        DroneSOP.objects.filter(line_id__iexact=normalized_line_id)
        .exclude(user_sdwt_prod__isnull=True)
        .exclude(user_sdwt_prod__exact="")
        .values_list("user_sdwt_prod", flat=True)
        .distinct()
    )
    values.extend(
        DroneSOP.objects.filter(line_id__iexact=normalized_line_id)
        .exclude(target_user_sdwt_prod__isnull=True)
        .exclude(target_user_sdwt_prod__exact="")
        .values_list("target_user_sdwt_prod", flat=True)
        .distinct()
    )
    return collapse_display_values(values)


def line_id_exists(*, line_id: str) -> bool:
    """Drone target 생성에 사용할 수 있는 line_id인지 확인합니다."""

    normalized_line_id = normalize_text(line_id)
    return bool(normalized_line_id)


def _derive_target_source(*, target_user_sdwt_prod: str) -> str:
    """Drone runtime에서는 명시 생성된 target을 custom source로 표시합니다."""

    return DroneSopTarget.Sources.CUSTOM


def list_drone_sop_notification_targets_for_line(*, line_id: str) -> list[dict[str, object]]:
    """라인별 Drone SOP 알림 target 목록을 조회합니다.

    실제 설정 소유권은 DroneSopTarget.line_id를 기준으로 판단합니다.

    인자:
        line_id: 라인 ID.

    반환:
        target 정보 dict 목록.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    normalized_line_id = normalize_text(line_id)
    if not normalized_line_id:
        return []

    targets_by_key: dict[str, dict[str, object]] = {}

    configured_rows = (
        DroneSopTarget.objects.filter(line_id__iexact=normalized_line_id)
        .exclude(target_user_sdwt_prod__isnull=True)
        .exclude(target_user_sdwt_prod__exact="")
        .prefetch_related("channel_configs", "needtosend_rule")
        .order_by("target_user_sdwt_prod", "id")
    )
    for row in configured_rows:
        target_value = normalize_text(row.target_user_sdwt_prod)
        if not target_value:
            continue
        configuration = serialize_drone_sop_target_configuration(row)
        targets_by_key[target_value.casefold()] = {
            "lineId": row.line_id or normalized_line_id,
            "targetUserSdwtProd": target_value,
            "source": _derive_target_source(target_user_sdwt_prod=target_value),
            "isConfigured": True,
            "jiraKey": configuration["jiraKey"],
            "jiraEnabled": configuration["jiraEnabled"],
            "messengerEnabled": configuration["messengerEnabled"],
            "mailEnabled": configuration["mailEnabled"],
        }

    for mapping in (
        DroneSopTargetMapping.objects.select_related("target")
        .exclude(target__target_user_sdwt_prod__isnull=True)
        .exclude(target__target_user_sdwt_prod__exact="")
        .order_by("sdwt_prod", "user_sdwt_prod", "id")
    ):
        target_value = normalize_text(mapping.target_user_sdwt_prod)
        target = targets_by_key.get(target_value.casefold())
        if target is None:
            continue
        mappings = target.setdefault("mappings", [])
        if isinstance(mappings, list):
            mappings.append(
                {
                    "sdwtProd": normalize_text(mapping.sdwt_prod),
                    "userSdwtProd": normalize_text(mapping.user_sdwt_prod),
                    "needtosendWithoutComment": bool(mapping.needtosend_without_comment),
                }
            )

    for target in targets_by_key.values():
        target.setdefault("mappings", [])

    return sorted(
        targets_by_key.values(),
        key=lambda item: (
            0 if item.get("isConfigured") else 1,
            str(item.get("targetUserSdwtProd") or "").casefold(),
        ),
    )


def _serialize_drone_sop_target_admin_row(target: DroneSopTarget) -> dict[str, object]:
    """DroneSopTarget admin row를 API 응답 형태로 변환합니다."""

    return {
        "id": target.id,
        "lineId": normalize_text(target.line_id) or "",
        "targetUserSdwtProd": normalize_text(target.target_user_sdwt_prod) or "",
        "mappingCount": int(getattr(target, "mapping_count", 0) or 0),
        "recipientCount": int(getattr(target, "recipient_count", 0) or 0),
        "channelConfigCount": int(getattr(target, "channel_config_count", 0) or 0),
        "dispatchCount": int(getattr(target, "dispatch_count", 0) or 0),
        "hasNeedToSendRule": bool(getattr(target, "needtosend_rule_count", 0) or 0),
        "createdAt": target.created_at.isoformat() if target.created_at else None,
        "updatedAt": target.updated_at.isoformat() if target.updated_at else None,
    }


def _drone_sop_target_admin_queryset() -> QuerySet[DroneSopTarget]:
    """admin target 목록용 annotation queryset을 구성합니다."""

    return DroneSopTarget.objects.annotate(
        mapping_count=Count("mappings", distinct=True),
        recipient_count=Count("recipients", distinct=True),
        channel_config_count=Count("channel_configs", distinct=True),
        dispatch_count=Count("sop_dispatches", distinct=True),
        needtosend_rule_count=Count("needtosend_rule", distinct=True),
    )


def list_drone_sop_target_admin_rows() -> list[dict[str, object]]:
    """Line Dashboard 관리자 화면용 Drone SOP target 목록을 반환합니다.

    반환:
        target row와 관련 설정 count 목록.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    rows = _drone_sop_target_admin_queryset().order_by("line_id", "target_user_sdwt_prod", "id")
    return [_serialize_drone_sop_target_admin_row(row) for row in rows]


def get_drone_sop_target_admin_row(*, target_id: int) -> dict[str, object] | None:
    """target id 기준 Line Dashboard 관리자 화면용 row를 반환합니다.

    인자:
        target_id: DroneSopTarget PK.

    반환:
        row dict 또는 None.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    target = _drone_sop_target_admin_queryset().filter(id=target_id).first()
    return _serialize_drone_sop_target_admin_row(target) if target is not None else None


def affiliation_exists_for_user_sdwt_prod(*, user_sdwt_prod: str) -> bool:
    """target_user_sdwt_prod에 대응하는 Drone target 존재 여부를 확인합니다.

    인자:
        user_sdwt_prod: target 식별자.

    반환:
        Drone target 존재 여부(bool).

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    normalized = normalize_text(user_sdwt_prod)
    if not normalized:
        return False
    return DroneSopTarget.objects.filter(target_user_sdwt_prod__iexact=normalized).exists()


def list_drone_sop_mapping_option_values_for_line(*, line_id: str) -> dict[str, list[str]]:
    """라인별 Drone target 기준 지정 조합 드롭다운 옵션을 조회합니다.

    인자:
        line_id: 라인 ID.

    반환:
        {"userSdwtProds": [...], "sdwtProds": [...]} 형태의 옵션 목록.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    normalized_line_id = normalize_text(line_id)
    if not normalized_line_id:
        return {"userSdwtProds": [], "sdwtProds": []}

    target_values = list(
        DroneSopTarget.objects.filter(line_id__iexact=normalized_line_id)
        .exclude(target_user_sdwt_prod__isnull=True)
        .exclude(target_user_sdwt_prod__exact="")
        .values_list("target_user_sdwt_prod", flat=True)
        .distinct()
    )
    options = collapse_display_values(target_values)
    return {
        "userSdwtProds": options,
        "sdwtProds": options,
    }


def list_drone_sop_mapping_option_lines() -> list[dict[str, object]]:
    """Drone target 기준 line별 지정 조합 드롭다운 옵션을 조회합니다.

    반환:
        [{"lineId": "...", "userSdwtProds": [...]}] 형태의 옵션 목록.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    rows = (
        DroneSopTarget.objects.exclude(line_id__isnull=True)
        .exclude(line_id__exact="")
        .exclude(target_user_sdwt_prod__isnull=True)
        .exclude(target_user_sdwt_prod__exact="")
        .values("line_id", "target_user_sdwt_prod")
        .distinct()
        .order_by("line_id", "target_user_sdwt_prod")
    )
    grouped: dict[str, list[str]] = {}
    for row in rows:
        line_id = normalize_text(row.get("line_id"))
        target_value = normalize_text(row.get("target_user_sdwt_prod"))
        if not line_id or not target_value:
            continue
        grouped.setdefault(line_id, []).append(target_value)

    option_lines = [
        {
            "lineId": line_id,
            "userSdwtProds": collapse_display_values(values),
        }
        for line_id, values in grouped.items()
    ]
    system_values = list_engr_mapping_values_from_settings()
    if system_values:
        option_lines.append(
            {
                "lineId": "System",
                "userSdwtProds": system_values,
            }
        )
    return option_lines


def get_tip_status_line_sdwt_options_payload() -> dict[str, object]:
    """TIP status 화면용 Drone target line/user_sdwt_prod 옵션을 반환합니다.

    반환:
        {"lines": [{"lineId": "...", "userSdwtProds": [...]}], "userSdwtProds": [...]} 형태.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    station_lookup_keys = station_master_selectors.list_distinct_sdwt_prod_lookup_values()
    if not station_lookup_keys:
        return {"lines": [], "userSdwtProds": []}

    rows = (
        DroneSopTarget.objects.exclude(line_id__isnull=True)
        .exclude(line_id__exact="")
        .exclude(target_user_sdwt_prod__isnull=True)
        .exclude(target_user_sdwt_prod__exact="")
        .values("line_id", "target_user_sdwt_prod")
        .distinct()
        .order_by("line_id", "target_user_sdwt_prod")
    )
    grouped: dict[str, list[str]] = {}
    all_values: list[str] = []
    for row in rows:
        line_id = normalize_text(row.get("line_id"))
        target_value = normalize_text(row.get("target_user_sdwt_prod"))
        if not line_id or not target_value:
            continue
        if target_value.strip().upper() not in station_lookup_keys:
            continue
        grouped.setdefault(line_id, []).append(target_value)
        all_values.append(target_value)

    return {
        "lines": [
            {
                "lineId": line_id,
                "userSdwtProds": collapse_display_values(values),
            }
            for line_id, values in grouped.items()
        ],
        "userSdwtProds": collapse_display_values(all_values),
    }


def list_drone_sop_target_user_sdwt_prod_values() -> list[str]:
    """Drone SOP 설정 대상 user_sdwt_prod 목록을 조회합니다.

    인자:
        없음.

    반환:
        대상 user_sdwt_prod 문자열 리스트.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) Drone runtime에서 확인 가능한 target 값을 병합
    # -----------------------------------------------------------------------------
    values: list[Any] = []
    values.extend(
        DroneSopTarget.objects.exclude(target_user_sdwt_prod="")
        .values_list("target_user_sdwt_prod", flat=True)
        .distinct()
    )
    values.extend(
        DroneSopTargetMapping.objects.exclude(target__target_user_sdwt_prod__isnull=True)
        .exclude(target__target_user_sdwt_prod="")
        .values_list("target__target_user_sdwt_prod", flat=True)
        .distinct()
    )
    values.extend(
        DroneSOP.objects.exclude(target_user_sdwt_prod__isnull=True)
        .exclude(target_user_sdwt_prod__exact="")
        .values_list("target_user_sdwt_prod", flat=True)
        .distinct()
    )
    return collapse_display_values(values)
