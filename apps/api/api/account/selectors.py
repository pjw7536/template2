from __future__ import annotations

from datetime import datetime
from typing import Any

from django.contrib.auth import get_user_model
from django.db.models import Q, QuerySet
from django.utils import timezone

from api.common.affiliations import UNKNOWN, UNCLASSIFIED_USER_SDWT_PROD

from .models import (
    Affiliation,
    ExternalAffiliationSnapshot,
    UserProfile,
    UserSdwtProdAccess,
    UserSdwtProdChange,
)


def get_accessible_user_sdwt_prods_for_user(user: Any) -> set[str]:
    """사용자가 접근 가능한 user_sdwt_prod 값 집합을 조회합니다.

    Return user_sdwt_prod values the user is allowed to access.

    Notes:
        - Regular users: include their own `user_sdwt_prod` plus explicit grants from `UserSdwtProdAccess`.
        - If no current user_sdwt_prod is set, include the pending change target for first-time onboarding.
        - Superusers: return all known `user_sdwt_prod` values across the system (used for global browsing).

    Args:
        user: Django user instance (may be anonymous / unauthenticated).

    Returns:
        Set of non-empty user_sdwt_prod strings the user can access.

    Side effects:
        None. Read-only query.
    """

    if not user or not getattr(user, "is_authenticated", False):
        return set()

    if getattr(user, "is_superuser", False):
        UserModel = get_user_model()
        values = set(list_distinct_user_sdwt_prod_values())
        values.update(
            UserModel.objects.exclude(user_sdwt_prod__isnull=True)
            .exclude(user_sdwt_prod="")
            .values_list("user_sdwt_prod", flat=True)
            .distinct()
        )
        return {val.strip() for val in values if isinstance(val, str) and val.strip()}

    values = set(
        UserSdwtProdAccess.objects.filter(user=user).values_list("user_sdwt_prod", flat=True)
    )

    user_sdwt_prod = getattr(user, "user_sdwt_prod", None)
    if isinstance(user_sdwt_prod, str) and user_sdwt_prod.strip():
        values.add(user_sdwt_prod)
    else:
        pending_change = get_pending_user_sdwt_prod_change(user=user)
        pending_user_sdwt_prod = getattr(pending_change, "to_user_sdwt_prod", None)
        if isinstance(pending_user_sdwt_prod, str) and pending_user_sdwt_prod.strip():
            values.add(pending_user_sdwt_prod.strip())

    return {val for val in values if isinstance(val, str) and val.strip()}


def list_distinct_user_sdwt_prod_values() -> set[str]:
    """시스템에서 '알려진' user_sdwt_prod 값 집합을 조회합니다.

    Return known user_sdwt_prod values across the system.

    Sources:
        - Affiliation.user_sdwt_prod
        - UserSdwtProdAccess.user_sdwt_prod

    Returns:
        Set of non-empty user_sdwt_prod strings.

    Side effects:
        None. Read-only query.
    """

    affiliation_values = set(
        Affiliation.objects.exclude(user_sdwt_prod="")
        .values_list("user_sdwt_prod", flat=True)
        .distinct()
    )
    access_values = set(
        UserSdwtProdAccess.objects.exclude(user_sdwt_prod="")
        .values_list("user_sdwt_prod", flat=True)
        .distinct()
    )

    combined = affiliation_values | access_values
    return {val.strip() for val in combined if isinstance(val, str) and val.strip()}


def list_affiliation_options() -> list[dict[str, str]]:
    """소속 선택 옵션(부서/라인/user_sdwt_prod) 전체를 조회합니다.

    Return all affiliation options.

    Returns:
        List of dicts with keys: department, line, user_sdwt_prod.

    Side effects:
        None. Read-only query.
    """

    return list(
        Affiliation.objects.all()
        .order_by("department", "line", "user_sdwt_prod")
        .values("department", "line", "user_sdwt_prod")
    )


def affiliation_exists_for_line(*, line_id: str) -> bool:
    """line_id에 대응하는 Affiliation이 존재하는지 확인합니다.

    Side effects:
        None. Read-only query.
    """

    if not isinstance(line_id, str) or not line_id.strip():
        return False
    return Affiliation.objects.filter(line=line_id.strip()).exists()


def get_affiliation_jira_key_for_line(*, line_id: str) -> str | None:
    """line_id에 해당하는 Jira project key를 조회합니다.

    여러 Affiliation이 같은 line_id를 공유할 수 있으므로, 비어있지 않은 key 중 하나를 반환합니다.

    Side effects:
        None. Read-only query.
    """

    if not isinstance(line_id, str) or not line_id.strip():
        return None

    key = (
        Affiliation.objects.filter(line=line_id.strip())
        .exclude(jira_key__isnull=True)
        .exclude(jira_key="")
        .values_list("jira_key", flat=True)
        .order_by("jira_key")
        .first()
    )
    if isinstance(key, str) and key.strip():
        return key.strip()
    return None


def get_affiliation_jira_key(*, line_id: str, user_sdwt_prod: str) -> str | None:
    """line_id + user_sdwt_prod 조합의 Jira project key를 조회합니다.

    Side effects:
        None. Read-only query.
    """

    if not isinstance(line_id, str) or not line_id.strip():
        return None
    if not isinstance(user_sdwt_prod, str) or not user_sdwt_prod.strip():
        return None

    key = (
        Affiliation.objects.filter(line=line_id.strip(), user_sdwt_prod=user_sdwt_prod.strip())
        .values_list("jira_key", flat=True)
        .first()
    )
    if isinstance(key, str) and key.strip():
        return key.strip()
    return None


def list_affiliation_jira_keys_by_line_and_sdwt(
    *,
    line_ids: set[str] | list[str],
    user_sdwt_prod_values: set[str] | list[str],
) -> dict[tuple[str, str], str | None]:
    """line_id + user_sdwt_prod 조합별 Jira project key 맵을 조회합니다.

    Returns:
        {(line_id, user_sdwt_prod): jira_key_or_none}

    Side effects:
        None. Read-only query.
    """

    normalized_lines = [line.strip() for line in line_ids if isinstance(line, str) and line.strip()]
    normalized_sdwt = [
        value.strip() for value in user_sdwt_prod_values if isinstance(value, str) and value.strip()
    ]
    if not normalized_lines or not normalized_sdwt:
        return {}

    rows = (
        Affiliation.objects.filter(line__in=normalized_lines, user_sdwt_prod__in=normalized_sdwt)
        .values("line", "user_sdwt_prod", "jira_key")
    )
    mapping: dict[tuple[str, str], str | None] = {}
    for row in rows:
        line_id = row.get("line")
        sdwt = row.get("user_sdwt_prod")
        if not isinstance(line_id, str) or not line_id.strip():
            continue
        if not isinstance(sdwt, str) or not sdwt.strip():
            continue
        key = row.get("jira_key")
        normalized_key = key.strip() if isinstance(key, str) and key.strip() else None
        mapping[(line_id.strip(), sdwt.strip())] = normalized_key

    return mapping


def list_user_sdwt_prod_access_rows(*, user: Any) -> list[UserSdwtProdAccess]:
    """사용자에 대한 접근 권한(UserSdwtProdAccess) 행 목록을 조회합니다.

    Return access rows for the given user.

    Side effects:
        None. Read-only query.
    """

    return list(
        UserSdwtProdAccess.objects.filter(user=user).order_by("user_sdwt_prod", "id")
    )


def get_user_profile_role(*, user: Any) -> str:
    """사용자 프로필(role) 값을 조회합니다.

    Returns:
        역할 문자열. 프로필이 없으면 기본값("viewer")을 반환합니다.

    Side effects:
        None. Read-only query.
    """

    if not user:
        return UserProfile.Roles.VIEWER

    profile = UserProfile.objects.filter(user=user).only("role").first()
    if profile is None:
        return UserProfile.Roles.VIEWER
    return profile.role or UserProfile.Roles.VIEWER


def list_user_sdwt_prod_changes(
    *, user: Any, limit: int = 50
) -> list[UserSdwtProdChange]:
    """사용자의 user_sdwt_prod 변경 히스토리를 최신순으로 반환합니다.

    Args:
        user: Django user instance.
        limit: 최대 반환 개수.

    Returns:
        UserSdwtProdChange 리스트.

    Side effects:
        None. Read-only query.
    """

    if not user:
        return []

    normalized_limit = max(1, int(limit or 50))
    return list(
        UserSdwtProdChange.objects.filter(user=user)
        .select_related("approved_by", "created_by")
        .order_by("-effective_from", "-id")[:normalized_limit]
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


def get_user_by_knox_id(*, knox_id: str) -> Any | None:
    """knox_id로 사용자를 조회하고 없으면 None을 반환합니다.

    Return a user by knox_id, or None if missing.
    """

    if not isinstance(knox_id, str) or not knox_id.strip():
        return None

    UserModel = get_user_model()
    if not hasattr(UserModel, "knox_id"):
        return None

    return UserModel.objects.filter(knox_id=knox_id.strip()).first()


def get_user_sdwt_prod_change_by_id(*, change_id: int) -> UserSdwtProdChange | None:
    """id로 UserSdwtProdChange를 조회하고 없으면 None을 반환합니다.

    Return a UserSdwtProdChange by id, or None if missing.
    """

    try:
        return UserSdwtProdChange.objects.select_related("user").get(id=change_id)
    except UserSdwtProdChange.DoesNotExist:
        return None


def get_external_affiliation_snapshot_by_knox_id(
    *,
    knox_id: str,
) -> ExternalAffiliationSnapshot | None:
    """knox_id로 외부 예측 소속 스냅샷을 조회합니다.

    Return ExternalAffiliationSnapshot by knox_id, or None if missing.
    """

    if not isinstance(knox_id, str) or not knox_id.strip():
        return None

    return ExternalAffiliationSnapshot.objects.filter(knox_id=knox_id.strip()).first()


def get_external_affiliation_snapshots_by_knox_ids(
    *,
    knox_ids: list[str],
) -> dict[str, ExternalAffiliationSnapshot]:
    """knox_id 목록으로 외부 예측 소속 스냅샷을 조회해 dict로 반환합니다.

    Returns:
        Dict keyed by knox_id with ExternalAffiliationSnapshot values.

    Side effects:
        None. Read-only query.
    """

    normalized_ids = [value.strip() for value in knox_ids if isinstance(value, str) and value.strip()]
    if not normalized_ids:
        return {}

    snapshots = ExternalAffiliationSnapshot.objects.filter(knox_id__in=normalized_ids)
    return {snapshot.knox_id: snapshot for snapshot in snapshots}


def get_current_user_sdwt_prod_change(*, user: Any) -> UserSdwtProdChange | None:
    """현재 사용자의 user_sdwt_prod에 해당하는 승인된 변경 이력을 반환합니다.

    Return the latest approved UserSdwtProdChange matching the user's current user_sdwt_prod.

    Side effects:
        None. Read-only query.
    """

    if not user:
        return None

    current_user_sdwt_prod = getattr(user, "user_sdwt_prod", None)
    if not isinstance(current_user_sdwt_prod, str) or not current_user_sdwt_prod.strip():
        return None

    normalized = current_user_sdwt_prod.strip()
    return (
        UserSdwtProdChange.objects.filter(user=user, to_user_sdwt_prod=normalized)
        .filter(Q(status=UserSdwtProdChange.Status.APPROVED) | Q(approved=True))
        .order_by("-effective_from", "-id")
        .first()
    )


def get_pending_user_sdwt_prod_change(*, user: Any) -> UserSdwtProdChange | None:
    """현재 사용자의 PENDING 상태 user_sdwt_prod 변경 요청을 조회합니다.

    Return the latest pending UserSdwtProdChange for the given user.
    """

    if not user:
        return None

    return (
        UserSdwtProdChange.objects.filter(user=user)
        .filter(
            Q(status=UserSdwtProdChange.Status.PENDING)
            | Q(status__isnull=True, approved=False, applied=False)
        )
        .order_by("-created_at", "-id")
        .first()
    )


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


def list_affiliation_change_requests(
    *,
    manageable_user_sdwt_prods: set[str] | None,
    status: str | None,
    search: str | None,
    user_sdwt_prod: str | None,
) -> QuerySet[UserSdwtProdChange]:
    """승인 대상 소속 변경 요청 목록을 필터링하여 조회합니다.

    Args:
        manageable_user_sdwt_prods: 관리 가능한 user_sdwt_prod 집합. None이면 전체 접근.
        status: 상태 필터(PENDING/APPROVED/REJECTED). None이면 필터 미적용.
        search: 사용자 정보 검색어.
        user_sdwt_prod: to_user_sdwt_prod 필터.

    Returns:
        필터링된 UserSdwtProdChange QuerySet.

    Side effects:
        None. Read-only query.
    """

    qs = UserSdwtProdChange.objects.select_related("user", "created_by", "approved_by")

    if manageable_user_sdwt_prods is not None:
        if not manageable_user_sdwt_prods:
            return UserSdwtProdChange.objects.none()
        qs = qs.filter(to_user_sdwt_prod__in=manageable_user_sdwt_prods)

    if isinstance(status, str) and status.strip():
        normalized_status = status.strip().upper()
        if normalized_status == UserSdwtProdChange.Status.PENDING:
            qs = qs.filter(
                Q(status=UserSdwtProdChange.Status.PENDING)
                | Q(status__isnull=True, approved=False, applied=False)
            )
        elif normalized_status == UserSdwtProdChange.Status.APPROVED:
            qs = qs.filter(
                Q(status=UserSdwtProdChange.Status.APPROVED)
                | Q(approved=True)
                | Q(applied=True)
            )
        elif normalized_status == UserSdwtProdChange.Status.REJECTED:
            qs = qs.filter(status=UserSdwtProdChange.Status.REJECTED)

    if isinstance(user_sdwt_prod, str) and user_sdwt_prod.strip():
        qs = qs.filter(to_user_sdwt_prod=user_sdwt_prod.strip())

    if isinstance(search, str) and search.strip():
        keyword = search.strip()
        qs = qs.filter(
            Q(user__username__icontains=keyword)
            | Q(user__email__icontains=keyword)
            | Q(user__sabun__icontains=keyword)
            | Q(user__knox_id__icontains=keyword)
            | Q(user__givenname__icontains=keyword)
            | Q(user__surname__icontains=keyword)
        )

    return qs.order_by("-created_at", "-id")


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

    pairs = (
        Affiliation.objects.filter(line__isnull=False)
        .exclude(line__exact="")
        .exclude(user_sdwt_prod__isnull=True)
        .exclude(user_sdwt_prod__exact="")
        .values("line", "user_sdwt_prod")
        .distinct()
        .order_by("line", "user_sdwt_prod")
    )
    return [{"line_id": row["line"], "user_sdwt_prod": row["user_sdwt_prod"]} for row in pairs]


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
        .filter(Q(status=UserSdwtProdChange.Status.APPROVED) | Q(approved=True))
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
        .filter(Q(status=UserSdwtProdChange.Status.APPROVED) | Q(approved=True))
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

    next_change = (
        UserSdwtProdChange.objects.filter(user=user, effective_from__gt=at_time)
        .filter(Q(status=UserSdwtProdChange.Status.APPROVED) | Q(approved=True))
        .order_by("effective_from", "id")
        .first()
    )

    before_user_sdwt_prod = None
    if next_change:
        before_user_sdwt_prod = next_change.from_user_sdwt_prod

    return {
        "department": getattr(user, "department", None) or UNKNOWN,
        "line": getattr(user, "line", None) or "",
        "user_sdwt_prod": before_user_sdwt_prod
        or getattr(user, "user_sdwt_prod", None)
        or UNCLASSIFIED_USER_SDWT_PROD,
    }


def get_affiliation_option(
    department: str,
    line: str,
    user_sdwt_prod: str,
) -> Affiliation | None:
    """부서/라인/user_sdwt_prod 조합에 해당하는 소속 옵션 행을 조회합니다.

    Return a single affiliation option row, or None when missing.
    """

    if not department or not line or not user_sdwt_prod:
        return None

    try:
        return Affiliation.objects.get(
            department=department.strip(),
            line=line.strip(),
            user_sdwt_prod=user_sdwt_prod.strip(),
        )
    except Affiliation.DoesNotExist:
        return None


def get_affiliation_option_by_user_sdwt_prod(*, user_sdwt_prod: str) -> Affiliation | None:
    """user_sdwt_prod로 단일 Affiliation 옵션을 조회합니다.

    Return an Affiliation when only one row matches the given user_sdwt_prod.
    """

    if not isinstance(user_sdwt_prod, str) or not user_sdwt_prod.strip():
        return None

    normalized = user_sdwt_prod.strip()
    rows = list(Affiliation.objects.filter(user_sdwt_prod=normalized).order_by("id")[:2])
    if len(rows) != 1:
        return None
    return rows[0]
