"""검증된 Keycloak 로그인 snapshot으로 앱·SDWT 권한을 판정합니다.

DB 권한과 Django 관리자 플래그는 사용하지 않습니다. context는 요청 생명주기에만
사용자 객체에 연결하며, DB에서 재조회한 사용자에게는 명시적으로 전달해야 합니다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.conf import settings

from .. import selectors

AUTHORIZATION_SESSION_KEY = "portal_authorization"
CONTEXT_ATTRIBUTE = "_portal_authorization_context"
ADMIN_SCOPES = frozenset({"access-stats", "appstore", "emails", "l3-spider", "line-dashboard", "voc"})
ROLE_RANK = {"viewer": 1, "user": 2, "admin": 3}


@dataclass(frozen=True)
class AuthorizationContext:
    """한 로그인 세션에 고정된 신원·앱 역할·SDWT 등급입니다."""

    epid: str = ""
    roles: frozenset[str] = frozenset()
    sdwt_roles: tuple[tuple[str, str], ...] = ()
    department: str = ""
    user_sdwt_prod: str = ""
    line: str = ""

    @property
    def portal_admin(self) -> bool:
        """Portal 전용 전체 관리자 역할만 확인합니다."""
        return "portal-admin" in self.roles

    @property
    def all_apps(self) -> bool:
        """조직 정보와 무관하게 전체 앱 사용 역할을 확인합니다."""
        return self.portal_admin or "portal-all-apps" in self.roles


def build_authorization_snapshot(claims: dict[str, Any]) -> dict[str, Any]:
    """검증한 토큰을 JSON 세션 값으로 정규화합니다. 자료형 오류는 ValueError입니다."""
    resources = claims.get("resource_access", {})
    if not isinstance(resources, dict):
        raise ValueError("invalid_roles")
    resource = resources.get(settings.OIDC_CLIENT_ID, {})
    if not isinstance(resource, dict):
        raise ValueError("invalid_roles")
    roles = resource.get("roles", [])
    groups = claims.get("groups", [])
    if any(not isinstance(values, list) or any(not isinstance(v, str) for v in values)
           for values in (roles, groups)):
        raise ValueError("invalid_authorization_claims")
    identity = {}
    for key in ("userid", "deptid", "deptname", "user_sdwt_prod", "line_id"):
        value = claims.get(key, "")
        if not isinstance(value, str):
            raise ValueError("invalid_identity_claims")
        identity[key] = value.strip()
    sdwts: dict[str, str] = {}
    for group in groups:
        parts = group.split("/")
        if len(parts) != 3 or parts[0] or not parts[1] or parts[1] != parts[1].strip():
            continue
        sdwt, role = parts[1:]
        if role in ROLE_RANK and ROLE_RANK[role] > ROLE_RANK.get(sdwts.get(sdwt), 0):
            sdwts[sdwt] = role
    return {
        "version": 1, "epid": identity["userid"], "roles": sorted(set(roles)),
        "sdwtRoles": sdwts,
        "department": identity["deptname"], "userSdwtProd": identity["user_sdwt_prod"],
        "line": identity["line_id"],
    }


def authorization_context(snapshot: Any) -> AuthorizationContext:
    """서버 세션 snapshot을 불변 context로 복원하며 잘못된 값은 권한 없음으로 처리합니다."""
    if not isinstance(snapshot, dict) or snapshot.get("version") != 1:
        return AuthorizationContext()
    try:
        roles = snapshot["roles"]
        sdwts = snapshot["sdwtRoles"]
        if not isinstance(roles, list) or any(not isinstance(r, str) for r in roles):
            return AuthorizationContext()
        if not isinstance(sdwts, dict) or any(not isinstance(k, str) or v not in ROLE_RANK for k, v in sdwts.items()):
            return AuthorizationContext()
        if any(not isinstance(snapshot[k], str) for k in ("epid", "department", "userSdwtProd", "line")):
            return AuthorizationContext()
        return AuthorizationContext(
            epid=snapshot["epid"], roles=frozenset(roles), sdwt_roles=tuple(sdwts.items()),
            department=snapshot["department"],
            user_sdwt_prod=snapshot["userSdwtProd"], line=snapshot["line"],
        )
    except (KeyError, TypeError, ValueError):
        return AuthorizationContext()


def get_authorization_context(*, user: Any, context: AuthorizationContext | None = None) -> AuthorizationContext:
    """요청 사용자에 바인딩된 context만 반환합니다. 사용자 식별자가 다르면 거부합니다."""
    candidate = context if context is not None else getattr(user, CONTEXT_ATTRIBUTE, None)
    if (not getattr(user, "is_authenticated", False) or not getattr(user, "is_active", False)
            or not isinstance(candidate, AuthorizationContext) or not candidate.epid
            or candidate.epid != getattr(user, "avatarid", None)):
        return AuthorizationContext()
    return candidate


def bind_authorization_context(*, user: Any, snapshot: Any) -> None:
    """서버가 검증한 세션 값을 요청 전용 사용자에 연결합니다. DB에는 저장하지 않습니다."""
    setattr(user, CONTEXT_ATTRIBUTE, authorization_context(snapshot))


def keycloak_access_payload(*, user: Any, scope_key: str, context: AuthorizationContext | None = None) -> dict[str, Any]:
    """활성 앱 카탈로그와 세션 역할로 기존 접근 payload 계약을 계산합니다."""
    ctx = get_authorization_context(user=user, context=context)
    scopes = selectors.list_access_scopes()
    scope = next((s for s in scopes if s.key == scope_key), None)
    active = {s.key for s in scopes if s.is_active and s.key != "portal"}
    all_apps = bool(ctx.epid and (ctx.all_apps))
    portal_allowed = all_apps or any(f"{key}-{role}" in ctx.roles for key in active for role in (("user", "admin") if key in ADMIN_SCOPES else ("user",)))
    admin = bool(ctx.epid and (ctx.portal_admin or (scope_key in ADMIN_SCOPES and f"{scope_key}-admin" in ctx.roles)))
    allowed = bool(scope and scope.is_active and portal_allowed and (
        scope_key == "portal" or all_apps or admin or f"{scope_key}-user" in ctx.roles))
    return {
        "allowed": allowed, "scope": scope_key, "scopeType": getattr(scope, "scope_type", None),
        "dataScopeType": getattr(scope, "data_scope_type", None), "includeCurrentAffiliation": False,
        "dataScopeMode": "all" if ctx.portal_admin else "default",
        "role": ("admin" if admin else "user") if allowed else None,
        "reason": "keycloak" if allowed else "scope_access_required", "source": "keycloak",
        "department": ctx.department, "canRequest": False, "requestedAt": None, "decidedAt": None,
        "rejectionReason": None, "effectiveStatus": "allowed" if allowed else "denied",
        "explicitStatus": None, "policy": None,
    }


def keycloak_data_scope(*, user: Any, scope_key: str, context: AuthorizationContext | None = None) -> dict[str, Any]:
    """조직 테이블 없이 SDWT 이름과 전체 범위 여부를 반환합니다."""
    ctx = get_authorization_context(user=user, context=context)
    access = keycloak_access_payload(user=user, scope_key=scope_key, context=ctx)
    allowed = access["allowed"]
    values = sorted(dict(ctx.sdwt_roles)) if allowed else []
    return {
        "allowed": allowed, "scope": scope_key, "type": "affiliation",
        "mode": "all" if allowed and ctx.portal_admin else "selected" if allowed else "denied",
        "all": bool(allowed and ctx.portal_admin), "userSdwtProds": values,
        "affiliations": [{"userSdwtProd": v, "line": ctx.line if v == ctx.user_sdwt_prod else None,
                          "role": dict(ctx.sdwt_roles)[v], "source": "keycloak"} for v in values],
    }


def has_sdwt_capability(*, user: Any, user_sdwt_prod: str, capability: str,
                        context: AuthorizationContext | None = None) -> bool:
    """SDWT 문자열에 대한 조회·수정·삭제 등급을 검사합니다."""
    ctx = get_authorization_context(user=user, context=context)
    required = {"read": 1, "write": 2, "delete": 3}.get(capability)
    if not required or not isinstance(user_sdwt_prod, str) or not user_sdwt_prod:
        return False
    return ctx.portal_admin or ROLE_RANK.get(dict(ctx.sdwt_roles).get(user_sdwt_prod), 0) >= required
