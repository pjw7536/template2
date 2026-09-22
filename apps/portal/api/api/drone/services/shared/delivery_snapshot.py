"""Drone SOP delivery snapshot 정규화 helper."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Sequence

from django.db.models import Q

from ...models import DroneSOP, DroneSopDelivery

DELIVERY_CHANNELS: tuple[str, ...] = (
    DroneSopDelivery.Channels.JIRA,
    DroneSopDelivery.Channels.MESSENGER,
    DroneSopDelivery.Channels.MAIL,
)


def normalize_string_value(value: Any) -> str | None:
    """문자열 값을 공백 제거 기준으로 정규화합니다."""

    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned if cleaned else None
    cleaned = str(value).strip()
    return cleaned if cleaned else None


def normalize_lookup_key(value: Any) -> str | None:
    """대소문자 비구분 비교용 문자열 키를 생성합니다."""

    cleaned = normalize_string_value(value)
    if not cleaned:
        return None
    return cleaned.casefold()


def normalize_int_flag(value: Any) -> int:
    """숫자 플래그 값을 정수 상태로 정규화합니다."""

    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def is_sop_delivery_eligible(row: dict[str, Any]) -> bool:
    """SOP가 delivery snapshot 생성 대상인지 확인합니다."""

    if normalize_int_flag(row.get("instant_inform")) == 1:
        return True
    return normalize_int_flag(row.get("needtosend")) == 1 and str(row.get("status") or "").strip() == "COMPLETE"


def build_sop_delivery_eligible_q() -> Q:
    """SOP delivery 생성 대상 조회 조건을 반환합니다."""

    return Q(needtosend=1, status="COMPLETE") | Q(instant_inform=1)


def extract_sop_id(row: dict[str, Any]) -> int | None:
    """row에서 양의 정수 SOP ID를 추출합니다."""

    raw_id = row.get("id")
    if isinstance(raw_id, int) and raw_id > 0:
        return raw_id
    return None


def extract_row_targets(row: dict[str, Any]) -> list[str]:
    """row에 포함된 target snapshot 값을 target 목록으로 정규화합니다."""

    raw_targets = row.get("target_user_sdwt_prods")
    candidates: list[Any]
    if isinstance(raw_targets, list):
        candidates = raw_targets
    else:
        candidates = [row.get("target_user_sdwt_prod")]

    targets: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        target = normalize_string_value(candidate)
        target_key = normalize_lookup_key(target)
        if not target or not target_key or target_key in seen:
            continue
        seen.add(target_key)
        targets.append(target)
    return targets


def append_unique_target(*, target_list: list[str], target: str) -> None:
    """target 목록에 대소문자 비구분 중복 없이 추가합니다."""

    target_key = normalize_lookup_key(target)
    if not target_key:
        return
    if any(normalize_lookup_key(existing) == target_key for existing in target_list):
        return
    target_list.append(target)


def normalize_channels(channels: Sequence[str]) -> list[str]:
    """허용 delivery 채널만 중복 없이 정규화합니다."""

    normalized: list[str] = []
    for channel in channels:
        if channel in DELIVERY_CHANNELS and channel not in normalized:
            normalized.append(channel)
    return normalized


def _summarize_channel_deliveries(
    delivery_rows: Sequence[DroneSopDelivery],
) -> tuple[int, str | None]:
    """한 채널의 normalized delivery row를 숫자 상태와 사유로 요약합니다."""

    if not delivery_rows:
        return 0, None
    blocked_statuses = {
        DroneSopDelivery.Statuses.FAILED,
        DroneSopDelivery.Statuses.CANCELLED,
    }
    blocked_reason = next(
        (row.reason for row in delivery_rows if row.status in blocked_statuses and row.reason),
        None,
    )
    if blocked_reason or any(row.status in blocked_statuses for row in delivery_rows):
        return -1, blocked_reason
    if any(
        row.status in {DroneSopDelivery.Statuses.PENDING, DroneSopDelivery.Statuses.SENDING}
        for row in delivery_rows
    ):
        return 0, None
    if any(row.status == DroneSopDelivery.Statuses.SUCCESS for row in delivery_rows):
        return 1, None
    return 0, next((row.reason for row in delivery_rows if row.reason), None)


def summarize_sop_delivery_state(sop: DroneSOP) -> dict[str, object]:
    """SOP의 normalized delivery row를 표시·검증용 상태로 투영합니다."""

    prefetched = getattr(sop, "_prefetched_objects_cache", {}).get("channel_deliveries")
    if prefetched is None:
        rows = list(sop.channel_deliveries.order_by("id")) if sop.pk else []
    else:
        rows = sorted(list(prefetched), key=lambda row: row.id or 0)

    rows_by_channel = {
        channel: [row for row in rows if row.channel == channel]
        for channel in DELIVERY_CHANNELS
    }
    channel_state = {
        channel: _summarize_channel_deliveries(channel_rows)
        for channel, channel_rows in rows_by_channel.items()
    }
    successful_jira = next(
        (
            row
            for row in rows_by_channel[DroneSopDelivery.Channels.JIRA]
            if row.status == DroneSopDelivery.Statuses.SUCCESS
        ),
        None,
    )
    successful_sent_at: list[datetime] = [
        row.sent_at
        for row in rows
        if row.status == DroneSopDelivery.Statuses.SUCCESS and row.sent_at is not None
    ]
    return {
        "sendJira": channel_state[DroneSopDelivery.Channels.JIRA][0],
        "sendMessenger": channel_state[DroneSopDelivery.Channels.MESSENGER][0],
        "sendMail": channel_state[DroneSopDelivery.Channels.MAIL][0],
        "jiraReason": channel_state[DroneSopDelivery.Channels.JIRA][1],
        "messengerReason": channel_state[DroneSopDelivery.Channels.MESSENGER][1],
        "mailReason": channel_state[DroneSopDelivery.Channels.MAIL][1],
        "jiraKey": successful_jira.external_key if successful_jira else None,
        "informStep": successful_jira.sent_step if successful_jira else None,
        "informedAt": min(successful_sent_at) if successful_sent_at else None,
    }


__all__ = [
    "DELIVERY_CHANNELS",
    "append_unique_target",
    "build_sop_delivery_eligible_q",
    "extract_row_targets",
    "extract_sop_id",
    "is_sop_delivery_eligible",
    "normalize_channels",
    "normalize_lookup_key",
    "normalize_string_value",
    "summarize_sop_delivery_state",
]
