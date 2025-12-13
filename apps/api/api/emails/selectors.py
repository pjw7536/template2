from __future__ import annotations

from datetime import datetime
from typing import TypedDict

from django.contrib.auth import get_user_model
from django.db.models import Q, QuerySet
from django.utils import timezone

from api.account.selectors import get_accessible_user_sdwt_prods_for_user as get_accessible_user_sdwt_prods_for_user
from api.account.selectors import get_next_user_sdwt_prod_change as get_next_user_sdwt_prod_change
from api.account.selectors import resolve_user_affiliation as resolve_user_affiliation
from api.common.affiliations import UNCLASSIFIED_USER_SDWT_PROD

from .models import Email, SenderSdwtHistory


class EmailAffiliation(TypedDict):
    """이메일 발신자 소속 판별 결과(user_sdwt_prod)를 담는 타입입니다."""

    user_sdwt_prod: str


def _normalize_time(value: datetime | None) -> datetime:
    """datetime 값을 timezone-aware(UTC)로 정규화합니다."""

    if value is None:
        return timezone.now()
    if timezone.is_naive(value):
        return timezone.make_aware(value, timezone.utc)
    return value


def _resolve_user_fields(sender_id: str) -> dict:
    """sender_id로 User 모델에서 user_sdwt_prod 관련 필드를 조회합니다."""

    UserModel = get_user_model()
    if not sender_id:
        return {}

    if hasattr(UserModel, "knox_id"):
        matched = UserModel.objects.filter(knox_id=sender_id).values("user_sdwt_prod").first()
        if matched:
            return matched

    if hasattr(UserModel, "sabun"):
        return UserModel.objects.filter(sabun=sender_id).values("user_sdwt_prod").first() or {}

    return UserModel.objects.filter(username=sender_id).values("user_sdwt_prod").first() or {}


def resolve_email_affiliation(*, sender_id: str, received_at: datetime | None) -> EmailAffiliation:
    """이메일 발신자/수신 시각 기준으로 user_sdwt_prod 소속을 판별합니다.

    Determine the affiliation snapshot for an email based on sender and received time.

    Priority:
    - SenderSdwtHistory.user_sdwt_prod (if present)
    - User.user_sdwt_prod
    - UNCLASSIFIED_USER_SDWT_PROD fallback

    Args:
        sender_id: Parsed sender identifier (username/local-part).
        received_at: Email received time.

    Returns:
        Dict containing resolved user_sdwt_prod.

    Side effects:
        None. Read-only query.
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
        return {"user_sdwt_prod": history.user_sdwt_prod or fallback_user_sdwt}

    return {"user_sdwt_prod": fallback_user_sdwt}


def get_next_user_sdwt_prod_change_effective_from(
    *,
    user,
    effective_from: datetime,
) -> datetime | None:
    """effective_from 이후 예정된 다음 소속 변경 시각을 반환합니다.

    Return the next affiliation change timestamp after effective_from.

    Side effects:
        None. Read-only query.
    """

    when = _normalize_time(effective_from)
    change = get_next_user_sdwt_prod_change(user=user, effective_from=when)
    return change.effective_from if change else None


def get_filtered_emails(
    *,
    accessible_user_sdwt_prods: set[str],
    is_privileged: bool,
    search: str,
    sender: str,
    recipient: str,
    date_from: datetime | None,
    date_to: datetime | None,
) -> QuerySet[Email]:
    """검색/기간/발신자/수신자 조건으로 Email QuerySet을 필터링해 반환합니다.

    Return an Email queryset filtered by the provided criteria.

    Args:
        accessible_user_sdwt_prods: Allowed user_sdwt_prod values for the caller.
        is_privileged: When True, bypass user_sdwt_prod filtering.
        search: Free-text query (subject/body/sender).
        sender: Sender substring filter.
        recipient: Recipient substring filter.
        date_from: Minimum received_at (inclusive).
        date_to: Maximum received_at (inclusive).

    Returns:
        QuerySet ordered by newest first.

    Side effects:
        None. Read-only query.
    """

    queryset = Email.objects.order_by("-received_at", "-id")
    if not is_privileged:
        queryset = queryset.filter(user_sdwt_prod__in=accessible_user_sdwt_prods)

    if search:
        queryset = queryset.filter(
            Q(subject__icontains=search)
            | Q(body_text__icontains=search)
            | Q(sender__icontains=search)
        )
    if sender:
        queryset = queryset.filter(sender__icontains=sender)
    if recipient:
        queryset = queryset.filter(recipient__icontains=recipient)
    if date_from:
        queryset = queryset.filter(received_at__gte=date_from)
    if date_to:
        queryset = queryset.filter(received_at__lte=date_to)

    return queryset


def get_email_by_id(*, email_id: int) -> Email | None:
    """email_id로 Email을 조회하고 없으면 None을 반환합니다.

    Return the Email row for the given id.

    Args:
        email_id: Email primary key.

    Returns:
        Email instance when found, otherwise None.

    Side effects:
        None. Read-only query.
    """

    try:
        return Email.objects.get(id=email_id)
    except Email.DoesNotExist:
        return None


def user_can_bulk_delete_emails(
    *,
    email_ids: list[int],
    accessible_user_sdwt_prods: set[str],
) -> bool:
    """요청한 email_ids가 모두 접근 가능한 user_sdwt_prod 범위인지 검사합니다.

    Return whether all email_ids are within accessible_user_sdwt_prods.

    Args:
        email_ids: List of email IDs requested for deletion.
        accessible_user_sdwt_prods: Allowed user_sdwt_prod values for the caller.

    Returns:
        True when every requested id maps to an Email with user_sdwt_prod in the allowed set.

    Side effects:
        None. Read-only query.
    """

    if not email_ids:
        return False

    owned_count = Email.objects.filter(
        id__in=email_ids,
        user_sdwt_prod__in=accessible_user_sdwt_prods,
    ).count()
    return owned_count == len(email_ids)
