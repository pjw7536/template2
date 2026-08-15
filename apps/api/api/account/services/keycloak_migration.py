"""legacy Account 권한을 Keycloak group/client role 계획으로 변환합니다."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from api.auth import services as auth_services

from .. import selectors
from ..models import SYSTEM_ACCESS_SCOPE_KEYS
from .access_runtime import get_access_payload


class KeycloakMigrationValidationError(ValueError):
    """누락·중복·비상 계정 오류로 안전한 이관이 불가능할 때 발생합니다."""


def _role_for_current_affiliation(*, user: Any, name: str) -> str:
    """현재 기본 소속의 viewer/member/manager 역할을 반환합니다."""

    roles = selectors.get_accessible_user_sdwt_prod_roles_for_user(user)
    for candidate, role in roles.items():
        if str(candidate).casefold() == name.casefold() and role in {"viewer", "member", "manager"}:
            return str(role)
    return "viewer"


def _client_roles(*, user: Any, emergency: bool) -> list[str]:
    """현재 유효한 Portal·앱 역할만 Keycloak client role 이름으로 변환합니다."""

    roles: list[str] = []
    for scope_key in SYSTEM_ACCESS_SCOPE_KEYS:
        if emergency:
            role = "admin"
            allowed = True
        else:
            access = get_access_payload(user=user, scope_key=scope_key)
            allowed = bool(access.get("allowed"))
            role = str(access.get("role") or "user")
        if not allowed:
            continue
        roles.append(f"{scope_key}-admin" if role == "admin" else f"{scope_key}-user")
    return sorted(set(roles))


def build_legacy_keycloak_plan(*, emergency_sabun: str) -> dict[str, Any]:
    """쓰기 없이 legacy DB의 현재 유효 권한을 deterministic 이관 계획으로 만듭니다."""

    normalized_emergency = str(emergency_sabun or "").strip()
    if not normalized_emergency:
        raise KeycloakMigrationValidationError("비상 계정 사번이 필요합니다.")

    users: list[dict[str, Any]] = []
    errors: list[str] = []
    seen_usernames: set[str] = set()
    seen_emails: set[str] = set()
    emergency_count = 0
    for user in selectors.list_active_users_for_keycloak_migration():
        sabun = str(getattr(user, "sabun", "") or "").strip()
        username = str(getattr(user, "knox_id", "") or "").strip()
        email = str(getattr(user, "email", "") or "").strip().casefold()
        current = getattr(user, "current_affiliation", None)
        affiliation = getattr(current, "affiliation", None)
        name = str(getattr(affiliation, "user_sdwt_prod", "") or "").strip()
        identity_key = username.casefold()
        if not sabun or not username or not email or not name:
            errors.append(f"필수 사용자/소속 값 누락: user_id={user.id}")
            continue
        if identity_key in seen_usernames:
            errors.append(f"중복 username: {username}")
            continue
        if email in seen_emails:
            errors.append(f"중복 email: {email}")
            continue
        seen_usernames.add(identity_key)
        seen_emails.add(email)
        emergency = sabun == normalized_emergency
        emergency_count += int(emergency)
        affiliation_role = "manager" if emergency else _role_for_current_affiliation(
            user=user,
            name=name,
        )
        users.append(
            {
                "legacy_user_id": user.id,
                "sabun": sabun,
                "username": username,
                "email": email,
                "first_name": str(getattr(user, "first_name", "") or ""),
                "last_name": str(getattr(user, "last_name", "") or ""),
                "affiliation_name": name,
                "affiliation_role": affiliation_role,
                "group_path": f"/affiliations/{name}/{affiliation_role}",
                "client_roles": _client_roles(user=user, emergency=emergency),
                "emergency": emergency,
            }
        )
    if emergency_count != 1:
        errors.append("비상 계정은 활성 사용자 중 정확히 한 명이어야 합니다.")
    if errors:
        raise KeycloakMigrationValidationError("; ".join(errors))
    canonical = json.dumps(users, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "version": 1,
        "users": users,
        "user_count": len(users),
        "checksum": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "omitted": ["pending", "denied", "expired_grants", "additional_data_scopes", "audit_history"],
    }


def apply_keycloak_plan(*, plan: dict[str, Any]) -> dict[str, int]:
    """검증된 이관 계획을 Keycloak에 멱등 반영합니다."""

    client = auth_services.KeycloakProvisioningClient.from_settings()
    applied = 0
    for item in plan.get("users", []):
        parent_path = f"/affiliations/{item['affiliation_name']}"
        parent_group_id = client.resolve_group_id(path=parent_path)
        user_id = client.ensure_user(
            user={**item, "affiliation_group_id": parent_group_id}
        )
        client.replace_affiliation_group(
            user_id=user_id,
            group_path=item["group_path"],
        )
        client.replace_client_roles(
            user_id=user_id,
            client_id="portal",
            roles=item["client_roles"],
        )
        applied += 1
    return {"applied": applied}


def compare_keycloak_plan(*, plan: dict[str, Any]) -> dict[str, Any]:
    """legacy 이관 계획과 Keycloak 실상태의 누락·초과를 비교합니다."""

    client = auth_services.KeycloakProvisioningClient.from_settings()
    mismatches: list[dict[str, Any]] = []
    for item in plan.get("users", []):
        state = client.get_user_state(username=item["username"], client_id="portal")
        expected_groups = [item["group_path"]]
        expected_roles = sorted(item["client_roles"])
        actual_affiliation_groups = [
            path for path in state["groups"] if path.startswith("/affiliations/")
        ]
        if actual_affiliation_groups != expected_groups or state["client_roles"] != expected_roles:
            mismatches.append(
                {
                    "username": item["username"],
                    "expected_groups": expected_groups,
                    "actual_groups": actual_affiliation_groups,
                    "expected_roles": expected_roles,
                    "actual_roles": state["client_roles"],
                }
            )
    return {"matched": not mismatches, "mismatches": mismatches}
