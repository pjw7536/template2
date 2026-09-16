# =============================================================================
# 모듈 설명: Keycloak 로그인 전용 OIDC 계약을 검증합니다.
# - 주요 대상: code+PKCE authorize, callback, JWKS 검증, logout
# - 불변 조건: Keycloak 로그인 후에도 Portal 권한 원천은 Django에 유지됩니다.
# =============================================================================

"""Keycloak login-only OIDC 흐름의 회귀 테스트입니다."""

from __future__ import annotations

from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from api.auth.services import keycloak_oidc


KEYCLOAK_SETTINGS = {
    "OIDC_PROVIDER": "keycloak",
    "OIDC_PROVIDER_CONFIGURED": True,
    "OIDC_CLIENT_ID": "portal",
    "OIDC_CLIENT_SECRET": "portal-local-secret",
    "OIDC_ISSUER": "http://localhost:8180/realms/portal",
    "OIDC_REDIRECT_URI": "http://localhost:8080/auth/keycloak/callback/",
    "OIDC_TOKEN_URL": "http://keycloak:8080/realms/portal/protocol/openid-connect/token",
    "OIDC_JWKS_URL": "http://keycloak:8080/realms/portal/protocol/openid-connect/certs",
    "ADFS_AUTH_URL": "http://localhost:8180/realms/portal/protocol/openid-connect/auth",
    "ADFS_LOGOUT_URL": "http://localhost:8180/realms/portal/protocol/openid-connect/logout",
    "FRONTEND_BASE_URL": "http://localhost:8080",
    "ALLOWED_REDIRECT_HOSTS": {"localhost:8080"},
}


@override_settings(**KEYCLOAK_SETTINGS)
class KeycloakOidcFlowTests(TestCase):
    """Keycloak browser/API 로그인 경계를 검증합니다."""

    def test_login_uses_authorization_code_and_pkce(self) -> None:
        """로그인 시작은 code flow와 S256 PKCE를 사용해야 합니다."""

        response = self.client.get(reverse("auth-login"), {"target": "/account"})

        self.assertEqual(response.status_code, 302)
        query = parse_qs(urlparse(response["Location"]).query)
        self.assertEqual(query["response_type"], ["code"])
        self.assertEqual(query["response_mode"], ["query"])
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertTrue(query["code_challenge"][0])
        self.assertTrue(self.client.session.get(keycloak_oidc.PKCE_SESSION_KEY))

    @patch("api.auth.services.keycloak_oidc.decode_id_token")
    @patch("api.auth.services.keycloak_oidc.exchange_code")
    def test_callback_logs_in_with_existing_django_permission_model(
        self,
        exchange_code: Mock,
        decode_id_token: Mock,
    ) -> None:
        """검증된 Keycloak identity는 기존 Django 사용자로만 저장되어야 합니다."""

        login_response = self.client.get(reverse("auth-login"))
        self.assertEqual(login_response.status_code, 302)
        nonce = self.client.session["oidc_nonce"]
        state = parse_qs(urlparse(login_response["Location"]).query)["state"][0]
        exchange_code.return_value = {"id_token": "signed-keycloak-id-token"}
        decode_id_token.return_value = {
            "sub": "keycloak-user-id",
            "sabun": "S000001",
            "preferred_username": "dummy.user",
            "name": "Dummy User",
            "given_name": "Dummy",
            "family_name": "User",
            "email": "dummy.user@example.com",
            "nonce": nonce,
        }

        response = self.client.get(
            reverse("auth-keycloak-callback"),
            {"code": "one-time-code", "state": state},
        )

        self.assertEqual(response.status_code, 302)
        user = get_user_model().objects.get(sabun="S000001")
        self.assertEqual(user.knox_id, "dummy.user")
        self.assertEqual(user.email, "dummy.user@example.com")
        self.assertFalse(user.is_superuser)
        self.assertEqual(
            self.client.session[keycloak_oidc.ID_TOKEN_SESSION_KEY],
            "signed-keycloak-id-token",
        )
        exchange_code.assert_called_once()

    def test_callback_requires_code_and_state(self) -> None:
        """Keycloak callback은 code와 state 누락을 canonical 오류로 반환해야 합니다."""

        response = self.client.get(reverse("auth-keycloak-callback"))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(sorted(response.json()["fieldErrors"]), ["code", "state"])

    def test_logout_includes_id_token_hint_and_safe_redirect(self) -> None:
        """Keycloak logout은 SSO 세션과 Portal 복귀 주소를 함께 전달해야 합니다."""

        session = self.client.session
        session[keycloak_oidc.ID_TOKEN_SESSION_KEY] = "stored-id-token"
        session.save()

        response = self.client.post(reverse("auth-logout"))

        self.assertEqual(response.status_code, 200)
        query = parse_qs(urlparse(response.json()["logoutUrl"]).query)
        self.assertEqual(query["client_id"], ["portal"])
        self.assertEqual(query["id_token_hint"], ["stored-id-token"])
        self.assertEqual(query["post_logout_redirect_uri"], ["http://localhost:8080"])


@override_settings(**KEYCLOAK_SETTINGS)
class KeycloakJwksValidationTests(TestCase):
    """Keycloak JWKS 검증 옵션을 고정합니다."""

    @patch("api.auth.services.keycloak_oidc.jwt.decode")
    @patch("api.auth.services.keycloak_oidc.jwt.PyJWKClient")
    def test_decode_requires_signature_issuer_audience_and_time_claims(
        self,
        jwks_client_class: Mock,
        jwt_decode: Mock,
    ) -> None:
        """JWKS decode는 운영 보안 검증 항목을 비활성화하지 않아야 합니다."""

        signing_key = Mock()
        signing_key.key = "public-key"
        jwks_client_class.return_value.get_signing_key_from_jwt.return_value = signing_key
        jwt_decode.return_value = {"sub": "user-id"}

        result = keycloak_oidc.decode_id_token("signed-token")

        self.assertEqual(result, {"sub": "user-id"})
        _, kwargs = jwt_decode.call_args
        self.assertEqual(kwargs["audience"], "portal")
        self.assertEqual(kwargs["issuer"], KEYCLOAK_SETTINGS["OIDC_ISSUER"])
        self.assertEqual(kwargs["algorithms"], ["RS256"])
        self.assertEqual(
            kwargs["options"]["require"],
            ["exp", "iat", "iss", "sub"],
        )
