from __future__ import annotations

from datetime import datetime
from typing import Optional, TypedDict

from django.contrib.auth import get_user_model
from django.utils import timezone

from api.common.affiliations import UNCLASSIFIED_USER_SDWT_PROD
from api.models import SenderSdwtHistory


class EmailAffiliation(TypedDict):
    user_sdwt_prod: str


def _normalize_time(value: Optional[datetime]) -> datetime:
    if value is None:
        return timezone.now()
    if timezone.is_naive(value):
        return timezone.make_aware(value, timezone.utc)
    return value


def _resolve_user_fields(sender_id: str) -> dict:
    UserModel = get_user_model()
    return (
        UserModel.objects.filter(username=sender_id)
        .values("user_sdwt_prod")
        .first()
        or {}
    )


def resolve_email_affiliation(sender_id: str, received_at: Optional[datetime]) -> EmailAffiliation:
    """
    Determine the affiliation snapshot for an email based on sender and received time.
    Priority:
    - SenderSdwtHistory의 user_sdwt_prod가 있으면 사용
    - 없으면 api.user.user_sdwt_prod 사용
    - 둘 다 없으면 rp-unclassified로 처리
    """
    when = _normalize_time(received_at)

    history = (
        SenderSdwtHistory.objects.filter(sender_id=sender_id, effective_from__lte=when)
        .order_by("-effective_from", "-id")
        .first()
    )
    user_fields = _resolve_user_fields(sender_id)
    user_user_sdwt_prod = user_fields.get("user_sdwt_prod") or ""
    fallback_user_sdwt = user_user_sdwt_prod or UNCLASSIFIED_USER_SDWT_PROD

    if history:
        return {
            "user_sdwt_prod": history.user_sdwt_prod or fallback_user_sdwt,
        }

    return {
        "user_sdwt_prod": fallback_user_sdwt,
    }
