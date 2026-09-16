# =============================================================================
# 모듈 설명: Emails Outbox와 RAG 대기열 읽기 selector를 제공합니다.
# =============================================================================

from __future__ import annotations

from datetime import datetime

from django.db.models import Q

from ..models import Email, EmailOutbox
from .mailboxes import _normalize_time

def list_pending_rag_emails(*, limit: int) -> list[Email]:
    """rag_doc_id가 없는 이메일 목록을 limit 만큼 반환합니다.

    입력:
        limit: 조회할 최대 건수.
    반환:
        Email 리스트.
    부작용:
        없음. 조회 전용.
    오류:
        limit <= 0이면 빈 리스트 반환.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 검증
    # -----------------------------------------------------------------------------
    if limit <= 0:
        return []

    # -----------------------------------------------------------------------------
    # 2) 조회 실행
    # -----------------------------------------------------------------------------
    queryset = (
        Email.objects.filter(
            Q(rag_doc_id__isnull=True) | Q(rag_doc_id=""),
            classification_source=Email.ClassificationSource.CONFIRMED_USER,
            rag_index_status=Email.RagIndexStatus.PENDING,
        )
        .order_by("id")[:limit]
    )
    return list(queryset)


def list_pending_email_outbox(
    *,
    limit: int,
    ready_before: datetime | None = None,
    for_update: bool = False,
    skip_locked: bool = True,
) -> list[EmailOutbox]:
    """처리 대기 중인 EmailOutbox 항목을 반환합니다.

    입력:
        limit: 조회할 최대 건수.
        ready_before: 처리 가능 시각 상한.
        for_update: select_for_update 적용 여부.
        skip_locked: 잠긴 행 건너뛰기 여부.
    반환:
        EmailOutbox 리스트.
    부작용:
        없음. 조회 전용.
    오류:
        limit <= 0이면 빈 리스트 반환.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 검증
    # -----------------------------------------------------------------------------
    if limit <= 0:
        return []

    # -----------------------------------------------------------------------------
    # 2) 조회 쿼리 구성
    # -----------------------------------------------------------------------------
    when = _normalize_time(ready_before)
    queryset = EmailOutbox.objects.filter(
        status=EmailOutbox.Status.PENDING,
        available_at__lte=when,
    ).order_by("id")
    if for_update:
        queryset = queryset.select_for_update(skip_locked=skip_locked)
    queryset = queryset[:limit]
    return list(queryset)


def list_email_id_user_sdwt_by_ids(*, email_ids: list[int]) -> dict[int, str | None]:
    """Email id 목록으로 (id -> user_sdwt_prod) 매핑을 반환합니다.

    입력:
        email_ids: Email id 목록.
    반환:
        {id: user_sdwt_prod} 매핑.
    부작용:
        없음. 조회 전용.
    오류:
        email_ids가 비어 있으면 빈 dict 반환.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 검증
    # -----------------------------------------------------------------------------
    if not email_ids:
        return {}

    # -----------------------------------------------------------------------------
    # 2) 매핑 조회
    # -----------------------------------------------------------------------------
    rows = Email.objects.filter(id__in=email_ids).values("id", "user_sdwt_prod")
    return {row["id"]: row["user_sdwt_prod"] for row in rows}


def list_email_ids_by_sender_after(
    *,
    sender_id: str,
    received_at_gte: datetime,
) -> list[int]:
    """sender_id의 특정 시각 이후 이메일 id 목록을 반환합니다.

    입력:
        sender_id: Email.sender_id 값.
        received_at_gte: 기준 시각(이 시각 이상 수신).
    반환:
        Email id 리스트.
    부작용:
        없음. 조회 전용.
    오류:
        sender_id가 비어 있으면 빈 리스트 반환.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 검증
    # -----------------------------------------------------------------------------
    if not isinstance(sender_id, str) or not sender_id.strip():
        return []

    # -----------------------------------------------------------------------------
    # 2) id 목록 조회
    # -----------------------------------------------------------------------------
    normalized = sender_id.strip()
    return list(
        Email.objects.filter(sender_id=normalized, received_at__gte=received_at_gte)
        .values_list("id", flat=True)
        .order_by("id")
    )
