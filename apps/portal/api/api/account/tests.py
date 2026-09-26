"""기존 account migration 이력을 검증합니다.

현재 런타임의 Keycloak 계약은 test_keycloak_access와 test_http_contract에서 검증합니다.
종료한 Portal 권한 수정·소속 승인·자동 관리자 생성 API는 더 이상 지원하지 않습니다.
"""
from __future__ import annotations
import importlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import StringIO
from threading import Barrier
from unittest.mock import patch
from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import (
    IntegrityError,
    close_old_connections,
    connection,
    connections,
    transaction,
)
from django.db.migrations.executor import MigrationExecutor
from django.db.models import Q, QuerySet
from django.db.models.deletion import ProtectedError
from django.test import RequestFactory, TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from django.urls import reverse
from api.account import selectors as account_selectors
from api.account.models import (
    ACCESS_SCOPE_PORTAL,
    AccessAuditLog,
    AccessPolicyRule,
    AccessRole,
    AccessScope,
    AccessSource,
    Affiliation,
    ExternalAffiliationSnapshot,
    UserAccess,
    UserCurrentAffiliation,
    UserScopeAffiliationGrant,
    UserSdwtProdAccess,
    UserSdwtProdChange,
)
from api.account.selectors import (
    filter_access_management_users_by_effective_access,
    get_accessible_user_sdwt_prods_for_user,
    get_current_user_sdwt_prod,
    get_next_user_sdwt_prod_change,
    list_active_affiliations_by_ids_for_update,
    list_active_affiliations_by_user_sdwt_prods_for_update,
    list_active_user_emails_by_user_sdwt_prod,
    list_active_user_knox_ids_by_user_sdwt_prod,
    list_affiliation_options,
    list_access_management_users,
    list_line_sdwt_pairs,
    resolve_user_affiliation,
)
from api.account.services import access_control as access_control_services
from api.account.services import (
    AFFILIATION_CAPABILITY_MANAGE_ACCESS,
    approve_affiliation_change,
    auto_approve_affiliation_from_snapshot,
    bulk_apply_access_policy_rules,
    create_affiliation,
    create_access_policy_rule,
    decide_user_access,
    delete_access_policy_rule,
    ensure_affiliation_option,
    ensure_self_access,
    get_account_overview,
    get_access_payload,
    get_affiliation_scope_decision,
    get_effective_affiliation_scope,
    get_scope_access_payloads,
    get_affiliation_change_requests,
    get_affiliation_overview,
    grant_or_revoke_access,
    has_affiliation_capability,
    has_affiliation_capability_for_ids,
    can_manage_access,
    has_scope_role,
    reject_affiliation_change,
    request_affiliation_change,
    request_access,
    seed_dev_access_data,
    set_affiliation_active,
    set_affiliations_active,
    submit_affiliation_reconfirm_response,
    sync_external_affiliations,
    update_user_scope_affiliation_data,
    update_access_policy_rule,
)

class FixedAccessRoleMigrationTests(TransactionTestCase):
    """실제 과거 스키마에서 접근 권한 migration의 데이터 보존을 검증합니다."""

    serialized_rollback = True
    migrate_from = ("account", "0004_app_scope_requests")
    migrate_to = ("account", "0005_fixed_access_roles")

    @classmethod
    def _fixture_setup(cls) -> None:
        """초기 스냅샷은 종료 복원용으로만 사용하고 테스트 시작 시 중복 적재하지 않습니다."""

    def setUp(self) -> None:
        """0004 상태를 만든 뒤 legacy 역할과 관련 데이터를 저장합니다."""

        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_from])
        self.addCleanup(self._restore_latest_migrations)
        old_apps = executor.loader.project_state([self.migrate_from]).apps

        User = old_apps.get_model("account", "User")
        AccessScope = old_apps.get_model("account", "AccessScope")
        AccessAuditLog = old_apps.get_model("account", "AccessAuditLog")
        AccessPolicyRule = old_apps.get_model("account", "AccessPolicyRule")
        UserAccess = old_apps.get_model("account", "UserAccess")
        UserProfile = old_apps.get_model("account", "UserProfile")

        user = User.objects.create(avatarid="MIGRATION-RBAC-USER",
            sabun="MIGRATION-RBAC-USER",
            username="migration-user",
        )
        self.user_id = user.id
        UserProfile.objects.create(user_id=user.id, role="manager")
        scope = AccessScope.objects.create(
            key="migration-feature",
            name="Migration Feature",
            scope_type="feature",
            requestable=True,
            default_role="manager",
        )
        self.access_id = UserAccess.objects.create(
            user_id=user.id,
            scope_id=scope.id,
            status="allowed",
            role="admin",
            reason="기존 메모 유지",
        ).id
        self.denied_access_id = UserAccess.objects.create(
            user_id=user.id,
            scope_id=AccessScope.objects.create(
                key="migration-denied-feature",
                name="Migration Denied Feature",
                scope_type="feature",
                requestable=True,
                default_role="viewer",
            ).id,
            status="denied",
            role="admin",
            reason="기존 차단 메모 유지",
        ).id
        self.policy_id = AccessPolicyRule.objects.create(
            scope_id=scope.id,
            rule_type="department",
            value="Migration Department",
            role="manager",
        ).id
        self.audit_id = AccessAuditLog.objects.create(
            scope_id=scope.id,
            target_user_id=user.id,
            action="access_manager_grant",
            after={"canManageAccess": True},
        ).id
        batched_audits = AccessAuditLog.objects.bulk_create(
            [
                AccessAuditLog(
                    scope_id=scope.id,
                    action="policy_create",
                    before={},
                    after={
                        "id": index,
                        "ruleType": "department",
                        "value": f"Migration Department {index}",
                        "role": "manager",
                        "isActive": True,
                    },
                )
                for index in range(1001)
            ]
        )
        self.batched_audit_ids = [batched_audits[0].id, batched_audits[-1].id]

    def _restore_latest_migrations(self) -> None:
        """실패 여부와 관계없이 다른 테스트를 위해 전체 migration leaf를 복구합니다."""

        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def _fixture_teardown(self) -> None:
        """테스트 DB의 migration 초기 데이터까지 시작 시점 스냅샷으로 복원합니다."""

        # -----------------------------------------------------------------------------
        # 1) 최신 스키마를 먼저 복원해 이후 테스트가 과거 migration 상태를 보지 않게 함
        # -----------------------------------------------------------------------------
        self._restore_latest_migrations()

        # -----------------------------------------------------------------------------
        # 2) 최신 스키마 기준으로 데이터를 비우고 초기 직렬화 데이터를 복원
        # -----------------------------------------------------------------------------
        for database_name in self._databases_names(include_mirrors=False):
            database_connection = connections[database_name]
            call_command(
                "flush",
                verbosity=0,
                interactive=False,
                database=database_name,
                reset_sequences=False,
                inhibit_post_migrate=True,
            )
            serialized_contents = getattr(
                database_connection,
                "_test_serialized_contents",
                None,
            )
            if serialized_contents:
                database_connection.creation.deserialize_db_from_string(
                    serialized_contents
                )

    def test_migration_preserves_access_data_and_removes_legacy_role_fields(self) -> None:
        """통합 0005가 상태·사유를 보존하고 미사용 프로필을 제거하는지 검증합니다."""

        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_to])
        new_apps = executor.loader.project_state([self.migrate_to]).apps

        AccessScope = new_apps.get_model("account", "AccessScope")
        AccessAuditLog = new_apps.get_model("account", "AccessAuditLog")
        AccessPolicyRule = new_apps.get_model("account", "AccessPolicyRule")
        UserAccess = new_apps.get_model("account", "UserAccess")
        access = UserAccess.objects.get(id=self.access_id)
        denied_access = UserAccess.objects.get(id=self.denied_access_id)
        audit_log = AccessAuditLog.objects.get(id=self.audit_id)

        self.assertEqual(access.status, "allowed")
        self.assertEqual(access.role, "user")
        self.assertEqual(access.reason, "기존 메모 유지")
        self.assertEqual(denied_access.status, "denied")
        self.assertEqual(denied_access.role, "user")
        self.assertEqual(denied_access.reason, "기존 차단 메모 유지")
        with self.assertRaises(LookupError):
            new_apps.get_model("account", "UserProfile")
        self.assertTrue(AccessPolicyRule.objects.filter(id=self.policy_id).exists())
        self.assertNotIn("default_role", {field.name for field in AccessScope._meta.fields})
        self.assertNotIn("role", {field.name for field in AccessPolicyRule._meta.fields})
        self.assertEqual(audit_log.action, "grant")
        self.assertEqual(audit_log.scope.key, "portal")
        self.assertEqual(audit_log.before, {})
        self.assertEqual(
            audit_log.after,
            {"explicitStatus": "allowed", "role": "admin"},
        )
        batched_audits = list(
            AccessAuditLog.objects.filter(id__in=self.batched_audit_ids).order_by("id")
        )
        self.assertEqual(len(batched_audits), 2)
        self.assertTrue(all("role" not in row.after for row in batched_audits))

class AccountAuthorizationMigrationTests(TransactionTestCase):
    """통합 권한 migration의 대기 소속 요청 정리와 제약을 검증합니다."""

    serialized_rollback = True
    migrate_from = ("account", "0005_fixed_access_roles")
    migrate_to = ("account", "0006_account_authorization_system")

    @classmethod
    def _fixture_setup(cls) -> None:
        """초기 스냅샷은 종료 복원용으로만 사용합니다."""

    def setUp(self) -> None:
        """0005 스키마에서 사용자별 중복 대기 요청을 준비합니다."""

        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_from])
        self.addCleanup(self._restore_latest_migrations)
        old_apps = executor.loader.project_state([self.migrate_from]).apps
        User = old_apps.get_model("account", "User")
        UserSdwtProdChange = old_apps.get_model(
            "account",
            "UserSdwtProdChange",
        )
        AccessScope = old_apps.get_model("account", "AccessScope")
        Affiliation = old_apps.get_model("account", "Affiliation")
        UserAccess = old_apps.get_model("account", "UserAccess")
        UserSdwtProdAccess = old_apps.get_model("account", "UserSdwtProdAccess")
        user = User.objects.create(avatarid="MIGRATION-AFFILIATION-PENDING",
            sabun="MIGRATION-AFFILIATION-PENDING",
            username="migration-affiliation-pending",
        )
        self.user_id = user.id
        pending_rows = [
            UserSdwtProdChange.objects.create(
                user_id=user.id,
                from_user_sdwt_prod="group-old",
                to_user_sdwt_prod=f"group-{index}",
                effective_from=timezone.now() + timedelta(minutes=index),
                status="PENDING",
            )
            for index in range(3)
        ]
        self.latest_pending_id = pending_rows[-1].id
        inconsistent_approved = UserSdwtProdChange.objects.create(
            user_id=user.id,
            from_user_sdwt_prod="group-old",
            to_user_sdwt_prod="group-approved",
            effective_from=timezone.now() - timedelta(days=1),
            status="APPROVED",
            approved=False,
            applied=False,
        )
        self.inconsistent_approved_id = inconsistent_approved.id
        legacy_affiliation = Affiliation.objects.create(
            department="Migration Dept",
            line="Migration Line",
            user_sdwt_prod="migration-group",
        )
        UserSdwtProdAccess.objects.create(
            user_id=user.id,
            affiliation_id=legacy_affiliation.id,
            role="member",
        )
        emails_scope = AccessScope.objects.get(key="emails")
        UserAccess.objects.update_or_create(
            user_id=user.id,
            scope_id=emails_scope.id,
            defaults={
                "status": "allowed",
                "role": "admin",
            },
        )
        self.legacy_affiliation_id = legacy_affiliation.id

    def _restore_latest_migrations(self) -> None:
        """다른 테스트를 위해 전체 migration leaf를 복구합니다."""

        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def _fixture_teardown(self) -> None:
        """최신 스키마 복구 후 테스트 데이터를 초기 상태로 되돌립니다."""

        self._restore_latest_migrations()
        for database_name in self._databases_names(include_mirrors=False):
            database_connection = connections[database_name]
            call_command(
                "flush",
                verbosity=0,
                interactive=False,
                database=database_name,
                reset_sequences=False,
                inhibit_post_migrate=True,
            )
            serialized_contents = getattr(
                database_connection,
                "_test_serialized_contents",
                None,
            )
            if serialized_contents:
                database_connection.creation.deserialize_db_from_string(
                    serialized_contents
                )

    def test_migration_keeps_only_latest_pending_request(self) -> None:
        """최신 요청만 PENDING으로 남기고 DB 제약이 추가되는지 확인합니다."""

        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_to])
        new_apps = executor.loader.project_state([self.migrate_to]).apps
        UserSdwtProdChange = new_apps.get_model(
            "account",
            "UserSdwtProdChange",
        )
        UserAccess = new_apps.get_model("account", "UserAccess")
        UserScopeAffiliationGrant = new_apps.get_model(
            "account",
            "UserScopeAffiliationGrant",
        )
        rows = list(
            UserSdwtProdChange.objects.filter(user_id=self.user_id).order_by("id")
        )

        self.assertEqual(
            [row.id for row in rows if row.status == "PENDING"],
            [self.latest_pending_id],
        )
        self.assertTrue(
            all(
                row.status == "SUPERSEDED"
                and row.rejection_reason == "취소(중복 대기 요청 정리)"
                for row in rows
                if row.id not in {
                    self.latest_pending_id,
                    self.inconsistent_approved_id,
                }
            )
        )
        normalized_approved = UserSdwtProdChange.objects.get(
            id=self.inconsistent_approved_id,
        )
        self.assertTrue(normalized_approved.approved)
        self.assertTrue(normalized_approved.applied)
        self.assertIsNotNone(normalized_approved.approved_at)
        self.assertIsNone(normalized_approved.rejection_reason)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                UserSdwtProdChange.objects.create(
                    user_id=self.user_id,
                    from_user_sdwt_prod="group-old",
                    to_user_sdwt_prod="group-new",
                    effective_from=timezone.now(),
                    status="PENDING",
                )

        self.assertEqual(
            set(
                UserScopeAffiliationGrant.objects.filter(
                    user_id=self.user_id,
                    affiliation_id=self.legacy_affiliation_id,
                    is_active=True,
                ).values_list("scope__key", flat=True)
            ),
            {"assistant", "emails"},
        )
        self.assertEqual(
            UserAccess.objects.get(
                user_id=self.user_id,
                scope__key="emails",
            ).data_scope_mode,
            "all",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                UserSdwtProdChange.objects.create(
                    user_id=self.user_id,
                    from_user_sdwt_prod="group-old",
                    to_user_sdwt_prod="group-invalid-state",
                    effective_from=timezone.now(),
                    status="APPROVED",
                    approved=False,
                    applied=False,
                )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                UserSdwtProdChange.objects.create(
                    user_id=self.user_id,
                    from_user_sdwt_prod="group-old",
                    to_user_sdwt_prod="group-invalid-pending-metadata",
                    effective_from=timezone.now(),
                    status="REJECTED",
                    approved=False,
                    applied=False,
                    approved_at=None,
                )

class RegistrationAccessMigrationTests(TransactionTestCase):
    """실제 이전 schema에서 파생 권한을 명시적 권한으로 이관합니다."""

    def test_preserves_roles_ranges_and_department_fallback(self):
        """viewer 승급·만료 grant·정책 fallback을 보존하고 거절은 유지합니다."""
        executor = MigrationExecutor(connection)
        previous = [("account", "0006_account_authorization_system")]
        latest = [("account", "0007_separate_affiliation_access")]
        executor.migrate(previous)
        try:
            old = executor.loader.project_state(previous).apps
            User = old.get_model("account", "User")
            AffiliationModel = old.get_model("account", "Affiliation")
            Current = old.get_model("account", "UserCurrentAffiliation")
            Scope = old.get_model("account", "AccessScope")
            Role = old.get_model("account", "UserSdwtProdAccess")
            Grant = old.get_model("account", "UserScopeAffiliationGrant")
            Policy = old.get_model("account", "AccessPolicyRule")
            Access = old.get_model("account", "UserAccess")
            option = AffiliationModel.objects.create(user_sdwt_prod="MIG-A", line="L1", department="Fallback")
            user = User.objects.create(avatarid="MIG-REG", sabun="MIG-REG", department="")
            current = Current.objects.create(user=user, affiliation=option, requires_reconfirm=True)
            role = Role.objects.create(user=user, affiliation=option, role="viewer")
            portal, _ = Scope.objects.get_or_create(key="portal", defaults={"name": "Portal", "scope_type": "portal"})
            scope = Scope.objects.create(key="migration-reg", name="Migration", data_scope_type="affiliation", include_current_affiliation=True)
            denied = Scope.objects.create(key="migration-denied", name="Denied")
            for target in (portal, scope, denied):
                Policy.objects.create(scope=target, rule_type="department", value="Fallback")
            Access.objects.create(user=user, scope=denied, status="denied", role="user")
            grant = Grant.objects.create(user=user, scope=scope, affiliation=option,
                                         is_active=False, expires_at=timezone.now() - timedelta(days=1))
            executor = MigrationExecutor(connection)
            executor.migrate(latest)
            role.refresh_from_db()
            grant.refresh_from_db()
            current.refresh_from_db()
            scope.refresh_from_db()
            self.assertEqual(role.role, "member")
            self.assertTrue(grant.is_active)
            self.assertIsNone(grant.expires_at)
            self.assertFalse(current.requires_reconfirm)
            self.assertFalse(scope.include_current_affiliation)
            self.assertEqual(Access.objects.get(user=user, scope=portal).status, "allowed")
            self.assertEqual(Access.objects.get(user=user, scope=scope).status, "allowed")
            self.assertEqual(Access.objects.get(user=user, scope=denied).status, "denied")
            # 새 소속을 저장해도 이관된 범위는 이전 소속에 남습니다.
            new_option = AffiliationModel.objects.create(user_sdwt_prod="MIG-B", line="L2", department="Other")
            current.affiliation = new_option
            current.save(update_fields=["affiliation"])
            self.assertEqual(Grant.objects.get(pk=grant.pk).affiliation_id, option.pk)
            self.assertEqual(Role.objects.get(pk=role.pk).affiliation_id, option.pk)
        finally:
            restore = MigrationExecutor(connection)
            restore.migrate(restore.loader.graph.leaf_nodes())
