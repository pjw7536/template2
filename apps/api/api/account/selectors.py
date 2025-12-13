from __future__ import annotations

from datetime import datetime
from typing import Any

from django.contrib.auth import get_user_model
from django.db.models import QuerySet
from django.utils import timezone

from api.common.affiliations import UNKNOWN, UNCLASSIFIED_USER_SDWT_PROD

from .models import (
    AffiliationHierarchy,
    LineSDWT,
    UserSdwtProdAccess,
    UserSdwtProdChange,
)


def get_accessible_user_sdwt_prods_for_user(user: Any) -> set[str]:
    """사용자가 접근 가능한 user_sdwt_prod 값 집합을 조회합니다.

    Return user_sdwt_prod values the user is allowed to access.

    Args:
        user: Django user instance (may be anonymous / unauthenticated).

    Returns:
        Set of non-empty user_sdwt_prod strings the user can access.

    Side effects:
        None. Read-only query.
    """

    if not user or not getattr(user, "is_authenticated", False):
        return set()

    values = set(
        UserSdwtProdAccess.objects.filter(user=user).values_list("user_sdwt_prod", flat=True)
    )

    user_sdwt_prod = getattr(user, "user_sdwt_prod", None)
    if isinstance(user_sdwt_prod, str) and user_sdwt_prod.strip():
        values.add(user_sdwt_prod)

    return {val for val in values if isinstance(val, str) and val.strip()}


def list_affiliation_options() -> list[dict[str, str]]:
    """소속 선택 옵션(부서/라인/user_sdwt_prod) 전체를 조회합니다.

    Return all affiliation options.

    Returns:
        List of dicts with keys: department, line, user_sdwt_prod.

    Side effects:
        None. Read-only query.
    """

    return list(
        AffiliationHierarchy.objects.all()
        .order_by("department", "line", "user_sdwt_prod")
        .values("department", "line", "user_sdwt_prod")
    )


def list_user_sdwt_prod_access_rows(*, user: Any) -> list[UserSdwtProdAccess]:
    """사용자에 대한 접근 권한(UserSdwtProdAccess) 행 목록을 조회합니다.

    Return access rows for the given user.

    Side effects:
        None. Read-only query.
    """

    return list(
        UserSdwtProdAccess.objects.filter(user=user).order_by("user_sdwt_prod", "id")
    )


def user_has_manage_permission(*, user: Any, user_sdwt_prod: str) -> bool:
    """사용자가 특정 user_sdwt_prod 그룹을 관리할 권한이 있는지 확인합니다.

    Return whether user can manage the given user_sdwt_prod.
    """

    return UserSdwtProdAccess.objects.filter(
        user=user,
        user_sdwt_prod=user_sdwt_prod,
        can_manage=True,
    ).exists()


def get_user_by_id(*, user_id: int) -> Any | None:
    """id로 사용자를 조회하고 없으면 None을 반환합니다.

    Return a user by id, or None if missing.
    """

    UserModel = get_user_model()
    try:
        return UserModel.objects.get(id=user_id)
    except UserModel.DoesNotExist:
        return None


def get_user_by_username(*, username: str) -> Any | None:
    """로그인 식별자(sabun/username)로 사용자를 조회하고 없으면 None을 반환합니다.

    Return a user by login identifier (sabun), or None if missing.
    """

    UserModel = get_user_model()
    try:
        if hasattr(UserModel, "sabun"):
            return UserModel.objects.get(sabun=username)
        return UserModel.objects.get(username=username)
    except UserModel.DoesNotExist:
        return None


def get_user_sdwt_prod_change_by_id(*, change_id: int) -> UserSdwtProdChange | None:
    """id로 UserSdwtProdChange를 조회하고 없으면 None을 반환합니다.

    Return a UserSdwtProdChange by id, or None if missing.
    """

    try:
        return UserSdwtProdChange.objects.select_related("user").get(id=change_id)
    except UserSdwtProdChange.DoesNotExist:
        return None


def get_access_row_for_user_and_prod(
    *,
    user: Any,
    user_sdwt_prod: str,
) -> UserSdwtProdAccess | None:
    """(user, user_sdwt_prod)에 대한 접근 권한 행을 조회하고 없으면 None을 반환합니다.

    Return the access row for (user, user_sdwt_prod), or None.
    """

    return (
        UserSdwtProdAccess.objects.filter(user=user, user_sdwt_prod=user_sdwt_prod)
        .select_related("user")
        .first()
    )


def other_manager_exists(
    *,
    user_sdwt_prod: str,
    exclude_user: Any,
) -> bool:
    """그룹에 현재 사용자 외 다른 관리자(can_manage)가 존재하는지 확인합니다.

    Return whether there is any other manager for the group.
    """

    return (
        UserSdwtProdAccess.objects.filter(user_sdwt_prod=user_sdwt_prod, can_manage=True)
        .exclude(user=exclude_user)
        .exists()
    )


def list_manageable_user_sdwt_prod_values(*, user: Any) -> set[str]:
    """사용자가 관리(can_manage)할 수 있는 user_sdwt_prod 값 집합을 조회합니다.

    Return user_sdwt_prod values the user can manage (can_manage=True).
    """

    values = set(
        UserSdwtProdAccess.objects.filter(user=user, can_manage=True).values_list(
            "user_sdwt_prod",
            flat=True,
        )
    )
    return {val for val in values if isinstance(val, str) and val.strip()}


def list_group_members(*, user_sdwt_prods: set[str]) -> QuerySet[UserSdwtProdAccess]:
    """지정한 user_sdwt_prods 그룹들에 속한 멤버 접근 권한 행을 조회합니다.

    Return access rows for members in the given user_sdwt_prods.
    """

    return (
        UserSdwtProdAccess.objects.filter(user_sdwt_prod__in=user_sdwt_prods)
        .select_related("user")
        .order_by("user_sdwt_prod", "user_id")
    )


def list_line_sdwt_pairs() -> list[dict[str, str]]:
    """선택 가능한 (line_id, user_sdwt_prod) 쌍 목록을 조회합니다.

    Return all available (line_id, user_sdwt_prod) pairs for selection.
    """

    return list(
        LineSDWT.objects.filter(line_id__isnull=False, line_id__gt="")
        .exclude(user_sdwt_prod__isnull=True)
        .exclude(user_sdwt_prod__exact="")
        .order_by("line_id", "user_sdwt_prod")
        .values("line_id", "user_sdwt_prod")
    )


def get_next_user_sdwt_prod_change(
    *,
    user: Any,
    effective_from: datetime,
) -> UserSdwtProdChange | None:
    """effective_from 이후 예정된 다음 소속 변경(UserSdwtProdChange)을 조회합니다.

    Return the next UserSdwtProdChange after effective_from for the given user.

    Side effects:
        None. Read-only query.
    """

    if effective_from is None:
        effective_from = timezone.now()
    if timezone.is_naive(effective_from):
        effective_from = timezone.make_aware(effective_from, timezone.utc)

    return (
        UserSdwtProdChange.objects.filter(user=user, effective_from__gt=effective_from)
        .order_by("effective_from", "id")
        .first()
    )


def resolve_user_affiliation(user: Any, at_time: datetime | None) -> dict[str, str]:
    """지정 시점의 사용자 소속(부서/라인/user_sdwt_prod) 스냅샷을 계산합니다.

    Resolve a user's affiliation snapshot at a given time.

    Side effects:
        None. Read-only query.
    """

    if at_time is None:
        at_time = timezone.now()
    if timezone.is_naive(at_time):
        at_time = timezone.make_aware(at_time, timezone.utc)

    change = (
        UserSdwtProdChange.objects.filter(user=user, effective_from__lte=at_time)
        .order_by("-effective_from", "-id")
        .first()
    )

    if change:
        return {
            "department": change.department or getattr(user, "department", None) or UNKNOWN,
            "line": change.line or getattr(user, "line", None) or "",
            "user_sdwt_prod": change.to_user_sdwt_prod
            or getattr(user, "user_sdwt_prod", None)
            or UNCLASSIFIED_USER_SDWT_PROD,
        }

    return {
        "department": getattr(user, "department", None) or UNKNOWN,
        "line": getattr(user, "line", None) or "",
        "user_sdwt_prod": getattr(user, "user_sdwt_prod", None) or UNCLASSIFIED_USER_SDWT_PROD,
    }


def get_affiliation_option(
    department: str,
    line: str,
    user_sdwt_prod: str,
) -> AffiliationHierarchy | None:
    """부서/라인/user_sdwt_prod 조합에 해당하는 소속 옵션 행을 조회합니다.

    Return a single affiliation option row, or None when missing.
    """

    if not department or not line or not user_sdwt_prod:
        return None

    try:
        return AffiliationHierarchy.objects.get(
            department=department.strip(),
            line=line.strip(),
            user_sdwt_prod=user_sdwt_prod.strip(),
        )
    except AffiliationHierarchy.DoesNotExist:
        return None
