# =============================================================================
# 모듈: Assistant access requirements 정규화와 현재 권한 검증
# 주요 함수: merge_access_requirements, validate_access_requirements
# 핵심 전제: 알 수 없는 version/claim은 허용하지 않고 fail-closed합니다.
# =============================================================================
"""Assistant 파생 데이터가 요구하는 Account scope와 data claim을 관리합니다."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

import api.account.services as account_services
import api.rag.services as rag_services

from .. import selectors
from .normalization import resolve_sender_id

ACCESS_REQUIREMENTS_VERSION = 1
DATA_CLAIM_KEYS = ("ragPermissionGroups", "mailboxes")


@dataclass(frozen=True)
class AssistantAccessDecision:
    """현재 사용자 권한 검증 결과와 안전한 Account scope 누락 목록입니다."""

    allowed: bool
    missing_scopes: tuple[str, ...] = ()
    data_claim_denied: bool = False


def empty_access_requirements() -> dict[str, object]:
    """저장 가능한 빈 version 1 요구사항을 반환합니다."""

    return {"version": ACCESS_REQUIREMENTS_VERSION, "accountScopes": [], "dataClaims": {}}


def normalize_access_requirements(value: object) -> dict[str, object]:
    """임의 JSON을 제한된 version 1 access requirements로 정규화합니다.

    알 수 없는 version 또는 shape은 `legacy-unresolved` Account scope를 추가해
    read-time 검증에서 항상 잠기도록 보수적으로 변환합니다.
    """

    if (
        not isinstance(value, Mapping)
        or value.get("version") != ACCESS_REQUIREMENTS_VERSION
        or set(value) - {"version", "accountScopes", "dataClaims"}
        or not isinstance(value.get("accountScopes"), list)
        or not isinstance(value.get("dataClaims"), Mapping)
        or set(value.get("dataClaims", {})) - set(DATA_CLAIM_KEYS)
    ):
        return {
            "version": ACCESS_REQUIREMENTS_VERSION,
            "accountScopes": ["legacy-unresolved"],
            "dataClaims": {},
        }
    account_scopes = sorted(
        {
            str(item).strip()
            for item in value.get("accountScopes", [])
            if isinstance(item, str) and str(item).strip()
        }
    )
    raw_claims = value.get("dataClaims")
    claims: dict[str, list[str]] = {}
    if isinstance(raw_claims, Mapping):
        for claim_key in DATA_CLAIM_KEYS:
            claim_values = raw_claims.get(claim_key)
            if not isinstance(claim_values, list):
                continue
            normalized = sorted(
                {
                    str(item).strip()
                    for item in claim_values
                    if isinstance(item, str) and str(item).strip()
                }
            )
            if normalized:
                claims[claim_key] = normalized
    return {
        "version": ACCESS_REQUIREMENTS_VERSION,
        "accountScopes": account_scopes,
        "dataClaims": claims,
    }


def merge_access_requirements(*values: object) -> dict[str, object]:
    """여러 요구사항의 Account scope와 알려진 data claim을 합집합으로 결합합니다."""

    account_scopes: set[str] = set()
    claims: dict[str, set[str]] = {key: set() for key in DATA_CLAIM_KEYS}
    for value in values:
        normalized = normalize_access_requirements(value)
        account_scopes.update(normalized["accountScopes"])
        for claim_key, claim_values in normalized["dataClaims"].items():
            claims[claim_key].update(claim_values)
    return {
        "version": ACCESS_REQUIREMENTS_VERSION,
        "accountScopes": sorted(account_scopes),
        "dataClaims": {
            key: sorted(items) for key, items in claims.items() if items
        },
    }


def access_requirements_for_scopes(scopes: Iterable[str]) -> dict[str, object]:
    """Profile Account scope 목록을 저장 요구사항 형태로 변환합니다."""

    return merge_access_requirements(
        {
            "version": ACCESS_REQUIREMENTS_VERSION,
            "accountScopes": list(scopes),
            "dataClaims": {},
        }
    )


def _allowed_rag_groups(*, user: Any) -> set[str]:
    """현재 사용자가 Emails data scope에서 검색할 수 있는 group을 반환합니다."""

    allowed = set(
        selectors.get_accessible_email_user_sdwt_prods_for_user(user=user)
    )
    sender_id = resolve_sender_id(user)
    if sender_id:
        allowed.add(sender_id)
    allowed.add(rag_services.RAG_PUBLIC_GROUP)
    return allowed


def validate_access_requirements(
    *,
    user: Any,
    requirements: object,
    request: Any | None = None,
) -> AssistantAccessDecision:
    """저장된 요구사항을 현재 Account/data 권한으로 다시 검증합니다.

    반환:
        Account scope 누락은 안전한 key만 반환하며 data claim 실패 상세는 숨깁니다.

    부작용:
        Account와 affiliation selector를 읽기 전용으로 조회합니다.
    """

    normalized = normalize_access_requirements(requirements)
    missing_scopes = tuple(
        scope
        for scope in normalized["accountScopes"]
        if not account_services.get_access_payload(
            user=user,
            scope_key=scope,
            request=request,
        ).get("allowed")
    )
    data_claims = normalized["dataClaims"]
    rag_groups = set(data_claims.get("ragPermissionGroups", []))
    mailboxes = set(data_claims.get("mailboxes", []))
    data_claim_denied = bool(
        not rag_groups.issubset(_allowed_rag_groups(user=user))
        or not mailboxes.issubset(
            account_services.get_accessible_user_sdwt_prods_for_scope(
                user=user,
                scope_key="emails",
            )
        )
    )
    return AssistantAccessDecision(
        allowed=not missing_scopes and not data_claim_denied,
        missing_scopes=missing_scopes,
        data_claim_denied=data_claim_denied,
    )


__all__ = [
    "ACCESS_REQUIREMENTS_VERSION",
    "AssistantAccessDecision",
    "access_requirements_for_scopes",
    "empty_access_requirements",
    "merge_access_requirements",
    "normalize_access_requirements",
    "validate_access_requirements",
]
