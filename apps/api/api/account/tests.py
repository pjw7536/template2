"""Keycloak 전환 후 Account shadow 사용자와 읽기 전용 표면을 검증합니다."""

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import NoReverseMatch, reverse

from api.account.models import Affiliation
from api.account.services import get_access_payload


class ShadowAccountTests(TestCase):
    """shadow User 저장, 권한 판정과 읽기 전용 API를 검증합니다."""

    def setUp(self) -> None:
        """기본 소속과 Portal 역할이 있는 Keycloak shadow 사용자를 만듭니다."""

        User = get_user_model()
        self.user = User.objects.create_user(
            sabun="KC-ACCOUNT-1",
            knox_id="keycloak.account",
            email="keycloak.account@example.com",
            username="Keycloak Account",
            keycloak_subject="subject-account-1",
            keycloak_group_id="group-alpha",
            keycloak_groups=["/affiliations/ALPHA/member"],
            keycloak_client_roles={
                "portal": ["portal-user", "emails-user"],
            },
            affiliation_snapshot={
                "department": "ETCH",
                "line": "L1",
                "name": "ALPHA",
                "user_sdwt_prod": "ALPHA",
                "role": "member",
            },
        )
        self.client.force_login(self.user)

    def test_keycloak_subject_is_unique(self) -> None:
        """서로 다른 shadow User가 같은 Keycloak subject를 사용할 수 없습니다."""

        User = get_user_model()
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user(
                sabun="KC-ACCOUNT-2",
                keycloak_subject="subject-account-1",
            )

    def test_user_pool_reads_affiliation_snapshot(self) -> None:
        """사용자 pool은 legacy 소속 FK 없이 Keycloak snapshot을 반환합니다."""

        response = self.client.get(reverse("account-users"), {"search": "keycloak.account"})

        self.assertEqual(response.status_code, 200)
        row = response.json()["results"][0]
        self.assertEqual(row["userSdwtProd"], "ALPHA")
        self.assertEqual(row["department"], "ETCH")
        self.assertEqual(row["line"], "L1")

    def test_line_options_include_shadow_affiliation(self) -> None:
        """업무 화면 호환 옵션은 shadow 소속 snapshot도 포함합니다."""

        response = self.client.get(reverse("account-line-sdwt-options"))

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            {"lineId": "L1", "userSdwtProds": ["ALPHA"]},
            response.json()["lines"],
        )

    def test_removed_write_routes_are_not_registered(self) -> None:
        """신청·승인·정책·감사 쓰기 route 이름을 더 이상 공개하지 않습니다."""

        for route_name in (
            "account-affiliation",
            "account-access-request",
            "account-access-policy-rules",
            "account-access-audit-logs",
        ):
            with self.assertRaises(NoReverseMatch):
                reverse(route_name)

    def test_django_superuser_does_not_bypass_portal_role(self) -> None:
        """Keycloak 역할이 없는 Django superuser를 Portal 관리자로 취급하지 않습니다."""

        User = get_user_model()
        superuser = User.objects.create_superuser(
            sabun="LEGACY-SUPERUSER",
            password="password",
        )

        payload = get_access_payload(user=superuser, scope_key="portal")

        self.assertFalse(payload["allowed"])

    def test_only_shadow_user_is_registered_in_account_admin(self) -> None:
        """Account admin에는 shadow User만 남기고 legacy 모델을 노출하지 않습니다."""

        User = get_user_model()
        account_models = {
            model
            for model in admin.site._registry
            if model._meta.app_label == "account"
        }

        self.assertEqual(account_models, {User})
        self.assertNotIn(Affiliation, account_models)
