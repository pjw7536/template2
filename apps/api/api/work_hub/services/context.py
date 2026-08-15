"""현재 사용자의 소속 권한을 Grist launcher context로 변환합니다."""

from __future__ import annotations

from typing import Any

from django.conf import settings

from api.account import selectors as account_selectors
from api.account import services as account_services

from ..selectors import (
    list_active_document_scopes,
    list_active_document_scopes_for_user_sdwt_prods,
    list_active_document_scopes_for_keycloak_group_ids,
)


def build_work_hub_context(*, user: Any) -> dict[str, object]:
    """일반 사용자는 현재 소속만, manager는 접근 가능한 소속 mapping을 반환합니다."""

    if not getattr(settings, "WORK_HUB_ENABLED", False):
        return {
            "enabled": False,
            "available": False,
            "mode": "disabled",
            "reason": "work_hub_disabled",
            "groups": [],
        }

    if getattr(user, "keycloak_subject", None):
        access = account_services.get_access_payload(user=user, scope_key="work-hub")
        if not access.get("allowed"):
            return {
                "enabled": True,
                "available": False,
                "mode": "unavailable",
                "reason": "work_hub_role_missing",
                "groups": [],
            }
        is_admin = access.get("role") == "admin"
        mappings = list(
            list_active_document_scopes()
            if is_admin
            else list_active_document_scopes_for_keycloak_group_ids(
                group_ids=[str(getattr(user, "keycloak_group_id", "") or "")]
            )
        )
        groups = [
            {
                "user_sdwt_prod": str(
                    mapping.affiliation_snapshot.get("user_sdwt_prod")
                    or mapping.affiliation_snapshot.get("name")
                    or ""
                ),
                "department": str(mapping.affiliation_snapshot.get("department") or ""),
                "line": str(mapping.affiliation_snapshot.get("line") or ""),
                "role": "manager" if is_admin else str(
                    getattr(user, "affiliation_snapshot", {}).get("role") or "viewer"
                ),
                "launch_url": mapping.launch_url,
            }
            for mapping in mappings
        ]
        return _context_from_groups(groups)

    roles = account_selectors.get_accessible_user_sdwt_prod_roles_for_user(user)
    current = account_selectors.get_current_user_sdwt_prod(user=user)
    scoped_values = account_services.get_accessible_user_sdwt_prods_for_scope(
        user=user,
        scope_key="work-hub",
    )
    scoped_lookups = {value.casefold() for value in scoped_values}
    is_manager = bool(
        getattr(user, "is_superuser", False)
        or any(role == "manager" for role in roles.values())
    )
    allowed_values = (
        {value for value in roles if value.casefold() in scoped_lookups}
        if is_manager
        else (
            {current}
            if current and current.casefold() in scoped_lookups
            else set()
        )
    )
    mappings = list(
        list_active_document_scopes_for_user_sdwt_prods(
            user_sdwt_prods=allowed_values,
        )
    )

    groups = []
    for mapping in mappings:
        group_name = str(mapping.affiliation_snapshot.get("user_sdwt_prod") or "")
        role = next(
            (
                candidate_role
                for candidate, candidate_role in roles.items()
                if candidate.casefold() == group_name.casefold()
            ),
            "member" if current and current.casefold() == group_name.casefold() else "viewer",
        )
        groups.append(
            {
                "user_sdwt_prod": group_name,
                "department": mapping.affiliation_snapshot.get("department", ""),
                "line": mapping.affiliation_snapshot.get("line", ""),
                "role": role,
                "launch_url": mapping.launch_url,
            }
        )

    return _context_from_groups(groups)


def _context_from_groups(groups: list[dict[str, object]]) -> dict[str, object]:
    """launcher group 목록을 공통 context 응답으로 변환합니다."""

    if not groups:
        return {
            "enabled": True,
            "available": False,
            "mode": "unavailable",
            "reason": "no_active_grist_mapping",
            "groups": [],
        }
    return {
        "enabled": True,
        "available": True,
        "mode": "single" if len(groups) == 1 else "multiple",
        "reason": "",
        "groups": groups,
    }
