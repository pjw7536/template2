# =============================================================================
# 모듈 설명: Emails 쓰기 service가 사용하는 잠금·권한 읽기 selector를 제공합니다.
# =============================================================================

from __future__ import annotations

from typing import Sequence

from django.db.models import Q

from ..models import Email

def get_email_for_update(*, email_id: int) -> Email:
    """Email을 행 잠금(select_for_update)으로 조회합니다.

    입력:
        email_id: Email PK(이메일 ID).
    반환:
        Email 인스턴스.
    부작용:
        없음. 호출 측 트랜잭션에서 행 잠금이 발생합니다.
    오류:
        Email.DoesNotExist 예외가 발생할 수 있습니다.
    """

    return Email.objects.select_for_update().get(id=email_id)


def list_emails_for_update(*, email_ids: Sequence[int]) -> list[Email]:
    """Email 목록을 행 잠금(select_for_update)으로 조회합니다.

    입력:
        email_ids: Email id 목록.
    반환:
        Email 인스턴스 리스트(없으면 빈 리스트).
    부작용:
        없음. 호출 측 트랜잭션에서 행 잠금이 발생합니다.
    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 검증
    # -----------------------------------------------------------------------------
    if not email_ids:
        return []
    normalized = sorted(
        {
            int(value)
            for value in email_ids
            if isinstance(value, int) or str(value).isdigit()
        }
    )
    if not normalized:
        return []

    # -----------------------------------------------------------------------------
    # 2) 행 잠금 조회
    # -----------------------------------------------------------------------------
    return list(
        Email.objects.select_for_update()
        .filter(id__in=normalized)
        .order_by("id")
    )

def user_can_bulk_delete_emails(
    *,
    email_ids: list[int],
    accessible_user_sdwt_prods: set[str],
    sender_id: str | None = None,
) -> bool:
    """요청한 email_ids가 모두 접근 가능한 user_sdwt_prod 범위인지 검사합니다.

    입력:
        email_ids: 삭제 요청 Email id 목록.
        accessible_user_sdwt_prods: 접근 가능한 user_sdwt_prod 집합.
        sender_id: 본인 발신자 ID(옵션).
    반환:
        모든 id가 접근 가능 범위면 True.
    부작용:
        없음. 조회 전용.
    오류:
        email_ids가 비어 있으면 False 반환.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 검증
    # -----------------------------------------------------------------------------
    if not email_ids:
        return False

    # -----------------------------------------------------------------------------
    # 2) 접근 범위 필터 구성
    # -----------------------------------------------------------------------------
    mailbox_filter = Q(user_sdwt_prod__in=accessible_user_sdwt_prods)
    normalized_sender_id = sender_id.strip() if isinstance(sender_id, str) else ""
    if normalized_sender_id:
        mailbox_filter |= Q(sender_id=normalized_sender_id)

    # -----------------------------------------------------------------------------
    # 3) 접근 가능한 메일 개수 비교
    # -----------------------------------------------------------------------------
    owned_count = Email.objects.filter(id__in=email_ids).filter(mailbox_filter).count()
    return owned_count == len(email_ids)
