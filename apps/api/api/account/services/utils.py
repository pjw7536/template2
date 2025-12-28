from __future__ import annotations

from typing import Any

from .. import selectors


def _is_privileged_user(user: Any) -> bool:
    """superuser/staff 여부를 반환합니다."""

    return bool(getattr(user, "is_superuser", False) or getattr(user, "is_staff", False))


def _user_can_manage_user_sdwt_prod(*, user: Any, user_sdwt_prod: str) -> bool:
    """사용자가 user_sdwt_prod 그룹을 관리할 권한이 있는지 반환합니다."""

    if _is_privileged_user(user):
        return True
    return selectors.user_has_manage_permission(user=user, user_sdwt_prod=user_sdwt_prod)
