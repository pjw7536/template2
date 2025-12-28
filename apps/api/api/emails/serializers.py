from __future__ import annotations

from typing import Any, Dict


def serialize_email_summary(email: Any) -> Dict[str, Any]:
    """Email 인스턴스를 목록 응답용 dict로 직렬화합니다."""

    snippet = (email.body_text or "").strip()
    if len(snippet) > 180:
        snippet = snippet[:177] + "..."
    return {
        "id": email.id,
        "messageId": email.message_id,
        "receivedAt": email.received_at.isoformat(),
        "subject": email.subject,
        "sender": email.sender,
        "senderId": email.sender_id,
        "recipient": email.recipient,
        "cc": email.cc,
        "userSdwtProd": email.user_sdwt_prod,
        "snippet": snippet,
        "ragDocId": email.rag_doc_id,
    }


def serialize_email_detail(email: Any) -> Dict[str, Any]:
    """Email 인스턴스를 상세 응답용 dict로 직렬화합니다."""

    return {
        **serialize_email_summary(email),
        "bodyText": email.body_text,
        "createdAt": email.created_at.isoformat(),
        "updatedAt": email.updated_at.isoformat(),
    }


__all__ = ["serialize_email_detail", "serialize_email_summary"]
