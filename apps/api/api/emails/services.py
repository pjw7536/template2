import gzip
from typing import List

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from ..models import Email
from ..rag.client import delete_rag_doc, insert_email_to_rag


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
    department_code,
    body_html,
    body_text,
) -> Email:
    """POP3 파서에서 호출하는 저장 함수 (message_id 중복 방지)."""

    email, _created = Email.objects.get_or_create(
        message_id=message_id,
        defaults={
            "received_at": received_at or timezone.now(),
            "subject": subject,
            "sender": sender,
            "sender_id": sender_id,
            "recipient": recipient,
            "department_code": department_code,
            "body_text": body_text or "",
            "body_html_gzip": gzip_body(body_html),
        },
    )
    if not _created:
        fields_to_update = []
        if not email.sender_id:
            email.sender_id = sender_id
            fields_to_update.append("sender_id")
        if not email.department_code:
            email.department_code = department_code
            fields_to_update.append("department_code")
        if fields_to_update:
            email.save(update_fields=fields_to_update)
    return email


def register_email_to_rag(email: Email) -> Email:
    """
    이메일을 RAG에 등록하고 rag_doc_id를 저장.
    - 이미 rag_doc_id가 있으면 그대로 사용.
    - 실패 시 예외를 발생시켜 호출 측에서 재시도 가능.
    """

    update_fields = []
    if not email.department_code:
        email.department_code = "UNKNOWN"
        update_fields.append("department_code")
    if not email.rag_doc_id:
        email.rag_doc_id = f"email-{email.id}"
        update_fields.append("rag_doc_id")

    insert_email_to_rag(email)
    if update_fields:
        email.save(update_fields=update_fields)
    return email


@transaction.atomic
def delete_single_email(email_id: int):
    """단일 메일 삭제 (RAG 삭제 실패 시 전체 롤백)."""

    try:
        email = Email.objects.select_for_update().get(id=email_id)
    except Email.DoesNotExist:
        raise NotFound("Email not found")

    if email.rag_doc_id:
        delete_rag_doc(email.rag_doc_id)  # 실패 시 예외 발생 → 트랜잭션 롤백

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
            delete_rag_doc(email.rag_doc_id)  # 실패 시 예외 → 전체 롤백

    target_ids = [email.id for email in emails]
    Email.objects.filter(id__in=target_ids).delete()

    return len(emails)
