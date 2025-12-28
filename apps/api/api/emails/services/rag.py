from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Dict, Sequence

from django.db import transaction
from django.utils import timezone

from api.common.affiliations import UNASSIGNED_USER_SDWT_PROD
from api.rag import services as rag_services

from ..models import Email, EmailOutbox
from ..selectors import (
    list_emails_by_ids,
    list_pending_email_outbox,
    list_pending_rag_emails,
)

logger = logging.getLogger(__name__)

OUTBOX_MAX_RETRIES = 5
OUTBOX_RETRY_BASE_SECONDS = 30
OUTBOX_RETRY_MAX_SECONDS = 3600


def _compute_outbox_backoff_seconds(retry_count: int) -> int:
    """재시도 횟수에 따른 백오프(초)를 계산합니다."""

    if retry_count <= 0:
        return OUTBOX_RETRY_BASE_SECONDS
    seconds = OUTBOX_RETRY_BASE_SECONDS * (2**retry_count)
    return min(seconds, OUTBOX_RETRY_MAX_SECONDS)


def _ensure_email_rag_doc_id(email: Email) -> None:
    """Email.rag_doc_id가 비어있으면 기본 규칙으로 채웁니다."""

    if email.rag_doc_id:
        return
    email.rag_doc_id = f"email-{email.id}"
    email.save(update_fields=["rag_doc_id"])


def _resolve_email_permission_groups(email: Email) -> list[str] | None:
    """이메일의 user_sdwt_prod 값을 permission_groups로 변환합니다."""

    user_sdwt_prod = (email.user_sdwt_prod or "").strip()
    sender_id = (email.sender_id or "").strip()
    groups: list[str] = []
    if user_sdwt_prod:
        groups.append(user_sdwt_prod)
    if sender_id:
        groups.append(sender_id)
    if groups:
        return list(dict.fromkeys(groups))
    return [rag_services.RAG_PUBLIC_GROUP]


def enqueue_email_outbox(
    *,
    email: Email | None,
    action: str,
    payload: dict[str, Any] | None = None,
) -> EmailOutbox:
    """이메일 RAG 작업을 Outbox로 적재합니다."""

    return EmailOutbox.objects.create(
        email=email,
        action=action,
        payload=payload or {},
        status=EmailOutbox.Status.PENDING,
        available_at=timezone.now(),
    )


def enqueue_rag_index(*, email: Email, previous_user_sdwt_prod: str | None = None) -> EmailOutbox:
    """RAG 인덱싱 요청을 Outbox에 적재합니다."""

    _ensure_email_rag_doc_id(email)
    payload = {}
    if previous_user_sdwt_prod is not None:
        payload["previous_user_sdwt_prod"] = previous_user_sdwt_prod
    return enqueue_email_outbox(email=email, action=EmailOutbox.Action.INDEX, payload=payload)


def enqueue_rag_delete(*, email: Email) -> EmailOutbox | None:
    """RAG 삭제 요청을 Outbox에 적재합니다."""

    if not email.rag_doc_id:
        return None
    permission_groups = _resolve_email_permission_groups(email)
    payload = {
        "rag_doc_id": email.rag_doc_id,
        "index_name": rag_services.resolve_rag_index_name(rag_services.RAG_INDEX_EMAILS),
        "permission_groups": permission_groups,
    }
    return enqueue_email_outbox(email=email, action=EmailOutbox.Action.DELETE, payload=payload)


def _call_insert_email_to_rag(
    email: Email,
    *,
    index_name: str | None = None,
    permission_groups: Sequence[str] | None = None,
) -> None:
    from api.emails import services as email_services

    email_services.insert_email_to_rag(
        email,
        index_name=index_name,
        permission_groups=permission_groups,
    )


def _call_delete_rag_doc(
    doc_id: str,
    *,
    index_name: str | None = None,
    permission_groups: Sequence[str] | None = None,
) -> None:
    from api.emails import services as email_services

    email_services.delete_rag_doc(
        doc_id,
        index_name=index_name,
        permission_groups=permission_groups,
    )


def enqueue_rag_index_for_emails(
    *,
    email_ids: list[int],
    target_user_sdwt_prod: str,
    previous_user_sdwt_prod_by_email_id: Dict[int, str | None] | None,
) -> Dict[str, int]:
    """메일 목록의 RAG 인덱싱을 즉시 시도하고 실패 시 Outbox에 적재합니다.

    Returns:
        Dict with ragRegistered/ragFailed/ragMissing counts.
    """

    if not email_ids:
        return {"ragRegistered": 0, "ragFailed": 0, "ragMissing": 0}

    requested_ids = [
        int(value) for value in email_ids if isinstance(value, int) or str(value).isdigit()
    ]
    requested_set = set(requested_ids)
    resolved_ids: list[int] = []
    rag_registered = 0
    rag_failed = 0

    for email in list_emails_by_ids(email_ids=requested_ids).iterator():
        resolved_ids.append(email.id)
        previous_user_sdwt_prod = (
            previous_user_sdwt_prod_by_email_id.get(email.id)
            if previous_user_sdwt_prod_by_email_id is not None
            else None
        )
        try:
            register_email_to_rag(email, previous_user_sdwt_prod=previous_user_sdwt_prod)
            rag_registered += 1
        except Exception:
            logger.exception("Failed to register email to RAG id=%s", email.id)
            try:
                enqueue_rag_index(email=email, previous_user_sdwt_prod=previous_user_sdwt_prod)
            except Exception:
                logger.exception("Failed to enqueue RAG outbox for email id=%s", email.id)
                rag_failed += 1

    resolved_set = set(resolved_ids)
    rag_missing = len(requested_set - resolved_set)

    return {"ragRegistered": rag_registered, "ragFailed": rag_failed, "ragMissing": rag_missing}


def register_email_to_rag(
    email: Email,
    previous_user_sdwt_prod: str | None = None,
    persist_fields: Sequence[str] | None = None,
) -> Email:
    """
    이메일을 RAG에 등록하고 rag_doc_id를 저장.
    - 이미 rag_doc_id가 있으면 그대로 사용.
    - 실패 시 예외를 발생시켜 호출 측에서 재시도 가능.
    - 이전 user_sdwt_prod가 주어져도 단일 인덱스에서 doc_id 재등록으로 권한을 갱신한다.
    """

    update_fields = []
    if email.classification_source != Email.ClassificationSource.CONFIRMED_USER:
        raise ValueError("Cannot register a non-confirmed email to RAG")

    normalized_user_sdwt = (email.user_sdwt_prod or "").strip()
    if not normalized_user_sdwt or normalized_user_sdwt == UNASSIGNED_USER_SDWT_PROD:
        raise ValueError("Cannot register an UNASSIGNED email to RAG")
    if normalized_user_sdwt != email.user_sdwt_prod:
        email.user_sdwt_prod = normalized_user_sdwt
        update_fields.append("user_sdwt_prod")
    if not email.rag_doc_id:
        email.rag_doc_id = f"email-{email.id}"
        update_fields.append("rag_doc_id")

    permission_groups = _resolve_email_permission_groups(email)
    target_index = rag_services.resolve_rag_index_name(rag_services.RAG_INDEX_EMAILS)
    _call_insert_email_to_rag(email, index_name=target_index, permission_groups=permission_groups)
    if email.rag_index_status != Email.RagIndexStatus.INDEXED:
        email.rag_index_status = Email.RagIndexStatus.INDEXED
        update_fields.append("rag_index_status")
    if persist_fields:
        update_fields.extend(list(persist_fields))
    if update_fields:
        email.save(update_fields=list(dict.fromkeys(update_fields)))  # deduplicate
    return email


def _process_outbox_item(item: EmailOutbox) -> None:
    """단일 Outbox 항목을 처리합니다."""

    if item.action == EmailOutbox.Action.INDEX:
        if item.email is None:
            raise ValueError("Email not found for outbox item")
        previous_user_sdwt_prod = item.payload.get("previous_user_sdwt_prod")
        register_email_to_rag(item.email, previous_user_sdwt_prod=previous_user_sdwt_prod)
        return

    if item.action == EmailOutbox.Action.DELETE:
        rag_doc_id = item.payload.get("rag_doc_id")
        index_name = item.payload.get("index_name")
        permission_groups = item.payload.get("permission_groups")
        if not rag_doc_id or not index_name:
            raise ValueError("rag_doc_id or index_name missing for delete outbox item")
        _call_delete_rag_doc(rag_doc_id, index_name=index_name, permission_groups=permission_groups)
        return

    if item.action in {EmailOutbox.Action.RECLASSIFY, EmailOutbox.Action.RECLASSIFY_ALL}:
        logger.info("Skipping deprecated outbox action=%s id=%s", item.action, item.id)
        return

    raise ValueError(f"Unsupported outbox action: {item.action}")


def process_email_outbox_batch(*, limit: int = 100) -> Dict[str, int]:
    """Outbox 항목을 처리하고 결과 통계를 반환합니다."""

    if limit <= 0:
        return {"processed": 0, "succeeded": 0, "failed": 0}

    with transaction.atomic():
        pending = list_pending_email_outbox(limit=limit, for_update=True)
        if not pending:
            return {"processed": 0, "succeeded": 0, "failed": 0}
        EmailOutbox.objects.filter(id__in=[item.id for item in pending]).update(
            status=EmailOutbox.Status.PROCESSING,
        )

    succeeded = 0
    failed = 0
    for item in pending:
        try:
            _process_outbox_item(item)
            EmailOutbox.objects.filter(id=item.id).update(
                status=EmailOutbox.Status.DONE,
                last_error="",
            )
            succeeded += 1
        except Exception as exc:
            logger.exception("Failed to process email outbox item id=%s", item.id)
            retry_count = item.retry_count + 1
            if retry_count >= OUTBOX_MAX_RETRIES:
                EmailOutbox.objects.filter(id=item.id).update(
                    status=EmailOutbox.Status.FAILED,
                    retry_count=retry_count,
                    last_error=str(exc),
                )
            else:
                delay = _compute_outbox_backoff_seconds(retry_count)
                EmailOutbox.objects.filter(id=item.id).update(
                    status=EmailOutbox.Status.PENDING,
                    retry_count=retry_count,
                    last_error=str(exc),
                    available_at=timezone.now() + timedelta(seconds=delay),
                )
            failed += 1

    return {"processed": len(pending), "succeeded": succeeded, "failed": failed}


def register_missing_rag_docs(limit: int = 500) -> int:
    """
    rag_doc_id가 없는 이메일을 Outbox에 적재합니다.
    - POP3 삭제 이후 RAG 등록 실패 건을 재시도하기 위한 백필용.
    """

    pending = list_pending_rag_emails(limit=limit)
    enqueued = 0

    for email in pending:
        try:
            enqueue_rag_index(email=email)
            enqueued += 1
        except Exception:
            logger.exception("Failed to enqueue RAG outbox for email id=%s", email.id)

    return enqueued
