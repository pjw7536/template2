from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List, Tuple

from django.core.paginator import EmptyPage, Paginator
from django.db import transaction
from django.utils import timezone

from api.common.affiliations import UNASSIGNED_USER_SDWT_PROD
from api.emails import services as email_services

from .models import (
    Affiliation,
    ExternalAffiliationSnapshot,
    UserProfile,
    UserSdwtProdAccess,
    UserSdwtProdChange,
)
from . import selectors


def _is_privileged_user(user: Any) -> bool:
    """superuser/staff 여부를 반환합니다."""

    return bool(getattr(user, "is_superuser", False) or getattr(user, "is_staff", False))


def _user_can_manage_user_sdwt_prod(*, user: Any, user_sdwt_prod: str) -> bool:
    """사용자가 user_sdwt_prod 그룹을 관리할 권한이 있는지 반환합니다."""

    if _is_privileged_user(user):
        return True
    return selectors.user_has_manage_permission(user=user, user_sdwt_prod=user_sdwt_prod)


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


def _serialize_actor(user: Any) -> dict[str, object] | None:
    """승인/요청 사용자 정보를 직렬화합니다."""

    if not user:
        return None
    username = getattr(user, "username", "") or ""
    return {"id": user.id, "username": username}


def _serialize_affiliation_change(change: UserSdwtProdChange) -> dict[str, object]:
    """UserSdwtProdChange를 응답용 dict로 직렬화합니다."""

    return {
        "id": change.id,
        "status": change.status,
        "department": change.department,
        "line": change.line,
        "fromUserSdwtProd": change.from_user_sdwt_prod,
        "toUserSdwtProd": change.to_user_sdwt_prod,
        "effectiveFrom": change.effective_from.isoformat(),
        "approvedAt": change.approved_at.isoformat() if change.approved_at else None,
        "requestedAt": change.created_at.isoformat(),
        "approvedBy": _serialize_actor(change.approved_by),
        "requestedBy": _serialize_actor(change.created_by),
    }


def _serialize_affiliation_change_request(change: UserSdwtProdChange) -> dict[str, object]:
    """승인 요청용 UserSdwtProdChange 응답 payload를 구성합니다."""

    user = change.user
    user_payload = {
        "id": getattr(user, "id", None),
        "username": getattr(user, "username", None),
        "email": getattr(user, "email", None),
        "sabun": getattr(user, "sabun", None),
        "knoxId": getattr(user, "knox_id", None),
        "department": getattr(user, "department", None),
        "line": getattr(user, "line", None),
        "userSdwtProd": getattr(user, "user_sdwt_prod", None),
    }

    return {
        **_serialize_affiliation_change(change),
        "user": user_payload,
    }


def get_affiliation_change_requests(
    *,
    user: Any,
    status: str | None,
    search: str | None,
    user_sdwt_prod: str | None,
    page: int,
    page_size: int,
) -> Tuple[dict[str, object], int]:
    """승인 가능한 소속 변경 요청 목록을 페이지 단위로 조회합니다.

    Returns:
        (payload, http_status)

    Side effects:
        None. Read-only query.
    """

    is_privileged = _is_privileged_user(user)
    manageable_user_sdwt_prods = None
    can_manage = False
    allowed_user_sdwt_prods: set[str] | None = None
    if not is_privileged:
        manageable_user_sdwt_prods = selectors.list_manageable_user_sdwt_prod_values(user=user)
        can_manage = bool(manageable_user_sdwt_prods)
        allowed_user_sdwt_prods = set(manageable_user_sdwt_prods)
        current_user_sdwt = getattr(user, "user_sdwt_prod", None)
        if isinstance(current_user_sdwt, str) and current_user_sdwt.strip():
            allowed_user_sdwt_prods.add(current_user_sdwt.strip())
        if not allowed_user_sdwt_prods:
            return {"error": "forbidden"}, 403
        if user_sdwt_prod and user_sdwt_prod not in allowed_user_sdwt_prods:
            return {"error": "forbidden"}, 403
        manageable_user_sdwt_prods = allowed_user_sdwt_prods
    else:
        can_manage = True

    qs = selectors.list_affiliation_change_requests(
        manageable_user_sdwt_prods=manageable_user_sdwt_prods,
        status=status,
        search=search,
        user_sdwt_prod=user_sdwt_prod,
    )

    paginator = Paginator(qs, page_size)
    try:
        page_obj = paginator.page(page)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages or 1)

    results = [_serialize_affiliation_change_request(change) for change in page_obj.object_list]

    return (
        {
            "results": results,
            "page": page_obj.number,
            "pageSize": page_size,
            "total": paginator.count,
            "totalPages": paginator.num_pages,
            "canManage": can_manage,
        },
        200,
    )


def get_account_overview(*, user: Any, timezone_name: str) -> dict[str, object]:
    """계정 화면에서 필요한 전체 정보를 한번에 구성합니다.

    Returns:
        Dict with profile, affiliation, history, mailbox access, manageable groups.
    """

    access_list = _current_access_list(user)
    manageable = [entry["userSdwtProd"] for entry in access_list if entry["canManage"]]

    profile = {
        "id": getattr(user, "id", None),
        "username": getattr(user, "username", None),
        "knoxId": getattr(user, "knox_id", None),
        "userSdwtProd": getattr(user, "user_sdwt_prod", None),
        "role": selectors.get_user_profile_role(user=user),
        "isSuperuser": bool(getattr(user, "is_superuser", False)),
        "isStaff": bool(getattr(user, "is_staff", False)),
    }

    affiliation_payload = {
        "currentUserSdwtProd": getattr(user, "user_sdwt_prod", None),
        "currentDepartment": getattr(user, "department", None),
        "currentLine": getattr(user, "line", None),
        "timezone": timezone_name,
        "accessibleUserSdwtProds": access_list,
        "manageableUserSdwtProds": manageable,
    }

    history_rows = selectors.list_user_sdwt_prod_changes(user=user)
    history_payload = [_serialize_affiliation_change(change) for change in history_rows]

    manageable_groups = get_manageable_groups_with_members(user=user)

    mailbox_rows = email_services.get_mailbox_access_summary_for_user(user=user)
    access_map = {entry["userSdwtProd"]: entry for entry in access_list}
    is_privileged = _is_privileged_user(user)

    mailbox_payload: list[dict[str, object]] = []
    for mailbox in mailbox_rows:
        user_sdwt_prod = mailbox.get("userSdwtProd")
        access = access_map.get(user_sdwt_prod)
        if access is None and is_privileged:
            access_source = "privileged"
            can_manage = True
            granted_by = None
            granted_at = None
        else:
            access_source = access.get("source") if access else "unknown"
            can_manage = bool(access.get("canManage")) if access else False
            granted_by = access.get("grantedBy") if access else None
            granted_at = access.get("grantedAt") if access else None

        mailbox_payload.append(
            {
                **mailbox,
                "accessSource": access_source,
                "canManage": can_manage,
                "grantedBy": granted_by,
                "grantedAt": granted_at,
            }
        )

    return {
        "user": profile,
        "affiliation": affiliation_payload,
        "affiliationReconfirm": get_affiliation_reconfirm_status(user=user),
        "affiliationHistory": history_payload,
        "manageableGroups": manageable_groups,
        "mailboxAccess": mailbox_payload,
    }


def request_affiliation_change(
    *,
    user: Any,
    option: Any,
    to_user_sdwt_prod: str,
    effective_from: datetime,
    timezone_name: str,
) -> Tuple[dict[str, object], int]:
    """user_sdwt_prod 소속 변경을 요청합니다.

    Request a user_sdwt_prod affiliation change.

    Returns:
        (payload, http_status)

    Side effects:
        - Writes UserSdwtProdChange rows.
    """

    ensure_self_access(user, as_manager=False)

    existing_pending = selectors.get_pending_user_sdwt_prod_change(user=user)
    if existing_pending is not None:
        return {"error": "pending change exists", "changeId": existing_pending.id}, 409

    if effective_from is None:
        effective_from = timezone.now()
    elif timezone.is_naive(effective_from):
        effective_from = timezone.make_aware(effective_from, timezone.utc)
    change = UserSdwtProdChange.objects.create(
        user=user,
        department=getattr(option, "department", None),
        line=getattr(option, "line", None),
        from_user_sdwt_prod=getattr(user, "user_sdwt_prod", None),
        to_user_sdwt_prod=to_user_sdwt_prod,
        effective_from=effective_from,
        status=UserSdwtProdChange.Status.PENDING,
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
    """

    change = selectors.get_user_sdwt_prod_change_by_id(change_id=change_id)
    if change is None:
        return {"error": "Change not found"}, 404

    if not _user_can_manage_user_sdwt_prod(user=approver, user_sdwt_prod=change.to_user_sdwt_prod):
        return {"error": "forbidden"}, 403

    if change.status == UserSdwtProdChange.Status.APPROVED or change.approved or change.applied:
        return {"error": "already applied"}, 400
    if change.status == UserSdwtProdChange.Status.REJECTED:
        return {"error": "already rejected"}, 400

    target_user = change.user
    previous_user_sdwt = getattr(target_user, "user_sdwt_prod", None)
    had_previous_affiliation = bool(
        isinstance(previous_user_sdwt, str)
        and previous_user_sdwt.strip()
        and previous_user_sdwt.strip() != UNASSIGNED_USER_SDWT_PROD
    )

    now = timezone.now()
    with transaction.atomic():
        target_user.user_sdwt_prod = change.to_user_sdwt_prod
        target_user.department = change.department
        target_user.line = change.line
        target_user.affiliation_confirmed_at = now
        target_user.requires_affiliation_reconfirm = False
        target_user.save(
            update_fields=[
                "user_sdwt_prod",
                "department",
                "line",
                "affiliation_confirmed_at",
                "requires_affiliation_reconfirm",
            ]
        )

        change.approved = True
        change.approved_by = approver
        change.approved_at = now
        change.applied = True
        change.status = UserSdwtProdChange.Status.APPROVED
        change.save(
            update_fields=[
                "approved",
                "approved_by",
                "approved_at",
                "applied",
                "status",
            ]
        )

        ensure_self_access(target_user, as_manager=False)

        # Keep any existing access rows even when affiliation changes.

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


def reject_affiliation_change(
    *,
    approver: Any,
    change_id: int,
) -> Tuple[dict[str, object], int]:
    """대기 중인 UserSdwtProdChange를 거절 처리합니다.

    Reject a pending UserSdwtProdChange.

    Returns:
        (payload, http_status)

    Side effects:
        - Updates UserSdwtProdChange status to REJECTED.
    """

    change = selectors.get_user_sdwt_prod_change_by_id(change_id=change_id)
    if change is None:
        return {"error": "Change not found"}, 404

    if not _user_can_manage_user_sdwt_prod(user=approver, user_sdwt_prod=change.to_user_sdwt_prod):
        return {"error": "forbidden"}, 403

    if change.status == UserSdwtProdChange.Status.REJECTED:
        return {"error": "already rejected"}, 400
    if change.status == UserSdwtProdChange.Status.APPROVED or change.approved or change.applied:
        return {"error": "already applied"}, 400

    change.status = UserSdwtProdChange.Status.REJECTED
    change.approved = False
    change.approved_by = approver
    change.approved_at = timezone.now()
    change.applied = False
    change.save(update_fields=["status", "approved", "approved_by", "approved_at", "applied"])

    return {"status": "rejected", "changeId": change.id}, 200


def sync_external_affiliations(
    *,
    records: Iterable[dict[str, object]],
) -> dict[str, int]:
    """외부 DB 예측 소속 스냅샷을 업서트하고 변경 시 재확인 플래그를 세웁니다.

    Args:
        records: Iterable of dicts with knox_id, user_sdwt_prod, source_updated_at.

    Returns:
        Dict with created/updated/unchanged/flagged counts.

    Side effects:
        - Upserts ExternalAffiliationSnapshot rows.
        - Updates User.requires_affiliation_reconfirm when predicted values change.
    """

    now = timezone.now()
    created = 0
    updated = 0
    unchanged = 0
    flagged = 0

    record_list = [record for record in records if isinstance(record, dict)]
    # 동일 knox_id 중복 입력으로 인한 unique 충돌을 피하려고 마지막 레코드로 정규화합니다.
    normalized_records: dict[str, dict[str, object]] = {}
    for record in record_list:
        knox_id = record.get("knox_id")
        if isinstance(knox_id, str) and knox_id.strip():
            normalized_records[knox_id.strip()] = record

    knox_ids = list(normalized_records.keys())
    existing = selectors.get_external_affiliation_snapshots_by_knox_ids(knox_ids=knox_ids)

    for record in normalized_records.values():
        knox_id = (record.get("knox_id") or "").strip()
        predicted = (record.get("user_sdwt_prod") or record.get("predicted_user_sdwt_prod") or "").strip()
        source_updated_at = record.get("source_updated_at") or record.get("sourceUpdatedAt") or now
        if not knox_id or not predicted:
            continue
        if isinstance(source_updated_at, datetime) and timezone.is_naive(source_updated_at):
            source_updated_at = timezone.make_aware(source_updated_at, timezone.utc)
        if not isinstance(source_updated_at, datetime):
            source_updated_at = now

        snapshot = existing.get(knox_id)
        if snapshot is None:
            snapshot = ExternalAffiliationSnapshot.objects.create(
                knox_id=knox_id,
                predicted_user_sdwt_prod=predicted,
                source_updated_at=source_updated_at,
                last_seen_at=now,
            )
            created += 1
            existing[knox_id] = snapshot
            continue

        changed = snapshot.predicted_user_sdwt_prod != predicted
        if changed or snapshot.source_updated_at != source_updated_at:
            snapshot.predicted_user_sdwt_prod = predicted
            snapshot.source_updated_at = source_updated_at
            snapshot.last_seen_at = now
            snapshot.save(update_fields=["predicted_user_sdwt_prod", "source_updated_at", "last_seen_at"])
            updated += 1
        else:
            snapshot.last_seen_at = now
            snapshot.save(update_fields=["last_seen_at"])
            unchanged += 1

        if changed:
            user = selectors.get_user_by_knox_id(knox_id=knox_id)
            if user is not None:
                user.requires_affiliation_reconfirm = True
                user.save(update_fields=["requires_affiliation_reconfirm"])
                flagged += 1

    return {"created": created, "updated": updated, "unchanged": unchanged, "flagged": flagged}


def get_affiliation_reconfirm_status(*, user: Any) -> dict[str, object]:
    """사용자의 소속 재확인 상태와 예측값을 반환합니다.

    Returns:
        Dict with requiresReconfirm, predictedUserSdwtProd, currentUserSdwtProd.
    """

    if not user:
        return {"requiresReconfirm": False, "predictedUserSdwtProd": None, "currentUserSdwtProd": None}

    snapshot = selectors.get_external_affiliation_snapshot_by_knox_id(
        knox_id=getattr(user, "knox_id", "") or ""
    )
    predicted = snapshot.predicted_user_sdwt_prod if snapshot else None
    return {
        "requiresReconfirm": bool(getattr(user, "requires_affiliation_reconfirm", False)),
        "predictedUserSdwtProd": predicted,
        "currentUserSdwtProd": getattr(user, "user_sdwt_prod", None),
    }


def submit_affiliation_reconfirm_response(
    *,
    user: Any,
    accepted: bool,
    department: str | None,
    line: str | None,
    user_sdwt_prod: str | None,
    timezone_name: str,
) -> Tuple[dict[str, object], int]:
    """재확인 응답을 처리해 소속 변경 요청을 생성합니다.

    Returns:
        (payload, http_status)
    """

    if not user:
        return {"error": "unauthorized"}, 401

    selected_user_sdwt = (user_sdwt_prod or "").strip()
    if accepted and not selected_user_sdwt:
        snapshot = selectors.get_external_affiliation_snapshot_by_knox_id(
            knox_id=getattr(user, "knox_id", "") or ""
        )
        if snapshot:
            selected_user_sdwt = snapshot.predicted_user_sdwt_prod

    if not selected_user_sdwt:
        return {"error": "user_sdwt_prod is required"}, 400

    option = None
    if department and line:
        option = selectors.get_affiliation_option(
            (department or "").strip(),
            (line or "").strip(),
            selected_user_sdwt,
        )
    if option is None:
        option = selectors.get_affiliation_option_by_user_sdwt_prod(
            user_sdwt_prod=selected_user_sdwt
        )
    if option is None:
        return {"error": "Invalid department/line/user_sdwt_prod combination"}, 400

    response_payload, status_code = request_affiliation_change(
        user=user,
        option=option,
        to_user_sdwt_prod=selected_user_sdwt,
        effective_from=timezone.now(),
        timezone_name=timezone_name,
    )
    if status_code in (200, 202):
        user.requires_affiliation_reconfirm = False
        user.save(update_fields=["requires_affiliation_reconfirm"])

    return response_payload, status_code


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


def update_affiliation_jira_key(*, line_id: str, jira_key: str | None) -> int:
    """line_id에 해당하는 Affiliation의 jira_key를 업데이트합니다.

    Args:
        line_id: 대상 line_id 문자열.
        jira_key: Jira 프로젝트 키(없으면 None).

    Returns:
        업데이트된 row 개수.

    Side effects:
        Updates Affiliation.jira_key rows.
    """

    if not isinstance(line_id, str) or not line_id.strip():
        raise ValueError("line_id is required")

    normalized = jira_key.strip() if isinstance(jira_key, str) and jira_key.strip() else None
    with transaction.atomic():
        updated = Affiliation.objects.filter(line=line_id.strip()).update(jira_key=normalized)
    return int(updated or 0)


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
