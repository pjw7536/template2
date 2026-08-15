"""legacy Account 권한의 Keycloak 이관 계약을 검증합니다."""

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from api.account.services.keycloak_migration import (
    KeycloakMigrationValidationError,
    apply_keycloak_plan,
    build_legacy_keycloak_plan,
    compare_keycloak_plan,
)
from api.account.services.keycloak_cutover import (
    KeycloakCutoverValidationError,
    build_keycloak_cutover_manifest,
)


def _legacy_user(
    *,
    user_id: int,
    sabun: str,
    username: str,
    email: str,
    affiliation_name: str = "ALPHA",
):
    """테스트용 legacy 사용자와 기본 소속 관계를 만듭니다."""

    affiliation = SimpleNamespace(user_sdwt_prod=affiliation_name)
    return SimpleNamespace(
        id=user_id,
        sabun=sabun,
        knox_id=username,
        email=email,
        first_name="Test",
        last_name="User",
        current_affiliation=SimpleNamespace(affiliation=affiliation),
    )


class KeycloakMigrationPlanTests(SimpleTestCase):
    """이관 dry-run, 차단 조건, 멱등 적용과 비교를 검증합니다."""

    @patch(
        "api.account.services.keycloak_migration.selectors."
        "get_accessible_user_sdwt_prod_roles_for_user",
        return_value={"ALPHA": "member"},
    )
    @patch("api.account.services.keycloak_migration.get_access_payload")
    @patch(
        "api.account.services.keycloak_migration.selectors."
        "list_active_users_for_keycloak_migration"
    )
    def test_dry_run_is_deterministic_and_omits_legacy_history(
        self,
        list_users,
        get_access_payload,
        _get_roles,
    ):
        """동일 입력은 같은 checksum이며 현재 유효 권한만 포함합니다."""

        list_users.return_value = [
            _legacy_user(
                user_id=1,
                sabun="S000001",
                username="normal.user",
                email="normal@example.com",
            ),
            _legacy_user(
                user_id=2,
                sabun="S999999",
                username="emergency.admin",
                email="emergency@example.com",
            ),
        ]
        get_access_payload.side_effect = lambda *, user, scope_key: {
            "allowed": scope_key in {"portal", "work-hub"},
            "role": "user",
        }

        first = build_legacy_keycloak_plan(emergency_sabun="S999999")
        second = build_legacy_keycloak_plan(emergency_sabun="S999999")

        self.assertEqual(first["checksum"], second["checksum"])
        self.assertEqual(first["user_count"], 2)
        self.assertEqual(first["users"][0]["group_path"], "/affiliations/ALPHA/member")
        self.assertIn("work-hub-user", first["users"][0]["client_roles"])
        self.assertIn("work-hub-admin", first["users"][1]["client_roles"])
        self.assertEqual(
            first["omitted"],
            [
                "pending",
                "denied",
                "expired_grants",
                "additional_data_scopes",
                "audit_history",
            ],
        )

    @patch(
        "api.account.services.keycloak_migration.selectors."
        "list_active_users_for_keycloak_migration"
    )
    @patch("api.account.services.keycloak_migration.get_access_payload")
    def test_missing_or_duplicate_identity_blocks_plan(
        self,
        get_access_payload,
        list_users,
    ):
        """비상 계정 누락과 중복 identity는 이관 전에 차단합니다."""

        get_access_payload.return_value = {"allowed": False, "role": None}
        list_users.return_value = [
            _legacy_user(
                user_id=1,
                sabun="S000001",
                username="duplicate.user",
                email="one@example.com",
            ),
            _legacy_user(
                user_id=2,
                sabun="S000002",
                username="DUPLICATE.USER",
                email="two@example.com",
            ),
        ]

        with self.assertRaises(KeycloakMigrationValidationError) as raised:
            build_legacy_keycloak_plan(emergency_sabun="S999999")

        self.assertIn("중복 username", str(raised.exception))
        self.assertIn("비상 계정", str(raised.exception))

    @patch("api.account.services.keycloak_migration.auth_services.KeycloakProvisioningClient")
    def test_apply_can_repeat_and_compare_detects_mismatch(self, client_class):
        """동일 계획 재적용은 가능하고 비교는 역할 차이를 보고합니다."""

        client = Mock()
        client_class.from_settings.return_value = client
        client.resolve_group_id.return_value = "group-alpha"
        client.ensure_user.return_value = "user-alpha"
        plan = {
            "users": [
                {
                    "username": "normal.user",
                    "sabun": "S000001",
                    "email": "normal@example.com",
                    "first_name": "Normal",
                    "last_name": "User",
                    "affiliation_name": "ALPHA",
                    "affiliation_role": "member",
                    "group_path": "/affiliations/ALPHA/member",
                    "client_roles": ["portal-user", "work-hub-user"],
                }
            ]
        }

        self.assertEqual(apply_keycloak_plan(plan=plan), {"applied": 1})
        self.assertEqual(apply_keycloak_plan(plan=plan), {"applied": 1})
        self.assertEqual(client.ensure_user.call_count, 2)

        client.get_user_state.return_value = {
            "groups": ["/affiliations/ALPHA/member"],
            "client_roles": ["portal-user"],
        }
        comparison = compare_keycloak_plan(plan=plan)

        self.assertFalse(comparison["matched"])
        self.assertEqual(comparison["mismatches"][0]["username"], "normal.user")


class KeycloakCutoverManifestTests(SimpleTestCase):
    """cutover manifest가 세 가지 복구 증적을 모두 강제하는지 검증합니다."""

    @patch("api.account.services.keycloak_cutover.build_account_table_manifest")
    @patch("api.account.services.keycloak_cutover.build_legacy_keycloak_plan")
    def test_manifest_records_evidence_checksums(self, build_plan, build_tables):
        """DB backup, realm export, 복원 시험 파일의 checksum을 기록합니다."""

        build_plan.return_value = {"user_count": 2, "checksum": "plan-checksum"}
        build_tables.return_value = {"account_user": {"rows": 2, "sha256": "rows"}}
        with TemporaryDirectory() as directory:
            paths = [Path(directory) / name for name in ("db.dump", "realm.json", "restore.txt")]
            for path in paths:
                path.write_text(path.name, encoding="utf-8")

            manifest = build_keycloak_cutover_manifest(
                emergency_sabun="S999999",
                database_backup_path=str(paths[0]),
                realm_export_path=str(paths[1]),
                realm_restore_evidence_path=str(paths[2]),
            )

        self.assertEqual(manifest["migration_plan"]["user_count"], 2)
        self.assertEqual(set(manifest["evidence"]), {
            "database_backup",
            "realm_export",
            "realm_restore_test",
        })
        self.assertTrue(all(item["sha256"] for item in manifest["evidence"].values()))

    @patch("api.account.services.keycloak_cutover.build_legacy_keycloak_plan")
    def test_manifest_rejects_missing_evidence(self, build_plan):
        """필수 복구 증적 하나라도 없으면 cutover 검증을 중단합니다."""

        build_plan.return_value = {"user_count": 0, "checksum": "plan-checksum"}
        with self.assertRaises(KeycloakCutoverValidationError):
            build_keycloak_cutover_manifest(
                emergency_sabun="S999999",
                database_backup_path="/missing/database.dump",
                realm_export_path="/missing/realm.json",
                realm_restore_evidence_path="/missing/restore.txt",
            )
