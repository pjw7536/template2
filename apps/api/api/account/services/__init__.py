# =============================================================================
# 모듈 설명: account 서비스 파사드(공용 진입점)를 제공합니다.
# - 주요 대상: 소속/권한/요청 처리 서비스 함수
# - 불변 조건: 서비스 구현은 services/* 모듈로 위임합니다.
# =============================================================================

"""account 서비스 파사드 모듈입니다."""

from __future__ import annotations

from .access import (
    AFFILIATION_CAPABILITY_APPROVE,
    AFFILIATION_CAPABILITY_DELETE,
    AFFILIATION_CAPABILITY_MANAGE_ACCESS,
    AFFILIATION_CAPABILITY_READ,
    AFFILIATION_CAPABILITY_WRITE,
    ensure_self_access,
    get_affiliation_members,
    get_manageable_groups_with_members,
    grant_or_revoke_access,
    has_affiliation_capability,
    has_affiliation_capability_for_ids,
)
from .affiliations import (
    AFFILIATION_AUDIT_SOURCE_DJANGO_ADMIN,
    AFFILIATION_AUDIT_SOURCE_DEV_SEED,
    AFFILIATION_AUDIT_SOURCE_SYSTEM_SYNC,
    auto_approve_affiliation_from_snapshot,
    create_affiliation,
    ensure_affiliation_option,
    get_affiliation_overview,
    get_affiliation_reconfirm_status,
    get_line_sdwt_options_payload,
    set_affiliation_active,
    set_affiliations_active,
    set_current_affiliation_for_user,
    submit_affiliation_reconfirm_response,
)
from .affiliation_requests import (
    approve_affiliation_change,
    get_affiliation_change_requests,
    get_current_user_sdwt_prod_change,
    get_pending_user_sdwt_prod_change,
    reject_affiliation_change,
    request_affiliation_change,
)
from .external_sync import sync_external_affiliations
from .overview import get_account_overview
from .access_control import (
    approve_pending_access_requests,
    bulk_apply_access_policy_rules,
    create_access_audit_log,
    create_access_policy_rule,
    decide_user_access,
    delete_access_policy_rule,
    apply_all_user_accesses,
    get_access_audit_logs,
    get_access_matrix,
    get_pending_access_requests,
    get_access_policy_rules,
    get_access_users,
    request_access,
    update_access_policy_rule,
)
from .access_runtime import (
    can_manage_access,
    get_access_payload,
    get_scope_access_payloads,
    has_scope_role,
    list_effective_affiliation_member_roles_for_scope,
)
from .dev_affiliation import ensure_dev_user_affiliation
from .dev_access import seed_dev_access_data
from .dev_users import ensure_dev_dummy_superuser
from .data_scope import (
    can_access_scope_affiliation,
    deactivate_expired_scope_affiliation_grants,
    get_affiliation_scope_decision,
    get_accessible_user_sdwt_prods_for_scope,
    get_effective_affiliation_scope,
    get_user_scope_affiliation_data,
    update_user_scope_affiliation_data,
)
from .bootstrap import (
    ensure_access_scope,
    set_department_access_policy,
    set_user_scope_access,
)
from .users import get_user_by_knox_id

__all__ = [
    "AFFILIATION_AUDIT_SOURCE_DJANGO_ADMIN",
    "AFFILIATION_AUDIT_SOURCE_DEV_SEED",
    "AFFILIATION_AUDIT_SOURCE_SYSTEM_SYNC",
    "AFFILIATION_CAPABILITY_APPROVE",
    "AFFILIATION_CAPABILITY_DELETE",
    "AFFILIATION_CAPABILITY_MANAGE_ACCESS",
    "AFFILIATION_CAPABILITY_READ",
    "AFFILIATION_CAPABILITY_WRITE",
    "approve_pending_access_requests",
    "approve_affiliation_change",
    "auto_approve_affiliation_from_snapshot",
    "bulk_apply_access_policy_rules",
    "can_manage_access",
    "can_access_scope_affiliation",
    "deactivate_expired_scope_affiliation_grants",
    "create_affiliation",
    "create_access_audit_log",
    "create_access_policy_rule",
    "decide_user_access",
    "delete_access_policy_rule",
    "ensure_self_access",
    "ensure_affiliation_option",
    "ensure_access_scope",
    "ensure_dev_dummy_superuser",
    "ensure_dev_user_affiliation",
    "apply_all_user_accesses",
    "get_current_user_sdwt_prod_change",
    "get_account_overview",
    "get_affiliation_change_requests",
    "get_affiliation_members",
    "get_affiliation_overview",
    "get_affiliation_reconfirm_status",
    "get_line_sdwt_options_payload",
    "get_manageable_groups_with_members",
    "get_pending_user_sdwt_prod_change",
    "get_access_payload",
    "get_affiliation_scope_decision",
    "get_accessible_user_sdwt_prods_for_scope",
    "get_access_audit_logs",
    "get_access_matrix",
    "get_effective_affiliation_scope",
    "get_pending_access_requests",
    "get_scope_access_payloads",
    "get_access_policy_rules",
    "get_access_users",
    "has_scope_role",
    "list_effective_affiliation_member_roles_for_scope",
    "has_affiliation_capability",
    "has_affiliation_capability_for_ids",
    "get_user_by_knox_id",
    "get_user_scope_affiliation_data",
    "grant_or_revoke_access",
    "reject_affiliation_change",
    "request_access",
    "request_affiliation_change",
    "set_current_affiliation_for_user",
    "set_affiliation_active",
    "set_affiliations_active",
    "set_department_access_policy",
    "set_user_scope_access",
    "seed_dev_access_data",
    "submit_affiliation_reconfirm_response",
    "sync_external_affiliations",
    "update_access_policy_rule",
    "update_user_scope_affiliation_data",
]
