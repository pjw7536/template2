# =============================================================================
# 모듈 설명: scope 기반 접근 권한 판정/요청/결정 서비스 로직을 제공합니다.
# - 주요 대상: AccessScope, AccessPolicyRule, UserAccess
# - 불변 조건: 기존 account 테이블은 정책 판정 근거로 재사용합니다.
# =============================================================================

"""scope 기반 접근 권한 서비스 모음."""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
from django.core.paginator import EmptyPage, Paginator
from django.db import IntegrityError, transaction
from django.utils import timezone

from .. import selectors
from ..models import (
    ACCESS_SCOPE_PORTAL,
    AccessAuditLog,
    AccessPolicyRule,
    AccessRole,
    AccessScope,
    UserAccess,
)
from .access_runtime import (
    _apply_portal_access_requirement,
    _build_access_payload,
    _build_portal_access_payloads_by_user,
    _get_user_department,
    _normalize_access_role,
    _requires_portal_access,
    _serialize_access_user,
    _serialize_effective_access_user,
    _serialize_scope,
    _serialize_user_access,
    can_manage_access,
)


_GRANT_ACTIONS = {"approve", "grant"}
_REVOKE_ACTIONS = {"reject", "revoke"}
_POLICY_AUDIT_ACTIONS = {
    AccessAuditLog.Actions.POLICY_CREATE,
    AccessAuditLog.Actions.POLICY_UPDATE,
    AccessAuditLog.Actions.POLICY_DELETE,
}
_SCOPE_AUDIT_ACTIONS = {
    AccessAuditLog.Actions.SCOPE_CREATE,
    AccessAuditLog.Actions.SCOPE_UPDATE,
    AccessAuditLog.Actions.SCOPE_DELETE,
}

def _set_pending_access_request(
    *,
    user: Any,
    scope: AccessScope,
    user_access: UserAccess | None,
) -> UserAccess:
    """명시 접근 행을 pending 일반 사용자 상태로 저장하고 감사 로그를 남깁니다."""

    before = _serialize_user_access(user_access) if user_access else {}
    if user_access is None:
        user_access = UserAccess(
            scope=scope,
            user=user,
        )

    user_access.department = _get_user_department(user=user)
    user_access.status = UserAccess.Status.PENDING
    user_access.role = AccessRole.USER
    user_access.requested_at = timezone.now()
    user_access.decided_by = None
    user_access.decided_at = None
    user_access.reason = None
    user_access.save()
    create_access_audit_log(
        scope=scope,
        actor=user,
        target_user=user,
        policy_rule=None,
        action=AccessAuditLog.Actions.REQUEST,
        before=before,
        after=_serialize_user_access(user_access),
        reason=None,
    )
    return user_access


def request_access(
    *,
    user: Any,
    scope_keys: list[str],
) -> tuple[dict[str, object], int]:
    """요청한 scope들과 필요한 Portal 접근을 한 transaction에서 신청합니다."""

    if not user or not getattr(user, "is_authenticated", False):
        return {"error": "unauthorized"}, 401
    normalized_scope_keys = list(
        dict.fromkeys(
            scope_key.strip()
            for scope_key in scope_keys
            if isinstance(scope_key, str) and scope_key.strip()
        )
    )
    if not normalized_scope_keys:
        return {"error": "scopes_required"}, 400

    with transaction.atomic():
        # 같은 사용자의 모든 scope 요청을 직렬화해 부분 성공과 중복 생성을 막습니다.
        locked_user = selectors.get_user_by_id_for_update(user_id=getattr(user, "pk", 0))
        if locked_user is None:
            return {"error": "user_not_found"}, 404

        scopes_by_key: dict[str, AccessScope] = {}
        for scope_key in normalized_scope_keys:
            scope = selectors.get_access_scope_by_key(scope_key=scope_key)
            if scope is None or not scope.is_active:
                return {"error": "scope_not_found", "scope": scope_key}, 404
            if not scope.requestable:
                return {"error": "not_requestable", "scope": scope_key}, 400
            scopes_by_key[scope_key] = scope

        requires_portal = any(
            _requires_portal_access(scope=scope)
            for scope in scopes_by_key.values()
        )
        if requires_portal and ACCESS_SCOPE_PORTAL not in scopes_by_key:
            portal_scope = selectors.get_access_scope_by_key(
                scope_key=ACCESS_SCOPE_PORTAL
            )
            if portal_scope is None or not portal_scope.is_active:
                return {"error": "portal_scope_not_found"}, 404
            if not portal_scope.requestable:
                return {
                    "error": "portal_not_requestable",
                    "scope": ACCESS_SCOPE_PORTAL,
                }, 400
            scopes_by_key = {
                ACCESS_SCOPE_PORTAL: portal_scope,
                **scopes_by_key,
            }

        raw_access_by_key: dict[str, dict[str, object]] = {}
        changed = False
        for scope_key, scope in scopes_by_key.items():
            policy_rules = selectors.list_active_access_policy_rules(
                scope=scope,
                department=_get_user_department(user=locked_user),
            )
            user_access = selectors.get_user_access_for_scope_for_update(
                user=locked_user,
                scope=scope,
            )
            raw_access = _build_access_payload(
                user=locked_user,
                scope=scope,
                user_access=user_access,
                policy_rules=policy_rules,
            )
            if (
                not raw_access["allowed"]
                and (
                    user_access is None
                    or user_access.status != UserAccess.Status.PENDING
                )
            ):
                user_access = _set_pending_access_request(
                    user=locked_user,
                    scope=scope,
                    user_access=user_access,
                )
                changed = True
                raw_access = _build_access_payload(
                    user=locked_user,
                    scope=scope,
                    user_access=user_access,
                    policy_rules=policy_rules,
                )
            raw_access_by_key[scope_key] = raw_access

        portal_access = raw_access_by_key.get(ACCESS_SCOPE_PORTAL)
        if requires_portal and portal_access is None:
            raise RuntimeError("Portal 선행 접근 판정이 누락되었습니다.")
        response_accesses: dict[str, dict[str, object]] = {}
        for scope_key in normalized_scope_keys:
            scope = scopes_by_key[scope_key]
            raw_access = raw_access_by_key[scope_key]
            response_accesses[scope_key] = (
                _apply_portal_access_requirement(
                    scope_access=raw_access,
                    portal_access=portal_access,
                )
                if _requires_portal_access(scope=scope)
                else raw_access
            )
        if requires_portal and ACCESS_SCOPE_PORTAL not in normalized_scope_keys:
            response_accesses = {
                ACCESS_SCOPE_PORTAL: portal_access,
                **response_accesses,
            }

    has_pending = any(
        access.get("explicitStatus") == UserAccess.Status.PENDING
        for access in response_accesses.values()
    )
    response_status = "pending" if changed or has_pending else "already_allowed"
    return {"status": response_status, "accesses": response_accesses}, 200


def _grant_default_app_accesses(
    *,
    actor: Any,
    target_user: Any,
    reason: str | None,
) -> None:
    """Portal 승인과 함께 차단되지 않은 활성 앱을 일반 사용자 역할로 허용합니다."""

    for scope in selectors.list_active_app_access_scopes():
        app_access = selectors.get_user_access_for_scope_for_update(
            user=target_user,
            scope=scope,
        )
        if app_access is not None and app_access.status in {
            UserAccess.Status.ALLOWED,
            UserAccess.Status.DENIED,
        }:
            continue

        before = _serialize_user_access(app_access) if app_access else {}
        if app_access is None:
            app_access = UserAccess(
                scope=scope,
                user=target_user,
                department=_get_user_department(user=target_user),
            )
        app_access.department = _get_user_department(user=target_user)
        app_access.status = UserAccess.Status.ALLOWED
        app_access.role = AccessRole.USER
        app_access.decided_by = actor
        app_access.decided_at = timezone.now()
        app_access.reason = None
        app_access.save()
        create_access_audit_log(
            scope=scope,
            actor=actor,
            target_user=target_user,
            policy_rule=None,
            action=AccessAuditLog.Actions.GRANT,
            before=before,
            after=_serialize_user_access(app_access),
            reason=reason,
        )


def get_access_users(
    *,
    actor: Any,
    request: Any | None = None,
    scope_key: str | None,
    status: str | None,
    source: str | None,
    search: str | None,
    department: str | None,
    page: int,
    page_size: int,
) -> tuple[dict[str, object], int]:
    """Portal admin용 전체 사용자 접근 상태 목록을 반환합니다."""

    if not can_manage_access(user=actor, request=request):
        return {"error": "forbidden"}, 403

    scope = selectors.get_access_scope_by_key(scope_key=scope_key or ACCESS_SCOPE_PORTAL)
    if scope is None:
        return {"error": "scope_not_found"}, 404

    user_queryset = selectors.list_access_management_users(search=search, department=department)
    user_queryset = selectors.filter_access_management_users_by_effective_access(
        queryset=user_queryset,
        scope=scope,
        status=status,
        source=source,
    )
    policy_rules = selectors.list_active_access_policy_rules(scope=scope)
    paginator = Paginator(user_queryset, page_size)

    try:
        page_obj = paginator.page(page)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages or 1)

    page_users = list(page_obj.object_list)
    page_rows = _build_effective_access_rows(
        users=page_users,
        scope=scope,
        policy_rules=policy_rules,
    )

    return {
        "scope": _serialize_scope(scope),
        "results": page_rows,
        "pagination": {
            "page": page_obj.number,
            "pageSize": page_size,
            "total": paginator.count,
            "totalPages": paginator.num_pages,
        },
    }, 200


def get_access_matrix(
    *,
    actor: Any,
    request: Any | None = None,
    search: str | None,
    department: str | None,
    page: int,
    page_size: int,
) -> tuple[dict[str, object], int]:
    """Portal admin용 사용자별 전체 scope 접근 권한 매트릭스를 반환합니다."""

    if not can_manage_access(user=actor, request=request):
        return {"error": "forbidden"}, 403

    scopes = selectors.list_managed_access_scopes()
    portal_scope = next(
        (scope for scope in scopes if scope.key == ACCESS_SCOPE_PORTAL),
        None,
    )
    if portal_scope is None:
        return {"error": "scope_not_found"}, 404
    user_queryset = selectors.list_access_management_users(search=search, department=department)
    paginator = Paginator(user_queryset, page_size)
    try:
        page_obj = paginator.page(page)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages or 1)

    users = list(page_obj.object_list)
    policy_rules = selectors.list_active_access_policy_rules_for_scopes(scopes=scopes)
    policy_rules_by_scope: dict[int, list[AccessPolicyRule]] = {scope.id: [] for scope in scopes}
    for rule in policy_rules:
        policy_rules_by_scope.setdefault(rule.scope_id, []).append(rule)

    access_rows = selectors.list_user_access_rows_for_scopes_and_users(
        scopes=scopes,
        user_ids=[user.id for user in users],
    )
    access_by_scope_and_user = {
        (access.scope_id, access.user_id): access
        for access in access_rows
    }

    results = []
    for target_user in users:
        portal_access = _build_access_payload(
            user=target_user,
            scope=portal_scope,
            user_access=access_by_scope_and_user.get((portal_scope.id, target_user.id)),
            policy_rules=policy_rules_by_scope.get(portal_scope.id, []),
        )
        accesses = {portal_scope.key: portal_access}
        for scope in scopes[1:]:
            raw_scope_access = _build_access_payload(
                user=target_user,
                scope=scope,
                user_access=access_by_scope_and_user.get((scope.id, target_user.id)),
                policy_rules=policy_rules_by_scope.get(scope.id, []),
            )
            accesses[scope.key] = _apply_portal_access_requirement(
                scope_access=raw_scope_access,
                portal_access=portal_access,
            )
        results.append({"user": _serialize_access_user(target_user), "accesses": accesses})

    return {
        "scopes": [_serialize_scope(scope) for scope in scopes],
        "results": results,
        "pagination": {
            "page": page_obj.number,
            "pageSize": page_size,
            "total": paginator.count,
            "totalPages": paginator.num_pages,
        },
    }, 200


def decide_user_access(
    *,
    actor: Any,
    request: Any | None = None,
    user_id: int,
    scope_key: str,
    action: str,
    reason: str | None = None,
    role: str | None = None,
    approve_all_apps: bool = False,
) -> tuple[dict[str, object], int]:
    """Portal admin이 특정 사용자의 scope 접근 상태를 변경합니다."""

    if not can_manage_access(user=actor, request=request):
        return {"error": "forbidden"}, 403

    return _decide_user_access(
        actor=actor,
        user_id=user_id,
        scope_key=scope_key,
        action=action,
        reason=reason,
        role=role,
        approve_all_apps=approve_all_apps,
    )


def _decide_user_access(
    *,
    actor: Any,
    user_id: int,
    scope_key: str,
    action: str,
    reason: str | None,
    role: str | None = None,
    approve_all_apps: bool = False,
) -> tuple[dict[str, object], int]:
    """모든 공개 API가 공유하는 사용자 scope 권한 변경을 수행합니다."""

    scope = selectors.get_access_scope_by_key(scope_key=scope_key)
    if scope is None:
        return {"error": "scope_not_found"}, 404

    normalized_action = (action or "").strip().lower()
    normalized_reason = (reason or "").strip()
    role_actions = _GRANT_ACTIONS | {AccessAuditLog.Actions.CHANGE_ROLE}
    if (role or "").strip() and normalized_action not in role_actions:
        return {"error": "role_not_supported_for_action"}, 400
    if approve_all_apps and not (
        scope.key == ACCESS_SCOPE_PORTAL and normalized_action == "approve"
    ):
        return {"error": "approve_all_apps_not_supported"}, 400

    is_reset_action = normalized_action == AccessAuditLog.Actions.RESET_TO_POLICY
    supported_actions = (
        _GRANT_ACTIONS
        | _REVOKE_ACTIONS
        | {
            AccessAuditLog.Actions.CHANGE_ROLE,
            AccessAuditLog.Actions.RESET_TO_POLICY,
        }
    )
    if normalized_action not in supported_actions:
        return {"error": "invalid_action"}, 400

    explicit_role = None
    if normalized_action == AccessAuditLog.Actions.CHANGE_ROLE:
        if not (role or "").strip():
            return {"error": "role_required"}, 400
        explicit_role = _normalize_access_role(role)
        if explicit_role is None:
            return {"error": "invalid_role"}, 400

    with transaction.atomic():
        target_user = selectors.get_user_by_id_for_update(user_id=user_id)
        if target_user is None:
            return {"error": "user_not_found"}, 404
        if target_user.is_superuser:
            return {"error": "immutable_access_bypass"}, 409
        if is_reset_action:
            return _reset_locked_user_access_to_policy(
                actor=actor,
                target_user=target_user,
                scope=scope,
                reason=normalized_reason,
            )

        if normalized_action == AccessAuditLog.Actions.CHANGE_ROLE:
            next_status = UserAccess.Status.ALLOWED
            audit_action = AccessAuditLog.Actions.CHANGE_ROLE
        elif normalized_action in _GRANT_ACTIONS:
            next_status = UserAccess.Status.ALLOWED
            audit_action = (
                AccessAuditLog.Actions.APPROVE
                if normalized_action == "approve"
                else AccessAuditLog.Actions.GRANT
            )
        else:
            next_status = UserAccess.Status.DENIED
            audit_action = (
                AccessAuditLog.Actions.REJECT
                if normalized_action == "reject"
                else AccessAuditLog.Actions.REVOKE
            )

        user_access = selectors.get_user_access_for_scope_for_update(user=target_user, scope=scope)
        if normalized_action in {"approve", "reject"} and (
            user_access is None or user_access.status != UserAccess.Status.PENDING
        ):
            return {
                "error": "invalid_status_transition",
                "currentStatus": user_access.status if user_access else None,
            }, 409

        policy_rules = selectors.list_active_access_policy_rules(
            scope=scope,
            department=_get_user_department(user=target_user),
        )
        if normalized_action == AccessAuditLog.Actions.CHANGE_ROLE:
            current_access = _build_access_payload(
                user=target_user,
                scope=scope,
                user_access=user_access,
                policy_rules=policy_rules,
            )
            if not current_access["allowed"]:
                return {
                    "error": "invalid_status_transition",
                    "currentStatus": current_access["effectiveStatus"],
                }, 409

        before = _serialize_user_access(user_access) if user_access else {}
        if user_access is None:
            user_access = UserAccess(
                scope=scope,
                user=target_user,
                department=_get_user_department(user=target_user),
            )

        if next_status == UserAccess.Status.DENIED:
            # 비허용 행에는 과거 관리자 역할을 남기지 않아 재허용 시 승격되는 일을 막습니다.
            normalized_role = AccessRole.USER
        elif explicit_role is not None:
            normalized_role = explicit_role
        elif (role or "").strip():
            normalized_role = _normalize_access_role(role)
        else:
            # 역할이 없는 승인·부여는 항상 일반 사용자이며 기존 행의 역할을 재사용하지 않습니다.
            normalized_role = AccessRole.USER
        if normalized_role is None:
            return {"error": "invalid_role"}, 400

        user_access.department = _get_user_department(user=target_user)
        user_access.status = next_status
        user_access.role = normalized_role
        user_access.decided_by = actor
        user_access.decided_at = timezone.now()
        user_access.reason = normalized_reason if next_status == UserAccess.Status.DENIED else None
        user_access.save()
        after = _serialize_user_access(user_access)
        create_access_audit_log(
            scope=scope,
            actor=actor,
            target_user=target_user,
            policy_rule=None,
            action=audit_action,
            before=before,
            after=after,
            reason=normalized_reason or None,
        )
        if approve_all_apps:
            _grant_default_app_accesses(
                actor=actor,
                target_user=target_user,
                reason=normalized_reason or None,
            )

    return {
        "status": "ok",
        "row": _serialize_effective_access_user(
            user=target_user,
            scope=scope,
            user_access=user_access,
            policy_rules=policy_rules,
        ),
    }, 200


def get_access_policy_rules(
    *,
    actor: Any,
    request: Any | None = None,
    scope_key: str | None,
) -> tuple[dict[str, object], int]:
    """Portal admin용 접근 정책 규칙 목록을 반환합니다."""

    if not can_manage_access(user=actor, request=request):
        return {"error": "forbidden"}, 403

    return {
        "results": [
            _serialize_access_policy_rule(rule)
            for rule in selectors.list_access_policy_rules(scope_key=scope_key or ACCESS_SCOPE_PORTAL)
        ]
    }, 200


def create_access_policy_rule(
    *,
    actor: Any,
    request: Any | None = None,
    scope_key: str,
    rule_type: str | None,
    value: str | None,
    is_active: bool | None,
) -> tuple[dict[str, object], int]:
    """접근 정책 규칙을 생성합니다."""

    if not can_manage_access(user=actor, request=request):
        return {"error": "forbidden"}, 403

    with transaction.atomic():
        scope = selectors.get_access_scope_by_key_for_update(scope_key=scope_key)
        if scope is None:
            return {"error": "scope_not_found"}, 404

        if rule_type not in AccessPolicyRule.RuleTypes.values:
            return {"error": "invalid_rule_type"}, 400

        rule = AccessPolicyRule(
            scope=scope,
            rule_type=rule_type,
            value=(value or "").strip(),
            is_active=True if is_active is None else bool(is_active),
        )
        validation_error = _clean_policy_rule(rule)
        if validation_error:
            return validation_error, 400

        try:
            # 경쟁 삽입의 IntegrityError가 바깥 트랜잭션을 깨뜨리지 않게 savepoint를 둡니다.
            with transaction.atomic():
                rule.save()
        except IntegrityError:
            return {"error": "duplicate_policy_rule"}, 400

        after = _serialize_access_policy_rule(rule)
        create_access_audit_log(
            scope=rule.scope,
            actor=actor,
            target_user=None,
            policy_rule=rule,
            action=AccessAuditLog.Actions.POLICY_CREATE,
            before={},
            after=after,
            reason=None,
        )

    return {"status": "ok", "policyRule": after}, 201


def update_access_policy_rule(
    *,
    actor: Any,
    request: Any | None = None,
    rule_id: int,
    rule_type: str | None,
    value: str | None,
    is_active: bool | None,
) -> tuple[dict[str, object], int]:
    """접근 정책 규칙을 수정합니다."""

    if not can_manage_access(user=actor, request=request):
        return {"error": "forbidden"}, 403

    with transaction.atomic():
        rule = selectors.get_access_policy_rule_by_id_for_update(rule_id=rule_id)
        if rule is None:
            return {"error": "not_found"}, 404

        before = _serialize_access_policy_rule(rule)
        if rule_type is not None:
            if rule_type not in AccessPolicyRule.RuleTypes.values:
                return {"error": "invalid_rule_type"}, 400
            rule.rule_type = rule_type
        if value is not None:
            rule.value = value.strip()
        if is_active is not None:
            rule.is_active = bool(is_active)

        validation_error = _clean_policy_rule(rule)
        if validation_error:
            return validation_error, 400

        try:
            with transaction.atomic():
                rule.save()
        except IntegrityError:
            return {"error": "duplicate_policy_rule"}, 400

        after = _serialize_access_policy_rule(rule)
        create_access_audit_log(
            scope=rule.scope,
            actor=actor,
            target_user=None,
            policy_rule=rule,
            action=AccessAuditLog.Actions.POLICY_UPDATE,
            before=before,
            after=after,
            reason=None,
        )

    return {"status": "ok", "policyRule": after}, 200


def delete_access_policy_rule(
    *,
    actor: Any,
    request: Any | None = None,
    rule_id: int,
) -> tuple[dict[str, object], int]:
    """접근 정책 규칙을 삭제합니다."""

    if not can_manage_access(user=actor, request=request):
        return {"error": "forbidden"}, 403

    with transaction.atomic():
        rule = selectors.get_access_policy_rule_by_id_for_update(rule_id=rule_id)
        if rule is None:
            return {"error": "not_found"}, 404

        before = _serialize_access_policy_rule(rule)
        scope = rule.scope
        create_access_audit_log(
            scope=scope,
            actor=actor,
            target_user=None,
            policy_rule=rule,
            action=AccessAuditLog.Actions.POLICY_DELETE,
            before=before,
            after={},
            reason=None,
        )
        rule.delete()

    return {"status": "ok"}, 200


def get_access_audit_logs(
    *,
    actor: Any,
    request: Any | None = None,
    scope_key: str | None,
    user_id: int | None,
    action: str | None,
    page: int,
    page_size: int,
) -> tuple[dict[str, object], int]:
    """Portal admin용 접근 권한 감사 로그 목록을 반환합니다."""

    if not can_manage_access(user=actor, request=request):
        return {"error": "forbidden"}, 403

    queryset = selectors.list_access_audit_logs(
        scope_key=scope_key,
        user_id=user_id,
        action=action,
    )
    paginator = Paginator(queryset, page_size)
    try:
        page_obj = paginator.page(page)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages or 1)

    return {
        "results": [_serialize_access_audit_log(row) for row in page_obj.object_list],
        "pagination": {
            "page": page_obj.number,
            "pageSize": page_size,
            "total": paginator.count,
            "totalPages": paginator.num_pages,
        },
    }, 200


def _reset_locked_user_access_to_policy(
    *,
    actor: Any,
    target_user: Any,
    scope: AccessScope,
    reason: str,
) -> tuple[dict[str, object], int]:
    """잠긴 사용자의 명시 접근 row를 제거해 정책 판정 상태로 되돌립니다."""

    user_access = selectors.get_user_access_for_scope_for_update(
        user=target_user,
        scope=scope,
    )
    before = _serialize_user_access(user_access) if user_access else {}
    if user_access is not None:
        user_access.delete()

    policy_rules = selectors.list_active_access_policy_rules(
        scope=scope,
        department=_get_user_department(user=target_user),
    )
    create_access_audit_log(
        scope=scope,
        actor=actor,
        target_user=target_user,
        policy_rule=None,
        action=AccessAuditLog.Actions.RESET_TO_POLICY,
        before=before,
        after={},
        reason=reason or None,
    )

    return {
        "status": "ok",
        "row": _serialize_effective_access_user(
            user=target_user,
            scope=scope,
            user_access=None,
            policy_rules=policy_rules,
        ),
    }, 200


def _build_effective_access_rows(
    *,
    users: list[Any],
    scope: AccessScope,
    policy_rules: list[AccessPolicyRule],
) -> list[dict[str, object]]:
    """페이지 사용자 목록을 최종 접근 상태 행 목록으로 변환합니다."""

    access_rows = selectors.list_user_access_rows_by_scope_and_user_ids(
        scope=scope,
        user_ids=[user.id for user in users],
    )
    access_by_user_id = {row.user_id: row for row in access_rows}
    portal_access_by_user_id = (
        _build_portal_access_payloads_by_user(users=users)
        if _requires_portal_access(scope=scope)
        else {}
    )

    rows: list[dict[str, object]] = []
    for target_user in users:
        row = _serialize_effective_access_user(
            user=target_user,
            scope=scope,
            user_access=access_by_user_id.get(target_user.id),
            policy_rules=policy_rules,
            portal_access=portal_access_by_user_id.get(target_user.id),
        )
        rows.append(row)
    return rows


def _clean_policy_rule(rule: AccessPolicyRule) -> dict[str, object] | None:
    """정책 규칙 모델 검증을 수행하고 오류 payload를 반환합니다."""

    try:
        rule.full_clean()
    except ValidationError as error:
        details = getattr(error, "message_dict", None) or {"__all__": error.messages}
        return {"error": "invalid_policy_rule", "details": details}
    return None


def _serialize_access_policy_rule(rule: AccessPolicyRule) -> dict[str, object]:
    """접근 정책 규칙을 API 응답 형태로 직렬화합니다."""

    return {
        "id": rule.id,
        "scope": rule.scope.key,
        "scopeName": rule.scope.name,
        "ruleType": rule.rule_type,
        "value": rule.value,
        "isActive": rule.is_active,
        "createdAt": rule.created_at.isoformat() if rule.created_at else None,
        "updatedAt": rule.updated_at.isoformat() if rule.updated_at else None,
    }


def create_access_audit_log(
    *,
    scope: AccessScope | None,
    actor: Any,
    target_user: Any | None,
    policy_rule: AccessPolicyRule | None,
    action: str,
    before: dict[str, object],
    after: dict[str, object],
    reason: str | None,
) -> None:
    """접근 권한 변경 감사 로그를 생성합니다."""

    AccessAuditLog.objects.create(
        scope=scope,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        target_user=target_user,
        policy_rule=policy_rule,
        action=action,
        before=_canonicalize_audit_snapshot(action=action, snapshot=before),
        after=_canonicalize_audit_snapshot(action=action, snapshot=after),
        reason=(reason or "").strip() or None,
    )


def _serialize_access_audit_log(row: AccessAuditLog) -> dict[str, object]:
    """접근 권한 감사 로그를 API 응답 형태로 직렬화합니다."""

    policy_rule = row.policy_rule
    policy_snapshot = _get_policy_rule_snapshot(row=row)
    return {
        "id": row.id,
        "scope": getattr(row.scope, "key", None),
        "scopeName": getattr(row.scope, "name", None),
        "action": row.action,
        "reason": row.reason,
        "before": row.before,
        "after": row.after,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "actor": _serialize_access_actor(row.actor),
        "targetUser": _serialize_access_actor(row.target_user),
        "policyRule": policy_snapshot or ({
            "id": policy_rule.id,
            "ruleType": policy_rule.rule_type,
            "value": policy_rule.value,
        } if policy_rule else None),
    }


def _get_policy_rule_snapshot(*, row: AccessAuditLog) -> dict[str, object] | None:
    """삭제된 정책 규칙 정보를 감사 로그 JSON snapshot에서 복원합니다."""

    for snapshot in (row.after, row.before):
        rule_type = snapshot.get("ruleType")
        value = snapshot.get("value")
        if rule_type or value:
            payload = {
                "id": snapshot.get("id"),
                "ruleType": rule_type,
                "value": value,
            }
            return payload
    return None


def _canonicalize_audit_snapshot(
    *,
    action: str,
    snapshot: object,
) -> dict[str, object]:
    """JSON snapshot을 action별 고정 필드로 정규화합니다."""

    if not isinstance(snapshot, dict):
        return {}

    if action in _POLICY_AUDIT_ACTIONS:
        return {
            key: snapshot.get(key)
            for key in ("id", "ruleType", "value", "isActive")
            if key in snapshot
        }
    if action in _SCOPE_AUDIT_ACTIONS:
        return {
            key: snapshot.get(key)
            for key in ("key", "name", "scopeType", "isActive", "requestable")
            if key in snapshot
        }
    explicit_status = snapshot.get("explicitStatus")
    payload: dict[str, object] = {}
    if explicit_status in UserAccess.Status.values:
        payload["explicitStatus"] = explicit_status
    role = _normalize_access_role(snapshot.get("role"))
    if role is not None:
        payload["role"] = role
    return payload


def _serialize_access_actor(user: Any | None) -> dict[str, object] | None:
    """감사 로그 사용자 요약 정보를 직렬화합니다."""

    if user is None:
        return None
    return {
        "id": user.id,
        "knoxId": getattr(user, "knox_id", None),
        "username": getattr(user, "username", None),
        "email": getattr(user, "email", None),
    }
