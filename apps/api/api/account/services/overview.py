from __future__ import annotations

from typing import Any

from api.emails import services as email_services

from .. import selectors
from .access import _current_access_list, get_manageable_groups_with_members
from .affiliation_requests import _serialize_affiliation_change
from .affiliations import get_affiliation_reconfirm_status
from .utils import _is_privileged_user


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
