from __future__ import annotations

from typing import Any, Optional, Set

from django.http import HttpRequest

from api.common.affiliations import UNASSIGNED_USER_SDWT_PROD

from .selectors import get_accessible_user_sdwt_prods_for_user


def user_can_view_unassigned(user: Any) -> bool:
    """UNASSIGNED(미분류) 메일함 조회 가능 여부를 반환합니다."""

    return bool(
        user
        and (getattr(user, "is_superuser", False) or getattr(user, "is_staff", False))
    )


def email_is_unassigned(email: Any) -> bool:
    """Email 인스턴스가 UNASSIGNED(미분류) 메일인지 판별합니다."""

    raw = getattr(email, "user_sdwt_prod", None)
    if raw is None:
        return True
    if not isinstance(raw, str):
        return False
    normalized = raw.strip()
    return normalized in {"", UNASSIGNED_USER_SDWT_PROD, "rp-unclassified"}


def resolve_accessible_user_sdwt_prods(user: Any) -> Set[str]:
    """사용자가 접근 가능한 user_sdwt_prod 목록(집합)을 조회합니다."""

    return get_accessible_user_sdwt_prods_for_user(user)


def _resolve_sender_id_from_user(user: Any) -> str | None:
    """사용자에서 sender_id(knox_id)를 추출합니다."""

    knox_id = getattr(user, "knox_id", None)
    if isinstance(knox_id, str) and knox_id.strip():
        return knox_id.strip()
    return None


def user_can_access_email(
    user: Any,
    email: Any,
    accessible: Optional[Set[str]],
) -> bool:
    """일반 사용자 기준으로 특정 이메일 접근 권한을 검사합니다."""

    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return True
    if accessible is None:
        return False
    sender_id = _resolve_sender_id_from_user(user)
    if sender_id and getattr(email, "sender_id", None) == sender_id:
        return True
    return bool(getattr(email, "user_sdwt_prod", None) and email.user_sdwt_prod in accessible)


def resolve_access_control(request: HttpRequest) -> tuple[bool, bool, Set[str]]:
    """
    공통 권한 처리: 인증 여부, 접근 가능한 user_sdwt_prod 목록 반환.
    superuser/staff는 무제한 접근을 허용한다.
    """

    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return False, False, set()

    if not _resolve_sender_id_from_user(user):
        return True, False, set()

    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return True, True, set()

    accessible = resolve_accessible_user_sdwt_prods(user)
    return True, False, accessible


def extract_bearer_token(request: HttpRequest) -> str:
    """Authorization 헤더에서 Bearer 토큰을 추출."""

    auth_header = request.headers.get("Authorization") or request.META.get("HTTP_AUTHORIZATION") or ""
    if not isinstance(auth_header, str):
        return ""

    normalized = auth_header.strip()
    if normalized.lower().startswith("bearer "):
        return normalized[7:].strip()
    return normalized


__all__ = [
    "email_is_unassigned",
    "extract_bearer_token",
    "resolve_access_control",
    "resolve_accessible_user_sdwt_prods",
    "user_can_access_email",
    "user_can_view_unassigned",
]
