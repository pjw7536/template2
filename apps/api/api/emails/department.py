from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Optional

from api.common.affiliations import UNCLASSIFIED_USER_SDWT_PROD
from ..models import Email, SenderSdwtHistory
from ..rag.client import delete_rag_doc, insert_email_to_rag, resolve_rag_index_name

logger = logging.getLogger(__name__)


def _delete_and_reinsert_email(email: Email, previous_user_sdwt_prod: Optional[str] = None):
    """단일 Email의 RAG 문서를 최신 user_sdwt_prod 기준으로 재생성."""

    if not email.rag_doc_id:
        email.rag_doc_id = f"email-{email.id}"
    old_index = resolve_rag_index_name(
        previous_user_sdwt_prod if previous_user_sdwt_prod is not None else email.user_sdwt_prod
    )
    new_index = resolve_rag_index_name(email.user_sdwt_prod)

    try:
        delete_rag_doc(email.rag_doc_id, index_name=old_index)
    except Exception:
        logger.exception("Failed to delete RAG doc for email id=%s (index=%s)", email.id, old_index)

    try:
        insert_email_to_rag(email, index_name=new_index)
        email.save(update_fields=["user_sdwt_prod", "rag_doc_id"])
    except Exception:
        # 재삽입 실패 시에도 소속 업데이트는 유지
        email.save(update_fields=["user_sdwt_prod", "rag_doc_id"])
        logger.exception("Failed to reinsert RAG doc for email id=%s (index=%s)", email.id, new_index)


def reclassify_emails_for_sender_history_change(
    sender_id: str,
    effective_from: datetime,
) -> int:
    """
    SenderSdwtHistory 기준 user_sdwt_prod 이력이 effective_from 시점에 추가/수정되었을 때,
    해당 시점부터 다음 이력 변경 전까지의 모든 메일을 새 소속으로 재분류한다.
    """

    history: Optional[SenderSdwtHistory] = (
        SenderSdwtHistory.objects.filter(sender_id=sender_id, effective_from=effective_from)
        .order_by("-id")
        .first()
    )
    if not history:
        raise ValueError("해당 소속 이력 row를 찾을 수 없습니다.")

    user_sdwt_prod = history.user_sdwt_prod or UNCLASSIFIED_USER_SDWT_PROD

    next_history: Optional[SenderSdwtHistory] = (
        SenderSdwtHistory.objects.filter(sender_id=sender_id, effective_from__gt=effective_from)
        .order_by("effective_from", "id")
        .first()
    )

    start = effective_from
    end = next_history.effective_from if next_history else None

    qs = Email.objects.filter(sender_id=sender_id, received_at__gte=start)
    if end is not None:
        qs = qs.filter(received_at__lt=end)

    previous_user_sdwt: Dict[int, Optional[str]] = {
        row["id"]: row["user_sdwt_prod"] for row in qs.values("id", "user_sdwt_prod")
    }
    email_ids: List[int] = list(previous_user_sdwt.keys())
    if not email_ids:
        return 0

    # 소속 스냅샷을 일괄 업데이트
    Email.objects.filter(id__in=email_ids).update(
        user_sdwt_prod=user_sdwt_prod,
    )

    # 이후 RAG 재색인 (batch 최적화 필요 시 별도 배치 처리 가능)
    for email in Email.objects.filter(id__in=email_ids).iterator():
        email.user_sdwt_prod = user_sdwt_prod
        _delete_and_reinsert_email(email, previous_user_sdwt_prod=previous_user_sdwt.get(email.id))

    return len(email_ids)
