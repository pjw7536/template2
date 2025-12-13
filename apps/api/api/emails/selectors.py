from __future__ import annotations

from datetime import datetime
from typing import TypedDict

from django.contrib.auth import get_user_model
from django.db.models import Q, QuerySet
from django.utils import timezone

from api.account.selectors import (
    get_accessible_user_sdwt_prods_for_user as get_accessible_user_sdwt_prods_for_user,
)
from api.account.selectors import get_next_user_sdwt_prod_change as get_next_user_sdwt_prod_change
from api.account.selectors import list_distinct_user_sdwt_prod_values as list_distinct_user_sdwt_prod_values
from api.account.selectors import resolve_user_affiliation as resolve_user_affiliation
from api.common.affiliations import UNASSIGNED_USER_SDWT_PROD

from .models import Email


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


def _get_user_by_knox_id(sender_id: str):
    """sender_id(knox_id)로 User 모델을 조회합니다."""

    if not sender_id:
        return None

    UserModel = get_user_model()
    if not hasattr(UserModel, "knox_id"):
        return None

    return UserModel.objects.filter(knox_id=sender_id).first()


def resolve_email_affiliation(*, sender_id: str, received_at: datetime | None) -> EmailAffiliation:
    """이메일 발신자/수신 시각 기준으로 user_sdwt_prod 소속을 판별합니다.

    Determine the affiliation snapshot for an email based on sender and received time.

    Priority:
    - UserSdwtProdChange (approved, time-based)
    - User.user_sdwt_prod
    - UNASSIGNED_USER_SDWT_PROD fallback

    Args:
        sender_id: Parsed sender identifier (username/local-part).
        received_at: Email received time.

    Returns:
        Dict containing resolved user_sdwt_prod.

    Side effects:
        None. Read-only query.
    """

    when = _normalize_time(received_at)

    user = _get_user_by_knox_id(sender_id)
    if user is None:
        return {"user_sdwt_prod": UNASSIGNED_USER_SDWT_PROD}

    affiliation = resolve_user_affiliation(user, when)
    resolved = (affiliation.get("user_sdwt_prod") or "").strip()
    return {"user_sdwt_prod": resolved or UNASSIGNED_USER_SDWT_PROD}

def _unassigned_mailbox_query() -> Q:
    """UNASSIGNED(미분류) 메일함 조건(Q)을 반환합니다.

    Return a reusable Q object that matches unassigned mailboxes.

    Notes:
        We keep legacy fallbacks ("rp-unclassified", NULL/empty) so the policy
        works even before the normalization migration is applied.
    """

    return (
        Q(user_sdwt_prod__isnull=True)
        | Q(user_sdwt_prod__exact="")
        | Q(user_sdwt_prod=UNASSIGNED_USER_SDWT_PROD)
        | Q(user_sdwt_prod="rp-unclassified")
    )


def count_unassigned_emails_for_sender_id(*, sender_id: str) -> int:
    """발신자(sender_id)의 UNASSIGNED 메일 개수를 반환합니다.

    Return the count of UNASSIGNED emails for the given sender_id.

    Side effects:
        None. Read-only query.
    """

    if not isinstance(sender_id, str) or not sender_id.strip():
        return 0

    normalized = sender_id.strip()
    return (
        Email.objects.filter(sender_id=normalized)
        .filter(_unassigned_mailbox_query())
        .count()
    )


def list_unassigned_email_ids_for_sender_id(*, sender_id: str) -> list[int]:
    """발신자(sender_id)의 UNASSIGNED 메일 id 목록을 반환합니다.

    Return Email ids for UNASSIGNED emails of the sender_id.

    Side effects:
        None. Read-only query.
    """

    if not isinstance(sender_id, str) or not sender_id.strip():
        return []

    normalized = sender_id.strip()
    return list(
        Email.objects.filter(sender_id=normalized)
        .filter(_unassigned_mailbox_query())
        .order_by("id")
        .values_list("id", flat=True)
    )

def contains_unassigned_emails(*, email_ids: list[int]) -> bool:
    """email_ids 중 UNASSIGNED(미분류) 메일이 포함되는지 확인합니다.

    Return whether any of the given Email ids are UNASSIGNED.

    Side effects:
        None. Read-only query.
    """

    if not email_ids:
        return False

    return Email.objects.filter(id__in=email_ids).filter(_unassigned_mailbox_query()).exists()


def list_emails_by_ids(*, email_ids: list[int]) -> QuerySet[Email]:
    """Email id 목록으로 Email QuerySet을 조회합니다.

    Return Email queryset by ids.

    Side effects:
        None. Read-only query.
    """

    if not email_ids:
        return Email.objects.none()
    return Email.objects.filter(id__in=email_ids).order_by("id")


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
    can_view_unassigned: bool,
    mailbox_user_sdwt_prod: str,
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
        mailbox_user_sdwt_prod: When set, filter to the selected mailbox user_sdwt_prod.
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

    if not can_view_unassigned:
        queryset = queryset.exclude(_unassigned_mailbox_query())

    if mailbox_user_sdwt_prod:
        queryset = queryset.filter(user_sdwt_prod=mailbox_user_sdwt_prod)

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


def list_distinct_email_mailboxes() -> list[str]:
    """Email 테이블에서 중복 제거된 user_sdwt_prod 목록을 반환합니다.

    Return distinct mailbox(user_sdwt_prod) values present in the Email table.

    Returns:
        Sorted list of distinct, non-empty user_sdwt_prod strings.

    Side effects:
        None. Read-only query.
    """

    queryset = (
        Email.objects.exclude(user_sdwt_prod__isnull=True)
        .exclude(user_sdwt_prod="")
        .values_list("user_sdwt_prod", flat=True)
        .distinct()
        .order_by("user_sdwt_prod")
    )
    return list(queryset)


def list_privileged_email_mailboxes() -> list[str]:
    """특권 사용자(staff/superuser)가 볼 메일함(user_sdwt_prod) 목록을 반환합니다.

    Return mailbox(user_sdwt_prod) values for privileged users.

    Returns:
        Sorted list of known user_sdwt_prod values (including empty mailboxes).

    Side effects:
        None. Read-only query.
    """

    known = set(list_distinct_user_sdwt_prod_values())
    known.update(list_distinct_email_mailboxes())
    known.add(UNASSIGNED_USER_SDWT_PROD)
    return sorted({val for val in known if isinstance(val, str) and val.strip()})


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
