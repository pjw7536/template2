"""Keycloak 세션 권한과 신규 EPID 계정 계약의 회귀 테스트입니다."""
from django.test import TestCase, override_settings
from django.db import IntegrityError, transaction

from .models import User, UserAccess, AccessScope, AccessPolicyRule
from .services import (
    build_authorization_snapshot, bind_authorization_context, get_authorization_context,
    get_access_payload, get_effective_affiliation_scope, has_sdwt_capability,
    upsert_user_identity, has_scope_role,
)


@override_settings(OIDC_CLIENT_ID="portal")
class KeycloakAccessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(sabun="1001", avatarid="9001", knox_id="test.user")

    def bind(self, *, dept="OTHER", roles=(), groups=(), user=None):
        user = user or self.user
        snapshot = build_authorization_snapshot({"userid": user.avatarid, "deptid": dept,
            "user_sdwt_prod": "SDWT-A", "line_id": "L1", "groups": list(groups),
            "resource_access": {"portal": {"roles": list(roles)}}})
        bind_authorization_context(user=user, snapshot=snapshot)
        return snapshot

    def test_standard_role_opens_apps_but_not_data(self):
        self.bind(dept="ETCH", roles=["portal-all-apps"])
        for scope in ("portal", "emails", "assistant", "line-dashboard"):
            self.assertTrue(get_access_payload(user=self.user, scope_key=scope)["allowed"])
            self.assertFalse(has_scope_role(user=self.user, scope_key=scope))
        self.assertEqual(get_effective_affiliation_scope(user=self.user, scope_key="emails")["userSdwtProds"], [])
        self.assertFalse(has_sdwt_capability(user=self.user, user_sdwt_prod="SDWT-A", capability="read"))

    def test_external_specific_and_all_apps(self):
        self.bind(roles=["emails-user"])
        self.assertTrue(get_access_payload(user=self.user)["allowed"])
        self.assertTrue(get_access_payload(user=self.user, scope_key="emails")["allowed"])
        self.assertFalse(get_access_payload(user=self.user, scope_key="assistant")["allowed"])
        self.bind(roles=["portal-all-apps"])
        self.assertTrue(get_access_payload(user=self.user, scope_key="assistant")["allowed"])
        self.assertFalse(has_scope_role(user=self.user, scope_key="emails"))

    def test_future_active_apps_and_disabled_apps(self):
        scope = AccessScope.objects.create(key="future-app", name="Future", scope_type="app")
        for roles, dept in [(["portal-all-apps"], "ETCH"), (["portal-all-apps"], "OTHER"), (["portal-admin"], "OTHER")]:
            self.bind(dept=dept, roles=roles)
            self.assertTrue(get_access_payload(user=self.user, scope_key=scope.key)["allowed"])
        scope.is_active = False; scope.save()
        self.assertFalse(get_access_payload(user=self.user, scope_key=scope.key)["allowed"])
        self.assertFalse(get_access_payload(user=self.user, scope_key="unknown")["allowed"])

    def test_sdwt_grades_and_exact_names(self):
        for grade, capabilities in [("viewer", ["read"]), ("user", ["read", "write"]), ("admin", ["read", "write", "delete"])]:
            self.bind(roles=["emails-user"], groups=[f"/SDWT-A/{grade}"])
            for capability in ("read", "write", "delete"):
                self.assertEqual(has_sdwt_capability(user=self.user, user_sdwt_prod="SDWT-A", capability=capability), capability in capabilities)
            self.assertFalse(has_sdwt_capability(user=self.user, user_sdwt_prod="sdwt-a", capability="read"))

    def test_strongest_grade_and_unrecognized_groups(self):
        self.bind(roles=["emails-user"], groups=["/SDWT-A/viewer", "/SDWT-A/admin", "/SDWT-B/root", "/headlamp-admins", "/A/B/admin"])
        self.assertEqual(dict(get_authorization_context(user=self.user).sdwt_roles), {"SDWT-A": "admin"})

    def test_group_alone_does_not_open_app(self):
        self.bind(groups=["/SDWT-A/admin"])
        self.assertFalse(get_access_payload(user=self.user)["allowed"])
        self.assertFalse(get_effective_affiliation_scope(user=self.user, scope_key="emails")["allowed"])

    def test_app_admin_has_no_global_data_privilege(self):
        self.bind(roles=["emails-admin"], groups=["/SDWT-A/viewer"])
        self.assertTrue(has_scope_role(user=self.user, scope_key="emails"))
        self.assertTrue(has_scope_role(user=self.user, scope_key="emails", required_role="user"))
        self.assertFalse(has_sdwt_capability(user=self.user, user_sdwt_prod="SDWT-A", capability="delete"))
        self.assertFalse(get_effective_affiliation_scope(user=self.user, scope_key="emails")["all"])

    def test_portal_admin_all_data_without_catalog(self):
        self.bind(roles=["portal-admin"])
        self.assertTrue(get_effective_affiliation_scope(user=self.user, scope_key="emails")["all"])
        self.assertTrue(has_sdwt_capability(user=self.user, user_sdwt_prod="UNSEEN-SDWT", capability="delete"))

    def test_database_permissions_and_staff_do_not_grant_access(self):
        self.user.is_staff = self.user.is_superuser = True
        self.user.save()
        scope = AccessScope.objects.get(key="emails")
        UserAccess.objects.create(user=self.user, scope=scope, status="allowed", role="admin")
        AccessPolicyRule.objects.create(scope=scope, rule_type="department", value="OTHER")
        self.bind()
        self.assertFalse(get_access_payload(user=self.user, scope_key="emails")["allowed"])
        self.assertFalse(get_authorization_context(user=User.objects.get(pk=self.user.pk)).portal_admin)

    def test_other_clients_and_realm_roles_do_not_grant_access(self):
        snapshot = build_authorization_snapshot({"userid": self.user.avatarid,
            "resource_access": {"other": {"roles": ["portal-admin"]}},
            "realm_access": {"roles": ["portal-admin"]}})
        bind_authorization_context(user=self.user, snapshot=snapshot)
        self.assertFalse(get_access_payload(user=self.user)["allowed"])

    def test_invalid_claim_types_fail(self):
        for bad in [{"groups": "admin"}, {"groups": [1]}, {"resource_access": []}, {"deptid": ["ETCH"]}]:
            with self.assertRaises(ValueError):
                build_authorization_snapshot({"userid": "9001", **bad})

    def test_wrong_user_and_inactive_user_fail_closed(self):
        snapshot = self.bind(roles=["portal-admin"])
        other = User.objects.create_user(sabun="1002", avatarid="9002")
        bind_authorization_context(user=other, snapshot=snapshot)
        self.assertFalse(get_access_payload(user=other)["allowed"])
        self.user.is_active = False
        self.assertFalse(get_access_payload(user=self.user)["allowed"])

    def test_context_is_per_session_and_explicit_for_reloaded_user(self):
        first = self.bind(roles=["emails-user"], groups=["/SDWT-A/viewer"])
        context = get_authorization_context(user=self.user)
        second_user = User.objects.get(pk=self.user.pk)
        self.bind(user=second_user, roles=[])
        self.assertTrue(get_access_payload(user=self.user, scope_key="emails")["allowed"])
        self.assertFalse(get_access_payload(user=second_user, scope_key="emails")["allowed"])
        reloaded = User.objects.get(pk=self.user.pk)
        self.assertFalse(get_access_payload(user=reloaded, scope_key="emails")["allowed"])
        self.assertTrue(get_access_payload(user=reloaded, scope_key="emails", context=context)["allowed"])
        bind_authorization_context(user=second_user, snapshot=first)
        self.assertFalse(get_authorization_context(user=second_user).all_apps)

    def test_identity_matches_epid_and_preserves_primary_key(self):
        identity = {"avatarid": "9001", "username": "Updated", "identity_profile": {"user_sdwt_prod": "SDWT-A", "line_id": "L1"}}
        user, created = upsert_user_identity(identity=identity, sabun="1001", knox_id="test.user")
        self.assertFalse(created); self.assertEqual(user.pk, self.user.pk)
        self.assertEqual(user.identity_profile["user_sdwt_prod"], "SDWT-A")

    def test_identity_never_links_by_sabun(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            upsert_user_identity(identity={"avatarid": "DIFFERENT"}, sabun="1001", knox_id="test.user")
        self.user.refresh_from_db()
        self.assertEqual(self.user.avatarid, "9001")

    def test_manager_requires_explicit_epid(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(sabun="1234")

    def test_unknown_admin_role_does_not_open_unmanaged_app(self):
        self.bind(roles=["assistant-admin"])
        self.assertFalse(get_access_payload(user=self.user, scope_key="assistant")["allowed"])

    def test_missing_optional_claims_clear_previous_profile(self):
        self.user.department = "OLD"
        self.user.email = "old@example.com"
        self.user.save()
        updated, _ = upsert_user_identity(identity={"avatarid": self.user.avatarid, "department": None, "email": None}, sabun=self.user.sabun, knox_id=self.user.knox_id)
        self.assertIsNone(updated.department)
        self.assertEqual(updated.email, "")

    def test_department_and_legacy_internal_flag_never_grant_access(self):
        for dept in ("ETCH", "OTHER", ""):
            snapshot = self.bind(dept=dept, groups=["/portal-members", "/SDWT-A/admin"])
            snapshot["internal"] = True
            bind_authorization_context(user=self.user, snapshot=snapshot)
            self.assertFalse(get_access_payload(user=self.user)["allowed"])
            self.assertFalse(get_access_payload(user=self.user, scope_key="emails")["allowed"])
            self.assertFalse(get_authorization_context(user=self.user).all_apps)

    def test_standard_role_is_independent_of_department_and_group_name(self):
        for dept in ("ETCH", "OTHER", ""):
            self.bind(dept=dept, roles=["portal-all-apps"])
            self.assertTrue(get_access_payload(user=self.user, scope_key="emails")["allowed"])
            self.assertFalse(get_effective_affiliation_scope(user=self.user, scope_key="emails")["all"])
