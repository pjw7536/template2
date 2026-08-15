"""Keycloak cutover 직전 DB와 복구 증적 manifest를 출력합니다."""

import json

from django.core.management.base import BaseCommand, CommandError

from api.account.services.keycloak_cutover import (
    KeycloakCutoverValidationError,
    build_keycloak_cutover_manifest,
)
from api.account.services.keycloak_migration import KeycloakMigrationValidationError


class Command(BaseCommand):
    """모든 필수 증적이 준비된 경우에만 cutover manifest를 출력합니다."""

    help = "Keycloak cutover용 Account checksum과 backup/export/복원 증적을 검증합니다."

    def add_arguments(self, parser) -> None:
        """비상 계정과 세 가지 필수 복구 증적 경로를 등록합니다."""

        parser.add_argument("--emergency-sabun", required=True)
        parser.add_argument("--database-backup", required=True)
        parser.add_argument("--realm-export", required=True)
        parser.add_argument("--realm-restore-evidence", required=True)

    def handle(self, *args, **options) -> None:
        """검증된 manifest를 JSON으로 출력합니다."""

        try:
            manifest = build_keycloak_cutover_manifest(
                emergency_sabun=options["emergency_sabun"],
                database_backup_path=options["database_backup"],
                realm_export_path=options["realm_export"],
                realm_restore_evidence_path=options["realm_restore_evidence"],
            )
        except (KeycloakCutoverValidationError, KeycloakMigrationValidationError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2)
        )
