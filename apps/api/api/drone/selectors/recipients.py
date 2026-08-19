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
from .targets import _derive_target_source, list_drone_sop_target_user_sdwt_prod_values

def user_can_manage_drone_sop_recipients(*, user: Any) -> bool:
    """사용자가 Drone SOP 수신인 설정을 관리할 수 있는지 확인합니다.

    인자:
        user: Django 사용자 객체.

    반환:
        관리 가능 여부.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 초기 배포 혼선을 줄이기 위해 로그인 사용자는 알림 설정 변경을 허용
    # -----------------------------------------------------------------------------
    return bool(user and getattr(user, "is_authenticated", False))


def get_drone_sop_permission_context(*, user: Any) -> dict[str, object]:
    """프론트엔드에서 사용할 Drone SOP 권한 컨텍스트를 반환합니다.

    인자:
        user: Django 사용자 객체.

    반환:
        수신 설정 변경 가능 여부와 관리 가능한 target_user_sdwt_prod 목록.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    can_manage_recipients = user_can_manage_drone_sop_recipients(user=user)
    return {
        "canManageRecipients": can_manage_recipients,
        "manageableUserSdwtProds": (
            list_drone_sop_target_user_sdwt_prod_values() if can_manage_recipients else []
        ),
    }


def list_mail_receiver_emails_for_user_sdwt_prod(*, line_id: str, user_sdwt_prod: str) -> list[str]:
    """Drone SOP 메일 수신자 이메일 목록을 조회합니다.

    인자:
        line_id: 호환성을 위해 받는 라인 ID. 실제 수신인은 target 기준으로 조회합니다.
        user_sdwt_prod: 최종 알림 대상 소속 값.

    반환:
        이메일 주소 리스트.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    return _list_recipient_contact_values(
        target_user_sdwt_prod=user_sdwt_prod,
        channel=DroneSopTargetRecipient.Channels.MAIL,
        contact_field="email",
    )


def list_messenger_receiver_knox_ids_for_user_sdwt_prod(*, line_id: str, user_sdwt_prod: str) -> list[str]:
    """Drone SOP 메신저 수신자 knox_id 목록을 조회합니다.

    인자:
        line_id: 호환성을 위해 받는 라인 ID. 실제 수신인은 target 기준으로 조회합니다.
        user_sdwt_prod: 최종 알림 대상 소속 값.

    반환:
        knox_id 리스트.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    return _list_recipient_contact_values(
        target_user_sdwt_prod=user_sdwt_prod,
        channel=DroneSopTargetRecipient.Channels.MESSENGER,
        contact_field="knox_id",
    )


def _list_recipient_contact_values(
    *,
    target_user_sdwt_prod: str,
    channel: str,
    contact_field: str,
) -> list[str]:
    """채널 수신인에서 사용자 연락처 값을 중복 없이 조회합니다."""

    normalized = normalize_text(target_user_sdwt_prod)
    if not normalized:
        return []

    user_values = (
        DroneSopTargetRecipient.objects.filter(
            target__target_user_sdwt_prod__iexact=normalized,
            channel=channel,
            user__is_active=True,
        )
        .exclude(**{f"user__{contact_field}__isnull": True})
        .exclude(**{f"user__{contact_field}__exact": ""})
        .values_list(f"user__{contact_field}", flat=True)
        .order_by(f"user__{contact_field}")
        .distinct()
    )
    external_knox_ids = (
        DroneSopTargetRecipient.objects.filter(
            target__target_user_sdwt_prod__iexact=normalized,
            channel=channel,
            user__isnull=True,
        )
        .exclude(external_knox_id__exact="")
        .values_list("external_knox_id", flat=True)
        .order_by("external_knox_id")
        .distinct()
    )

    normalized_values: list[str] = []
    seen: set[str] = set()
    for value in user_values:
        cleaned = normalize_text(value)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        normalized_values.append(cleaned)
    for knox_id in external_knox_ids:
        cleaned_knox_id = normalize_text(knox_id)
        if not cleaned_knox_id:
            continue
        value = f"{cleaned_knox_id}@samsung.com" if contact_field == "email" else cleaned_knox_id
        if value in seen:
            continue
        seen.add(value)
        normalized_values.append(value)
    return normalized_values


def list_drone_sop_channel_recipients(
    *,
    line_id: str,
    target_user_sdwt_prod: str,
    channel: str,
) -> list[dict[str, object]]:
    """Drone SOP target/channel에 등록된 수신인을 조회합니다.

    커스텀 target_user_sdwt_prod를 허용하므로 외부 소속표 매핑은 요구하지 않습니다.

    인자:
        line_id: 호환성을 위해 받는 라인 ID. 실제 수신인은 target 기준으로 조회합니다.
        target_user_sdwt_prod: 최종 알림 대상 소속 값.
        channel: mail 또는 messenger.

    반환:
        사용자 정보가 포함된 수신인 dict 목록.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    normalized = normalize_text(target_user_sdwt_prod)
    if not normalized:
        return []

    target_row = get_drone_sop_channel_by_target_user_sdwt_prod(target_user_sdwt_prod=normalized)
    response_line_id = (target_row.line_id if target_row and target_row.line_id else normalize_text(line_id)) or ""

    rows = list(
        DroneSopTargetRecipient.objects.filter(
            target__target_user_sdwt_prod__iexact=normalized,
            channel=channel,
        )
        .filter(Q(user__is_active=True) | (Q(user__isnull=True) & ~Q(external_knox_id="")))
        .select_related("target", "user")
        .order_by(
            "user__username",
            "external_knox_id",
            "user_id",
            "id",
        )
    )
    affiliation_by_user_id = account_selectors.get_current_affiliation_values_by_user_ids(
        user_ids=[row.user_id for row in rows if row.user_id]
    )
    external_snapshot_by_knox_id = account_selectors.get_external_affiliation_snapshots_by_knox_lookup_keys(
        knox_ids=[row.external_knox_id for row in rows if row.user_id is None and row.external_knox_id]
    )

    recipients: list[dict[str, object]] = []
    for row in rows:
        if row.user_id is None:
            knox_id = normalize_text(row.external_knox_id)
            if not knox_id:
                continue
            snapshot = external_snapshot_by_knox_id.get(knox_id.lower())
            username = normalize_text(getattr(snapshot, "username", None))
            recipients.append(
                {
                    "id": row.id,
                    "userId": None,
                    "recipientType": "external",
                    "recipientKey": f"external:{knox_id.lower()}",
                    "externalKnoxId": knox_id,
                    "username": username,
                    "displayName": username or knox_id,
                    "sabun": "",
                    "knoxId": knox_id,
                    "email": f"{knox_id}@samsung.com",
                    "department": getattr(snapshot, "department", None) or "",
                    "line": "",
                    "userSdwtProd": getattr(snapshot, "predicted_user_sdwt_prod", None) or "",
                    "channel": row.channel,
                    "lineId": response_line_id,
                    "targetUserSdwtProd": row.target_user_sdwt_prod,
                }
            )
            continue
        user = row.user
        affiliation_values = affiliation_by_user_id.get(user.id, {})
        display_name = (
            getattr(user, "username", None)
            or getattr(user, "username_en", None)
            or getattr(user, "givenname", None)
            or getattr(user, "knox_id", None)
            or getattr(user, "sabun", None)
            or ""
        )
        recipients.append(
            {
                "id": row.id,
                "userId": user.id,
                "recipientType": "user",
                "recipientKey": f"user:{user.id}",
                "username": getattr(user, "username", None) or "",
                "displayName": display_name,
                "sabun": getattr(user, "sabun", None) or "",
                "knoxId": getattr(user, "knox_id", None) or "",
                "email": getattr(user, "email", None) or "",
                "department": affiliation_values.get("department") or "",
                "line": affiliation_values.get("line") or "",
                "userSdwtProd": affiliation_values.get("user_sdwt_prod") or "",
                "channel": row.channel,
                "lineId": response_line_id,
                "targetUserSdwtProd": row.target_user_sdwt_prod,
            }
        )
    return recipients


def list_drone_sop_recipient_targets_for_user(
    *,
    user: Any,
    line_id: str = "",
) -> list[dict[str, object]]:
    """현재 사용자가 수신인으로 등록된 target 목록을 조회합니다.

    인자:
        user: 조회 대상 Django 사용자 객체.
        line_id: 선택된 라인 ID. 비어 있으면 전체 라인을 조회합니다.

    반환:
        target별 등록 채널을 묶은 dict 목록.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    user_id = getattr(user, "id", None)
    if not user_id:
        return []

    normalized_line_id = normalize_text(line_id)
    queryset = (
        DroneSopTargetRecipient.objects.filter(
            user_id=user_id,
            target__target_user_sdwt_prod__isnull=False,
        )
        .exclude(target__target_user_sdwt_prod__exact="")
        .select_related("target")
        .prefetch_related("target__channel_configs")
        .order_by("target__line_id", "target__target_user_sdwt_prod", "channel", "id")
    )
    if normalized_line_id:
        queryset = queryset.filter(target__line_id__iexact=normalized_line_id)

    targets_by_key: dict[tuple[str, str], dict[str, object]] = {}
    for row in queryset:
        target = row.target
        target_value = normalize_text(target.target_user_sdwt_prod)
        if not target_value:
            continue
        response_line_id = normalize_text(target.line_id)
        key = (response_line_id.casefold(), target_value.casefold())
        configuration = serialize_drone_sop_target_configuration(target)
        target_payload = targets_by_key.setdefault(
            key,
            {
                "lineId": response_line_id,
                "targetUserSdwtProd": target_value,
                "channels": [],
                "source": _derive_target_source(target_user_sdwt_prod=target_value),
                "jiraEnabled": configuration["jiraEnabled"],
                "messengerEnabled": configuration["messengerEnabled"],
                "mailEnabled": configuration["mailEnabled"],
            },
        )
        channels = target_payload.get("channels")
        if isinstance(channels, list) and row.channel not in channels:
            channels.append(row.channel)

    return sorted(
        targets_by_key.values(),
        key=lambda item: (
            str(item.get("lineId") or "").casefold(),
            str(item.get("targetUserSdwtProd") or "").casefold(),
        ),
    )


def get_drone_sop_channel_by_target_user_sdwt_prod(
    *,
    target_user_sdwt_prod: str,
) -> DroneSopTarget | None:
    """target_user_sdwt_prod에 해당하는 채널 설정을 조회합니다.

    인자:
        target_user_sdwt_prod: 최종 사용자 소속 값.

    반환:
        DroneSopTarget 또는 None.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 유효성 확인
    # -----------------------------------------------------------------------------
    normalized = normalize_text(target_user_sdwt_prod)
    if not normalized:
        return None

    # -----------------------------------------------------------------------------
    # 2) 채널 설정 조회
    # -----------------------------------------------------------------------------
    return (
        DroneSopTarget.objects.filter(target_user_sdwt_prod__iexact=normalized)
        .prefetch_related("channel_configs", "needtosend_rule")
        .first()
    )


def list_drone_sop_jira_target_user_sdwt_prods() -> list[str]:
    """채널 설정에 등록된 target_user_sdwt_prod 목록을 조회합니다.

    반환:
        target_user_sdwt_prod 문자열 리스트.

    부작용:
        없음. 읽기 전용 조회입니다.

    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) target_user_sdwt_prod 목록 조회
    # -----------------------------------------------------------------------------
    rows = (
        DroneSopTarget.objects.exclude(target_user_sdwt_prod__isnull=True)
        .exclude(target_user_sdwt_prod__exact="")
        .values_list("target_user_sdwt_prod", flat=True)
        .distinct()
        .order_by("target_user_sdwt_prod")
    )

    # -----------------------------------------------------------------------------
    # 2) 공백 제거 및 반환
    # -----------------------------------------------------------------------------
    return normalize_text_list(rows)


def list_line_ids_for_user_sdwt_prod(*, user_sdwt_prod: str) -> list[str]:
    """Drone target/mapping/SOP 기준으로 user_sdwt_prod에 연결된 line_id를 조회합니다.

    인자:
        user_sdwt_prod: 사용자 소속 값.

    반환:
        line_id 문자열 리스트.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 검증
    # -----------------------------------------------------------------------------
    normalized = normalize_text(user_sdwt_prod)
    if not normalized:
        return []

    # -----------------------------------------------------------------------------
    # 2) Drone target, mapping, SOP 관측값 기준으로 line 후보 병합
    # -----------------------------------------------------------------------------
    values: list[Any] = []
    values.extend(
        DroneSopTarget.objects.filter(target_user_sdwt_prod__iexact=normalized)
        .exclude(line_id__isnull=True)
        .exclude(line_id__exact="")
        .values_list("line_id", flat=True)
        .distinct()
    )
    values.extend(
        DroneSopTargetMapping.objects.filter(
            Q(user_sdwt_prod__iexact=normalized) | Q(sdwt_prod__iexact=normalized),
        )
        .exclude(target__line_id__isnull=True)
        .exclude(target__line_id__exact="")
        .values_list("target__line_id", flat=True)
        .distinct()
    )
    values.extend(
        DroneSOP.objects.filter(
            Q(target_user_sdwt_prod__iexact=normalized)
            | Q(user_sdwt_prod__iexact=normalized)
            | Q(sdwt_prod__iexact=normalized),
        )
        .exclude(line_id__isnull=True)
        .exclude(line_id__exact="")
        .values_list("line_id", flat=True)
        .distinct()
    )
    return collapse_display_values(values)
