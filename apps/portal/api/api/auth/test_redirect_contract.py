"""Auth redirect target 허용·차단 행렬 회귀 테스트입니다."""

from __future__ import annotations

from django.test import RequestFactory, SimpleTestCase, override_settings

from .services.oidc_validation import resolve_safe_redirect_target


@override_settings(
    FRONTEND_BASE_URL="https://portal.example.com",
    ALLOWED_REDIRECT_HOSTS=["portal.example.com"],
    DJANGO_SECURE=True,
    DEBUG=False,
)
class AuthRedirectContractTests(SimpleTestCase):
    """same-origin 상대·절대 target만 최종 redirect로 사용합니다."""

    def setUp(self) -> None:
        """redirect 해석에 사용할 요청을 준비합니다."""

        self.request = RequestFactory().get("/api/v1/auth/login")

    def test_relative_and_same_origin_targets_are_allowed(self) -> None:
        """상대 경로와 설정된 frontend origin은 그대로 보존합니다."""

        self.assertEqual(
            resolve_safe_redirect_target("/settings/account?tab=profile", self.request),
            "https://portal.example.com/settings/account?tab=profile",
        )
        self.assertEqual(
            resolve_safe_redirect_target(
                "https://portal.example.com/settings/account",
                self.request,
            ),
            "https://portal.example.com/settings/account",
        )

    def test_external_and_scheme_relative_targets_fall_back(self) -> None:
        """외부 origin과 scheme-relative 입력은 frontend 기본 URL로 제한합니다."""

        self.assertEqual(
            resolve_safe_redirect_target("https://evil.example/account", self.request),
            "https://portal.example.com",
        )
        self.assertEqual(
            resolve_safe_redirect_target("//evil.example/account", self.request),
            "https://portal.example.com",
        )
