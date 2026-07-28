"""배포 전 접근 권한 데이터와 고정 역할 계약의 정합성을 점검합니다."""

from __future__ import annotations

import re

from django.core.management.base import BaseCommand, CommandError
from django.db.models.functions import Lower, Trim

from api.account.models import (
    ACCESS_SCOPE_KEY_PATTERN,
    ACCESS_SCOPE_PORTAL,
    SYSTEM_APP_SCOPE_KEYS,
    AccessPolicyRule,
    AccessRole,
    AccessScope,
    UserAccess,
)

PRE_MIGRATION_PHASE = "pre-migration"
POST_MIGRATION_PHASE = "post-migration"
LEGACY_ACCESS_ROLES = ("viewer", "member", "manager", "admin")


class Command(BaseCommand):
    """접근 권한 배포를 막아야 할 데이터 불일치를 보고합니다."""

    help = "접근 권한 scope, 정책, 사용자 역할의 정합성을 점검합니다."

    def add_arguments(self, parser):
        """검사할 migration 시점을 필수 인자로 등록합니다."""

        parser.add_argument(
            "--phase",
            choices=(PRE_MIGRATION_PHASE, POST_MIGRATION_PHASE),
            required=True,
            help="pre-migration은 legacy 역할, post-migration은 고정 역할 계약을 검사합니다.",
        )

    def handle(self, *args, **options):
        """읽기 전용 점검을 실행하고 문제가 있으면 실패 코드로 종료합니다."""

        phase = options["phase"]
        role_findings = (
            self._check_legacy_role_contract()
            if phase == PRE_MIGRATION_PHASE
            else self._check_fixed_role_contract()
        )
        findings = [
            *self._check_system_scopes(),
            *self._check_scope_identity(),
            *role_findings,
            *self._check_policy_values(),
        ]
        if findings:
            details = "\n".join(f"- {finding}" for finding in findings)
            raise CommandError(f"접근 권한 무결성 점검에 실패했습니다.\n{details}")

        self.stdout.write(
            self.style.SUCCESS(f"접근 권한 무결성 점검을 통과했습니다. phase={phase}")
        )

    def _check_system_scopes(self) -> list[str]:
        """코드가 요구하는 시스템 scope의 존재와 유형을 확인합니다."""

        expected_types = {ACCESS_SCOPE_PORTAL: AccessScope.ScopeTypes.PORTAL}
        expected_types.update({key: AccessScope.ScopeTypes.APP for key in SYSTEM_APP_SCOPE_KEYS})
        scopes = AccessScope.objects.filter(key__in=expected_types).in_bulk(field_name="key")
        findings = []
        for key, expected_type in expected_types.items():
            scope = scopes.get(key)
            if scope is None:
                findings.append(f"시스템 scope가 없습니다: {key}")
            elif scope.scope_type != expected_type:
                findings.append(
                    f"시스템 scope 유형이 잘못되었습니다: {key}={scope.scope_type}, expected={expected_type}"
                )
        return findings

    def _check_scope_identity(self) -> list[str]:
        """모든 scope가 고정 key 형식과 canonical Portal 규칙을 따르는지 확인합니다."""

        findings = []
        for scope in AccessScope.objects.order_by("id").only("id", "key", "scope_type"):
            if not re.fullmatch(ACCESS_SCOPE_KEY_PATTERN, scope.key or ""):
                findings.append(f"scope key 형식이 잘못되었습니다: id={scope.id}, key={scope.key!r}")
            if scope.key == ACCESS_SCOPE_PORTAL and scope.scope_type != AccessScope.ScopeTypes.PORTAL:
                findings.append(
                    f"canonical Portal 유형이 잘못되었습니다: id={scope.id}, type={scope.scope_type}"
                )
            if scope.key != ACCESS_SCOPE_PORTAL and scope.scope_type == AccessScope.ScopeTypes.PORTAL:
                findings.append(
                    f"canonical Portal 이외의 portal 유형 scope가 있습니다: id={scope.id}, key={scope.key}"
                )
        return findings

    def _check_legacy_role_contract(self) -> list[str]:
        """migration 전 사용자 접근이 legacy 역할 계약을 따르는지 확인합니다."""

        invalid_access_count = UserAccess.objects.exclude(
            role__in=LEGACY_ACCESS_ROLES
        ).count()
        if not invalid_access_count:
            return []
        return [f"유효하지 않은 legacy 사용자 역할이 {invalid_access_count}건입니다."]

    def _check_fixed_role_contract(self) -> list[str]:
        """migration 후 사용자 접근이 고정 역할 계약을 따르는지 확인합니다."""

        findings = []
        invalid_access_count = UserAccess.objects.exclude(role__in=AccessRole.values).count()
        if invalid_access_count:
            findings.append(f"유효하지 않은 사용자 역할이 {invalid_access_count}건입니다.")
        invalid_role_state_count = (
            UserAccess.objects.exclude(status=UserAccess.Status.ALLOWED)
            .exclude(role=AccessRole.USER)
            .count()
        )
        if invalid_role_state_count:
            findings.append(
                f"비허용 상태에 관리자 역할이 남은 사용자 권한이 {invalid_role_state_count}건입니다."
            )
        return findings

    def _check_policy_values(self) -> list[str]:
        """정책 값의 공백과 대소문자를 정규화했을 때 중복이 없는지 확인합니다."""

        findings = []
        seen_keys = {}
        rules = (
            AccessPolicyRule.objects.annotate(
                _access_policy_value=Lower(Trim("value")),
            )
            .order_by("id")
            .only("id", "scope_id", "rule_type", "value")
        )
        for rule in rules:
            normalized_value = (rule.value or "").strip()
            if not normalized_value:
                findings.append(f"정책 값이 비어 있습니다: id={rule.id}")
                continue
            if rule.value != normalized_value:
                findings.append(f"정책 값 앞뒤에 공백이 있습니다: id={rule.id}")
            # PostgreSQL Lower 기반 유일 제약과 같은 의미 키를 사용합니다.
            semantic_key = (
                rule.scope_id,
                rule.rule_type,
                rule._access_policy_value,
            )
            if semantic_key in seen_keys:
                findings.append(
                    f"의미상 중복 정책이 있습니다: id={seen_keys[semantic_key]}, id={rule.id}"
                )
            else:
                seen_keys[semantic_key] = rule.id
        return findings
