# =============================================================================
# 모듈 설명: 접근 권한(UserSdwtProdAccess) 서비스 로직을 제공합니다.
# - 주요 대상: ensure_self_access, grant_or_revoke_access, get_manageable_groups_with_members
# - 불변 조건: 권한 부여/회수는 서비스 레이어에서만 처리합니다.
# =============================================================================

"""접근 권한(UserSdwtProdAccess) 관련 서비스 모음.

- 주요 대상: 접근 권한 보장, 부여/회수, 관리 그룹 조회
- 주요 엔드포인트/클래스: ensure_self_access, grant_or_revoke_access 등
- 가정/불변 조건: 권한 부여/회수는 서비스 레이어에서만 처리됨
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List

from django.db import IntegrityError, transaction

from .keycloak_access import has_sdwt_capability
from .. import selectors
from ..models import AccessAuditLog, UserSdwtProdAccess
from .access_control import create_access_audit_log
from .utils import (
    _build_user_sdwt_display_map,
    _is_privileged_user,
    _normalize_user_sdwt_lookup_key,
    _resolve_user_sdwt_prod_role,
    _user_can_manage_user_sdwt_prod,
    _same_user_sdwt_prod,
)


ROLE_ORDER = {
    UserSdwtProdAccess.Roles.VIEWER: 0,
    UserSdwtProdAccess.Roles.MEMBER: 1,
    UserSdwtProdAccess.Roles.MANAGER: 2,
}

AFFILIATION_CAPABILITY_READ = "read"
AFFILIATION_CAPABILITY_WRITE = "write"
AFFILIATION_CAPABILITY_DELETE = "delete"
AFFILIATION_CAPABILITY_MANAGE_ACCESS = "manage_access"
AFFILIATION_CAPABILITY_APPROVE = "approve"

AFFILIATION_CAPABILITY_ROLES = {
    AFFILIATION_CAPABILITY_READ: frozenset(
        {
            UserSdwtProdAccess.Roles.VIEWER,
            UserSdwtProdAccess.Roles.MEMBER,
            UserSdwtProdAccess.Roles.MANAGER,
        }
    ),
    AFFILIATION_CAPABILITY_WRITE: frozenset(
        {
            UserSdwtProdAccess.Roles.MEMBER,
            UserSdwtProdAccess.Roles.MANAGER,
        }
    ),
    AFFILIATION_CAPABILITY_DELETE: frozenset({UserSdwtProdAccess.Roles.MANAGER}),
    AFFILIATION_CAPABILITY_MANAGE_ACCESS: frozenset({UserSdwtProdAccess.Roles.MANAGER}),
    AFFILIATION_CAPABILITY_APPROVE: frozenset({UserSdwtProdAccess.Roles.MANAGER}),
}


def _serialize_affiliation_role_audit(
    access: UserSdwtProdAccess | None,
) -> dict[str, object]:
    """소속 역할 변경 전후 상태를 감사 snapshot으로 직렬화합니다."""

    if access is None:
        return {}
    return {
        "role": access.role,
        "grantedBy": access.granted_by_id,
    }


def has_affiliation_capability(*, user: Any, user_sdwt_prod: str, capability: str, context=None) -> bool:
    """검증된 세션 context로 SDWT 데이터 작업을 검사합니다."""
    return has_sdwt_capability(user=user, user_sdwt_prod=user_sdwt_prod, capability=capability, context=context)


def has_affiliation_capability_for_ids(
    *,
    user: Any,
    affiliation_ids: Iterable[int],
    capability: str,
) -> bool:
    """여러 활성 소속에서 동일 capability 보유 여부를 일괄 판정합니다."""

    normalized_capability = (capability or "").strip().lower()
    allowed_roles = AFFILIATION_CAPABILITY_ROLES.get(normalized_capability)
    if allowed_roles is None or user is None:
        return False
    requested_ids = list(affiliation_ids)
    if not requested_ids or any(
        type(affiliation_id) is not int or affiliation_id <= 0
        for affiliation_id in requested_ids
    ):
        return False
    normalized_ids = set(requested_ids)

    active_ids = selectors.list_active_affiliation_ids(
        affiliation_ids=normalized_ids,
    )
    if active_ids != normalized_ids:
        return False
    if _is_privileged_user(user):
        return True

    explicit_roles = selectors.list_affiliation_roles_for_user_by_ids(
        user=user,
        affiliation_ids=normalized_ids,
    )
    return all(explicit_roles.get(key) in allowed_roles for key in normalized_ids)


def _normalize_access_role(role: str) -> str:
    """접근 권한 역할을 정규화합니다.

    입력:
    - role: viewer/member/manager 중 하나

    반환:
    - str: 정규화된 역할

    부작용:
    - 없음

    오류:
    - 없음
    """

    normalized = (role or "").strip().lower()
    if normalized in ROLE_ORDER:
        return normalized
    return UserSdwtProdAccess.Roles.VIEWER


def _normalize_role_for_current_affiliation(
    *,
    user: Any,
    user_sdwt_prod: str,
    role: str,
) -> str:
    """소속에 의한 자동 승급 없이 요청한 역할을 정규화합니다."""

    return _normalize_access_role(role)


def _should_upgrade_role(current_role: str, target_role: str) -> bool:
    """현재 역할에서 목표 역할로 상향이 필요한지 확인합니다."""

    current_rank = ROLE_ORDER.get(current_role, 0)
    target_rank = ROLE_ORDER.get(target_role, 0)
    return target_rank > current_rank


def ensure_self_access(
    user: Any,
    *,
    role: str = UserSdwtProdAccess.Roles.MEMBER,
    audit_actor: Any | None = None,
    audit_reason: str | None = None,
) -> UserSdwtProdAccess | None:
    """사용자 본인의 user_sdwt_prod 접근 권한 행을 보장합니다.

    입력:
    - user: Django 사용자 객체
    - role: 부여할 역할(viewer/member/manager)
    - audit_actor: 자동 역할 변경을 기록할 행위자
    - audit_reason: 자동 역할 변경 사유

    반환:
    - UserSdwtProdAccess | None: 접근 권한 행 또는 None

    부작용:
    - UserSdwtProdAccess 생성/업데이트
    - audit_actor가 있고 역할이 바뀌면 AccessAuditLog 생성

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 현재 소속 유효성 확인
    # -----------------------------------------------------------------------------
    current_affiliation = selectors.get_current_affiliation_record(user=user)
    if current_affiliation is None or current_affiliation.affiliation is None:
        return None

    normalized_user_sdwt = current_affiliation.affiliation.user_sdwt_prod.strip()
    if not normalized_user_sdwt:
        return None

    # -----------------------------------------------------------------------------
    # 2) 접근 권한 역할 정규화
    # -----------------------------------------------------------------------------
    normalized_role = _normalize_role_for_current_affiliation(
        user=user,
        user_sdwt_prod=normalized_user_sdwt,
        role=role,
    )

    # -----------------------------------------------------------------------------
    # 3) 접근 권한 행 생성/업데이트
    # -----------------------------------------------------------------------------
    with transaction.atomic():
        access = selectors.get_access_row_for_user_and_prod(
            user=user,
            user_sdwt_prod=normalized_user_sdwt,
        )
        before = _serialize_affiliation_role_audit(access)
        is_new_access = access is None
        if access is None:
            try:
                with transaction.atomic():
                    access = UserSdwtProdAccess.objects.create(
                        user=user,
                        affiliation=current_affiliation.affiliation,
                        role=normalized_role,
                        granted_by=None,
                    )
            except IntegrityError:
                access = selectors.get_access_row_for_user_and_prod(
                    user=user,
                    user_sdwt_prod=normalized_user_sdwt,
                )
                if access is None:
                    raise
                before = _serialize_affiliation_role_audit(access)
                is_new_access = False

        role_upgraded = _should_upgrade_role(access.role, normalized_role)
        if role_upgraded:
            access.role = normalized_role
            access.save(update_fields=["role"])

        if audit_actor is not None and (is_new_access or role_upgraded):
            create_access_audit_log(
                scope=None,
                actor=audit_actor,
                target_user=user,
                policy_rule=None,
                affiliation=access.affiliation,
                action=(
                    AccessAuditLog.Actions.AFFILIATION_ROLE_GRANT
                    if is_new_access
                    else AccessAuditLog.Actions.AFFILIATION_ROLE_CHANGE
                ),
                before=before,
                after=_serialize_affiliation_role_audit(access),
                reason=audit_reason,
            )

    return access


def downgrade_member_access(
    *,
    user: Any,
    user_sdwt_prod: str,
    audit_actor: Any | None = None,
    audit_reason: str | None = None,
) -> None:
    """특정 소속의 member 역할을 viewer로 강등합니다.

    입력:
    - user: Django 사용자 객체
    - user_sdwt_prod: 대상 소속
    - audit_actor: 자동 역할 변경을 기록할 행위자
    - audit_reason: 자동 역할 변경 사유

    반환:
    - 없음

    부작용:
    - UserSdwtProdAccess role 업데이트
    - audit_actor가 있으면 AccessAuditLog 생성

    오류:
    - 없음
    """

    with transaction.atomic():
        access = selectors.get_access_row_for_user_and_prod_for_update(
            user=user,
            user_sdwt_prod=user_sdwt_prod,
        )
        if access is None or access.role != UserSdwtProdAccess.Roles.MEMBER:
            return

        before = _serialize_affiliation_role_audit(access)
        access.role = UserSdwtProdAccess.Roles.VIEWER
        access.save(update_fields=["role"])
        if audit_actor is not None:
            create_access_audit_log(
                scope=None,
                actor=audit_actor,
                target_user=user,
                policy_rule=None,
                affiliation=access.affiliation,
                action=AccessAuditLog.Actions.AFFILIATION_ROLE_CHANGE,
                before=before,
                after=_serialize_affiliation_role_audit(access),
                reason=audit_reason,
            )


def grant_or_revoke_access(
    *,
    grantor: Any,
    target_group: str,
    target_user: Any,
    action: str,
    role: str | None,
    reason: str | None,
) -> tuple[dict[str, object], int]:
    """사용자의 user_sdwt_prod 그룹 접근 권한을 부여/회수합니다.

    입력:
    - grantor: 권한을 부여/회수하는 사용자
    - target_group: 대상 그룹
    - target_user: 대상 사용자
    - action: grant/revoke (부여/회수)
    - role: 부여할 역할(viewer/member/manager)
    - reason: 수동 변경 사유

    반환:
    - tuple[dict[str, object], int]: (payload, status_code) (응답 본문, 상태 코드)

    부작용:
    - UserSdwtProdAccess 생성/업데이트/삭제

    오류:
    - 400: 변경 사유 누락 또는 잘못된 입력
    - 403: 권한 없음
    - 409: 마지막 manager 강등 또는 제거 시도
    """

    # -----------------------------------------------------------------------------
    # 1) 입력과 관리 권한 검증
    # -----------------------------------------------------------------------------
    normalized_target = (target_group or "").strip()
    normalized_action = (action or "").strip().lower()
    normalized_reason = (reason or "").strip()
    if normalized_action not in {"grant", "revoke"}:
        return {"error": "Invalid action"}, 400
    if not normalized_reason:
        return {"error": "reason_required"}, 400

    requested_role = (role or "").strip().lower()
    if normalized_action == "grant" and requested_role not in ROLE_ORDER:
        return {"error": "Invalid role"}, 400

    # -----------------------------------------------------------------------------
    # 2) 소속 단위 잠금으로 마지막 manager 불변조건을 직렬화
    # -----------------------------------------------------------------------------
    with transaction.atomic():
        target_affiliation = selectors.get_affiliation_option_for_update_by_user_sdwt_prod(
            user_sdwt_prod=normalized_target
        )
        locked_target_user = selectors.get_user_by_id_for_update(
            user_id=getattr(target_user, "id", None)
        )
        if target_affiliation is None:
            return {"error": "Invalid user_sdwt_prod"}, 400
        if locked_target_user is None:
            return {"error": "User not found"}, 404

        # 소속 잠금 뒤 최신 역할을 읽어 권한 회수와 현재 작업을 직렬화합니다.
        if not _user_can_manage_user_sdwt_prod(
            user=grantor,
            user_sdwt_prod=target_affiliation.user_sdwt_prod,
        ):
            return {"error": "forbidden"}, 403

        access = selectors.get_access_row_for_user_and_prod_for_update(
            user=locked_target_user,
            user_sdwt_prod=normalized_target,
        )

        # -----------------------------------------------------------------------------
        # 3) 회수 처리
        # -----------------------------------------------------------------------------
        if normalized_action == "revoke":
            if access is None:
                return {"status": "ok", "deleted": 0}, 200
            if (
                access.role == UserSdwtProdAccess.Roles.MANAGER
                and not selectors.other_manager_exists(
                    user_sdwt_prod=normalized_target,
                    exclude_user=locked_target_user,
                )
            ):
                return {"error": "Cannot remove the last manager for this group"}, 409

            before = _serialize_affiliation_role_audit(access)
            create_access_audit_log(
                scope=None,
                actor=grantor,
                target_user=locked_target_user,
                policy_rule=None,
                affiliation=target_affiliation,
                action=AccessAuditLog.Actions.AFFILIATION_ROLE_REVOKE,
                before=before,
                after={},
                reason=normalized_reason,
            )
            access.delete()
            return {"status": "ok", "deleted": 1}, 200

        # -----------------------------------------------------------------------------
        # 4) 신규 부여 또는 역할 변경 처리
        # -----------------------------------------------------------------------------
        normalized_role = _normalize_role_for_current_affiliation(
            user=locked_target_user,
            user_sdwt_prod=normalized_target,
            role=requested_role,
        )
        if (
            access is not None
            and access.role == UserSdwtProdAccess.Roles.MANAGER
            and normalized_role != UserSdwtProdAccess.Roles.MANAGER
            and not selectors.other_manager_exists(
                user_sdwt_prod=normalized_target,
                exclude_user=locked_target_user,
            )
        ):
            return {"error": "Cannot demote the last manager for this group"}, 409

        before = _serialize_affiliation_role_audit(access)
        is_new_access = access is None
        if is_new_access:
            try:
                with transaction.atomic():
                    access = UserSdwtProdAccess.objects.create(
                        user=locked_target_user,
                        affiliation=target_affiliation,
                        role=normalized_role,
                        granted_by=grantor,
                    )
            except IntegrityError:
                access = selectors.get_access_row_for_user_and_prod_for_update(
                    user=locked_target_user,
                    user_sdwt_prod=normalized_target,
                )
                if access is None:
                    raise
                is_new_access = False
                before = _serialize_affiliation_role_audit(access)

        has_changed = bool(
            is_new_access
            or access.role != normalized_role
            or access.granted_by_id != grantor.id
        )
        if access.role != normalized_role or access.granted_by_id != grantor.id:
            access.role = normalized_role
            access.granted_by = grantor
            access.save(update_fields=["role", "granted_by"])

        if has_changed:
            create_access_audit_log(
                scope=None,
                actor=grantor,
                target_user=locked_target_user,
                policy_rule=None,
                affiliation=target_affiliation,
                action=(
                    AccessAuditLog.Actions.AFFILIATION_ROLE_GRANT
                    if is_new_access
                    else AccessAuditLog.Actions.AFFILIATION_ROLE_CHANGE
                ),
                before=before,
                after=_serialize_affiliation_role_audit(access),
                reason=normalized_reason,
            )

        return _serialize_member(access), 200


def get_manageable_groups_with_members(*, user: Any) -> dict[str, object]:
    """사용자가 관리 가능한 그룹과 멤버 목록을 반환합니다.

    입력:
    - user: Django 사용자 객체

    반환:
    - dict[str, object]: 그룹/멤버 목록

    부작용:
    - 없음

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 관리 가능한 그룹 집합 계산
    # -----------------------------------------------------------------------------
    manageable_set = selectors.list_manageable_user_sdwt_prod_values(user=user)

    groups: List[Dict[str, object]] = []
    if not manageable_set:
        return {"groups": groups}

    # -----------------------------------------------------------------------------
    # 2) 멤버 목록 구성
    # -----------------------------------------------------------------------------
    manageable_display_map = _build_user_sdwt_display_map(sorted(manageable_set))
    members_by_group: Dict[str, List[Dict[str, object]]] = {
        prod: [] for prod in manageable_display_map.values()
    }
    for access in selectors.list_group_members(user_sdwt_prods=manageable_set):
        lookup_key = _normalize_user_sdwt_lookup_key(access.user_sdwt_prod)
        canonical_prod = manageable_display_map.get(lookup_key, access.user_sdwt_prod)
        members_by_group.setdefault(canonical_prod, []).append(_serialize_member(access))

    # -----------------------------------------------------------------------------
    # 3) 응답 정렬 및 반환
    # -----------------------------------------------------------------------------
    for prod in sorted(manageable_display_map.values()):
        groups.append({"userSdwtProd": prod, "members": members_by_group.get(prod, [])})

    return {"groups": groups}


def get_affiliation_members(
    *,
    user: Any,
    user_sdwt_prod: str,
) -> tuple[dict[str, object], int]:
    """접근 가능한 소속의 사용자 멤버 목록을 반환합니다.

    입력:
    - user: 요청 사용자
    - user_sdwt_prod: 조회할 소속 식별자

    반환:
    - tuple[dict[str, object], int]: 응답 payload와 HTTP 상태 코드

    부작용:
    - 없음

    오류:
    - 400: 소속 식별자 누락
    - 403: 조회 권한 없음
    """

    normalized_target = (user_sdwt_prod or "").strip()
    if not normalized_target:
        return {"error": "user_sdwt_prod is required"}, 400

    target_lookup_key = _normalize_user_sdwt_lookup_key(normalized_target)
    accessible_values = selectors.get_accessible_user_sdwt_prods_for_user(user)
    accessible_display_map = _build_user_sdwt_display_map(accessible_values)
    if not _is_privileged_user(user) and target_lookup_key not in accessible_display_map:
        return {"error": "forbidden"}, 403

    canonical_user_sdwt = accessible_display_map.get(target_lookup_key, normalized_target)
    access_rows = list(selectors.list_group_members(user_sdwt_prods={canonical_user_sdwt}))
    access_by_user_id = {access.user_id: access for access in access_rows}
    members: list[dict[str, object]] = []
    for access in access_rows:
        members.append(
            _serialize_affiliation_member(
                member_user=access.user,
                user_sdwt_prod=canonical_user_sdwt,
                access=access,
            )
        )

    role_order = {"manager": 0, "member": 1, "viewer": 2}
    members.sort(
        key=lambda row: (
            role_order.get(str(row.get("role") or "viewer"), 2),
            str(row.get("username") or ""),
            int(row.get("userId") or 0),
        )
    )
    actor_role = _resolve_user_sdwt_prod_role(
        user=user,
        user_sdwt_prod=canonical_user_sdwt,
    )
    return {
        "userSdwtProd": canonical_user_sdwt,
        "actorRole": actor_role,
        "canManage": has_affiliation_capability(
            user=user,
            user_sdwt_prod=canonical_user_sdwt,
            capability=AFFILIATION_CAPABILITY_MANAGE_ACCESS,
        ),
        "members": members,
    }, 200


def _serialize_access(access: UserSdwtProdAccess, source: str) -> Dict[str, object]:
    """UserSdwtProdAccess 행을 API 응답용 dict로 직렬화합니다.

    입력:
    - access: 접근 권한 행
    - source: 권한 출처 문자열

    반환:
    - Dict[str, object]: 직렬화 결과

    부작용:
    - 없음

    오류:
    - 없음
    """

    return {
        "userSdwtProd": access.user_sdwt_prod,
        "role": access.role,
        "source": source,
        "grantedBy": access.granted_by_id,
        "grantedAt": access.created_at.isoformat(),
    }


def _serialize_access_fallback(
    *,
    user_sdwt_prod: str,
    source: str,
    role: str,
) -> Dict[str, object]:
    """DB row가 없는 경우를 위한 접근 권한 기본값을 생성합니다.

    입력:
    - user_sdwt_prod: 소속 식별자
    - source: 권한 출처 문자열

    반환:
    - Dict[str, object]: 기본값 응답

    부작용:
    - 없음

    오류:
    - 없음
    """

    return {
        "userSdwtProd": user_sdwt_prod,
        "role": role,
        "source": source,
        "grantedBy": None,
        "grantedAt": None,
    }


def _serialize_member(access: UserSdwtProdAccess) -> Dict[str, object]:
    """그룹 멤버(access + user)를 API 응답용 dict로 직렬화합니다.

    입력:
    - access: 접근 권한 행

    반환:
    - Dict[str, object]: 멤버 응답

    부작용:
    - 없음

    오류:
    - 없음
    """

    user = access.user
    return {
        "userId": user.id,
        "username": user.username,
        "name": (user.first_name or "") + (user.last_name or ""),
        "knoxId": getattr(user, "knox_id", None),
        "userSdwtProd": access.user_sdwt_prod,
        "role": access.role,
        "grantedBy": access.granted_by_id,
        "grantedAt": access.created_at.isoformat(),
    }


def _serialize_affiliation_member(
    *,
    member_user: Any,
    user_sdwt_prod: str,
    access: UserSdwtProdAccess | None,
) -> Dict[str, object]:
    """현재 소속 사용자와 명시 접근 권한을 멤버 응답으로 직렬화합니다."""

    username = getattr(member_user, "username", None)
    username_value = username.strip() if isinstance(username, str) else ""
    current_affiliation = _get_user_current_affiliation(member_user)
    affiliation = getattr(current_affiliation, "affiliation", None)
    current_user_sdwt_prod = getattr(affiliation, "user_sdwt_prod", None)
    name_value = (
        username_value
        or f"{getattr(member_user, 'first_name', '') or ''}{getattr(member_user, 'last_name', '') or ''}"
    )
    return {
        "userId": member_user.id,
        "username": username_value,
        "name": name_value,
        "knoxId": getattr(member_user, "knox_id", None),
        "email": getattr(member_user, "email", None),
        "department": getattr(affiliation, "department", None) or getattr(member_user, "department", None),
        "userSdwtProd": user_sdwt_prod,
        "role": access.role if access else UserSdwtProdAccess.Roles.MEMBER,
        "isCurrentAffiliation": _same_user_sdwt_prod(
            current_user_sdwt_prod,
            user_sdwt_prod,
        ),
        "grantedBy": access.granted_by_id if access else None,
        "grantedAt": access.created_at.isoformat() if access else None,
    }


def _get_user_current_affiliation(member_user: Any) -> Any | None:
    """사용자의 현재 소속 역참조를 안전하게 반환합니다."""

    try:
        return getattr(member_user, "current_affiliation", None)
    except Exception:
        return None


def _current_access_list(user: Any) -> List[Dict[str, object]]:
    """현재 사용자 기준 접근 가능한 그룹 목록을 구성합니다.

    입력:
    - user: Django 사용자 객체

    반환:
    - List[Dict[str, object]]: 접근 가능한 그룹 목록

    부작용:
    - 없음

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 접근 권한 행 조회
    # -----------------------------------------------------------------------------
    rows = selectors.list_user_sdwt_prod_access_rows(user=user)
    return [_serialize_access(row, "grant") for row in sorted(rows, key=lambda row: row.user_sdwt_prod)]
