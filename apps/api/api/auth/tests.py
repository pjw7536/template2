from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test.utils import override_settings
from django.utils import timezone
from django.urls import reverse

from api.account.models import UserSdwtProdChange


class AuthMeTests(TestCase):
    def test_auth_me_requires_login(self) -> None:
        response = self.client.get(reverse("auth-me"))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"detail": "unauthorized"})

    def test_auth_me_returns_username_and_knox_id(self) -> None:
        User = get_user_model()
        user = User.objects.create_user(sabun="S12345", password="test-password")
        user.knox_id = "KNOX-12345"
        user.username = "홍길동"
        user.first_name = "John"
        user.last_name = "Doe"
        user.email = "hong@example.com"
        user.save(update_fields=["knox_id", "username", "first_name", "last_name", "email"])

        self.client.force_login(user)

        response = self.client.get(reverse("auth-me"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual(payload["usr_id"], "KNOX-12345")
        self.assertEqual(payload["username"], "홍길동")
        self.assertNotIn("name", payload)
        self.assertEqual(payload["email"], "hong@example.com")

    def test_auth_me_includes_pending_user_sdwt_prod(self) -> None:
        User = get_user_model()
        user = User.objects.create_user(sabun="S12346", password="test-password")
        UserSdwtProdChange.objects.create(
            user=user,
            department="Dept",
            line="Line",
            from_user_sdwt_prod=None,
            to_user_sdwt_prod="group-pending",
            effective_from=timezone.now(),
            status=UserSdwtProdChange.Status.PENDING,
            applied=False,
            approved=False,
            created_by=user,
        )

        self.client.force_login(user)

        response = self.client.get(reverse("auth-me"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual(payload["pending_user_sdwt_prod"], "group-pending")


class AuthEndpointTests(TestCase):
    @override_settings(OIDC_PROVIDER_CONFIGURED=False)
    def test_auth_login_returns_bad_request_when_not_configured(self) -> None:
        response = self.client.get(reverse("auth-login"))
        self.assertEqual(response.status_code, 400)

    def test_auth_logout_returns_logout_url(self) -> None:
        response = self.client.post(reverse("auth-logout"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("logoutUrl", response.json())

    def test_auth_config_returns_fields(self) -> None:
        response = self.client.get(reverse("auth-config"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("clientId", payload)
        self.assertIn("loginUrl", payload)

    @override_settings(FRONTEND_BASE_URL="http://frontend.local")
    def test_frontend_redirect_uses_base_url(self) -> None:
        response = self.client.get(reverse("frontend-redirect"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("http://frontend.local"))
