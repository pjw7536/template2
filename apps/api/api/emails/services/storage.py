# =============================================================================
# 모듈 설명: 이메일 저장/압축 유틸을 제공합니다.
# - 주요 함수: gzip_body, save_parsed_email
# - 불변 조건: message_id는 중복 방지 키로 사용됩니다.
# =============================================================================

from __future__ import annotations

import gzip
from datetime import datetime
from typing import Any, Sequence

from django.utils import timezone

from api.common.affiliations import UNASSIGNED_USER_SDWT_PROD

from ..models import Email
from .utils import _build_participants_search, _normalize_participants


def gzip_body(body_html: str | None) -> bytes | None:
    """HTML 문자열을 gzip 압축하여 BinaryField 저장 형식으로 변환합니다.

    입력:
        body_html: HTML 문자열 또는 None.
    반환:
        gzip 압축 바이트 또는 None.
    부작용:
        없음.
    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 검증 및 압축 수행
    # -----------------------------------------------------------------------------
    if not body_html:
        return None
    return gzip.compress(body_html.encode("utf-8"))


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
    """POP3 파서에서 호출하는 저장 함수입니다(message_id 중복 방지).

    입력:
        message_id: 이메일 고유 식별자.
        received_at: 수신 시각(없으면 현재 시각).
        subject/sender/sender_id: 제목/발신자 정보.
        recipient/cc: 수신/참조 목록.
        user_sdwt_prod: 메일함 식별자.
        classification_source: 분류 출처 코드.
        rag_index_status: RAG 인덱싱 상태.
        body_html/body_text: 본문 데이터.
    반환:
        저장/갱신된 Email 인스턴스.
    부작용:
        Email 테이블에 insert/update 수행.
    오류:
        ORM 예외가 발생할 수 있음.
    """

    # -----------------------------------------------------------------------------
    # 1) 기본값/참여자 정규화
    # -----------------------------------------------------------------------------
    user_sdwt_prod = user_sdwt_prod or UNASSIGNED_USER_SDWT_PROD

    normalized_recipient = _normalize_participants(recipient)
    normalized_cc = _normalize_participants(cc)
    participants_search = _build_participants_search(recipient=normalized_recipient, cc=normalized_cc)

    # -----------------------------------------------------------------------------
    # 2) message_id 기준 upsert
    # -----------------------------------------------------------------------------
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

    # -----------------------------------------------------------------------------
    # 3) 기존 레코드 보정 업데이트
    # -----------------------------------------------------------------------------
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
