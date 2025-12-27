from __future__ import annotations

import base64
import hashlib
import gzip
import logging
import os
import poplib
from datetime import datetime, timedelta
from email.header import decode_header, make_header
from email.message import Message
from email.parser import BytesParser
from email.policy import default
from email.utils import getaddresses, parseaddr, parsedate_to_datetime
from typing import Any, Dict, Iterable, List, Sequence, Tuple

import requests
from api.common.affiliations import UNASSIGNED_USER_SDWT_PROD
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from .selectors import (
    get_accessible_user_sdwt_prods_for_user,
    list_email_id_user_sdwt_by_ids,
    list_email_ids_by_sender_after,
    list_emails_by_ids,
    list_mailbox_members,
    list_pending_email_outbox,
    list_pending_rag_emails,
    list_privileged_email_mailboxes,
    list_unassigned_email_ids_for_sender_id,
    resolve_email_affiliation,
    user_can_bulk_delete_emails,
)
from .models import Email, EmailOutbox
from api.rag.services import (
    RAG_INDEX_EMAILS,
    RAG_PUBLIC_GROUP,
    delete_rag_doc,
    insert_email_to_rag,
    resolve_rag_index_name,
)
from .permissions import user_can_view_unassigned

logger = logging.getLogger(__name__)

OUTBOX_MAX_RETRIES = 5
OUTBOX_RETRY_BASE_SECONDS = 30
OUTBOX_RETRY_MAX_SECONDS = 3600
SENT_MAILBOX_ID = "__sent__"


def _compute_outbox_backoff_seconds(retry_count: int) -> int:
    """재시도 횟수에 따른 백오프(초)를 계산합니다."""

    if retry_count <= 0:
        return OUTBOX_RETRY_BASE_SECONDS
    seconds = OUTBOX_RETRY_BASE_SECONDS * (2**retry_count)
    return min(seconds, OUTBOX_RETRY_MAX_SECONDS)


class MailSendError(Exception):
    """사내 메일 발신 API 호출 실패 예외."""


def send_knox_mail_api(
    sender_email: str,
    receiver_emails: Sequence[str],
    subject: str,
    html_content: str,
) -> Dict[str, Any]:
    """사내 Knox 메일 발신 API를 호출해 메일을 발송합니다.

    Env:
    - MAIL_API_URL: 발신 API URL (예: https://.../send)
    - MAIL_API_KEY: x-dep-ticket 값
    - MAIL_API_SYSTEM_ID: systemId (default: plane)
    - MAIL_API_KNOX_ID: loginUser.login 값

    Returns:
    - API가 JSON을 반환하면 해당 dict
    - JSON이 아니면 {"ok": True}

    Side effects:
    - 외부 메일 발신 API에 HTTP 요청을 전송합니다.
    """

    url = (os.getenv("MAIL_API_URL") or "").strip()
    prod_key = (os.getenv("MAIL_API_KEY") or "").strip()
    system_id = (os.getenv("MAIL_API_SYSTEM_ID") or "plane").strip()
    knox_id = (os.getenv("MAIL_API_KNOX_ID") or "").strip()

    if not url:
        raise MailSendError("MAIL_API_URL 미설정")
    if not prod_key or not knox_id:
        raise MailSendError("MAIL_API_KEY / MAIL_API_KNOX_ID 미설정")

    normalized_receivers = [str(email).strip() for email in receiver_emails if str(email).strip()]
    if not normalized_receivers:
        raise MailSendError("수신자 없음")

    params = {"systemId": system_id, "loginUser.login": knox_id}
    headers = {"x-dep-ticket": prod_key}
    payload = {
        "receiverList": [{"email": email, "recipientType": "TO"} for email in normalized_receivers],
        "title": subject,
        "content": html_content,
        "senderMailAddress": sender_email,
    }

    try:
        response = requests.post(url, params=params, headers=headers, json=payload, timeout=10)
        if not response.ok:
            raise MailSendError(f"메일 API 오류 {response.status_code}: {response.text[:300]}")
        content_type = response.headers.get("content-type", "")
        if content_type.startswith("application/json"):
            data = response.json()
            if isinstance(data, dict):
                return data
            return {"data": data}
        return {"ok": True}
    except requests.Timeout as exc:
        raise MailSendError("메일 API 타임아웃") from exc
    except requests.RequestException as exc:
        raise MailSendError(f"메일 API 요청 실패: {exc}") from exc


def gzip_body(body_html: str | None) -> bytes | None:
    """HTML 문자열을 gzip 압축하여 BinaryField에 저장 가능하도록 변환."""

    if not body_html:
        return None
    return gzip.compress(body_html.encode("utf-8"))


def _resolve_sender_id_from_user(user: Any) -> str | None:
    """사용자에서 sender_id(knox_id)를 추출합니다."""

    knox_id = getattr(user, "knox_id", None)
    if isinstance(knox_id, str) and knox_id.strip():
        return knox_id.strip()
    return None


def get_mailbox_access_summary_for_user(*, user: Any) -> list[dict[str, object]]:
    """현재 사용자 기준 메일함 접근 요약을 반환합니다.

    Returns:
        List of dicts with mailbox membership stats.

    Side effects:
        None. Read-only query.
    """

    if not user or not getattr(user, "is_authenticated", False):
        return []

    is_privileged = bool(getattr(user, "is_superuser", False) or getattr(user, "is_staff", False))
    if is_privileged:
        mailboxes = list_privileged_email_mailboxes()
        if not user_can_view_unassigned(user):
            mailboxes = [
                mailbox
                for mailbox in mailboxes
                if mailbox not in {UNASSIGNED_USER_SDWT_PROD, "rp-unclassified"}
            ]
    else:
        mailboxes = sorted(get_accessible_user_sdwt_prods_for_user(user))

    summaries: list[dict[str, object]] = []
    user_id = getattr(user, "id", None)

    for mailbox in mailboxes:
        members = list_mailbox_members(mailbox_user_sdwt_prod=mailbox)
        member_count = len(members)
        current_member = None
        if isinstance(user_id, int):
            for member in members:
                if member.get("userId") == user_id:
                    current_member = member
                    break

        summaries.append(
            {
                "userSdwtProd": mailbox,
                "memberCount": member_count,
                "myEmailCount": int(current_member.get("emailCount", 0)) if current_member else 0,
                "myCanManage": bool(current_member.get("canManage", False)) if current_member else False,
                "myGrantedAt": current_member.get("grantedAt") if current_member else None,
                "myGrantedBy": current_member.get("grantedBy") if current_member else None,
            }
        )

    return summaries


def save_parsed_email(
    *,
    message_id: str,
    received_at: datetime | None,
    subject: str,
    sender: str,
    sender_id: str,
    recipient: Sequence[str] | None,
    cc: Sequence[str] | None,
    user_sdwt_prod: str | None,
    classification_source: str,
    rag_index_status: str,
    body_html: str | None,
    body_text: str | None,
) -> Email:
    """POP3 파서에서 호출하는 저장 함수 (message_id 중복 방지)."""

    user_sdwt_prod = user_sdwt_prod or UNASSIGNED_USER_SDWT_PROD

    normalized_recipient = _normalize_participants(recipient)
    normalized_cc = _normalize_participants(cc)
    participants_search = _build_participants_search(recipient=normalized_recipient, cc=normalized_cc)

    email, _created = Email.objects.get_or_create(
        message_id=message_id,
        defaults={
            "received_at": received_at or timezone.now(),
            "subject": subject,
            "sender": sender,
            "sender_id": sender_id,
            "recipient": normalized_recipient or None,
            "cc": normalized_cc or None,
            "participants_search": participants_search,
            "user_sdwt_prod": user_sdwt_prod,
            "classification_source": classification_source,
            "rag_index_status": rag_index_status,
            "body_text": body_text or "",
            "body_html_gzip": gzip_body(body_html),
        },
    )
    if not _created:
        fields_to_update = []
        if not email.sender_id:
            email.sender_id = sender_id
            fields_to_update.append("sender_id")
        if not email.user_sdwt_prod and user_sdwt_prod:
            email.user_sdwt_prod = user_sdwt_prod
            fields_to_update.append("user_sdwt_prod")
        if classification_source and email.classification_source != classification_source:
            email.classification_source = classification_source
            fields_to_update.append("classification_source")
        if rag_index_status and email.rag_index_status != rag_index_status:
            email.rag_index_status = rag_index_status
            fields_to_update.append("rag_index_status")
        if fields_to_update:
            email.save(update_fields=fields_to_update)
    return email


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
    return [RAG_PUBLIC_GROUP]


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
        "index_name": resolve_rag_index_name(RAG_INDEX_EMAILS),
        "permission_groups": permission_groups,
    }
    return enqueue_email_outbox(email=email, action=EmailOutbox.Action.DELETE, payload=payload)


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
    target_index = resolve_rag_index_name(RAG_INDEX_EMAILS)
    insert_email_to_rag(email, index_name=target_index, permission_groups=permission_groups)
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
        delete_rag_doc(rag_doc_id, index_name=index_name, permission_groups=permission_groups)
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


DEFAULT_EXCLUDED_SUBJECT_PREFIXES = ("[drone_sop]", "[test]")


def _load_excluded_subject_prefixes() -> tuple[str, ...]:
    """환경변수 기반 메일 제목 제외 prefix 목록을 로드합니다."""

    raw = os.getenv("EMAIL_EXCLUDED_SUBJECT_PREFIXES", "")
    if not raw:
        return DEFAULT_EXCLUDED_SUBJECT_PREFIXES

    prefixes: List[str] = []
    for item in raw.split(","):
        cleaned = item.strip().strip("\"'").lower()
        if cleaned:
            prefixes.append(cleaned)

    return tuple(prefixes) if prefixes else DEFAULT_EXCLUDED_SUBJECT_PREFIXES


EXCLUDED_SUBJECT_PREFIXES = _load_excluded_subject_prefixes()


def _is_excluded_subject(subject: str) -> bool:
    """제목이 제외 대상 prefix로 시작하는지 검사합니다."""

    normalized = (subject or "").strip().lower()
    return any(normalized.startswith(prefix) for prefix in EXCLUDED_SUBJECT_PREFIXES)


def _decode_header_value(raw_value: str | None) -> str:
    """RFC2047 인코딩 헤더 값을 사람이 읽을 수 있는 문자열로 디코딩합니다."""

    if not raw_value:
        return ""
    try:
        return str(make_header(decode_header(raw_value)))
    except Exception:
        return raw_value


def _format_display_address(*, name: str, address: str) -> str:
    """(name, address) 튜플을 사람이 읽기 좋은 "Name <addr>" 형식 문자열로 정규화합니다."""

    normalized_name = " ".join(str(name or "").split()).strip()
    normalized_address = str(address or "").strip()
    if normalized_name and normalized_address:
        return f"{normalized_name} <{normalized_address}>"
    return normalized_address or normalized_name


def _normalize_participants(values: Sequence[str] | None) -> list[str]:
    """참여자(수신/참조) 문자열 리스트를 trim/dedup하여 반환합니다."""

    if not values:
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = " ".join(str(value or "").split()).strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(cleaned)
    return normalized


def _build_participants_search(*, recipient: Sequence[str] | None, cc: Sequence[str] | None) -> str | None:
    """recipient/cc를 합쳐 부분검색용 텍스트를 생성합니다(소문자 정규화)."""

    combined = _normalize_participants(list(recipient or []) + list(cc or []))
    if not combined:
        return None
    return "\n".join([value.lower() for value in combined])


def _extract_participants(msg: Message, header_name: str) -> list[str]:
    """메일 헤더(To/Cc 등)에서 수신자 리스트를 파싱해 반환합니다."""

    raw_values = msg.get_all(header_name, []) or []
    decoded_values = [_decode_header_value(value) for value in raw_values if value]
    parsed = getaddresses(decoded_values)

    results: list[str] = []
    for name, address in parsed:
        formatted = _format_display_address(name=name, address=address)
        if formatted:
            results.append(formatted)
    return _normalize_participants(results)


def _decode_part(part: Message) -> str:
    """메일 MIME 파트의 payload를 charset 기반으로 문자열 디코딩합니다."""

    payload = part.get_payload(decode=True)
    if payload is None:
        return ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except LookupError:
        return payload.decode("utf-8", errors="replace")


def _replace_cid_images(soup: Any, cid_map: Dict[str, Dict[str, Any]]) -> None:
    """HTML 본문 내 cid: 이미지 참조를 data URI로 치환합니다."""

    for img in soup.find_all("img"):
        src = img.get("src", "")
        if not src.startswith("cid:"):
            continue
        cid = src[4:]
        if cid not in cid_map:
            continue
        data = cid_map[cid].get("data")
        img_type = cid_map[cid].get("type") or "png"
        if not data:
            continue
        b64 = base64.b64encode(data).decode("utf-8")
        img["src"] = f"data:image/{img_type};base64,{b64}"


def _replace_mosaic_embeds(soup: Any) -> None:
    """모자이크(https://mosaic...) embed를 링크로 치환해 렌더링 문제를 완화합니다."""

    for embed in soup.find_all("embed"):
        src = embed.get("src", "")
        if not src.startswith("https://mosaic"):
            continue
        parent_div = embed.find_parent("div")
        if parent_div:
            span_tag = soup.new_tag("span")
            a_tag = soup.new_tag("a", href=src)
            a_tag.string = "모자이크 링크"
            span_tag.append(a_tag)
            parent_div.replace_with(span_tag)


def _extract_bodies(msg: Message) -> Tuple[str, str]:
    """메일 메시지에서 텍스트/HTML 본문을 추출하고(가능하면) 정규화합니다."""

    text_body = ""
    html_content = ""
    cid_map: Dict[str, Dict[str, Any]] = {}

    if msg.is_multipart():
        for part in msg.walk():
            if part.is_multipart():
                continue
            content_type = part.get_content_type()
            disposition = (part.get("Content-Disposition") or "").lower()
            content_id = part.get("Content-ID")

            if content_type.startswith("image/") and content_id:
                payload = part.get_payload(decode=True)
                if payload:
                    cid_map[content_id.strip("<>")] = {
                        "data": payload,
                        "type": part.get_content_subtype(),
                    }
                continue

            if disposition.startswith("attachment"):
                continue

            if content_type == "text/plain" and not text_body:
                text_body = _decode_part(part)
            elif content_type == "text/html" and not html_content:
                html_content = _decode_part(part)
    else:
        content_type = msg.get_content_type()
        disposition = (msg.get("Content-Disposition") or "").lower()
        content_id = msg.get("Content-ID")

        if content_type.startswith("image/") and content_id:
            payload = msg.get_payload(decode=True)
            if payload:
                cid_map[content_id.strip("<>")] = {
                    "data": payload,
                    "type": msg.get_content_subtype(),
                }

        if not disposition.startswith("attachment"):
            if content_type == "text/plain":
                text_body = _decode_part(msg)
            elif content_type == "text/html":
                html_content = _decode_part(msg)

    if html_content:
        from bs4 import BeautifulSoup  # dependency used only for ingest

        soup = BeautifulSoup(html_content, "lxml")
        _replace_cid_images(soup, cid_map)
        _replace_mosaic_embeds(soup)
        body_html = soup.prettify()
        body_text = soup.get_text()
        return body_text, body_html

    if not text_body and hasattr(msg, "get_body"):
        try:
            fallback = msg.get_body(preferencelist=("plain", "html"))
            if fallback:
                text_body = _decode_part(fallback)
        except Exception:
            pass

    return text_body or "", ""


def _parse_received_at(msg: Message) -> datetime:
    """메일 Date 헤더를 파싱해 수신 시각(timezone-aware)을 반환합니다."""

    raw_date = msg.get("Date")
    if raw_date:
        try:
            parsed = parsedate_to_datetime(raw_date)
            if parsed and timezone.is_naive(parsed):
                parsed = timezone.make_aware(parsed, timezone.utc)
            if parsed:
                return parsed
        except Exception:
            logger.exception("Failed to parse email Date header: %s", raw_date)
    return timezone.now()


def _extract_subject_header(msg: Message) -> str:
    """메일 Subject 헤더를 디코딩해 반환합니다."""

    return _decode_header_value(msg.get("Subject"))


def _extract_sender_id(sender: str) -> str:
    """발신자 주소 문자열에서 sender_id(로컬파트)를 추출합니다."""

    address = parseaddr(sender or "")[1]
    if address and "@" in address:
        local = address.split("@", 1)[0].strip()
        if local:
            return local
    normalized = (sender or "").strip()
    return normalized or "UNKNOWN"


def _parse_message_to_fields(msg: Message) -> Dict[str, Any]:
    """메일 Message 객체를 Email 저장에 필요한 필드 dict로 변환합니다."""

    subject = _extract_subject_header(msg)
    sender = _decode_header_value(msg.get("From"))
    recipient = _extract_participants(msg, "To") or _extract_participants(msg, "Delivered-To")
    cc = _extract_participants(msg, "Cc")
    message_id = (msg.get("Message-ID") or msg.get("Message-Id") or "").strip()
    if not message_id:
        content_hash = hashlib.sha256(msg.as_bytes()).hexdigest()
        message_id = f"generated-{content_hash}"

    body_text, body_html = _extract_bodies(msg)
    received_at = _parse_received_at(msg)
    sender_id = _extract_sender_id(sender)

    return {
        "message_id": message_id,
        "received_at": received_at,
        "subject": subject,
        "sender": sender,
        "sender_id": sender_id,
        "recipient": recipient,
        "cc": cc,
        "body_text": body_text,
        "body_html": body_html,
    }


def _iter_pop3_messages(session: Any) -> Iterable[Tuple[int, Message]]:
    """POP3 세션에서 (메시지 번호, Message) 스트림을 생성합니다."""

    if hasattr(session, "iter_messages"):
        yield from session.iter_messages()
        return

    _resp, items, _octets = session.list()
    if not items:
        return

    for item in items:
        raw = item.decode() if isinstance(item, (bytes, bytearray)) else str(item)
        msg_num = int(raw.split()[0])
        _resp, lines, _octets = session.retr(msg_num)
        raw_msg = b"\n".join(lines)
        msg = BytesParser(policy=default).parsebytes(raw_msg)
        yield msg_num, msg


def _delete_pop3_messages(session: Any, message_numbers: List[int]) -> None:
    """POP3 세션에서 지정한 메시지 번호들을 삭제(mark)합니다."""

    if not message_numbers:
        return

    for msg_num in message_numbers:
        try:
            session.dele(msg_num)
        except Exception:
            logger.exception("Failed to delete POP3 message #%s", msg_num)


def ingest_pop3_mailbox(session: Any) -> List[int]:
    """
    POP3 메일함을 순회하며 Email + RAG 등록 후 삭제 대상 번호를 반환.
    - 제목 제외 규칙을 최상단에서 처리
    - DB 저장 성공 시에만 POP3 삭제
    - RAG 등록 실패는 POP3 삭제 여부에 영향을 주지 않음
    """

    to_delete: List[int] = []

    for msg_num, msg in _iter_pop3_messages(session):
        try:
            subject = _extract_subject_header(msg)
            if _is_excluded_subject(subject):
                logger.info("Skipping excluded email subject: %s", subject)
                continue

            fields = _parse_message_to_fields(msg)
            sender_id = fields["sender_id"]
            received_at = fields["received_at"]
            affiliation = resolve_email_affiliation(sender_id=sender_id, received_at=received_at)
            user_sdwt_prod = affiliation["user_sdwt_prod"]
            classification_source = affiliation["classification_source"]
            rag_index_status = (
                Email.RagIndexStatus.PENDING
                if classification_source == Email.ClassificationSource.CONFIRMED_USER
                else Email.RagIndexStatus.SKIPPED
            )

            email_obj = save_parsed_email(
                message_id=fields["message_id"],
                received_at=received_at,
                subject=fields["subject"],
                sender=fields["sender"],
                sender_id=sender_id,
                recipient=fields["recipient"],
                cc=fields["cc"],
                user_sdwt_prod=user_sdwt_prod,
                classification_source=classification_source,
                rag_index_status=rag_index_status,
                body_text=fields.get("body_text") or "",
                body_html=fields.get("body_html"),
            )

            to_delete.append(msg_num)

            if (
                not email_obj.rag_doc_id
                and email_obj.user_sdwt_prod != UNASSIGNED_USER_SDWT_PROD
                and email_obj.classification_source == Email.ClassificationSource.CONFIRMED_USER
                and email_obj.rag_index_status == Email.RagIndexStatus.PENDING
            ):
                try:
                    enqueue_rag_index(email=email_obj)
                except Exception:
                    logger.exception("Failed to enqueue RAG outbox for email %s", email_obj.id)

        except Exception as exc:
            logger.exception("Failed to process POP3 message #%s: %s", msg_num, exc)
            continue

    _delete_pop3_messages(session, to_delete)
    return to_delete


def run_pop3_ingest(
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    use_ssl: bool = True,
    timeout: int = 60,
) -> Dict[str, int]:
    """POP3 세션을 열어 메일을 수집/저장하고 삭제를 커밋합니다.

    Create a POP3 session, ingest messages, and commit deletions.

    Args:
        host: POP3 server host.
        port: POP3 port.
        username: POP3 login username.
        password: POP3 login password.
        use_ssl: Use POP3_SSL when True.
        timeout: Socket timeout seconds.

    Returns:
        Dict with deleted message count and reindexed count.

    Side effects:
        - Reads from POP3 mailbox.
        - Writes Email rows and RAG documents.
        - Deletes messages from POP3 mailbox (commit via quit()).
    """

    if not host or not username or not password:
        raise ValueError("POP3 connection info is incomplete (host/username/password required)")

    client_cls = poplib.POP3_SSL if use_ssl else poplib.POP3
    client = client_cls(host, port, timeout=timeout)
    deleted: List[int] = []
    reindexed = 0
    try:
        client.user(username)
        client.pass_(password)
        logger.info("POP3 login succeeded: host=%s port=%s ssl=%s", host, port, use_ssl)

        deleted = ingest_pop3_mailbox(client) or []
        try:
            reindexed = register_missing_rag_docs()
            if reindexed:
                logger.info("RAG backfill attempted for %s emails without rag_doc_id", reindexed)
        except Exception:
            logger.exception("RAG backfill failed after POP3 ingest")
        logger.info("Ingest complete; marked %s messages for deletion", len(deleted))

        client.quit()
        logger.info("POP3 session closed (quit)")
    except Exception:
        logger.exception("POP3 ingest failed; rolling back via rset()")
        try:
            client.rset()
        except Exception:
            logger.debug("POP3 rset failed")
        raise
    finally:
        try:
            client.quit()
        except Exception:
            pass

    return {"deleted": len(deleted), "reindexed": reindexed}


def _env_bool(key: str, default: bool = False) -> bool:
    """환경변수 값을 boolean으로 파싱합니다."""

    value = os.getenv(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def run_pop3_ingest_from_env() -> Dict[str, int]:
    """환경변수로 POP3 수집을 실행합니다.

    Run POP3 ingest using environment variables.

    Env keys (new preferred):
    - EMAIL_POP3_HOST / EMAIL_POP3_PORT / EMAIL_POP3_USERNAME / EMAIL_POP3_PASSWORD
    - EMAIL_POP3_USE_SSL / EMAIL_POP3_TIMEOUT

    Fallback keys:
    - POP3_HOST / POP3_PORT / POP3_USERNAME / POP3_PASSWORD / POP3_USE_SSL / POP3_TIMEOUT
    """

    host = os.getenv("EMAIL_POP3_HOST") or os.getenv("POP3_HOST") or ""
    port = int(os.getenv("EMAIL_POP3_PORT") or os.getenv("POP3_PORT") or "995")
    username = os.getenv("EMAIL_POP3_USERNAME") or os.getenv("POP3_USERNAME") or ""
    password = os.getenv("EMAIL_POP3_PASSWORD") or os.getenv("POP3_PASSWORD") or ""
    use_ssl = _env_bool("EMAIL_POP3_USE_SSL", _env_bool("POP3_USE_SSL", True))
    timeout = int(os.getenv("EMAIL_POP3_TIMEOUT") or os.getenv("POP3_TIMEOUT") or "60")

    return run_pop3_ingest(
        host=host,
        port=port,
        username=username,
        password=password,
        use_ssl=use_ssl,
        timeout=timeout,
    )
