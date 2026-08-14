# =============================================================================
# 모듈 설명: account 도메인 서비스/셀렉터/엔드포인트 테스트를 제공합니다.
# - 주요 대상: 소속 변경, 접근 권한, 외부 동기화, 개요 응답
# - 불변 조건: 테스트는 등록된 URL 네임을 기준으로 수행합니다.
# =============================================================================

"""계정 도메인 서비스/셀렉터/엔드포인트 테스트 모음.

- 주요 대상: 소속 변경, 접근 권한, 외부 동기화, 개요 응답
- 주요 엔드포인트/클래스: AccountEndpointTests 등
- 가정/불변 조건: 테스트는 기본 URL 네임이 등록되어 있음
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
    deactivate_expired_scope_affiliation_grants,
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


def _affiliation(*, department: str = "Dept", line: str = "Line", user_sdwt_prod: str) -> Affiliation:
    """테스트용 소속 옵션을 중복 없이 준비합니다."""
    option = Affiliation.objects.filter(user_sdwt_prod__iexact=user_sdwt_prod).order_by("id").first()
    if option is not None:
        option.department = department
        option.line = line
        option.save(update_fields=["department", "line"])
        return option
    return Affiliation.objects.create(
        department=department,
        line=line,
        user_sdwt_prod=user_sdwt_prod,
    )


def _set_current_affiliation(
    user,
    *,
    user_sdwt_prod: str,
    department: str = "Dept",
    line: str = "Line",
    requires_reconfirm: bool = False,
    confirmed_at=None,
    source: str = UserCurrentAffiliation.Sources.USER_SELECTED,
) -> UserCurrentAffiliation:
    """테스트 사용자의 현재 앱 소속을 명시적으로 설정합니다."""

    option = _affiliation(department=department, line=line, user_sdwt_prod=user_sdwt_prod)
    row, _created = UserCurrentAffiliation.objects.update_or_create(
        user=user,
        defaults={
            "affiliation": option,
            "source": source,
            "requires_reconfirm": requires_reconfirm,
            "confirmed_at": confirmed_at,
        },
    )
    return row


def _grant_access(
    *,
    user,
    user_sdwt_prod: str,
    role: str,
    department: str = "Dept",
    line: str = "Line",
    granted_by=None,
) -> UserSdwtProdAccess:
    """테스트용 소속 접근 권한을 생성합니다."""

    option = _affiliation(department=department, line=line, user_sdwt_prod=user_sdwt_prod)
    return UserSdwtProdAccess.objects.create(
        user=user,
        affiliation=option,
        role=role,
        granted_by=granted_by,
    )


def _clear_permission_cache(user) -> None:
    """사용자 인스턴스의 Django permission 캐시를 제거합니다."""

    for cache_name in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
        if hasattr(user, cache_name):
            delattr(user, cache_name)


def _grant_manage_access(user):
    """테스트 사용자에게 Portal admin 역할을 부여합니다."""

    scope = AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL)
    UserAccess.objects.update_or_create(
        user=user,
        scope=scope,
        defaults={
            "status": UserAccess.Status.ALLOWED,
            "role": "admin",
        },
    )
    return user


class AccountConfigDefaultUserTests(TestCase):
    """account 앱의 migrate 후 기본 사용자 보장 로직을 검증합니다."""

    def test_ensure_default_superuser_promotes_existing_dev_dummy_user(self) -> None:
        """기존 dev dummy 사용자는 migrate 보정 시 staff 슈퍼유저가 되어야 합니다."""

        User = get_user_model()
        user = User.objects.create_user(
            sabun="S-DUMMY-EXISTING",
            password="test-password",
            knox_id="dummy.existing",
            email="old@example.com",
        )

        with patch.dict(
            "os.environ",
            {
                "ENVIRONMENT": "development",
                "DUMMY_ADFS_SABUN": "S-DUMMY-EXISTING",
                "DUMMY_ADFS_LOGINID": "dummy.existing",
                "DUMMY_ADFS_EMAIL": "dummy.existing@example.com",
                "DUMMY_ADFS_NAME": "Dummy Existing",
                "DUMMY_ADFS_DEPT": "Development",
            },
            clear=True,
        ):
            django_apps.get_app_config("account")._ensure_default_superuser()

        user.refresh_from_db()
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertEqual(user.email, "dummy.existing@example.com")
        self.assertEqual(user.username, "Dummy Existing")
        self.assertEqual(user.department, "Development")

    def test_ensure_default_superuser_creates_dev_dummy_superuser(self) -> None:
        """dev dummy 사용자가 없으면 migrate 보정 시 슈퍼유저로 생성해야 합니다."""

        with patch.dict(
            "os.environ",
            {
                "ENVIRONMENT": "development",
                "DUMMY_ADFS_SABUN": "S-DUMMY-NEW",
                "DUMMY_ADFS_LOGINID": "dummy.new",
                "DUMMY_ADFS_EMAIL": "dummy.new@example.com",
                "DUMMY_ADFS_NAME": "Dummy New",
                "DUMMY_ADFS_DEPT": "Development",
                "DJANGO_SUPERUSER_PASSWORD": "test-password",
            },
            clear=True,
        ):
            django_apps.get_app_config("account")._ensure_default_superuser()

        User = get_user_model()
        user = User.objects.get(sabun="S-DUMMY-NEW")
        self.assertEqual(user.knox_id, "dummy.new")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertEqual(user.email, "dummy.new@example.com")
        self.assertTrue(user.check_password("test-password"))

    def test_ensure_default_superuser_does_not_promote_dummy_outside_development(self) -> None:
        """development 환경이 아니면 dummy 사용자를 보정하지 않아야 합니다."""

        User = get_user_model()
        user = User.objects.create_user(
            sabun="S-DUMMY-OIDC",
            password="test-password",
            knox_id="dummy.oidc",
            email="old@example.com",
        )

        with patch.dict(
            "os.environ",
            {
                "ENVIRONMENT": "production",
                "DUMMY_ADFS_SABUN": "S-DUMMY-OIDC",
                "DUMMY_ADFS_LOGINID": "dummy.oidc",
                "DUMMY_ADFS_EMAIL": "dummy.oidc@example.com",
            },
            clear=True,
        ):
            django_apps.get_app_config("account")._ensure_default_superuser()

        user.refresh_from_db()
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(user.email, "old@example.com")


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

        user = User.objects.create(
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
        user = User.objects.create(
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


class AccessFilterParityTests(TestCase):
    """런타임 접근 판정과 관리 목록 DB 필터의 계약 동등성을 검증합니다."""

    def setUp(self) -> None:
        """모든 접근 상태·출처 우선순위를 대표하는 사용자와 scope를 준비합니다."""

        User = get_user_model()
        self.portal_scope = AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL)
        self.app_scope = AccessScope.objects.create(
            key="access-parity-app",
            name="접근 판정 동등성 앱",
            scope_type=AccessScope.ScopeTypes.APP,
        )
        self.inactive_scope = AccessScope.objects.create(
            key="access-parity-inactive",
            name="접근 판정 동등성 비활성 기능",
            scope_type=AccessScope.ScopeTypes.FEATURE,
            is_active=False,
        )
        self.users = {
            "superuser": User.objects.create_superuser(
                sabun="PARITY-SUPERUSER",
                password="test-password",
            ),
            "portal_denied": User.objects.create_user(
                sabun="PARITY-PORTAL-DENIED",
                password="test-password",
            ),
            "portal_pending": User.objects.create_user(
                sabun="PARITY-PORTAL-PENDING",
                password="test-password",
            ),
            "portal_policy": User.objects.create_user(
                sabun="PARITY-PORTAL-POLICY",
                password="test-password",
                department="Parity Portal Department",
            ),
            "portal_none": User.objects.create_user(
                sabun="PARITY-PORTAL-NONE",
                password="test-password",
            ),
            "app_denied": User.objects.create_user(
                sabun="PARITY-APP-DENIED",
                password="test-password",
            ),
            "app_allowed": User.objects.create_user(
                sabun="PARITY-APP-ALLOWED",
                password="test-password",
            ),
            "app_pending": User.objects.create_user(
                sabun="PARITY-APP-PENDING",
                password="test-password",
            ),
            "app_policy": User.objects.create_user(
                sabun="PARITY-APP-POLICY",
                password="test-password",
                department="Parity App Department",
            ),
            "app_unicode_distinct": User.objects.create_user(
                sabun="PARITY-APP-UNICODE-DISTINCT",
                password="test-password",
                department="Straße",
            ),
            "app_database_lower_equal": User.objects.create_user(
                sabun="PARITY-APP-DATABASE-LOWER-EQUAL",
                password="test-password",
                department="İ",
            ),
            "app_python_lower_false_positive": User.objects.create_user(
                sabun="PARITY-APP-PYTHON-LOWER-FALSE-POSITIVE",
                password="test-password",
                department="ΟΣ",
            ),
            "app_none": User.objects.create_user(
                sabun="PARITY-APP-NONE",
                password="test-password",
            ),
            "portal_required": User.objects.create_user(
                sabun="PARITY-PORTAL-REQUIRED",
                password="test-password",
            ),
        }
        AccessPolicyRule.objects.create(
            scope=self.portal_scope,
            rule_type=AccessPolicyRule.RuleTypes.DEPARTMENT,
            value="Parity Portal Department",
        )
        AccessPolicyRule.objects.create(
            scope=self.app_scope,
            rule_type=AccessPolicyRule.RuleTypes.DEPARTMENT,
            value="Parity App Department",
        )
        AccessPolicyRule.objects.create(
            scope=self.app_scope,
            rule_type=AccessPolicyRule.RuleTypes.DEPARTMENT,
            value="STRASSE",
        )
        AccessPolicyRule.objects.create(
            scope=self.app_scope,
            rule_type=AccessPolicyRule.RuleTypes.DEPARTMENT,
            value="I",
        )
        AccessPolicyRule.objects.create(
            scope=self.app_scope,
            rule_type=AccessPolicyRule.RuleTypes.DEPARTMENT,
            value="ος",
        )
        self._create_access("portal_denied", self.portal_scope, UserAccess.Status.DENIED)
        self._create_access("portal_pending", self.portal_scope, UserAccess.Status.PENDING)
        for user_key in (
            "app_denied",
            "app_allowed",
            "app_pending",
            "app_policy",
            "app_unicode_distinct",
            "app_database_lower_equal",
            "app_python_lower_false_positive",
            "app_none",
        ):
            self._create_access(user_key, self.portal_scope, UserAccess.Status.ALLOWED)
        self._create_access("app_denied", self.app_scope, UserAccess.Status.DENIED)
        self._create_access("app_allowed", self.app_scope, UserAccess.Status.ALLOWED)
        self._create_access("app_pending", self.app_scope, UserAccess.Status.PENDING)
        self._create_access("portal_required", self.app_scope, UserAccess.Status.ALLOWED)

    def _create_access(
        self,
        user_key: str,
        scope: AccessScope,
        status: str,
    ) -> None:
        """지정한 사용자와 scope에 명시 접근 상태를 생성합니다."""

        UserAccess.objects.create(
            user=self.users[user_key],
            scope=scope,
            status=status,
            role="user",
        )

    def test_runtime_payload_and_database_filter_return_identical_user_sets(self) -> None:
        """상태·출처 단독/조합 필터가 런타임 판정과 같은 사용자를 반환해야 합니다."""

        user_ids = {user.id for user in self.users.values()}
        base_queryset = list_access_management_users(
            search=None,
            department=None,
        ).filter(id__in=user_ids)

        for scope in (self.portal_scope, self.app_scope, self.inactive_scope):
            expected_payloads = {
                user.id: get_access_payload(user=user, scope_key=scope.key)
                for user in self.users.values()
            }
            if scope == self.app_scope:
                database_equal_payload = expected_payloads[
                    self.users["app_database_lower_equal"].id
                ]
                python_false_positive_payload = expected_payloads[
                    self.users["app_python_lower_false_positive"].id
                ]
                self.assertTrue(database_equal_payload["allowed"])
                self.assertEqual(
                    database_equal_payload["source"],
                    AccessSource.POLICY_DEPARTMENT,
                )
                self.assertFalse(python_false_positive_payload["allowed"])
                self.assertEqual(
                    python_false_positive_payload["source"],
                    AccessSource.NONE,
                )
            statuses = {
                str(payload["effectiveStatus"])
                for payload in expected_payloads.values()
            }
            sources = {
                str(payload["source"])
                for payload in expected_payloads.values()
            }
            expected_contract = {
                self.portal_scope.key: (
                    {"allowed", "denied", "pending", "not_requested"},
                    {
                        "superuser_bypass",
                        "explicit_denied",
                        "explicit_allowed",
                        "explicit_pending",
                        "policy_department",
                        "none",
                    },
                ),
                self.app_scope.key: (
                    {"allowed", "denied", "pending", "not_requested"},
                    {
                        "superuser_bypass",
                        "portal_access_required",
                        "explicit_denied",
                        "explicit_allowed",
                        "explicit_pending",
                        "policy_department",
                        "none",
                    },
                ),
                self.inactive_scope.key: (
                    {"allowed", "denied", "inactive"},
                    {
                        "superuser_bypass",
                        "portal_access_required",
                        "scope_inactive",
                    },
                ),
            }
            expected_statuses, expected_sources = expected_contract[scope.key]
            self.assertEqual(statuses, expected_statuses)
            self.assertEqual(sources, expected_sources)

            for status in statuses:
                with self.subTest(scope=scope.key, status=status):
                    expected_ids = {
                        user_id
                        for user_id, payload in expected_payloads.items()
                        if payload["effectiveStatus"] == status
                    }
                    actual_ids = set(
                        filter_access_management_users_by_effective_access(
                            queryset=base_queryset,
                            scope=scope,
                            status=status,
                            source=None,
                        ).values_list("id", flat=True)
                    )
                    self.assertEqual(actual_ids, expected_ids)

            for source in sources:
                with self.subTest(scope=scope.key, source=source):
                    expected_ids = {
                        user_id
                        for user_id, payload in expected_payloads.items()
                        if payload["source"] == source
                    }
                    actual_ids = set(
                        filter_access_management_users_by_effective_access(
                            queryset=base_queryset,
                            scope=scope,
                            status=None,
                            source=source,
                        ).values_list("id", flat=True)
                    )
                    self.assertEqual(actual_ids, expected_ids)

            for status, source in {
                (str(payload["effectiveStatus"]), str(payload["source"]))
                for payload in expected_payloads.values()
            }:
                with self.subTest(scope=scope.key, status=status, source=source):
                    expected_ids = {
                        user_id
                        for user_id, payload in expected_payloads.items()
                        if payload["effectiveStatus"] == status
                        and payload["source"] == source
                    }
                    actual_ids = set(
                        filter_access_management_users_by_effective_access(
                            queryset=base_queryset,
                            scope=scope,
                            status=status,
                            source=source,
                        ).values_list("id", flat=True)
                    )
                    self.assertEqual(actual_ids, expected_ids)

    def test_inactive_portal_scope_blocks_explicitly_allowed_app_access(self) -> None:
        """Portal scope가 비활성이면 app 명시 허용도 최종 접근으로 인정하지 않습니다."""

        self.portal_scope.is_active = False
        self.portal_scope.save(update_fields=["is_active"])
        app_allowed_user = self.users["app_allowed"]
        superuser = self.users["superuser"]
        base_queryset = list_access_management_users(
            search=None,
            department=None,
        ).filter(id__in=[app_allowed_user.id, superuser.id])

        blocked_ids = set(
            filter_access_management_users_by_effective_access(
                queryset=base_queryset,
                scope=self.app_scope,
                status="denied",
                source=AccessSource.PORTAL_ACCESS_REQUIRED,
            ).values_list("id", flat=True)
        )
        bypass_ids = set(
            filter_access_management_users_by_effective_access(
                queryset=base_queryset,
                scope=self.app_scope,
                status="allowed",
                source=AccessSource.SUPERUSER_BYPASS,
            ).values_list("id", flat=True)
        )

        self.assertEqual(blocked_ids, {app_allowed_user.id})
        self.assertEqual(bypass_ids, {superuser.id})


class AccountEndpointTests(TestCase):
    """계정 관련 엔드포인트의 기본 흐름을 검증합니다."""

    def setUp(self) -> None:
        """테스트에 필요한 사용자/권한/소속 데이터를 준비합니다."""
        # -----------------------------------------------------------------------------
        # 1) 기본 사용자 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        self.user = User.objects.create_user(sabun="S50000", password="test-password")
        self.user.knox_id = "knox-50000"
        self.user.department = "Dept"
        self.user.save(update_fields=["knox_id", "department"])
        scope, _created = AccessScope.objects.get_or_create(
            key=ACCESS_SCOPE_PORTAL,
            defaults={"name": "Portal", "scope_type": AccessScope.ScopeTypes.PORTAL},
        )
        AccessPolicyRule.objects.update_or_create(
            scope=scope,
            rule_type=AccessPolicyRule.RuleTypes.DEPARTMENT,
            value="Dept",
            defaults={"is_active": True},
        )
        _set_current_affiliation(
            self.user,
            department="Dept",
            line="L1",
            user_sdwt_prod="group-a",
        )

        # -----------------------------------------------------------------------------
        # 2) 매니저/접근 권한 준비
        # -----------------------------------------------------------------------------
        self.manager = User.objects.create_user(
            sabun="S50001",
            password="test-password",
            knox_id="knox-50001",
            department="Dept",
        )
        _set_current_affiliation(self.manager, user_sdwt_prod="group-b")
        _grant_access(user=self.manager, user_sdwt_prod="group-a", role="manager")
        _grant_access(user=self.manager, user_sdwt_prod="group-b", role="manager")

        # -----------------------------------------------------------------------------
        # 3) 슈퍼유저/소속 옵션 준비
        # -----------------------------------------------------------------------------
        self.superuser = User.objects.create_superuser(
            sabun="S50002",
            password="test-password",
            knox_id="knox-50002",
        )

        _affiliation(department="Dept", line="L1", user_sdwt_prod="group-a")
        _affiliation(department="Dept", line="L1", user_sdwt_prod="group-b")

    def test_default_app_access_scopes_are_seeded(self) -> None:
        """포털 내부 앱의 기본 접근 scope와 공통 속성을 검증합니다."""

        expected_scopes = {
            "access-stats": "접속 현황",
            "appstore": "Appstore",
            "assistant": "Assistant",
            "emails": "Emails",
            "l0-spider": "L0 Spider",
            "l1-spider": "L1 Spider",
            "l3-spider": "L3 Spider",
            "line-dashboard": "ESOP Dashboard",
            "observer": "Observer",
            "pm-spider": "PM Spider",
            "teamstaff": "Teamstaff",
            "tttm-spider": "TTTM Spider",
            "voc": "VoE",
            "work-hub": "설비 업무일지",
        }
        scopes = AccessScope.objects.filter(scope_type=AccessScope.ScopeTypes.APP).order_by("key")

        self.assertEqual({scope.key: scope.name for scope in scopes}, expected_scopes)
        for scope in scopes:
            with self.subTest(scope=scope.key):
                self.assertTrue(scope.is_active)
                self.assertTrue(scope.requestable)

    def test_new_user_does_not_receive_automatic_app_access(self) -> None:
        """마이그레이션 이후 생성된 신규 사용자는 앱 허용 행을 자동 생성하지 않아야 합니다."""

        User = get_user_model()
        new_user = User.objects.create_user(
            sabun="S-NEW-ACCESS",
            password="test-password",
            department="New Department",
        )

        self.assertFalse(
            UserAccess.objects.filter(
                user=new_user,
                scope__scope_type=AccessScope.ScopeTypes.APP,
            ).exists()
        )
        payload = get_access_payload(user=new_user, scope_key="appstore")
        self.assertFalse(payload["allowed"])
        self.assertEqual(payload["source"], AccessSource.PORTAL_ACCESS_REQUIRED)
        self.assertTrue(payload["blockedByPortal"])
        self.assertEqual(payload["underlyingAccess"]["source"], AccessSource.NONE)

    def test_app_scope_is_self_requestable(self) -> None:
        """앱 권한은 사용자가 직접 신청할 수 있어야 합니다."""

        payload, status_code = request_access(user=self.user, scope_keys=["appstore"])

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["status"], "pending")
        self.assertEqual(
            payload["accesses"]["appstore"]["source"],
            AccessSource.EXPLICIT_PENDING,
        )
        self.assertFalse(payload["accesses"]["appstore"]["blockedByPortal"])
        self.assertIsNone(payload["accesses"]["appstore"]["underlyingAccess"])
        self.assertNotIn("requestId", payload["accesses"]["appstore"])
        access = UserAccess.objects.get(user=self.user, scope__key="appstore")
        self.assertEqual(access.status, UserAccess.Status.PENDING)

    def test_app_access_request_endpoint_creates_pending_request(self) -> None:
        """현재 사용자 앱 접근 신청 API가 pending 요청을 생성하는지 확인합니다."""

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("account-access-request"),
            data='{"scopes":["appstore"]}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "pending")
        self.assertTrue(
            UserAccess.objects.filter(
                user=self.user,
                scope__key="appstore",
                status=UserAccess.Status.PENDING,
            ).exists()
        )

    def test_access_request_endpoint_creates_multiple_pending_rows_atomically(self) -> None:
        """여러 앱과 필요한 Portal 요청을 한 번에 pending으로 저장해야 합니다."""

        _set_current_affiliation(
            self.user,
            department="OtherDept",
            line="L1",
            user_sdwt_prod="group-a",
        )
        self.user.department = "OtherDept"
        self.user.save(update_fields=["department"])
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("account-access-request"),
            data='{"scopes":["appstore","voc"]}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(response.json()["accesses"]),
            {ACCESS_SCOPE_PORTAL, "appstore", "voc"},
        )
        self.assertEqual(
            set(
                UserAccess.objects.filter(user=self.user).values_list(
                    "scope__key",
                    flat=True,
                )
            ),
            {ACCESS_SCOPE_PORTAL, "appstore", "voc"},
        )
        self.assertFalse(
            UserAccess.objects.filter(user=self.user).exclude(
                status=UserAccess.Status.PENDING,
                role="user",
            ).exists()
        )

    def test_access_request_endpoint_rolls_back_all_scopes_on_invalid_scope(self) -> None:
        """요청 목록에 잘못된 scope가 하나라도 있으면 어떤 행도 저장하지 않아야 합니다."""

        self.client.force_login(self.user)

        response = self.client.post(
            reverse("account-access-request"),
            data='{"scopes":["appstore","missing-scope"]}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(UserAccess.objects.filter(user=self.user).exists())

    def test_access_request_endpoint_rejects_legacy_scope_field(self) -> None:
        """제거된 단일 scope 요청 계약을 명시적으로 거절해야 합니다."""

        self.client.force_login(self.user)

        response = self.client.post(
            reverse("account-access-request"),
            data='{"scope":"appstore"}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["details"]["unexpectedFields"],
            ["scope"],
        )

    def test_fixed_role_migration_removes_legacy_access_manager_permission(self) -> None:
        """고정 역할 migration 이후 legacy 그룹과 permission이 남지 않아야 합니다."""

        self.assertFalse(Group.objects.filter(name="Access Managers").exists())
        self.assertFalse(
            Permission.objects.filter(
                content_type__app_label="account",
                codename="manage_access",
            ).exists()
        )

    def test_scope_and_policy_models_do_not_store_automatic_roles(self) -> None:
        """자동 경로에는 role 컬럼이 없고 사용자별 접근만 role을 저장해야 합니다."""

        scopes = AccessScope.objects.filter(
            key__in=("l0-spider", "l1-spider", "l3-spider"),
        )
        self.assertEqual(scopes.count(), 3)
        self.assertNotIn("default_role", {field.name for field in AccessScope._meta.fields})
        self.assertNotIn("role", {field.name for field in AccessPolicyRule._meta.fields})
        self.assertIn("role", {field.name for field in UserAccess._meta.fields})

    def test_access_source_contract_uses_explicit_stable_values(self) -> None:
        """접근 판정 source 값은 API 계약에 사용하는 명시적 목록으로 고정되어야 합니다."""

        self.assertEqual(
            set(AccessSource.values),
            {
                "superuser_bypass",
                "portal_access_required",
                "scope_inactive",
                "explicit_denied",
                "explicit_allowed",
                "explicit_pending",
                "policy_department",
                "none",
                "scope_not_found",
            },
        )

    def test_user_access_accepts_fixed_admin_role_and_rejects_unknown_role(self) -> None:
        """사용자별 접근은 admin을 허용하고 정의되지 않은 역할을 거부해야 합니다."""

        scope = AccessScope.objects.get(key="appstore")
        policy = AccessPolicyRule(
            scope=scope,
            rule_type=AccessPolicyRule.RuleTypes.DEPARTMENT,
            value="Role Validation Dept",
        )
        access = UserAccess(
            scope=scope,
            user=self.user,
            status=UserAccess.Status.ALLOWED,
            role="admin",
        )

        policy.full_clean()
        access.full_clean()
        access.role = "owner"
        with self.assertRaises(ValidationError):
            access.full_clean()

        requestable_scope = AccessScope(
            key="requestable-app",
            name="Requestable App",
            scope_type=AccessScope.ScopeTypes.APP,
            requestable=True,
        )
        requestable_scope.full_clean()

    def test_non_portal_feature_scope_requires_portal_access(self) -> None:
        """feature scope도 앱과 동일하게 Portal 접근을 필수 선행 조건으로 사용해야 합니다."""

        portal_scope = AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL)
        feature_scope = AccessScope.objects.create(
            key="feature-report-export",
            name="보고서 내보내기",
            scope_type=AccessScope.ScopeTypes.FEATURE,
        )
        UserAccess.objects.create(
            scope=portal_scope,
            user=self.user,
            status=UserAccess.Status.ALLOWED,
            role="user",
        )
        UserAccess.objects.create(
            scope=feature_scope,
            user=self.user,
            status=UserAccess.Status.ALLOWED,
            role="admin",
        )

        self.assertTrue(
            has_scope_role(
                user=self.user,
                scope_key=feature_scope.key,
                required_role="admin",
            )
        )
        UserAccess.objects.filter(scope=portal_scope, user=self.user).update(
            status=UserAccess.Status.DENIED
        )
        payload = get_access_payload(user=self.user, scope_key=feature_scope.key)

        self.assertFalse(payload["allowed"])
        self.assertTrue(payload["blockedByPortal"])
        self.assertEqual(payload["source"], AccessSource.PORTAL_ACCESS_REQUIRED)
        self.assertFalse(
            has_scope_role(
                user=self.user,
                scope_key=feature_scope.key,
                required_role="admin",
            )
        )

    def test_access_scope_database_rejects_noncanonical_portal_and_invalid_key(self) -> None:
        """DB는 canonical Portal 중복과 표준 형식이 아닌 scope key를 거부해야 합니다."""

        invalid_rows = (
            {
                "key": "secondary-portal",
                "name": "보조 Portal",
                "scope_type": AccessScope.ScopeTypes.PORTAL,
            },
            {
                "key": "Invalid Scope",
                "name": "잘못된 Key",
                "scope_type": AccessScope.ScopeTypes.FEATURE,
            },
        )
        for values in invalid_rows:
            with self.subTest(values=values):
                with self.assertRaises(IntegrityError):
                    with transaction.atomic():
                        AccessScope.objects.create(**values)

        portal_scope = AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AccessScope.objects.filter(pk=portal_scope.pk).update(
                    scope_type=AccessScope.ScopeTypes.APP
                )

    def test_scope_role_resolver_reuses_batch_queries_within_request(self) -> None:
        """한 요청에서 여러 역할 검사는 동일한 일괄 조회 결과를 재사용해야 합니다."""

        feature_scope = AccessScope.objects.create(
            key="feature-query-cache",
            name="역할 조회 캐시",
            scope_type=AccessScope.ScopeTypes.FEATURE,
        )
        for scope, role in (
            (AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL), "user"),
            (AccessScope.objects.get(key="appstore"), "admin"),
            (feature_scope, "admin"),
        ):
            UserAccess.objects.create(
                scope=scope,
                user=self.user,
                status=UserAccess.Status.ALLOWED,
                role=role,
            )
        request = RequestFactory().get("/api/v1/appstore/apps")

        with self.assertNumQueries(3):
            portal_payload = get_access_payload(
                user=self.user,
                scope_key=ACCESS_SCOPE_PORTAL,
                request=request,
            )
            app_payload = get_access_payload(
                user=self.user,
                scope_key="appstore",
                request=request,
            )
            self.assertTrue(portal_payload["allowed"])
            self.assertTrue(app_payload["allowed"])
            self.assertTrue(
                has_scope_role(
                    user=self.user,
                    scope_key="appstore",
                    request=request,
                )
            )
            self.assertTrue(
                has_scope_role(
                    user=self.user,
                    scope_key=feature_scope.key,
                    request=request,
                )
            )

    def test_scope_access_auth_payload_uses_constant_batch_queries(self) -> None:
        """auth scope map은 scope 수와 관계없이 세 번의 일괄 조회로 계산해야 합니다."""

        for index in range(3):
            AccessScope.objects.create(
                key=f"feature-auth-query-{index}",
                name=f"Auth Query {index}",
                scope_type=AccessScope.ScopeTypes.FEATURE,
            )

        with self.assertNumQueries(3):
            payloads = get_scope_access_payloads(user=self.user)

        self.assertIn(ACCESS_SCOPE_PORTAL, payloads)
        self.assertIn("feature-auth-query-2", payloads)

    def test_scope_access_auth_payload_includes_inactive_scope_only_for_superuser(
        self,
    ) -> None:
        """비활성 scope는 일반 사용자에게 숨기고 superuser 비상 접근에는 노출해야 합니다."""

        inactive_scope = AccessScope.objects.create(
            key="inactive-auth-scope",
            name="비활성 Auth Scope",
            scope_type=AccessScope.ScopeTypes.FEATURE,
            is_active=False,
        )

        user_payloads = get_scope_access_payloads(user=self.user)
        superuser_payloads = get_scope_access_payloads(user=self.superuser)

        self.assertNotIn(inactive_scope.key, user_payloads)
        inactive_access = superuser_payloads[inactive_scope.key]
        self.assertTrue(inactive_access["allowed"])
        self.assertEqual(inactive_access["role"], AccessRole.ADMIN)
        self.assertEqual(inactive_access["source"], AccessSource.SUPERUSER_BYPASS)

    def test_user_access_database_rejects_unknown_status(self) -> None:
        """UserAccess status는 DB에서도 pending/allowed/denied 외 값을 거부해야 합니다."""

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                UserAccess.objects.create(
                    scope=AccessScope.objects.get(key="appstore"),
                    user=self.user,
                    status="unknown",
                )

    def test_account_admin_blocks_non_superuser_privilege_escalation(self) -> None:
        """일반 staff는 민감 권한 필드와 privileged user를 변경하지 못해야 합니다."""

        from django.contrib.admin.sites import AdminSite
        from django.test import RequestFactory

        from api.account.admin import AccountUserAdmin

        User = get_user_model()
        staff_user = self.manager
        staff_user.is_staff = True
        staff_user.save(update_fields=["is_staff"])
        staff_user.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="account",
                codename__in=("change_user", "delete_user"),
            )
        )
        _clear_permission_cache(staff_user)
        request = RequestFactory().get("/admin/account/user/")
        request.user = staff_user
        user_admin = AccountUserAdmin(User, AdminSite())

        readonly_fields = set(user_admin.get_readonly_fields(request, self.user))
        self.assertTrue({"is_staff", "is_superuser", "groups", "user_permissions"} <= readonly_fields)
        self.assertTrue(user_admin.has_change_permission(request, self.user))
        self.assertFalse(user_admin.has_delete_permission(request, self.user))

        _grant_manage_access(self.user)

        self.assertFalse(user_admin.has_change_permission(request, self.user))
        self.assertFalse(user_admin.has_delete_permission(request, self.user))
        self.assertFalse(user_admin.has_change_permission(request, self.superuser))

        superuser_request = RequestFactory().get("/admin/account/user/")
        superuser_request.user = self.superuser
        superuser_readonly_fields = set(user_admin.get_readonly_fields(superuser_request, self.user))
        self.assertFalse(
            {"is_staff", "is_superuser", "groups", "user_permissions"}
            & superuser_readonly_fields
        )
        self.assertTrue(user_admin.has_change_permission(superuser_request, self.user))
        self.assertFalse(user_admin.has_delete_permission(superuser_request, self.user))

    def test_group_admin_is_superuser_only(self) -> None:
        """Django Group 변경은 superuser에게만 허용되어야 합니다."""

        from django.contrib.admin.sites import AdminSite
        from django.test import RequestFactory

        from api.account.admin import AccountGroupAdmin

        staff_user = self.manager
        staff_user.is_staff = True
        staff_user.save(update_fields=["is_staff"])
        staff_user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="auth",
                codename="change_group",
            )
        )
        _clear_permission_cache(staff_user)
        group_admin = AccountGroupAdmin(Group, AdminSite())
        other_group = Group.objects.create(name="Other Operators")
        staff_request = RequestFactory().get("/admin/auth/group/")
        staff_request.user = staff_user
        superuser_request = RequestFactory().get("/admin/auth/group/")
        superuser_request.user = self.superuser

        self.assertFalse(group_admin.has_add_permission(staff_request))
        self.assertFalse(group_admin.has_change_permission(staff_request, other_group))
        self.assertFalse(group_admin.has_delete_permission(staff_request, other_group))
        self.assertTrue(group_admin.has_add_permission(superuser_request))
        self.assertTrue(group_admin.has_change_permission(superuser_request, other_group))
        self.assertTrue(group_admin.has_delete_permission(superuser_request, other_group))

    def test_access_model_admin_write_contract(self) -> None:
        """scope만 superuser가 관리하고 정책과 사용자 접근은 Admin에서 읽기 전용이어야 합니다."""

        from django.contrib.admin.sites import AdminSite
        from django.test import RequestFactory

        from api.account.admin import AccessPolicyRuleAdmin, AccessScopeAdmin, UserAccessAdmin

        staff_user = self.manager
        staff_user.is_staff = True
        staff_user.save(update_fields=["is_staff"])
        staff_user.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="account",
                codename__in=(
                    "add_accessscope",
                    "change_accessscope",
                    "delete_accessscope",
                    "add_accesspolicyrule",
                    "change_accesspolicyrule",
                    "delete_accesspolicyrule",
                    "add_useraccess",
                    "change_useraccess",
                    "delete_useraccess",
                ),
            )
        )
        _clear_permission_cache(staff_user)
        scope = AccessScope.objects.get(key="appstore")
        policy = AccessPolicyRule.objects.create(
            scope=scope,
            rule_type=AccessPolicyRule.RuleTypes.DEPARTMENT,
            value="Admin Security Dept",
        )
        access = UserAccess.objects.create(
            scope=scope,
            user=self.user,
            status=UserAccess.Status.ALLOWED,
            role="user",
        )
        site = AdminSite()
        scope_admin = AccessScopeAdmin(AccessScope, site)
        readonly_admin_objects = (
            (AccessPolicyRuleAdmin(AccessPolicyRule, site), policy),
            (UserAccessAdmin(UserAccess, site), access),
        )
        staff_request = RequestFactory().get("/admin/account/")
        staff_request.user = staff_user
        superuser_request = RequestFactory().get("/admin/account/")
        superuser_request.user = self.superuser

        self.assertFalse(scope_admin.has_add_permission(staff_request))
        self.assertFalse(scope_admin.has_change_permission(staff_request, scope))
        self.assertFalse(scope_admin.has_delete_permission(staff_request, scope))
        self.assertFalse(scope_admin.has_add_permission(superuser_request))
        self.assertTrue(scope_admin.has_change_permission(superuser_request, scope))
        self.assertFalse(scope_admin.has_delete_permission(superuser_request, scope))

        for model_admin, obj in readonly_admin_objects:
            with self.subTest(model=obj._meta.label_lower):
                self.assertFalse(model_admin.has_add_permission(staff_request))
                self.assertFalse(model_admin.has_change_permission(staff_request, obj))
                self.assertFalse(model_admin.has_delete_permission(staff_request, obj))
                self.assertFalse(model_admin.has_add_permission(superuser_request))
                self.assertFalse(model_admin.has_change_permission(superuser_request, obj))
                self.assertFalse(model_admin.has_delete_permission(superuser_request, obj))

    def test_affiliation_admin_write_paths_use_services_only(self) -> None:
        """소속 기준점과 변경 요청은 Admin 직접 저장을 허용하지 않아야 합니다."""

        from django.contrib.admin.sites import AdminSite

        from api.account.admin import (
            AffiliationAdmin,
            UserCurrentAffiliationAdmin,
            UserSdwtProdChangeAdmin,
        )

        request = RequestFactory().post("/admin/account/")
        request.user = self.superuser
        affiliation = _affiliation(user_sdwt_prod="admin-protected-group")
        current = _set_current_affiliation(
            self.user,
            user_sdwt_prod=affiliation.user_sdwt_prod,
        )
        change = UserSdwtProdChange.objects.create(
            user=self.user,
            from_user_sdwt_prod=affiliation.user_sdwt_prod,
            to_user_sdwt_prod="admin-protected-target",
            effective_from=timezone.now(),
        )
        site = AdminSite()
        affiliation_admin = AffiliationAdmin(Affiliation, site)
        current_admin = UserCurrentAffiliationAdmin(
            UserCurrentAffiliation,
            site,
        )
        change_admin = UserSdwtProdChangeAdmin(UserSdwtProdChange, site)

        self.assertIn(
            "user_sdwt_prod",
            affiliation_admin.get_readonly_fields(request, affiliation),
        )
        self.assertIn(
            "is_active",
            affiliation_admin.get_readonly_fields(request, affiliation),
        )
        self.assertFalse(
            affiliation_admin.has_change_permission(request, affiliation)
        )
        self.assertTrue(affiliation_admin.has_change_permission(request))
        self.assertFalse(affiliation_admin.has_delete_permission(request, affiliation))
        with self.assertRaises(ValidationError):
            affiliation_admin.save_model(
                request,
                affiliation,
                form=None,
                change=True,
            )

        self.assertFalse(current_admin.has_add_permission(request))
        self.assertFalse(current_admin.has_change_permission(request, current))
        self.assertFalse(current_admin.has_delete_permission(request, current))

        self.assertFalse(change_admin.has_add_permission(request))
        self.assertFalse(change_admin.has_change_permission(request, change))
        self.assertFalse(change_admin.has_delete_permission(request, change))
        self.assertTrue(change_admin.has_change_permission(request))
        with self.assertRaises(PermissionDenied):
            change_admin.save_model(request, change, form=None, change=True)

    def test_affiliation_admin_bulk_action_is_atomic_and_uses_operator_reason(self) -> None:
        """소속 Admin 일괄 action은 입력 사유로 한 번의 서비스 호출을 수행해야 합니다."""

        from django.contrib.admin.sites import AdminSite

        from api.account.admin import AffiliationAdmin

        first = _affiliation(user_sdwt_prod="admin-action-first")
        second = _affiliation(user_sdwt_prod="admin-action-second")
        request = RequestFactory().post(
            "/admin/account/affiliation/",
            data={"reason": "조직 개편으로 일괄 중지"},
        )
        request.user = self.superuser
        model_admin = AffiliationAdmin(Affiliation, AdminSite())

        self.assertTrue(model_admin.action_form.base_fields["reason"].required)
        with (
            patch.object(model_admin, "message_user") as message_user,
            patch(
                "api.account.admin.services.set_affiliations_active",
                wraps=set_affiliations_active,
            ) as bulk_service,
        ):
            model_admin.deactivate_affiliations(
                request,
                Affiliation.objects.filter(id__in=[second.id, first.id]),
            )

        bulk_service.assert_called_once()
        self.assertEqual(
            bulk_service.call_args.kwargs["affiliation_ids"],
            [first.id, second.id],
        )
        self.assertEqual(
            bulk_service.call_args.kwargs["reason"],
            "조직 개편으로 일괄 중지",
        )
        self.assertFalse(
            Affiliation.objects.filter(
                id__in=[first.id, second.id],
                is_active=True,
            ).exists()
        )
        self.assertEqual(
            AccessAuditLog.objects.filter(
                affiliation_id__in=[first.id, second.id],
                action=AccessAuditLog.Actions.AFFILIATION_DEACTIVATE,
                reason="조직 개편으로 일괄 중지",
            ).count(),
            2,
        )
        message_user.assert_called_once()

    def test_affiliation_admin_create_uses_audited_service(self) -> None:
        """소속 Admin 생성 폼은 입력 사유를 생성 감사 로그에 전달해야 합니다."""

        from django.contrib.admin.sites import AdminSite

        from api.account.admin import AffiliationAdmin

        request = RequestFactory().post("/admin/account/affiliation/add/")
        request.user = self.superuser
        model_admin = AffiliationAdmin(Affiliation, AdminSite())
        form = model_admin.get_form(request)(
            data={
                "department": "Admin Create Dept",
                "line": "Admin Create Line",
                "user_sdwt_prod": "admin-form-created",
                "reason": "Admin 생성 경로 검증",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        option = form.save(commit=False)

        model_admin.save_model(
            request,
            option,
            form=form,
            change=False,
        )

        self.assertIsNotNone(option.pk)
        audit = AccessAuditLog.objects.get(
            affiliation=option,
            action=AccessAuditLog.Actions.AFFILIATION_CREATE,
        )
        self.assertEqual(audit.actor_id, self.superuser.id)
        self.assertEqual(audit.reason, "Admin 생성 경로 검증")

    def test_portal_admin_role_is_manage_access_source(self) -> None:
        """Portal admin 역할만으로 접근 관리 권한을 획득해야 합니다."""

        self.assertFalse(can_manage_access(user=self.user))
        _grant_manage_access(self.user)
        self.assertTrue(can_manage_access(user=self.user))

    def test_account_overview_and_affiliation_endpoints(self) -> None:
        """개요/소속/옵션 엔드포인트가 정상 응답하는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 로그인
        # -----------------------------------------------------------------------------
        self.client.force_login(self.user)

        # -----------------------------------------------------------------------------
        # 2) 개요 조회 및 검증
        # -----------------------------------------------------------------------------
        overview = self.client.get(reverse("account-overview"))
        self.assertEqual(overview.status_code, 200)
        self.assertEqual(overview.json()["user"]["userSdwtProd"], "group-a")

        # -----------------------------------------------------------------------------
        # 3) 소속 조회 및 검증
        # -----------------------------------------------------------------------------
        affiliation = self.client.get(reverse("account-affiliation"))
        self.assertEqual(affiliation.status_code, 200)

        # -----------------------------------------------------------------------------
        # 4) 옵션 조회 및 검증
        # -----------------------------------------------------------------------------
        options = self.client.get(reverse("account-line-sdwt-options"))
        self.assertEqual(options.status_code, 200)
        self.assertIn("lines", options.json())

    def test_onboarding_affiliation_post_auto_applies_external_match(self) -> None:
        """신규 사용자가 외부 예측 소속과 같은 값을 선택하면 즉시 적용되는지 확인합니다."""

        User = get_user_model()
        onboarding_user = User.objects.create_user(
            sabun="S50009",
            password="test-password",
            knox_id="knox-50009",
        )
        ExternalAffiliationSnapshot.objects.create(
            knox_id="knox-50009",
            department="Dept",
            predicted_user_sdwt_prod="GROUP-B",
            source_updated_at=timezone.now(),
            last_seen_at=timezone.now(),
        )

        self.client.force_login(onboarding_user)
        response = self.client.post(
            reverse("account-affiliation"),
            data='{"userSdwtProd":"group-b"}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "applied")
        self.assertEqual(get_current_user_sdwt_prod(user=onboarding_user), "group-b")
        change = UserSdwtProdChange.objects.get(user=onboarding_user)
        self.assertEqual(change.status, UserSdwtProdChange.Status.APPROVED)

    def test_account_user_pool_requires_authentication(self) -> None:
        """사용자 pool 조회는 인증된 사용자에게만 허용되어야 합니다."""

        response = self.client.get(reverse("account-users"))

        self.assertEqual(response.status_code, 401)

    def test_account_user_pool_filters_by_search_and_group(self) -> None:
        """사용자 pool 조회가 검색어와 user_sdwt_prod 필터를 적용하는지 확인합니다."""

        User = get_user_model()
        searched_user = User.objects.create_user(
            sabun="S50003",
            password="test-password",
            knox_id="knox-50003",
            email="searched@example.com",
            username="검색대상",
        )
        _set_current_affiliation(searched_user, user_sdwt_prod="group-a")
        group_user = User.objects.create_user(
            sabun="S50004",
            password="test-password",
            knox_id="knox-50004",
            email="group@example.com",
            username="그룹대상",
        )
        _set_current_affiliation(group_user, user_sdwt_prod="group-b")

        self.client.force_login(self.user)
        search_response = self.client.get(reverse("account-users"), {"search": "검색대상"})
        group_response = self.client.get(reverse("account-users"), {"userSdwtProd": "group-b"})

        self.assertEqual(search_response.status_code, 200)
        search_ids = {row["id"] for row in search_response.json()["results"]}
        self.assertIn(searched_user.id, search_ids)
        self.assertNotIn(group_user.id, search_ids)

        self.assertEqual(group_response.status_code, 200)
        group_ids = {row["id"] for row in group_response.json()["results"]}
        self.assertIn(group_user.id, group_ids)
        self.assertNotIn(searched_user.id, group_ids)

    def test_account_user_pool_filters_by_contact_field(self) -> None:
        """사용자 pool 조회가 요청한 연락처 보유 사용자만 반환하는지 확인합니다."""

        User = get_user_model()
        email_user = User.objects.create_user(
            sabun="S50006",
            password="test-password",
            knox_id="knox-50006",
            email="with-email@example.com",
            username="메일있음",
        )
        _set_current_affiliation(email_user, user_sdwt_prod="group-a")
        no_email_user = User.objects.create_user(
            sabun="S50007",
            password="test-password",
            knox_id="knox-50007",
            username="메일없음",
        )
        _set_current_affiliation(no_email_user, user_sdwt_prod="group-a")

        self.client.force_login(self.user)
        response = self.client.get(
            reverse("account-users"),
            {"userSdwtProd": "group-a", "contactField": "email", "limit": "all"},
        )

        self.assertEqual(response.status_code, 200)
        user_ids = {row["id"] for row in response.json()["results"]}
        self.assertIn(email_user.id, user_ids)
        self.assertNotIn(no_email_user.id, user_ids)

    def test_account_user_pool_can_include_external_snapshot_users(self) -> None:
        """수신인 선택용 사용자 pool이 미가입 외부 스냅샷 사용자를 함께 반환하는지 확인합니다."""

        now = timezone.now()
        ExternalAffiliationSnapshot.objects.create(
            knox_id="external-50008",
            department="ExtDept",
            predicted_user_sdwt_prod="external-group",
            source_updated_at=now,
            last_seen_at=now,
        )

        self.client.force_login(self.user)
        default_response = self.client.get(reverse("account-users"), {"search": "external-50008"})
        include_response = self.client.get(
            reverse("account-users"),
            {
                "search": "external-50008",
                "contactField": "email",
                "includeExternalSnapshots": "true",
            },
        )

        self.assertEqual(default_response.status_code, 200)
        self.assertEqual(default_response.json()["results"], [])

        self.assertEqual(include_response.status_code, 200)
        payload = include_response.json()
        self.assertIn("external-group", payload["userSdwtProds"])
        self.assertEqual(len(payload["results"]), 1)
        row = payload["results"][0]
        self.assertEqual(row["recipientType"], "external")
        self.assertEqual(row["recipientKey"], "external:external-50008")
        self.assertIsNone(row["userId"])
        self.assertEqual(row["knoxId"], "external-50008")
        self.assertEqual(row["email"], "external-50008@samsung.com")
        self.assertEqual(row["userSdwtProd"], "external-group")

    def test_account_user_pool_filters_by_department_before_group(self) -> None:
        """사용자 pool 조회가 department 기준 소속 후보와 사용자 결과를 좁히는지 확인합니다."""

        User = get_user_model()
        now = timezone.now()
        target_user = User.objects.create_user(
            sabun="S52001",
            password="test-password",
            knox_id="knox-52001",
            email="target@example.com",
            username="대상사용자",
        )
        _set_current_affiliation(
            target_user,
            department="TargetDept",
            line="L9",
            user_sdwt_prod="target-group",
        )
        same_department_other_group = User.objects.create_user(
            sabun="S52002",
            password="test-password",
            knox_id="knox-52002",
            email="same-dept-other@example.com",
            username="같은부서다른소속",
        )
        _set_current_affiliation(
            same_department_other_group,
            department="TargetDept",
            line="L9",
            user_sdwt_prod="target-other-group",
        )
        other_department_user = User.objects.create_user(
            sabun="S52003",
            password="test-password",
            knox_id="knox-52003",
            email="other-dept-same@example.com",
            username="다른부서사용자",
        )
        _set_current_affiliation(
            other_department_user,
            department="OtherDept",
            line="L9",
            user_sdwt_prod="other-dept-group",
        )
        ExternalAffiliationSnapshot.objects.create(
            knox_id="external-target-dept",
            username="외부대상",
            department="TargetDept",
            predicted_user_sdwt_prod="target-group",
            source_updated_at=now,
            last_seen_at=now,
        )
        ExternalAffiliationSnapshot.objects.create(
            knox_id="external-other-dept",
            username="외부타부서",
            department="OtherDept",
            predicted_user_sdwt_prod="target-group",
            source_updated_at=now,
            last_seen_at=now,
        )

        self.client.force_login(self.user)
        option_response = self.client.get(
            reverse("account-users"),
            {"department": "TargetDept", "includeExternalSnapshots": "true", "limit": 1},
        )
        load_response = self.client.get(
            reverse("account-users"),
            {
                "department": "TargetDept",
                "userSdwtProd": "target-group",
                "contactField": "email",
                "includeExternalSnapshots": "true",
                "limit": "all",
            },
        )

        self.assertEqual(option_response.status_code, 200)
        option_payload = option_response.json()
        self.assertIn("TargetDept", option_payload["departments"])
        self.assertIn("OtherDept", option_payload["departments"])
        self.assertIn("target-group", option_payload["userSdwtProds"])
        self.assertIn("target-other-group", option_payload["userSdwtProds"])
        self.assertNotIn("other-dept-group", option_payload["userSdwtProds"])
        self.assertNotIn("group-a", option_payload["userSdwtProds"])

        self.assertEqual(load_response.status_code, 200)
        rows_by_key = {row["recipientKey"]: row for row in load_response.json()["results"]}
        self.assertIn(f"user:{target_user.id}", rows_by_key)
        self.assertIn("external:external-target-dept", rows_by_key)
        self.assertNotIn(f"user:{same_department_other_group.id}", rows_by_key)
        self.assertNotIn(f"user:{other_department_user.id}", rows_by_key)
        self.assertNotIn("external:external-other-dept", rows_by_key)
        self.assertEqual(rows_by_key[f"user:{target_user.id}"]["department"], "TargetDept")
        self.assertEqual(rows_by_key[f"user:{target_user.id}"]["userSdwtProd"], "target-group")
        self.assertEqual(rows_by_key["external:external-target-dept"]["recipientType"], "external")
        self.assertEqual(rows_by_key["external:external-target-dept"]["department"], "TargetDept")
        self.assertEqual(rows_by_key["external:external-target-dept"]["userSdwtProd"], "target-group")

    def test_account_user_pool_rejects_unknown_contact_field(self) -> None:
        """지원하지 않는 연락처 필드는 명시적으로 거부해야 합니다."""

        self.client.force_login(self.user)
        response = self.client.get(reverse("account-users"), {"contactField": "phone"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("contactField", response.json())

    def test_account_user_pool_rejects_removed_alias_and_invalid_limit(self) -> None:
        """사용자 pool은 snake_case 별칭과 모호한 limit fallback을 거절해야 합니다."""

        self.client.force_login(self.user)
        alias_response = self.client.get(
            reverse("account-users"),
            {"user_sdwt_prod": "group-a"},
        )
        invalid_limit_response = self.client.get(
            reverse("account-users"),
            {"limit": "invalid"},
        )
        unbounded_response = self.client.get(
            reverse("account-users"),
            {"limit": "all"},
        )

        self.assertEqual(alias_response.status_code, 400)
        self.assertEqual(alias_response.json()["unexpectedFields"], ["user_sdwt_prod"])
        self.assertEqual(invalid_limit_response.status_code, 400)
        self.assertIn("limit", invalid_limit_response.json())
        self.assertEqual(unbounded_response.status_code, 400)
        self.assertIn("limit", unbounded_response.json())

    def test_account_user_pool_returns_all_group_users_when_requested(self) -> None:
        """소속 단위 전체 불러오기는 기본 500명 제한 없이 해당 소속 사용자를 반환해야 합니다."""

        User = get_user_model()
        for index in range(505):
            user = User.objects.create_user(
                sabun=f"S51{index:03d}",
                knox_id=f"knox-51{index:03d}",
                email=f"bulk-{index}@example.com",
                username=f"Bulk {index}",
            )
            _set_current_affiliation(user, user_sdwt_prod="bulk-group-all")

        self.client.force_login(self.user)
        response = self.client.get(
            reverse("account-users"),
            {"userSdwtProd": "bulk-group-all", "limit": "all"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["results"]), 505)

    def test_portal_access_allows_configured_department(self) -> None:
        """허용 부서 사용자는 별도 승인 없이 포털 접근이 허용되어야 합니다."""

        scope, _created = AccessScope.objects.get_or_create(
            key=ACCESS_SCOPE_PORTAL,
            defaults={"name": "Portal", "scope_type": AccessScope.ScopeTypes.PORTAL},
        )
        AccessPolicyRule.objects.update_or_create(
            scope=scope,
            rule_type=AccessPolicyRule.RuleTypes.DEPARTMENT,
            value="메모리Etch기술팀(글로벌 제조&인프라총괄)",
            defaults={"is_active": True},
        )
        self.user.department = "메모리Etch기술팀(글로벌 제조&인프라총괄)"
        self.user.save(update_fields=["department"])

        payload = get_access_payload(scope_key=ACCESS_SCOPE_PORTAL, user=self.user)

        self.assertTrue(payload["allowed"])
        self.assertEqual(payload["reason"], "department_allowed")
        self.assertTrue(payload["policy"]["matched"])

    def test_portal_access_rejected_row_blocks_allowed_department(self) -> None:
        """허용 부서 사용자도 거절 상태 행이 있으면 수동 차단되어야 합니다."""

        scope, _created = AccessScope.objects.get_or_create(
            key=ACCESS_SCOPE_PORTAL,
            defaults={"name": "Portal", "scope_type": AccessScope.ScopeTypes.PORTAL},
        )
        AccessPolicyRule.objects.update_or_create(
            scope=scope,
            rule_type=AccessPolicyRule.RuleTypes.DEPARTMENT,
            value="메모리Etch기술팀(글로벌 제조&인프라총괄)",
            defaults={"is_active": True},
        )
        self.user.department = "메모리Etch기술팀(글로벌 제조&인프라총괄)"
        self.user.save(update_fields=["department"])
        UserAccess.objects.create(
            user=self.user,
            scope=scope,
            department=self.user.department,
            status=UserAccess.Status.DENIED,
            reason="수동 차단",
        )

        payload = get_access_payload(scope_key=ACCESS_SCOPE_PORTAL, user=self.user)

        self.assertFalse(payload["allowed"])
        self.assertEqual(payload["reason"], "denied")
        self.assertEqual(payload["rejectionReason"], "수동 차단")

        self.client.force_login(self.user)
        onboarding_response = self.client.get(reverse("account-affiliation"))
        self.assertEqual(onboarding_response.status_code, 200)

        response = self.client.get(reverse("account-overview"))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"], "scope_access_required")

        request_list_response = self.client.get(reverse("account-affiliation-requests"))
        self.assertEqual(request_list_response.status_code, 403)
        self.assertEqual(request_list_response.json()["error"], "scope_access_required")

        request_payload, request_status = request_access(
            scope_keys=[ACCESS_SCOPE_PORTAL],
            user=self.user,
        )
        self.assertEqual(request_status, 200)
        self.assertEqual(request_payload["status"], "pending")
        self.assertFalse(request_payload["accesses"][ACCESS_SCOPE_PORTAL]["allowed"])
        self.assertEqual(
            request_payload["accesses"][ACCESS_SCOPE_PORTAL]["reason"],
            "pending",
        )

        approval = UserAccess.objects.get(user=self.user, scope=scope)
        self.assertEqual(approval.status, UserAccess.Status.PENDING)

        response_after_rerequest = self.client.get(reverse("account-overview"))
        self.assertEqual(response_after_rerequest.status_code, 403)
        self.assertEqual(response_after_rerequest.json()["access"]["reason"], "pending")

    def test_portal_access_request_and_admin_approval_flow(self) -> None:
        """비허용 부서 사용자가 요청 후 account admin 승인으로 접근 가능한지 확인합니다."""

        self.user.department = "OtherDept"
        self.user.save(update_fields=["department"])
        admin_user = self.manager
        _grant_manage_access(admin_user)

        request_payload, request_status = request_access(
            scope_keys=[ACCESS_SCOPE_PORTAL],
            user=self.user,
        )
        approval = UserAccess.objects.get(user=self.user, scope__key=ACCESS_SCOPE_PORTAL)

        self.assertEqual(request_status, 200)
        self.assertEqual(request_payload["status"], "pending")
        self.assertFalse(
            request_payload["accesses"][ACCESS_SCOPE_PORTAL]["allowed"]
        )
        self.assertEqual(approval.department, "OtherDept")

        self.client.force_login(admin_user)
        list_response = self.client.get(
            reverse("account-access-users"),
            {"scope": ACCESS_SCOPE_PORTAL, "status": "pending"},
        )
        self.assertEqual(list_response.status_code, 200)
        serialized_user = list_response.json()["results"][0]["user"]
        self.assertEqual(serialized_user["id"], self.user.id)
        self.assertEqual(
            set(serialized_user),
            {
                "id",
                "username",
                "displayName",
                "sabun",
                "knoxId",
                "email",
                "department",
                "userSdwtProd",
                "isSuperuser",
            },
        )
        self.assertNotIn("canManage", list_response.json()["results"][0]["access"])

        approve_response = self.client.post(
            reverse("account-access-user-decision", kwargs={"user_id": self.user.id}),
            data={"scope": ACCESS_SCOPE_PORTAL, "action": "approve"},
            content_type="application/json",
        )
        self.assertEqual(approve_response.status_code, 200)

        payload = get_access_payload(scope_key=ACCESS_SCOPE_PORTAL, user=self.user)
        self.assertTrue(payload["allowed"])
        self.assertEqual(payload["reason"], "allowed")

    def test_portal_access_admin_approval_applies_role(self) -> None:
        """포털 접근 승인 API가 요청 role을 사용자 접근 행에 반영하는지 확인합니다."""

        self.user.department = "OtherDept"
        self.user.save(update_fields=["department"])
        admin_user = self.manager
        _grant_manage_access(admin_user)
        request_access(scope_keys=[ACCESS_SCOPE_PORTAL], user=self.user)
        approval = UserAccess.objects.get(user=self.user, scope__key=ACCESS_SCOPE_PORTAL)

        self.client.force_login(admin_user)
        response = self.client.post(
            reverse("account-access-user-decision", kwargs={"user_id": self.user.id}),
            data={"scope": ACCESS_SCOPE_PORTAL, "action": "approve", "role": "admin"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        approval.refresh_from_db()
        self.assertEqual(approval.status, UserAccess.Status.ALLOWED)
        self.assertEqual(approval.role, "admin")
        self.assertEqual(response.json()["row"]["access"]["role"], "admin")

    def test_access_user_decision_can_grant_all_apps_as_user(self) -> None:
        """통합 사용자 결정 API도 Portal 승인 시 활성 앱을 함께 허용해야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        self.user.department = "OtherDept"
        self.user.save(update_fields=["department"])
        request_access(scope_keys=[ACCESS_SCOPE_PORTAL], user=self.user)
        UserAccess.objects.create(
            user=self.user,
            scope=AccessScope.objects.get(key="l3-spider"),
            status=UserAccess.Status.PENDING,
            role="user",
        )

        self.client.force_login(admin_user)
        response = self.client.post(
            reverse("account-access-user-decision", kwargs={"user_id": self.user.id}),
            data={
                "scope": ACCESS_SCOPE_PORTAL,
                "action": "approve",
                "role": "user",
                "approveAllApps": True,
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            UserAccess.objects.filter(
                user=self.user,
                scope__scope_type=AccessScope.ScopeTypes.APP,
                scope__is_active=True,
            ).exclude(
                status=UserAccess.Status.ALLOWED,
                role="user",
            ).exists()
        )

    def test_portal_access_admin_approval_rejects_invalid_role(self) -> None:
        """포털 접근 승인 API는 정의되지 않은 role 입력을 거절해야 합니다."""

        self.user.department = "OtherDept"
        self.user.save(update_fields=["department"])
        admin_user = self.manager
        _grant_manage_access(admin_user)
        request_access(scope_keys=[ACCESS_SCOPE_PORTAL], user=self.user)
        approval = UserAccess.objects.get(user=self.user, scope__key=ACCESS_SCOPE_PORTAL)

        self.client.force_login(admin_user)
        response = self.client.post(
            reverse("account-access-user-decision", kwargs={"user_id": self.user.id}),
            data={"scope": ACCESS_SCOPE_PORTAL, "action": "approve", "role": "owner"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        approval.refresh_from_db()
        self.assertEqual(approval.status, UserAccess.Status.PENDING)

    def test_portal_access_admin_approval_requires_explicit_decision(self) -> None:
        """포털 접근 승인 API는 decision 누락을 묵시 승인으로 처리하지 않아야 합니다."""

        self.user.department = "OtherDept"
        self.user.save(update_fields=["department"])
        admin_user = self.manager
        _grant_manage_access(admin_user)
        request_access(scope_keys=[ACCESS_SCOPE_PORTAL], user=self.user)
        approval = UserAccess.objects.get(user=self.user, scope__key=ACCESS_SCOPE_PORTAL)

        self.client.force_login(admin_user)
        response = self.client.post(
            reverse("account-access-user-decision", kwargs={"user_id": self.user.id}),
            data={"scope": ACCESS_SCOPE_PORTAL},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        approval.refresh_from_db()
        self.assertEqual(approval.status, UserAccess.Status.PENDING)
        self.assertIsNone(approval.decided_by)
        self.assertIsNone(approval.decided_at)

    def test_portal_access_request_uses_current_affiliation_department_fallback(self) -> None:
        """접근 요청 row의 부서는 현재 소속 부서 fallback과 일치해야 합니다."""

        self.user.department = ""
        self.user.save(update_fields=["department"])
        _set_current_affiliation(
            self.user,
            department="FallbackDept",
            line="L9",
            user_sdwt_prod="group-fallback",
        )
        self.user = get_user_model().objects.get(id=self.user.id)

        payload, status_code = request_access(
            scope_keys=[ACCESS_SCOPE_PORTAL],
            user=self.user,
        )

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["status"], "pending")
        approval = UserAccess.objects.get(user=self.user, scope__key=ACCESS_SCOPE_PORTAL)
        self.assertEqual(approval.department, "FallbackDept")

    def test_portal_access_rerequest_updates_requested_at(self) -> None:
        """거절 사용자가 재요청하면 pending 전환 시 요청 시각을 갱신해야 합니다."""

        scope = AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL)
        approval = UserAccess.objects.create(
            user=self.user,
            scope=scope,
            department=self.user.department,
            status=UserAccess.Status.DENIED,
            reason="사유 확인 필요",
            decided_by=self.manager,
            decided_at=timezone.now() - timedelta(days=1),
        )
        old_requested_at = timezone.now() - timedelta(days=2)
        UserAccess.objects.filter(id=approval.id).update(requested_at=old_requested_at)
        before_request = timezone.now()

        payload, status_code = request_access(
            scope_keys=[ACCESS_SCOPE_PORTAL],
            user=self.user,
        )

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["status"], "pending")
        approval.refresh_from_db()
        self.assertEqual(approval.status, UserAccess.Status.PENDING)
        self.assertIsNone(approval.reason)
        self.assertIsNone(approval.decided_by)
        self.assertIsNone(approval.decided_at)
        self.assertGreaterEqual(approval.requested_at, before_request)

    def test_portal_access_rerequest_resets_role_to_user(self) -> None:
        """관리자 권한이 회수된 사용자가 재요청해도 user 역할을 유지해야 합니다."""

        scope = AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL)
        approval = UserAccess.objects.create(
            user=self.user,
            scope=scope,
            department=self.user.department,
            status=UserAccess.Status.ALLOWED,
            role="admin",
            decided_by=self.superuser,
            decided_at=timezone.now(),
        )
        revoke_payload, revoke_status = access_control_services.decide_user_access(
            actor=self.superuser,
            user_id=self.user.id,
            scope_key=ACCESS_SCOPE_PORTAL,
            action="revoke",
            reason="권한 회수",
        )

        payload, status_code = request_access(
            scope_keys=[ACCESS_SCOPE_PORTAL],
            user=self.user,
        )

        self.assertEqual(revoke_status, 200)
        self.assertEqual(revoke_payload["row"]["access"]["explicitStatus"], "denied")
        self.assertEqual(status_code, 200)
        self.assertEqual(payload["status"], "pending")
        approval.refresh_from_db()
        self.assertEqual(approval.status, UserAccess.Status.PENDING)
        self.assertEqual(approval.role, "user")

    def test_portal_access_request_records_initial_and_rerequest_audit_snapshots(self) -> None:
        """최초 요청과 거절 후 재요청은 각각 당시 상태 snapshot을 감사 로그에 남겨야 합니다."""

        self.user.department = "OtherDept"
        self.user.save(update_fields=["department"])

        request_access(scope_keys=[ACCESS_SCOPE_PORTAL], user=self.user)
        approval = UserAccess.objects.get(user=self.user, scope__key=ACCESS_SCOPE_PORTAL)
        first_log = AccessAuditLog.objects.get(
            action=AccessAuditLog.Actions.REQUEST,
            target_user=self.user,
        )
        self.assertEqual(first_log.before, {})
        self.assertEqual(
            first_log.after["explicitStatus"],
            UserAccess.Status.PENDING,
        )

        approval.status = UserAccess.Status.DENIED
        approval.reason = "추가 확인"
        approval.decided_by = self.manager
        approval.decided_at = timezone.now()
        approval.save(update_fields=["status", "reason", "decided_by", "decided_at", "updated_at"])

        request_access(scope_keys=[ACCESS_SCOPE_PORTAL], user=self.user)
        logs = list(
            AccessAuditLog.objects.filter(
                action=AccessAuditLog.Actions.REQUEST,
                target_user=self.user,
            ).order_by("id")
        )
        self.assertEqual(len(logs), 2)
        self.assertEqual(
            logs[1].before,
            {"explicitStatus": UserAccess.Status.DENIED, "role": "user"},
        )
        self.assertEqual(
            logs[1].after,
            {"explicitStatus": UserAccess.Status.PENDING, "role": "user"},
        )

    def test_portal_access_request_rolls_back_when_audit_creation_fails(self) -> None:
        """접근 요청 감사 로그 생성 실패 시 pending 행도 남지 않아야 합니다."""

        self.user.department = "OtherDept"
        self.user.save(update_fields=["department"])

        with patch(
            "api.account.services.access_control.create_access_audit_log",
            side_effect=RuntimeError("audit failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "audit failed"):
                request_access(scope_keys=[ACCESS_SCOPE_PORTAL], user=self.user)

        self.assertFalse(
            UserAccess.objects.filter(user=self.user, scope__key=ACCESS_SCOPE_PORTAL).exists()
        )

    def test_decide_access_rolls_back_when_audit_creation_fails(self) -> None:
        """승인 감사 로그 생성 실패 시 pending 상태를 유지해야 합니다."""

        scope = AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL)
        _grant_manage_access(self.manager)
        self.manager.refresh_from_db()
        approval = UserAccess.objects.create(
            user=self.user,
            scope=scope,
            department=self.user.department,
            status=UserAccess.Status.PENDING,
        )

        with patch(
            "api.account.services.access_control.create_access_audit_log",
            side_effect=RuntimeError("audit failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "audit failed"):
                decide_user_access(
                    actor=self.manager,
                    user_id=self.user.id,
                    scope_key=ACCESS_SCOPE_PORTAL,
                    action="approve",
                    reason=None,
                )

        approval.refresh_from_db()
        self.assertEqual(approval.status, UserAccess.Status.PENDING)
        self.assertIsNone(approval.decided_by)
        self.assertIsNone(approval.decided_at)

    def test_decide_access_rejects_stale_already_decided_request(self) -> None:
        """이미 결정된 요청을 다시 승인하거나 거절하지 않아야 합니다."""

        scope = AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL)
        _grant_manage_access(self.manager)
        self.manager.refresh_from_db()
        approval = UserAccess.objects.create(
            user=self.user,
            scope=scope,
            department=self.user.department,
            status=UserAccess.Status.ALLOWED,
            decided_by=self.manager,
            decided_at=timezone.now(),
        )

        payload, status_code = decide_user_access(
            actor=self.manager,
            user_id=self.user.id,
            scope_key=ACCESS_SCOPE_PORTAL,
            action="reject",
            reason="늦게 도착한 요청",
        )

        self.assertEqual(status_code, 409)
        self.assertEqual(payload["error"], "invalid_status_transition")
        approval.refresh_from_db()
        self.assertEqual(approval.status, UserAccess.Status.ALLOWED)
        self.assertFalse(
            AccessAuditLog.objects.filter(target_user=self.user, action=AccessAuditLog.Actions.REJECT).exists()
        )

    def test_public_decision_service_delegates_to_canonical_mutation(self) -> None:
        """공개 권한 결정 서비스가 canonical 변경 함수만 실행해야 합니다."""

        scope = AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL)
        _grant_manage_access(self.manager)
        self.manager.refresh_from_db()
        approval = UserAccess.objects.create(
            user=self.user,
            scope=scope,
            department=self.user.department,
            status=UserAccess.Status.PENDING,
        )

        with patch(
            "api.account.services.access_control._decide_user_access",
            wraps=access_control_services._decide_user_access,
        ) as canonical_decision:
            payload, status_code = decide_user_access(
                actor=self.manager,
                user_id=self.user.id,
                scope_key=ACCESS_SCOPE_PORTAL,
                action="approve",
                reason=None,
                role="admin",
            )

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["row"]["access"]["role"], "admin")
        canonical_decision.assert_called_once()

    def test_decide_access_rejects_invalid_service_role(self) -> None:
        """서비스 직접 호출에서도 정의되지 않은 role은 조용히 viewer로 바꾸지 않아야 합니다."""

        scope = AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL)
        _grant_manage_access(self.manager)
        self.manager.refresh_from_db()
        approval = UserAccess.objects.create(
            user=self.user,
            scope=scope,
            department=self.user.department,
            status=UserAccess.Status.PENDING,
        )

        payload, status_code = decide_user_access(
            actor=self.manager,
            user_id=self.user.id,
            scope_key=ACCESS_SCOPE_PORTAL,
            action="approve",
            reason=None,
            role="owner",
        )

        self.assertEqual(status_code, 400)
        self.assertEqual(payload["error"], "invalid_role")
        approval.refresh_from_db()
        self.assertEqual(approval.status, UserAccess.Status.PENDING)

    def test_decide_access_rejects_invalid_service_action(self) -> None:
        """서비스 직접 호출에서도 정의되지 않은 action은 승인으로 처리하지 않아야 합니다."""

        scope = AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL)
        _grant_manage_access(self.manager)
        self.manager.refresh_from_db()
        approval = UserAccess.objects.create(
            user=self.user,
            scope=scope,
            department=self.user.department,
            status=UserAccess.Status.PENDING,
        )

        payload, status_code = decide_user_access(
            actor=self.manager,
            user_id=self.user.id,
            scope_key=ACCESS_SCOPE_PORTAL,
            action="aprove",
            reason=None,
        )

        self.assertEqual(status_code, 400)
        self.assertEqual(payload["error"], "invalid_action")
        approval.refresh_from_db()
        self.assertEqual(approval.status, UserAccess.Status.PENDING)
        self.assertIsNone(approval.decided_by)
        self.assertIsNone(approval.decided_at)

    def test_inactive_portal_scope_cannot_be_requested(self) -> None:
        """비활성 portal scope는 화면에서 승인 요청 가능 상태로 노출하지 않아야 합니다."""

        scope = AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL)
        scope.is_active = False
        scope.save(update_fields=["is_active"])

        payload = get_access_payload(scope_key=ACCESS_SCOPE_PORTAL, user=self.user)

        self.assertFalse(payload["allowed"])
        self.assertEqual(payload["reason"], "scope_inactive")
        self.assertFalse(payload["canRequest"])

    def test_superuser_is_allowed_when_portal_scope_is_missing(self) -> None:
        """portal scope 설정이 누락되어도 superuser 비상 접근은 허용해야 합니다."""

        AccessScope.objects.filter(key=ACCESS_SCOPE_PORTAL).delete()
        self.user.is_superuser = True
        self.user.save(update_fields=["is_superuser"])

        payload = get_access_payload(scope_key=ACCESS_SCOPE_PORTAL, user=self.user)

        self.assertTrue(payload["allowed"])
        self.assertEqual(payload["reason"], "superuser_bypass")
        self.assertEqual(payload["source"], "superuser_bypass")
        self.assertEqual(payload["role"], "admin")

    def test_portal_access_staff_without_portal_admin_cannot_approve(self) -> None:
        """is_staff만 있는 사용자는 포털 접근 승인 관리자가 아니어야 합니다."""

        staff_user = self.manager
        staff_user.is_staff = True
        staff_user.save(update_fields=["is_staff"])

        self.user.department = "OtherDept"
        self.user.save(update_fields=["department"])
        request_access(scope_keys=[ACCESS_SCOPE_PORTAL], user=self.user)
        approval = UserAccess.objects.get(user=self.user, scope__key=ACCESS_SCOPE_PORTAL)

        self.client.force_login(staff_user)
        response = self.client.post(
            reverse("account-access-user-decision", kwargs={"user_id": self.user.id}),
            data={"scope": ACCESS_SCOPE_PORTAL, "action": "approve"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        approval.refresh_from_db()
        self.assertEqual(approval.status, UserAccess.Status.PENDING)

    def test_access_management_lists_policy_allowed_user_and_revoke_blocks(self) -> None:
        """권한 관리 목록은 정책 허용 사용자를 표시하고 명시 회수로 차단할 수 있어야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        self.user.department = "Dept"
        self.user.save(update_fields=["department"])

        self.client.force_login(admin_user)
        list_response = self.client.get(reverse("account-access-users"), {"search": self.user.knox_id})
        self.assertEqual(list_response.status_code, 200)
        row = list_response.json()["results"][0]
        self.assertEqual(row["user"]["id"], self.user.id)
        self.assertTrue(row["access"]["allowed"])
        self.assertEqual(row["access"]["source"], "policy_department")
        self.assertIsNone(row["access"]["explicitStatus"])

        revoke_response = self.client.post(
            reverse("account-access-user-decision", kwargs={"user_id": self.user.id}),
            data='{"scope": "portal", "action": "revoke", "reason": "운영 회수"}',
            content_type="application/json",
        )
        self.assertEqual(revoke_response.status_code, 200)
        self.assertEqual(revoke_response.json()["row"]["access"]["source"], "explicit_denied")

        payload = get_access_payload(scope_key=ACCESS_SCOPE_PORTAL, user=self.user)
        self.assertFalse(payload["allowed"])
        self.assertEqual(payload["reason"], "denied")
        self.assertEqual(UserAccess.objects.get(user=self.user, scope__key=ACCESS_SCOPE_PORTAL).status, UserAccess.Status.DENIED)
        audit_log = AccessAuditLog.objects.get(
            action=AccessAuditLog.Actions.REVOKE,
            target_user=self.user,
            actor=admin_user,
        )
        self.assertEqual(audit_log.reason, "운영 회수")

    def test_access_user_decision_returns_updated_full_matrix_row(self) -> None:
        """단일 권한 결정은 Portal 연쇄 판정까지 반영한 최신 매트릭스 행을 반환해야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        portal_scope = AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL)
        appstore_scope = AccessScope.objects.get(key="appstore")
        UserAccess.objects.bulk_create(
            [
                UserAccess(
                    user=self.user,
                    scope=portal_scope,
                    status=UserAccess.Status.ALLOWED,
                ),
                UserAccess(
                    user=self.user,
                    scope=appstore_scope,
                    status=UserAccess.Status.ALLOWED,
                ),
            ]
        )

        self.client.force_login(admin_user)
        response = self.client.post(
            reverse("account-access-user-decision", kwargs={"user_id": self.user.id}),
            data={
                "scope": ACCESS_SCOPE_PORTAL,
                "action": "revoke",
                "reason": "Portal 접근 차단",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        matrix_row = response.json()["matrixRow"]
        self.assertEqual(matrix_row["user"]["id"], self.user.id)
        self.assertFalse(matrix_row["accesses"][ACCESS_SCOPE_PORTAL]["allowed"])
        appstore_access = matrix_row["accesses"]["appstore"]
        self.assertFalse(appstore_access["allowed"])
        self.assertTrue(appstore_access["blockedByPortal"])
        self.assertEqual(appstore_access["explicitStatus"], UserAccess.Status.ALLOWED)
        self.assertEqual(
            appstore_access["underlyingAccess"]["source"],
            AccessSource.EXPLICIT_ALLOWED,
        )

    def test_access_user_apply_all_sets_every_matrix_scope_to_user_role(self) -> None:
        """전체 변경은 표시 scope를 일반 권한으로 통일하고 비활성 scope는 제외해야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        portal_scope = AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL)
        appstore_scope = AccessScope.objects.get(key="appstore")
        observer_scope = AccessScope.objects.get(key="observer")
        feature_scope = AccessScope.objects.create(
            key="apply-all-feature",
            name="전체 승인 기능",
            scope_type=AccessScope.ScopeTypes.FEATURE,
            is_active=True,
        )
        inactive_scope = AccessScope.objects.create(
            key="apply-all-inactive",
            name="비활성 전체 승인 제외",
            scope_type=AccessScope.ScopeTypes.APP,
            is_active=False,
        )
        UserAccess.objects.bulk_create(
            [
                UserAccess(
                    user=self.user,
                    scope=portal_scope,
                    status=UserAccess.Status.DENIED,
                    role=AccessRole.USER,
                ),
                UserAccess(
                    user=self.user,
                    scope=appstore_scope,
                    status=UserAccess.Status.PENDING,
                    role=AccessRole.USER,
                ),
                UserAccess(
                    user=self.user,
                    scope=feature_scope,
                    status=UserAccess.Status.ALLOWED,
                    role=AccessRole.ADMIN,
                ),
                UserAccess(
                    user=self.user,
                    scope=observer_scope,
                    status=UserAccess.Status.ALLOWED,
                    role=AccessRole.USER,
                ),
                UserAccess(
                    user=self.user,
                    scope=inactive_scope,
                    status=UserAccess.Status.DENIED,
                    role=AccessRole.USER,
                ),
            ]
        )

        self.client.force_login(admin_user)
        response = self.client.post(
            reverse("account-access-user-apply-all", kwargs={"user_id": self.user.id}),
            data={"value": "user", "reason": "전체 일반 권한 검증"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        matrix_accesses = payload["matrixRow"]["accesses"]
        managed_scope_keys = set(matrix_accesses)
        expected_changed_scope_keys = managed_scope_keys - {observer_scope.key}
        self.assertNotIn(inactive_scope.key, managed_scope_keys)
        self.assertEqual(payload["summary"]["total"], len(managed_scope_keys))
        self.assertEqual(payload["summary"]["updated"], len(expected_changed_scope_keys))
        self.assertEqual(payload["summary"]["unchanged"], 1)
        self.assertEqual(set(payload["changedScopes"]), expected_changed_scope_keys)

        stored_accesses = UserAccess.objects.filter(
            user=self.user,
            scope__key__in=managed_scope_keys,
        )
        self.assertEqual(stored_accesses.count(), len(managed_scope_keys))
        self.assertFalse(
            stored_accesses.exclude(
                status=UserAccess.Status.ALLOWED,
                role=AccessRole.USER,
            ).exists()
        )
        for scope_key, access in matrix_accesses.items():
            with self.subTest(scope=scope_key):
                self.assertTrue(access["allowed"])
                self.assertEqual(access["role"], AccessRole.USER)
                self.assertEqual(access["explicitStatus"], UserAccess.Status.ALLOWED)

        inactive_access = UserAccess.objects.get(user=self.user, scope=inactive_scope)
        self.assertEqual(inactive_access.status, UserAccess.Status.DENIED)
        self.assertEqual(inactive_access.role, AccessRole.USER)
        changed_audits = AccessAuditLog.objects.filter(
            actor=admin_user,
            target_user=self.user,
            scope__key__in=managed_scope_keys,
        )
        self.assertEqual(changed_audits.count(), len(expected_changed_scope_keys))
        self.assertEqual(
            changed_audits.get(scope=feature_scope).action,
            AccessAuditLog.Actions.CHANGE_ROLE,
        )

    def test_access_user_apply_all_sets_every_matrix_scope_to_admin_role(self) -> None:
        """관리자 선택은 모든 표시 scope를 관리자 권한으로 통일해야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        self.client.force_login(admin_user)

        response = self.client.post(
            reverse("account-access-user-apply-all", kwargs={"user_id": self.user.id}),
            data={"value": "admin", "reason": "전체 관리자 권한 검증"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["value"], "admin")
        managed_scope_keys = set(payload["matrixRow"]["accesses"])
        stored_accesses = UserAccess.objects.filter(
            user=self.user,
            scope__key__in=managed_scope_keys,
        )
        self.assertEqual(stored_accesses.count(), len(managed_scope_keys))
        self.assertFalse(
            stored_accesses.exclude(
                status=UserAccess.Status.ALLOWED,
                role=AccessRole.ADMIN,
            ).exists()
        )
        for scope_key, access in payload["matrixRow"]["accesses"].items():
            with self.subTest(scope=scope_key):
                self.assertTrue(access["allowed"])
                self.assertEqual(access["role"], AccessRole.ADMIN)

    def test_access_user_apply_all_denies_every_matrix_scope(self) -> None:
        """접근 차단 선택은 모든 표시 scope를 명시적으로 차단해야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        self.client.force_login(admin_user)

        response = self.client.post(
            reverse("account-access-user-apply-all", kwargs={"user_id": self.user.id}),
            data={"value": "denied", "reason": "전체 권한 차단 검증"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["value"], "denied")
        managed_scope_keys = set(payload["matrixRow"]["accesses"])
        stored_accesses = UserAccess.objects.filter(
            user=self.user,
            scope__key__in=managed_scope_keys,
        )
        self.assertEqual(stored_accesses.count(), len(managed_scope_keys))
        self.assertFalse(
            stored_accesses.exclude(
                status=UserAccess.Status.DENIED,
                role=AccessRole.USER,
            ).exists()
        )
        for scope_key, access in payload["matrixRow"]["accesses"].items():
            with self.subTest(scope=scope_key):
                self.assertFalse(access["allowed"])
                self.assertEqual(access["explicitStatus"], UserAccess.Status.DENIED)

    def test_access_user_apply_all_resets_every_matrix_scope_to_policy(self) -> None:
        """자동 규칙 선택은 모든 표시 scope의 명시 권한을 제거해야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        managed_scopes = list(
            AccessScope.objects.filter(
                Q(key=ACCESS_SCOPE_PORTAL) | Q(is_active=True)
            )
        )
        UserAccess.objects.bulk_create(
            [
                UserAccess(
                    user=self.user,
                    scope=scope,
                    status=UserAccess.Status.ALLOWED,
                    role=AccessRole.ADMIN,
                )
                for scope in managed_scopes
            ]
        )
        self.client.force_login(admin_user)

        response = self.client.post(
            reverse("account-access-user-apply-all", kwargs={"user_id": self.user.id}),
            data={"value": "inherit", "reason": "전체 자동 규칙 검증"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["value"], "inherit")
        self.assertEqual(payload["summary"]["updated"], len(managed_scopes))
        self.assertFalse(
            UserAccess.objects.filter(
                user=self.user,
                scope__in=managed_scopes,
            ).exists()
        )
        for scope_key, access in payload["matrixRow"]["accesses"].items():
            with self.subTest(scope=scope_key):
                self.assertIsNone(access["explicitStatus"])
        self.assertEqual(
            AccessAuditLog.objects.filter(
                actor=admin_user,
                target_user=self.user,
                action=AccessAuditLog.Actions.RESET_TO_POLICY,
            ).count(),
            len(managed_scopes),
        )

    def test_access_user_apply_all_rejects_invalid_value(self) -> None:
        """전체 변경 API는 지원하지 않는 권한 값을 거절해야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        self.client.force_login(admin_user)

        response = self.client.post(
            reverse("account-access-user-apply-all", kwargs={"user_id": self.user.id}),
            data={"value": "pending"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "invalid_request")
        self.assertFalse(UserAccess.objects.filter(user=self.user).exists())

    def test_access_user_apply_all_rejects_superuser_without_writes(self) -> None:
        """슈퍼유저 전체 변경은 기존 우회 권한을 유지하고 어떤 행도 생성하지 않아야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        self.client.force_login(admin_user)

        response = self.client.post(
            reverse("account-access-user-apply-all", kwargs={"user_id": self.superuser.id}),
            data={"value": "user", "reason": "슈퍼유저 변경 거부 검증"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"], "immutable_access_bypass")
        self.assertFalse(UserAccess.objects.filter(user=self.superuser).exists())
        self.assertFalse(
            AccessAuditLog.objects.filter(target_user=self.superuser).exists()
        )

    def test_access_management_change_role_requires_explicit_role(self) -> None:
        """change_role action은 정책 허용 사용자에게도 명시적인 role이 필요합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        self.client.force_login(admin_user)

        response = self.client.post(
            reverse("account-access-user-decision", kwargs={"user_id": self.user.id}),
            data='{"scope": "portal", "action": "change_role"}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("role", response.json()["details"])
        self.assertFalse(
            UserAccess.objects.filter(user=self.user, scope__key=ACCESS_SCOPE_PORTAL).exists()
        )

    def test_access_management_rejects_every_superuser_mutation_without_writes(self) -> None:
        """superuser의 우회 권한은 명시 접근 행과 감사 로그로 변경할 수 없어야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        scope = AccessScope.objects.get(key="appstore")
        UserAccess.objects.create(
            user=self.superuser,
            scope=scope,
            department="Operations",
            status=UserAccess.Status.ALLOWED,
            role="admin",
        )
        endpoint = reverse(
            "account-access-user-decision",
            kwargs={"user_id": self.superuser.id},
        )
        stored_access = UserAccess.objects.filter(
            user=self.superuser,
            scope=scope,
        ).values(
            "department",
            "status",
            "role",
            "reason",
            "decided_by_id",
            "decided_at",
        ).get()
        audit_count = AccessAuditLog.objects.filter(
            target_user=self.superuser,
            scope=scope,
        ).count()
        actions = (
            ("approve", {}),
            ("reject", {}),
            ("grant", {"role": "user"}),
            ("revoke", {}),
            ("reset_to_policy", {}),
            ("change_role", {"role": "user"}),
        )
        self.client.force_login(admin_user)

        for action, extra_payload in actions:
            with self.subTest(action=action):
                response = self.client.post(
                    endpoint,
                    data={
                        "scope": scope.key,
                        "action": action,
                        "reason": "슈퍼유저 변경 거부 검증",
                        **extra_payload,
                    },
                    content_type="application/json",
                )

                self.assertEqual(response.status_code, 409)
                self.assertEqual(response.json()["error"], "immutable_access_bypass")
                self.assertEqual(
                    UserAccess.objects.filter(
                        user=self.superuser,
                        scope=scope,
                    ).values(
                        "department",
                        "status",
                        "role",
                        "reason",
                        "decided_by_id",
                        "decided_at",
                    ).get(),
                    stored_access,
                )
                self.assertEqual(
                    AccessAuditLog.objects.filter(
                        target_user=self.superuser,
                        scope=scope,
                    ).count(),
                    audit_count,
                )

    def test_access_management_approve_requires_pending_request(self) -> None:
        """운영 승인 action은 pending 요청이 없으면 직접 부여로 동작하지 않아야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        self.client.force_login(admin_user)

        response = self.client.post(
            reverse("account-access-user-decision", kwargs={"user_id": self.user.id}),
            data='{"scope": "portal", "action": "approve", "role": "user"}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"], "invalid_status_transition")
        self.assertFalse(
            UserAccess.objects.filter(user=self.user, scope__key=ACCESS_SCOPE_PORTAL).exists()
        )

    def test_access_management_fast_filters_only_exclude_superuser_bypass(self) -> None:
        """명시 상태 필터는 일반 사용자를 포함하고 superuser 우회만 제외해야 합니다."""

        scope = AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL)
        admin_user = self.manager
        _grant_manage_access(admin_user)
        User = get_user_model()
        pending_portal_user = User.objects.create_user(
            sabun="S51000",
            password="test-password",
            knox_id="knox-51000",
            department="Dept",
        )
        _grant_manage_access(pending_portal_user)
        UserAccess.objects.filter(user=pending_portal_user, scope=scope).update(
            status=UserAccess.Status.PENDING,
            role="user",
        )
        UserAccess.objects.create(
            user=self.user,
            scope=scope,
            status=UserAccess.Status.PENDING,
        )
        UserAccess.objects.create(
            user=self.superuser,
            scope=scope,
            status=UserAccess.Status.DENIED,
        )

        self.client.force_login(admin_user)
        pending_response = self.client.get(reverse("account-access-users"), {"status": "pending"})
        denied_source_response = self.client.get(
            reverse("account-access-users"),
            {"source": "explicit_denied"},
        )
        bypass_source_response = self.client.get(
            reverse("account-access-users"),
            {"source": "superuser_bypass"},
        )
        pending_ids = {row["user"]["id"] for row in pending_response.json()["results"]}
        denied_ids = {row["user"]["id"] for row in denied_source_response.json()["results"]}
        bypass_ids = {row["user"]["id"] for row in bypass_source_response.json()["results"]}
        self.assertIn(self.user.id, pending_ids)
        self.assertIn(pending_portal_user.id, pending_ids)
        self.assertNotIn(self.superuser.id, denied_ids)
        self.assertIn(self.superuser.id, bypass_ids)
        self.assertNotIn(self.user.id, bypass_ids)
        self.assertNotIn(pending_portal_user.id, bypass_ids)

    def test_portal_admin_role_can_manage_access(self) -> None:
        """Portal admin 역할이 전역 접근 관리 권한의 단일 근거인지 확인합니다."""

        UserAccess.objects.create(
            user=self.user,
            scope=AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL),
            status=UserAccess.Status.ALLOWED,
            role="admin",
        )

        payload = get_access_payload(scope_key=ACCESS_SCOPE_PORTAL, user=self.user)

        self.assertTrue(payload["allowed"])
        self.assertEqual(payload["role"], "admin")
        self.assertTrue(can_manage_access(user=self.user))

        self.client.force_login(self.user)
        response = self.client.get(reverse("account-access-users"))

        self.assertEqual(response.status_code, 200)

    def test_denied_former_portal_admin_cannot_manage_access(self) -> None:
        """Portal admin을 회수하면 즉시 전역 관리 권한도 제거되어야 합니다."""

        _grant_manage_access(self.manager)
        revoke_payload, revoke_status = access_control_services.decide_user_access(
            actor=self.superuser,
            user_id=self.manager.id,
            scope_key=ACCESS_SCOPE_PORTAL,
            action="revoke",
            reason="관리자 권한 회수",
        )

        payload = get_access_payload(scope_key=ACCESS_SCOPE_PORTAL, user=self.manager)

        self.assertEqual(revoke_status, 200)
        self.assertEqual(revoke_payload["row"]["access"]["role"], "user")
        self.assertFalse(can_manage_access(user=self.manager))
        self.assertFalse(payload["allowed"])
        self.assertEqual(payload["source"], "explicit_denied")

        self.client.force_login(self.manager)
        response = self.client.get(reverse("account-access-users"))

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"], "scope_access_required")
        self.assertEqual(response.json()["scope"], ACCESS_SCOPE_PORTAL)
        self.assertFalse(response.json()["access"]["allowed"])

    def test_pending_access_remains_denied_when_department_policy_matches(self) -> None:
        """승인 대기 상태는 부서 자동 허용 규칙보다 우선해 접근을 차단해야 합니다."""

        UserAccess.objects.create(
            user=self.user,
            scope=AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL),
            status=UserAccess.Status.PENDING,
        )

        payload = get_access_payload(scope_key=ACCESS_SCOPE_PORTAL, user=self.user)

        self.assertTrue(payload["policy"]["matched"])
        self.assertFalse(payload["allowed"])
        self.assertEqual(payload["effectiveStatus"], "pending")
        self.assertEqual(payload["source"], "explicit_pending")

    def test_access_admin_mutations_require_json_content_type(self) -> None:
        """브라우저 form Content-Type으로 권한과 정책을 변경할 수 없어야 합니다."""

        scope = AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL)
        admin_user = self.manager
        _grant_manage_access(admin_user)
        approval = UserAccess.objects.create(
            user=self.user,
            scope=scope,
            status=UserAccess.Status.PENDING,
        )
        rule = AccessPolicyRule.objects.get(
            scope=scope,
            rule_type=AccessPolicyRule.RuleTypes.DEPARTMENT,
            value="Dept",
        )
        self.client.force_login(admin_user)

        user_response = self.client.post(
            reverse("account-access-user-decision", kwargs={"user_id": self.user.id}),
            data='{"action": "grant"}',
            content_type="application/x-www-form-urlencoded",
        )
        create_response = self.client.post(
            reverse("account-access-policy-rules"),
            data='{"ruleType": "department", "value": "FormDept"}',
            content_type="text/plain",
        )
        patch_response = self.client.patch(
            reverse("account-access-policy-rule-detail", kwargs={"rule_id": rule.id}),
            data='{"isActive": false}',
            content_type="text/plain",
        )

        self.assertEqual(user_response.status_code, 415)
        self.assertEqual(create_response.status_code, 415)
        self.assertEqual(patch_response.status_code, 415)
        approval.refresh_from_db()
        rule.refresh_from_db()
        self.assertEqual(approval.status, UserAccess.Status.PENDING)
        self.assertFalse(AccessPolicyRule.objects.filter(value="FormDept").exists())

    def test_access_management_users_paginates_default_list(self) -> None:
        """권한 관리 기본 사용자 목록은 페이지 크기만큼만 응답해야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        User = get_user_model()
        for index in range(25):
            User.objects.create_user(
                sabun=f"S51{index:03d}",
                password="test-password",
                knox_id=f"knox-51{index:03d}",
                department="Dept",
            )
        expected_total = User.objects.count()

        self.client.force_login(admin_user)
        response = self.client.get(reverse("account-access-users"), {"pageSize": "5"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["results"]), 5)
        self.assertEqual(payload["pagination"]["pageSize"], 5)
        self.assertEqual(payload["pagination"]["total"], expected_total)
        self.assertNotIn("summary", payload)

    def test_access_matrix_returns_all_scope_role_contracts(self) -> None:
        """통합 권한 매트릭스는 Portal·app·feature 판정을 함께 반환해야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        appstore_scope = AccessScope.objects.get(key="appstore")
        line_dashboard_scope = AccessScope.objects.get(key="line-dashboard")
        feature_scope = AccessScope.objects.create(
            key="report-export",
            name="보고서 내보내기",
            scope_type=AccessScope.ScopeTypes.FEATURE,
        )
        UserAccess.objects.create(
            user=self.user,
            scope=appstore_scope,
            department="Dept",
            status=UserAccess.Status.ALLOWED,
            role="admin",
        )
        AccessPolicyRule.objects.create(
            scope=line_dashboard_scope,
            rule_type=AccessPolicyRule.RuleTypes.DEPARTMENT,
            value="Dept",
        )
        UserAccess.objects.create(
            user=self.user,
            scope=feature_scope,
            department="Dept",
            status=UserAccess.Status.ALLOWED,
            role="admin",
        )

        self.client.force_login(admin_user)
        response = self.client.get(
            reverse("account-access-matrix"),
            {"search": self.user.knox_id, "pageSize": 5},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        expected_scope_keys = {
            ACCESS_SCOPE_PORTAL,
            *AccessScope.objects.filter(is_active=True).values_list("key", flat=True),
        }
        self.assertEqual(
            {scope["key"] for scope in payload["scopes"]},
            expected_scope_keys,
        )
        self.assertEqual(payload["pagination"]["total"], 1)
        self.assertEqual(payload["scopes"][0]["key"], ACCESS_SCOPE_PORTAL)
        self.assertEqual(payload["scopes"][0]["scopeType"], AccessScope.ScopeTypes.PORTAL)
        row = payload["results"][0]
        self.assertEqual(row["user"]["id"], self.user.id)
        self.assertEqual(row["accesses"][ACCESS_SCOPE_PORTAL]["source"], "policy_department")
        self.assertEqual(row["accesses"][ACCESS_SCOPE_PORTAL]["role"], "user")
        self.assertEqual(row["accesses"]["appstore"]["source"], "explicit_allowed")
        self.assertEqual(row["accesses"]["appstore"]["role"], "admin")
        self.assertEqual(row["accesses"]["line-dashboard"]["source"], "policy_department")
        self.assertTrue(row["accesses"]["line-dashboard"]["allowed"])
        self.assertEqual(row["accesses"]["line-dashboard"]["role"], "user")
        self.assertEqual(row["accesses"]["observer"]["effectiveStatus"], "not_requested")
        self.assertEqual(row["accesses"]["report-export"]["source"], "explicit_allowed")
        self.assertEqual(row["accesses"]["report-export"]["role"], "admin")

    def test_access_matrix_filters_users_with_manual_grants_in_managed_scopes(self) -> None:
        """수동 부여 필터는 표시 scope의 명시 허용 사용자를 중복 없이 반환해야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        User = get_user_model()
        allowed_user = User.objects.create_user(
            sabun="S-MATRIX-MANUAL-1",
            password="test-password",
            knox_id="matrix-manual-allowed",
        )
        pending_user = User.objects.create_user(
            sabun="S-MATRIX-MANUAL-2",
            password="test-password",
            knox_id="matrix-manual-pending",
        )
        denied_user = User.objects.create_user(
            sabun="S-MATRIX-MANUAL-3",
            password="test-password",
            knox_id="matrix-manual-denied",
        )
        inactive_user = User.objects.create_user(
            sabun="S-MATRIX-MANUAL-4",
            password="test-password",
            knox_id="matrix-manual-inactive",
        )
        appstore_scope = AccessScope.objects.get(key="appstore")
        observer_scope = AccessScope.objects.get(key="observer")
        inactive_scope = AccessScope.objects.create(
            key="inactive-manual-filter",
            name="비활성 수동 필터",
            scope_type=AccessScope.ScopeTypes.APP,
            is_active=False,
        )
        UserAccess.objects.bulk_create(
            [
                UserAccess(
                    user=allowed_user,
                    scope=appstore_scope,
                    status=UserAccess.Status.ALLOWED,
                ),
                UserAccess(
                    user=allowed_user,
                    scope=observer_scope,
                    status=UserAccess.Status.ALLOWED,
                ),
                UserAccess(
                    user=pending_user,
                    scope=appstore_scope,
                    status=UserAccess.Status.PENDING,
                ),
                UserAccess(
                    user=denied_user,
                    scope=appstore_scope,
                    status=UserAccess.Status.DENIED,
                ),
                UserAccess(
                    user=inactive_user,
                    scope=inactive_scope,
                    status=UserAccess.Status.ALLOWED,
                ),
            ]
        )

        self.client.force_login(admin_user)
        response = self.client.get(
            reverse("account-access-matrix"),
            {
                "search": "matrix-manual",
                "manualGrantOnly": "true",
                "pageSize": 10,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["pagination"]["total"], 1)
        self.assertEqual(
            [row["user"]["id"] for row in payload["results"]],
            [allowed_user.id],
        )

    def test_access_users_returns_pending_feature_scope_requests(self) -> None:
        """대기 요청 목록은 feature scope도 앱과 같은 API 계약으로 조회해야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        feature_scope = AccessScope.objects.create(
            key="pending-report-export",
            name="대기 보고서 내보내기",
            scope_type=AccessScope.ScopeTypes.FEATURE,
        )
        UserAccess.objects.create(
            user=self.user,
            scope=feature_scope,
            department="Dept",
            status=UserAccess.Status.PENDING,
        )

        self.client.force_login(admin_user)
        response = self.client.get(
            reverse("account-access-users"),
            {
                "scope": feature_scope.key,
                "status": UserAccess.Status.PENDING,
                "pageSize": 5,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["scope"]["key"], feature_scope.key)
        self.assertEqual(payload["pagination"]["total"], 1)
        self.assertEqual(payload["results"][0]["user"]["id"], self.user.id)
        self.assertEqual(
            payload["results"][0]["access"]["effectiveStatus"],
            UserAccess.Status.PENDING,
        )

    def test_pending_access_requests_lists_all_scopes_and_filters_one_scope(self) -> None:
        """전체 승인 대기는 scope별 요청을 독립 행으로 반환하고 앱 필터를 지원해야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        portal_scope = AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL)
        appstore_scope = AccessScope.objects.get(key="appstore")
        portal_request = UserAccess.objects.create(
            user=self.user,
            scope=portal_scope,
            department="Dept",
            status=UserAccess.Status.PENDING,
        )
        appstore_request = UserAccess.objects.create(
            user=self.user,
            scope=appstore_scope,
            department="Dept",
            status=UserAccess.Status.PENDING,
        )

        self.client.force_login(admin_user)
        all_response = self.client.get(
            reverse("account-pending-access-requests"),
            {"pageSize": 5},
        )
        filtered_response = self.client.get(
            reverse("account-pending-access-requests"),
            {"scope": "appstore", "pageSize": 5},
        )

        self.assertEqual(all_response.status_code, 200)
        all_payload = all_response.json()
        self.assertEqual(all_payload["summary"]["total"], 2)
        self.assertEqual(all_payload["pagination"]["total"], 2)
        self.assertEqual(
            {
                (row["requestId"], row["scope"]["key"], row["user"]["id"])
                for row in all_payload["results"]
            },
            {
                (portal_request.id, ACCESS_SCOPE_PORTAL, self.user.id),
                (appstore_request.id, "appstore", self.user.id),
            },
        )
        scope_counts = {
            row["scope"]["key"]: row["total"]
            for row in all_payload["scopeCounts"]
        }
        self.assertEqual(
            scope_counts,
            {ACCESS_SCOPE_PORTAL: 1, "appstore": 1},
        )

        self.assertEqual(filtered_response.status_code, 200)
        filtered_payload = filtered_response.json()
        self.assertEqual(filtered_payload["summary"]["total"], 2)
        self.assertEqual(filtered_payload["pagination"]["total"], 1)
        self.assertEqual(
            filtered_payload["results"][0]["requestId"],
            appstore_request.id,
        )
        self.assertEqual(
            filtered_payload["results"][0]["access"]["effectiveStatus"],
            UserAccess.Status.PENDING,
        )

    def test_bulk_approve_pending_access_requests_only_updates_selected_rows(self) -> None:
        """일괄 승인은 선택한 scope 요청만 일반 사용자로 승인하고 각각 감사 로그를 남겨야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        portal_request = UserAccess.objects.create(
            user=self.user,
            scope=AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL),
            department="Dept",
            status=UserAccess.Status.PENDING,
        )
        appstore_request = UserAccess.objects.create(
            user=self.user,
            scope=AccessScope.objects.get(key="appstore"),
            department="Dept",
            status=UserAccess.Status.PENDING,
        )
        unselected_request = UserAccess.objects.create(
            user=self.user,
            scope=AccessScope.objects.get(key="observer"),
            department="Dept",
            status=UserAccess.Status.PENDING,
        )

        self.client.force_login(admin_user)
        response = self.client.post(
            reverse("account-pending-access-requests-bulk-approve"),
            data={
                "requestIds": [
                    appstore_request.id,
                    portal_request.id,
                    appstore_request.id,
                ],
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(
            payload["summary"],
            {"requested": 2, "approved": 2, "failed": 0},
        )
        portal_request.refresh_from_db()
        appstore_request.refresh_from_db()
        unselected_request.refresh_from_db()
        self.assertEqual(portal_request.status, UserAccess.Status.ALLOWED)
        self.assertEqual(appstore_request.status, UserAccess.Status.ALLOWED)
        self.assertEqual(portal_request.role, AccessRole.USER)
        self.assertEqual(appstore_request.role, AccessRole.USER)
        self.assertEqual(unselected_request.status, UserAccess.Status.PENDING)
        self.assertEqual(
            AccessAuditLog.objects.filter(
                actor=admin_user,
                target_user=self.user,
                action=AccessAuditLog.Actions.APPROVE,
                scope__key__in=[ACCESS_SCOPE_PORTAL, "appstore"],
            ).count(),
            2,
        )

    def test_bulk_approve_pending_access_requests_reports_partial_failure(self) -> None:
        """이미 처리된 요청은 실패로 남기고 유효한 선택 요청은 계속 승인해야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        pending_request = UserAccess.objects.create(
            user=self.user,
            scope=AccessScope.objects.get(key="appstore"),
            department="Dept",
            status=UserAccess.Status.PENDING,
        )
        decided_request = UserAccess.objects.create(
            user=self.user,
            scope=AccessScope.objects.get(key="observer"),
            department="Dept",
            status=UserAccess.Status.ALLOWED,
            role=AccessRole.USER,
        )

        self.client.force_login(admin_user)
        response = self.client.post(
            reverse("account-pending-access-requests-bulk-approve"),
            data={
                "requestIds": [
                    pending_request.id,
                    decided_request.id,
                    999999,
                ],
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "partial")
        self.assertEqual(
            payload["summary"],
            {"requested": 3, "approved": 1, "failed": 2},
        )
        self.assertEqual(
            {row["requestId"] for row in payload["approved"]},
            {pending_request.id},
        )
        self.assertEqual(
            {
                (row["requestId"], row["error"])
                for row in payload["failed"]
            },
            {
                (decided_request.id, "invalid_status_transition"),
                (999999, "request_not_found"),
            },
        )
        pending_request.refresh_from_db()
        decided_request.refresh_from_db()
        self.assertEqual(pending_request.status, UserAccess.Status.ALLOWED)
        self.assertEqual(decided_request.status, UserAccess.Status.ALLOWED)

    def test_pending_access_request_management_requires_portal_admin(self) -> None:
        """일반 사용자는 전체 승인 대기 조회와 일괄 승인을 실행할 수 없어야 합니다."""

        pending_request = UserAccess.objects.create(
            user=self.manager,
            scope=AccessScope.objects.get(key="appstore"),
            department="Dept",
            status=UserAccess.Status.PENDING,
        )
        self.client.force_login(self.user)

        list_response = self.client.get(
            reverse("account-pending-access-requests"),
        )
        bulk_response = self.client.post(
            reverse("account-pending-access-requests-bulk-approve"),
            data={"requestIds": [pending_request.id]},
            content_type="application/json",
        )

        self.assertEqual(list_response.status_code, 403)
        self.assertEqual(bulk_response.status_code, 403)
        pending_request.refresh_from_db()
        self.assertEqual(pending_request.status, UserAccess.Status.PENDING)

    def test_access_matrix_blocks_apps_when_portal_access_is_denied(self) -> None:
        """Portal 차단 사용자의 앱 명시 허용은 보존하되 최종 접근은 차단해야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        portal_scope = AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL)
        appstore_scope = AccessScope.objects.get(key="appstore")
        UserAccess.objects.create(
            user=self.user,
            scope=portal_scope,
            department="Dept",
            status=UserAccess.Status.DENIED,
            role="user",
            reason="Portal 운영 차단",
        )
        UserAccess.objects.create(
            user=self.user,
            scope=appstore_scope,
            department="Dept",
            status=UserAccess.Status.ALLOWED,
            role="user",
        )

        self.client.force_login(admin_user)
        response = self.client.get(
            reverse("account-access-matrix"),
            {"search": self.user.knox_id, "pageSize": 5},
        )

        self.assertEqual(response.status_code, 200)
        row = response.json()["results"][0]
        portal_access = row["accesses"][ACCESS_SCOPE_PORTAL]
        app_access = row["accesses"]["appstore"]
        self.assertFalse(portal_access["allowed"])
        self.assertFalse(app_access["allowed"])
        self.assertTrue(app_access["blockedByPortal"])
        self.assertEqual(app_access["source"], AccessSource.PORTAL_ACCESS_REQUIRED)
        self.assertEqual(app_access["explicitStatus"], UserAccess.Status.ALLOWED)
        self.assertEqual(app_access["underlyingAccess"]["source"], AccessSource.EXPLICIT_ALLOWED)
        self.assertTrue(app_access["underlyingAccess"]["allowed"])

    def test_access_users_filters_portal_blocked_apps_by_final_source(self) -> None:
        """앱 권한 목록 필터는 Portal 우선 차단 source를 최종 판정으로 사용해야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        UserAccess.objects.create(
            user=self.user,
            scope=AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL),
            status=UserAccess.Status.DENIED,
            role="user",
        )
        UserAccess.objects.create(
            user=self.user,
            scope=AccessScope.objects.get(key="appstore"),
            status=UserAccess.Status.ALLOWED,
            role="user",
        )

        self.client.force_login(admin_user)
        response = self.client.get(
            reverse("account-access-users"),
            {
                "scope": "appstore",
                "status": "denied",
                "source": AccessSource.PORTAL_ACCESS_REQUIRED,
            },
        )

        self.assertEqual(response.status_code, 200)
        rows_by_user_id = {row["user"]["id"]: row for row in response.json()["results"]}
        self.assertIn(self.user.id, rows_by_user_id)
        self.assertTrue(rows_by_user_id[self.user.id]["access"]["blockedByPortal"])

    def test_access_matrix_requires_portal_admin(self) -> None:
        """일반 사용자는 통합 권한 매트릭스를 조회할 수 없어야 합니다."""

        self.client.force_login(self.user)

        response = self.client.get(reverse("account-access-matrix"))

        self.assertEqual(response.status_code, 403)

    def test_access_matrix_decision_updates_selected_app_scope(self) -> None:
        """매트릭스의 수동 권한 변경은 선택한 앱 scope에만 저장되어야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        self.client.force_login(admin_user)

        response = self.client.post(
            reverse("account-access-user-decision", kwargs={"user_id": self.user.id}),
            data='{"scope": "appstore", "action": "grant", "reason": "매트릭스 부여 검증"}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        app_access = UserAccess.objects.get(user=self.user, scope__key="appstore")
        self.assertEqual(app_access.status, UserAccess.Status.ALLOWED)
        self.assertEqual(app_access.role, "user")
        self.assertEqual(response.json()["row"]["access"]["role"], "user")
        self.assertFalse(
            UserAccess.objects.filter(user=self.user, scope__key=ACCESS_SCOPE_PORTAL).exists()
        )

    def test_access_matrix_can_explicitly_deny_and_reset_unrequested_scope(self) -> None:
        """미설정 앱도 명시 차단할 수 있고 다시 자동 규칙 상태로 되돌릴 수 있어야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        self.client.force_login(admin_user)
        endpoint = reverse(
            "account-access-user-decision",
            kwargs={"user_id": self.user.id},
        )

        deny_response = self.client.post(
            endpoint,
            data='{"scope": "appstore", "action": "revoke", "reason": "매트릭스 차단 검증"}',
            content_type="application/json",
        )
        reset_response = self.client.post(
            endpoint,
            data='{"scope": "appstore", "action": "reset_to_policy", "reason": "자동 규칙 복귀 검증"}',
            content_type="application/json",
        )

        self.assertEqual(deny_response.status_code, 200)
        self.assertEqual(
            deny_response.json()["row"]["access"]["explicitStatus"],
            UserAccess.Status.DENIED,
        )
        self.assertEqual(reset_response.status_code, 200)
        self.assertIsNone(reset_response.json()["row"]["access"]["explicitStatus"])
        self.assertFalse(
            UserAccess.objects.filter(user=self.user, scope__key="appstore").exists()
        )

    def test_scope_access_decision_supports_fixed_roles(self) -> None:
        """앱 scope도 Portal과 동일하게 user/admin 역할 변경을 지원해야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        self.client.force_login(admin_user)
        endpoint = reverse("account-access-user-decision", kwargs={"user_id": self.user.id})

        grant_response = self.client.post(
            endpoint,
            data='{"scope": "appstore", "action": "grant", "role": "admin", "reason": "관리자 부여 검증"}',
            content_type="application/json",
        )
        change_role_response = self.client.post(
            endpoint,
            data='{"scope": "appstore", "action": "change_role", "role": "user", "reason": "일반 역할 변경 검증"}',
            content_type="application/json",
        )

        self.assertEqual(grant_response.status_code, 200)
        self.assertEqual(grant_response.json()["row"]["access"]["role"], "admin")
        self.assertEqual(change_role_response.status_code, 200)
        self.assertEqual(change_role_response.json()["row"]["access"]["role"], "user")

    def test_revoked_admin_role_does_not_return_on_roleless_grant(self) -> None:
        """차단된 관리자 권한은 역할 없는 재부여에서 일반 사용자로만 복원되어야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        self.client.force_login(admin_user)
        endpoint = reverse("account-access-user-decision", kwargs={"user_id": self.user.id})

        grant_admin_response = self.client.post(
            endpoint,
            data='{"scope": "appstore", "action": "grant", "role": "admin", "reason": "관리자 부여 검증"}',
            content_type="application/json",
        )
        revoke_response = self.client.post(
            endpoint,
            data='{"scope": "appstore", "action": "revoke", "reason": "관리자 권한 회수 검증"}',
            content_type="application/json",
        )
        denied_access = UserAccess.objects.get(user=self.user, scope__key="appstore")

        self.assertEqual(grant_admin_response.status_code, 200)
        self.assertEqual(revoke_response.status_code, 200)
        self.assertEqual(revoke_response.json()["row"]["access"]["explicitStatus"], "denied")
        self.assertEqual(denied_access.status, UserAccess.Status.DENIED)
        self.assertEqual(denied_access.role, "user")

        roleless_grant_response = self.client.post(
            endpoint,
            data='{"scope": "appstore", "action": "grant", "reason": "일반 역할 복원 검증"}',
            content_type="application/json",
        )
        denied_access.refresh_from_db()

        self.assertEqual(denied_access.status, UserAccess.Status.ALLOWED)
        self.assertEqual(denied_access.role, "user")
        self.assertEqual(roleless_grant_response.status_code, 200)
        self.assertEqual(roleless_grant_response.json()["row"]["access"]["role"], "user")

    def test_database_rejects_admin_role_for_non_allowed_access(self) -> None:
        """DB는 pending·denied 상태에 admin 역할을 저장하지 못하게 해야 합니다."""

        scope = AccessScope.objects.create(
            key="role-state-constraint",
            name="역할 상태 제약 검증",
            scope_type=AccessScope.ScopeTypes.FEATURE,
        )

        for status in (UserAccess.Status.PENDING, UserAccess.Status.DENIED):
            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    UserAccess.objects.create(
                        scope=scope,
                        user=self.user,
                        status=status,
                        role="admin",
                    )

    def test_scope_access_policy_rejects_removed_role_field(self) -> None:
        """자동 정책 API는 제거된 role 입력을 조용히 허용하지 않아야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        self.client.force_login(admin_user)
        endpoint = reverse("account-access-policy-rules")

        role_response = self.client.post(
            endpoint,
            data='{"scope":"appstore","ruleType":"department","value":"Role Dept","role":"admin"}',
            content_type="application/json",
        )
        create_response = self.client.post(
            endpoint,
            data='{"scope":"appstore","ruleType":"department","value":"Allowed Dept"}',
            content_type="application/json",
        )

        self.assertEqual(role_response.status_code, 400)
        self.assertEqual(
            role_response.json()["details"]["unexpectedFields"],
            ["role"],
        )
        self.assertEqual(create_response.status_code, 201)
        self.assertNotIn("role", create_response.json()["policyRule"])
        self.assertTrue(
            AccessPolicyRule.objects.filter(scope__key="appstore", value="Allowed Dept").exists()
        )

    def test_access_management_api_rejects_removed_input_aliases(self) -> None:
        """접근 관리 API는 제거된 body·query 별칭을 명시적으로 거절해야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        self.client.force_login(admin_user)

        query_response = self.client.get(
            reverse("account-access-users"),
            {"page_size": "5", "q": self.user.knox_id},
        )
        decision_response = self.client.post(
            reverse("account-access-user-decision", kwargs={"user_id": self.user.id}),
            data={
                "scope": ACCESS_SCOPE_PORTAL,
                "action": "grant",
                "userId": self.user.id,
            },
            content_type="application/json",
        )
        missing_scope_response = self.client.post(
            reverse("account-access-user-decision", kwargs={"user_id": self.user.id}),
            data={"action": "grant"},
            content_type="application/json",
        )
        invalid_bulk_response = self.client.post(
            reverse("account-access-user-decision", kwargs={"user_id": self.user.id}),
            data={
                "scope": "appstore",
                "action": "grant",
                "approveAllApps": True,
            },
            content_type="application/json",
        )
        policy_response = self.client.post(
            reverse("account-access-policy-rules"),
            data={"ruleType": "department", "value": "Missing Scope"},
            content_type="application/json",
        )

        self.assertEqual(query_response.status_code, 400)
        self.assertEqual(
            query_response.json(),
            {
                "error": "invalid_query",
                "details": {
                    "unexpectedFields": ["page_size", "q"],
                },
            },
        )
        self.assertEqual(decision_response.status_code, 400)
        self.assertEqual(
            decision_response.json()["details"]["unexpectedFields"],
            ["userId"],
        )
        self.assertEqual(missing_scope_response.status_code, 400)
        self.assertIn("scope", missing_scope_response.json()["details"])
        self.assertEqual(invalid_bulk_response.status_code, 400)
        self.assertIn("approveAllApps", invalid_bulk_response.json()["details"])
        self.assertEqual(policy_response.status_code, 400)
        self.assertIn("scope", policy_response.json()["details"])

    def test_access_management_users_combined_status_source_filter_requires_both(self) -> None:
        """권한 관리 복합 필터는 status와 source를 모두 만족하는 사용자만 반환해야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        User = get_user_model()
        pending_user = User.objects.create_user(
            sabun="S52000",
            password="test-password",
            knox_id="knox-52000",
            department="OtherDept",
        )
        UserAccess.objects.create(
            user=pending_user,
            scope=AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL),
            department="OtherDept",
            status=UserAccess.Status.PENDING,
        )

        self.client.force_login(admin_user)
        impossible_response = self.client.get(
            reverse("account-access-users"),
            {"status": "pending", "source": "policy_department"},
        )
        self.assertEqual(impossible_response.status_code, 200)
        self.assertEqual(impossible_response.json()["results"], [])

        policy_allowed_response = self.client.get(
            reverse("account-access-users"),
            {"status": "allowed", "source": "policy_department"},
        )
        self.assertEqual(policy_allowed_response.status_code, 200)
        self.assertIn(self.user.id, {row["user"]["id"] for row in policy_allowed_response.json()["results"]})
        self.assertNotIn(pending_user.id, {row["user"]["id"] for row in policy_allowed_response.json()["results"]})

    def test_access_management_filter_uses_affiliation_for_blank_account_department(self) -> None:
        """공백 계정 부서는 실제 판정처럼 현재 소속 부서로 대체해야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        self.user.department = "   "
        self.user.save(update_fields=["department"])
        self.client.force_login(admin_user)

        response = self.client.get(
            reverse("account-access-users"),
            {
                "status": "allowed",
                "source": "policy_department",
                "search": self.user.knox_id,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [row["user"]["id"] for row in response.json()["results"]],
            [self.user.id],
        )
        self.assertEqual(
            response.json()["results"][0]["access"]["department"],
            "Dept",
        )

    def test_access_management_department_filter_uses_resolved_department(self) -> None:
        """부서 필터는 정책 판정과 같은 계정 부서 우선·공백 제거 규칙을 사용해야 합니다."""

        User = get_user_model()
        affiliation_only_user = User.objects.create_user(
            sabun="S52001",
            password="test-password",
            knox_id="knox-52001",
            department="Direct Department",
        )
        _set_current_affiliation(
            affiliation_only_user,
            department="Affiliation Department",
            user_sdwt_prod="group-filter-affiliation",
        )
        trimmed_direct_user = User.objects.create_user(
            sabun="S52002",
            password="test-password",
            knox_id="knox-52002",
            department="  Trimmed Department  ",
        )
        _set_current_affiliation(
            trimmed_direct_user,
            department="Other Department",
            user_sdwt_prod="group-filter-trimmed",
        )

        affiliation_rows = list_access_management_users(
            search=None,
            department="Affiliation Department",
        )
        trimmed_rows = list_access_management_users(
            search=None,
            department="Trimmed Department",
        )

        self.assertNotIn(
            affiliation_only_user.id,
            set(affiliation_rows.values_list("id", flat=True)),
        )
        self.assertIn(
            trimmed_direct_user.id,
            set(trimmed_rows.values_list("id", flat=True)),
        )

    def test_access_management_users_inactive_scope_uses_effective_status_filter(self) -> None:
        """비활성 scope에서는 명시 상태 fast filter보다 최종 inactive 판정을 우선해야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        scope = AccessScope.objects.get(key="appstore")
        UserAccess.objects.create(
            user=self.user,
            scope=scope,
            department=self.user.department,
            status=UserAccess.Status.DENIED,
            reason="운영 차단",
        )
        scope.is_active = False
        scope.save(update_fields=["is_active"])

        self.client.force_login(admin_user)
        denied_response = self.client.get(
            reverse("account-access-users"),
            {"scope": scope.key, "status": "denied"},
        )
        explicit_denied_response = self.client.get(
            reverse("account-access-users"),
            {"scope": scope.key, "source": "explicit_denied"},
        )
        inactive_response = self.client.get(
            reverse("account-access-users"),
            {"scope": scope.key, "status": "inactive"},
        )

        self.assertEqual(denied_response.status_code, 200)
        self.assertEqual(explicit_denied_response.status_code, 200)
        self.assertEqual(inactive_response.status_code, 200)
        self.assertNotIn(self.user.id, {row["user"]["id"] for row in denied_response.json()["results"]})
        self.assertNotIn(self.user.id, {row["user"]["id"] for row in explicit_denied_response.json()["results"]})
        self.assertIn(self.user.id, {row["user"]["id"] for row in inactive_response.json()["results"]})

    def test_access_management_reset_to_policy_restores_policy_allowed(self) -> None:
        """명시 차단을 정책 기준으로 복귀하면 부서 정책 허용이 다시 적용되어야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        scope = AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL)
        self.user.department = "Dept"
        self.user.save(update_fields=["department"])
        UserAccess.objects.create(
            user=self.user,
            scope=scope,
            department="Dept",
            status=UserAccess.Status.DENIED,
            reason="임시 차단",
        )

        self.client.force_login(admin_user)
        response = self.client.post(
            reverse("account-access-user-decision", kwargs={"user_id": self.user.id}),
            data='{"scope": "portal", "action": "reset_to_policy", "reason": "정책 권한 복귀 검증"}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["row"]["access"]["source"], "policy_department")
        self.assertFalse(UserAccess.objects.filter(user=self.user, scope=scope).exists())
        self.assertTrue(get_access_payload(scope_key=ACCESS_SCOPE_PORTAL, user=self.user)["allowed"])
        self.assertTrue(
            AccessAuditLog.objects.filter(
                action=AccessAuditLog.Actions.RESET_TO_POLICY,
                target_user=self.user,
                actor=admin_user,
            ).exists()
        )

    def test_access_policy_rule_management_crud_and_audit_log(self) -> None:
        """관리자는 기본 허용 정책 규칙을 생성, 수정, 삭제하고 감사 로그를 남길 수 있어야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        self.client.force_login(admin_user)

        create_response = self.client.post(
            reverse("account-access-policy-rules"),
            data='{"scope": "portal", "ruleType": "department", "value": "NewDept", "isActive": true}',
            content_type="application/json",
        )
        self.assertEqual(create_response.status_code, 201)
        rule_id = create_response.json()["policyRule"]["id"]
        self.assertNotIn("role", create_response.json()["policyRule"])

        patch_response = self.client.patch(
            reverse("account-access-policy-rule-detail", kwargs={"rule_id": rule_id}),
            data='{"isActive": false}',
            content_type="application/json",
        )
        self.assertEqual(patch_response.status_code, 200)
        self.assertFalse(patch_response.json()["policyRule"]["isActive"])
        collection_patch_response = self.client.patch(
            reverse("account-access-policy-rules"),
            data='{"isActive": true}',
            content_type="application/json",
        )
        detail_post_response = self.client.post(
            reverse(
                "account-access-policy-rule-detail",
                kwargs={"rule_id": rule_id},
            ),
            data='{"isActive": true}',
            content_type="application/json",
        )
        self.assertEqual(collection_patch_response.status_code, 405)
        self.assertEqual(detail_post_response.status_code, 405)

        list_response = self.client.get(reverse("account-access-policy-rules"))
        self.assertEqual(list_response.status_code, 200)
        self.assertIn(rule_id, {row["id"] for row in list_response.json()["results"]})

        delete_response = self.client.delete(
            reverse("account-access-policy-rule-detail", kwargs={"rule_id": rule_id})
        )
        self.assertEqual(delete_response.status_code, 200)
        self.assertFalse(AccessPolicyRule.objects.filter(id=rule_id).exists())
        self.assertTrue(
            AccessAuditLog.objects.filter(
                action=AccessAuditLog.Actions.POLICY_CREATE,
                actor=admin_user,
            ).exists()
        )
        self.assertTrue(
            AccessAuditLog.objects.filter(
                action=AccessAuditLog.Actions.POLICY_UPDATE,
                actor=admin_user,
            ).exists()
        )
        self.assertTrue(
            AccessAuditLog.objects.filter(
                action=AccessAuditLog.Actions.POLICY_DELETE,
                actor=admin_user,
            ).exists()
        )
        audit_response = self.client.get(
            reverse("account-access-audit-logs"),
            {"action": AccessAuditLog.Actions.POLICY_DELETE},
        )
        self.assertEqual(audit_response.status_code, 200)
        self.assertEqual(audit_response.json()["results"][0]["policyRule"]["value"], "NewDept")

    def test_access_policy_rule_list_can_return_all_scopes(self) -> None:
        """정책 목록은 매트릭스 구성을 위해 모든 scope 규칙을 함께 반환해야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        appstore_scope = AccessScope.objects.get(key="appstore")
        appstore_rule = AccessPolicyRule.objects.create(
            scope=appstore_scope,
            rule_type=AccessPolicyRule.RuleTypes.DEPARTMENT,
            value="MatrixListDept",
        )
        inactive_scope = AccessScope.objects.create(
            key="policy-matrix-list-inactive",
            name="비활성 정책 목록 제외",
            scope_type=AccessScope.ScopeTypes.APP,
            is_active=False,
        )
        inactive_rule = AccessPolicyRule.objects.create(
            scope=inactive_scope,
            rule_type=AccessPolicyRule.RuleTypes.DEPARTMENT,
            value="MatrixListInactiveDept",
        )
        self.client.force_login(admin_user)

        response = self.client.get(
            reverse("account-access-policy-rules"),
            {"scope": "all"},
        )

        self.assertEqual(response.status_code, 200)
        rules = response.json()["results"]
        self.assertIn(appstore_rule.id, {rule["id"] for rule in rules})
        self.assertNotIn(inactive_rule.id, {rule["id"] for rule in rules})
        self.assertIn(ACCESS_SCOPE_PORTAL, {rule["scope"] for rule in rules})

    def test_access_policy_rule_bulk_apply_creates_updates_and_skips_same_state(self) -> None:
        """정책 일괄 적용은 모든 대상 scope를 같은 상태로 맞추고 동일 상태는 건너뛰어야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        portal_scope = AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL)
        appstore_scope = AccessScope.objects.get(key="appstore")
        observer_scope = AccessScope.objects.get(key="observer")
        AccessPolicyRule.objects.create(
            scope=portal_scope,
            rule_type=AccessPolicyRule.RuleTypes.DEPARTMENT,
            value="MatrixBulkDept",
            is_active=False,
        )
        AccessPolicyRule.objects.create(
            scope=appstore_scope,
            rule_type=AccessPolicyRule.RuleTypes.DEPARTMENT,
            value="MatrixBulkDept",
            is_active=True,
        )
        self.client.force_login(admin_user)

        response = self.client.post(
            reverse("account-access-policy-rules-bulk-apply"),
            data={
                "value": "MatrixBulkDept",
                "scopeKeys": [
                    ACCESS_SCOPE_PORTAL,
                    "appstore",
                    "observer",
                    "observer",
                ],
                "isActive": True,
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["summary"], {"total": 3, "updated": 2, "unchanged": 1})
        rules = AccessPolicyRule.objects.filter(value="MatrixBulkDept")
        self.assertEqual(rules.count(), 3)
        self.assertFalse(rules.filter(is_active=False).exists())
        self.assertEqual(
            AccessAuditLog.objects.filter(
                actor=admin_user,
                action=AccessAuditLog.Actions.POLICY_CREATE,
                policy_rule__value="MatrixBulkDept",
            ).count(),
            1,
        )
        self.assertEqual(
            AccessAuditLog.objects.filter(
                actor=admin_user,
                action=AccessAuditLog.Actions.POLICY_UPDATE,
                policy_rule__value="MatrixBulkDept",
            ).count(),
            1,
        )

        disable_response = self.client.post(
            reverse("account-access-policy-rules-bulk-apply"),
            data={
                "value": "MatrixBulkDept",
                "scopeKeys": [ACCESS_SCOPE_PORTAL, "appstore", "observer"],
                "isActive": False,
            },
            content_type="application/json",
        )
        self.assertEqual(disable_response.status_code, 200)
        self.assertEqual(disable_response.json()["summary"]["updated"], 3)
        self.assertFalse(
            AccessPolicyRule.objects.filter(
                value="MatrixBulkDept",
                is_active=True,
            ).exists()
        )

    def test_access_policy_rule_bulk_apply_rejects_unmanaged_scope_without_writes(self) -> None:
        """정책 일괄 적용은 비활성 또는 존재하지 않는 scope를 포함하면 전체를 거절해야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        inactive_scope = AccessScope.objects.create(
            key="policy-matrix-inactive",
            name="비활성 정책 매트릭스",
            scope_type=AccessScope.ScopeTypes.APP,
            is_active=False,
        )
        self.client.force_login(admin_user)

        response = self.client.post(
            reverse("account-access-policy-rules-bulk-apply"),
            data={
                "value": "InvalidMatrixDept",
                "scopeKeys": [ACCESS_SCOPE_PORTAL, inactive_scope.key, "missing-scope"],
                "isActive": True,
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["scopeKeys"],
            [inactive_scope.key, "missing-scope"],
        )
        self.assertFalse(
            AccessPolicyRule.objects.filter(value="InvalidMatrixDept").exists()
        )

    def test_access_policy_rule_bulk_apply_rolls_back_when_audit_creation_fails(self) -> None:
        """정책 일괄 적용은 감사 로그 생성 실패 시 모든 scope 변경을 복구해야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        admin_user.refresh_from_db()

        with patch(
            "api.account.services.access_control.create_access_audit_log",
            side_effect=RuntimeError("audit failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "audit failed"):
                bulk_apply_access_policy_rules(
                    actor=admin_user,
                    scope_keys=[ACCESS_SCOPE_PORTAL, "appstore"],
                    value="RollbackMatrixDept",
                    is_active=True,
                )

        self.assertFalse(
            AccessPolicyRule.objects.filter(value="RollbackMatrixDept").exists()
        )

    def test_access_policy_rule_api_rejects_non_department_types(self) -> None:
        """정책 API는 부서 이외의 적용 기준을 거부해야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        self.client.force_login(admin_user)

        for rule_type in ("profile_role", "user_sdwt_prod_role", "authenticated"):
            with self.subTest(rule_type=rule_type):
                response = self.client.post(
                    reverse("account-access-policy-rules"),
                    data={"scope": "portal", "ruleType": rule_type, "value": "invalid"},
                    content_type="application/json",
                )

                self.assertEqual(response.status_code, 400)
                self.assertIn("ruleType", response.json()["details"])

        self.assertFalse(AccessPolicyRule.objects.filter(value="invalid").exists())

    def test_access_policy_mutations_roll_back_when_audit_creation_fails(self) -> None:
        """정책 생성, 수정, 삭제는 감사 로그 실패 시 모두 원래 상태로 복구되어야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        admin_user.refresh_from_db()

        with patch(
            "api.account.services.access_control.create_access_audit_log",
            side_effect=RuntimeError("audit failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "audit failed"):
                create_access_policy_rule(
                    actor=admin_user,
                    scope_key=ACCESS_SCOPE_PORTAL,
                    rule_type=AccessPolicyRule.RuleTypes.DEPARTMENT,
                    value="RollbackCreateDept",
                    is_active=True,
                )
        self.assertFalse(AccessPolicyRule.objects.filter(value="RollbackCreateDept").exists())

        scope = AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL)
        rule = AccessPolicyRule.objects.create(
            scope=scope,
            rule_type=AccessPolicyRule.RuleTypes.DEPARTMENT,
            value="RollbackMutationDept",
        )
        with patch(
            "api.account.services.access_control.create_access_audit_log",
            side_effect=RuntimeError("audit failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "audit failed"):
                update_access_policy_rule(
                    actor=admin_user,
                    rule_id=rule.id,
                    rule_type=None,
                    value=None,
                    is_active=None,
                )
        rule.refresh_from_db()
        self.assertEqual(rule.value, "RollbackMutationDept")

        with patch(
            "api.account.services.access_control.create_access_audit_log",
            side_effect=RuntimeError("audit failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "audit failed"):
                delete_access_policy_rule(actor=admin_user, rule_id=rule.id)
        self.assertTrue(AccessPolicyRule.objects.filter(id=rule.id).exists())

    def test_access_audit_api_prefers_event_policy_snapshot(self) -> None:
        """과거 정책 감사 응답은 이후 수정된 live 정책 값이 아니라 당시 snapshot을 반환해야 합니다."""

        admin_user = self.manager
        _grant_manage_access(admin_user)
        self.client.force_login(admin_user)
        create_response = self.client.post(
            reverse("account-access-policy-rules"),
            data='{"scope": "portal", "ruleType": "department", "value": "SnapshotBefore"}',
            content_type="application/json",
        )
        rule_id = create_response.json()["policyRule"]["id"]
        patch_response = self.client.patch(
            reverse("account-access-policy-rule-detail", kwargs={"rule_id": rule_id}),
            data='{"value": "SnapshotAfter"}',
            content_type="application/json",
        )
        self.assertEqual(patch_response.status_code, 200)

        audit_response = self.client.get(
            reverse("account-access-audit-logs"),
            {"action": AccessAuditLog.Actions.POLICY_CREATE},
        )
        matching_log = next(
            row for row in audit_response.json()["results"] if row["policyRule"]["id"] == rule_id
        )
        self.assertEqual(matching_log["policyRule"]["value"], "SnapshotBefore")
        self.assertNotIn("role", matching_log["policyRule"])

    def test_access_scope_admin_only_updates_mutable_fields_and_never_deletes(self) -> None:
        """Admin은 scope 생성·식별자 변경·삭제를 막고 운영 속성 변경만 기록해야 합니다."""

        from django.contrib.admin.sites import AdminSite
        from django.test import RequestFactory

        from api.account.admin import AccessScopeAdmin

        request = RequestFactory().post("/admin/")
        request.user = self.superuser
        scope_admin = AccessScopeAdmin(AccessScope, AdminSite())
        portal_scope = AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL)

        self.assertFalse(scope_admin.has_add_permission(request))
        self.assertIn("key", scope_admin.get_readonly_fields(request, portal_scope))
        self.assertIn("scope_type", scope_admin.get_readonly_fields(request, portal_scope))
        self.assertFalse(scope_admin.has_delete_permission(request, portal_scope))
        portal_scope.key = "renamed-portal"
        with self.assertRaises(ValidationError):
            scope_admin.save_model(request, portal_scope, form=None, change=True)
        portal_scope.refresh_from_db()
        self.assertEqual(portal_scope.key, ACCESS_SCOPE_PORTAL)
        with self.assertRaises(PermissionDenied):
            scope_admin.delete_model(request, portal_scope)

        appstore_scope = AccessScope.objects.get(key="appstore")
        self.assertIn("key", scope_admin.get_readonly_fields(request, appstore_scope))
        self.assertIn("scope_type", scope_admin.get_readonly_fields(request, appstore_scope))
        self.assertFalse(scope_admin.has_delete_permission(request, appstore_scope))
        appstore_scope.scope_type = AccessScope.ScopeTypes.FEATURE
        with self.assertRaises(ValidationError):
            scope_admin.save_model(request, appstore_scope, form=None, change=True)
        appstore_scope.refresh_from_db()
        self.assertEqual(appstore_scope.scope_type, AccessScope.ScopeTypes.APP)
        with self.assertRaises(PermissionDenied):
            scope_admin.delete_model(request, appstore_scope)

        app_scope = AccessScope.objects.create(
            key="audited-app",
            name="Audited App",
            scope_type=AccessScope.ScopeTypes.APP,
            requestable=False,
        )
        app_scope.name = "Audited App Updated"
        scope_admin.save_model(request, app_scope, form=None, change=True)
        audit_count = AccessAuditLog.objects.filter(
            action=AccessAuditLog.Actions.SCOPE_UPDATE,
            scope=app_scope,
        ).count()
        scope_admin.save_model(request, app_scope, form=None, change=True)
        with self.assertRaises(PermissionDenied):
            scope_admin.delete_model(request, app_scope)

        self.assertTrue(AccessScope.objects.filter(id=app_scope.id).exists())
        self.assertEqual(
            AccessAuditLog.objects.filter(
                action=AccessAuditLog.Actions.SCOPE_UPDATE,
                scope=app_scope,
            ).count(),
            audit_count,
        )
        self.assertTrue(
            AccessAuditLog.objects.filter(
                action=AccessAuditLog.Actions.SCOPE_UPDATE,
                before__name="Audited App",
                after__name="Audited App Updated",
            ).exists()
        )
        for audit_log in AccessAuditLog.objects.filter(
            action=AccessAuditLog.Actions.SCOPE_UPDATE,
        ):
            self.assertNotIn("id", audit_log.before)
            self.assertNotIn("id", audit_log.after)

    def test_access_audit_references_protect_scope_and_users_from_physical_delete(self) -> None:
        """감사 로그가 참조하는 scope와 사용자는 물리 삭제할 수 없어야 합니다."""

        scope = AccessScope.objects.create(
            key="protected-feature",
            name="보존 기능",
            scope_type=AccessScope.ScopeTypes.FEATURE,
        )
        AccessAuditLog.objects.create(
            scope=scope,
            actor=self.manager,
            target_user=self.user,
            action=AccessAuditLog.Actions.GRANT,
            after={"explicitStatus": "allowed", "role": "user"},
        )

        for target in (scope, self.manager, self.user):
            with self.subTest(target=target):
                with self.assertRaises(ProtectedError):
                    target.delete()

        scope.is_active = False
        scope.save(update_fields=["is_active", "updated_at"])
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        self.assertFalse(AccessScope.objects.get(pk=scope.pk).is_active)
        self.assertFalse(get_user_model().objects.get(pk=self.user.pk).is_active)

    def test_access_audit_log_admin_is_fully_read_only(self) -> None:
        """Django Admin에서 감사 로그를 추가, 수정, 삭제할 수 없어야 합니다."""

        from django.contrib.admin.sites import AdminSite
        from django.test import RequestFactory

        from api.account.admin import AccessAuditLogAdmin

        request = RequestFactory().get("/admin/")
        request.user = self.superuser
        audit_admin = AccessAuditLogAdmin(AccessAuditLog, AdminSite())

        self.assertFalse(audit_admin.has_add_permission(request))
        self.assertFalse(audit_admin.has_change_permission(request))
        self.assertFalse(audit_admin.has_delete_permission(request))
        self.assertEqual(
            set(audit_admin.readonly_fields),
            {
                "id",
                "scope",
                "actor",
                "target_user",
                "policy_rule",
                "affiliation",
                "action",
                "before",
                "after",
                "reason",
                "created_at",
            },
        )

    def test_access_audit_log_endpoint_requires_access_admin(self) -> None:
        """감사 로그는 Portal admin에게 전체 scope를 기본 제공하고 scope 필터를 지원해야 합니다."""

        self.client.force_login(self.user)
        forbidden_response = self.client.get(reverse("account-access-audit-logs"))
        self.assertEqual(forbidden_response.status_code, 403)

        admin_user = self.manager
        _grant_manage_access(admin_user)
        AccessAuditLog.objects.create(
            scope=AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL),
            actor=admin_user,
            target_user=self.user,
            action=AccessAuditLog.Actions.GRANT,
            after={"explicitStatus": "allowed"},
        )
        AccessAuditLog.objects.create(
            scope=AccessScope.objects.get(key="appstore"),
            actor=admin_user,
            target_user=self.user,
            action=AccessAuditLog.Actions.REVOKE,
            after={"explicitStatus": "denied"},
        )
        AccessAuditLog.objects.create(
            scope=AccessScope.objects.get(key="appstore"),
            actor=self.superuser,
            target_user=admin_user,
            action=AccessAuditLog.Actions.CHANGE_ROLE,
            before={"explicitStatus": "allowed", "role": "user"},
            after={"explicitStatus": "allowed", "role": "admin"},
        )

        self.client.force_login(admin_user)
        response = self.client.get(reverse("account-access-audit-logs"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["pagination"]["total"], 3)
        self.assertEqual(
            {row["action"] for row in response.json()["results"]},
            {
                AccessAuditLog.Actions.GRANT,
                AccessAuditLog.Actions.REVOKE,
                AccessAuditLog.Actions.CHANGE_ROLE,
            },
        )

        portal_response = self.client.get(
            reverse("account-access-audit-logs"),
            {"scope": ACCESS_SCOPE_PORTAL},
        )
        self.assertEqual(portal_response.status_code, 200)
        self.assertEqual(portal_response.json()["pagination"]["total"], 1)
        self.assertEqual(portal_response.json()["results"][0]["action"], AccessAuditLog.Actions.GRANT)

        all_action_response = self.client.get(
            reverse("account-access-audit-logs"),
            {"action": "all"},
        )
        self.assertEqual(all_action_response.status_code, 200)
        self.assertEqual(all_action_response.json()["pagination"]["total"], 3)

    def test_access_policy_rule_only_accepts_department_type(self) -> None:
        """모델 검증과 DB 제약은 부서 이외의 정책 유형을 차단해야 합니다."""

        scope = AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL)
        self.assertEqual(AccessPolicyRule.RuleTypes.values, ["department"])

        with self.assertRaises(ValidationError):
            AccessPolicyRule(
                scope=scope,
                rule_type="profile_role",
                value="viewer",
            ).full_clean()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AccessPolicyRule.objects.create(
                    scope=scope,
                    rule_type="authenticated",
                    value="*",
                )

    def test_access_policy_rule_requires_department_value(self) -> None:
        """부서 정책에는 비교할 부서명이 필요합니다."""

        scope = AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL)
        rule = AccessPolicyRule(
            scope=scope,
            rule_type=AccessPolicyRule.RuleTypes.DEPARTMENT,
            value="",
        )

        with self.assertRaises(ValidationError):
            rule.full_clean()

    def test_affiliation_identifier_is_unique_after_trim_and_lower(self) -> None:
        """소속 식별자는 앞뒤 공백과 대소문자를 무시해 중복을 차단해야 합니다."""

        Affiliation.objects.create(
            department="Dept",
            line="Line",
            user_sdwt_prod="Case-Group",
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Affiliation.objects.create(
                    department="Dept",
                    line="Line",
                    user_sdwt_prod=" case-group ",
                )

    def test_affiliation_identifier_rejects_blank_and_whitespace(self) -> None:
        """소속 식별자는 DB에서도 빈 값과 앞뒤 공백을 허용하지 않아야 합니다."""

        for value in ("", " group-with-space "):
            with self.subTest(value=value), self.assertRaises(IntegrityError):
                with transaction.atomic():
                    Affiliation.objects.create(
                        department="Dept",
                        line="Line",
                        user_sdwt_prod=value,
                    )

    def test_affiliation_access_role_has_database_constraint(self) -> None:
        """잘못된 소속 접근 역할은 DB 제약에서 차단해야 합니다."""

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                UserSdwtProdAccess.objects.create(
                    user=self.user,
                    affiliation=Affiliation.objects.get(user_sdwt_prod="group-b"),
                    role="owner",
                )

    def test_user_has_only_one_pending_affiliation_change(self) -> None:
        """사용자별 승인 대기 소속 요청은 DB에서도 한 건만 허용해야 합니다."""

        UserSdwtProdChange.objects.create(
            user=self.user,
            from_user_sdwt_prod="group-a",
            to_user_sdwt_prod="group-b",
            effective_from=timezone.now(),
            status=UserSdwtProdChange.Status.PENDING,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                UserSdwtProdChange.objects.create(
                    user=self.user,
                    from_user_sdwt_prod="group-a",
                    to_user_sdwt_prod="group-c",
                    effective_from=timezone.now(),
                    status=UserSdwtProdChange.Status.PENDING,
                )

    def test_access_policy_rule_normalizes_value_and_rejects_semantic_duplicates(self) -> None:
        """정책 값은 공백을 제거하고 대소문자가 다른 의미상 중복도 차단해야 합니다."""

        scope = AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL)
        normalized_rule = AccessPolicyRule(
            scope=scope,
            rule_type=AccessPolicyRule.RuleTypes.DEPARTMENT,
            value="  New Department  ",
        )
        normalized_rule.full_clean()
        self.assertEqual(normalized_rule.value, "New Department")

        AccessPolicyRule.objects.create(
            scope=scope,
            rule_type=AccessPolicyRule.RuleTypes.DEPARTMENT,
            value="Case Department",
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AccessPolicyRule.objects.create(
                    scope=scope,
                    rule_type=AccessPolicyRule.RuleTypes.DEPARTMENT,
                    value=" case department ",
                )

    def test_access_permission_integrity_command_requires_explicit_phase(self) -> None:
        """운영 점검 명령은 migration 시점을 생략하면 실행되지 않아야 합니다."""

        with self.assertRaises(CommandError):
            call_command("check_access_permission_integrity", stdout=StringIO())

    def test_access_permission_integrity_command_supports_both_phases(self) -> None:
        """운영 점검 명령은 직전·현재 release의 고정 역할 계약을 검사해야 합니다."""

        AccessPolicyRule.objects.create(
            scope=AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL),
            rule_type=AccessPolicyRule.RuleTypes.DEPARTMENT,
            value="Safe User Policy",
        )

        for phase in ("pre-migration", "post-migration"):
            with self.subTest(phase=phase):
                output = StringIO()
                call_command(
                    "check_access_permission_integrity",
                    phase=phase,
                    stdout=output,
                )
                self.assertIn(f"phase={phase}", output.getvalue())

        UserAccess.objects.create(
            user=self.user,
            scope=AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL),
            status=UserAccess.Status.ALLOWED,
            role="user",
        )
        for phase in ("pre-migration", "post-migration"):
            output = StringIO()
            call_command(
                "check_access_permission_integrity",
                phase=phase,
                stdout=output,
            )
            self.assertIn(f"phase={phase}", output.getvalue())

    def test_access_permission_integrity_uses_database_lower_contract(self) -> None:
        """Unicode 정책 값도 PostgreSQL Lower 유일 제약과 같은 기준으로 검사해야 합니다."""

        scope = AccessScope.objects.get(key=ACCESS_SCOPE_PORTAL)
        AccessPolicyRule.objects.create(
            scope=scope,
            rule_type=AccessPolicyRule.RuleTypes.DEPARTMENT,
            value="Straße",
        )
        AccessPolicyRule.objects.create(
            scope=scope,
            rule_type=AccessPolicyRule.RuleTypes.DEPARTMENT,
            value="STRASSE",
        )
        output = StringIO()

        call_command(
            "check_access_permission_integrity",
            phase="post-migration",
            stdout=output,
        )

        self.assertIn("phase=post-migration", output.getvalue())

    def test_access_permission_integrity_allows_dormant_inactive_affiliation_grant(self) -> None:
        """비활성 소속의 보존 grant는 실효 권한이 아니므로 무결성 오류가 아니어야 합니다."""

        affiliation = Affiliation.objects.create(
            department="Dept",
            line="Line",
            user_sdwt_prod="inactive-scope-group",
            is_active=False,
        )
        UserScopeAffiliationGrant.objects.create(
            user=self.user,
            scope=AccessScope.objects.get(key="emails"),
            affiliation=affiliation,
        )

        output = StringIO()
        call_command(
            "check_access_permission_integrity",
            phase="post-migration",
            stdout=output,
        )
        self.assertIn("phase=post-migration", output.getvalue())

    def test_auth_me_does_not_create_access_row_for_current_affiliation(self) -> None:
        """auth_me 호출이 현재 소속 접근 권한 행을 백필하지 않는지 확인합니다."""
        self.assertFalse(
            UserSdwtProdAccess.objects.filter(
                user=self.user,
                affiliation__user_sdwt_prod__iexact="group-a",
            ).exists()
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("auth-me"))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            UserSdwtProdAccess.objects.filter(
                user=self.user,
                affiliation__user_sdwt_prod__iexact="group-a",
            ).exists()
        )

    def test_account_affiliation_request_and_approval_flow(self) -> None:
        """소속 변경 요청과 승인 플로우가 정상 동작하는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 소속 변경 요청 생성
        # -----------------------------------------------------------------------------
        self.client.force_login(self.user)

        create_response = self.client.post(
            reverse("account-affiliation"),
            data='{"userSdwtProd":"group-b"}',
            content_type="application/json",
        )
        self.assertEqual(create_response.status_code, 202)
        change_id = create_response.json()["changeId"]

        # -----------------------------------------------------------------------------
        # 2) 요청 목록 조회
        # -----------------------------------------------------------------------------
        self.client.force_login(self.manager)
        list_response = self.client.get(reverse("account-affiliation-requests"))
        self.assertEqual(list_response.status_code, 200)

        # -----------------------------------------------------------------------------
        # 3) 승인 요청
        # -----------------------------------------------------------------------------
        approve_response = self.client.post(
            reverse("account-affiliation-approve"),
            data='{"changeId": %d, "decision": "approve"}' % change_id,
            content_type="application/json",
        )
        self.assertEqual(approve_response.status_code, 200)

    def test_account_affiliation_post_rejects_unknown_fields(self) -> None:
        """사용자 소속 변경 API는 선언되지 않은 입력을 거절해야 합니다."""
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("account-affiliation"),
            data='{"userSdwtProd":"group-b","effectiveFrom":"2026-01-01T00:00:00Z"}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["unexpectedFields"], ["effectiveFrom"])

    def test_account_affiliation_rejection_reason_is_exposed(self) -> None:
        """거절 사유가 히스토리에 노출되는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 소속 변경 요청 생성
        # -----------------------------------------------------------------------------
        self.client.force_login(self.user)

        create_response = self.client.post(
            reverse("account-affiliation"),
            data='{"userSdwtProd":"group-b"}',
            content_type="application/json",
        )
        self.assertEqual(create_response.status_code, 202)
        change_id = create_response.json()["changeId"]

        # -----------------------------------------------------------------------------
        # 2) 관리자 거절 처리(거절 사유 포함)
        # -----------------------------------------------------------------------------
        self.client.force_login(self.manager)
        reject_response = self.client.post(
            reverse("account-affiliation-approve"),
            data='{"changeId": %d, "decision": "reject", "rejectionReason": "사유 확인 필요"}'
            % change_id,
            content_type="application/json",
        )
        self.assertEqual(reject_response.status_code, 200)

        # -----------------------------------------------------------------------------
        # 3) 요청자 히스토리 확인
        # -----------------------------------------------------------------------------
        self.client.force_login(self.user)
        overview_response = self.client.get(reverse("account-overview"))
        self.assertEqual(overview_response.status_code, 200)
        history = overview_response.json()["affiliationHistory"]
        self.assertTrue(history)
        self.assertEqual(history[0]["status"], "REJECTED")
        self.assertEqual(history[0]["rejectionReason"], "사유 확인 필요")

    def test_account_affiliation_rejects_non_string_user_sdwt_prod(self) -> None:
        """userSdwtProd 타입 오류는 400을 반환해야 합니다."""
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("account-affiliation"),
            data='{"userSdwtProd":123}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("userSdwtProd", response.json())

    def test_account_affiliation_api_rejects_removed_aliases(self) -> None:
        """SPA 소속 API는 제거된 snake_case와 이전 별칭을 거절해야 합니다."""

        self.client.force_login(self.manager)
        create_response = self.client.post(
            reverse("account-affiliation"),
            data={"user_sdwt_prod": "group-b"},
            content_type="application/json",
        )
        list_response = self.client.get(
            reverse("account-affiliation-requests"),
            {"q": self.user.knox_id, "page_size": 5, "user_sdwt_prod": "group-a"},
        )
        approval_response = self.client.post(
            reverse("account-affiliation-approve"),
            data={"id": 1, "decision": "reject", "rejection_reason": "별칭 검증"},
            content_type="application/json",
        )
        members_response = self.client.get(
            reverse("account-affiliation-members"),
            {"user_sdwt_prod": "group-a"},
        )

        self.assertEqual(create_response.status_code, 400)
        self.assertEqual(create_response.json()["unexpectedFields"], ["user_sdwt_prod"])
        self.assertEqual(list_response.status_code, 400)
        self.assertEqual(
            list_response.json()["unexpectedFields"],
            ["page_size", "q", "user_sdwt_prod"],
        )
        self.assertEqual(approval_response.status_code, 400)
        self.assertEqual(
            approval_response.json()["unexpectedFields"],
            ["id", "rejection_reason"],
        )
        self.assertEqual(members_response.status_code, 400)
        self.assertEqual(members_response.json()["unexpectedFields"], ["user_sdwt_prod"])

    def test_account_affiliation_reconfirm(self) -> None:
        """소속 재확인 플로우가 정상 응답하는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 외부 예측/재확인 데이터 준비
        # -----------------------------------------------------------------------------
        ExternalAffiliationSnapshot.objects.create(
            knox_id="knox-50000",
            predicted_user_sdwt_prod="group-b",
            source_updated_at=timezone.now(),
            last_seen_at=timezone.now(),
        )
        current_affiliation = UserCurrentAffiliation.objects.get(user=self.user)
        current_affiliation.requires_reconfirm = True
        current_affiliation.save(update_fields=["requires_reconfirm"])

        # -----------------------------------------------------------------------------
        # 2) 상태 조회
        # -----------------------------------------------------------------------------
        self.client.force_login(self.user)

        status_response = self.client.get(reverse("account-affiliation-reconfirm"))
        self.assertEqual(status_response.status_code, 200)
        self.assertTrue(status_response.json()["requiresReconfirm"])

        # -----------------------------------------------------------------------------
        # 3) 재확인 응답 전송
        # -----------------------------------------------------------------------------
        confirm_response = self.client.post(
            reverse("account-affiliation-reconfirm"),
            data='{"accepted": true, "user_sdwt_prod": "group-b"}',
            content_type="application/json",
        )
        self.assertEqual(confirm_response.status_code, 200)

        self.user.refresh_from_db()
        self.assertEqual(get_current_user_sdwt_prod(user=self.user), "group-b")
        self.assertFalse(UserCurrentAffiliation.objects.get(user=self.user).requires_reconfirm)

    def test_account_affiliation_reconfirm_requires_flag(self) -> None:
        """재확인 플래그가 없으면 409를 반환하는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 외부 예측 데이터 준비
        # -----------------------------------------------------------------------------
        ExternalAffiliationSnapshot.objects.create(
            knox_id="knox-50000",
            predicted_user_sdwt_prod="group-b",
            source_updated_at=timezone.now(),
            last_seen_at=timezone.now(),
        )

        # -----------------------------------------------------------------------------
        # 2) 재확인 응답 전송
        # -----------------------------------------------------------------------------
        self.client.force_login(self.user)
        confirm_response = self.client.post(
            reverse("account-affiliation-reconfirm"),
            data='{"accepted": true, "user_sdwt_prod": "group-b"}',
            content_type="application/json",
        )

        # -----------------------------------------------------------------------------
        # 3) 결과 검증
        # -----------------------------------------------------------------------------
        self.assertEqual(confirm_response.status_code, 409)
        self.assertEqual(confirm_response.json().get("error"), "reconfirm not required")

    @override_settings(AIRFLOW_TRIGGER_TOKEN="token")
    def test_account_external_sync_and_grants(self) -> None:
        """외부 동기화/권한 부여 흐름을 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 외부 소속 동기화 호출
        # -----------------------------------------------------------------------------
        sync_response = self.client.post(
            reverse("account-external-affiliation-sync"),
            data='{"records":[{"knox_id":"knox-50000","department":"Dept","user_sdwt_prod":"group-a"}]}',
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer token",
        )
        self.assertEqual(sync_response.status_code, 200)

        # -----------------------------------------------------------------------------
        # 2) 매니저 권한 부여 및 조회
        # -----------------------------------------------------------------------------
        _grant_payload, grant_status = grant_or_revoke_access(
            grantor=self.manager,
            target_group="group-a",
            target_user=self.user,
            action="grant",
            role="member",
            reason="테스트 권한 변경",
        )
        self.assertEqual(grant_status, 200)

        overview = get_account_overview(user=self.manager, timezone_name="Asia/Seoul")
        self.assertTrue(overview["manageableGroups"]["groups"])

    def test_viewer_grant_for_current_affiliation_upgrades_to_member(self) -> None:
        """현재 소속에 viewer 권한을 부여하면 member로 승급되는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 대상 사용자 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        target = User.objects.create_user(
            sabun="S50003",
            password="test-password",
            knox_id="knox-50003",
        )
        _set_current_affiliation(target, user_sdwt_prod="group-a")

        # -----------------------------------------------------------------------------
        # 2) viewer 부여 요청
        # -----------------------------------------------------------------------------
        _grant_payload, grant_status = grant_or_revoke_access(
            grantor=self.manager,
            target_group="group-a",
            target_user=target,
            action="grant",
            role="viewer",
            reason="테스트 권한 변경",
        )
        self.assertEqual(grant_status, 200)

        # -----------------------------------------------------------------------------
        # 3) 결과 검증
        # -----------------------------------------------------------------------------
        access = UserSdwtProdAccess.objects.get(
            user=target,
            affiliation__user_sdwt_prod__iexact="group-a",
        )
        self.assertEqual(access.role, "member")

    def test_revoke_current_affiliation_is_blocked(self) -> None:
        """현재 소속에 대한 권한 회수는 거부되는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 대상 사용자/권한 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        target = User.objects.create_user(
            sabun="S50004",
            password="test-password",
            knox_id="knox-50004",
        )
        _set_current_affiliation(target, user_sdwt_prod="group-a")
        _grant_access(user=target, user_sdwt_prod="group-a", role="member")

        # -----------------------------------------------------------------------------
        # 2) 회수 요청
        # -----------------------------------------------------------------------------
        revoke_payload, revoke_status = grant_or_revoke_access(
            grantor=self.manager,
            target_group="group-a",
            target_user=target,
            action="revoke",
            role=None,
            reason="테스트 권한 변경",
        )

        # -----------------------------------------------------------------------------
        # 3) 결과 검증
        # -----------------------------------------------------------------------------
        self.assertEqual(revoke_status, 400)
        self.assertEqual(
            revoke_payload.get("error"),
            "Cannot revoke access for the user's current affiliation",
        )

    def test_last_manager_cannot_be_demoted_or_revoked(self) -> None:
        """소속의 마지막 manager는 강등하거나 회수할 수 없습니다."""

        demote_payload, demote_status = grant_or_revoke_access(
            grantor=self.manager,
            target_group="group-a",
            target_user=self.manager,
            action="grant",
            role="member",
            reason="테스트 권한 변경",
        )
        revoke_payload, revoke_status = grant_or_revoke_access(
            grantor=self.manager,
            target_group="group-a",
            target_user=self.manager,
            action="revoke",
            role=None,
            reason="테스트 권한 변경",
        )

        self.assertEqual(demote_status, 409)
        self.assertEqual(
            demote_payload.get("error"),
            "Cannot demote the last manager for this group",
        )
        self.assertEqual(revoke_status, 409)
        self.assertEqual(
            revoke_payload.get("error"),
            "Cannot remove the last manager for this group",
        )
        self.assertEqual(
            UserSdwtProdAccess.objects.get(
                user=self.manager,
                affiliation__user_sdwt_prod="group-a",
            ).role,
            UserSdwtProdAccess.Roles.MANAGER,
        )

    def test_affiliation_manager_can_grant_change_and_revoke_access_via_api(self) -> None:
        """소속 manager가 제품 API로 추가 접근 역할을 관리할 수 있습니다."""

        User = get_user_model()
        target = User.objects.create_user(
            sabun="S50010",
            password="test-password",
            knox_id="knox-50010",
        )
        _set_current_affiliation(target, user_sdwt_prod="group-b")
        self.client.force_login(self.manager)

        grant_response = self.client.post(
            reverse("account-affiliation-access"),
            data={
                "userId": target.id,
                "userSdwtProd": "group-a",
                "role": "viewer",
                "reason": "추가 소속 권한 부여 검증",
            },
            content_type="application/json",
        )
        self.assertEqual(grant_response.status_code, 200)
        self.assertEqual(grant_response.json()["role"], "viewer")

        change_response = self.client.post(
            reverse("account-affiliation-access"),
            data={
                "userId": target.id,
                "userSdwtProd": "group-a",
                "role": "member",
                "reason": "추가 소속 역할 변경 검증",
            },
            content_type="application/json",
        )
        self.assertEqual(change_response.status_code, 200)
        self.assertEqual(change_response.json()["role"], "member")
        members_response = self.client.get(
            reverse("account-affiliation-members"),
            {"userSdwtProd": "group-a"},
        )
        self.assertEqual(members_response.status_code, 200)
        self.assertTrue(members_response.json()["canManage"])
        self.assertEqual(members_response.json()["actorRole"], "manager")

        revoke_response = self.client.delete(
            reverse("account-affiliation-access"),
            data={
                "userId": target.id,
                "userSdwtProd": "group-a",
                "reason": "추가 소속 권한 회수 검증",
            },
            content_type="application/json",
        )
        self.assertEqual(revoke_response.status_code, 200)
        self.assertFalse(
            UserSdwtProdAccess.objects.filter(
                user=target,
                affiliation__user_sdwt_prod="group-a",
            ).exists()
        )
        role_audits = list(
            AccessAuditLog.objects.filter(
                actor=self.manager,
                target_user=target,
                affiliation__user_sdwt_prod="group-a",
                action__in=[
                    AccessAuditLog.Actions.AFFILIATION_ROLE_GRANT,
                    AccessAuditLog.Actions.AFFILIATION_ROLE_CHANGE,
                    AccessAuditLog.Actions.AFFILIATION_ROLE_REVOKE,
                ],
            ).order_by("id")
        )
        self.assertEqual(
            [audit.action for audit in role_audits],
            [
                AccessAuditLog.Actions.AFFILIATION_ROLE_GRANT,
                AccessAuditLog.Actions.AFFILIATION_ROLE_CHANGE,
                AccessAuditLog.Actions.AFFILIATION_ROLE_REVOKE,
            ],
        )
        self.assertEqual(role_audits[0].before, {})
        self.assertEqual(
            role_audits[0].after,
            {"role": "viewer", "grantedBy": self.manager.id},
        )
        self.assertEqual(role_audits[1].before["role"], "viewer")
        self.assertEqual(role_audits[1].after["role"], "member")
        self.assertEqual(role_audits[2].before["role"], "member")
        self.assertEqual(role_audits[2].after, {})

    def test_affiliation_role_change_rolls_back_when_audit_fails(self) -> None:
        """소속 역할 감사 저장 실패 시 역할 부여도 함께 롤백해야 합니다."""

        User = get_user_model()
        target = User.objects.create_user(
            sabun="S50013",
            password="test-password",
            knox_id="knox-50013",
        )
        _set_current_affiliation(target, user_sdwt_prod="group-b")

        with patch(
            "api.account.services.access.create_access_audit_log",
            side_effect=RuntimeError("audit failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "audit failed"):
                grant_or_revoke_access(
                    grantor=self.manager,
                    target_group="group-a",
                    target_user=target,
                    action="grant",
                    role="viewer",
                    reason="테스트 권한 변경",
                )

        self.assertFalse(
            UserSdwtProdAccess.objects.filter(
                user=target,
                affiliation__user_sdwt_prod="group-a",
            ).exists()
        )

    def test_affiliation_role_management_rechecks_manager_after_lock(self) -> None:
        """소속 잠금 대기 중 manager가 강등되면 최신 역할로 작업을 거절해야 합니다."""

        User = get_user_model()
        target = User.objects.create_user(
            sabun="S50014",
            password="test-password",
            knox_id="knox-50014",
        )
        _set_current_affiliation(target, user_sdwt_prod="group-b")
        original_lock = (
            account_selectors.get_affiliation_option_for_update_by_user_sdwt_prod
        )

        def lock_and_demote(*, user_sdwt_prod):
            affiliation = original_lock(user_sdwt_prod=user_sdwt_prod)
            UserSdwtProdAccess.objects.filter(
                user=self.manager,
                affiliation=affiliation,
            ).update(role=UserSdwtProdAccess.Roles.MEMBER)
            return affiliation

        with patch(
            "api.account.services.access.selectors."
            "get_affiliation_option_for_update_by_user_sdwt_prod",
            side_effect=lock_and_demote,
        ):
            payload, status_code = grant_or_revoke_access(
                grantor=self.manager,
                target_group="group-a",
                target_user=target,
                action="grant",
                role="viewer",
                reason="테스트 권한 변경",
            )

        self.assertEqual(status_code, 403)
        self.assertEqual(payload["error"], "forbidden")
        self.assertFalse(
            UserSdwtProdAccess.objects.filter(
                user=target,
                affiliation__user_sdwt_prod="group-a",
            ).exists()
        )

    def test_affiliation_access_admin_is_read_only(self) -> None:
        """Django Admin은 마지막 manager 보호를 우회해 소속 역할을 수정하지 못합니다."""

        from django.contrib.admin.sites import AdminSite

        from api.account.admin import UserSdwtProdAccessAdmin

        request = RequestFactory().get("/admin/")
        request.user = self.superuser
        access_admin = UserSdwtProdAccessAdmin(UserSdwtProdAccess, AdminSite())

        self.assertFalse(access_admin.has_add_permission(request))
        self.assertFalse(access_admin.has_change_permission(request))
        self.assertFalse(access_admin.has_delete_permission(request))

    def test_affiliation_member_cannot_manage_access_via_api(self) -> None:
        """일반 member는 다른 사용자의 소속 접근 역할을 관리할 수 없습니다."""

        User = get_user_model()
        target = User.objects.create_user(
            sabun="S50011",
            password="test-password",
            knox_id="knox-50011",
        )
        _set_current_affiliation(target, user_sdwt_prod="group-b")
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("account-affiliation-access"),
            data={
                "userId": target.id,
                "userSdwtProd": "group-a",
                "role": "viewer",
                "reason": "권한 없는 사용자 변경 거부 검증",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            UserSdwtProdAccess.objects.filter(
                user=target,
                affiliation__user_sdwt_prod="group-a",
            ).exists()
        )

    def test_inactive_affiliation_cannot_receive_access_role(self) -> None:
        """비활성 소속에는 신규 접근 역할을 부여할 수 없습니다."""

        affiliation = Affiliation.objects.get(user_sdwt_prod="group-a")
        affiliation.is_active = False
        affiliation.save(update_fields=["is_active"])
        User = get_user_model()
        target = User.objects.create_user(
            sabun="S50012",
            password="test-password",
            knox_id="knox-50012",
        )

        payload, status_code = grant_or_revoke_access(
            grantor=self.manager,
            target_group="group-a",
            target_user=target,
            action="grant",
            role="viewer",
            reason="테스트 권한 변경",
        )

        self.assertEqual(status_code, 400)
        self.assertEqual(payload["error"], "Invalid user_sdwt_prod")
        self.assertFalse(
            UserSdwtProdAccess.objects.filter(
                user=target,
                affiliation=affiliation,
            ).exists()
        )

    def test_account_affiliation_members_uses_account_domain(self) -> None:
        """소속 멤버 조회가 emails 정보 없이 account 소속/권한 기준으로 동작해야 합니다."""

        User = get_user_model()
        member = User.objects.create_user(
            sabun="S50008",
            password="test-password",
            knox_id="knox-50008",
            username="소속멤버",
        )
        _set_current_affiliation(member, user_sdwt_prod="group-a")

        viewer = User.objects.create_user(
            sabun="S50009",
            password="test-password",
            knox_id="knox-50009",
            username="권한멤버",
        )
        _grant_access(user=viewer, user_sdwt_prod="group-a", role="viewer")

        self.client.force_login(self.user)
        response = self.client.get(
            reverse("account-affiliation-members"),
            {"userSdwtProd": "group-a"},
        )

        self.assertEqual(response.status_code, 200)
        rows = response.json()["members"]
        user_ids = {row["userId"] for row in rows}
        self.assertIn(member.id, user_ids)
        self.assertIn(viewer.id, user_ids)
        rows_by_user_id = {row["userId"]: row for row in rows}
        self.assertEqual(rows_by_user_id[member.id]["role"], "member")
        self.assertEqual(rows_by_user_id[viewer.id]["role"], "viewer")
        self.assertFalse(response.json()["canManage"])
        self.assertNotIn("emailCount", rows[0])


class AffiliationSelectorTests(TestCase):
    """소속 셀렉터 로직을 검증합니다."""

    def test_list_affiliation_options_orders_rows(self) -> None:
        """소속 옵션이 정렬된 순서로 반환되는지 확인합니다."""
        affiliation_s3 = _affiliation(
            department="DeptB",
            line="L2",
            user_sdwt_prod="S3",
        )
        affiliation_s2 = _affiliation(
            department="DeptA",
            line="L2",
            user_sdwt_prod="S2",
        )
        affiliation_s1 = _affiliation(
            department="DeptA",
            line="L1",
            user_sdwt_prod="S1",
        )

        rows = list_affiliation_options()
        self.assertEqual(
            rows,
            [
                {
                    "id": affiliation_s1.id,
                    "department": "DeptA",
                    "line": "L1",
                    "user_sdwt_prod": "S1",
                },
                {
                    "id": affiliation_s2.id,
                    "department": "DeptA",
                    "line": "L2",
                    "user_sdwt_prod": "S2",
                },
                {
                    "id": affiliation_s3.id,
                    "department": "DeptB",
                    "line": "L2",
                    "user_sdwt_prod": "S3",
                },
            ],
        )

    def test_list_line_sdwt_pairs_returns_all_active_pairs_in_order(self) -> None:
        """활성 라인-소속 쌍을 외부 데이터 매칭 없이 정렬 반환하는지 확인합니다."""
        Affiliation.objects.bulk_create(
            [
                Affiliation(department="DeptA", line="L1", user_sdwt_prod="S1"),
                Affiliation(department="DeptB", line="L1", user_sdwt_prod="S2"),
                Affiliation(department="DeptA", line="L2", user_sdwt_prod="S0"),
            ],
            ignore_conflicts=True,
        )

        rows = list_line_sdwt_pairs()

        self.assertEqual(
            rows,
            [
                {"line_id": "L1", "user_sdwt_prod": "S1"},
                {"line_id": "L1", "user_sdwt_prod": "S2"},
                {"line_id": "L2", "user_sdwt_prod": "S0"},
            ],
        )

    def test_list_line_sdwt_pairs_excludes_inactive_and_blank_rows(self) -> None:
        """비활성 또는 빈 라인/소속 행을 선택지에서 제외하는지 확인합니다."""
        Affiliation.objects.bulk_create(
            [
                Affiliation(department="DeptA", line="L1", user_sdwt_prod="S1"),
                Affiliation(
                    department="DeptA",
                    line="L2",
                    user_sdwt_prod="S2",
                    is_active=False,
                ),
                Affiliation(department="DeptA", line="", user_sdwt_prod="S3"),
            ],
        )

        rows = list_line_sdwt_pairs()

        self.assertEqual(rows, [{"line_id": "L1", "user_sdwt_prod": "S1"}])

    def test_affiliation_write_locks_use_primary_key_order(self) -> None:
        """표시값 정렬과 무관하게 다중 소속 잠금은 id 오름차순을 사용해야 합니다."""

        first = _affiliation(
            department="Z Dept",
            line="Z Line",
            user_sdwt_prod="z-lock-group",
        )
        second = _affiliation(
            department="A Dept",
            line="A Line",
            user_sdwt_prod="a-lock-group",
        )

        with transaction.atomic():
            by_ids = list_active_affiliations_by_ids_for_update(
                affiliation_ids=[second.id, first.id],
            )
            by_values = list_active_affiliations_by_user_sdwt_prods_for_update(
                user_sdwt_prods=[
                    second.user_sdwt_prod,
                    first.user_sdwt_prod,
                ],
            )

        self.assertEqual([row.id for row in by_ids], [first.id, second.id])
        self.assertEqual([row.id for row in by_values], [first.id, second.id])


class AccessibleUserSdwtProdTests(TestCase):
    """사용자 접근 가능한 user_sdwt_prod 계산을 검증합니다."""

    def test_pending_change_not_included_when_no_current_affiliation(self) -> None:
        """현재 소속이 없고 승인 대기 상태라도 접근 목록은 비어 있어야 합니다."""
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S42000",
            password="test-password",
            knox_id="knox-42000",
        )

        UserSdwtProdChange.objects.create(
            user=user,
            department="Dept",
            line="Line",
            from_user_sdwt_prod=None,
            to_user_sdwt_prod="group-new",
            effective_from=timezone.now(),
            status=UserSdwtProdChange.Status.PENDING,
            applied=False,
            approved=False,
            created_by=user,
        )

        accessible = get_accessible_user_sdwt_prods_for_user(user)
        self.assertEqual(accessible, set())

    def test_pending_change_ignored_when_current_affiliation_exists(self) -> None:
        """현재 소속이 있으면 대기 변경이 제외되는지 확인합니다."""
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S42001",
            password="test-password",
            knox_id="knox-42001",
        )
        _set_current_affiliation(user, user_sdwt_prod="group-old")

        UserSdwtProdChange.objects.create(
            user=user,
            department="Dept",
            line="Line",
            from_user_sdwt_prod="group-old",
            to_user_sdwt_prod="group-new",
            effective_from=timezone.now(),
            status=UserSdwtProdChange.Status.PENDING,
            applied=False,
            approved=False,
            created_by=user,
        )

        accessible = get_accessible_user_sdwt_prods_for_user(user)
        self.assertIn("group-old", accessible)
        self.assertNotIn("group-new", accessible)


class AffiliationCapabilityTests(TestCase):
    """소속 역할별 공통 capability 판정을 검증합니다."""

    def test_viewer_member_manager_capabilities_are_separated(self) -> None:
        """viewer는 읽기, member는 일반 변경, manager는 삭제·관리를 수행합니다."""

        User = get_user_model()
        viewer = User.objects.create_user(sabun="S42100", password="test-password")
        member = User.objects.create_user(sabun="S42101", password="test-password")
        manager = User.objects.create_user(sabun="S42102", password="test-password")
        _set_current_affiliation(viewer, user_sdwt_prod="group-other")
        _set_current_affiliation(member, user_sdwt_prod="group-a")
        _set_current_affiliation(manager, user_sdwt_prod="group-a")
        _grant_access(user=viewer, user_sdwt_prod="group-a", role="viewer")
        _grant_access(user=manager, user_sdwt_prod="group-a", role="manager")

        self.assertTrue(
            has_affiliation_capability(
                user=viewer,
                user_sdwt_prod="group-a",
                capability="read",
            )
        )
        self.assertFalse(
            has_affiliation_capability(
                user=viewer,
                user_sdwt_prod="group-a",
                capability="write",
            )
        )
        self.assertTrue(
            has_affiliation_capability(
                user=member,
                user_sdwt_prod="group-a",
                capability="write",
            )
        )
        self.assertFalse(
            has_affiliation_capability(
                user=member,
                user_sdwt_prod="group-a",
                capability="delete",
            )
        )
        for capability in ("read", "write", "delete", "manage_access", "approve"):
            with self.subTest(capability=capability):
                self.assertTrue(
                    has_affiliation_capability(
                        user=manager,
                        user_sdwt_prod="group-a",
                        capability=capability,
                    )
                )

    def test_inactive_affiliation_is_inert_until_audited_reactivation(self) -> None:
        """비활성 소속은 현재 소속과 명시 역할을 모두 중지하고 재활성화는 감사해야 합니다."""

        User = get_user_model()
        actor = User.objects.create_superuser(
            sabun="S-AFFILIATION-STATE-ACTOR",
            password="test-password",
        )
        user = User.objects.create_user(
            sabun="S-AFFILIATION-STATE-USER",
            password="test-password",
        )
        current = _set_current_affiliation(
            user,
            user_sdwt_prod="state-controlled-group",
        )
        _grant_access(
            user=user,
            user_sdwt_prod=current.affiliation.user_sdwt_prod,
            role=UserSdwtProdAccess.Roles.MANAGER,
        )

        payload, status_code = set_affiliation_active(
            actor=actor,
            affiliation_id=current.affiliation_id,
            is_active=False,
            reason="조직 운영 중지",
        )

        self.assertEqual(status_code, 200, payload)
        self.assertIsNone(get_current_user_sdwt_prod(user=user))
        self.assertEqual(get_accessible_user_sdwt_prods_for_user(user), set())
        self.assertFalse(
            has_affiliation_capability(
                user=user,
                user_sdwt_prod="state-controlled-group",
                capability="manage_access",
            )
        )
        self.assertFalse(
            has_affiliation_capability(
                user=actor,
                user_sdwt_prod="state-controlled-group",
                capability="manage_access",
            )
        )
        deactivate_audit = AccessAuditLog.objects.get(
            affiliation_id=current.affiliation_id,
            action=AccessAuditLog.Actions.AFFILIATION_DEACTIVATE,
        )
        self.assertTrue(deactivate_audit.before["isActive"])
        self.assertFalse(deactivate_audit.after["isActive"])
        self.assertEqual(deactivate_audit.reason, "조직 운영 중지")

        payload, status_code = set_affiliation_active(
            actor=actor,
            affiliation_id=current.affiliation_id,
            is_active=True,
            reason="조직 운영 재개",
        )

        self.assertEqual(status_code, 200, payload)
        self.assertEqual(
            get_current_user_sdwt_prod(user=user),
            "state-controlled-group",
        )
        self.assertTrue(
            has_affiliation_capability(
                user=user,
                user_sdwt_prod="state-controlled-group",
                capability="manage_access",
            )
        )
        self.assertTrue(
            AccessAuditLog.objects.filter(
                affiliation_id=current.affiliation_id,
                action=AccessAuditLog.Actions.AFFILIATION_ACTIVATE,
                reason="조직 운영 재개",
            ).exists()
        )

    def test_batch_capability_matches_single_role_rules_with_constant_queries(self) -> None:
        """여러 소속 capability는 소속 수와 무관한 쿼리로 기존 역할 규칙을 유지해야 합니다."""

        User = get_user_model()
        user = User.objects.create_user(
            sabun="S-AFFILIATION-BATCH",
            password="test-password",
        )
        current = _set_current_affiliation(
            user,
            user_sdwt_prod="batch-current",
        ).affiliation
        member = _affiliation(user_sdwt_prod="batch-member")
        viewer = _affiliation(user_sdwt_prod="batch-viewer")
        _grant_access(
            user=user,
            user_sdwt_prod=member.user_sdwt_prod,
            role=UserSdwtProdAccess.Roles.MEMBER,
        )
        _grant_access(
            user=user,
            user_sdwt_prod=viewer.user_sdwt_prod,
            role=UserSdwtProdAccess.Roles.VIEWER,
        )
        user = User.objects.select_related(
            "current_affiliation__affiliation"
        ).get(pk=user.pk)
        affiliation_ids = [current.id, member.id, viewer.id]

        with self.assertNumQueries(2):
            can_read = has_affiliation_capability_for_ids(
                user=user,
                affiliation_ids=affiliation_ids,
                capability="read",
            )
        with self.assertNumQueries(2):
            can_write = has_affiliation_capability_for_ids(
                user=user,
                affiliation_ids=affiliation_ids,
                capability="write",
            )

        self.assertTrue(can_read)
        self.assertFalse(can_write)

    def test_bulk_affiliation_state_change_rolls_back_on_audit_failure(self) -> None:
        """일괄 활성 상태 변경은 감사 로그 생성 실패 시 전부 롤백해야 합니다."""

        actor = get_user_model().objects.create_superuser(
            sabun="S-AFFILIATION-BULK-ROLLBACK",
            password="test-password",
        )
        first = _affiliation(user_sdwt_prod="bulk-rollback-first")
        second = _affiliation(user_sdwt_prod="bulk-rollback-second")

        with patch(
            "api.account.services.affiliations.create_access_audit_log",
            side_effect=[None, RuntimeError("audit failed")],
        ):
            with self.assertRaisesRegex(RuntimeError, "audit failed"):
                set_affiliations_active(
                    actor=actor,
                    affiliation_ids=[second.id, first.id],
                    is_active=False,
                    reason="원자성 검증",
                )

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertTrue(first.is_active)
        self.assertTrue(second.is_active)

    def test_affiliation_create_and_sync_changes_are_audited(self) -> None:
        """Admin 생성과 system sync의 실제 생성·변경만 lifecycle 감사로 남겨야 합니다."""

        actor = get_user_model().objects.create_superuser(
            sabun="S-AFFILIATION-CREATE-ACTOR",
            password="test-password",
        )
        admin_option = create_affiliation(
            actor=actor,
            affiliation=Affiliation(
                department="Admin Dept",
                line="Admin Line",
                user_sdwt_prod="admin-created-group",
            ),
            reason="신규 조직 등록",
        )
        created_audit = AccessAuditLog.objects.get(
            affiliation=admin_option,
            action=AccessAuditLog.Actions.AFFILIATION_CREATE,
        )
        self.assertEqual(created_audit.actor_id, actor.id)
        self.assertEqual(created_audit.after["source"], "django_admin")
        self.assertEqual(created_audit.reason, "신규 조직 등록")

        synced = ensure_affiliation_option(
            department="Sync Dept",
            line="Sync Line",
            user_sdwt_prod="synced-group",
        )
        ensure_affiliation_option(
            department="Sync Dept",
            line="Sync Line",
            user_sdwt_prod="synced-group",
        )
        ensure_affiliation_option(
            department="Updated Sync Dept",
            line="Sync Line",
            user_sdwt_prod="synced-group",
        )

        sync_audits = AccessAuditLog.objects.filter(
            affiliation=synced,
            action__in=[
                AccessAuditLog.Actions.AFFILIATION_CREATE,
                AccessAuditLog.Actions.AFFILIATION_UPDATE,
            ],
        ).order_by("id")
        self.assertEqual(sync_audits.count(), 2)
        self.assertIsNone(sync_audits[0].actor_id)
        self.assertEqual(sync_audits[0].after["source"], "system_sync")
        self.assertEqual(sync_audits[1].before["department"], "Sync Dept")
        self.assertEqual(
            sync_audits[1].after["department"],
            "Updated Sync Dept",
        )

        with patch(
            "api.account.services.affiliations.create_access_audit_log",
            side_effect=RuntimeError("audit failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "audit failed"):
                create_affiliation(
                    actor=actor,
                    affiliation=Affiliation(
                        department="Rollback Dept",
                        line="Rollback Line",
                        user_sdwt_prod="audit-rollback-created",
                    ),
                    reason="생성 롤백 검증",
                )
        self.assertFalse(
            Affiliation.objects.filter(
                user_sdwt_prod="audit-rollback-created",
            ).exists()
        )


class AffiliationChangeApprovalTests(TestCase):
    """소속 변경 승인 로직을 검증합니다."""

    def test_manager_can_approve_and_preserves_effective_from(self) -> None:
        """대상 소속 manager 승인 시 적용 시각을 유지하는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자/승인자 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        requester = User.objects.create_user(
            sabun="S10000",
            password="test-password",
            knox_id="knox-10000",
        )
        _set_current_affiliation(requester, user_sdwt_prod="group-old")
        _grant_access(user=requester, user_sdwt_prod="group-old", role="member")

        manager = User.objects.create_user(
            sabun="S20000",
            password="test-password",
            knox_id="knox-20000",
        )
        _set_current_affiliation(manager, user_sdwt_prod="group-new")
        _grant_access(user=manager, user_sdwt_prod="group-new", role="manager")

        # -----------------------------------------------------------------------------
        # 2) 변경 요청 생성
        # -----------------------------------------------------------------------------
        past = timezone.now() - timedelta(days=7)
        change = UserSdwtProdChange.objects.create(
            user=requester,
            department="Dept",
            line="Line",
            from_user_sdwt_prod="group-old",
            to_user_sdwt_prod="group-new",
            effective_from=past,
            status=UserSdwtProdChange.Status.PENDING,
            applied=False,
            approved=False,
            created_by=requester,
        )

        # -----------------------------------------------------------------------------
        # 3) 승인 처리 실행
        # -----------------------------------------------------------------------------
        _payload, status_code = approve_affiliation_change(
            approver=manager,
            change_id=change.id,
        )

        # -----------------------------------------------------------------------------
        # 4) 승인 결과 검증
        # -----------------------------------------------------------------------------
        self.assertEqual(status_code, 200)
        change.refresh_from_db()
        requester.refresh_from_db()

        self.assertEqual(get_current_user_sdwt_prod(user=requester), "group-new")
        self.assertTrue(change.approved)
        self.assertTrue(change.applied)
        self.assertEqual(change.status, UserSdwtProdChange.Status.APPROVED)
        self.assertEqual(change.approved_by_id, manager.id)
        self.assertIsNotNone(change.approved_at)
        self.assertEqual(change.effective_from, past)
        role_audits = {
            audit.affiliation.user_sdwt_prod: audit
            for audit in AccessAuditLog.objects.filter(
                target_user=requester,
                action__in=(
                    AccessAuditLog.Actions.AFFILIATION_ROLE_GRANT,
                    AccessAuditLog.Actions.AFFILIATION_ROLE_CHANGE,
                ),
            ).select_related("affiliation")
        }
        self.assertEqual(set(role_audits), {"group-old", "group-new"})
        self.assertEqual(
            role_audits["group-new"].action,
            AccessAuditLog.Actions.AFFILIATION_ROLE_GRANT,
        )
        self.assertEqual(role_audits["group-new"].actor_id, manager.id)
        self.assertEqual(role_audits["group-new"].before, {})
        self.assertEqual(role_audits["group-new"].after["role"], "member")
        self.assertEqual(
            role_audits["group-old"].action,
            AccessAuditLog.Actions.AFFILIATION_ROLE_CHANGE,
        )
        self.assertEqual(role_audits["group-old"].before["role"], "member")
        self.assertEqual(role_audits["group-old"].after["role"], "viewer")

    def test_approval_rechecks_manager_after_affiliation_lock(self) -> None:
        """소속 잠금 대기 중 manager가 강등되면 승인 권한을 다시 확인해야 합니다."""

        User = get_user_model()
        requester = User.objects.create_user(
            sabun="S10006",
            password="test-password",
            knox_id="knox-10006",
        )
        _set_current_affiliation(requester, user_sdwt_prod="group-old")
        manager = User.objects.create_user(
            sabun="S20006",
            password="test-password",
            knox_id="knox-20006",
        )
        _set_current_affiliation(manager, user_sdwt_prod="group-new")
        manager_access = _grant_access(
            user=manager,
            user_sdwt_prod="group-new",
            role=UserSdwtProdAccess.Roles.MANAGER,
        )
        change = UserSdwtProdChange.objects.create(
            user=requester,
            from_user_sdwt_prod="group-old",
            to_user_sdwt_prod="group-new",
            effective_from=timezone.now(),
            status=UserSdwtProdChange.Status.PENDING,
            created_by=requester,
        )
        original_lock = (
            account_selectors.get_affiliation_option_for_update_by_user_sdwt_prod
        )

        def lock_and_demote(*, user_sdwt_prod):
            affiliation = original_lock(user_sdwt_prod=user_sdwt_prod)
            UserSdwtProdAccess.objects.filter(id=manager_access.id).update(
                role=UserSdwtProdAccess.Roles.MEMBER,
            )
            return affiliation

        with patch(
            "api.account.services.affiliation_requests.selectors."
            "get_affiliation_option_for_update_by_user_sdwt_prod",
            side_effect=lock_and_demote,
        ):
            payload, status_code = approve_affiliation_change(
                approver=manager,
                change_id=change.id,
            )

        self.assertEqual(status_code, 403)
        self.assertEqual(payload["error"], "forbidden")
        change.refresh_from_db()
        self.assertEqual(change.status, UserSdwtProdChange.Status.PENDING)
        self.assertEqual(
            get_current_user_sdwt_prod(user=requester),
            "group-old",
        )

    def test_approval_rolls_back_when_automatic_role_audit_fails(self) -> None:
        """자동 역할 감사 저장에 실패하면 소속과 역할 변경을 모두 되돌려야 합니다."""

        User = get_user_model()
        requester = User.objects.create_user(
            sabun="S10007",
            password="test-password",
            knox_id="knox-10007",
        )
        _set_current_affiliation(requester, user_sdwt_prod="group-old")
        _grant_access(user=requester, user_sdwt_prod="group-old", role="member")
        manager = User.objects.create_user(
            sabun="S20007",
            password="test-password",
            knox_id="knox-20007",
        )
        _set_current_affiliation(manager, user_sdwt_prod="group-new")
        _grant_access(user=manager, user_sdwt_prod="group-new", role="manager")
        change = UserSdwtProdChange.objects.create(
            user=requester,
            from_user_sdwt_prod="group-old",
            to_user_sdwt_prod="group-new",
            effective_from=timezone.now(),
            status=UserSdwtProdChange.Status.PENDING,
            created_by=requester,
        )

        with patch(
            "api.account.services.access.create_access_audit_log",
            side_effect=RuntimeError("audit failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "audit failed"):
                approve_affiliation_change(
                    approver=manager,
                    change_id=change.id,
                )

        change.refresh_from_db()
        self.assertEqual(change.status, UserSdwtProdChange.Status.PENDING)
        self.assertEqual(get_current_user_sdwt_prod(user=requester), "group-old")
        self.assertEqual(
            UserSdwtProdAccess.objects.get(
                user=requester,
                affiliation__user_sdwt_prod="group-old",
            ).role,
            UserSdwtProdAccess.Roles.MEMBER,
        )
        self.assertFalse(
            UserSdwtProdAccess.objects.filter(
                user=requester,
                affiliation__user_sdwt_prod="group-new",
            ).exists()
        )

    def test_current_affiliation_member_without_access_row_cannot_approve(self) -> None:
        """현재 소속 member라도 명시적인 manager 역할 없이는 승인할 수 없습니다."""
        User = get_user_model()
        requester = User.objects.create_user(
            sabun="S10002",
            password="test-password",
            knox_id="knox-10002",
        )
        _set_current_affiliation(requester, user_sdwt_prod="group-old")

        member = User.objects.create_user(
            sabun="S20002",
            password="test-password",
            knox_id="knox-20002",
        )
        _set_current_affiliation(member, user_sdwt_prod="group-new")
        self.assertFalse(
            UserSdwtProdAccess.objects.filter(
                user=member,
                affiliation__user_sdwt_prod__iexact="group-new",
            ).exists()
        )

        change = UserSdwtProdChange.objects.create(
            user=requester,
            department="Dept",
            line="Line",
            from_user_sdwt_prod="group-old",
            to_user_sdwt_prod="group-new",
            effective_from=timezone.now(),
            status=UserSdwtProdChange.Status.PENDING,
            applied=False,
            approved=False,
            created_by=requester,
        )

        _payload, status_code = approve_affiliation_change(
            approver=member,
            change_id=change.id,
        )

        self.assertEqual(status_code, 403)
        change.refresh_from_db()
        self.assertEqual(change.status, UserSdwtProdChange.Status.PENDING)
        self.assertIsNone(change.approved_by_id)

    def test_manager_cannot_decide_own_affiliation_request(self) -> None:
        """대상 소속 manager여도 자신의 변경 요청은 승인·거절할 수 없습니다."""

        User = get_user_model()
        requester = User.objects.create_user(
            sabun="S10004",
            password="test-password",
            knox_id="knox-10004",
        )
        _set_current_affiliation(requester, user_sdwt_prod="group-old")
        _grant_access(user=requester, user_sdwt_prod="group-new", role="manager")
        change = UserSdwtProdChange.objects.create(
            user=requester,
            department="Dept",
            line="Line",
            from_user_sdwt_prod="group-old",
            to_user_sdwt_prod="group-new",
            effective_from=timezone.now(),
            status=UserSdwtProdChange.Status.PENDING,
            applied=False,
            approved=False,
            created_by=requester,
        )

        _approve_payload, approve_status = approve_affiliation_change(
            approver=requester,
            change_id=change.id,
        )
        _reject_payload, reject_status = reject_affiliation_change(
            approver=requester,
            change_id=change.id,
            rejection_reason="self",
        )

        self.assertEqual(approve_status, 403)
        self.assertEqual(reject_status, 403)
        change.refresh_from_db()
        self.assertEqual(change.status, UserSdwtProdChange.Status.PENDING)

    def test_decided_affiliation_request_returns_conflict(self) -> None:
        """이미 처리된 요청은 잠금 후 409 Conflict로 거절해야 합니다."""

        User = get_user_model()
        requester = User.objects.create_user(
            sabun="S10005",
            password="test-password",
            knox_id="knox-10005",
        )
        _set_current_affiliation(requester, user_sdwt_prod="group-old")
        manager = User.objects.create_user(
            sabun="S20005",
            password="test-password",
            knox_id="knox-20005",
        )
        _set_current_affiliation(manager, user_sdwt_prod="group-new")
        _grant_access(user=manager, user_sdwt_prod="group-new", role="manager")
        change = UserSdwtProdChange.objects.create(
            user=requester,
            department="Dept",
            line="Line",
            from_user_sdwt_prod="group-old",
            to_user_sdwt_prod="group-new",
            effective_from=timezone.now(),
            status=UserSdwtProdChange.Status.REJECTED,
            applied=False,
            approved=False,
            approved_by=manager,
            approved_at=timezone.now(),
            created_by=requester,
        )

        _payload, status_code = approve_affiliation_change(
            approver=manager,
            change_id=change.id,
        )

        self.assertEqual(status_code, 409)

    def test_non_member_cannot_approve(self) -> None:
        """대상 소속 멤버가 아니면 승인할 수 없음을 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 요청자/비관리자 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        requester = User.objects.create_user(
            sabun="S10001",
            password="test-password",
            knox_id="knox-10001",
        )
        _set_current_affiliation(requester, user_sdwt_prod="group-old")

        other = User.objects.create_user(
            sabun="S30000",
            password="test-password",
            knox_id="knox-30000",
        )
        _set_current_affiliation(other, user_sdwt_prod="group-other")

        # -----------------------------------------------------------------------------
        # 2) 변경 요청 생성
        # -----------------------------------------------------------------------------
        change = UserSdwtProdChange.objects.create(
            user=requester,
            department="Dept",
            line="Line",
            from_user_sdwt_prod="group-old",
            to_user_sdwt_prod="group-new",
            effective_from=timezone.now() - timedelta(days=1),
            status=UserSdwtProdChange.Status.PENDING,
            applied=False,
            approved=False,
            created_by=requester,
        )

        # -----------------------------------------------------------------------------
        # 3) 승인 시도 및 결과 검증
        # -----------------------------------------------------------------------------
        _payload, status_code = approve_affiliation_change(approver=other, change_id=change.id)
        self.assertEqual(status_code, 403)
        requester.refresh_from_db()
        self.assertEqual(get_current_user_sdwt_prod(user=requester), "group-old")

    def test_other_affiliation_viewer_cannot_approve(self) -> None:
        """다른 소속의 viewer 권한은 소속 변경 승인 권한으로 승격되지 않아야 합니다."""
        User = get_user_model()
        requester = User.objects.create_user(
            sabun="S10003",
            password="test-password",
            knox_id="knox-10003",
        )
        _set_current_affiliation(requester, user_sdwt_prod="group-old")

        viewer = User.objects.create_user(
            sabun="S30003",
            password="test-password",
            knox_id="knox-30003",
        )
        _set_current_affiliation(viewer, user_sdwt_prod="group-other")
        _grant_access(user=viewer, user_sdwt_prod="group-new", role="viewer")

        change = UserSdwtProdChange.objects.create(
            user=requester,
            department="Dept",
            line="Line",
            from_user_sdwt_prod="group-old",
            to_user_sdwt_prod="group-new",
            effective_from=timezone.now(),
            status=UserSdwtProdChange.Status.PENDING,
            applied=False,
            approved=False,
            created_by=requester,
        )

        _payload, status_code = approve_affiliation_change(
            approver=viewer,
            change_id=change.id,
        )

        self.assertEqual(status_code, 403)
        change.refresh_from_db()
        self.assertEqual(change.status, UserSdwtProdChange.Status.PENDING)


class AffiliationChangeSelectorTests(TestCase):
    """소속 변경 셀렉터 동작을 검증합니다."""

    def test_resolve_user_affiliation_ignores_unapproved_change(self) -> None:
        """미승인 변경은 현재 소속 계산에 반영되지 않아야 합니다."""
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S40000",
            password="test-password",
            knox_id="knox-40000",
        )
        _set_current_affiliation(user, user_sdwt_prod="group-a")

        UserSdwtProdChange.objects.create(
            user=user,
            to_user_sdwt_prod="group-b",
            effective_from=timezone.now() - timedelta(days=1),
            status=UserSdwtProdChange.Status.PENDING,
            applied=False,
            approved=False,
        )

        affiliation = resolve_user_affiliation(user, timezone.now())
        self.assertEqual(affiliation["user_sdwt_prod"], "group-a")

    def test_get_next_user_sdwt_prod_change_ignores_unapproved_change(self) -> None:
        """다음 변경 조회에서 미승인 변경은 제외되어야 합니다."""
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S40001",
            password="test-password",
            knox_id="knox-40001",
        )
        _set_current_affiliation(user, user_sdwt_prod="group-a")

        now = timezone.now()
        UserSdwtProdChange.objects.create(
            user=user,
            to_user_sdwt_prod="group-b",
            effective_from=now + timedelta(days=1),
            status=UserSdwtProdChange.Status.PENDING,
            applied=False,
            approved=False,
        )

        approved_change = UserSdwtProdChange.objects.create(
            user=user,
            to_user_sdwt_prod="group-c",
            effective_from=now + timedelta(days=2),
            status=UserSdwtProdChange.Status.APPROVED,
            applied=True,
            approved=True,
            approved_at=now,
        )

        next_change = get_next_user_sdwt_prod_change(user=user, effective_from=now)
        self.assertIsNotNone(next_change)
        self.assertEqual(next_change.id, approved_change.id)


class AffiliationChangeRequestListTests(TestCase):
    """소속 변경 요청 목록 조회를 검증합니다."""

    def test_manager_only_sees_manageable_groups(self) -> None:
        """관리자는 관리 가능한 그룹만 조회해야 합니다."""
        # -----------------------------------------------------------------------------
        # 1) 관리자/요청자 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        manager = User.objects.create_user(
            sabun="S90000",
            password="test-password",
            knox_id="knox-90000",
        )
        _grant_access(user=manager, user_sdwt_prod="group-a", role="manager")

        requester_a = User.objects.create_user(
            sabun="S90001",
            password="test-password",
            knox_id="knox-90001",
        )
        requester_b = User.objects.create_user(
            sabun="S90002",
            password="test-password",
            knox_id="knox-90002",
        )

        # -----------------------------------------------------------------------------
        # 2) 변경 요청 생성
        # -----------------------------------------------------------------------------
        change_a = UserSdwtProdChange.objects.create(
            user=requester_a,
            to_user_sdwt_prod="group-a",
            effective_from=timezone.now(),
            status=UserSdwtProdChange.Status.PENDING,
            applied=False,
            approved=False,
            created_by=requester_a,
        )
        UserSdwtProdChange.objects.create(
            user=requester_b,
            to_user_sdwt_prod="group-b",
            effective_from=timezone.now(),
            status=UserSdwtProdChange.Status.PENDING,
            applied=False,
            approved=False,
            created_by=requester_b,
        )

        # -----------------------------------------------------------------------------
        # 3) 서비스 호출
        # -----------------------------------------------------------------------------
        payload, status_code = get_affiliation_change_requests(
            user=manager,
            status="pending",
            search=None,
            user_sdwt_prod=None,
            page=1,
            page_size=20,
        )

        # -----------------------------------------------------------------------------
        # 4) 결과 검증
        # -----------------------------------------------------------------------------
        self.assertEqual(status_code, 200)
        ids = [entry["id"] for entry in payload["results"]]
        self.assertIn(change_a.id, ids)
        self.assertEqual(len(ids), 1)
        self.assertEqual(payload["results"][0]["role"], "manager")

    def test_manager_filters_manageable_groups_case_insensitively(self) -> None:
        """관리 그룹 필터가 user_sdwt_prod 대소문자를 구분하지 않는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 관리자/요청자 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        manager = User.objects.create_user(
            sabun="S90010",
            password="test-password",
            knox_id="knox-90010",
        )
        _grant_access(user=manager, user_sdwt_prod="GROUP-A", role="manager")

        requester = User.objects.create_user(
            sabun="S90011",
            password="test-password",
            knox_id="knox-90011",
        )

        # -----------------------------------------------------------------------------
        # 2) 변경 요청 생성
        # -----------------------------------------------------------------------------
        change = UserSdwtProdChange.objects.create(
            user=requester,
            to_user_sdwt_prod="group-a",
            effective_from=timezone.now(),
            status=UserSdwtProdChange.Status.PENDING,
            applied=False,
            approved=False,
            created_by=requester,
        )

        # -----------------------------------------------------------------------------
        # 3) 서비스 호출 및 결과 검증
        # -----------------------------------------------------------------------------
        payload, status_code = get_affiliation_change_requests(
            user=manager,
            status="pending",
            search=None,
            user_sdwt_prod="group-a",
            page=1,
            page_size=20,
        )

        self.assertEqual(status_code, 200)
        self.assertEqual([entry["id"] for entry in payload["results"]], [change.id])

    def test_search_filters_by_sabun(self) -> None:
        """검색 조건이 사번 필터에 적용되는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 관리자/요청자 및 권한 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        manager = User.objects.create_user(
            sabun="S91000",
            password="test-password",
            knox_id="knox-91000",
        )
        _grant_access(user=manager, user_sdwt_prod="group-c", role="manager")

        requester = User.objects.create_user(
            sabun="S91001",
            password="test-password",
            knox_id="knox-91001",
        )

        # -----------------------------------------------------------------------------
        # 2) 변경 요청 생성
        # -----------------------------------------------------------------------------
        change = UserSdwtProdChange.objects.create(
            user=requester,
            to_user_sdwt_prod="group-c",
            effective_from=timezone.now(),
            status=UserSdwtProdChange.Status.PENDING,
            applied=False,
            approved=False,
            created_by=requester,
        )

        # -----------------------------------------------------------------------------
        # 3) 서비스 호출
        # -----------------------------------------------------------------------------
        payload, status_code = get_affiliation_change_requests(
            user=manager,
            status="pending",
            search="S91001",
            user_sdwt_prod=None,
            page=1,
            page_size=20,
        )

        # -----------------------------------------------------------------------------
        # 4) 결과 검증
        # -----------------------------------------------------------------------------
        self.assertEqual(status_code, 200)
        self.assertEqual(payload["results"][0]["id"], change.id)
        self.assertEqual(payload["results"][0]["user"]["sabun"], "S91001")
        self.assertEqual(payload["results"][0]["role"], "manager")

    def test_non_manager_is_forbidden(self) -> None:
        """비관리자는 요청 목록 조회가 거부되어야 합니다."""
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S92000",
            password="test-password",
            knox_id="knox-92000",
        )

        payload, status_code = get_affiliation_change_requests(
            user=user,
            status="pending",
            search=None,
            user_sdwt_prod=None,
            page=1,
            page_size=20,
        )

        self.assertEqual(status_code, 403)
        self.assertEqual(payload["error"], "forbidden")

    def test_non_manager_can_view_own_group_requests(self) -> None:
        """비관리자는 자신의 그룹 요청만 조회 가능해야 합니다."""
        # -----------------------------------------------------------------------------
        # 1) 요청자 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        requester = User.objects.create_user(
            sabun="S93000",
            password="test-password",
            knox_id="knox-93000",
        )
        _set_current_affiliation(requester, user_sdwt_prod="group-own")
        _grant_access(user=requester, user_sdwt_prod="group-own", role="member")

        # -----------------------------------------------------------------------------
        # 2) 변경 요청 생성
        # -----------------------------------------------------------------------------
        change = UserSdwtProdChange.objects.create(
            user=requester,
            to_user_sdwt_prod="group-own",
            effective_from=timezone.now(),
            status=UserSdwtProdChange.Status.PENDING,
            applied=False,
            approved=False,
            created_by=requester,
        )

        # -----------------------------------------------------------------------------
        # 3) 서비스 호출
        # -----------------------------------------------------------------------------
        payload, status_code = get_affiliation_change_requests(
            user=requester,
            status="pending",
            search=None,
            user_sdwt_prod="group-own",
            page=1,
            page_size=20,
        )

        # -----------------------------------------------------------------------------
        # 4) 결과 검증
        # -----------------------------------------------------------------------------
        self.assertEqual(status_code, 200)
        self.assertEqual(payload["results"][0]["id"], change.id)
        self.assertEqual(payload["results"][0]["role"], "member")

    def test_current_affiliation_without_access_row_is_returned_as_member(self) -> None:
        """현재 소속 사용자의 승인 요청 역할은 명시적 권한 행 없이도 member여야 합니다."""
        User = get_user_model()
        member = User.objects.create_user(
            sabun="S93001",
            password="test-password",
            knox_id="knox-93001",
        )
        _set_current_affiliation(member, user_sdwt_prod="group-own")
        self.assertFalse(
            UserSdwtProdAccess.objects.filter(
                user=member,
                affiliation__user_sdwt_prod__iexact="group-own",
            ).exists()
        )

        change = UserSdwtProdChange.objects.create(
            user=member,
            to_user_sdwt_prod="group-own",
            effective_from=timezone.now(),
            status=UserSdwtProdChange.Status.PENDING,
            applied=False,
            approved=False,
            created_by=member,
        )

        payload, status_code = get_affiliation_change_requests(
            user=member,
            status="pending",
            search=None,
            user_sdwt_prod="group-own",
            page=1,
            page_size=20,
        )

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["results"][0]["id"], change.id)
        self.assertEqual(payload["results"][0]["role"], "member")


class AffiliationChangeRequestEffectiveFromTests(TestCase):
    """소속 변경 요청 서비스 로직을 검증합니다."""

    def test_request_affiliation_change_respects_effective_from_for_all(self) -> None:
        """요청 시각이 관리자/일반 사용자 모두에 적용되는지 확인합니다."""
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S50000",
            password="test-password",
            knox_id="knox-50000",
        )
        _set_current_affiliation(user, user_sdwt_prod="group-old")
        approver = User.objects.create_user(
            sabun="S50010",
            password="test-password",
            knox_id="knox-50010",
        )
        _set_current_affiliation(approver, user_sdwt_prod="group-new")
        _grant_access(user=approver, user_sdwt_prod="group-new", role="member")

        option = _affiliation(department="Dept", line="Line", user_sdwt_prod="group-new")
        requested_effective_from = timezone.now() - timedelta(days=30)

        payload, status_code = request_affiliation_change(
            user=user,
            option=option,
            to_user_sdwt_prod="group-new",
            effective_from=requested_effective_from,
            timezone_name="Asia/Seoul",
        )

        self.assertEqual(status_code, 202)
        change = UserSdwtProdChange.objects.get(id=payload["changeId"])
        self.assertEqual(change.effective_from, requested_effective_from)
        self.assertEqual(change.status, UserSdwtProdChange.Status.PENDING)


class AccountOverviewTests(TestCase):
    """계정 개요 응답을 검증합니다."""

    def test_account_overview_includes_profile_history_and_groups(self) -> None:
        """프로필/소속 이력/관리 그룹 정보 포함을 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자/프로필/권한 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S90000",
            password="test-password",
            knox_id="knox-90000",
        )
        user.username = "Tester"
        user.knox_id = "KNOX-90000"
        _set_current_affiliation(user, user_sdwt_prod="group-a")
        user.save(update_fields=["username", "knox_id"])

        _grant_access(user=user, user_sdwt_prod="group-b", role="manager")

        # -----------------------------------------------------------------------------
        # 2) 변경 이력 준비
        # -----------------------------------------------------------------------------
        change = UserSdwtProdChange.objects.create(
            user=user,
            department="Dept",
            line="Line",
            from_user_sdwt_prod="group-a",
            to_user_sdwt_prod="group-b",
            effective_from=timezone.now(),
            status=UserSdwtProdChange.Status.APPROVED,
            applied=True,
            approved=True,
            created_by=user,
            approved_by=user,
            approved_at=timezone.now(),
        )

        # -----------------------------------------------------------------------------
        # 3) 서비스 호출 및 결과 검증
        # -----------------------------------------------------------------------------
        payload = get_account_overview(user=user, timezone_name="Asia/Seoul")

        self.assertNotIn("operatorRole", payload["user"])
        self.assertNotIn("role", payload["user"])
        self.assertTrue(payload["affiliationHistory"])
        self.assertEqual(payload["affiliationHistory"][0]["id"], change.id)
        self.assertIn("manageableGroups", payload)
        self.assertNotIn("mailboxAccess", payload)

    def test_account_overview_collapses_accessible_groups_case_insensitively(self) -> None:
        """개요 응답의 접근 가능 그룹이 대소문자 비구분으로 중복 제거되는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자/접근 권한 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S90010",
            password="test-password",
            knox_id="knox-90010",
        )
        _set_current_affiliation(user, user_sdwt_prod="GROUP-A")
        _grant_access(user=user, user_sdwt_prod="group-a", role="member")
        _grant_access(user=user, user_sdwt_prod="group-b", role="manager")

        # -----------------------------------------------------------------------------
        # 3) 결과 검증
        # -----------------------------------------------------------------------------
        payload = get_account_overview(user=user, timezone_name="Asia/Seoul")

        accessible_rows = payload["affiliation"]["accessibleUserSdwtProds"]
        normalized_groups = {row["userSdwtProd"].casefold() for row in accessible_rows}

        self.assertEqual(len(accessible_rows), 2)
        self.assertEqual(normalized_groups, {"group-a", "group-b"})

        group_a_row = next(
            row for row in accessible_rows if isinstance(row["userSdwtProd"], str) and row["userSdwtProd"].casefold() == "group-a"
        )
        self.assertEqual(group_a_row["source"], "self")

    def test_request_affiliation_change_defaults_to_request_time(self) -> None:
        """effective_from이 없으면 요청 시각이 사용되는지 확인합니다."""
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S50001",
            password="test-password",
            is_staff=True,
            knox_id="knox-50001",
        )
        _set_current_affiliation(user, user_sdwt_prod="group-old")
        approver = User.objects.create_user(
            sabun="S50011",
            password="test-password",
            knox_id="knox-50011",
        )
        _set_current_affiliation(approver, user_sdwt_prod="group-new")
        _grant_access(user=approver, user_sdwt_prod="group-new", role="member")

        option = _affiliation(department="Dept", line="Line", user_sdwt_prod="group-new")

        before = timezone.now()
        payload, status_code = request_affiliation_change(
            user=user,
            option=option,
            to_user_sdwt_prod="group-new",
            effective_from=None,
            timezone_name="Asia/Seoul",
        )
        after = timezone.now()

        self.assertEqual(status_code, 202)
        change = UserSdwtProdChange.objects.get(id=payload["changeId"])
        self.assertGreaterEqual(change.effective_from, before)
        self.assertLessEqual(change.effective_from, after)
        self.assertEqual(change.status, UserSdwtProdChange.Status.PENDING)


class AffiliationOverviewTests(TestCase):
    """소속 개요 응답을 검증합니다."""

    def test_get_affiliation_overview_does_not_create_access_row(self) -> None:
        """개요 조회가 접근 권한 행을 생성하지 않는지 확인합니다."""
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S60000",
            password="test-password",
            knox_id="knox-60000",
        )
        _set_current_affiliation(user, user_sdwt_prod="group-a")

        self.assertEqual(UserSdwtProdAccess.objects.count(), 0)
        payload = get_affiliation_overview(user=user, timezone_name="Asia/Seoul")
        self.assertEqual(UserSdwtProdAccess.objects.count(), 0)

        self.assertEqual(payload["currentUserSdwtProd"], "group-a")
        self.assertEqual(payload["accessibleUserSdwtProds"][0]["userSdwtProd"], "group-a")

    def test_get_affiliation_overview_includes_external_snapshot(self) -> None:
        """외부 소속 스냅샷 값이 개요 응답에 포함되는지 확인합니다."""
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S60001",
            password="test-password",
            knox_id="knox-60001",
        )

        now = timezone.now()
        ExternalAffiliationSnapshot.objects.create(
            knox_id="knox-60001",
            department="Dept-External",
            predicted_user_sdwt_prod="group-external",
            source_updated_at=now,
            last_seen_at=now,
        )

        payload = get_affiliation_overview(user=user, timezone_name="Asia/Seoul")

        self.assertEqual(payload["snapshotUserSdwtProd"], "group-external")
        self.assertEqual(payload["snapshotDepartment"], "Dept-External")

    def test_get_affiliation_overview_uses_sso_department_without_snapshot(self) -> None:
        """외부 스냅샷이 없으면 SSO department를 개요 응답에 사용합니다."""
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S60002",
            password="test-password",
            knox_id="knox-60002",
        )
        user.department = "Dept-SSO"
        user.save(update_fields=["department"])

        payload = get_affiliation_overview(user=user, timezone_name="Asia/Seoul")

        self.assertEqual(payload["currentDepartment"], "Dept-SSO")
        self.assertIsNone(payload["snapshotUserSdwtProd"])
        self.assertEqual(payload["snapshotDepartment"], "Dept-SSO")


class AffiliationChangeRequestTests(TestCase):
    """소속 변경 요청을 검증합니다."""

    def test_request_affiliation_change_creates_pending_when_approver_exists(self) -> None:
        """승인자가 있으면 첫 소속 변경 요청은 승인 대기 상태로 생성되어야 합니다."""
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S50001",
            password="test-password",
            knox_id="knox-50001",
        )

        option = _affiliation(department="Dept", line="Line", user_sdwt_prod="group-new")
        approver = User.objects.create_user(
            sabun="S50012",
            password="test-password",
            knox_id="knox-50012",
        )
        _set_current_affiliation(approver, user_sdwt_prod="group-new")
        _grant_access(user=approver, user_sdwt_prod="group-new", role="member")

        payload, status_code = request_affiliation_change(
            user=user,
            option=option,
            to_user_sdwt_prod="group-new",
            effective_from=timezone.now() - timedelta(days=30),
            timezone_name="Asia/Seoul",
        )

        self.assertEqual(status_code, 202)

        user.refresh_from_db()
        self.assertIsNone(get_current_user_sdwt_prod(user=user))

        change = UserSdwtProdChange.objects.get(user=user, to_user_sdwt_prod="group-new")
        self.assertFalse(change.approved)
        self.assertFalse(change.applied)
        self.assertEqual(change.status, UserSdwtProdChange.Status.PENDING)

    def test_request_affiliation_change_rejects_same_as_current(self) -> None:
        """현재 소속과 동일한 값으로 요청하면 거절되는지 확인합니다."""
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S50010",
            password="test-password",
            knox_id="knox-50010",
        )
        _set_current_affiliation(user, user_sdwt_prod="group-a")

        option = _affiliation(department="Dept", line="Line", user_sdwt_prod="group-a")

        payload, status_code = request_affiliation_change(
            user=user,
            option=option,
            to_user_sdwt_prod="group-a",
            effective_from=timezone.now(),
            timezone_name="Asia/Seoul",
        )

        self.assertEqual(status_code, 400)
        self.assertEqual(payload["error"], "already current affiliation")
        self.assertFalse(UserSdwtProdChange.objects.filter(user=user).exists())

    def test_request_affiliation_change_rejects_same_as_current_case_insensitively(self) -> None:
        """현재 소속과 대소문자만 다른 값으로 요청해도 거절되는지 확인합니다."""
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S50013",
            password="test-password",
            knox_id="knox-50013",
        )
        _set_current_affiliation(user, user_sdwt_prod="GROUP-A")

        option = _affiliation(department="Dept", line="Line", user_sdwt_prod="group-a")

        payload, status_code = request_affiliation_change(
            user=user,
            option=option,
            to_user_sdwt_prod="group-a",
            effective_from=timezone.now(),
            timezone_name="Asia/Seoul",
        )

        self.assertEqual(status_code, 400)
        self.assertEqual(payload["error"], "already current affiliation")
        self.assertFalse(UserSdwtProdChange.objects.filter(user=user).exists())

    def test_request_affiliation_change_creates_pending_when_no_approver_and_no_prediction(self) -> None:
        """승인자가 없어도 예측 소속이 없으면 승인 대기가 생성되는지 확인합니다."""
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S50020",
            password="test-password",
            knox_id="knox-50020",
        )

        option = _affiliation(department="Dept", line="Line", user_sdwt_prod="group-auto")

        payload, status_code = request_affiliation_change(
            user=user,
            option=option,
            to_user_sdwt_prod="group-auto",
            effective_from=timezone.now() - timedelta(days=30),
            timezone_name="Asia/Seoul",
        )

        self.assertEqual(status_code, 202)
        self.assertEqual(payload["status"], "pending")

        user.refresh_from_db()
        self.assertIsNone(get_current_user_sdwt_prod(user=user))

        change = UserSdwtProdChange.objects.get(id=payload["changeId"])
        self.assertEqual(change.status, UserSdwtProdChange.Status.PENDING)
        self.assertFalse(change.approved)
        self.assertFalse(change.applied)

    def test_request_affiliation_change_auto_applies_when_predicted_match(self) -> None:
        """예측 소속과 일치하면 승인자 유무와 관계없이 자동 승인되는지 확인합니다."""
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S50021",
            password="test-password",
            knox_id="knox-50021",
        )

        ExternalAffiliationSnapshot.objects.create(
            knox_id="knox-50021",
            predicted_user_sdwt_prod="group-auto",
            source_updated_at=timezone.now(),
            last_seen_at=timezone.now(),
        )

        option = _affiliation(department="Dept", line="Line", user_sdwt_prod="group-auto")

        approver = User.objects.create_user(
            sabun="S50022",
            password="test-password",
            knox_id="knox-50022",
        )
        _set_current_affiliation(approver, user_sdwt_prod="group-auto")
        _grant_access(user=approver, user_sdwt_prod="group-auto", role="member")

        payload, status_code = request_affiliation_change(
            user=user,
            option=option,
            to_user_sdwt_prod="group-auto",
            effective_from=timezone.now() - timedelta(days=30),
            timezone_name="Asia/Seoul",
        )

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["status"], "applied")

        user.refresh_from_db()
        self.assertEqual(get_current_user_sdwt_prod(user=user), "group-auto")

        change = UserSdwtProdChange.objects.get(id=payload["changeId"])
        self.assertEqual(change.status, UserSdwtProdChange.Status.APPROVED)
        access = UserSdwtProdAccess.objects.get(
            user=user,
            affiliation__user_sdwt_prod__iexact="group-auto",
        )
        self.assertEqual(access.role, "member")

    def test_request_affiliation_change_auto_applies_when_predicted_match_case_insensitively(self) -> None:
        """예측 소속과 대소문자만 다른 요청도 자동 승인되는지 확인합니다."""
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S50023",
            password="test-password",
            knox_id="knox-50023",
        )

        ExternalAffiliationSnapshot.objects.create(
            knox_id="knox-50023",
            predicted_user_sdwt_prod="GROUP-AUTO",
            source_updated_at=timezone.now(),
            last_seen_at=timezone.now(),
        )

        option = _affiliation(department="Dept", line="Line", user_sdwt_prod="group-auto")

        payload, status_code = request_affiliation_change(
            user=user,
            option=option,
            to_user_sdwt_prod="group-auto",
            effective_from=timezone.now() - timedelta(days=30),
            timezone_name="Asia/Seoul",
        )

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["status"], "applied")

        user.refresh_from_db()
        self.assertEqual(get_current_user_sdwt_prod(user=user), "group-auto")

        change = UserSdwtProdChange.objects.get(id=payload["changeId"])
        self.assertEqual(change.status, UserSdwtProdChange.Status.APPROVED)

    def test_request_affiliation_change_supersedes_pending_and_skips_auto_apply(self) -> None:
        """기존 pending이 있으면 대체하고 자동 승인을 건너뛰는지 확인합니다."""
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S50002",
            password="test-password",
            knox_id="knox-50002",
        )
        _set_current_affiliation(user, user_sdwt_prod="group-old")

        ExternalAffiliationSnapshot.objects.create(
            knox_id="knox-50002",
            predicted_user_sdwt_prod="group-new",
            source_updated_at=timezone.now(),
            last_seen_at=timezone.now(),
        )

        pending = UserSdwtProdChange.objects.create(
            user=user,
            department="Dept",
            line="Line",
            from_user_sdwt_prod="group-old",
            to_user_sdwt_prod="group-pending",
            effective_from=timezone.now(),
            status=UserSdwtProdChange.Status.PENDING,
            applied=False,
            approved=False,
            created_by=user,
        )

        option = _affiliation(department="Dept", line="Line", user_sdwt_prod="group-new")

        payload, status_code = request_affiliation_change(
            user=user,
            option=option,
            to_user_sdwt_prod="group-new",
            effective_from=timezone.now(),
            timezone_name="Asia/Seoul",
        )

        self.assertEqual(status_code, 202)
        self.assertEqual(payload["status"], "pending")

        pending.refresh_from_db()
        self.assertEqual(pending.status, UserSdwtProdChange.Status.SUPERSEDED)
        self.assertEqual(pending.rejection_reason, "취소(대체됨)")

        change = UserSdwtProdChange.objects.get(id=payload["changeId"])
        self.assertEqual(change.status, UserSdwtProdChange.Status.PENDING)
        self.assertFalse(change.approved)
        self.assertFalse(change.applied)

        user.refresh_from_db()
        self.assertEqual(get_current_user_sdwt_prod(user=user), "group-old")

    def test_member_cannot_approve_affiliation_change(self) -> None:
        """소속 member는 manager 역할 없이 승인할 수 없습니다."""
        User = get_user_model()
        approver = User.objects.create_user(
            sabun="S50003",
            password="test-password",
            knox_id="knox-50003",
        )
        _set_current_affiliation(approver, user_sdwt_prod="group-a")
        _grant_access(user=approver, user_sdwt_prod="group-a", role="member")

        requester = User.objects.create_user(
            sabun="S50004",
            password="test-password",
            knox_id="knox-50004",
        )

        change = UserSdwtProdChange.objects.create(
            user=requester,
            department="Dept",
            line="Line",
            from_user_sdwt_prod=None,
            to_user_sdwt_prod="group-a",
            effective_from=timezone.now(),
            status=UserSdwtProdChange.Status.PENDING,
            applied=False,
            approved=False,
            created_by=requester,
        )

        payload, status_code = approve_affiliation_change(approver=approver, change_id=change.id)
        self.assertEqual(status_code, 403)
        self.assertEqual(payload["error"], "forbidden")

        change.refresh_from_db()
        self.assertEqual(change.status, UserSdwtProdChange.Status.PENDING)
        requester.refresh_from_db()
        self.assertIsNone(get_current_user_sdwt_prod(user=requester))


class ExternalAffiliationSyncTests(TestCase):
    """외부 소속 동기화/재확인 흐름을 검증합니다."""

    def test_sync_external_affiliations_stores_username_from_record(self) -> None:
        """외부 동기화 입력의 username을 스냅샷에 저장하는지 확인합니다."""

        result = sync_external_affiliations(
            records=[
                {
                    "knox_id": "loginid-ext-username-1",
                    "username": "홍길동",
                    "department": "Dept",
                    "user_sdwt_prod": "group-a",
                    "source_updated_at": timezone.now(),
                }
            ]
        )

        snapshot = ExternalAffiliationSnapshot.objects.get(knox_id="loginid-ext-username-1")
        self.assertEqual(result["created"], 1)
        self.assertEqual(snapshot.username, "홍길동")

    def test_sync_external_affiliations_does_not_use_account_user_username_when_record_missing(self) -> None:
        """입력 username이 없으면 account_user.username을 대신 저장하지 않습니다."""

        User = get_user_model()
        user = User.objects.create_user(
            sabun="S70100",
            password="test-password",
            username="계정사용자",
            knox_id="loginid-ext-username-2",
        )

        sync_external_affiliations(
            records=[
                {
                    "knox_id": user.knox_id,
                    "department": "Dept",
                    "user_sdwt_prod": "group-a",
                    "source_updated_at": timezone.now(),
                }
            ]
        )

        snapshot = ExternalAffiliationSnapshot.objects.get(knox_id="loginid-ext-username-2")
        self.assertIsNone(snapshot.username)

    def test_sync_external_affiliations_keeps_username_when_record_omits_username(self) -> None:
        """기존 username은 입력 필드가 아예 없을 때 보존합니다."""

        updated_at = timezone.now()
        ExternalAffiliationSnapshot.objects.create(
            knox_id="loginid-ext-username-3",
            username="기존이름",
            department="Dept",
            predicted_user_sdwt_prod="group-a",
            source_updated_at=updated_at,
            last_seen_at=updated_at,
        )

        result = sync_external_affiliations(
            records=[
                {
                    "knox_id": "loginid-ext-username-3",
                    "department": "Dept",
                    "user_sdwt_prod": "group-a",
                    "source_updated_at": updated_at,
                }
            ]
        )

        snapshot = ExternalAffiliationSnapshot.objects.get(knox_id="loginid-ext-username-3")
        self.assertEqual(result["unchanged"], 1)
        self.assertEqual(snapshot.username, "기존이름")

    def test_sync_external_affiliations_flags_user_on_change(self) -> None:
        """예측 소속 변경 시 재확인 플래그가 켜지는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        user = User.objects.create_user(sabun="S70001", password="test-password")
        user.knox_id = "loginid-ext-1"
        user.save(update_fields=["knox_id"])
        _set_current_affiliation(user, user_sdwt_prod="group-a")

        # -----------------------------------------------------------------------------
        # 2) 초기 동기화(변경 없음)
        # -----------------------------------------------------------------------------
        sync_external_affiliations(
            records=[
                {
                    "knox_id": "loginid-ext-1",
                    "department": "Dept",
                    "user_sdwt_prod": "group-a",
                    "source_updated_at": timezone.now(),
                }
            ]
        )
        user.refresh_from_db()
        self.assertFalse(UserCurrentAffiliation.objects.get(user=user).requires_reconfirm)

        # -----------------------------------------------------------------------------
        # 3) 변경 동기화 및 결과 검증
        # -----------------------------------------------------------------------------
        result = sync_external_affiliations(
            records=[
                {
                    "knox_id": "loginid-ext-1",
                    "department": "Dept",
                    "user_sdwt_prod": "group-b",
                    "source_updated_at": timezone.now(),
                }
            ]
        )
        user.refresh_from_db()

        self.assertEqual(result["updated"], 1)
        self.assertTrue(UserCurrentAffiliation.objects.get(user=user).requires_reconfirm)

    def test_sync_external_affiliations_ignores_case_only_predicted_change(self) -> None:
        """예측 소속이 대소문자만 다르면 변경으로 보지 않는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자/스냅샷 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        user = User.objects.create_user(sabun="S70009", password="test-password")
        user.knox_id = "loginid-ext-9"
        user.save(update_fields=["knox_id"])
        _set_current_affiliation(user, user_sdwt_prod="group-a")

        updated_at = timezone.now()
        ExternalAffiliationSnapshot.objects.create(
            knox_id="loginid-ext-9",
            department="Dept",
            predicted_user_sdwt_prod="GROUP-A",
            source_updated_at=updated_at,
            last_seen_at=updated_at,
        )

        # -----------------------------------------------------------------------------
        # 2) 동일 소속(대소문자만 다름) 동기화 호출
        # -----------------------------------------------------------------------------
        result = sync_external_affiliations(
            records=[
                {
                    "knox_id": "loginid-ext-9",
                    "department": "Dept",
                    "user_sdwt_prod": "group-a",
                    "source_updated_at": updated_at,
                }
            ]
        )

        # -----------------------------------------------------------------------------
        # 3) 결과 검증
        # -----------------------------------------------------------------------------
        user.refresh_from_db()
        snapshot = ExternalAffiliationSnapshot.objects.get(knox_id="loginid-ext-9")

        self.assertEqual(result["updated"], 0)
        self.assertEqual(result["unchanged"], 1)
        self.assertFalse(UserCurrentAffiliation.objects.get(user=user).requires_reconfirm)
        self.assertEqual(snapshot.predicted_user_sdwt_prod, "GROUP-A")

    def test_sync_external_affiliations_ignores_when_pending_exists(self) -> None:
        """대기 변경이 있으면 재확인 플래그를 켜지 않는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자/스냅샷/대기 요청 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        user = User.objects.create_user(sabun="S70008", password="test-password")
        user.knox_id = "loginid-ext-8"
        user.save(update_fields=["knox_id"])
        _set_current_affiliation(user, user_sdwt_prod="group-a")

        ExternalAffiliationSnapshot.objects.create(
            knox_id="loginid-ext-8",
            predicted_user_sdwt_prod="group-a",
            source_updated_at=timezone.now(),
            last_seen_at=timezone.now(),
        )

        UserSdwtProdChange.objects.create(
            user=user,
            department="Dept",
            line="Line",
            from_user_sdwt_prod="group-a",
            to_user_sdwt_prod="group-b",
            effective_from=timezone.now(),
            status=UserSdwtProdChange.Status.PENDING,
            applied=False,
            approved=False,
            created_by=user,
        )

        # -----------------------------------------------------------------------------
        # 2) 예측 변경 동기화 호출
        # -----------------------------------------------------------------------------
        sync_external_affiliations(
            records=[
                {
                    "knox_id": "loginid-ext-8",
                    "department": "Dept",
                    "user_sdwt_prod": "group-b",
                    "source_updated_at": timezone.now(),
                }
            ]
        )

        # -----------------------------------------------------------------------------
        # 3) 결과 검증
        # -----------------------------------------------------------------------------
        user.refresh_from_db()
        self.assertFalse(UserCurrentAffiliation.objects.get(user=user).requires_reconfirm)

    def test_sync_external_affiliations_dedupes_knox_ids(self) -> None:
        """동일 knox_id가 중복되면 최신 값만 반영되는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자/스냅샷 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        user = User.objects.create_user(sabun="S70003", password="test-password")
        user.knox_id = "loginid-ext-3"
        user.save(update_fields=["knox_id"])
        _set_current_affiliation(user, user_sdwt_prod="group-a")

        ExternalAffiliationSnapshot.objects.create(
            knox_id="loginid-ext-3",
            predicted_user_sdwt_prod="group-a",
            source_updated_at=timezone.now(),
            last_seen_at=timezone.now(),
        )

        # -----------------------------------------------------------------------------
        # 2) 중복 knox_id 동기화 호출
        # -----------------------------------------------------------------------------
        result = sync_external_affiliations(
            records=[
                {
                    "knox_id": "loginid-ext-3",
                    "department": "Dept",
                    "user_sdwt_prod": "group-b",
                    "source_updated_at": timezone.now(),
                },
                {
                    "knox_id": "loginid-ext-3",
                    "department": "Dept",
                    "user_sdwt_prod": "group-c",
                    "source_updated_at": timezone.now(),
                },
            ]
        )

        # -----------------------------------------------------------------------------
        # 3) 결과 검증
        # -----------------------------------------------------------------------------
        self.assertEqual(result["updated"], 1)
        user.refresh_from_db()
        self.assertTrue(UserCurrentAffiliation.objects.get(user=user).requires_reconfirm)
        snapshot = ExternalAffiliationSnapshot.objects.get(knox_id="loginid-ext-3")
        self.assertEqual(snapshot.predicted_user_sdwt_prod, "group-c")

    def test_sync_external_affiliations_keeps_affiliation_options_app_managed(self) -> None:
        """외부 동기화가 앱 소속 옵션을 자동 생성하지 않는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사전 조건 확인
        # -----------------------------------------------------------------------------
        self.assertFalse(Affiliation.objects.filter(user_sdwt_prod="group-new").exists())

        # -----------------------------------------------------------------------------
        # 2) 외부 동기화 호출
        # -----------------------------------------------------------------------------
        sync_external_affiliations(
            records=[
                {
                    "knox_id": "loginid-ext-9",
                    "department": "Dept",
                    "user_sdwt_prod": "group-new",
                    "source_updated_at": timezone.now(),
                }
            ]
        )

        # -----------------------------------------------------------------------------
        # 3) 결과 검증
        # -----------------------------------------------------------------------------
        option = Affiliation.objects.filter(user_sdwt_prod="group-new").first()
        self.assertIsNone(option)

    def test_sync_external_affiliations_reuses_affiliation_option_case_insensitively(self) -> None:
        """기존 소속 옵션이 대소문자만 다르면 중복 생성하지 않는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 기존 소속 옵션 준비
        # -----------------------------------------------------------------------------
        _affiliation(department="Dept", line="", user_sdwt_prod="GROUP-NEW")

        # -----------------------------------------------------------------------------
        # 2) 외부 동기화 호출
        # -----------------------------------------------------------------------------
        sync_external_affiliations(
            records=[
                {
                    "knox_id": "loginid-ext-13",
                    "department": "Dept",
                    "user_sdwt_prod": "group-new",
                    "source_updated_at": timezone.now(),
                }
            ]
        )

        # -----------------------------------------------------------------------------
        # 3) 결과 검증
        # -----------------------------------------------------------------------------
        self.assertEqual(Affiliation.objects.filter(user_sdwt_prod__iexact="group-new").count(), 1)
        option = Affiliation.objects.get(user_sdwt_prod__iexact="group-new")
        self.assertEqual(option.user_sdwt_prod, "GROUP-NEW")

    def test_sync_external_affiliations_does_not_create_majority_affiliation(self) -> None:
        """외부 스냅샷 department 다수결로 앱 소속 옵션을 만들지 않는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사전 조건 확인
        # -----------------------------------------------------------------------------
        self.assertFalse(Affiliation.objects.filter(user_sdwt_prod="group-major").exists())

        # -----------------------------------------------------------------------------
        # 2) 외부 동기화 호출(DeptA 2회, DeptB 1회)
        # -----------------------------------------------------------------------------
        sync_external_affiliations(
            records=[
                {
                    "knox_id": "loginid-ext-10",
                    "department": "DeptA",
                    "user_sdwt_prod": "group-major",
                    "source_updated_at": timezone.now(),
                },
                {
                    "knox_id": "loginid-ext-11",
                    "department": "DeptA",
                    "user_sdwt_prod": "group-major",
                    "source_updated_at": timezone.now(),
                },
                {
                    "knox_id": "loginid-ext-12",
                    "department": "DeptB",
                    "user_sdwt_prod": "group-major",
                    "source_updated_at": timezone.now(),
                },
            ]
        )

        # -----------------------------------------------------------------------------
        # 3) 결과 검증
        # -----------------------------------------------------------------------------
        option = Affiliation.objects.filter(user_sdwt_prod="group-major").first()
        self.assertIsNone(option)

    def test_reconfirm_response_auto_approves(self) -> None:
        """재확인 응답이 자동 승인으로 적용되는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자/소속 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        user = User.objects.create_user(sabun="S70002", password="test-password")
        user.knox_id = "loginid-ext-2"
        user.save(update_fields=["knox_id"])
        _set_current_affiliation(
            user,
            user_sdwt_prod="group-old",
            requires_reconfirm=True,
        )

        _affiliation(department="Dept", line="Line", user_sdwt_prod="group-old")
        _affiliation(department="Dept", line="Line", user_sdwt_prod="group-a")

        # -----------------------------------------------------------------------------
        # 2) 외부 동기화 및 재확인 요청
        # -----------------------------------------------------------------------------
        sync_external_affiliations(
            records=[
                {
                    "knox_id": "loginid-ext-2",
                    "department": "Dept",
                    "user_sdwt_prod": "group-a",
                    "source_updated_at": timezone.now(),
                }
            ]
        )

        payload, status_code = submit_affiliation_reconfirm_response(
            user=user,
            accepted=True,
            user_sdwt_prod="group-a",
            timezone_name="Asia/Seoul",
        )

        # -----------------------------------------------------------------------------
        # 3) 결과 검증
        # -----------------------------------------------------------------------------
        self.assertEqual(status_code, 200)
        self.assertEqual(payload["status"], "applied")

        user.refresh_from_db()
        values = UserCurrentAffiliation.objects.get(user=user)
        self.assertEqual(values.affiliation.user_sdwt_prod, "group-a")
        self.assertFalse(values.requires_reconfirm)

        change = UserSdwtProdChange.objects.get(id=payload["changeId"])
        self.assertEqual(change.status, UserSdwtProdChange.Status.APPROVED)

    def test_reconfirm_response_creates_pending_on_mismatch(self) -> None:
        """재확인 응답이 예측값과 불일치하면 승인 대기를 생성하는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자/소속/스냅샷 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        user = User.objects.create_user(sabun="S70006", password="test-password")
        user.knox_id = "loginid-ext-6"
        user.save(update_fields=["knox_id"])
        _set_current_affiliation(
            user,
            user_sdwt_prod="group-a",
            requires_reconfirm=True,
        )

        _affiliation(department="Dept", line="Line", user_sdwt_prod="group-a")
        _affiliation(department="Dept", line="Line", user_sdwt_prod="group-b")
        ExternalAffiliationSnapshot.objects.create(
            knox_id="loginid-ext-6",
            predicted_user_sdwt_prod="group-a",
            source_updated_at=timezone.now(),
            last_seen_at=timezone.now(),
        )

        # -----------------------------------------------------------------------------
        # 2) 재확인 응답(불일치) 제출
        # -----------------------------------------------------------------------------
        payload, status_code = submit_affiliation_reconfirm_response(
            user=user,
            accepted=True,
            user_sdwt_prod="group-b",
            timezone_name="Asia/Seoul",
        )

        # -----------------------------------------------------------------------------
        # 3) 결과 검증
        # -----------------------------------------------------------------------------
        self.assertEqual(status_code, 202)
        self.assertEqual(payload["status"], "pending")

        user.refresh_from_db()
        self.assertFalse(UserCurrentAffiliation.objects.get(user=user).requires_reconfirm)

        change = UserSdwtProdChange.objects.get(id=payload["changeId"])
        self.assertEqual(change.status, UserSdwtProdChange.Status.PENDING)

    def test_reconfirm_response_keeps_current_affiliation(self) -> None:
        """재확인에서 기존 소속 유지를 선택하면 플래그만 해제되는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        user = User.objects.create_user(sabun="S70004", password="test-password")
        user.knox_id = "loginid-ext-4"
        user.save(update_fields=["knox_id"])
        _set_current_affiliation(
            user,
            user_sdwt_prod="group-x",
            requires_reconfirm=True,
        )

        # -----------------------------------------------------------------------------
        # 2) 재확인 유지 응답
        # -----------------------------------------------------------------------------
        payload, status_code = submit_affiliation_reconfirm_response(
            user=user,
            accepted=False,
            user_sdwt_prod=None,
            timezone_name="Asia/Seoul",
        )

        # -----------------------------------------------------------------------------
        # 3) 결과 검증
        # -----------------------------------------------------------------------------
        self.assertEqual(status_code, 200)
        self.assertEqual(payload["status"], "kept")

        user.refresh_from_db()
        values = UserCurrentAffiliation.objects.get(user=user)
        self.assertEqual(values.affiliation.user_sdwt_prod, "group-x")
        self.assertFalse(values.requires_reconfirm)

    def test_reconfirm_response_keeps_current_affiliation_case_insensitively(self) -> None:
        """재확인에서 현재 소속과 대소문자만 다른 선택을 해도 유지 처리되는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        user = User.objects.create_user(sabun="S70010", password="test-password")
        user.knox_id = "loginid-ext-10"
        user.save(update_fields=["knox_id"])
        _set_current_affiliation(
            user,
            user_sdwt_prod="GROUP-X",
            requires_reconfirm=True,
        )

        # -----------------------------------------------------------------------------
        # 2) 재확인 응답
        # -----------------------------------------------------------------------------
        payload, status_code = submit_affiliation_reconfirm_response(
            user=user,
            accepted=True,
            user_sdwt_prod="group-x",
            timezone_name="Asia/Seoul",
        )

        # -----------------------------------------------------------------------------
        # 3) 결과 검증
        # -----------------------------------------------------------------------------
        self.assertEqual(status_code, 200)
        self.assertEqual(payload["status"], "kept")

        user.refresh_from_db()
        values = UserCurrentAffiliation.objects.get(user=user)
        self.assertEqual(values.affiliation.user_sdwt_prod, "GROUP-X")
        self.assertFalse(values.requires_reconfirm)

    def test_auto_approve_affiliation_from_snapshot(self) -> None:
        """외부 스냅샷 기반 자동 승인이 적용되는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 소속/스냅샷 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()

        _affiliation(department="Dept", line="Line", user_sdwt_prod="group-auto")
        ExternalAffiliationSnapshot.objects.create(
            knox_id="loginid-auto-1",
            predicted_user_sdwt_prod="group-auto",
            source_updated_at=timezone.now(),
            last_seen_at=timezone.now(),
        )

        # -----------------------------------------------------------------------------
        # 2) 사용자 생성 및 자동 승인 호출
        # -----------------------------------------------------------------------------
        user = User.objects.create_user(sabun="S70005", password="test-password")
        user.knox_id = "loginid-auto-1"
        user.save(update_fields=["knox_id"])

        result = auto_approve_affiliation_from_snapshot(user=user, timezone_name="Asia/Seoul")

        # -----------------------------------------------------------------------------
        # 3) 결과 검증
        # -----------------------------------------------------------------------------
        self.assertIsNotNone(result)
        payload, status_code = result or ({}, 0)
        self.assertEqual(status_code, 200)
        self.assertEqual(payload.get("status"), "applied")

        user.refresh_from_db()
        values = UserCurrentAffiliation.objects.get(user=user)
        self.assertEqual(values.affiliation.user_sdwt_prod, "group-auto")
        self.assertFalse(values.requires_reconfirm)


class AccountAccessServiceTests(TestCase):
    """접근 권한 서비스 로직을 검증합니다."""

    def test_ensure_self_access_normalizes_user_sdwt_prod(self) -> None:
        """ensure_self_access가 user_sdwt_prod 공백을 정규화하는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        user = User.objects.create_user(sabun="S80002", password="test-password")
        _set_current_affiliation(user, user_sdwt_prod="group-a")

        # -----------------------------------------------------------------------------
        # 2) 접근 권한 보장
        # -----------------------------------------------------------------------------
        access = ensure_self_access(user, role="member")

        # -----------------------------------------------------------------------------
        # 3) 결과 검증
        # -----------------------------------------------------------------------------
        self.assertIsNotNone(access)
        self.assertEqual(access.user_sdwt_prod, "group-a")
        self.assertEqual(
            UserSdwtProdAccess.objects.filter(
                user=user,
                affiliation__user_sdwt_prod__iexact="group-a",
            ).count(),
            1,
        )

    def test_ensure_self_access_reuses_existing_row_case_insensitively(self) -> None:
        """기존 접근 권한 행이 대소문자만 다르면 재사용하는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자/기존 접근 권한 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        user = User.objects.create_user(sabun="S80003", password="test-password")
        _set_current_affiliation(user, user_sdwt_prod="GROUP-A")

        existing = _grant_access(
            user=user,
            user_sdwt_prod="group-a",
            role="viewer",
        )

        # -----------------------------------------------------------------------------
        # 2) 접근 권한 보장
        # -----------------------------------------------------------------------------
        access = ensure_self_access(user, role="member")

        # -----------------------------------------------------------------------------
        # 3) 결과 검증
        # -----------------------------------------------------------------------------
        self.assertIsNotNone(access)
        self.assertEqual(access.id, existing.id)
        self.assertEqual(access.role, "member")
        self.assertEqual(
            UserSdwtProdAccess.objects.filter(
                user=user,
                affiliation__user_sdwt_prod__iexact="group-a",
            ).count(),
            1,
        )


class DevAccessSeedTests(TestCase):
    """로컬 권한 관리 화면용 더미데이터 구성을 검증합니다."""

    def setUp(self) -> None:
        """권한 결정 감사 로그에 사용할 dev 관리자 역할 사용자를 준비합니다."""

        AccessScope.objects.update_or_create(
            key=ACCESS_SCOPE_PORTAL,
            defaults={
                "name": "Portal",
                "scope_type": AccessScope.ScopeTypes.PORTAL,
                "is_active": True,
                "requestable": True,
            },
        )
        for scope_key in (
            "appstore",
            "assistant",
            "line-dashboard",
            "observer",
            "voc",
            "l3-spider",
        ):
            AccessScope.objects.update_or_create(
                key=scope_key,
                defaults={
                    "name": scope_key,
                    "scope_type": AccessScope.ScopeTypes.APP,
                    "is_active": True,
                    "requestable": True,
                },
            )
        self.actor = get_user_model().objects.create_superuser(
            sabun="S-SEED-ADMIN",
            password="test-password",
            knox_id="seed-admin",
        )

    def test_seed_dev_access_data_builds_pending_and_matrix_samples(self) -> None:
        """시드가 페이지네이션용 대기 요청과 상태 비교 행을 함께 생성해야 합니다."""

        result = seed_dev_access_data(
            prefix="dev",
            actor=self.actor,
            reset=True,
        )

        self.assertEqual(
            result,
            {
                "deletedUsers": 0,
                "users": 28,
                "pending": 54,
                "allowed": 6,
                "denied": 2,
            },
        )
        seeded_users = get_user_model().objects.filter(
            sabun__startswith="DEV-ACCESS-",
        )
        self.assertEqual(seeded_users.count(), 28)
        self.assertEqual(
            UserAccess.objects.filter(
                user__in=seeded_users,
                scope__key=ACCESS_SCOPE_PORTAL,
                status=UserAccess.Status.PENDING,
            ).count(),
            24,
        )
        self.assertEqual(
            UserAccess.objects.filter(
                user__sabun="DEV-ACCESS-025",
                scope__key="appstore",
                status=UserAccess.Status.ALLOWED,
                role=AccessRole.ADMIN,
            ).count(),
            1,
        )
        self.assertTrue(
            AccessAuditLog.objects.filter(
                affiliation__user_sdwt_prod__startswith="DEV_ACCESS_",
                action=AccessAuditLog.Actions.AFFILIATION_CREATE,
                after__source="dev_seed",
            ).exists()
        )
        self.assertEqual(
            UserAccess.objects.filter(
                user__sabun="DEV-ACCESS-027",
                scope__key=ACCESS_SCOPE_PORTAL,
                status=UserAccess.Status.DENIED,
            ).count(),
            1,
        )

    def test_seed_dev_access_data_is_repeatable_with_and_without_reset(self) -> None:
        """같은 prefix 시드를 반복해도 사용자와 권한 행 수가 늘어나지 않아야 합니다."""

        seed_dev_access_data(prefix="DEV", actor=self.actor)
        repeated_result = seed_dev_access_data(prefix="DEV", actor=self.actor)
        reset_result = seed_dev_access_data(
            prefix="DEV",
            actor=self.actor,
            reset=True,
        )

        self.assertEqual(repeated_result["users"], 28)
        self.assertEqual(repeated_result["pending"], 54)
        self.assertEqual(reset_result["deletedUsers"], 28)
        self.assertEqual(reset_result["users"], 28)
        self.assertEqual(
            get_user_model().objects.filter(
                sabun__startswith="DEV-ACCESS-",
            ).count(),
            28,
        )


class AppAffiliationDataScopeTests(TestCase):
    """앱 접근 역할과 앱별 소속 데이터 범위가 독립적으로 동작하는지 검증합니다."""

    def setUp(self) -> None:
        """Portal 관리자, 대상 사용자, 앱 scope와 소속 옵션을 준비합니다."""

        User = get_user_model()
        self.actor = User.objects.create_superuser(
            sabun="S-SCOPE-ADMIN",
            password="test-password",
            knox_id="scope-admin",
        )
        self.user = User.objects.create_user(
            sabun="S-SCOPE-USER",
            password="test-password",
        )
        self.portal = AccessScope.objects.update_or_create(
            key=ACCESS_SCOPE_PORTAL,
            defaults={
                "name": "Portal",
                "scope_type": AccessScope.ScopeTypes.PORTAL,
                "data_scope_type": AccessScope.DataScopeTypes.NONE,
                "include_current_affiliation": False,
            },
        )[0]
        self.assistant = AccessScope.objects.update_or_create(
            key="assistant",
            defaults={
                "name": "Assistant",
                "scope_type": AccessScope.ScopeTypes.APP,
                "data_scope_type": AccessScope.DataScopeTypes.AFFILIATION,
                "include_current_affiliation": True,
            },
        )[0]
        self.emails = AccessScope.objects.update_or_create(
            key="emails",
            defaults={
                "name": "Emails",
                "scope_type": AccessScope.ScopeTypes.APP,
                "data_scope_type": AccessScope.DataScopeTypes.AFFILIATION,
                "include_current_affiliation": True,
            },
        )[0]
        self.appstore = AccessScope.objects.update_or_create(
            key="appstore",
            defaults={
                "name": "Appstore",
                "scope_type": AccessScope.ScopeTypes.APP,
                "data_scope_type": AccessScope.DataScopeTypes.NONE,
                "include_current_affiliation": False,
            },
        )[0]
        self.affiliation_a = _affiliation(user_sdwt_prod="scope-group-a")
        self.affiliation_b = _affiliation(user_sdwt_prod="scope-group-b")
        self.affiliation_c = _affiliation(user_sdwt_prod="scope-group-c")
        self.inactive_affiliation = _affiliation(user_sdwt_prod="scope-group-inactive")
        self.inactive_affiliation.is_active = False
        self.inactive_affiliation.save(update_fields=["is_active"])
        UserCurrentAffiliation.objects.create(
            user=self.user,
            affiliation=self.affiliation_a,
            source=UserCurrentAffiliation.Sources.USER_SELECTED,
            confirmed_at=timezone.now(),
        )
        for scope, role in (
            (self.portal, AccessRole.USER),
            (self.assistant, AccessRole.ADMIN),
            (self.emails, AccessRole.ADMIN),
        ):
            UserAccess.objects.create(
                user=self.user,
                scope=scope,
                status=UserAccess.Status.ALLOWED,
                role=role,
            )

    def test_explicit_grants_are_isolated_by_app_and_include_current_affiliation(self) -> None:
        """같은 사용자의 명시 소속 grant가 다른 앱으로 전파되지 않아야 합니다."""

        assistant_payload, assistant_status = update_user_scope_affiliation_data(
            actor=self.actor,
            user_id=self.user.id,
            scope_key="assistant",
            data_scope_mode=UserAccess.DataScopeModes.DEFAULT,
            affiliation_ids=[self.affiliation_b.id],
            reason="Assistant 추가 데이터 범위",
        )
        emails_payload, emails_status = update_user_scope_affiliation_data(
            actor=self.actor,
            user_id=self.user.id,
            scope_key="emails",
            data_scope_mode=UserAccess.DataScopeModes.DEFAULT,
            affiliation_ids=[self.affiliation_c.id],
            reason="Emails 추가 데이터 범위",
        )

        self.assertEqual(assistant_status, 200, assistant_payload)
        self.assertEqual(emails_status, 200, emails_payload)
        assistant_effective = get_effective_affiliation_scope(
            user=self.user,
            scope_key="assistant",
        )
        emails_effective = get_effective_affiliation_scope(
            user=self.user,
            scope_key="emails",
        )
        self.assertEqual(
            set(assistant_effective["affiliationIds"]),
            {self.affiliation_a.id, self.affiliation_b.id},
        )
        self.assertEqual(
            set(emails_effective["affiliationIds"]),
            {self.affiliation_a.id, self.affiliation_c.id},
        )
        self.assertFalse(assistant_effective["all"])
        self.assertFalse(emails_effective["all"])

    def test_current_affiliation_source_wins_over_overlapping_manual_grant(self) -> None:
        """현재 소속과 수동 grant가 겹쳐도 자동 포함 source를 유지해야 합니다."""

        payload, status_code = update_user_scope_affiliation_data(
            actor=self.actor,
            user_id=self.user.id,
            scope_key="emails",
            data_scope_mode=UserAccess.DataScopeModes.DEFAULT,
            affiliation_ids=[self.affiliation_a.id],
            reason="현재 소속과 겹치는 수동 범위",
        )

        self.assertEqual(status_code, 200, payload)
        self.assertEqual(payload["grants"][0]["source"], "manual")
        self.assertEqual(payload["effective"]["affiliationIds"], [self.affiliation_a.id])
        self.assertEqual(payload["effective"]["affiliations"][0]["source"], "current")

    def test_admin_role_does_not_imply_all_affiliations(self) -> None:
        """앱 admin 역할만으로 전체 소속 데이터 접근이 생기지 않아야 합니다."""

        effective = get_effective_affiliation_scope(
            user=self.user,
            scope_key="emails",
        )

        self.assertEqual(effective["mode"], "selected")
        self.assertEqual(effective["affiliationIds"], [self.affiliation_a.id])

    def test_explicit_all_mode_returns_only_active_affiliations(self) -> None:
        """사유와 함께 부여한 전체 모드는 활성 소속만 반환해야 합니다."""

        payload, status_code = update_user_scope_affiliation_data(
            actor=self.actor,
            user_id=self.user.id,
            scope_key="emails",
            data_scope_mode=UserAccess.DataScopeModes.ALL,
            affiliation_ids=[],
            reason="메일 운영 전체 조회",
        )

        self.assertEqual(status_code, 200, payload)
        effective = get_effective_affiliation_scope(
            user=self.user,
            scope_key="emails",
        )
        self.assertEqual(effective["mode"], "all")
        self.assertEqual(
            set(effective["affiliationIds"]),
            {
                self.affiliation_a.id,
                self.affiliation_b.id,
                self.affiliation_c.id,
            },
        )
        self.assertNotIn(self.inactive_affiliation.id, effective["affiliationIds"])

    def test_lightweight_all_decision_does_not_enumerate_affiliations(self) -> None:
        """전체 범위의 쓰기 판정은 활성 소속 목록을 조회하지 않아야 합니다."""

        access = UserAccess.objects.get(user=self.user, scope=self.emails)
        access.data_scope_mode = UserAccess.DataScopeModes.ALL
        access.save(update_fields=["data_scope_mode", "updated_at"])

        with patch(
            "api.account.services.data_scope.selectors.list_active_affiliations"
        ) as list_active_affiliations:
            decision = get_affiliation_scope_decision(
                user=self.user,
                scope_key="emails",
            )

        list_active_affiliations.assert_not_called()
        self.assertTrue(decision["allowed"])
        self.assertTrue(decision["all"])
        self.assertEqual(decision["affiliationIds"], [])
        self.assertEqual(decision["userSdwtProds"], [])

    def test_repeated_app_grant_preserves_explicit_all_mode(self) -> None:
        """이미 허용된 앱을 다시 부여해도 명시적 전체 범위를 유지해야 합니다."""

        access = UserAccess.objects.get(user=self.user, scope=self.emails)
        access.data_scope_mode = UserAccess.DataScopeModes.ALL
        access.save(update_fields=["data_scope_mode", "updated_at"])

        payload, status_code = decide_user_access(
            actor=self.actor,
            user_id=self.user.id,
            scope_key=self.emails.key,
            action="grant",
            role=AccessRole.ADMIN,
            reason="앱 권한 재확인",
        )

        self.assertEqual(status_code, 200, payload)
        access.refresh_from_db()
        self.assertEqual(
            access.data_scope_mode,
            UserAccess.DataScopeModes.ALL,
        )
        self.assertFalse(
            AccessAuditLog.objects.filter(
                target_user=self.user,
                scope=self.emails,
                action=AccessAuditLog.Actions.DATA_SCOPE_CHANGE,
            ).exists()
        )

    def test_revoke_resets_all_mode_with_data_scope_audit(self) -> None:
        """앱을 회수하며 전체 범위를 닫을 때 별도 데이터 범위 감사를 남겨야 합니다."""

        access = UserAccess.objects.get(user=self.user, scope=self.emails)
        access.data_scope_mode = UserAccess.DataScopeModes.ALL
        access.save(update_fields=["data_scope_mode", "updated_at"])

        payload, status_code = decide_user_access(
            actor=self.actor,
            user_id=self.user.id,
            scope_key=self.emails.key,
            action="revoke",
            reason="메일 앱 운영 종료",
        )

        self.assertEqual(status_code, 200, payload)
        access.refresh_from_db()
        self.assertEqual(
            access.data_scope_mode,
            UserAccess.DataScopeModes.DEFAULT,
        )
        audit = AccessAuditLog.objects.get(
            target_user=self.user,
            scope=self.emails,
            action=AccessAuditLog.Actions.DATA_SCOPE_CHANGE,
        )
        self.assertEqual(audit.before, {"dataScopeMode": "all"})
        self.assertEqual(audit.after, {"dataScopeMode": "default"})

    def test_reset_to_policy_records_all_mode_data_scope_change(self) -> None:
        """자동 규칙으로 되돌리며 전체 범위를 제거할 때 별도 감사를 남겨야 합니다."""

        access = UserAccess.objects.get(user=self.user, scope=self.emails)
        access.data_scope_mode = UserAccess.DataScopeModes.ALL
        access.save(update_fields=["data_scope_mode", "updated_at"])

        payload, status_code = decide_user_access(
            actor=self.actor,
            user_id=self.user.id,
            scope_key=self.emails.key,
            action=AccessAuditLog.Actions.RESET_TO_POLICY,
            reason="메일 권한 자동 규칙 복귀",
        )

        self.assertEqual(status_code, 200, payload)
        self.assertFalse(
            UserAccess.objects.filter(user=self.user, scope=self.emails).exists()
        )
        audit = AccessAuditLog.objects.get(
            target_user=self.user,
            scope=self.emails,
            action=AccessAuditLog.Actions.DATA_SCOPE_CHANGE,
        )
        self.assertEqual(audit.before, {"dataScopeMode": "all"})
        self.assertEqual(audit.after, {"dataScopeMode": "default"})

    def test_apply_all_denied_records_all_mode_data_scope_change(self) -> None:
        """전체 권한 차단으로 전체 범위를 닫을 때 데이터 범위 감사를 남겨야 합니다."""

        access = UserAccess.objects.get(user=self.user, scope=self.emails)
        access.data_scope_mode = UserAccess.DataScopeModes.ALL
        access.save(update_fields=["data_scope_mode", "updated_at"])
        self.client.force_login(self.actor)

        response = self.client.post(
            reverse(
                "account-access-user-apply-all",
                kwargs={"user_id": self.user.id},
            ),
            data={"value": "denied", "reason": "전체 권한 차단 검증"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        access.refresh_from_db()
        self.assertEqual(access.status, UserAccess.Status.DENIED)
        self.assertEqual(
            access.data_scope_mode,
            UserAccess.DataScopeModes.DEFAULT,
        )
        audit = AccessAuditLog.objects.get(
            target_user=self.user,
            scope=self.emails,
            action=AccessAuditLog.Actions.DATA_SCOPE_CHANGE,
        )
        self.assertEqual(audit.before, {"dataScopeMode": "all"})
        self.assertEqual(audit.after, {"dataScopeMode": "default"})

    def test_apply_all_inherit_records_all_mode_data_scope_change(self) -> None:
        """전체 자동 규칙 적용으로 전체 범위를 삭제할 때 별도 감사를 남겨야 합니다."""

        access = UserAccess.objects.get(user=self.user, scope=self.emails)
        access.data_scope_mode = UserAccess.DataScopeModes.ALL
        access.save(update_fields=["data_scope_mode", "updated_at"])
        self.client.force_login(self.actor)

        response = self.client.post(
            reverse(
                "account-access-user-apply-all",
                kwargs={"user_id": self.user.id},
            ),
            data={"value": "inherit", "reason": "전체 자동 규칙 검증"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(
            UserAccess.objects.filter(user=self.user, scope=self.emails).exists()
        )
        audit = AccessAuditLog.objects.get(
            target_user=self.user,
            scope=self.emails,
            action=AccessAuditLog.Actions.DATA_SCOPE_CHANGE,
        )
        self.assertEqual(audit.before, {"dataScopeMode": "all"})
        self.assertEqual(audit.after, {"dataScopeMode": "default"})

    def test_denied_app_access_makes_existing_grant_inert(self) -> None:
        """명시 소속 grant가 남아 있어도 앱 접근이 거부되면 fail-closed 해야 합니다."""

        UserScopeAffiliationGrant.objects.create(
            user=self.user,
            scope=self.assistant,
            affiliation=self.affiliation_b,
            granted_by=self.actor,
        )
        access = UserAccess.objects.get(user=self.user, scope=self.assistant)
        access.status = UserAccess.Status.DENIED
        access.role = AccessRole.USER
        access.save(update_fields=["status", "role", "updated_at"])

        effective = get_effective_affiliation_scope(
            user=self.user,
            scope_key="assistant",
        )

        self.assertFalse(effective["allowed"])
        self.assertEqual(effective["mode"], "denied")
        self.assertEqual(effective["affiliationIds"], [])

    def test_management_api_updates_scope_and_writes_audit_logs(self) -> None:
        """관리 API가 선택 범위를 교체하고 소속 단위 감사 로그를 남겨야 합니다."""

        self.client.force_login(self.actor)
        response = self.client.put(
            reverse(
                "account-access-user-data-scope",
                kwargs={"user_id": self.user.id},
            ),
            data=json.dumps(
                {
                    "scope": "assistant",
                    "dataScopeMode": "default",
                    "affiliationIds": [self.affiliation_b.id],
                    "reason": "프로젝트 협업 범위",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(
            UserScopeAffiliationGrant.objects.filter(
                user=self.user,
                scope=self.assistant,
                affiliation=self.affiliation_b,
                is_active=True,
            ).exists()
        )
        self.assertTrue(
            AccessAuditLog.objects.filter(
                target_user=self.user,
                scope=self.assistant,
                affiliation=self.affiliation_b,
                action=AccessAuditLog.Actions.DATA_SCOPE_GRANT,
            ).exists()
        )

    def test_data_scope_change_requires_reason_and_all_requires_app_access(self) -> None:
        """모든 범위 변경은 사유가 필요하고 전체 범위는 앱 허용 행도 요구해야 합니다."""

        payload, status_code = update_user_scope_affiliation_data(
            actor=self.actor,
            user_id=self.user.id,
            scope_key="emails",
            data_scope_mode=UserAccess.DataScopeModes.DEFAULT,
            affiliation_ids=[],
            reason="",
        )
        self.assertEqual(status_code, 400)
        self.assertEqual(payload["error"], "reason_required")

        access = UserAccess.objects.get(user=self.user, scope=self.emails)
        access.status = UserAccess.Status.DENIED
        access.role = AccessRole.USER
        access.save(update_fields=["status", "role", "updated_at"])
        payload, status_code = update_user_scope_affiliation_data(
            actor=self.actor,
            user_id=self.user.id,
            scope_key="emails",
            data_scope_mode=UserAccess.DataScopeModes.ALL,
            affiliation_ids=[],
            reason="운영 확인",
        )
        self.assertEqual(status_code, 409)
        self.assertEqual(payload["error"], "allowed_app_access_required_for_all")

    def test_access_only_app_rejects_affiliation_scope_management(self) -> None:
        """소속 정보가 필요 없는 앱에는 소속 데이터 범위를 설정할 수 없어야 합니다."""

        payload, status_code = update_user_scope_affiliation_data(
            actor=self.actor,
            user_id=self.user.id,
            scope_key="appstore",
            data_scope_mode=UserAccess.DataScopeModes.DEFAULT,
            affiliation_ids=[self.affiliation_b.id],
            reason="지원되지 않는 설정",
        )

        self.assertEqual(status_code, 400)
        self.assertEqual(payload["error"], "affiliation_scope_not_supported")

    def test_data_migration_converts_legacy_grants_and_existing_emails_admin(self) -> None:
        """전환 migration이 기존 전역 grant와 Emails 관리자 동작을 보존해야 합니다."""

        for affiliation in (self.affiliation_b, self.affiliation_c):
            UserSdwtProdAccess.objects.create(
                user=self.user,
                affiliation=affiliation,
                role=UserSdwtProdAccess.Roles.MEMBER,
                granted_by=self.actor,
            )
        migration = importlib.import_module(
            "api.account.migrations.0006_account_authorization_system"
        )
        schema_editor = type(
            "SchemaEditorStub",
            (),
            {"connection": connection},
        )()
        original_bulk_create = QuerySet.bulk_create
        batch_sizes: list[int] = []

        def tracking_bulk_create(queryset, objects, **kwargs):
            """migration이 전달한 batch 크기를 기록한 뒤 실제 저장을 수행합니다."""

            batch_sizes.append(len(objects))
            return original_bulk_create(queryset, objects, **kwargs)

        with patch.object(migration, "MIGRATION_BATCH_SIZE", 2), patch.object(
            QuerySet,
            "bulk_create",
            tracking_bulk_create,
        ):
            migration.seed_app_affiliation_data_scopes(django_apps, schema_editor)

        self.assertEqual(
            set(
                UserScopeAffiliationGrant.objects.filter(
                    user=self.user,
                    affiliation=self.affiliation_b,
                    is_active=True,
                ).values_list("scope__key", flat=True)
            ),
            {"assistant", "emails"},
        )
        self.assertEqual(batch_sizes, [2, 2])
        emails_access = UserAccess.objects.get(user=self.user, scope=self.emails)
        self.assertEqual(
            emails_access.data_scope_mode,
            UserAccess.DataScopeModes.ALL,
        )

    def test_manual_update_protects_effective_grants_and_reclaims_ended_grants(self) -> None:
        """활성 자동 grant는 보호하고 만료·비활성 자동 grant는 수동으로 전환해야 합니다."""

        policy_grant = UserScopeAffiliationGrant.objects.create(
            user=self.user,
            scope=self.assistant,
            affiliation=self.affiliation_b,
            source=UserScopeAffiliationGrant.Sources.POLICY,
            granted_by=self.actor,
        )
        expired_grant = UserScopeAffiliationGrant.objects.create(
            user=self.user,
            scope=self.assistant,
            affiliation=self.affiliation_c,
            source=UserScopeAffiliationGrant.Sources.EXTERNAL,
            expires_at=timezone.now() - timedelta(minutes=1),
            granted_by=self.actor,
        )

        payload, status_code = update_user_scope_affiliation_data(
            actor=self.actor,
            user_id=self.user.id,
            scope_key="assistant",
            data_scope_mode=UserAccess.DataScopeModes.DEFAULT,
            affiliation_ids=[],
            reason="수동 범위 초기화",
        )

        self.assertEqual(status_code, 200, payload)
        policy_grant.refresh_from_db()
        expired_grant.refresh_from_db()
        self.assertTrue(policy_grant.is_active)
        self.assertTrue(expired_grant.is_active)
        effective = get_effective_affiliation_scope(
            user=self.user,
            scope_key="assistant",
        )
        self.assertEqual(
            set(effective["affiliationIds"]),
            {self.affiliation_a.id, self.affiliation_b.id},
        )
        conflict_payload, conflict_status = update_user_scope_affiliation_data(
            actor=self.actor,
            user_id=self.user.id,
            scope_key="assistant",
            data_scope_mode=UserAccess.DataScopeModes.DEFAULT,
            affiliation_ids=[self.affiliation_b.id],
            reason="자동 grant 수동 전환 시도",
        )
        self.assertEqual(conflict_status, 409)
        self.assertEqual(
            conflict_payload["error"],
            "non_manual_affiliation_grants_immutable",
        )

        converted_payload, converted_status = update_user_scope_affiliation_data(
            actor=self.actor,
            user_id=self.user.id,
            scope_key="assistant",
            data_scope_mode=UserAccess.DataScopeModes.DEFAULT,
            affiliation_ids=[self.affiliation_c.id],
            reason="만료 자동 grant 수동 전환",
        )
        self.assertEqual(converted_status, 200, converted_payload)
        expired_grant.refresh_from_db()
        self.assertEqual(
            expired_grant.source,
            UserScopeAffiliationGrant.Sources.MANUAL,
        )
        self.assertTrue(expired_grant.is_active)
        self.assertIsNone(expired_grant.expires_at)
        conversion_audit = AccessAuditLog.objects.get(
            target_user=self.user,
            scope=self.assistant,
            affiliation=self.affiliation_c,
            action=AccessAuditLog.Actions.DATA_SCOPE_GRANT,
        )
        self.assertEqual(conversion_audit.before["source"], "external")
        self.assertEqual(conversion_audit.after["source"], "manual")

        policy_grant.is_active = False
        policy_grant.save(update_fields=["is_active", "updated_at"])
        inactive_payload, inactive_status = update_user_scope_affiliation_data(
            actor=self.actor,
            user_id=self.user.id,
            scope_key="assistant",
            data_scope_mode=UserAccess.DataScopeModes.DEFAULT,
            affiliation_ids=[self.affiliation_b.id, self.affiliation_c.id],
            reason="비활성 자동 grant 수동 전환",
        )
        self.assertEqual(inactive_status, 200, inactive_payload)
        policy_grant.refresh_from_db()
        self.assertEqual(
            policy_grant.source,
            UserScopeAffiliationGrant.Sources.MANUAL,
        )
        self.assertTrue(policy_grant.is_active)
        self.assertIsNone(policy_grant.expires_at)

    def test_expired_scope_grants_are_deactivated_once_with_audit(self) -> None:
        """worker용 만료 처리는 grant를 한 번만 비활성화하고 감사 로그를 남겨야 합니다."""

        grant = UserScopeAffiliationGrant.objects.create(
            user=self.user,
            scope=self.assistant,
            affiliation=self.affiliation_b,
            source=UserScopeAffiliationGrant.Sources.EXTERNAL,
            expires_at=timezone.now() - timedelta(minutes=1),
            granted_by=self.actor,
        )

        first = deactivate_expired_scope_affiliation_grants(
            scope_key="assistant",
            limit=10,
        )
        second = deactivate_expired_scope_affiliation_grants(
            scope_key="assistant",
            limit=10,
        )

        grant.refresh_from_db()
        self.assertEqual((first, second), (1, 0))
        self.assertFalse(grant.is_active)
        audit = AccessAuditLog.objects.get(
            target_user=self.user,
            scope=self.assistant,
            affiliation=self.affiliation_b,
            action=AccessAuditLog.Actions.DATA_SCOPE_REVOKE,
        )
        self.assertTrue(audit.before["isActive"])
        self.assertFalse(audit.after["isActive"])
        self.assertEqual(audit.reason, "소속 데이터 범위 grant 만료")

    def test_data_scope_update_locks_active_affiliations_inside_transaction(self) -> None:
        """소속 범위 저장은 활성 소속을 transaction 안에서 잠가 검증해야 합니다."""

        with patch(
            "api.account.services.data_scope.selectors."
            "list_active_affiliations_by_ids_for_update",
            wraps=list_active_affiliations_by_ids_for_update,
        ) as locked_selector:
            payload, status_code = update_user_scope_affiliation_data(
                actor=self.actor,
                user_id=self.user.id,
                scope_key="assistant",
                data_scope_mode=UserAccess.DataScopeModes.DEFAULT,
                affiliation_ids=[self.affiliation_b.id],
                reason="잠금 검증",
            )

        self.assertEqual(status_code, 200, payload)
        locked_selector.assert_called_once_with(
            affiliation_ids={self.affiliation_b.id},
        )

        invalid_payload, invalid_status = update_user_scope_affiliation_data(
            actor=self.actor,
            user_id=self.user.id,
            scope_key="assistant",
            data_scope_mode=UserAccess.DataScopeModes.DEFAULT,
            affiliation_ids=[self.inactive_affiliation.id],
            reason="비활성 소속 차단",
        )
        self.assertEqual(invalid_status, 400)
        self.assertEqual(invalid_payload["error"], "invalid_affiliation_ids")


class AccountSelectorEmailTests(TestCase):
    """계정 이메일 셀렉터 동작을 검증합니다."""

    def test_list_active_user_emails_deduplicates_and_filters_invalid_values(self) -> None:
        """활성 사용자 이메일 목록이 중복 제거/공백 제거되어 반환되는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자 데이터 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()

        user_a = User.objects.create_user(sabun="S82001", password="test-password")
        user_a.email = "dup@example.com"
        user_a.save(update_fields=["email"])
        _set_current_affiliation(user_a, user_sdwt_prod="group-a")

        user_b = User.objects.create_user(sabun="S82002", password="test-password")
        user_b.email = " dup@example.com "
        user_b.save(update_fields=["email"])
        _set_current_affiliation(user_b, user_sdwt_prod="group-a")

        user_c = User.objects.create_user(sabun="S82003", password="test-password")
        user_c.email = "other@example.com"
        user_c.save(update_fields=["email"])
        _set_current_affiliation(user_c, user_sdwt_prod="group-a")

        user_inactive = User.objects.create_user(sabun="S82004", password="test-password")
        user_inactive.email = "inactive@example.com"
        user_inactive.is_active = False
        user_inactive.save(update_fields=["email", "is_active"])
        _set_current_affiliation(user_inactive, user_sdwt_prod="group-a")

        user_blank = User.objects.create_user(sabun="S82005", password="test-password")
        user_blank.email = "   "
        user_blank.save(update_fields=["email"])
        _set_current_affiliation(user_blank, user_sdwt_prod="group-a")

        user_other_group = User.objects.create_user(sabun="S82006", password="test-password")
        user_other_group.email = "group-b@example.com"
        user_other_group.save(update_fields=["email"])
        _set_current_affiliation(user_other_group, user_sdwt_prod="group-b")

        # -----------------------------------------------------------------------------
        # 2) 셀렉터 호출
        # -----------------------------------------------------------------------------
        emails = list_active_user_emails_by_user_sdwt_prod(user_sdwt_prod="group-a")

        # -----------------------------------------------------------------------------
        # 3) 결과 검증
        # -----------------------------------------------------------------------------
        self.assertEqual(emails, ["dup@example.com", "other@example.com"])

    def test_list_active_user_emails_matches_user_sdwt_prod_case_insensitively(self) -> None:
        """활성 사용자 이메일 조회가 user_sdwt_prod 대소문자를 구분하지 않는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자 데이터 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()

        user = User.objects.create_user(sabun="S82007", password="test-password")
        user.email = "case@example.com"
        user.save(update_fields=["email"])
        _set_current_affiliation(user, user_sdwt_prod="GROUP-A")

        # -----------------------------------------------------------------------------
        # 2) 셀렉터 호출 및 결과 검증
        # -----------------------------------------------------------------------------
        emails = list_active_user_emails_by_user_sdwt_prod(user_sdwt_prod="group-a")
        self.assertEqual(emails, ["case@example.com"])

    def test_list_active_user_knox_ids_deduplicates_and_filters_invalid_values(self) -> None:
        """활성 사용자 knox_id 목록이 중복 제거/공백 제거되어 반환되는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자 데이터 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()

        user_a = User.objects.create_user(sabun="S82011", password="test-password")
        user_a.knox_id = "knox-dup"
        user_a.save(update_fields=["knox_id"])
        _set_current_affiliation(user_a, user_sdwt_prod="group-a")

        user_b = User.objects.create_user(sabun="S82012", password="test-password")
        user_b.knox_id = " knox-dup "
        user_b.save(update_fields=["knox_id"])
        _set_current_affiliation(user_b, user_sdwt_prod="group-a")

        user_c = User.objects.create_user(sabun="S82013", password="test-password")
        user_c.knox_id = "knox-other"
        user_c.save(update_fields=["knox_id"])
        _set_current_affiliation(user_c, user_sdwt_prod="group-a")

        user_inactive = User.objects.create_user(sabun="S82014", password="test-password")
        user_inactive.knox_id = "knox-inactive"
        user_inactive.is_active = False
        user_inactive.save(update_fields=["knox_id", "is_active"])
        _set_current_affiliation(user_inactive, user_sdwt_prod="group-a")

        user_blank = User.objects.create_user(sabun="S82015", password="test-password")
        user_blank.knox_id = "   "
        user_blank.save(update_fields=["knox_id"])
        _set_current_affiliation(user_blank, user_sdwt_prod="group-a")

        user_other_group = User.objects.create_user(sabun="S82016", password="test-password")
        user_other_group.knox_id = "knox-group-b"
        user_other_group.save(update_fields=["knox_id"])
        _set_current_affiliation(user_other_group, user_sdwt_prod="group-b")

        # -----------------------------------------------------------------------------
        # 2) 셀렉터 호출
        # -----------------------------------------------------------------------------
        knox_ids = list_active_user_knox_ids_by_user_sdwt_prod(user_sdwt_prod="group-a")

        # -----------------------------------------------------------------------------
        # 3) 결과 검증
        # -----------------------------------------------------------------------------
        self.assertEqual(knox_ids, ["knox-dup", "knox-other"])

    def test_list_active_user_knox_ids_matches_user_sdwt_prod_case_insensitively(self) -> None:
        """활성 사용자 knox_id 조회가 user_sdwt_prod 대소문자를 구분하지 않는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자 데이터 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()

        user = User.objects.create_user(sabun="S82017", password="test-password")
        user.knox_id = "knox-case"
        user.save(update_fields=["knox_id"])
        _set_current_affiliation(user, user_sdwt_prod="GROUP-A")

        # -----------------------------------------------------------------------------
        # 2) 셀렉터 호출 및 결과 검증
        # -----------------------------------------------------------------------------
        knox_ids = list_active_user_knox_ids_by_user_sdwt_prod(user_sdwt_prod="group-a")
        self.assertEqual(knox_ids, ["knox-case"])


class AuthorizationConcurrencyTests(TransactionTestCase):
    """PostgreSQL 행 잠금이 권한 불변조건을 직렬화하는지 검증합니다."""

    def _fixture_teardown(self) -> None:
        """다음 migration 테스트가 초기 데이터까지 포함한 최신 상태에서 시작하게 합니다."""

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

    def _run_concurrently(self, *workers):
        """각 worker가 독립 DB 연결을 사용하도록 동시에 실행합니다."""

        with ThreadPoolExecutor(max_workers=len(workers)) as executor:
            futures = [executor.submit(worker) for worker in workers]
            results = [future.result(timeout=15) for future in futures]
        close_old_connections()
        return results

    def test_concurrent_manager_revokes_preserve_one_manager(self) -> None:
        """두 manager를 동시에 회수해도 마지막 manager 한 명은 남아야 합니다."""

        User = get_user_model()
        actor = User.objects.create_superuser(
            sabun="S-CONCURRENT-MANAGER-ACTOR",
            password="test-password",
        )
        affiliation = _affiliation(user_sdwt_prod="concurrent-managers")
        managers = [
            User.objects.create_user(
                sabun=f"S-CONCURRENT-MANAGER-{index}",
                password="test-password",
            )
            for index in (1, 2)
        ]
        for manager in managers:
            UserSdwtProdAccess.objects.create(
                user=manager,
                affiliation=affiliation,
                role=UserSdwtProdAccess.Roles.MANAGER,
                granted_by=actor,
            )
        barrier = Barrier(2)

        def revoke_manager(user_id):
            close_old_connections()
            barrier.wait(timeout=10)
            payload, status_code = grant_or_revoke_access(
                grantor=User.objects.get(pk=actor.id),
                target_group=affiliation.user_sdwt_prod,
                target_user=User.objects.get(pk=user_id),
                action="revoke",
                role=None,
                reason="동시 manager 회수 검증",
            )
            close_old_connections()
            return payload, status_code

        results = self._run_concurrently(
            lambda: revoke_manager(managers[0].id),
            lambda: revoke_manager(managers[1].id),
        )

        self.assertEqual(sorted(status for _payload, status in results), [200, 409])
        self.assertEqual(
            UserSdwtProdAccess.objects.filter(
                affiliation=affiliation,
                role=UserSdwtProdAccess.Roles.MANAGER,
            ).count(),
            1,
        )

    def test_concurrent_affiliation_requests_leave_one_pending_request(self) -> None:
        """같은 사용자의 동시 소속 요청은 이전 요청을 대체하고 하나만 대기시킵니다."""

        User = get_user_model()
        user = User.objects.create_user(
            sabun="S-CONCURRENT-REQUEST",
            password="test-password",
        )
        _set_current_affiliation(user, user_sdwt_prod="concurrent-current")
        targets = [
            _affiliation(user_sdwt_prod=f"concurrent-target-{index}")
            for index in (1, 2)
        ]
        barrier = Barrier(2)

        def request_change(option_id):
            close_old_connections()
            barrier.wait(timeout=10)
            locked_user = User.objects.get(pk=user.id)
            option = Affiliation.objects.get(pk=option_id)
            payload, status_code = request_affiliation_change(
                user=locked_user,
                option=option,
                to_user_sdwt_prod=option.user_sdwt_prod,
                effective_from=None,
                timezone_name="Asia/Seoul",
                force_pending=True,
            )
            close_old_connections()
            return payload, status_code

        results = self._run_concurrently(
            lambda: request_change(targets[0].id),
            lambda: request_change(targets[1].id),
        )

        self.assertEqual([status for _payload, status in results], [202, 202])
        changes = UserSdwtProdChange.objects.filter(user=user)
        self.assertEqual(
            changes.filter(status=UserSdwtProdChange.Status.PENDING).count(),
            1,
        )
        self.assertEqual(
            changes.filter(status=UserSdwtProdChange.Status.SUPERSEDED).count(),
            1,
        )

    def test_deactivate_and_grant_race_finishes_fail_closed(self) -> None:
        """소속 비활성화와 권한 부여가 경합해도 최종 capability는 없어야 합니다."""

        User = get_user_model()
        actor = User.objects.create_superuser(
            sabun="S-CONCURRENT-DEACTIVATE-ACTOR",
            password="test-password",
        )
        target = User.objects.create_user(
            sabun="S-CONCURRENT-DEACTIVATE-TARGET",
            password="test-password",
        )
        affiliation = _affiliation(user_sdwt_prod="concurrent-deactivate")
        barrier = Barrier(2)

        def deactivate():
            close_old_connections()
            barrier.wait(timeout=10)
            result = set_affiliation_active(
                actor=User.objects.get(pk=actor.id),
                affiliation_id=affiliation.id,
                is_active=False,
                reason="동시 비활성화 검증",
            )
            close_old_connections()
            return "deactivate", result

        def grant():
            close_old_connections()
            barrier.wait(timeout=10)
            result = grant_or_revoke_access(
                grantor=User.objects.get(pk=actor.id),
                target_group=affiliation.user_sdwt_prod,
                target_user=User.objects.get(pk=target.id),
                action="grant",
                role=UserSdwtProdAccess.Roles.MANAGER,
                reason="동시 권한 부여 검증",
            )
            close_old_connections()
            return "grant", result

        results = dict(self._run_concurrently(deactivate, grant))

        self.assertEqual(results["deactivate"][1], 200)
        self.assertIn(results["grant"][1], {200, 400})
        affiliation.refresh_from_db()
        self.assertFalse(affiliation.is_active)
        self.assertFalse(
            has_affiliation_capability(
                user=target,
                user_sdwt_prod=affiliation.user_sdwt_prod,
                capability=AFFILIATION_CAPABILITY_MANAGE_ACCESS,
            )
        )
        self.assertTrue(
            AccessAuditLog.objects.filter(
                affiliation=affiliation,
                action=AccessAuditLog.Actions.AFFILIATION_DEACTIVATE,
                reason="동시 비활성화 검증",
            ).exists()
        )
        role_audit_exists = AccessAuditLog.objects.filter(
            affiliation=affiliation,
            target_user=target,
            action=AccessAuditLog.Actions.AFFILIATION_ROLE_GRANT,
            reason="동시 권한 부여 검증",
        ).exists()
        self.assertEqual(role_audit_exists, results["grant"][1] == 200)
