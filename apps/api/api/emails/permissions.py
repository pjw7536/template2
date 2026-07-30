# =============================================================================
# 모듈 설명: emails 기능의 접근 권한 판별 유틸을 정의합니다.
# - 주요 함수: resolve_access_control, user_can_access_email
# - 불변 조건: UNASSIGNED 메일함은 특권 사용자만 기본 접근 가능합니다.
# =============================================================================

from __future__ import annotations

from typing import Any, Optional, Set

from django.http import HttpRequest

from api.account import services as account_services
from api.common.services import UNASSIGNED_USER_SDWT_PROD

from .selectors import (
    get_accessible_user_sdwt_prods_for_user,
    resolve_sender_id_from_user,
)


def _email_is_unassigned(email: Any) -> bool:
    """Email 인스턴스가 UNASSIGNED(미분류) 메일인지 판별합니다.

    입력:
        email: Email 모델 인스턴스 또는 유사 객체.
    반환:
        UNASSIGNED 메일이면 True.
    부작용:
        없음.
    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) user_sdwt_prod 값 추출
    # -----------------------------------------------------------------------------
    raw = getattr(email, "user_sdwt_prod", None)
    if raw is None:
        return True
    if not isinstance(raw, str):
        return False

    # -----------------------------------------------------------------------------
    # 2) 문자열 정규화 및 UNASSIGNED 판별
    # -----------------------------------------------------------------------------
    normalized = raw.strip()
    return normalized in {"", UNASSIGNED_USER_SDWT_PROD, "rp-unclassified"}


def _user_can_access_email(
    user: Any,
    email: Any,
    accessible: Optional[Set[str]],
    *,
    is_privileged: bool = False,
) -> bool:
    """일반 사용자 기준으로 특정 이메일 접근 권한을 검사합니다.

    입력:
        user: Django User 또는 유사 객체.
        email: Email 인스턴스 또는 유사 객체.
        accessible: 접근 가능한 user_sdwt_prod 집합.
    반환:
        접근 허용이면 True.
    부작용:
        없음.
    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) 특권 사용자 우선 허용
    # -----------------------------------------------------------------------------
    if is_privileged:
        return True
    if accessible is None:
        return False

    # -----------------------------------------------------------------------------
    # 2) 발신자/메일함 범위 검증
    # -----------------------------------------------------------------------------
    sender_id = resolve_sender_id_from_user(user)
    if sender_id and getattr(email, "sender_id", None) == sender_id:
        return True
    return bool(getattr(email, "user_sdwt_prod", None) and email.user_sdwt_prod in accessible)


def resolve_email_access_denial(
    *,
    user: Any,
    email: Any,
    is_privileged: bool,
    accessible: Optional[Set[str]],
) -> str | None:
    """단일 메일 접근 실패 사유를 반환합니다.

    입력:
        user: Django User 또는 유사 객체.
        email: Email 인스턴스 또는 None.
        is_privileged: 특권 사용자 여부.
        accessible: 접근 가능한 user_sdwt_prod 집합.
    반환:
        "not_found", "forbidden" 또는 None(접근 허용).
    부작용:
        없음.
    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) 대상 존재 여부 확인
    # -----------------------------------------------------------------------------
    if email is None:
        return "not_found"

    # -----------------------------------------------------------------------------
    # 2) UNASSIGNED 정책을 기존 순서 그대로 적용
    # -----------------------------------------------------------------------------
    if _email_is_unassigned(email) and not is_privileged:
        if not _user_can_access_email(
            user,
            email,
            accessible,
            is_privileged=is_privileged,
        ):
            return "forbidden"

    # -----------------------------------------------------------------------------
    # 3) 일반 사용자 접근 범위 확인
    # -----------------------------------------------------------------------------
    if not is_privileged:
        if not accessible or not _user_can_access_email(
            user,
            email,
            accessible,
            is_privileged=is_privileged,
        ):
            return "forbidden"

    return None


def user_can_access_mailbox(
    *,
    user: Any,
    mailbox_user_sdwt_prod: str,
    is_privileged: bool,
    accessible: Set[str],
) -> bool:
    """요청 사용자가 특정 메일함에 접근 가능한지 확인합니다.

    입력:
        user: Django User 또는 유사 객체.
        mailbox_user_sdwt_prod: 대상 메일함 식별자.
        is_privileged: 특권 사용자 여부.
        accessible: 접근 가능한 user_sdwt_prod 집합.
    반환:
        접근 가능하면 True.
    부작용:
        없음.
    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) 빈 메일함 필터는 전체 접근 범위 조회를 의미합니다.
    # -----------------------------------------------------------------------------
    if not mailbox_user_sdwt_prod:
        return True

    # -----------------------------------------------------------------------------
    # 2) UNASSIGNED 접근 정책과 일반 사용자 접근 범위 확인
    # -----------------------------------------------------------------------------
    if mailbox_user_sdwt_prod == UNASSIGNED_USER_SDWT_PROD and not is_privileged:
        return False
    if not is_privileged and mailbox_user_sdwt_prod not in accessible:
        return False
    return True


def resolve_access_control(request: HttpRequest) -> tuple[bool, bool, Set[str]]:
    """공통 권한 처리 결과(인증/특권/접근 범위)를 반환합니다.

    입력:
        요청: Django HttpRequest.
    반환:
        (is_authenticated, is_privileged, accessible_user_sdwt_prods) (인증/특권/접근 범위)
    부작용:
        없음.
    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) 인증 여부 확인
    # -----------------------------------------------------------------------------
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return False, False, set()

    # -----------------------------------------------------------------------------
    # 2) 모든 사용자에게 전역 식별자인 sender_id를 요구
    # -----------------------------------------------------------------------------
    if not resolve_sender_id_from_user(user):
        return True, False, set()

    # -----------------------------------------------------------------------------
    # 3) 앱 접근과 독립된 Emails 데이터 범위를 계산
    # -----------------------------------------------------------------------------
    data_scope = account_services.get_effective_affiliation_scope(
        user=user,
        scope_key="emails",
        request=request,
    )
    if not data_scope.get("allowed"):
        return True, False, set()

    # -----------------------------------------------------------------------------
    # 4) 전체 범위와 Emails admin 역할을 함께 가져야 전역 운영 특권을 부여
    # -----------------------------------------------------------------------------
    accessible = {
        str(affiliation.get("userSdwtProd") or "").strip()
        for affiliation in data_scope.get("affiliations", [])
        if str(affiliation.get("userSdwtProd") or "").strip()
    }
    is_privileged = bool(
        data_scope.get("all")
        and account_services.has_scope_role(
            user=user,
            scope_key="emails",
            request=request,
        )
    )
    return True, is_privileged, accessible


__all__ = [
    "resolve_access_control",
    "resolve_email_access_denial",
    "user_can_access_mailbox",
]
