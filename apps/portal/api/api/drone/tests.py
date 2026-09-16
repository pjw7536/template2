# =============================================================================
# 모듈: 드론 기능 테스트
# 주요 대상: POP3 파싱/업서트, Jira 생성, API 엔드포인트
# 주요 가정: 외부 호출은 mock으로 대체합니다.
# =============================================================================
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone as dt_timezone
from io import BytesIO, StringIO
from tempfile import NamedTemporaryFile
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock, patch

import requests
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection, IntegrityError, transaction
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext, override_settings
from django.urls import reverse
from django.utils import timezone

import api.account.services as account_services
from api.drone import selectors, services
from api.drone.models import (
    DroneEarlyInform,
    DroneSOP,
    DroneSopDelivery,
    DroneSopNeedToSendRule,
    DroneSopTarget,
    DroneSopTargetChannelConfig,
    DroneSopTargetDispatch,
    DroneSopTargetMapping,
    DroneSopTargetRecipient,
)
from api.drone.serializers import (
    DroneEarlyInformCreateSerializer,
    DroneEarlyInformUpdateFieldsSerializer,
    DroneNotificationTargetMappingCreateSerializer,
    DroneNotificationTargetMappingDeleteSerializer,
    DroneNotificationTargetMappingUpdateSerializer,
    serialize_drone_sop_target_configuration,
)
from api.drone.services.channels import recipients as recipient_services
from api.drone.services.channels import user_sdwt_channel as channel_services
from api.drone.services.jira.sop_jira import update_drone_sop_jira_status
from api.drone.services.pop3 import mailbox as pop3_mailbox
from api.drone.services.shared.delivery_state import (
    ensure_channel_delivery_snapshots_for_rows,
    filter_delivery_ids_for_config_failure,
    mark_channel_delivery_status,
)
from api.drone.services.shared.delivery_snapshot import build_sop_delivery_eligible_q, is_sop_delivery_eligible
from api.drone.services.shared.delivery_snapshot import summarize_sop_delivery_state
from api.drone.services.shared.notify_resolver import (
    load_user_sdwt_prod_map_index,
    resolve_target_user_sdwt_prods,
)
from api.drone.services.pop3.sop_pop3 import build_drone_sop_row, upsert_drone_sop_rows

_PREVIOUS_LOGGING_DISABLE: int | None = None


def setUpModule() -> None:
    """테스트 실행 중 로그 출력을 최소화합니다."""

    global _PREVIOUS_LOGGING_DISABLE
    _PREVIOUS_LOGGING_DISABLE = logging.root.manager.disable
    logging.disable(logging.CRITICAL)


def tearDownModule() -> None:
    """테스트 종료 후 로깅 설정을 복구합니다."""

    if _PREVIOUS_LOGGING_DISABLE is not None:
        logging.disable(_PREVIOUS_LOGGING_DISABLE)


def _allow_test_scope_access(test_case: TestCase) -> None:
    """도메인 endpoint 테스트에서 공통 portal/app 권한 경계를 격리합니다."""

    patcher = patch(
        "api.account.services.get_access_payload",
        return_value={"allowed": True},
    )
    patcher.start()
    test_case.addCleanup(patcher.stop)


def _ensure_target_mapping(
    *,
    sdwt_prod: str | None,
    user_sdwt_prod: str | None,
    target_user_sdwt_prod: str | None = None,
    needtosend_without_comment: bool = False,
) -> None:
    """테스트용 target_user_sdwt_prod 매핑을 생성합니다."""

    normalized_sdwt = sdwt_prod.strip() if isinstance(sdwt_prod, str) and sdwt_prod.strip() else None
    normalized_user = user_sdwt_prod.strip() if isinstance(user_sdwt_prod, str) and user_sdwt_prod.strip() else None
    resolved_target = target_user_sdwt_prod
    if not isinstance(resolved_target, str) or not resolved_target.strip():
        resolved_target = normalized_user or normalized_sdwt
    if not resolved_target:
        return

    target = services.get_or_create_drone_sop_target_by_name(target_user_sdwt_prod=resolved_target.strip())
    DroneSopTargetMapping.objects.create(
        sdwt_prod=normalized_sdwt,
        user_sdwt_prod=normalized_user,
        needtosend_without_comment=needtosend_without_comment,
        target=target,
    )


def _create_target_recipient(
    *,
    target_user_sdwt_prod: str,
    channel: str,
    user: Any | None = None,
    user_id: int | None = None,
    **kwargs: object,
) -> DroneSopTargetRecipient:
    """테스트용 target 수신인을 명시 FK 기준으로 생성합니다."""

    target = services.get_or_create_drone_sop_target_by_name(target_user_sdwt_prod=target_user_sdwt_prod)
    create_kwargs: dict[str, object] = {
        "target": target,
        "channel": channel,
        **kwargs,
    }
    if user is not None:
        create_kwargs["user"] = user
    if user_id is not None:
        create_kwargs["user_id"] = user_id
    return DroneSopTargetRecipient.objects.create(**create_kwargs)


def _upsert_target(**kwargs: object) -> DroneSopTarget:
    """테스트용 target row를 생성하거나 기존 row를 갱신합니다."""

    raw_target = kwargs.pop("target_user_sdwt_prod", None)
    if not isinstance(raw_target, str) or not raw_target.strip():
        raise ValueError("target_user_sdwt_prod is required")
    normalized_target = raw_target.strip()
    line_id = kwargs.pop("line_id", "")
    target = services.get_or_create_drone_sop_target_by_name(
        target_user_sdwt_prod=normalized_target,
        line_id=str(line_id or ""),
    )

    if line_id:
        target.line_id = str(line_id)
        target.save(update_fields=["line_id", "updated_at"])

    service_kwargs: dict[str, object] = {"target_user_sdwt_prod": normalized_target}
    service_kwargs.update(kwargs)
    if len(service_kwargs) > 1:
        services.upsert_drone_sop_user_sdwt_channel(**service_kwargs)

    return (
        DroneSopTarget.objects.prefetch_related("channel_configs", "needtosend_rule")
        .filter(target_user_sdwt_prod__iexact=normalized_target)
        .get()
    )


def _set_current_affiliation(user, *, user_sdwt_prod: str, department: str = "Dept", line: str = "Line") -> None:
    """테스트 사용자의 현재 앱 소속을 설정합니다."""

    account_services.set_current_affiliation_for_user(
        user=user,
        department=department,
        line=line,
        user_sdwt_prod=user_sdwt_prod,
    )


def _create_drone_sop(**overrides: object) -> DroneSOP:
    """테스트용 DroneSOP 기본 행을 생성합니다."""

    payload: dict[str, object] = {
        "line_id": "L1",
        "eqp_id": "EQP1",
        "chamber_ids": "1",
        "lot_id": "LOT.1",
        "main_step": "MS",
        "status": "COMPLETE",
        "needtosend": 1,
        "send_jira": 0,
    }
    payload.update(overrides)
    send_values = {
        channel: int(payload.pop(field_name, 0) or 0)
        for channel, field_name in (
            (DroneSopDelivery.Channels.JIRA, "send_jira"),
            (DroneSopDelivery.Channels.MESSENGER, "send_messenger"),
            (DroneSopDelivery.Channels.MAIL, "send_mail"),
        )
    }
    reason_values = {
        channel: payload.pop(field_name, None)
        for channel, field_name in (
            (DroneSopDelivery.Channels.JIRA, "jira_reason"),
            (DroneSopDelivery.Channels.MESSENGER, "messenger_reason"),
            (DroneSopDelivery.Channels.MAIL, "mail_reason"),
        )
    }
    external_key = payload.pop("jira_key", None)
    sent_step = payload.pop("inform_step", None)
    sent_at = payload.pop("informed_at", None)
    sop = DroneSOP.objects.create(**payload)
    resolved_targets = resolve_target_user_sdwt_prods(
        row={
            "sdwt_prod": sop.sdwt_prod,
            "user_sdwt_prod": sop.user_sdwt_prod,
            "target_user_sdwt_prod": sop.target_user_sdwt_prod,
        },
        index=load_user_sdwt_prod_map_index(),
    )
    target_code = next(
        (target.strip() for target in resolved_targets if isinstance(target, str) and target.strip()),
        str(sop.target_user_sdwt_prod or sop.user_sdwt_prod or sop.sdwt_prod or "").strip(),
    )
    deliveries = []
    for channel, numeric_status in send_values.items():
        deliveries.append(
            {
                "channel": channel,
                "status": (
                    DroneSopDelivery.Statuses.SUCCESS
                    if numeric_status > 0
                    else DroneSopDelivery.Statuses.FAILED
                    if numeric_status < 0
                    else DroneSopDelivery.Statuses.PENDING
                ),
                "reason": reason_values[channel] if numeric_status < 0 else None,
                "externalKey": external_key if channel == DroneSopDelivery.Channels.JIRA else None,
                "sentStep": sent_step,
                "sentAt": sent_at if numeric_status > 0 else None,
            }
        )
    services.seed_drone_sop_delivery_rows(
        sop=sop,
        target_user_sdwt_prod=target_code,
        deliveries=deliveries,
    )
    return sop


def _sop_delivery_value(sop: DroneSOP, field_name: str) -> object:
    """normalized delivery row의 표시 상태 한 필드를 반환합니다."""

    return summarize_sop_delivery_state(sop)[field_name]


def _target_configuration_value(target: DroneSopTarget, field_name: str) -> object:
    """normalized target 설정 응답의 한 필드를 반환합니다."""

    return serialize_drone_sop_target_configuration(target)[field_name]
