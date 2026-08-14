# =============================================================================
# 모듈 설명: 앱별 소속 데이터 범위를 판정하고 명시 grant를 관리합니다.
# - 주요 대상: 실효 소속 범위 resolver, Portal 관리자용 데이터 범위 변경
# - 불변 조건: 앱 접근이 없으면 소속 grant가 있어도 데이터 접근을 허용하지 않습니다.
# =============================================================================

"""앱 접근 역할과 분리된 소속 데이터 범위 서비스입니다."""

from __future__ import annotations

from typing import Any, Iterable

from django.db import transaction
from django.utils import timezone

from .. import selectors
from ..models import (
    AccessAuditLog,
    AccessScope,
    UserAccess,
    UserScopeAffiliationGrant,
)
from .access_control import create_access_audit_log
from .access_runtime import can_manage_access, get_access_payload


def _uses_keycloak(*, user: Any) -> bool:
    """사용자가 Keycloak group 기반 소속 범위를 사용하는지 반환합니다."""

    return bool(getattr(user, "keycloak_subject", None))


def _keycloak_affiliation_scope(*, user: Any, scope_key: str) -> dict[str, object]:
    """app admin은 전체, 일반 사용자는 기본 소속 하나로 범위를 제한합니다."""

    access = get_access_payload(user=user, scope_key=scope_key)
    if not access.get("allowed"):
        return {
            "allowed": False,
            "scope": scope_key,
            "type": AccessScope.DataScopeTypes.AFFILIATION,
            "mode": "denied",
            "all": False,
            "affiliationIds": [],
            "userSdwtProds": [],
        }
    is_admin = access.get("role") == "admin"
    snapshot = dict(getattr(user, "affiliation_snapshot", {}) or {})
    name = str(snapshot.get("user_sdwt_prod") or snapshot.get("name") or "").strip()
    return {
        "allowed": True,
        "scope": scope_key,
        "type": AccessScope.DataScopeTypes.AFFILIATION,
        "mode": "all" if is_admin else "selected",
        "all": is_admin,
        "affiliationIds": [],
        "userSdwtProds": [] if is_admin or not name else [name],
        "keycloakGroupIds": (
            [] if is_admin else [str(getattr(user, "keycloak_group_id", "") or "")]
        ),
    }


def _serialize_affiliation(affiliation: Any) -> dict[str, object]:
    """소속 모델을 권한 API의 고정 응답 형태로 변환합니다."""

    return {
        "id": affiliation.id,
        "department": affiliation.department,
        "line": affiliation.line,
        "userSdwtProd": affiliation.user_sdwt_prod,
        "isActive": affiliation.is_active,
    }


def _serialize_grant(grant: UserScopeAffiliationGrant) -> dict[str, object]:
    """앱별 소속 grant를 감사와 관리 API에서 재사용할 형태로 변환합니다."""

    return {
        "id": grant.id,
        "affiliationId": grant.affiliation_id,
        "source": grant.source,
        "isActive": grant.is_active,
        "expiresAt": grant.expires_at.isoformat() if grant.expires_at else None,
    }


def _resolve_affiliation_scope_state(
    *,
    user: Any,
    scope_key: str,
    request: Any | None = None,
) -> dict[str, object]:
    """상세 응답과 경량 판정이 공유하는 소속 범위 상태를 계산합니다."""

    access = get_access_payload(
        user=user,
        scope_key=scope_key,
        request=request,
    )
    scope = selectors.get_access_scope_by_key(scope_key=scope_key)
    if scope is None or not access.get("allowed"):
        return {
            "allowed": False,
            "scope": scope_key,
            "type": getattr(scope, "data_scope_type", None),
            "mode": "denied",
            "all": False,
            "affiliationIds": [],
            "_affiliations": [],
            "_sourceById": {},
        }

    if scope.data_scope_type == AccessScope.DataScopeTypes.NONE:
        return {
            "allowed": True,
            "scope": scope.key,
            "type": AccessScope.DataScopeTypes.NONE,
            "mode": "not_applicable",
            "all": False,
            "affiliationIds": [],
            "_affiliations": [],
            "_sourceById": {},
        }

    user_access = selectors.get_user_access_for_scope(user=user, scope=scope)
    has_all_scope = bool(
        getattr(user, "is_superuser", False)
        or (
            user_access
            and user_access.status == UserAccess.Status.ALLOWED
            and user_access.data_scope_mode == UserAccess.DataScopeModes.ALL
        )
    )
    if has_all_scope:
        return {
            "allowed": True,
            "scope": scope.key,
            "type": AccessScope.DataScopeTypes.AFFILIATION,
            "mode": "all",
            "all": True,
            "affiliationIds": [],
            "_affiliations": [],
            "_sourceById": {},
        }

    affiliation_by_id: dict[int, Any] = {}
    source_by_id: dict[int, str] = {}

    # -----------------------------------------------------------------------------
    # 1) 앱 정책이 허용한 현재 소속을 파생 범위로 추가
    # -----------------------------------------------------------------------------
    if scope.include_current_affiliation:
        current = selectors.get_current_affiliation_record(user=user)
        affiliation = getattr(current, "affiliation", None)
        if affiliation is not None and affiliation.is_active:
            affiliation_by_id[affiliation.id] = affiliation
            source_by_id[affiliation.id] = "current"

    # -----------------------------------------------------------------------------
    # 2) 앱에 명시적으로 부여된 활성·미만료 소속을 합산
    # -----------------------------------------------------------------------------
    for grant in selectors.list_active_scope_affiliation_grants(
        user=user,
        scope=scope,
    ):
        affiliation_by_id[grant.affiliation_id] = grant.affiliation
        # 현재 소속과 명시 grant가 겹치면 자동 포함 근거를 대표 source로 유지합니다.
        source_by_id.setdefault(grant.affiliation_id, grant.source)

    affiliations = sorted(
        affiliation_by_id.values(),
        key=lambda affiliation: (
            affiliation.department,
            affiliation.line,
            affiliation.user_sdwt_prod,
            affiliation.id,
        ),
    )
    return {
        "allowed": True,
        "scope": scope.key,
        "type": AccessScope.DataScopeTypes.AFFILIATION,
        "mode": "selected",
        "all": False,
        "affiliationIds": [affiliation.id for affiliation in affiliations],
        "_affiliations": affiliations,
        "_sourceById": source_by_id,
    }


def get_affiliation_scope_decision(
    *,
    user: Any,
    scope_key: str,
    request: Any | None = None,
) -> dict[str, object]:
    """쓰기 경로에서 사용할 경량 소속 범위 판정 결과를 반환합니다.

    `all=True`는 모든 활성 소속을 뜻하므로 개별 소속 목록을 조회하지 않습니다.
    """

    if _uses_keycloak(user=user):
        return _keycloak_affiliation_scope(user=user, scope_key=scope_key)

    state = _resolve_affiliation_scope_state(
        user=user,
        scope_key=scope_key,
        request=request,
    )
    affiliations = state.get("_affiliations", [])
    return {
        key: value
        for key, value in state.items()
        if not key.startswith("_")
    } | {
        "userSdwtProds": [affiliation.user_sdwt_prod for affiliation in affiliations],
    }


def get_effective_affiliation_scope(
    *,
    user: Any,
    scope_key: str,
    request: Any | None = None,
) -> dict[str, object]:
    """앱 접근을 포함해 사용자의 상세 실효 소속 데이터 범위를 반환합니다."""

    if _uses_keycloak(user=user):
        state = _keycloak_affiliation_scope(user=user, scope_key=scope_key)
        snapshot = dict(getattr(user, "affiliation_snapshot", {}) or {})
        serialized_snapshot = {
            "id": None,
            "department": str(snapshot.get("department") or ""),
            "line": str(snapshot.get("line") or ""),
            "userSdwtProd": str(
                snapshot.get("user_sdwt_prod") or snapshot.get("name") or ""
            ),
            "isActive": True,
            "keycloakGroupId": str(getattr(user, "keycloak_group_id", "") or ""),
            "role": str(snapshot.get("role") or ""),
        }
        return {
            **state,
            "affiliations": (
                []
                if state.get("all") or not serialized_snapshot["userSdwtProd"]
                else [serialized_snapshot]
            ),
        }

    state = _resolve_affiliation_scope_state(
        user=user,
        scope_key=scope_key,
        request=request,
    )
    affiliations = state.get("_affiliations", [])
    source_by_id = state.get("_sourceById", {})
    if state.get("all"):
        affiliations = selectors.list_active_affiliations()
        affiliation_ids = [affiliation.id for affiliation in affiliations]
        serialized_affiliations = [
            _serialize_affiliation(affiliation)
            for affiliation in affiliations
        ]
    else:
        affiliation_ids = state.get("affiliationIds", [])
        serialized_affiliations = [
            {
                **_serialize_affiliation(affiliation),
                "source": source_by_id[affiliation.id],
            }
            for affiliation in affiliations
        ]

    return {
        key: value
        for key, value in state.items()
        if not key.startswith("_") and key != "affiliationIds"
    } | {
        "affiliationIds": affiliation_ids,
        "affiliations": serialized_affiliations,
    }


def get_accessible_user_sdwt_prods_for_scope(
    *,
    user: Any,
    scope_key: str,
    request: Any | None = None,
) -> set[str]:
    """앱 scope에서 접근 가능한 활성 `user_sdwt_prod` 집합을 반환합니다."""

    if _uses_keycloak(user=user):
        resolved = _keycloak_affiliation_scope(user=user, scope_key=scope_key)
        if not resolved.get("allowed"):
            return set()
        if resolved.get("all"):
            return set(selectors.list_distinct_active_user_sdwt_prod_values())
        return set(resolved.get("userSdwtProds", []))

    resolved = get_affiliation_scope_decision(
        user=user,
        scope_key=scope_key,
        request=request,
    )
    if not resolved.get("allowed") or resolved.get("type") != AccessScope.DataScopeTypes.AFFILIATION:
        return set()
    if resolved.get("all"):
        return {
            affiliation.user_sdwt_prod
            for affiliation in selectors.list_active_affiliations()
        }
    return {
        str(value or "").strip()
        for value in resolved.get("userSdwtProds", [])
        if str(value or "").strip()
    }


def can_access_scope_affiliation(
    *,
    user: Any,
    scope_key: str,
    affiliation_id: int,
    request: Any | None = None,
) -> bool:
    """사용자가 앱 scope에서 특정 소속 데이터에 접근할 수 있는지 반환합니다."""

    resolved = get_affiliation_scope_decision(
        user=user,
        scope_key=scope_key,
        request=request,
    )
    return bool(
        resolved.get("allowed")
        and resolved.get("type") == AccessScope.DataScopeTypes.AFFILIATION
        and (
            resolved.get("all")
            or affiliation_id in set(resolved.get("affiliationIds", []))
        )
    )


@transaction.atomic
def deactivate_expired_scope_affiliation_grants(
    *,
    scope_key: str,
    limit: int = 100,
) -> int:
    """지정 앱 scope에서 만료된 활성 소속 grant를 비활성화합니다.

    grant별 저장 signal은 해당 소속의 외부 ACL projection을 다시 계산하게 합니다.
    한 번 비활성화한 grant는 다음 worker 검사에서 제외됩니다.
    """

    # Keycloak 전환 후 신규 grant는 생성하지 않지만 cutover 전 잔여 row 정리를 보존합니다.
    if limit <= 0:
        return 0
    scope = selectors.get_access_scope_by_key(scope_key=scope_key)
    if scope is None or scope.data_scope_type != AccessScope.DataScopeTypes.AFFILIATION:
        return 0

    grants = selectors.list_expired_scope_affiliation_grants_for_update(
        scope=scope,
        expired_at=timezone.now(),
        limit=limit,
    )
    for grant in grants:
        before = _serialize_grant(grant)
        grant.is_active = False
        grant.save(update_fields=["is_active", "updated_at"])
        create_access_audit_log(
            scope=scope,
            actor=None,
            target_user=grant.user,
            policy_rule=None,
            affiliation=grant.affiliation,
            action=AccessAuditLog.Actions.DATA_SCOPE_REVOKE,
            before=before,
            after=_serialize_grant(grant),
            reason="소속 데이터 범위 grant 만료",
        )
    return len(grants)


def get_user_scope_affiliation_data(
    *,
    actor: Any,
    user_id: int,
    scope_key: str,
    request: Any | None = None,
) -> tuple[dict[str, object], int]:
    """Portal 관리자가 편집할 사용자의 앱별 소속 데이터 범위를 반환합니다."""

    if _uses_keycloak(user=actor):
        return {"error": "keycloak_read_only"}, 410
    if not can_manage_access(user=actor, request=request):
        return {"error": "forbidden"}, 403
    target_user = selectors.get_user_by_id(user_id=user_id)
    if target_user is None:
        return {"error": "user_not_found"}, 404
    scope = selectors.get_access_scope_by_key(scope_key=scope_key)
    if scope is None:
        return {"error": "scope_not_found"}, 404
    if scope.data_scope_type != AccessScope.DataScopeTypes.AFFILIATION:
        return {"error": "affiliation_scope_not_supported"}, 400

    user_access = selectors.get_user_access_for_scope(user=target_user, scope=scope)
    grants = selectors.list_active_scope_affiliation_grants(
        user=target_user,
        scope=scope,
    )
    return {
        "user": {
            "id": target_user.id,
            "displayName": (
                getattr(target_user, "username", None)
                or getattr(target_user, "knox_id", None)
                or getattr(target_user, "sabun", None)
                or ""
            ),
        },
        "scope": {
            "key": scope.key,
            "name": scope.name,
            "dataScopeType": scope.data_scope_type,
            "includeCurrentAffiliation": scope.include_current_affiliation,
        },
        "dataScopeMode": (
            user_access.data_scope_mode
            if user_access
            else UserAccess.DataScopeModes.DEFAULT
        ),
        "grants": [_serialize_grant(grant) for grant in grants],
        "effective": get_effective_affiliation_scope(
            user=target_user,
            scope_key=scope.key,
        ),
    }, 200


def update_user_scope_affiliation_data(
    *,
    actor: Any,
    user_id: int,
    scope_key: str,
    data_scope_mode: str,
    affiliation_ids: Iterable[int],
    reason: str | None,
    request: Any | None = None,
) -> tuple[dict[str, object], int]:
    """Portal 관리자가 사용자의 앱별 전체·선택 소속 범위를 원자적으로 변경합니다."""

    if _uses_keycloak(user=actor):
        return {"error": "keycloak_read_only"}, 410
    if not can_manage_access(user=actor, request=request):
        return {"error": "forbidden"}, 403

    normalized_mode = (data_scope_mode or "").strip().lower()
    if normalized_mode not in UserAccess.DataScopeModes.values:
        return {"error": "invalid_data_scope_mode"}, 400
    normalized_reason = (reason or "").strip()
    if not normalized_reason:
        return {"error": "reason_required"}, 400

    raw_affiliation_ids = list(affiliation_ids)
    if any(
        type(affiliation_id) is not int or affiliation_id <= 0
        for affiliation_id in raw_affiliation_ids
    ):
        return {"error": "invalid_affiliation_ids"}, 400
    normalized_ids = set(raw_affiliation_ids)

    with transaction.atomic():
        scope = selectors.get_access_scope_by_key_for_update(scope_key=scope_key)
        if scope is None:
            return {"error": "scope_not_found"}, 404
        if (
            not scope.is_active
            or scope.data_scope_type != AccessScope.DataScopeTypes.AFFILIATION
        ):
            return {"error": "affiliation_scope_not_supported"}, 400
        affiliations = selectors.list_active_affiliations_by_ids_for_update(
            affiliation_ids=normalized_ids,
        )
        if {affiliation.id for affiliation in affiliations} != normalized_ids:
            return {"error": "invalid_affiliation_ids"}, 400

        # 소속 역할 변경 서비스와 같은 순서로 소속 다음 사용자를 잠가 교착을 방지합니다.
        target_user = selectors.get_user_by_id_for_update(user_id=user_id)
        if target_user is None:
            return {"error": "user_not_found"}, 404
        if target_user.is_superuser:
            return {"error": "immutable_access_bypass"}, 409

        user_access = selectors.get_user_access_for_scope_for_update(
            user=target_user,
            scope=scope,
        )
        if normalized_mode == UserAccess.DataScopeModes.ALL and (
            user_access is None
            or user_access.status != UserAccess.Status.ALLOWED
        ):
            return {"error": "allowed_app_access_required_for_all"}, 409
        scope_grants = selectors.list_scope_affiliation_grants_for_update(
            user=target_user,
            scope=scope,
        )
        now = timezone.now()
        protected_non_manual_affiliation_ids = {
            grant.affiliation_id
            for grant in scope_grants
            if (
                grant.source != UserScopeAffiliationGrant.Sources.MANUAL
                and grant.is_active
                and grant.affiliation.is_active
                and (grant.expires_at is None or grant.expires_at > now)
            )
        }
        non_manual_conflicts = sorted(
            normalized_ids & protected_non_manual_affiliation_ids
        )
        if non_manual_conflicts:
            return {
                "error": "non_manual_affiliation_grants_immutable",
                "affiliationIds": non_manual_conflicts,
            }, 409

        # -----------------------------------------------------------------------------
        # 1) 전체 범위 모드를 앱 접근 행과 함께 갱신
        # -----------------------------------------------------------------------------
        if user_access is not None and user_access.data_scope_mode != normalized_mode:
            before_mode = user_access.data_scope_mode
            user_access.data_scope_mode = normalized_mode
            user_access.save(update_fields=["data_scope_mode", "updated_at"])
            create_access_audit_log(
                scope=scope,
                actor=actor,
                target_user=target_user,
                policy_rule=None,
                affiliation=None,
                action=AccessAuditLog.Actions.DATA_SCOPE_CHANGE,
                before={"dataScopeMode": before_mode},
                after={"dataScopeMode": normalized_mode},
                reason=normalized_reason or None,
            )

        # -----------------------------------------------------------------------------
        # 2) 수동 grant 집합을 요청한 소속 ID와 일치시키고 비수동 grant는 보존
        # -----------------------------------------------------------------------------
        grants_by_affiliation_id = {
            grant.affiliation_id: grant
            for grant in scope_grants
            if grant.source == UserScopeAffiliationGrant.Sources.MANUAL
        }
        reclaimable_grants_by_affiliation_id = {
            grant.affiliation_id: grant
            for grant in scope_grants
            if (
                grant.source != UserScopeAffiliationGrant.Sources.MANUAL
                and grant.affiliation_id not in protected_non_manual_affiliation_ids
            )
        }
        for affiliation in affiliations:
            grant = grants_by_affiliation_id.get(affiliation.id)
            if grant is None:
                grant = reclaimable_grants_by_affiliation_id.get(affiliation.id)
            before = _serialize_grant(grant) if grant else {}
            if grant is None:
                grant = UserScopeAffiliationGrant.objects.create(
                    user=target_user,
                    scope=scope,
                    affiliation=affiliation,
                    source=UserScopeAffiliationGrant.Sources.MANUAL,
                    is_active=True,
                    expires_at=None,
                    reason=normalized_reason or None,
                    granted_by=actor,
                )
            elif (
                grant.source != UserScopeAffiliationGrant.Sources.MANUAL
                or not grant.is_active
                or grant.expires_at is not None
            ):
                grant.source = UserScopeAffiliationGrant.Sources.MANUAL
                grant.is_active = True
                grant.expires_at = None
                grant.reason = normalized_reason or None
                grant.granted_by = actor
                grant.save(
                    update_fields=[
                        "source",
                        "is_active",
                        "expires_at",
                        "reason",
                        "granted_by",
                        "updated_at",
                    ]
                )
            else:
                continue
            create_access_audit_log(
                scope=scope,
                actor=actor,
                target_user=target_user,
                policy_rule=None,
                affiliation=affiliation,
                action=AccessAuditLog.Actions.DATA_SCOPE_GRANT,
                before=before,
                after=_serialize_grant(grant),
                reason=normalized_reason or None,
            )

        for affiliation_id, grant in grants_by_affiliation_id.items():
            if affiliation_id in normalized_ids or not grant.is_active:
                continue
            before = _serialize_grant(grant)
            grant.is_active = False
            grant.reason = normalized_reason or None
            grant.granted_by = actor
            grant.save(
                update_fields=[
                    "is_active",
                    "reason",
                    "granted_by",
                    "updated_at",
                ]
            )
            create_access_audit_log(
                scope=scope,
                actor=actor,
                target_user=target_user,
                policy_rule=None,
                affiliation=grant.affiliation,
                action=AccessAuditLog.Actions.DATA_SCOPE_REVOKE,
                before=before,
                after=_serialize_grant(grant),
                reason=normalized_reason or None,
            )

    payload, status_code = get_user_scope_affiliation_data(
        actor=actor,
        user_id=user_id,
        scope_key=scope_key,
    )
    if status_code != 200:
        return payload, status_code
    return {"status": "ok", **payload}, 200


__all__ = [
    "can_access_scope_affiliation",
    "get_accessible_user_sdwt_prods_for_scope",
    "get_effective_affiliation_scope",
    "get_user_scope_affiliation_data",
    "update_user_scope_affiliation_data",
]
