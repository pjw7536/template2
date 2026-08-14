"""현재 사용자의 소속 권한을 Grist launcher context로 변환합니다."""

from __future__ import annotations

from typing import Any

from django.conf import settings

from api.account import selectors as account_selectors
from api.account import services as account_services

from ..selectors import list_active_document_scopes_for_user_sdwt_prods


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
        group_name = mapping.affiliation.user_sdwt_prod
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
                "department": mapping.affiliation.department,
                "line": mapping.affiliation.line,
                "role": role,
                "launch_url": mapping.launch_url,
            }
        )

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
