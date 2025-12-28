from __future__ import annotations

from typing import Any, Dict, List

from ..models import UserSdwtProdAccess
from .. import selectors
from .utils import _user_can_manage_user_sdwt_prod


def ensure_self_access(user: Any, *, as_manager: bool = False) -> UserSdwtProdAccess | None:
    """사용자 본인의 user_sdwt_prod 접근 권한 행을 보장(생성/업데이트)합니다.

    Ensure the user has an access row for their own user_sdwt_prod.

    Args:
        user: Authenticated Django user.
        as_manager: When True, grants can_manage=True for the self row.

    Returns:
        The access row when user.user_sdwt_prod is set, otherwise None.

    Side effects:
        Creates/updates UserSdwtProdAccess rows.
    """

    user_sdwt_prod = getattr(user, "user_sdwt_prod", None)
    if not isinstance(user_sdwt_prod, str) or not user_sdwt_prod.strip():
        return None

    access, created = UserSdwtProdAccess.objects.get_or_create(
        user=user,
        user_sdwt_prod=user_sdwt_prod,
        defaults={"can_manage": as_manager, "granted_by": None},
    )
    if not created and as_manager and not access.can_manage:
        access.can_manage = True
        access.save(update_fields=["can_manage"])
    return access


def grant_or_revoke_access(
    *,
    grantor: Any,
    target_group: str,
    target_user: Any,
    action: str,
    can_manage: bool,
) -> tuple[dict[str, object], int]:
    """사용자의 user_sdwt_prod 그룹 접근 권한을 부여/회수합니다.

    Grant or revoke a user's access to a user_sdwt_prod group.

    Side effects:
        Creates/updates/deletes UserSdwtProdAccess rows.
    """

    ensure_self_access(grantor, as_manager=False)

    if not _user_can_manage_user_sdwt_prod(user=grantor, user_sdwt_prod=target_group):
        return {"error": "forbidden"}, 403

    normalized_action = (action or "grant").lower()
    if normalized_action == "revoke":
        access = selectors.get_access_row_for_user_and_prod(
            user=target_user,
            user_sdwt_prod=target_group,
        )
        if not access:
            return {"status": "ok", "deleted": 0}, 200

        if access.can_manage:
            if not selectors.other_manager_exists(
                user_sdwt_prod=target_group,
                exclude_user=target_user,
            ):
                return {"error": "Cannot remove the last manager for this group"}, 400

        access.delete()
        return {"status": "ok", "deleted": 1}, 200

    access, created = UserSdwtProdAccess.objects.get_or_create(
        user=target_user,
        user_sdwt_prod=target_group,
        defaults={"can_manage": can_manage, "granted_by": grantor},
    )
    if not created and (access.can_manage != can_manage or access.granted_by_id != grantor.id):
        access.can_manage = can_manage
        access.granted_by = grantor
        access.save(update_fields=["can_manage", "granted_by"])

    return _serialize_member(access), 200


def get_manageable_groups_with_members(*, user: Any) -> dict[str, object]:
    """사용자가 관리 가능한 user_sdwt_prod 그룹과 멤버 목록을 반환합니다.

    Return manageable user_sdwt_prod groups and member lists.
    """

    manageable_set = selectors.list_manageable_user_sdwt_prod_values(user=user)
    user_sdwt_prod = getattr(user, "user_sdwt_prod", None)
    if isinstance(user_sdwt_prod, str) and user_sdwt_prod.strip():
        manageable_set.add(user_sdwt_prod)

    groups: List[Dict[str, object]] = []
    if not manageable_set:
        return {"groups": groups}

    members_by_group: Dict[str, List[Dict[str, object]]] = {prod: [] for prod in manageable_set}
    for access in selectors.list_group_members(user_sdwt_prods=manageable_set):
        members_by_group.setdefault(access.user_sdwt_prod, []).append(_serialize_member(access))

    for prod in sorted(manageable_set):
        groups.append({"userSdwtProd": prod, "members": members_by_group.get(prod, [])})

    return {"groups": groups}


def _serialize_access(access: UserSdwtProdAccess, source: str) -> Dict[str, object]:
    """UserSdwtProdAccess 행을 API 응답용 dict로 직렬화합니다."""

    return {
        "userSdwtProd": access.user_sdwt_prod,
        "canManage": access.can_manage,
        "source": source,
        "grantedBy": access.granted_by_id,
        "grantedAt": access.created_at.isoformat(),
    }


def _serialize_access_fallback(*, user_sdwt_prod: str, source: str) -> Dict[str, object]:
    """DB row가 없는 경우를 위한 access 응답 기본값."""

    return {
        "userSdwtProd": user_sdwt_prod,
        "canManage": False,
        "source": source,
        "grantedBy": None,
        "grantedAt": None,
    }


def _serialize_member(access: UserSdwtProdAccess) -> Dict[str, object]:
    """그룹 멤버(access + user)를 API 응답용 dict로 직렬화합니다."""

    user = access.user
    return {
        "userId": user.id,
        "username": user.username,
        "name": (user.first_name or "") + (user.last_name or ""),
        "userSdwtProd": access.user_sdwt_prod,
        "canManage": access.can_manage,
        "grantedBy": access.granted_by_id,
        "grantedAt": access.created_at.isoformat(),
    }


def _current_access_list(user: Any) -> List[Dict[str, object]]:
    """현재 사용자 기준 접근 가능한 그룹 목록을 응답 형식으로 구성합니다."""

    rows = selectors.list_user_sdwt_prod_access_rows(user=user)
    access_map = {row.user_sdwt_prod: row for row in rows}

    current_user_sdwt = getattr(user, "user_sdwt_prod", None)
    if isinstance(current_user_sdwt, str) and current_user_sdwt.strip():
        access_map.setdefault(current_user_sdwt, None)

    result: List[Dict[str, object]] = []
    for prod, entry in sorted(access_map.items()):
        source = "self" if prod == current_user_sdwt else "grant"
        if entry is None:
            result.append(_serialize_access_fallback(user_sdwt_prod=prod, source=source))
        else:
            result.append(_serialize_access(entry, source))
    return result
