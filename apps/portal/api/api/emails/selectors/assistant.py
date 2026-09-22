# =============================================================================
# 모듈 설명: Assistant용 Emails scope 읽기 selector를 제공합니다.
# =============================================================================

from __future__ import annotations

from typing import Any

from django.db.models import Q

from ..models import Email
from .mailboxes import get_accessible_user_sdwt_prods_for_user, resolve_sender_id_from_user

def resolve_assistant_email_scope(
    *,
    user: Any,
    mailbox: str,
    email_id: object = None,
) -> dict[str, str] | None:
    """ChatWidget이 보낸 현재 메일함과 선택 메일을 서버 권한으로 재검증합니다.

    입력:
        user: 현재 인증 사용자입니다.
        mailbox: 현재 화면의 메일함 식별자입니다.
        email_id: 선택한 Email PK 또는 RAG 문서 ID입니다.
    반환:
        검증된 mailbox와 선택적 RAG 문서 ID이며, 권한이나 대상이 맞지 않으면 None입니다.
    부작용:
        없음. Email 한 건을 읽을 수 있습니다.
    """

    normalized_mailbox = str(mailbox or "").strip()
    if not normalized_mailbox:
        return None
    accessible_mailboxes = get_accessible_user_sdwt_prods_for_user(user)
    is_sent_mailbox = normalized_mailbox.casefold() == "sent"
    if not is_sent_mailbox and normalized_mailbox not in accessible_mailboxes:
        return None

    normalized_email_id = str(email_id or "").strip()
    if not normalized_email_id:
        if is_sent_mailbox:
            return None
        return {"mailbox": normalized_mailbox}

    email_query = Q(rag_doc_id=normalized_email_id)
    if normalized_email_id.isdigit():
        email_query |= Q(id=int(normalized_email_id))
    email = Email.objects.filter(email_query).first()
    if email is None:
        return None
    if is_sent_mailbox:
        sender_id = resolve_sender_id_from_user(user)
        if not sender_id or email.sender_id != sender_id:
            return None
    elif str(email.user_sdwt_prod or "").strip() != normalized_mailbox:
        return None

    resolved_mailbox = str(email.user_sdwt_prod or "").strip() or normalized_mailbox
    return {
        "mailbox": resolved_mailbox,
        "emailId": str(email.rag_doc_id or f"__unindexed__:{email.id}"),
    }
