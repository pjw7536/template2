# =============================================================================
# 모듈 설명: AppStore 작성자/관리자 권한 helper를 제공합니다.
# - 주요 함수: can_manage_app, can_manage_comment
# - 불변 조건: AppStore admin 또는 작성자만 수정/삭제할 수 있습니다.
# =============================================================================
from __future__ import annotations

from typing import Any

from api.account import services as account_services


APPSTORE_SCOPE = "appstore"


def is_authenticated_user(user: Any) -> bool:
    """인증된 사용자 객체인지 확인합니다."""

    return bool(user and getattr(user, "is_authenticated", False))


def has_appstore_editor_permission(user: Any, *, request: Any | None = None) -> bool:
    """AppStore admin 역할 보유 여부를 반환합니다."""

    return account_services.has_scope_role(
        user=user,
        scope_key=APPSTORE_SCOPE,
        request=request,
    )


def is_app_owner(user: Any, app: Any) -> bool:
    """사용자가 앱 작성자인지 확인합니다."""

    user_id = getattr(user, "pk", None)
    return user_id is not None and getattr(app, "owner_id", None) == user_id


def is_comment_author(user: Any, comment: Any) -> bool:
    """사용자가 댓글 작성자인지 확인합니다."""

    user_id = getattr(user, "pk", None)
    return user_id is not None and getattr(comment, "user_id", None) == user_id


def can_manage_app(
    user: Any,
    app: Any,
    *,
    is_appstore_admin: bool,
) -> bool:
    """미리 계산한 관리자 여부와 작성자 관계만으로 앱 관리 권한을 검사합니다."""

    if not is_authenticated_user(user):
        return False
    return bool(is_appstore_admin) or is_app_owner(user, app)


def can_manage_comment(
    user: Any,
    comment: Any,
    *,
    is_appstore_admin: bool,
) -> bool:
    """미리 계산한 관리자 여부와 작성자 관계만으로 댓글 관리 권한을 검사합니다."""

    if not is_authenticated_user(user):
        return False
    return bool(is_appstore_admin) or is_comment_author(user, comment)


__all__ = [
    "can_manage_app",
    "can_manage_comment",
    "has_appstore_editor_permission",
    "is_app_owner",
    "is_authenticated_user",
    "is_comment_author",
]
