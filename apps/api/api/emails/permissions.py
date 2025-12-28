# =============================================================================
# 모듈 설명: emails 기능의 접근 권한 판별 유틸을 정의합니다.
# - 주요 함수: resolve_access_control, user_can_access_email
# - 불변 조건: UNASSIGNED 메일함은 특권 사용자만 기본 접근 가능합니다.
# =============================================================================

from __future__ import annotations

from typing import Any, Optional, Set

from django.http import HttpRequest

from api.common.affiliations import UNASSIGNED_USER_SDWT_PROD
from api.common.utils import extract_bearer_token

from .selectors import get_accessible_user_sdwt_prods_for_user


def user_can_view_unassigned(user: Any) -> bool:
    """UNASSIGNED(미분류) 메일함 조회 가능 여부를 반환합니다.

    입력:
        user: Django User 또는 유사 객체.
    반환:
        True면 UNASSIGNED 메일함 조회 허용.
    부작용:
        없음.
    오류:
        없음.
    """

    return bool(
        user
        and (getattr(user, "is_superuser", False) or getattr(user, "is_staff", False))
    )


def email_is_unassigned(email: Any) -> bool:
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


def resolve_accessible_user_sdwt_prods(user: Any) -> Set[str]:
    """사용자가 접근 가능한 user_sdwt_prod 목록(집합)을 조회합니다.

    입력:
        user: Django User 또는 유사 객체.
    반환:
        접근 가능한 user_sdwt_prod 값 집합.
    부작용:
        없음. 조회 전용.
    오류:
        없음.
    """

    return get_accessible_user_sdwt_prods_for_user(user)


def _resolve_sender_id_from_user(user: Any) -> str | None:
    """사용자에서 sender_id(knox_id)를 추출합니다.

    입력:
        user: Django User 또는 유사 객체.
    반환:
        유효한 knox_id 문자열 또는 None.
    부작용:
        없음.
    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) knox_id 후보 추출
    # -----------------------------------------------------------------------------
    knox_id = getattr(user, "knox_id", None)
    if isinstance(knox_id, str) and knox_id.strip():
        return knox_id.strip()
    return None


def user_can_access_email(
    user: Any,
    email: Any,
    accessible: Optional[Set[str]],
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
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return True
    if accessible is None:
        return False

    # -----------------------------------------------------------------------------
    # 2) 발신자/메일함 범위 검증
    # -----------------------------------------------------------------------------
    sender_id = _resolve_sender_id_from_user(user)
    if sender_id and getattr(email, "sender_id", None) == sender_id:
        return True
    return bool(getattr(email, "user_sdwt_prod", None) and email.user_sdwt_prod in accessible)


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
    # 2) sender_id 유무 및 특권 여부 판단
    # -----------------------------------------------------------------------------
    if not _resolve_sender_id_from_user(user):
        return True, False, set()

    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return True, True, set()

    # -----------------------------------------------------------------------------
    # 3) 접근 가능한 메일함 목록 조회
    # -----------------------------------------------------------------------------
    accessible = resolve_accessible_user_sdwt_prods(user)
    return True, False, accessible


__all__ = [
    "email_is_unassigned",
    "extract_bearer_token",
    "resolve_access_control",
    "resolve_accessible_user_sdwt_prods",
    "user_can_access_email",
    "user_can_view_unassigned",
]
