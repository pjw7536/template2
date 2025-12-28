# =============================================================================
# 모듈 설명: Email 응답 직렬화를 담당합니다.
# - 주요 함수: serialize_email_summary, serialize_email_detail
# - 불변 조건: 응답 키는 camelCase를 사용합니다.
# =============================================================================

from __future__ import annotations

from typing import Any, Dict


def serialize_email_summary(email: Any) -> Dict[str, Any]:
    """Email 인스턴스를 목록 응답용 dict로 직렬화합니다.

    입력:
        email: Email 모델 인스턴스 또는 유사 객체.
    반환:
        목록 응답용 dict (camelCase 키).
    부작용:
        없음.
    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) 본문 스니펫 정규화
    # -----------------------------------------------------------------------------
    snippet = (email.body_text or "").strip()
    if len(snippet) > 180:
        snippet = snippet[:177] + "..."

    # -----------------------------------------------------------------------------
    # 2) 응답 payload 구성
    # -----------------------------------------------------------------------------
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
    """Email 인스턴스를 상세 응답용 dict로 직렬화합니다.

    입력:
        email: Email 모델 인스턴스 또는 유사 객체.
    반환:
        상세 응답용 dict (camelCase 키, 본문 포함).
    부작용:
        없음.
    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) 상세 응답 구성
    # -----------------------------------------------------------------------------
    return {
        **serialize_email_summary(email),
        "bodyText": email.body_text,
        "createdAt": email.created_at.isoformat(),
        "updatedAt": email.updated_at.isoformat(),
    }


__all__ = ["serialize_email_detail", "serialize_email_summary"]
