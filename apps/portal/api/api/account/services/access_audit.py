"""Account 접근 권한 감사 로그 저장과 응답 직렬화를 담당합니다."""

from __future__ import annotations

from typing import Any

from ..models import AccessAuditLog, AccessPolicyRule, AccessScope, UserAccess, UserSdwtProdAccess
from .access_runtime import _normalize_access_role

_POLICY_ACTIONS = {
    AccessAuditLog.Actions.POLICY_CREATE,
    AccessAuditLog.Actions.POLICY_UPDATE,
    AccessAuditLog.Actions.POLICY_DELETE,
}
_SCOPE_ACTIONS = {
    AccessAuditLog.Actions.SCOPE_CREATE,
    AccessAuditLog.Actions.SCOPE_UPDATE,
    AccessAuditLog.Actions.SCOPE_DELETE,
}
_DATA_SCOPE_ACTIONS = {
    AccessAuditLog.Actions.DATA_SCOPE_GRANT,
    AccessAuditLog.Actions.DATA_SCOPE_REVOKE,
    AccessAuditLog.Actions.DATA_SCOPE_CHANGE,
}
_AFFILIATION_ROLE_ACTIONS = {
    AccessAuditLog.Actions.AFFILIATION_ROLE_GRANT,
    AccessAuditLog.Actions.AFFILIATION_ROLE_CHANGE,
    AccessAuditLog.Actions.AFFILIATION_ROLE_REVOKE,
}
_AFFILIATION_LIFECYCLE_ACTIONS = {
    AccessAuditLog.Actions.AFFILIATION_CREATE,
    AccessAuditLog.Actions.AFFILIATION_UPDATE,
    AccessAuditLog.Actions.AFFILIATION_ACTIVATE,
    AccessAuditLog.Actions.AFFILIATION_DEACTIVATE,
}


def create_access_audit_log(
    *,
    scope: AccessScope | None,
    actor: Any,
    target_user: Any | None,
    policy_rule: AccessPolicyRule | None,
    action: str,
    before: dict[str, object],
    after: dict[str, object],
    reason: str | None,
    affiliation: Any | None = None,
) -> None:
    """action별 canonical snapshot을 사용해 접근 권한 감사 로그를 생성합니다."""

    AccessAuditLog.objects.create(
        scope=scope,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        target_user=target_user,
        affiliation=affiliation,
        policy_rule=policy_rule,
        action=action,
        before=_canonicalize_snapshot(action=action, snapshot=before),
        after=_canonicalize_snapshot(action=action, snapshot=after),
        reason=(reason or "").strip() or None,
    )


def serialize_access_audit_log(row: AccessAuditLog) -> dict[str, object]:
    """접근 권한 감사 로그를 canonical API 응답으로 직렬화합니다."""

    policy_rule = row.policy_rule
    policy_snapshot = _get_policy_rule_snapshot(row=row)
    return {
        "id": row.id,
        "scope": getattr(row.scope, "key", None),
        "scopeName": getattr(row.scope, "name", None),
        "action": row.action,
        "reason": row.reason,
        "before": row.before,
        "after": row.after,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "actor": _serialize_actor(row.actor),
        "targetUser": _serialize_actor(row.target_user),
        "affiliation": (
            {
                "id": row.affiliation.id,
                "department": row.affiliation.department,
                "line": row.affiliation.line,
                "userSdwtProd": row.affiliation.user_sdwt_prod,
            }
            if row.affiliation
            else None
        ),
        "policyRule": policy_snapshot or (
            {
                "id": policy_rule.id,
                "ruleType": policy_rule.rule_type,
                "value": policy_rule.value,
            }
            if policy_rule
            else None
        ),
    }


def _get_policy_rule_snapshot(*, row: AccessAuditLog) -> dict[str, object] | None:
    """삭제된 정책 규칙을 저장된 JSON snapshot에서 복원합니다."""

    for snapshot in (row.after, row.before):
        rule_type = snapshot.get("ruleType")
        value = snapshot.get("value")
        if rule_type or value:
            return {"id": snapshot.get("id"), "ruleType": rule_type, "value": value}
    return None


def _canonicalize_snapshot(*, action: str, snapshot: object) -> dict[str, object]:
    """감사 snapshot을 action별 허용 필드로 제한합니다."""

    if not isinstance(snapshot, dict):
        return {}
    fields_by_actions = (
        (_POLICY_ACTIONS, ("id", "ruleType", "value", "isActive")),
        (
            _SCOPE_ACTIONS,
            ("key", "name", "scopeType", "dataScopeType", "includeCurrentAffiliation", "isActive", "requestable"),
        ),
        (_DATA_SCOPE_ACTIONS, ("id", "dataScopeMode", "affiliationId", "source", "isActive", "expiresAt")),
        (_AFFILIATION_LIFECYCLE_ACTIONS, ("id", "department", "line", "userSdwtProd", "isActive", "source")),
    )
    for actions, fields in fields_by_actions:
        if action in actions:
            return {key: snapshot.get(key) for key in fields if key in snapshot}
    if action in _AFFILIATION_ROLE_ACTIONS:
        role = snapshot.get("role")
        return {
            key: snapshot.get(key)
            for key in ("role", "grantedBy")
            if key in snapshot and (key != "role" or role in UserSdwtProdAccess.Roles.values)
        }
    payload: dict[str, object] = {}
    explicit_status = snapshot.get("explicitStatus")
    if explicit_status in UserAccess.Status.values:
        payload["explicitStatus"] = explicit_status
    role = _normalize_access_role(snapshot.get("role"))
    if role is not None:
        payload["role"] = role
    return payload


def _serialize_actor(user: Any | None) -> dict[str, object] | None:
    """감사 로그 actor 또는 대상 사용자의 최소 정보를 직렬화합니다."""

    if user is None:
        return None
    return {
        "id": user.id,
        "knoxId": getattr(user, "knox_id", None),
        "username": getattr(user, "username", None),
        "email": getattr(user, "email", None),
    }
