from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Sequence

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from api.common.affiliations import UNASSIGNED_USER_SDWT_PROD

from ..models import Email
from ..selectors import (
    get_accessible_user_sdwt_prods_for_user,
    list_email_id_user_sdwt_by_ids,
    list_email_ids_by_sender_after,
    list_unassigned_email_ids_for_sender_id,
    user_can_bulk_delete_emails,
)
from .rag import enqueue_rag_delete, enqueue_rag_index_for_emails

SENT_MAILBOX_ID = "__sent__"


def _resolve_sender_id_from_user(user: Any) -> str | None:
    """사용자에서 sender_id(knox_id)를 추출합니다."""

    knox_id = getattr(user, "knox_id", None)
    if isinstance(knox_id, str) and knox_id.strip():
        return knox_id.strip()
    return None


@transaction.atomic
def delete_single_email(email_id: int) -> Email:
    """단일 메일 삭제 (RAG 삭제는 Outbox로 비동기 처리)."""

    try:
        email = Email.objects.select_for_update().get(id=email_id)
    except Email.DoesNotExist:
        raise NotFound("Email not found")

    enqueue_rag_delete(email=email)

    email.delete()
    return email


@transaction.atomic
def bulk_delete_emails(email_ids: List[int]) -> int:
    """여러 메일을 한 번에 삭제 (RAG 삭제는 Outbox로 비동기 처리)."""

    emails = list(Email.objects.select_for_update().filter(id__in=email_ids))
    if not emails:
        raise NotFound("No emails found to delete")

    for email in emails:
        enqueue_rag_delete(email=email)

    target_ids = [email.id for email in emails]
    Email.objects.filter(id__in=target_ids).delete()

    return len(emails)


def claim_unassigned_emails_for_user(*, user: Any) -> Dict[str, int]:
    """사용자의 UNASSIGNED 메일을 현재 user_sdwt_prod로 귀속(옮김)합니다.

    Claim UNASSIGNED inbox emails for the given user into the user's current user_sdwt_prod.

    Rules:
    - Only emails with user_sdwt_prod not set (NULL/blank/UNASSIGNED) are eligible.
    - Previously classified emails are NOT moved.

    Returns:
        Dict with moved count and outbox enqueue stats.

    Side effects:
        - Updates Email.user_sdwt_prod in DB.
        - Enqueues RAG indexing requests.
    """

    sender_id = _resolve_sender_id_from_user(user)
    if not sender_id:
        raise PermissionError("knox_id is required to claim unassigned emails")

    target_user_sdwt_prod = getattr(user, "user_sdwt_prod", None)
    if not isinstance(target_user_sdwt_prod, str) or not target_user_sdwt_prod.strip():
        raise ValueError("user_sdwt_prod must be set to claim unassigned emails")

    target_user_sdwt_prod = target_user_sdwt_prod.strip()
    if target_user_sdwt_prod == UNASSIGNED_USER_SDWT_PROD:
        raise ValueError("Cannot claim emails into the UNASSIGNED mailbox")

    email_ids = list_unassigned_email_ids_for_sender_id(sender_id=sender_id)
    if not email_ids:
        return {"moved": 0, "ragRegistered": 0, "ragFailed": 0, "ragMissing": 0}

    with transaction.atomic():
        Email.objects.filter(id__in=email_ids).update(
            user_sdwt_prod=target_user_sdwt_prod,
            classification_source=Email.ClassificationSource.CONFIRMED_USER,
            rag_index_status=Email.RagIndexStatus.PENDING,
        )

    rag_result = enqueue_rag_index_for_emails(
        email_ids=email_ids,
        target_user_sdwt_prod=target_user_sdwt_prod,
        previous_user_sdwt_prod_by_email_id=None,
    )

    return {"moved": len(email_ids), **rag_result}


def move_emails_to_user_sdwt_prod(*, email_ids: Sequence[int], to_user_sdwt_prod: str) -> Dict[str, int]:
    """지정한 Email id들을 다른 user_sdwt_prod 메일함으로 이동합니다.

    Args:
        email_ids: 이동할 Email id 목록.
        to_user_sdwt_prod: 대상 메일함(user_sdwt_prod).

    Returns:
        Dict with moved count and outbox enqueue stats.

    Side effects:
        - Updates Email.user_sdwt_prod in DB.
        - Enqueues RAG indexing requests.
    """

    target_user_sdwt_prod = (to_user_sdwt_prod or "").strip()
    if not target_user_sdwt_prod:
        raise ValueError("to_user_sdwt_prod is required")
    if target_user_sdwt_prod in {UNASSIGNED_USER_SDWT_PROD, SENT_MAILBOX_ID}:
        raise ValueError("Cannot move emails into the target mailbox")

    ids = [int(value) for value in email_ids if isinstance(value, int) or str(value).isdigit()]
    if not ids:
        return {"moved": 0, "ragRegistered": 0, "ragFailed": 0, "ragMissing": 0}

    previous_user_sdwt = list_email_id_user_sdwt_by_ids(email_ids=ids)
    resolved_ids = list(previous_user_sdwt.keys())
    if not resolved_ids:
        return {"moved": 0, "ragRegistered": 0, "ragFailed": 0, "ragMissing": 0}

    moved_count = 0
    for previous in previous_user_sdwt.values():
        if (previous or "").strip() != target_user_sdwt_prod:
            moved_count += 1

    with transaction.atomic():
        Email.objects.filter(id__in=resolved_ids).update(
            user_sdwt_prod=target_user_sdwt_prod,
            classification_source=Email.ClassificationSource.CONFIRMED_USER,
            rag_index_status=Email.RagIndexStatus.PENDING,
        )

    rag_result = enqueue_rag_index_for_emails(
        email_ids=ids,
        target_user_sdwt_prod=target_user_sdwt_prod,
        previous_user_sdwt_prod_by_email_id=previous_user_sdwt,
    )

    return {"moved": moved_count, **rag_result}


def move_emails_for_user(
    *,
    user: Any,
    email_ids: Sequence[int],
    to_user_sdwt_prod: str,
) -> Dict[str, int]:
    """현재 사용자 권한을 확인한 뒤 메일을 다른 메일함으로 이동합니다.

    Rules:
    - 일반 사용자는 자신이 접근 가능한 메일함으로만 이동 가능.
    - 본인이 보낸 메일(sender_id)도 이동 가능.
    - 이동 대상은 UNASSIGNED/보낸메일함 sentinel이 될 수 없음.
    """

    if not user or not getattr(user, "is_authenticated", False):
        raise PermissionError("unauthorized")

    sender_id = _resolve_sender_id_from_user(user)
    if not sender_id:
        raise PermissionError("forbidden")

    target_user_sdwt_prod = (to_user_sdwt_prod or "").strip()
    if not target_user_sdwt_prod:
        raise ValueError("to_user_sdwt_prod is required")
    if target_user_sdwt_prod in {UNASSIGNED_USER_SDWT_PROD, SENT_MAILBOX_ID}:
        raise ValueError("Cannot move emails into the target mailbox")

    normalized_ids = [int(value) for value in email_ids if isinstance(value, int) or str(value).isdigit()]
    if not normalized_ids:
        return {"moved": 0, "ragRegistered": 0, "ragFailed": 0, "ragMissing": 0}

    is_privileged = bool(getattr(user, "is_superuser", False) or getattr(user, "is_staff", False))
    accessible = get_accessible_user_sdwt_prods_for_user(user) if not is_privileged else set()
    if not is_privileged and target_user_sdwt_prod not in accessible:
        raise PermissionError("forbidden")

    if not is_privileged:
        if not user_can_bulk_delete_emails(
            email_ids=normalized_ids,
            accessible_user_sdwt_prods=accessible,
            sender_id=sender_id,
        ):
            raise PermissionError("forbidden")

    return move_emails_to_user_sdwt_prod(email_ids=normalized_ids, to_user_sdwt_prod=target_user_sdwt_prod)


def move_sender_emails_after(
    *,
    sender_id: str,
    received_at_gte: datetime,
    to_user_sdwt_prod: str,
) -> Dict[str, int]:
    """발신자(sender_id)의 특정 시각 이후 메일을 다른 메일함으로 이동합니다.

    Args:
        sender_id: Email.sender_id (KNOX ID).
        received_at_gte: 기준 시각(이 시각 이상 수신된 메일만).
        to_user_sdwt_prod: 대상 메일함(user_sdwt_prod).

    Returns:
        Dict with moved count and outbox enqueue stats.

    Side effects:
        - Updates Email.user_sdwt_prod in DB.
        - Enqueues RAG indexing requests.
    """

    normalized_sender_id = (sender_id or "").strip()
    if not normalized_sender_id:
        raise ValueError("sender_id is required")

    when = received_at_gte
    if timezone.is_naive(when):
        when = timezone.make_aware(when, timezone.get_current_timezone())

    email_ids = list_email_ids_by_sender_after(sender_id=normalized_sender_id, received_at_gte=when)

    return move_emails_to_user_sdwt_prod(email_ids=email_ids, to_user_sdwt_prod=to_user_sdwt_prod)
