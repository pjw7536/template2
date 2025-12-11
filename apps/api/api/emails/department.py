from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional

from ..models import Email, UserDepartmentHistory
from ..rag.client import delete_rag_doc, insert_email_to_rag

logger = logging.getLogger(__name__)

UNKNOWN_DEPARTMENT = "UNKNOWN"


def get_department_for(sender_id: str, received_at: datetime) -> str:
    """
    발신자(sender_id)와 메일 수신시간(received_at)을 기반으로,
    그 시점에 유효한 부서 코드를 조회하여 반환한다.
    """

    history = (
        UserDepartmentHistory.objects.filter(employee_id=sender_id, effective_from__lte=received_at)
        .order_by("-effective_from")
        .first()
    )
    if history:
        return history.department_code
    return UNKNOWN_DEPARTMENT


def _delete_and_reinsert_email(email: Email):
    """단일 Email의 RAG 문서를 새 department_code 기준으로 재생성."""

    if not email.rag_doc_id:
        email.rag_doc_id = f"email-{email.id}"

    try:
        delete_rag_doc(email.rag_doc_id)
    except Exception:
        logger.exception("Failed to delete RAG doc for email id=%s", email.id)

    try:
        insert_email_to_rag(email)
        email.save(update_fields=["department_code", "rag_doc_id"])
    except Exception:
        # 재삽입 실패 시에도 department_code 업데이트는 유지
        email.save(update_fields=["department_code", "rag_doc_id"])
        logger.exception("Failed to reinsert RAG doc for email id=%s", email.id)


def reclassify_emails_for_department_change(
    employee_id: str,
    department_code: str,
    effective_from: datetime,
) -> int:
    """
    특정 직원의 부서 이동 이력이 effective_from 시점에 추가/수정되었을 때,
    해당 시점부터 다음 이력 변경 전까지의 모든 메일을 새 부서로 재분류한다.
    """

    try:
        UserDepartmentHistory.objects.get(
            employee_id=employee_id,
            department_code=department_code,
            effective_from=effective_from,
        )
    except UserDepartmentHistory.DoesNotExist as exc:  # pragma: no cover - defensive guard
        raise ValueError("해당 부서 이력 row를 찾을 수 없습니다.") from exc

    next_history: Optional[UserDepartmentHistory] = (
        UserDepartmentHistory.objects.filter(employee_id=employee_id, effective_from__gt=effective_from)
        .order_by("effective_from")
        .first()
    )

    start = effective_from
    end = next_history.effective_from if next_history else None

    qs = Email.objects.filter(sender_id=employee_id, received_at__gte=start)
    if end is not None:
        qs = qs.filter(received_at__lt=end)

    email_ids: List[int] = list(qs.values_list("id", flat=True))
    if not email_ids:
        return 0

    # department_code를 먼저 일괄 업데이트 (스냅샷 재설정)
    Email.objects.filter(id__in=email_ids).update(department_code=department_code)

    # 이후 RAG 재색인 (batch 최적화 필요 시 별도 배치 처리 가능)
    for email in Email.objects.filter(id__in=email_ids).iterator():
        email.department_code = department_code
        _delete_and_reinsert_email(email)

    return len(email_ids)
