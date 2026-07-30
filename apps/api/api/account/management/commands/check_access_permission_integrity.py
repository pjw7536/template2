"""배포 전 접근 권한 데이터와 고정 역할 계약의 정합성을 점검합니다."""

from __future__ import annotations

import re

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.db.models.functions import Lower, Trim

from api.account.models import (
    ACCESS_SCOPE_KEY_PATTERN,
    ACCESS_SCOPE_PORTAL,
    AFFILIATION_DATA_SCOPE_KEYS,
    SYSTEM_APP_SCOPE_KEYS,
    AccessPolicyRule,
    AccessRole,
    AccessScope,
    Affiliation,
    UserAccess,
    UserScopeAffiliationGrant,
    UserSdwtProdAccess,
)

PRE_MIGRATION_PHASE = "pre-migration"
POST_MIGRATION_PHASE = "post-migration"
PRE_MIGRATION_ACCESS_ROLES = tuple(AccessRole.values)


class Command(BaseCommand):
    """접근 권한 배포를 막아야 할 데이터 불일치를 보고합니다."""

    help = "접근 권한 scope, 정책, 사용자 역할의 정합성을 점검합니다."

    def add_arguments(self, parser):
        """검사할 migration 시점을 필수 인자로 등록합니다."""

        parser.add_argument(
            "--phase",
            choices=(PRE_MIGRATION_PHASE, POST_MIGRATION_PHASE),
            required=True,
            help="pre-migration은 직전 release, post-migration은 현재 release 계약을 검사합니다.",
        )

    def handle(self, *args, **options):
        """읽기 전용 점검을 실행하고 문제가 있으면 실패 코드로 종료합니다."""

        phase = options["phase"]
        role_findings = (
            self._check_pre_migration_role_contract()
            if phase == PRE_MIGRATION_PHASE
            else self._check_fixed_role_contract()
        )
        findings = [
            *self._check_system_scopes(),
            *self._check_scope_identity(),
            *role_findings,
            *self._check_policy_values(),
            *self._check_affiliation_access_values(),
            *(
                self._check_app_affiliation_data_scopes()
                if phase == POST_MIGRATION_PHASE
                else []
            ),
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
        scopes = (
            AccessScope.objects.filter(key__in=expected_types)
            .only("id", "key", "scope_type")
            .in_bulk(field_name="key")
        )
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

    def _check_pre_migration_role_contract(self) -> list[str]:
        """migration 전 사용자 접근이 직전 release의 고정 역할 계약을 따르는지 확인합니다."""

        invalid_access_count = UserAccess.objects.exclude(
            role__in=PRE_MIGRATION_ACCESS_ROLES
        ).count()
        if not invalid_access_count:
            return []
        return [f"유효하지 않은 migration 전 사용자 역할이 {invalid_access_count}건입니다."]

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

    def _check_affiliation_access_values(self) -> list[str]:
        """소속 식별자와 소속 접근 역할의 무결성을 확인합니다."""

        findings = []
        seen_keys: dict[str, int] = {}
        affiliations = (
            Affiliation.objects.annotate(
                _affiliation_lookup=Lower(Trim("user_sdwt_prod")),
            )
            .order_by("id")
            .only("id", "user_sdwt_prod")
        )
        for affiliation in affiliations:
            normalized = (affiliation.user_sdwt_prod or "").strip()
            if not normalized:
                findings.append(f"소속 식별자가 비어 있습니다: id={affiliation.id}")
                continue
            if affiliation.user_sdwt_prod != normalized:
                findings.append(
                    f"소속 식별자 앞뒤에 공백이 있습니다: id={affiliation.id}"
                )
            semantic_key = affiliation._affiliation_lookup
            if semantic_key in seen_keys:
                findings.append(
                    "의미상 중복 소속이 있습니다: "
                    f"id={seen_keys[semantic_key]}, id={affiliation.id}"
                )
            else:
                seen_keys[semantic_key] = affiliation.id

        invalid_role_count = UserSdwtProdAccess.objects.exclude(
            role__in=UserSdwtProdAccess.Roles.values
        ).count()
        if invalid_role_count:
            findings.append(
                f"유효하지 않은 소속 접근 역할이 {invalid_role_count}건입니다."
            )
        return findings

    def _check_app_affiliation_data_scopes(self) -> list[str]:
        """migration 후 앱별 소속 정책과 grant 참조가 일치하는지 확인합니다."""

        findings = []
        scopes = AccessScope.objects.filter(
            key__in=(ACCESS_SCOPE_PORTAL, *SYSTEM_APP_SCOPE_KEYS)
        ).only(
            "id",
            "key",
            "data_scope_type",
            "include_current_affiliation",
        )
        for scope in scopes:
            expects_affiliation = scope.key in AFFILIATION_DATA_SCOPE_KEYS
            expected_type = (
                AccessScope.DataScopeTypes.AFFILIATION
                if expects_affiliation
                else AccessScope.DataScopeTypes.NONE
            )
            if scope.data_scope_type != expected_type:
                findings.append(
                    "시스템 scope 데이터 유형이 잘못되었습니다: "
                    f"{scope.key}={scope.data_scope_type}, expected={expected_type}"
                )
            if scope.include_current_affiliation != expects_affiliation:
                findings.append(
                    "시스템 scope 현재 소속 정책이 잘못되었습니다: "
                    f"{scope.key}={scope.include_current_affiliation}"
                )

        invalid_all_count = UserAccess.objects.filter(
            data_scope_mode=UserAccess.DataScopeModes.ALL,
        ).filter(
            ~Q(status=UserAccess.Status.ALLOWED)
            | ~Q(scope__data_scope_type=AccessScope.DataScopeTypes.AFFILIATION)
        ).count()
        if invalid_all_count:
            findings.append(
                f"허용되지 않은 전체 소속 범위가 {invalid_all_count}건입니다."
            )

        invalid_grant_count = UserScopeAffiliationGrant.objects.filter(
            ~Q(scope__data_scope_type=AccessScope.DataScopeTypes.AFFILIATION)
        ).count()
        if invalid_grant_count:
            findings.append(
                f"유효하지 않은 앱별 소속 grant가 {invalid_grant_count}건입니다."
            )
        return findings
