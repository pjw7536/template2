# =============================================================================
# 모듈 설명: 인증(Auth) 기능 테스트를 제공합니다.
# - 주요 대상: /auth/me, /auth/login, /auth/logout, /auth/config, 프론트 리다이렉트
# - 불변 조건: URL 네임은 auth-* 네임스페이스로 등록되어 있어야 합니다.
# =============================================================================

"""인증(Auth) 기능 관련 테스트 모음.

- 주요 대상: /auth/me, /auth/login, /auth/logout, /auth/config, 프론트 리다이렉트
- 주요 엔드포인트/클래스: AuthMeTests, AuthEndpointTests
- 가정/불변 조건: URL 네임은 auth-* 네임스페이스로 등록됨
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test.utils import override_settings
from django.utils import timezone
from django.urls import reverse

from api.account.models import UserSdwtProdChange


class AuthMeTests(TestCase):
    """auth_me 응답의 인증/필드 구성을 검증합니다."""

    def test_auth_me_requires_login(self) -> None:
        """미인증 요청은 401을 반환해야 합니다."""
        response = self.client.get(reverse("auth-me"))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"detail": "unauthorized"})

    def test_auth_me_returns_username_and_knox_id(self) -> None:
        """인증된 사용자의 username/knox_id가 응답에 포함되어야 합니다."""
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
        """pending_user_sdwt_prod 값이 있을 때 응답에 포함되어야 합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자/대기 변경 요청 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        user = User.objects.create_user(sabun="S12346", password="test-password")
        user.knox_id = "KNOX-12346"
        user.save(update_fields=["knox_id"])
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

        # -----------------------------------------------------------------------------
        # 2) 로그인 및 API 호출
        # -----------------------------------------------------------------------------
        self.client.force_login(user)

        response = self.client.get(reverse("auth-me"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        # -----------------------------------------------------------------------------
        # 3) 응답 검증
        # -----------------------------------------------------------------------------
        self.assertEqual(payload["pending_user_sdwt_prod"], "group-pending")


class AuthEndpointTests(TestCase):
    """인증 엔드포인트의 기본 동작을 검증합니다."""

    @override_settings(OIDC_PROVIDER_CONFIGURED=False)
    def test_auth_login_returns_bad_request_when_not_configured(self) -> None:
        """OIDC 설정이 비활성화되면 login이 400을 반환해야 합니다."""
        response = self.client.get(reverse("auth-login"))
        self.assertEqual(response.status_code, 400)

    def test_auth_logout_returns_logout_url(self) -> None:
        """POST logout은 logoutUrl을 포함한 JSON을 반환해야 합니다."""
        response = self.client.post(reverse("auth-logout"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("logoutUrl", response.json())

    def test_auth_config_returns_fields(self) -> None:
        """auth_config 응답에 기본 필드가 포함되어야 합니다."""
        response = self.client.get(reverse("auth-config"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("clientId", payload)
        self.assertIn("loginUrl", payload)

    @override_settings(FRONTEND_BASE_URL="http://frontend.local")
    def test_frontend_redirect_uses_base_url(self) -> None:
        """프론트 리다이렉트는 설정된 베이스 URL을 사용해야 합니다."""
        response = self.client.get(reverse("frontend-redirect"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("http://frontend.local"))
