"""개발·테스트 seed용 normalized Drone delivery row 생성 서비스입니다."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from django.db import transaction

from ...models import DroneSOP, DroneSopDelivery
from .delivery_state import (
    prepare_channel_delivery_for_row,
    refresh_dispatch_statuses_for_delivery_ids,
)


def seed_drone_sop_delivery_rows(
    *,
    sop: DroneSOP,
    target_user_sdwt_prod: str | None,
    deliveries: Sequence[Mapping[str, Any]],
) -> None:
    """normalized target/channel delivery 목록을 명시적으로 저장합니다."""

    target_code = str(target_user_sdwt_prod or "").strip()
    if not sop.pk or not target_code or not deliveries:
        return

    source_row = {
        "id": int(sop.pk),
        "status": sop.status,
        "needtosend": sop.needtosend,
        "instant_inform": sop.instant_inform,
    }
    valid_channels = {choice for choice, _label in DroneSopDelivery.Channels.choices}
    valid_statuses = {choice for choice, _label in DroneSopDelivery.Statuses.choices}
    updated_delivery_ids: list[int] = []
    with transaction.atomic():
        for delivery_spec in deliveries:
            channel = delivery_spec.get("channel")
            status = delivery_spec.get("status")
            if channel not in valid_channels or status not in valid_statuses:
                raise ValueError("delivery channel/status is invalid")
            delivery = prepare_channel_delivery_for_row(
                row=source_row,
                target_user_sdwt_prod=target_code,
                channel=str(channel),
            )
            if delivery is None:
                continue
            delivery.status = str(status)
            delivery.reason = delivery_spec.get("reason")
            delivery.external_key = delivery_spec.get("externalKey")
            delivery.sent_step = delivery_spec.get("sentStep")
            delivery.sent_at = delivery_spec.get("sentAt")
            delivery.save(
                update_fields=[
                    "status",
                    "reason",
                    "external_key",
                    "sent_step",
                    "sent_at",
                    "updated_at",
                ]
            )
            updated_delivery_ids.append(int(delivery.id))
        refresh_dispatch_statuses_for_delivery_ids(delivery_ids=updated_delivery_ids)


__all__ = ["seed_drone_sop_delivery_rows"]
