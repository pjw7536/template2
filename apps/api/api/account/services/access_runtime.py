# =============================================================================
# 모듈 설명: scope 접근 상태를 조회하고 최종 권한 payload로 판정합니다.
# - 주요 대상: 요청 단위 역할 resolver, 정책 판정, 접근 상태 직렬화
# - 불변 조건: 이 모듈은 접근 권한 모델을 변경하지 않습니다.
# =============================================================================

"""scope 기반 접근 권한의 읽기 전용 런타임 판정 서비스입니다."""

from __future__ import annotations

from typing import Any

from .. import selectors
from ..models import (
    ACCESS_SCOPE_PORTAL,
    AccessPolicyRule,
    AccessRole,
    AccessScope,
    AccessSource,
    UserAccess,
)


_SCOPE_ROLE_RESOLVER_CACHE_ATTRIBUTE = "_account_scope_role_resolvers"


def _requires_portal_access(*, scope: AccessScope) -> bool:
    """canonical Portal key 이외의 모든 scope가 Portal 접근을 선행 조건으로 사용하는지 반환합니다."""

    return scope.key != ACCESS_SCOPE_PORTAL


class _ScopeRoleResolver:
    """한 사용자의 전체 scope 역할을 일괄 조회하고 메모리에서 판정합니다."""

    def __init__(self, *, user: Any) -> None:
        """scope, 정책, 명시 권한을 각각 한 번씩 조회합니다."""

        self.user = user
        department = _get_user_department(user=user)
        self.scopes = selectors.list_access_scopes()
        self.scopes_by_key = {scope.key: scope for scope in self.scopes}
        policy_rules = selectors.list_active_access_policy_rules_for_scopes(
            scopes=self.scopes,
            department=department,
        )
        self.policy_rules_by_scope: dict[int, list[AccessPolicyRule]] = {
            scope.id: [] for scope in self.scopes
        }
        for rule in policy_rules:
            self.policy_rules_by_scope.setdefault(rule.scope_id, []).append(rule)

        access_rows = selectors.list_user_access_rows_for_scopes_and_users(
            scopes=self.scopes,
            user_ids=[getattr(user, "id", 0)],
        )
        self.access_by_scope_id = {
            access.scope_id: access for access in access_rows
        }
        self.payload_by_scope_key: dict[str, dict[str, object]] = {}

    def get_payload(self, *, scope_key: str) -> dict[str, object]:
        """scope별 최종 접근 payload를 요청 생명주기 동안 재사용합니다."""

        cached = self.payload_by_scope_key.get(scope_key)
        if cached is not None:
            return cached

        scope = self.scopes_by_key.get(scope_key)
        if scope is None:
            payload = _build_missing_scope_payload(
                user=self.user,
                scope_key=scope_key,
            )
        else:
            payload = _build_access_payload(
                user=self.user,
                scope=scope,
                user_access=self.access_by_scope_id.get(scope.id),
                policy_rules=self.policy_rules_by_scope.get(scope.id, []),
            )
            if _requires_portal_access(scope=scope):
                payload = _apply_portal_access_requirement(
                    scope_access=payload,
                    portal_access=self.get_payload(scope_key=ACCESS_SCOPE_PORTAL),
                )

        self.payload_by_scope_key[scope_key] = payload
        return payload


def _get_scope_role_resolver(*, user: Any, request: Any | None) -> _ScopeRoleResolver:
    """요청이 있으면 사용자별 resolver를 요청 객체에 캐시해 반환합니다."""

    if request is None:
        return _ScopeRoleResolver(user=user)

    base_request = getattr(request, "_request", request)
    cached = getattr(base_request, _SCOPE_ROLE_RESOLVER_CACHE_ATTRIBUTE, None)
    if not isinstance(cached, dict):
        cached = {}
        setattr(base_request, _SCOPE_ROLE_RESOLVER_CACHE_ATTRIBUTE, cached)

    user_key = getattr(user, "pk", None) or id(user)
    resolver = cached.get(user_key)
    if not isinstance(resolver, _ScopeRoleResolver):
        resolver = _ScopeRoleResolver(user=user)
        cached[user_key] = resolver
    return resolver


def can_manage_access(*, user: Any, request: Any | None = None) -> bool:
    """사용자가 Portal 전역 접근 권한을 관리할 수 있는지 확인합니다."""

    return has_scope_role(
        user=user,
        scope_key=ACCESS_SCOPE_PORTAL,
        required_role=AccessRole.ADMIN,
        request=request,
    )


def has_scope_role(
    *,
    user: Any,
    scope_key: str,
    required_role: str = AccessRole.ADMIN,
    request: Any | None = None,
) -> bool:
    """Portal 접근을 포함해 특정 scope의 유효 역할을 일괄 조회 결과로 판정합니다."""

    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    normalized_role = _normalize_access_role(required_role)
    if normalized_role is None:
        return False

    access_payload = _get_scope_role_resolver(
        user=user,
        request=request,
    ).get_payload(scope_key=scope_key)
    return bool(
        access_payload.get("allowed")
        and access_payload.get("role") == normalized_role
    )


def get_access_payload(
    *,
    user: Any,
    scope_key: str = ACCESS_SCOPE_PORTAL,
    request: Any | None = None,
) -> dict[str, object]:
    """현재 사용자의 scope 접근 상태를 Portal 우선순위와 함께 반환합니다."""

    if request is not None:
        resolver = _get_scope_role_resolver(user=user, request=request)
        return dict(resolver.get_payload(scope_key=scope_key))

    scope = selectors.get_access_scope_by_key(scope_key=scope_key)
    if scope is None:
        return _build_missing_scope_payload(
            user=user,
            scope_key=scope_key,
        )

    user_access = selectors.get_user_access_for_scope(user=user, scope=scope)
    policy_rules = selectors.list_active_access_policy_rules(
        scope=scope,
        department=_get_user_department(user=user),
    )
    payload = _build_access_payload(
        user=user,
        scope=scope,
        user_access=user_access,
        policy_rules=policy_rules,
    )
    if not _requires_portal_access(scope=scope):
        return payload

    resolved_portal_access = get_access_payload(
        user=user,
        scope_key=ACCESS_SCOPE_PORTAL,
    )
    return _apply_portal_access_requirement(
        scope_access=payload,
        portal_access=resolved_portal_access,
    )


def get_scope_access_payloads(
    *,
    user: Any,
) -> dict[str, dict[str, object]]:
    """현재 사용자에게 노출할 scope의 최종 접근 상태를 한 map으로 반환합니다."""

    resolver = _ScopeRoleResolver(user=user)
    include_inactive_scopes = _has_access_bypass(user=user)
    non_portal_scopes = sorted(
        (
            scope
            for scope in resolver.scopes
            if scope.key != ACCESS_SCOPE_PORTAL
            and (scope.is_active or include_inactive_scopes)
        ),
        key=lambda scope: (scope.name, scope.key),
    )
    scope_keys = [
        ACCESS_SCOPE_PORTAL,
        *(scope.key for scope in non_portal_scopes),
    ]
    return {
        scope_key: dict(resolver.get_payload(scope_key=scope_key))
        for scope_key in scope_keys
    }


def list_effective_affiliation_member_roles_for_scope(
    *,
    user_sdwt_prod: str,
    scope_key: str,
) -> list[dict[str, str]]:
    """소속 역할 중 지정 scope의 최종 접근이 허용된 사용자만 반환합니다."""

    affiliation = selectors.get_active_affiliation_by_user_sdwt_prod(
        user_sdwt_prod=user_sdwt_prod
    )
    if affiliation is None:
        return []
    scope = selectors.get_access_scope_by_key(scope_key=scope_key)
    if scope is None or scope.data_scope_type != AccessScope.DataScopeTypes.AFFILIATION:
        return []
    memberships = selectors.list_effective_affiliation_member_role_users(
        user_sdwt_prod=user_sdwt_prod
    )
    memberships_by_user_id = {
        int(item["user_id"]): item for item in memberships
    }
    users = selectors.list_active_acl_projection_users(
        user_ids=[int(item["user_id"]) for item in memberships]
    )
    if not users:
        return []
    portal_scope = selectors.get_access_scope_by_key(scope_key=ACCESS_SCOPE_PORTAL)
    access_scopes = [scope]
    if portal_scope is not None and portal_scope.id != scope.id:
        access_scopes.append(portal_scope)
    policy_rules = selectors.list_active_access_policy_rules_for_scopes(
        scopes=access_scopes,
    )
    rules_by_scope_id: dict[int, list[AccessPolicyRule]] = {
        access_scope.id: [] for access_scope in access_scopes
    }
    for rule in policy_rules:
        rules_by_scope_id.setdefault(rule.scope_id, []).append(rule)
    access_rows = selectors.list_user_access_rows_for_scopes_and_users(
        scopes=access_scopes,
        user_ids=[user.id for user in users],
    )
    access_by_scope_and_user = {
        (access.scope_id, access.user_id): access for access in access_rows
    }
    granted_user_ids = selectors.list_active_scope_affiliation_grant_user_ids(
        scope=scope,
        affiliation_id=affiliation.id,
        user_ids=[user.id for user in users],
    )
    role_priority = {"viewer": 1, "member": 2, "manager": 3}
    roles_by_email: dict[str, str] = {}

    for user in users:
        membership = memberships_by_user_id.get(user.id)
        if membership is None and not getattr(user, "is_superuser", False):
            continue
        scope_access = _build_access_payload(
            user=user,
            scope=scope,
            user_access=access_by_scope_and_user.get((scope.id, user.id)),
            policy_rules=rules_by_scope_id.get(scope.id, []),
        )
        portal_access = (
            _build_access_payload(
                user=user,
                scope=portal_scope,
                user_access=access_by_scope_and_user.get((portal_scope.id, user.id)),
                policy_rules=rules_by_scope_id.get(portal_scope.id, []),
            )
            if portal_scope is not None
            else _build_missing_scope_payload(
                user=user,
                scope_key=ACCESS_SCOPE_PORTAL,
            )
        )
        scope_access = _apply_portal_access_requirement(
            scope_access=scope_access,
            portal_access=portal_access,
        )
        if not scope_access.get("allowed"):
            continue

        current = getattr(user, "current_affiliation", None)
        current_affiliation = getattr(current, "affiliation", None)
        has_affiliation_scope = bool(
            getattr(user, "is_superuser", False)
            or scope_access.get("dataScopeMode") == UserAccess.DataScopeModes.ALL
            or (
                scope.include_current_affiliation
                and current_affiliation is not None
                and current_affiliation.is_active
                and current_affiliation.id == affiliation.id
            )
            or user.id in granted_user_ids
        )
        if not has_affiliation_scope:
            continue
        email = (
            str(user.email).strip().lower()
            if getattr(user, "is_superuser", False)
            else str(membership["email"])
        )
        role = (
            "manager"
            if getattr(user, "is_superuser", False)
            else str(membership["role"])
        )
        previous = roles_by_email.get(email)
        if previous is None or role_priority[role] > role_priority[previous]:
            roles_by_email[email] = role
    return [
        {"email": email, "role": roles_by_email[email]}
        for email in sorted(roles_by_email)
    ]


def _build_portal_access_payloads_by_user(
    *,
    users: list[Any],
) -> dict[int, dict[str, object]]:
    """여러 사용자의 Portal 판정을 일괄 조회해 사용자 ID별로 반환합니다."""

    if not users:
        return {}

    portal_scope = selectors.get_access_scope_by_key(scope_key=ACCESS_SCOPE_PORTAL)
    if portal_scope is None:
        return {
            user.id: _build_missing_scope_payload(
                user=user,
                scope_key=ACCESS_SCOPE_PORTAL,
            )
            for user in users
        }

    policy_rules = selectors.list_active_access_policy_rules(scope=portal_scope)
    access_rows = selectors.list_user_access_rows_for_scopes_and_users(
        scopes=[portal_scope],
        user_ids=[user.id for user in users],
    )
    access_by_user_id = {access.user_id: access for access in access_rows}
    return {
        user.id: _build_access_payload(
            user=user,
            scope=portal_scope,
            user_access=access_by_user_id.get(user.id),
            policy_rules=policy_rules,
        )
        for user in users
    }


def _build_missing_scope_payload(
    *,
    user: Any,
    scope_key: str,
) -> dict[str, object]:
    """존재하지 않는 scope의 fail-closed 접근 payload를 생성합니다."""

    department = _get_user_department(user=user)
    can_bypass = _has_access_bypass(user=user)
    return {
        "allowed": can_bypass,
        "scope": scope_key,
        "scopeType": None,
        "reason": (
            AccessSource.SUPERUSER_BYPASS
            if can_bypass
            else AccessSource.SCOPE_NOT_FOUND
        ),
        "department": department,
        "role": AccessRole.ADMIN if can_bypass else None,
        "requestedAt": None,
        "decidedAt": None,
        "rejectionReason": None,
        "canRequest": False,
        "effectiveStatus": "allowed" if can_bypass else "inactive",
        "explicitStatus": None,
        "source": (
            AccessSource.SUPERUSER_BYPASS
            if can_bypass
            else AccessSource.SCOPE_NOT_FOUND
        ),
        "policy": None,
    }


def _apply_portal_access_requirement(
    *,
    scope_access: dict[str, object],
    portal_access: dict[str, object],
) -> dict[str, object]:
    """Portal 차단을 비-Portal scope 판정보다 우선하고 원래 판정을 보존합니다."""

    if portal_access.get("allowed"):
        return {
            **scope_access,
            "blockedByPortal": False,
            "underlyingAccess": None,
        }

    underlying_access = {
        "allowed": bool(scope_access.get("allowed")),
        "reason": scope_access.get("reason"),
        "effectiveStatus": scope_access.get("effectiveStatus"),
        "source": scope_access.get("source"),
    }
    return {
        **scope_access,
        "allowed": False,
        "reason": AccessSource.PORTAL_ACCESS_REQUIRED,
        "effectiveStatus": "denied",
        "source": AccessSource.PORTAL_ACCESS_REQUIRED,
        "blockedByPortal": True,
        "underlyingAccess": underlying_access,
    }


def _build_access_payload(
    *,
    user: Any,
    scope: AccessScope,
    user_access: UserAccess | None,
    policy_rules: list[AccessPolicyRule],
) -> dict[str, object]:
    """사용자 접근 row와 정책 규칙을 합쳐 최종 접근 상태를 계산합니다."""

    department = _get_user_department(user=user)
    can_bypass = _has_access_bypass(user=user)
    policy_result = _evaluate_policy_rules(
        user=user,
        scope=scope,
        rules=policy_rules,
    )
    policy_allowed = policy_result["allowed"]
    status = user_access.status if user_access else None
    role = (
        user_access.role
        if user_access and user_access.status == UserAccess.Status.ALLOWED
        else AccessRole.USER
    )

    if can_bypass:
        allowed = True
        reason = AccessSource.SUPERUSER_BYPASS
        role = AccessRole.ADMIN
        source = AccessSource.SUPERUSER_BYPASS
        effective_status = "allowed"
    elif not scope.is_active:
        allowed = False
        reason = "scope_inactive"
        source = AccessSource.SCOPE_INACTIVE
        effective_status = "inactive"
    elif status == UserAccess.Status.DENIED:
        allowed = False
        reason = "denied"
        source = AccessSource.EXPLICIT_DENIED
        effective_status = "denied"
    elif status == UserAccess.Status.ALLOWED:
        allowed = True
        reason = "allowed"
        source = AccessSource.EXPLICIT_ALLOWED
        effective_status = "allowed"
    elif status == UserAccess.Status.PENDING:
        allowed = False
        reason = "pending"
        source = AccessSource.EXPLICIT_PENDING
        effective_status = "pending"
    elif policy_allowed:
        allowed = True
        reason = policy_result["reason"]
        source = policy_result["source"]
        effective_status = "allowed"
    else:
        allowed = False
        reason = "not_requested"
        source = AccessSource.NONE
        effective_status = "not_requested"

    return {
        "allowed": allowed,
        "scope": scope.key,
        "scopeType": scope.scope_type,
        "dataScopeType": scope.data_scope_type,
        "includeCurrentAffiliation": scope.include_current_affiliation,
        "dataScopeMode": (
            user_access.data_scope_mode
            if user_access and user_access.status == UserAccess.Status.ALLOWED
            else UserAccess.DataScopeModes.DEFAULT
        ),
        "reason": reason,
        "department": department,
        "requestedAt": user_access.requested_at.isoformat() if user_access else None,
        "decidedAt": (
            user_access.decided_at.isoformat()
            if user_access and user_access.decided_at
            else None
        ),
        "rejectionReason": (
            user_access.reason
            if user_access and status == UserAccess.Status.DENIED
            else None
        ),
        "effectiveStatus": effective_status,
        "explicitStatus": status,
        "source": source,
        "policy": _serialize_policy_match(policy_result),
        "role": role,
        "canRequest": bool(
            getattr(user, "is_authenticated", False)
            and scope.is_active
            and scope.requestable
            and not allowed
            and status != UserAccess.Status.PENDING
        ),
    }


def _evaluate_policy_rules(
    *,
    user: Any,
    scope: AccessScope,
    rules: list[AccessPolicyRule] | None = None,
) -> dict[str, object]:
    """사용자 부서와 scope의 활성 부서 규칙을 비교합니다."""

    department = _get_user_department(user=user)
    policy_rules = (
        rules
        if rules is not None
        else selectors.list_active_access_policy_rules(
            scope=scope,
            department=department,
        )
    )
    normalized_department = getattr(user, "_access_department", None)
    if not isinstance(normalized_department, str):
        normalized_department = next(
            (
                getattr(rule, "_access_department", None)
                for rule in policy_rules
                if isinstance(getattr(rule, "_access_department", None), str)
            ),
            None,
        )
    for rule in policy_rules:
        if rule.rule_type != AccessPolicyRule.RuleTypes.DEPARTMENT:
            continue
        normalized_policy_value = getattr(rule, "_access_policy_value", None)
        # annotation이 없으면 Python locale 규칙으로 우회하지 않고 안전하게 불일치 처리합니다.
        if (
            department
            and isinstance(normalized_department, str)
            and isinstance(normalized_policy_value, str)
            and normalized_department == normalized_policy_value
        ):
            return {
                "allowed": True,
                "reason": "department_allowed",
                "source": AccessSource.POLICY_DEPARTMENT,
                "rule": rule,
            }

    return {
        "allowed": False,
        "reason": "not_requested",
        "source": AccessSource.NONE,
        "rule": None,
    }


def _serialize_policy_match(
    policy_result: dict[str, object],
) -> dict[str, object]:
    """정책 매칭 결과를 API 응답 형태로 직렬화합니다."""

    rule = policy_result.get("rule")
    return {
        "matched": bool(policy_result.get("allowed")),
        "reason": policy_result.get("reason"),
        "source": policy_result.get("source"),
        "ruleId": rule.id if isinstance(rule, AccessPolicyRule) else None,
        "ruleType": (
            rule.rule_type if isinstance(rule, AccessPolicyRule) else None
        ),
        "value": rule.value if isinstance(rule, AccessPolicyRule) else None,
    }


def _serialize_scope(scope: AccessScope) -> dict[str, object]:
    """접근 scope를 API 응답 형태로 직렬화합니다."""

    return {
        "key": scope.key,
        "name": scope.name,
        "scopeType": scope.scope_type,
        "dataScopeType": scope.data_scope_type,
        "includeCurrentAffiliation": scope.include_current_affiliation,
        "isActive": scope.is_active,
        "requestable": scope.requestable,
    }


def _serialize_effective_access_user(
    *,
    user: Any,
    scope: AccessScope,
    user_access: UserAccess | None,
    policy_rules: list[AccessPolicyRule],
    portal_access: dict[str, object] | None = None,
) -> dict[str, object]:
    """사용자와 최종 접근 상태를 한 행으로 직렬화합니다."""

    access = _build_access_payload(
        user=user,
        scope=scope,
        user_access=user_access,
        policy_rules=policy_rules,
    )
    if _requires_portal_access(scope=scope):
        resolved_portal_access = (
            portal_access
            if portal_access is not None
            else get_access_payload(
                user=user,
                scope_key=ACCESS_SCOPE_PORTAL,
            )
        )
        access = _apply_portal_access_requirement(
            scope_access=access,
            portal_access=resolved_portal_access,
        )
    return {
        "user": _serialize_access_user(user),
        "access": access,
    }


def _serialize_access_user(user: Any) -> dict[str, object]:
    """권한 관리 화면 사용자 정보를 직렬화합니다."""

    current_affiliation = getattr(user, "current_affiliation", None)
    affiliation = getattr(current_affiliation, "affiliation", None)
    if affiliation is not None and not affiliation.is_active:
        affiliation = None
    display_name = (
        getattr(user, "username", None)
        or getattr(user, "username_en", None)
        or getattr(user, "givenname", None)
        or getattr(user, "knox_id", None)
        or getattr(user, "sabun", None)
        or ""
    )
    return {
        "id": user.id,
        "username": getattr(user, "username", None) or "",
        "displayName": display_name,
        "sabun": getattr(user, "sabun", None) or "",
        "knoxId": getattr(user, "knox_id", None) or "",
        "email": getattr(user, "email", None) or "",
        "department": _get_user_department(user=user),
        "userSdwtProd": getattr(affiliation, "user_sdwt_prod", "") or "",
        "isSuperuser": bool(getattr(user, "is_superuser", False)),
    }


def _serialize_user_access(user_access: UserAccess) -> dict[str, object]:
    """사용자 접근 행의 감사용 canonical 상태를 반환합니다."""

    return {
        "explicitStatus": user_access.status,
        "role": user_access.role,
        "dataScopeMode": user_access.data_scope_mode,
    }


def _get_user_department(*, user: Any) -> str:
    """포털 정책 판정에 사용할 사용자 부서를 반환합니다."""

    department = (getattr(user, "department", None) or "").strip()
    if department:
        return department
    current_affiliation = getattr(user, "current_affiliation", None)
    affiliation = getattr(current_affiliation, "affiliation", None)
    if affiliation is not None and not affiliation.is_active:
        affiliation = None
    return (getattr(affiliation, "department", None) or "").strip()


def _has_access_bypass(*, user: Any) -> bool:
    """사용자가 portal/app 접근 제한을 우회할 수 있는지 확인합니다."""

    return bool(
        user
        and getattr(user, "is_authenticated", False)
        and getattr(user, "is_superuser", False)
    )


def _normalize_access_role(role: str | None) -> str | None:
    """접근 role 값을 정규화합니다."""

    if not isinstance(role, str):
        return None
    normalized = role.strip().lower()
    if normalized in AccessRole.values:
        return normalized
    return None
