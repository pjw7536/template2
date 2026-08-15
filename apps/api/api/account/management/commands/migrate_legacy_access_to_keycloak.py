"""legacy Account 권한의 Keycloak 이관 계획을 검증하고 선택적으로 적용합니다."""

import json

from django.core.management.base import BaseCommand, CommandError

from api.account.services.keycloak_migration import (
    KeycloakMigrationValidationError,
    apply_keycloak_plan,
    build_legacy_keycloak_plan,
    compare_keycloak_plan,
)


class Command(BaseCommand):
    """dry-run을 기본으로 하고 명시한 경우에만 Keycloak을 변경합니다."""

    help = "현재 유효한 legacy 소속/Portal/app 권한을 Keycloak으로 이관합니다."

    def add_arguments(self, parser) -> None:
        """비상 계정과 적용 여부 인자를 등록합니다."""

        parser.add_argument("--emergency-sabun", required=True)
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--compare", action="store_true")

    def handle(self, *args, **options) -> None:
        """검증된 계획과 checksum을 출력하고 선택적으로 적용합니다."""

        try:
            plan = build_legacy_keycloak_plan(
                emergency_sabun=options["emergency_sabun"]
            )
        except KeycloakMigrationValidationError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(plan, ensure_ascii=False, sort_keys=True, indent=2))
        if not options["apply"]:
            self.stdout.write(self.style.WARNING("DRY-RUN: Keycloak을 변경하지 않았습니다."))
            return
        result = apply_keycloak_plan(plan=plan)
        self.stdout.write(self.style.SUCCESS(f"Keycloak 이관 완료: {result['applied']}명"))
        if options["compare"]:
            comparison = compare_keycloak_plan(plan=plan)
            if not comparison["matched"]:
                raise CommandError(
                    json.dumps(comparison["mismatches"], ensure_ascii=False, sort_keys=True)
                )
            self.stdout.write(self.style.SUCCESS("legacy/Keycloak 권한 비교 일치"))
