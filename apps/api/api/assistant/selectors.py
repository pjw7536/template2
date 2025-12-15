from __future__ import annotations

from typing import Any

from api.account.selectors import get_accessible_user_sdwt_prods_for_user as _get_accessible_user_sdwt_prods_for_user


def get_accessible_user_sdwt_prods_for_user(*, user: Any) -> set[str]:
    """사용자가 조회 가능한 user_sdwt_prod 목록을 반환합니다.

    This is used by the assistant feature to validate/drive RAG index selection.

    Args:
        user: Django user instance (may be anonymous / unauthenticated).

    Returns:
        Set of non-empty user_sdwt_prod strings the user can access.

    Side effects:
        None. Read-only query.
    """

    return _get_accessible_user_sdwt_prods_for_user(user)

