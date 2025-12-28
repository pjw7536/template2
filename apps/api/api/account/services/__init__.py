"""Account feature service facade."""

from __future__ import annotations

from .access import ensure_self_access, get_manageable_groups_with_members, grant_or_revoke_access
from .affiliations import (
    get_affiliation_overview,
    get_affiliation_reconfirm_status,
    get_line_sdwt_options_payload,
    submit_affiliation_reconfirm_response,
    update_affiliation_jira_key,
)
from .affiliation_requests import (
    approve_affiliation_change,
    get_affiliation_change_requests,
    reject_affiliation_change,
    request_affiliation_change,
)
from .external_sync import sync_external_affiliations
from .overview import get_account_overview
from .users import ensure_user_profile, resolve_target_user

__all__ = [
    "approve_affiliation_change",
    "ensure_self_access",
    "ensure_user_profile",
    "get_account_overview",
    "get_affiliation_change_requests",
    "get_affiliation_overview",
    "get_affiliation_reconfirm_status",
    "get_line_sdwt_options_payload",
    "get_manageable_groups_with_members",
    "grant_or_revoke_access",
    "reject_affiliation_change",
    "request_affiliation_change",
    "resolve_target_user",
    "submit_affiliation_reconfirm_response",
    "sync_external_affiliations",
    "update_affiliation_jira_key",
]
