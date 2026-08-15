# =============================================================================
# 모듈 설명: auth 도메인 읽기 전용 셀렉터를 제공합니다.
# - 주요 대상: 사용자 조회, 현재 사용자 응답 payload 조립
# - 불변 조건: 모든 조회는 부작용 없이 수행합니다.
# =============================================================================

"""auth 도메인 읽기 전용 셀렉터 모음.

- 주요 대상: 사용자 조회, 현재 사용자 응답 payload 조립
- 주요 엔드포인트/클래스: 없음(셀렉터 함수만 제공)
- 가정/불변 조건: 읽기 전용 ORM 접근만 수행함
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from django.contrib.auth import get_user_model
from django.contrib.auth.base_user import AbstractBaseUser

import api.account.selectors as account_selectors
import api.account.services as account_services


# =============================================================================
# 사용자 조회
# =============================================================================


def get_user_by_sabun(*, sabun: str) -> Optional[AbstractBaseUser]:
    """사번으로 사용자 정보를 조회합니다.

    입력:
    - sabun: 사번 문자열

    반환:
    - Optional[AbstractBaseUser]: 사용자 객체 또는 None

    부작용:
    - 없음

    오류:
    - 없음
    """
    # -----------------------------------------------------------------------------
    # 1) 사용자 모델 준비
    # -----------------------------------------------------------------------------
    UserModel = get_user_model()
    # -----------------------------------------------------------------------------
    # 2) 사번으로 단건 조회
    # -----------------------------------------------------------------------------
    return UserModel.objects.filter(sabun=sabun).first()


def get_current_user_payload(*, user: Any) -> Dict[str, Any]:
    """현재 로그인한 사용자 응답 payload를 읽기 전용으로 구성합니다.

    입력:
    - user: 인증된 Django 사용자 객체

    반환:
    - Dict[str, Any]: canonical `/api/v1/auth/me` 응답

    부작용:
    - 없음

    오류:
    - 없음
    """
    username = user.username if isinstance(getattr(user, "username", None), str) else ""
    is_keycloak_user = bool(getattr(user, "keycloak_subject", None))
    pending_change = (
        None
        if is_keycloak_user
        else account_selectors.get_pending_user_sdwt_prod_change(user=user)
    )
    pending_user_sdwt_prod = pending_change.to_user_sdwt_prod if pending_change else None
    has_pending_affiliation = pending_change is not None
    current_values = (
        dict(getattr(user, "affiliation_snapshot", {}) or {})
        if is_keycloak_user
        else account_selectors.get_current_affiliation_values(user=user)
    )
    raw_department = getattr(user, "department", None)
    department = raw_department.strip() if isinstance(raw_department, str) else raw_department
    if not department:
        department = current_values.get("department")

    scope_access = (
        _get_keycloak_scope_access_payloads(user=user)
        if is_keycloak_user
        else account_services.get_scope_access_payloads(user=user)
    )
    return {
        "id": user.pk,
        "usr_id": getattr(user, "knox_id", None),
        "avatarid": getattr(user, "avatarid", None),
        "username": username,
        "email": user.email,
        "is_superuser": False if is_keycloak_user else bool(getattr(user, "is_superuser", False)),
        "department": department,
        "line": current_values.get("line"),
        "user_sdwt_prod": current_values.get("user_sdwt_prod"),
        "pending_user_sdwt_prod": pending_user_sdwt_prod,
        "has_pending_affiliation": has_pending_affiliation,
        "scope_access": scope_access,
        "keycloak_subject": getattr(user, "keycloak_subject", None),
        "keycloak_group_id": getattr(user, "keycloak_group_id", ""),
        "groups": list(getattr(user, "keycloak_groups", []) or []),
        "realm_roles": list(getattr(user, "keycloak_realm_roles", []) or []),
        "client_roles": dict(getattr(user, "keycloak_client_roles", {}) or {}),
    }


def _get_keycloak_scope_access_payloads(*, user: Any) -> dict[str, dict[str, object]]:
    """Keycloak client role을 기존 frontend scope_access 계약으로 변환합니다."""

    client_roles = getattr(user, "keycloak_client_roles", {}) or {}
    all_roles = {
        str(role)
        for roles in client_roles.values()
        if isinstance(roles, list)
        for role in roles
    }
    portal_admin = "portal-admin" in all_roles
    portal_allowed = portal_admin or "portal-user" in all_roles
    payloads: dict[str, dict[str, object]] = {}
    for scope_key in account_services.SYSTEM_ACCESS_SCOPE_KEYS:
        admin_role = f"{scope_key}-admin"
        user_role = f"{scope_key}-user"
        if scope_key == "portal":
            allowed = portal_allowed
            role = "admin" if portal_admin else "user" if allowed else None
        else:
            is_admin = admin_role in all_roles
            allowed = portal_allowed and (is_admin or user_role in all_roles)
            role = "admin" if is_admin else "user" if allowed else None
        payloads[scope_key] = {
            "allowed": allowed,
            "scope": scope_key,
            "scopeType": "portal" if scope_key == "portal" else "app",
            "reason": "keycloak_role" if allowed else "keycloak_role_missing",
            "role": role,
            "effectiveStatus": "allowed" if allowed else "denied",
            "source": "keycloak_client_role",
            "canRequest": False,
            "blockedByPortal": bool(scope_key != "portal" and not portal_allowed),
        }
    return payloads
