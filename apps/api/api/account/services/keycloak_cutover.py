"""Keycloak cutover 전 Account DB와 복구 증적의 검증 manifest를 만듭니다."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ..models import (
    AccessAuditLog,
    AccessPolicyRule,
    AccessScope,
    Affiliation,
    ExternalAffiliationSnapshot,
    User,
    UserAccess,
    UserCurrentAffiliation,
    UserScopeAffiliationGrant,
    UserSdwtProdAccess,
    UserSdwtProdChange,
)
from .keycloak_migration import build_legacy_keycloak_plan


ACCOUNT_CUTOVER_MODELS = (
    User,
    Affiliation,
    UserCurrentAffiliation,
    UserSdwtProdAccess,
    AccessScope,
    AccessPolicyRule,
    UserAccess,
    UserScopeAffiliationGrant,
    AccessAuditLog,
    UserSdwtProdChange,
    ExternalAffiliationSnapshot,
)


class KeycloakCutoverValidationError(ValueError):
    """backup/export/복원 증적이 없거나 비어 있을 때 발생합니다."""


def _sha256_file(path: Path) -> str:
    """파일을 메모리에 모두 올리지 않고 SHA-256을 계산합니다."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _evidence(path_value: str, *, label: str) -> dict[str, Any]:
    """복구 증적 파일의 존재, 크기와 checksum을 검증합니다."""

    path = Path(str(path_value or "").strip())
    if not path.is_file() or path.stat().st_size <= 0:
        raise KeycloakCutoverValidationError(f"{label} 파일이 없거나 비어 있습니다: {path}")
    return {
        "path": str(path),
        "size": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def build_account_table_manifest() -> dict[str, dict[str, Any]]:
    """Account 각 테이블의 row count와 정렬된 row checksum을 계산합니다."""

    result: dict[str, dict[str, Any]] = {}
    for model in ACCOUNT_CUTOVER_MODELS:
        primary_key = str(model._meta.pk.name)
        queryset = model.objects.order_by(primary_key).values()
        digest = hashlib.sha256()
        count = 0
        for row in queryset.iterator(chunk_size=1000):
            canonical = json.dumps(
                row,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            )
            digest.update(canonical.encode("utf-8"))
            digest.update(b"\n")
            count += 1
        result[model._meta.db_table] = {
            "rows": count,
            "sha256": digest.hexdigest(),
        }
    return result


def build_keycloak_cutover_manifest(
    *,
    emergency_sabun: str,
    database_backup_path: str,
    realm_export_path: str,
    realm_restore_evidence_path: str,
) -> dict[str, Any]:
    """이관 계획과 DB/Keycloak 복구 증적을 하나의 검증 manifest로 묶습니다."""

    evidence = {
        "database_backup": _evidence(database_backup_path, label="DB backup"),
        "realm_export": _evidence(realm_export_path, label="Keycloak realm export"),
        "realm_restore_test": _evidence(
            realm_restore_evidence_path,
            label="Keycloak realm 복원 시험 증적",
        ),
    }
    migration_plan = build_legacy_keycloak_plan(emergency_sabun=emergency_sabun)
    return {
        "version": 1,
        "migration_plan": {
            "user_count": migration_plan["user_count"],
            "checksum": migration_plan["checksum"],
        },
        "account_tables": build_account_table_manifest(),
        "evidence": evidence,
    }
