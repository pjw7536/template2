"""Keycloak 조회와 종료된 account 변경 API의 HTTP 계약을 검증합니다."""
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import User
from .services import AUTHORIZATION_SESSION_KEY, build_authorization_snapshot


@override_settings(OIDC_CLIENT_ID="portal")
class AccountHttpContractTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(avatarid="9001", sabun="1001", knox_id="test.user")
        self.client.force_login(self.user)
        session = self.client.session
        session[AUTHORIZATION_SESSION_KEY] = build_authorization_snapshot({"userid": "9001", "deptid": "ETCH",
            "resource_access": {"portal": {"roles": ["portal-all-apps"]}},
            "user_sdwt_prod": "SDWT-A", "line_id": "L1", "groups": ["/SDWT-A/viewer"]})
        session.save()

    def test_retired_mutations_return_410(self):
        routes = ["account-affiliation", "account-affiliation-approve", "account-affiliation-reconfirm",
                  "account-access-request", "account-access-policy-rules", "account-pending-access-requests-bulk-approve",
                  "account-external-affiliation-sync", "account-affiliation-access"]
        for route in routes:
            with self.subTest(route=route):
                response = self.client.post(reverse(route), data={"anything": "ignored"})
                self.assertEqual(response.status_code, 410)
                self.assertEqual(response.json()["code"], "managed_by_keycloak")

    def test_overview_uses_session_not_organization_catalog(self):
        response = self.client.get(reverse("account-overview"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["hasAllAppsAccess"])
        self.assertNotIn("isInternalMember", response.json())
        self.assertEqual(response.json()["userSdwtProd"], "SDWT-A")
        self.assertEqual(response.json()["sdwtAccess"], {"SDWT-A": "viewer"})

    def test_line_options_only_expose_known_line_and_accessible_sdwts(self):
        response = self.client.get(reverse("account-line-sdwt-options"))
        self.assertEqual(response.json(), {"lines": [{"lineId": "L1", "userSdwtProds": ["SDWT-A"]}], "userSdwtProds": ["SDWT-A"]})

    def test_user_pool_only_includes_logged_in_users(self):
        User.objects.create_user(avatarid="9002", sabun="1002", knox_id="not.logged.in")
        response = self.client.get(reverse("account-users"))
        self.assertEqual([r["userId"] for r in response.json()["results"]], [self.user.pk])
