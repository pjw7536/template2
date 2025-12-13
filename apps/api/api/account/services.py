from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from django.db import transaction
from django.utils import timezone

from .models import UserProfile, UserSdwtProdAccess, UserSdwtProdChange
from . import selectors

logger = logging.getLogger(__name__)


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


def get_affiliation_overview(*, user: Any, timezone_name: str) -> dict[str, object]:
    """AccountAffiliationView(GET) 응답 payload를 구성합니다.

    Build the AccountAffiliationView GET response payload.

    Side effects:
        Ensures the user's self access row exists.
    """

    access_list = _current_access_list(user)
    manageable = [entry["userSdwtProd"] for entry in access_list if entry["canManage"]]
    options = selectors.list_affiliation_options()

    return {
        "currentUserSdwtProd": getattr(user, "user_sdwt_prod", None),
        "currentDepartment": getattr(user, "department", None),
        "currentLine": getattr(user, "line", None),
        "timezone": timezone_name,
        "accessibleUserSdwtProds": access_list,
        "manageableUserSdwtProds": manageable,
        "affiliationOptions": options,
    }


def request_affiliation_change(
    *,
    user: Any,
    option: Any,
    to_user_sdwt_prod: str,
    effective_from: datetime,
    timezone_name: str,
) -> Tuple[dict[str, object], int]:
    """user_sdwt_prod 소속 변경을 요청하거나(일반) 즉시 적용(관리자)합니다.

    Request (or immediately apply) a user_sdwt_prod affiliation change.

    Returns:
        (payload, http_status)

    Side effects:
        - Writes UserSdwtProdChange and user fields.
        - May delete old UserSdwtProdAccess rows.
        - For staff users, triggers email reclassification (best-effort).
    """

    ensure_self_access(user, as_manager=False)

    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        previous_user_sdwt = getattr(user, "user_sdwt_prod", None)

        with transaction.atomic():
            UserSdwtProdChange.objects.create(
                user=user,
                department=getattr(option, "department", None),
                line=getattr(option, "line", None),
                from_user_sdwt_prod=previous_user_sdwt,
                to_user_sdwt_prod=to_user_sdwt_prod,
                effective_from=effective_from,
                applied=True,
                approved=True,
                approved_by=user,
                approved_at=timezone.now(),
                created_by=user,
            )

            user.user_sdwt_prod = to_user_sdwt_prod
            user.department = getattr(option, "department", None)
            user.line = getattr(option, "line", None)
            user.save(update_fields=["user_sdwt_prod", "department", "line"])

            ensure_self_access(user, as_manager=True)

            if (
                isinstance(previous_user_sdwt, str)
                and previous_user_sdwt
                and previous_user_sdwt != to_user_sdwt_prod
            ):
                UserSdwtProdAccess.objects.filter(
                    user=user,
                    user_sdwt_prod=previous_user_sdwt,
                ).delete()

        try:
            from api.emails.services import reclassify_emails_for_user_sdwt_change

            reclassify_emails_for_user_sdwt_change(user, effective_from)
        except Exception:
            logger.exception("Failed to reclassify emails for user %s", getattr(user, "username", ""))

        return get_affiliation_overview(user=user, timezone_name=timezone_name), 200

    change = UserSdwtProdChange.objects.create(
        user=user,
        department=getattr(option, "department", None),
        line=getattr(option, "line", None),
        from_user_sdwt_prod=getattr(user, "user_sdwt_prod", None),
        to_user_sdwt_prod=to_user_sdwt_prod,
        effective_from=effective_from,
        applied=False,
        approved=False,
        created_by=user,
    )

    return (
        {
            "status": "pending",
            "changeId": change.id,
            "requestedUserSdwtProd": to_user_sdwt_prod,
            "effectiveFrom": change.effective_from.isoformat(),
        },
        202,
    )


def approve_affiliation_change(
    *,
    approver: Any,
    change_id: int,
) -> Tuple[dict[str, object], int]:
    """대기 중인 UserSdwtProdChange를 승인하고 실제 사용자 정보에 반영합니다.

    Approve a pending UserSdwtProdChange and apply it.

    Returns:
        (payload, http_status)

    Side effects:
        - Updates the target user's affiliation fields.
        - Updates UserSdwtProdChange flags.
        - Ensures self-access row exists for the new user_sdwt_prod.
        - Best-effort email reclassification.
    """

    change = selectors.get_user_sdwt_prod_change_by_id(change_id=change_id)
    if change is None:
        return {"error": "Change not found"}, 404

    if change.approved or change.applied:
        return {"error": "already applied"}, 400

    target_user = change.user
    previous_user_sdwt = getattr(target_user, "user_sdwt_prod", None)

    with transaction.atomic():
        target_user.user_sdwt_prod = change.to_user_sdwt_prod
        target_user.department = change.department
        target_user.line = change.line
        target_user.save(update_fields=["user_sdwt_prod", "department", "line"])

        change.approved = True
        change.approved_by = approver
        change.approved_at = timezone.now()
        change.applied = True
        change.save(update_fields=["approved", "approved_by", "approved_at", "applied"])

        ensure_self_access(target_user, as_manager=False)

        if (
            isinstance(previous_user_sdwt, str)
            and previous_user_sdwt
            and previous_user_sdwt != change.to_user_sdwt_prod
        ):
            UserSdwtProdAccess.objects.filter(
                user=target_user,
                user_sdwt_prod=previous_user_sdwt,
            ).delete()

    try:
        from api.emails.services import reclassify_emails_for_user_sdwt_change

        reclassify_emails_for_user_sdwt_change(target_user, change.effective_from)
    except Exception:
        logger.exception(
            "Failed to reclassify emails for user %s",
            getattr(target_user, "username", ""),
        )

    return (
        {
            "status": "approved",
            "changeId": change.id,
            "userId": target_user.id,
            "userSdwtProd": target_user.user_sdwt_prod,
            "effectiveFrom": change.effective_from.isoformat(),
        },
        200,
    )


def grant_or_revoke_access(
    *,
    grantor: Any,
    target_group: str,
    target_user: Any,
    action: str,
    can_manage: bool,
) -> Tuple[dict[str, object], int]:
    """사용자의 user_sdwt_prod 그룹 접근 권한을 부여/회수합니다.

    Grant or revoke a user's access to a user_sdwt_prod group.

    Side effects:
        Creates/updates/deletes UserSdwtProdAccess rows.
    """

    ensure_self_access(grantor, as_manager=False)

    if not (getattr(grantor, "is_superuser", False) or getattr(grantor, "is_staff", False)):
        if not selectors.user_has_manage_permission(user=grantor, user_sdwt_prod=target_group):
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

    Side effects:
        Ensures the user's self access row exists.
    """

    ensure_self_access(user, as_manager=False)

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


def get_line_sdwt_options_payload(*, pairs: list[dict[str, str]]) -> dict[str, object]:
    """(line_id, user_sdwt_prod) 목록으로 LineSdwtOptionsView 응답 payload를 구성합니다.

    Build LineSdwtOptionsView response payload from (line_id, user_sdwt_prod) rows.
    """

    grouped: Dict[str, List[str]] = {}
    for row in pairs:
        line_id = row["line_id"]
        user_sdwt_prod = row["user_sdwt_prod"]
        grouped.setdefault(line_id, []).append(user_sdwt_prod)

    lines = [
        {
            "lineId": line_id,
            "userSdwtProds": sorted(list(set(user_sdwt_list))),
        }
        for line_id, user_sdwt_list in grouped.items()
    ]
    all_user_sdwt = sorted(
        {usdwt for user_sdwt_list in grouped.values() for usdwt in user_sdwt_list}
    )

    return {"lines": lines, "userSdwtProds": all_user_sdwt}


def resolve_target_user(
    *,
    target_id: object,
    target_username: object,
) -> Any | None:
    """id 또는 username으로 대상 사용자를 조회합니다(최대한 best-effort).

    Resolve target user by id or username (best-effort).
    """

    target: Any | None = None

    if target_id not in (None, ""):
        try:
            target = selectors.get_user_by_id(user_id=int(target_id))
        except (TypeError, ValueError):
            target = None

    if target is None and isinstance(target_username, str) and target_username.strip():
        target = selectors.get_user_by_username(username=target_username.strip())

    return target


def _serialize_access(access: UserSdwtProdAccess, source: str) -> Dict[str, object]:
    """UserSdwtProdAccess 행을 API 응답용 dict로 직렬화합니다."""

    return {
        "userSdwtProd": access.user_sdwt_prod,
        "canManage": access.can_manage,
        "source": source,
        "grantedBy": access.granted_by_id,
        "grantedAt": access.created_at.isoformat(),
    }


def _serialize_member(access: UserSdwtProdAccess) -> Dict[str, object]:
    """그룹 멤버(access + user)를 API 응답용 dict로 직렬화합니다."""

    user = access.user
    return {
        "userId": user.id,
        "username": user.get_username(),
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

    base_access = ensure_self_access(user, as_manager=False)
    if base_access:
        access_map.setdefault(base_access.user_sdwt_prod, base_access)

    current_user_sdwt = getattr(user, "user_sdwt_prod", None)
    result: List[Dict[str, object]] = []
    for prod, entry in sorted(access_map.items()):
        source = "self" if prod == current_user_sdwt else "grant"
        result.append(_serialize_access(entry, source))
    return result
