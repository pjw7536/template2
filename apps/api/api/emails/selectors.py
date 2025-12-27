from __future__ import annotations

from datetime import datetime
from typing import Any, TypedDict

from django.contrib.auth import get_user_model
from django.db.models import Count, Q, QuerySet
from django.utils import timezone

from api.account import selectors as account_selectors
from api.account.selectors import list_distinct_user_sdwt_prod_values
from api.common.affiliations import UNASSIGNED_USER_SDWT_PROD

from .models import Email, EmailOutbox


class EmailAffiliation(TypedDict):
    """이메일 발신자 소속 판별 결과를 담는 타입입니다."""

    user_sdwt_prod: str
    classification_source: str


def _normalize_time(value: datetime | None) -> datetime:
    """datetime 값을 timezone-aware(UTC)로 정규화합니다."""

    if value is None:
        return timezone.now()
    if timezone.is_naive(value):
        return timezone.make_aware(value, timezone.utc)
    return value


def get_accessible_user_sdwt_prods_for_user(user: Any) -> set[str]:
    """사용자가 접근 가능한 user_sdwt_prod 값 집합을 조회합니다.

    Delegates to api.account.selectors.get_accessible_user_sdwt_prods_for_user.

    Side effects:
        None. Read-only query.
    """

    return account_selectors.get_accessible_user_sdwt_prods_for_user(user)


def list_mailbox_members(*, mailbox_user_sdwt_prod: str) -> list[dict[str, object]]:
    """메일함(user_sdwt_prod)에 접근 가능한 사용자 목록을 반환합니다.

    The result includes:
    - Users whose `user_sdwt_prod` equals the mailbox (implicit access)
    - Users who were granted access via `UserSdwtProdAccess` (explicit access)
    - `emailCount`: Emails in the mailbox where Email.sender_id matches the user (knox_id)
    - `knoxId`: User.knox_id (loginid)

    Args:
        mailbox_user_sdwt_prod: The mailbox user_sdwt_prod value.

    Returns:
        List of member dicts aligned with account access payloads.

    Side effects:
        None. Read-only query.
    """

    normalized = mailbox_user_sdwt_prod.strip() if isinstance(mailbox_user_sdwt_prod, str) else ""
    if not normalized:
        return []

    access_rows = list(account_selectors.list_group_members(user_sdwt_prods={normalized}))
    access_by_user_id = {row.user_id: row for row in access_rows}

    UserModel = get_user_model()
    affiliated_users = list(UserModel.objects.filter(user_sdwt_prod=normalized).order_by("id"))

    members: list[dict[str, object]] = []
    seen_user_ids: set[int] = set()
    sender_id_by_user_id: dict[int, str] = {}

    def resolve_sender_id(user: Any) -> str:
        sender_id = getattr(user, "knox_id", None)
        return sender_id.strip() if isinstance(sender_id, str) and sender_id.strip() else ""

    def serialize_user(user: Any, access: Any | None) -> dict[str, object]:
        sender_id_by_user_id[user.id] = resolve_sender_id(user)
        knox_id = getattr(user, "knox_id", None)
        knox_id_value = knox_id.strip() if isinstance(knox_id, str) else ""
        display_username = getattr(user, "username", None)
        display_username_value = display_username.strip() if isinstance(display_username, str) else ""
        return {
            "userId": user.id,
            "username": display_username_value,
            "name": (getattr(user, "first_name", "") or "") + (getattr(user, "last_name", "") or ""),
            "knoxId": knox_id_value,
            "userSdwtProd": normalized,
            "canManage": bool(getattr(access, "can_manage", False)) if access else False,
            "grantedBy": getattr(access, "granted_by_id", None) if access else None,
            "grantedAt": access.created_at.isoformat() if access else None,
            "emailCount": 0,
        }

    for user in affiliated_users:
        access = access_by_user_id.get(user.id)
        members.append(serialize_user(user, access))
        seen_user_ids.add(user.id)

    for access in access_rows:
        if access.user_id in seen_user_ids:
            continue
        members.append(serialize_user(access.user, access))
        seen_user_ids.add(access.user_id)

    sender_ids = sorted({value for value in sender_id_by_user_id.values() if value})
    if sender_ids:
        email_count_rows = (
            Email.objects.filter(user_sdwt_prod=normalized, sender_id__in=sender_ids)
            .values("sender_id")
            .annotate(email_count=Count("id"))
        )
        count_by_sender_id = {row["sender_id"]: row["email_count"] for row in email_count_rows}

        for member in members:
            user_id = member.get("userId")
            sender_id = sender_id_by_user_id.get(user_id) if isinstance(user_id, int) else ""
            member["emailCount"] = int(count_by_sender_id.get(sender_id, 0)) if sender_id else 0

    members.sort(key=lambda member: (not member.get("canManage", False), str(member.get("username", ""))))
    return members


def resolve_email_affiliation(*, sender_id: str, received_at: datetime | None) -> EmailAffiliation:
    """이메일 발신자 기준으로 user_sdwt_prod 소속을 판별합니다.

    Determine the affiliation snapshot for an email based on sender.

    Priority:
    - User.user_sdwt_prod (current)
    - ExternalAffiliationSnapshot.predicted_user_sdwt_prod
    - UNASSIGNED_USER_SDWT_PROD fallback

    Args:
        sender_id: Parsed sender identifier (username/local-part).
        received_at: Email received time. (unused for current-only policy)

    Returns:
        Dict containing resolved user_sdwt_prod.

    Side effects:
        None. Read-only query.
    """

    user = account_selectors.get_user_by_knox_id(knox_id=sender_id)
    if user is not None:
        resolved = (getattr(user, "user_sdwt_prod", None) or "").strip()
        if resolved and resolved != UNASSIGNED_USER_SDWT_PROD:
            return {
                "user_sdwt_prod": resolved,
                "classification_source": Email.ClassificationSource.CONFIRMED_USER,
            }

    snapshot = account_selectors.get_external_affiliation_snapshot_by_knox_id(knox_id=sender_id)
    if snapshot is not None:
        predicted = (snapshot.predicted_user_sdwt_prod or "").strip()
        if predicted:
            return {
                "user_sdwt_prod": predicted,
                "classification_source": Email.ClassificationSource.PREDICTED_EXTERNAL,
            }

    return {
        "user_sdwt_prod": UNASSIGNED_USER_SDWT_PROD,
        "classification_source": Email.ClassificationSource.UNASSIGNED,
    }


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


def list_pending_rag_emails(*, limit: int) -> list[Email]:
    """rag_doc_id가 없는 이메일 목록을 limit 만큼 반환합니다.

    Return emails missing rag_doc_id for backfill.

    Side effects:
        None. Read-only query.
    """

    if limit <= 0:
        return []

    queryset = (
        Email.objects.filter(
            Q(rag_doc_id__isnull=True) | Q(rag_doc_id=""),
            classification_source=Email.ClassificationSource.CONFIRMED_USER,
            rag_index_status=Email.RagIndexStatus.PENDING,
        )
        .order_by("id")[:limit]
    )
    return list(queryset)


def list_pending_email_outbox(
    *,
    limit: int,
    ready_before: datetime | None = None,
    for_update: bool = False,
    skip_locked: bool = True,
) -> list[EmailOutbox]:
    """처리 대기 중인 EmailOutbox 항목을 반환합니다.

    Return pending outbox items that are ready to be processed.

    Side effects:
        None. Read-only query.
    """

    if limit <= 0:
        return []

    when = _normalize_time(ready_before)
    queryset = EmailOutbox.objects.filter(
        status=EmailOutbox.Status.PENDING,
        available_at__lte=when,
    ).order_by("id")
    if for_update:
        queryset = queryset.select_for_update(skip_locked=skip_locked)
    queryset = queryset[:limit]
    return list(queryset)


def list_email_id_user_sdwt_by_ids(*, email_ids: list[int]) -> dict[int, str | None]:
    """Email id 목록으로 (id -> user_sdwt_prod) 매핑을 반환합니다.

    Return mapping for Email.user_sdwt_prod by ids.

    Side effects:
        None. Read-only query.
    """

    if not email_ids:
        return {}

    rows = Email.objects.filter(id__in=email_ids).values("id", "user_sdwt_prod")
    return {row["id"]: row["user_sdwt_prod"] for row in rows}


def list_email_ids_by_sender_after(
    *,
    sender_id: str,
    received_at_gte: datetime,
) -> list[int]:
    """sender_id의 특정 시각 이후 이메일 id 목록을 반환합니다.

    Return Email ids for sender_id after received_at_gte.

    Side effects:
        None. Read-only query.
    """

    if not isinstance(sender_id, str) or not sender_id.strip():
        return []

    normalized = sender_id.strip()
    return list(
        Email.objects.filter(sender_id=normalized, received_at__gte=received_at_gte)
        .values_list("id", flat=True)
        .order_by("id")
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
        search: Free-text query (subject/body/sender/participants).
        sender: Sender substring filter.
        recipient: Recipient substring filter (searches To/Cc).
        date_from: Minimum received_at (inclusive).
        date_to: Maximum received_at (inclusive).

    Returns:
        QuerySet ordered by newest first.

    Side effects:
        None. Read-only query.
    """

    if not is_privileged and not accessible_user_sdwt_prods:
        return Email.objects.none()

    queryset = Email.objects.order_by("-received_at", "-id")
    if not is_privileged:
        queryset = queryset.filter(user_sdwt_prod__in=accessible_user_sdwt_prods)

    if not can_view_unassigned:
        queryset = queryset.exclude(_unassigned_mailbox_query())

    if mailbox_user_sdwt_prod:
        queryset = queryset.filter(user_sdwt_prod=mailbox_user_sdwt_prod)

    if search:
        normalized_participant_search = search.lower()
        queryset = queryset.filter(
            Q(subject__icontains=search)
            | Q(body_text__icontains=search)
            | Q(sender__icontains=search)
            | Q(participants_search__contains=normalized_participant_search)
        )
    if sender:
        queryset = queryset.filter(sender__icontains=sender)
    if recipient:
        queryset = queryset.filter(participants_search__contains=recipient.lower())
    if date_from:
        queryset = queryset.filter(received_at__gte=date_from)
    if date_to:
        queryset = queryset.filter(received_at__lte=date_to)

    return queryset


def get_sent_emails(
    *,
    sender_id: str,
    search: str,
    sender: str,
    recipient: str,
    date_from: datetime | None,
    date_to: datetime | None,
) -> QuerySet[Email]:
    """발신자(sender_id) 기준으로 보낸 메일 QuerySet을 반환합니다.

    Args:
        sender_id: Email.sender_id (KNOX ID).
        search: Free-text query (subject/body/sender/participants).
        sender: Sender substring filter.
        recipient: Recipient substring filter (searches To/Cc).
        date_from: Minimum received_at (inclusive).
        date_to: Maximum received_at (inclusive).

    Returns:
        QuerySet ordered by newest first.

    Side effects:
        None. Read-only query.
    """

    if not isinstance(sender_id, str) or not sender_id.strip():
        return Email.objects.none()

    queryset = Email.objects.filter(sender_id=sender_id.strip()).order_by("-received_at", "-id")

    if search:
        normalized_participant_search = search.lower()
        queryset = queryset.filter(
            Q(subject__icontains=search)
            | Q(body_text__icontains=search)
            | Q(sender__icontains=search)
            | Q(participants_search__contains=normalized_participant_search)
        )
    if sender:
        queryset = queryset.filter(sender__icontains=sender)
    if recipient:
        queryset = queryset.filter(participants_search__contains=recipient.lower())
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
    sender_id: str | None = None,
) -> bool:
    """요청한 email_ids가 모두 접근 가능한 user_sdwt_prod 범위인지 검사합니다.

    Return whether all email_ids are within accessible_user_sdwt_prods or sender_id scope.

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

    mailbox_filter = Q(user_sdwt_prod__in=accessible_user_sdwt_prods)
    normalized_sender_id = sender_id.strip() if isinstance(sender_id, str) else ""
    if normalized_sender_id:
        mailbox_filter |= Q(sender_id=normalized_sender_id)

    owned_count = Email.objects.filter(id__in=email_ids).filter(mailbox_filter).count()
    return owned_count == len(email_ids)
