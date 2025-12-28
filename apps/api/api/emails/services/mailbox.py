from __future__ import annotations

from typing import Any

from api.common.affiliations import UNASSIGNED_USER_SDWT_PROD

from ..selectors import (
    get_accessible_user_sdwt_prods_for_user,
    list_mailbox_members,
    list_privileged_email_mailboxes,
)
from ..permissions import user_can_view_unassigned


def get_mailbox_access_summary_for_user(*, user: Any) -> list[dict[str, object]]:
    """현재 사용자 기준 메일함 접근 요약을 반환합니다.

    Returns:
        List of dicts with mailbox membership stats.

    Side effects:
        None. Read-only query.
    """

    if not user or not getattr(user, "is_authenticated", False):
        return []

    is_privileged = bool(getattr(user, "is_superuser", False) or getattr(user, "is_staff", False))
    if is_privileged:
        mailboxes = list_privileged_email_mailboxes()
        if not user_can_view_unassigned(user):
            mailboxes = [
                mailbox
                for mailbox in mailboxes
                if mailbox not in {UNASSIGNED_USER_SDWT_PROD, "rp-unclassified"}
            ]
    else:
        mailboxes = sorted(get_accessible_user_sdwt_prods_for_user(user))

    summaries: list[dict[str, object]] = []
    user_id = getattr(user, "id", None)

    for mailbox in mailboxes:
        members = list_mailbox_members(mailbox_user_sdwt_prod=mailbox)
        member_count = len(members)
        current_member = None
        if isinstance(user_id, int):
            for member in members:
                if member.get("userId") == user_id:
                    current_member = member
                    break

        summaries.append(
            {
                "userSdwtProd": mailbox,
                "memberCount": member_count,
                "myEmailCount": int(current_member.get("emailCount", 0)) if current_member else 0,
                "myCanManage": bool(current_member.get("canManage", False)) if current_member else False,
                "myGrantedAt": current_member.get("grantedAt") if current_member else None,
                "myGrantedBy": current_member.get("grantedBy") if current_member else None,
            }
        )

    return summaries
