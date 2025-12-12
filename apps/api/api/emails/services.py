import gzip
import logging
from typing import List, Sequence

from api.common.affiliations import UNCLASSIFIED_USER_SDWT_PROD
from django.db import models
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from ..models import Email
from ..rag.client import delete_rag_doc, insert_email_to_rag, resolve_rag_index_name

logger = logging.getLogger(__name__)


def gzip_body(body_html: str | None) -> bytes | None:
    """HTML 문자열을 gzip 압축하여 BinaryField에 저장 가능하도록 변환."""

    if not body_html:
        return None
    return gzip.compress(body_html.encode("utf-8"))


def save_parsed_email(
    *,
    message_id,
    received_at,
    subject,
    sender,
    sender_id,
    recipient,
    user_sdwt_prod,
    body_html,
    body_text,
) -> Email:
    """POP3 파서에서 호출하는 저장 함수 (message_id 중복 방지)."""

    user_sdwt_prod = user_sdwt_prod or UNCLASSIFIED_USER_SDWT_PROD

    email, _created = Email.objects.get_or_create(
        message_id=message_id,
        defaults={
            "received_at": received_at or timezone.now(),
            "subject": subject,
            "sender": sender,
            "sender_id": sender_id,
            "recipient": recipient,
            "user_sdwt_prod": user_sdwt_prod,
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
        if fields_to_update:
            email.save(update_fields=fields_to_update)
    return email


def register_email_to_rag(
    email: Email,
    previous_user_sdwt_prod: str | None = None,
    persist_fields: Sequence[str] | None = None,
) -> Email:
    """
    이메일을 RAG에 등록하고 rag_doc_id를 저장.
    - 이미 rag_doc_id가 있으면 그대로 사용.
    - 실패 시 예외를 발생시켜 호출 측에서 재시도 가능.
    - previous_user_sdwt_prod가 주어지면, 인덱스가 달라진 경우 이전 인덱스 문서를 삭제 후 재삽입
    """

    update_fields = []
    if not email.user_sdwt_prod:
        email.user_sdwt_prod = UNCLASSIFIED_USER_SDWT_PROD
        update_fields.append("user_sdwt_prod")
    if not email.rag_doc_id:
        email.rag_doc_id = f"email-{email.id}"
        update_fields.append("rag_doc_id")

    new_index = resolve_rag_index_name(email.user_sdwt_prod)
    previous_index = (
        resolve_rag_index_name(previous_user_sdwt_prod)
        if previous_user_sdwt_prod is not None
        else new_index
    )

    if email.rag_doc_id and previous_user_sdwt_prod is not None and previous_index != new_index:
        try:
            delete_rag_doc(email.rag_doc_id, index_name=previous_index)
        except Exception:
            logger.exception(
                "Failed to delete previous RAG doc for email id=%s (index=%s)", email.id, previous_index
            )

    target_index = new_index
    insert_email_to_rag(email, index_name=target_index)
    if persist_fields:
        update_fields.extend(list(persist_fields))
    if update_fields:
        email.save(update_fields=list(dict.fromkeys(update_fields)))  # deduplicate
    return email


def register_missing_rag_docs(limit: int = 500) -> int:
    """
    rag_doc_id가 없는 이메일을 다시 RAG에 등록 시도한다.
    - POP3 삭제 이후 RAG 등록 실패 건을 재시도하기 위한 백필용.
    """

    pending = list(
        Email.objects.filter(models.Q(rag_doc_id__isnull=True) | models.Q(rag_doc_id="")).order_by("id")[:limit]
    )
    registered = 0

    for email in pending:
        try:
            register_email_to_rag(email)
            registered += 1
        except Exception:
            logger.exception("Failed to register missing RAG doc for email id=%s", email.id)

    return registered


@transaction.atomic
def delete_single_email(email_id: int):
    """단일 메일 삭제 (RAG 삭제 실패 시 전체 롤백)."""

    try:
        email = Email.objects.select_for_update().get(id=email_id)
    except Email.DoesNotExist:
        raise NotFound("Email not found")

    if email.rag_doc_id:
        delete_rag_doc(email.rag_doc_id, index_name=resolve_rag_index_name(email.user_sdwt_prod))  # 실패 시 예외 발생 → 트랜잭션 롤백

    email.delete()
    return email


@transaction.atomic
def bulk_delete_emails(email_ids: List[int]) -> int:
    """여러 메일을 한 번에 삭제 (all-or-nothing)."""

    emails = list(Email.objects.select_for_update().filter(id__in=email_ids))
    if not emails:
        raise NotFound("No emails found to delete")

    for email in emails:
        if email.rag_doc_id:
            delete_rag_doc(email.rag_doc_id, index_name=resolve_rag_index_name(email.user_sdwt_prod))  # 실패 시 예외 → 전체 롤백

    target_ids = [email.id for email in emails]
    Email.objects.filter(id__in=target_ids).delete()

    return len(emails)
