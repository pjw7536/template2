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
from .early_inform import _drone_sop_eligible_filter

def list_drone_sop_user_sdwt_maps() -> list[dict[str, Any]]:
    """드론 SOP 사용자 매핑 규칙 목록을 조회합니다.

    반환:
        매핑 규칙 dict 리스트.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 매핑 규칙 조회
    # -----------------------------------------------------------------------------
    rows = DroneSopTargetMapping.objects.values(
        "sdwt_prod",
        "user_sdwt_prod",
        "target__target_user_sdwt_prod",
        "needtosend_without_comment",
    ).order_by("id")
    return [
        {
            "sdwt_prod": row.get("sdwt_prod"),
            "user_sdwt_prod": row.get("user_sdwt_prod"),
            "target_user_sdwt_prod": row.get("target__target_user_sdwt_prod"),
            "needtosend_without_comment": bool(row.get("needtosend_without_comment")),
        }
        for row in rows
    ]


def get_drone_sop_needtosend_rule_by_target(
    *,
    target_user_sdwt_prod: str,
) -> DroneSopNeedToSendRule | None:
    """target_user_sdwt_prod 기준 needtosend 채널 설정을 조회합니다.

    인자:
        target_user_sdwt_prod: 대상 소속 문자열.

    반환:
        needtosend 설정이 있는 DroneSopNeedToSendRule 또는 None.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 정규화
    # -----------------------------------------------------------------------------
    normalized = normalize_text(target_user_sdwt_prod, allow_non_str=True)
    if not normalized:
        return None

    # -----------------------------------------------------------------------------
    # 2) 채널 설정의 needtosend 규칙 조회
    # -----------------------------------------------------------------------------
    return (
        DroneSopNeedToSendRule.objects.select_related("target")
        .filter(
            target__target_user_sdwt_prod__iexact=normalized,
            enabled=True,
        )
        .order_by("id")
        .first()
    )


def list_drone_sop_user_sdwt_channels_by_targets(
    *,
    target_user_sdwt_prod_values: set[str] | list[str],
) -> dict[str, dict[str, str | bool | int | None]]:
    """target_user_sdwt_prod별 채널 설정 맵을 조회합니다.

    인자:
        target_user_sdwt_prod_values: target_user_sdwt_prod 집합 또는 리스트.

    반환:
        {target_user_sdwt_prod: {jira_key, chatroom_id, force_new_chatroom, jira_template_key, mail_template_key, messenger_template_key, *_enabled, *_configured}} 형태의 dict.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 정규화
    # -----------------------------------------------------------------------------
    normalized_targets = normalize_lookup_text_list(target_user_sdwt_prod_values)
    if not normalized_targets:
        return {}

    # -----------------------------------------------------------------------------
    # 2) 채널 설정 조회 및 매핑 구성
    # -----------------------------------------------------------------------------
    rows = (
        DroneSopTarget.objects.annotate(target_user_sdwt_prod_lookup=Lower("target_user_sdwt_prod"))
        .filter(target_user_sdwt_prod_lookup__in=normalized_targets)
        .prefetch_related("channel_configs")
    )
    mapping: dict[str, dict[str, str | bool | int | None]] = {}
    for row in rows:
        target_lookup = normalize_lookup_text(row.target_user_sdwt_prod)
        if not target_lookup:
            continue
        config_by_channel = {config.channel: config for config in row.channel_configs.all()}
        jira_config = config_by_channel.get(DroneSopTargetChannelConfig.Channels.JIRA)
        messenger_config = config_by_channel.get(DroneSopTargetChannelConfig.Channels.MESSENGER)
        mail_config = config_by_channel.get(DroneSopTargetChannelConfig.Channels.MAIL)
        chatroom_id = normalize_chatroom_id(messenger_config.chatroom_id if messenger_config else None)
        mapping[target_lookup] = {
            "jira_key": normalize_text(jira_config.jira_project_key if jira_config else None),
            "chatroom_id": chatroom_id,
            "force_new_chatroom": bool(messenger_config.force_new_chatroom) if messenger_config else False,
            "jira_template_key": normalize_text(jira_config.template_key if jira_config else None),
            "mail_template_key": normalize_text(mail_config.template_key if mail_config else None),
            "messenger_template_key": normalize_text(messenger_config.template_key if messenger_config else None),
            "jira_enabled": bool(jira_config.enabled) if jira_config else True,
            "messenger_enabled": bool(messenger_config.enabled) if messenger_config else True,
            "mail_enabled": bool(mail_config.enabled) if mail_config else True,
            "jira_configured": jira_config is not None,
            "messenger_configured": messenger_config is not None,
            "mail_configured": mail_config is not None,
        }
    return mapping


def load_drone_sop_custom_end_step_map() -> dict[tuple[str, str], str | None]:
    """(user_sdwt_prod, main_step) → custom_end_step 맵을 로드합니다.

    drone_early_inform(line_id, main_step) 설정을 Drone target/관측 소속과 조인해,
    Drone SOP 수집 시 custom_end_step 계산에 사용할 캐시 dict를 구성합니다.

    반환:
        {(user_sdwt_prod, main_step): custom_end_step} 형태의 dict.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 조기 알림 + Drone runtime 소속 후보 조인 조회
    # -----------------------------------------------------------------------------
    rows = run_query(
        """
        SELECT
            candidate.user_sdwt_prod AS user_sdwt_prod,
            ei.main_step AS main_step,
            ei.custom_end_step AS custom_end_step
        FROM drone_early_inform AS ei
        JOIN (
            SELECT line_id, target_user_sdwt_prod AS user_sdwt_prod
            FROM drone_sop_target
            WHERE line_id IS NOT NULL
              AND line_id <> ''
              AND target_user_sdwt_prod IS NOT NULL
              AND target_user_sdwt_prod <> ''
            UNION
            SELECT line_id, user_sdwt_prod
            FROM drone_sop
            WHERE line_id IS NOT NULL
              AND line_id <> ''
              AND user_sdwt_prod IS NOT NULL
              AND user_sdwt_prod <> ''
            UNION
            SELECT target.line_id, mapping.user_sdwt_prod
            FROM drone_sop_target_mapping AS mapping
            JOIN drone_sop_target AS target
              ON target.id = mapping.target_id
            WHERE target.line_id IS NOT NULL
              AND target.line_id <> ''
              AND mapping.user_sdwt_prod IS NOT NULL
              AND mapping.user_sdwt_prod <> ''
        ) AS candidate
          ON LOWER(candidate.line_id) = LOWER(ei.line_id)
        """
    )

    # -----------------------------------------------------------------------------
    # 2) 결과 매핑 구성
    # -----------------------------------------------------------------------------
    mapping: dict[tuple[str, str], str | None] = {}
    for row in rows:
        user_sdwt_prod = row.get("user_sdwt_prod")
        main_step = row.get("main_step")
        if not isinstance(user_sdwt_prod, str) or not isinstance(main_step, str):
            continue
        normalized_user_sdwt_prod = normalize_lookup_text(user_sdwt_prod)
        normalized_main_step = main_step.strip()
        if not normalized_user_sdwt_prod or not normalized_main_step:
            continue
        key = (normalized_user_sdwt_prod, normalized_main_step)
        custom_end_step = row.get("custom_end_step")
        if custom_end_step is None:
            mapping[key] = None
        elif isinstance(custom_end_step, str):
            mapping[key] = custom_end_step.strip()
        else:
            mapping[key] = str(custom_end_step).strip()

    return mapping


def _drone_sop_jira_candidates_queryset() -> QuerySet[DroneSOP]:
    """Jira 전송 대상 DroneSOP 기본 QuerySet을 구성합니다.

    반환:
        DroneSOP QuerySet.

    부작용:
        없음. 읽기 전용 조회 조건만 생성합니다.
    """

    pending_delivery = DroneSopDelivery.objects.filter(
        sop_id=OuterRef("pk"),
        channel=DroneSopDelivery.Channels.JIRA,
        status=DroneSopDelivery.Statuses.PENDING,
    )
    existing_delivery = DroneSopDelivery.objects.filter(
        sop_id=OuterRef("pk"),
        channel=DroneSopDelivery.Channels.JIRA,
    )
    needs_snapshot = ~Q(has_delivery=True)
    return (
        DroneSOP.objects.annotate(
            has_pending_delivery=Exists(pending_delivery),
            has_delivery=Exists(existing_delivery),
        )
        .filter(Q(has_pending_delivery=True) | needs_snapshot)
        .filter(_drone_sop_eligible_filter())
    )


def _drone_sop_pipeline_candidates_queryset() -> QuerySet[DroneSOP]:
    """고정 3채널 기준 DroneSOP 후보 QuerySet을 구성합니다."""

    pending_delivery = DroneSopDelivery.objects.filter(
        sop_id=OuterRef("pk"),
        status=DroneSopDelivery.Statuses.PENDING,
    )
    existing_delivery = DroneSopDelivery.objects.filter(sop_id=OuterRef("pk"))
    needs_snapshot = ~Q(has_delivery=True)
    return (
        DroneSOP.objects.annotate(
            has_pending_delivery=Exists(pending_delivery),
            has_delivery=Exists(existing_delivery),
        )
        .filter(Q(has_pending_delivery=True) | needs_snapshot)
        .filter(_drone_sop_eligible_filter())
    )


def _list_candidate_rows(
    *,
    queryset: QuerySet[DroneSOP],
    fields: Sequence[str],
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """대상 QuerySet에서 후보 row를 공통 방식으로 조회합니다."""

    ordered = queryset.order_by("id")
    if isinstance(limit, int) and limit > 0:
        ordered = ordered[:limit]
    return list(ordered.values(*fields))


def list_drone_sop_jira_candidates(*, limit: int | None = None) -> list[dict[str, Any]]:
    """Jira 전송 대상 DroneSOP 로우를 조회합니다.

    조건:
        - Jira delivery pending 또는 delivery snapshot 미생성 row
        - (needtosend = 1 & status = 'COMPLETE') 또는 instant_inform = 1

    인자:
        limit: 최대 조회 건수(옵션).

    반환:
        DroneSOP row dict 리스트.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    return _list_candidate_rows(
        queryset=_drone_sop_jira_candidates_queryset(),
        fields=_DRONE_SOP_JIRA_CANDIDATE_FIELDS,
        limit=limit,
    )


def list_drone_sop_pipeline_candidates(
    *,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """고정 3채널 기준 DroneSOP 후보 row 목록을 조회합니다.

    인자:
        limit: 최대 조회 건수(옵션).

    반환:
        DroneSOP row dict 리스트.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    queryset = _drone_sop_pipeline_candidates_queryset()
    return _list_candidate_rows(
        queryset=queryset,
        fields=_DRONE_SOP_PIPELINE_CANDIDATE_FIELDS,
        limit=limit,
    )


def list_drone_sop_channel_delivery_rows_by_sop_ids(*, sop_ids: Sequence[int]) -> dict[int, list[dict[str, Any]]]:
    """SOP ID별 채널 delivery row 목록을 조회합니다.

    인자:
        sop_ids: DroneSOP ID 목록.

    반환:
        {sop_id: [delivery row dict, ...]} 형태의 dict.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 ID 정규화
    # -----------------------------------------------------------------------------
    normalized_ids: list[int] = []
    seen: set[int] = set()
    for raw_id in sop_ids:
        if not isinstance(raw_id, int) or raw_id <= 0 or raw_id in seen:
            continue
        seen.add(raw_id)
        normalized_ids.append(raw_id)
    if not normalized_ids:
        return {}

    # -----------------------------------------------------------------------------
    # 2) SOP별 최초 target의 delivery row만 조회합니다.
    # -----------------------------------------------------------------------------
    rows = (
        DroneSopDelivery.objects.filter(sop_id__in=normalized_ids)
        .order_by("sop_id", "id")
        .values(
            "id",
            "sop_id",
            "dispatch_id",
            "dispatch__target_code_snapshot",
            "dispatch__status",
            "dispatch__comment_override",
            "channel",
            "status",
            "reason",
            "external_key",
            "sent_comment",
            "sent_step",
            "sent_at",
            "updated_at",
        )
    )

    # -----------------------------------------------------------------------------
    # 3) API row에 붙이기 쉬운 camelCase payload로 변환
    # -----------------------------------------------------------------------------
    grouped: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        sop_id = row.get("sop_id")
        if not isinstance(sop_id, int):
            continue
        target_user_sdwt_prod = display_delivery_target(row.get("dispatch__target_code_snapshot"))
        if not target_user_sdwt_prod:
            continue
        grouped.setdefault(sop_id, []).append(
            {
                "id": row.get("id"),
                "sopId": sop_id,
                "dispatchId": row.get("dispatch_id"),
                "targetUserSdwtProd": target_user_sdwt_prod,
                "dispatchStatus": row.get("dispatch__status"),
                "commentOverride": row.get("dispatch__comment_override"),
                "channel": row.get("channel"),
                "status": row.get("status"),
                "reason": row.get("reason"),
                "externalKey": row.get("external_key"),
                "sentComment": row.get("sent_comment"),
                "sentStep": row.get("sent_step"),
                "sentAt": row.get("sent_at"),
                "updatedAt": row.get("updated_at"),
            }
        )
    return grouped


def has_drone_sop_jira_candidates() -> bool:
    """Jira 전송 대상 DroneSOP가 존재하는지 확인합니다.

    조건:
        - Jira delivery pending 또는 delivery snapshot 미생성 row
        - (needtosend = 1 & status = 'COMPLETE') 또는 instant_inform = 1

    반환:
        존재 여부(boolean).

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 대상 쿼리 구성
    # -----------------------------------------------------------------------------
    qs = _drone_sop_jira_candidates_queryset()

    # -----------------------------------------------------------------------------
    # 2) 존재 여부 반환
    # -----------------------------------------------------------------------------
    return qs.exists()


def has_drone_sop_pipeline_candidates() -> bool:
    """고정 3채널 기준 DroneSOP 후보 존재 여부를 확인합니다."""

    qs = _drone_sop_pipeline_candidates_queryset()
    return qs.exists()


def load_drone_sop_ctttm_latest_workorders_by_eqp_ids(
    *,
    eqp_ids: Sequence[str],
    ctttm_table: str,
) -> dict[str, dict[str, str]]:
    """CTTTM 테이블에서 eqp_id별 최신 workorder 정보를 조회합니다.

    인자:
        eqp_ids: CTTTM 조회 대상 eqp_id 목록.
        ctttm_table: CTTTM 테이블명.

    반환:
        {eqp_id: {"eqp_id": "...", "workorder_id": "...", "line_id": "..."}} 형태의 dict.

    부작용:
        없음. 읽기 전용 조회입니다.

    오류:
        테이블명이 허용된 패턴이 아니면 ValueError를 발생시킵니다.
    """

    if not eqp_ids:
        return {}
    if connection.vendor != "postgresql":
        return {}

    raw_table_name = str(ctttm_table or "").strip()
    if not raw_table_name:
        return {}
    table_name = sanitize_identifier(raw_table_name)
    if not table_name:
        raise ValueError("CTTTM table name must match ^[A-Za-z0-9_]+$")

    normalized_eqp_ids = sorted(
        {
            str(eqp_id).strip()
            for eqp_id in eqp_ids
            if isinstance(eqp_id, str) and str(eqp_id).strip()
        }
    )
    if not normalized_eqp_ids:
        return {}

    rows = run_query(
        """
        SELECT DISTINCT ON (eqp_id)
            eqp_id,
            workorder_id,
            line_id
        FROM {ctttm_table}
        WHERE eqp_id = ANY(%s)
        ORDER BY eqp_id, inprg_date DESC
        """.format(ctttm_table=table_name),
        [normalized_eqp_ids],
    )

    mapping: dict[str, dict[str, str]] = {}
    for row in rows:
        eqp_id = str(row.get("eqp_id") or "").strip()
        workorder_id = str(row.get("workorder_id") or "").strip()
        line_id = str(row.get("line_id") or "").strip()
        if not eqp_id or not workorder_id or not line_id:
            continue
        mapping[eqp_id] = {
            "eqp_id": eqp_id,
            "workorder_id": workorder_id,
            "line_id": line_id,
        }
    return mapping
