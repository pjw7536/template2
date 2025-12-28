from __future__ import annotations

from typing import Any

from ..models import UserProfile
from .. import selectors


def ensure_user_profile(user: Any) -> UserProfile:
    """사용자 프로필(UserProfile)이 없으면 생성하고 반환합니다.

    Ensure the user has a profile row.

    Side effects:
        Creates a UserProfile row when missing.
    """

    if user is None:
        raise ValueError("user is required to ensure a profile exists")
    profile, _created = UserProfile.objects.get_or_create(user=user)
    return profile


def resolve_target_user(
    *,
    target_id: object,
    target_knox_id: object,
) -> Any | None:
    """id 또는 knox_id로 대상 사용자를 조회합니다(최대한 best-effort).

    Resolve target user by id or knox_id (best-effort).
    """

    target: Any | None = None

    if target_id not in (None, ""):
        try:
            target = selectors.get_user_by_id(user_id=int(target_id))
        except (TypeError, ValueError):
            target = None

    if target is None and isinstance(target_knox_id, str) and target_knox_id.strip():
        target = selectors.get_user_by_knox_id(knox_id=target_knox_id.strip())

    return target
