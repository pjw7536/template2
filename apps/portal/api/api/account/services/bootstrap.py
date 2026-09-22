"""다른 도메인의 통합 테스트와 시스템 초기화를 위한 Account 상태 서비스입니다."""

from __future__ import annotations

from typing import Any

from django.db import transaction

from .. import selectors
from ..models import AccessPolicyRule, AccessScope, UserAccess


@transaction.atomic
def ensure_access_scope(
    *,
    key: str,
    name: str,
    scope_type: str,
) -> AccessScope:
    """scope를 생성하거나 기존 행을 반환합니다."""

    scope, _created = AccessScope.objects.get_or_create(
        key=key,
        defaults={"name": name, "scope_type": scope_type},
    )
    return scope


@transaction.atomic
def set_department_access_policy(
    *,
    scope_key: str,
    department: str,
    is_active: bool = True,
) -> AccessPolicyRule:
    """부서 기반 scope 접근 정책을 생성하거나 갱신합니다."""

    scope = selectors.get_access_scope_by_key_for_update(scope_key=scope_key)
    if scope is None:
        raise ValueError(f"존재하지 않는 접근 scope입니다: {scope_key}")
    rule, _created = AccessPolicyRule.objects.update_or_create(
        scope=scope,
        rule_type=AccessPolicyRule.RuleTypes.DEPARTMENT,
        value=department,
        defaults={"is_active": is_active},
    )
    return rule


@transaction.atomic
def set_user_scope_access(
    *,
    user: Any,
    scope_key: str,
    status: str,
    role: str,
) -> UserAccess:
    """사용자의 명시적 scope 접근 상태를 생성하거나 갱신합니다."""

    scope = selectors.get_access_scope_by_key_for_update(scope_key=scope_key)
    if scope is None:
        raise ValueError(f"존재하지 않는 접근 scope입니다: {scope_key}")
    access, _created = UserAccess.objects.update_or_create(
        scope=scope,
        user=user,
        defaults={"status": status, "role": role},
    )
    return access


__all__ = [
    "ensure_access_scope",
    "set_department_access_policy",
    "set_user_scope_access",
]
