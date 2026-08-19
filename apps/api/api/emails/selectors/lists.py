# =============================================================================
# 모듈 설명: Emails 목록·상세 읽기 selector를 제공합니다.
# =============================================================================

from __future__ import annotations

from datetime import datetime

from django.db.models import Q, QuerySet

from api.account.selectors import list_distinct_user_sdwt_prod_values
from api.common.services import UNASSIGNED_USER_SDWT_PROD

from ..models import Email
from .mailboxes import _unassigned_mailbox_query

def list_emails_by_ids(*, email_ids: list[int]) -> QuerySet[Email]:
    """Email id 목록으로 Email QuerySet을 조회합니다.

    입력:
        email_ids: Email id 목록.
    반환:
        Email QuerySet(조회 결과).
    부작용:
        없음. 조회 전용.
    오류:
        email_ids가 비어 있으면 빈 QuerySet 반환.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 검증
    # -----------------------------------------------------------------------------
    if not email_ids:
        return Email.objects.none()
    return Email.objects.filter(id__in=email_ids).order_by("id")


def _apply_email_common_filters(
    queryset: QuerySet[Email],
    *,
    search: str,
    sender: str,
    recipient: str,
    date_from: datetime | None,
    date_to: datetime | None,
) -> QuerySet[Email]:
    """메일 목록 공통 검색/기간 필터를 QuerySet에 적용합니다.

    입력:
        queryset: 기본 Email QuerySet.
        search: 자유 검색(제목/본문/발신자/참여자).
        sender: 발신자 문자열 필터.
        recipient: 수신자 문자열 필터(To/Cc).
        date_from: 시작 시각(포함).
        date_to: 종료 시각(포함).
    반환:
        공통 필터가 적용된 QuerySet.
    부작용:
        없음. 조회 전용.
    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) 텍스트 검색 필터 적용
    # -----------------------------------------------------------------------------
    if search:
        normalized_participant_search = search.lower()
        queryset = queryset.filter(
            Q(subject__icontains=search)
            | Q(body_text__icontains=search)
            | Q(sender__icontains=search)
            | Q(participants_search__contains=normalized_participant_search)
        )
    if sender:
        queryset = queryset.filter(sender__icontains=sender)
    if recipient:
        queryset = queryset.filter(participants_search__contains=recipient.lower())

    # -----------------------------------------------------------------------------
    # 2) 수신 시각 범위 필터 적용
    # -----------------------------------------------------------------------------
    if date_from:
        queryset = queryset.filter(received_at__gte=date_from)
    if date_to:
        queryset = queryset.filter(received_at__lte=date_to)

    return queryset


def get_filtered_emails(
    *,
    accessible_user_sdwt_prods: set[str],
    is_privileged: bool,
    can_view_unassigned: bool,
    mailbox_user_sdwt_prod: str,
    search: str,
    sender: str,
    recipient: str,
    date_from: datetime | None,
    date_to: datetime | None,
) -> QuerySet[Email]:
    """검색/기간/발신자/수신자 조건으로 Email QuerySet을 필터링해 반환합니다.

    입력:
        accessible_user_sdwt_prods: 접근 가능한 user_sdwt_prod 집합.
        is_privileged: 특권 사용자 여부(메일함 필터 생략).
        can_view_unassigned: UNASSIGNED 조회 가능 여부.
        mailbox_user_sdwt_prod: 특정 메일함 필터 값.
        search: 자유 검색(제목/본문/발신자/참여자).
        sender: 발신자 문자열 필터.
        recipient: 수신자 문자열 필터(To/Cc).
        date_from: 시작 시각(포함).
        date_to: 종료 시각(포함).
    반환:
        최신순으로 정렬된 Email QuerySet.
    부작용:
        없음. 조회 전용.
    오류:
        접근 범위가 비어 있고 특권이 아니면 빈 QuerySet 반환.
    """

    # -----------------------------------------------------------------------------
    # 1) 접근 범위 검증
    # -----------------------------------------------------------------------------
    if not is_privileged and not accessible_user_sdwt_prods:
        return Email.objects.none()

    # -----------------------------------------------------------------------------
    # 2) 기본 쿼리 구성 및 권한 필터
    # -----------------------------------------------------------------------------
    queryset = Email.objects.order_by("-received_at", "-id")
    if not is_privileged:
        queryset = queryset.filter(user_sdwt_prod__in=accessible_user_sdwt_prods)

    if not can_view_unassigned:
        queryset = queryset.exclude(_unassigned_mailbox_query())

    # -----------------------------------------------------------------------------
    # 3) 메일함 및 공통 검색/기간 필터 적용
    # -----------------------------------------------------------------------------
    if mailbox_user_sdwt_prod:
        queryset = queryset.filter(user_sdwt_prod=mailbox_user_sdwt_prod)

    return _apply_email_common_filters(
        queryset,
        search=search,
        sender=sender,
        recipient=recipient,
        date_from=date_from,
        date_to=date_to,
    )


def get_sent_emails(
    *,
    sender_id: str,
    search: str,
    sender: str,
    recipient: str,
    date_from: datetime | None,
    date_to: datetime | None,
) -> QuerySet[Email]:
    """발신자(sender_id) 기준으로 보낸 메일 QuerySet을 반환합니다.

    입력:
        sender_id: Email.sender_id (KNOX ID, 발신자 식별자).
        search: 자유 검색(제목/본문/발신자/참여자).
        sender: 발신자 문자열 필터.
        recipient: 수신자 문자열 필터(To/Cc).
        date_from: 시작 시각(포함).
        date_to: 종료 시각(포함).
    반환:
        최신순으로 정렬된 Email QuerySet.
    부작용:
        없음. 조회 전용.
    오류:
        sender_id가 비어 있으면 빈 QuerySet 반환.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 검증 및 기본 쿼리 구성
    # -----------------------------------------------------------------------------
    if not isinstance(sender_id, str) or not sender_id.strip():
        return Email.objects.none()

    queryset = Email.objects.filter(sender_id=sender_id.strip()).order_by("-received_at", "-id")

    # -----------------------------------------------------------------------------
    # 2) 공통 검색/기간 필터 적용
    # -----------------------------------------------------------------------------
    return _apply_email_common_filters(
        queryset,
        search=search,
        sender=sender,
        recipient=recipient,
        date_from=date_from,
        date_to=date_to,
    )


def list_distinct_email_mailboxes() -> list[str]:
    """Email 테이블에서 중복 제거된 user_sdwt_prod 목록을 반환합니다.

    입력:
        없음.
    반환:
        중복 제거된 user_sdwt_prod 문자열 리스트(정렬됨).
    부작용:
        없음. 조회 전용.
    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) distinct 쿼리 수행
    # -----------------------------------------------------------------------------
    queryset = (
        Email.objects.exclude(user_sdwt_prod__isnull=True)
        .exclude(user_sdwt_prod="")
        .values_list("user_sdwt_prod", flat=True)
        .distinct()
        .order_by("user_sdwt_prod")
    )
    return list(queryset)


def list_privileged_email_mailboxes() -> list[str]:
    """Emails 관리자가 볼 메일함(user_sdwt_prod) 목록을 반환합니다.

    입력:
        없음.
    반환:
        Emails 관리자에게 노출할 user_sdwt_prod 목록(정렬됨).
    부작용:
        없음. 조회 전용.
    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) 계정/메일 기준 목록 병합
    # -----------------------------------------------------------------------------
    known = set(list_distinct_user_sdwt_prod_values())
    known.update(list_distinct_email_mailboxes())
    known.add(UNASSIGNED_USER_SDWT_PROD)
    return sorted({val for val in known if isinstance(val, str) and val.strip()})


def get_email_by_id(*, email_id: int) -> Email | None:
    """email_id로 Email을 조회하고 없으면 None을 반환합니다.

    입력:
        email_id: Email PK(이메일 ID).
    반환:
        Email 인스턴스 또는 None.
    부작용:
        없음. 조회 전용.
    오류:
        없으면 None 반환.
    """

    # -----------------------------------------------------------------------------
    # 1) PK 조회
    # -----------------------------------------------------------------------------
    try:
        return Email.objects.get(id=email_id)
    except Email.DoesNotExist:
        return None
