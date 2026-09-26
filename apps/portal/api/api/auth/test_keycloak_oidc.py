"""Keycloak code flow와 서명된 토큰·세션 계약을 검증합니다."""
import time
from unittest.mock import patch, Mock
from urllib.parse import urlparse, parse_qs

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from django.test import TestCase, override_settings
from django.urls import reverse

from api.account.services import AUTHORIZATION_SESSION_KEY
from .services import keycloak_oidc

KEYCLOAK_SETTINGS = {
    "OIDC_PROVIDER": "keycloak", "OIDC_PROVIDER_CONFIGURED": True,
    "OIDC_CLIENT_ID": "portal", "OIDC_CLIENT_SECRET": "test-secret",
    "OIDC_ISSUER": "https://sso.example/realms/portal",
    "OIDC_AUTH_URL": "https://sso.example/auth", "OIDC_LOGOUT_URL": "https://sso.example/logout",
    "OIDC_REDIRECT_URI": "https://portal.example/auth/keycloak/callback/",
    "OIDC_TOKEN_URL": "https://sso.example/token", "OIDC_JWKS_URL": "https://sso.example/certs",
    "FRONTEND_BASE_URL": "https://portal.example", "ALLOWED_REDIRECT_HOSTS": ["portal.example"],
}


@override_settings(**KEYCLOAK_SETTINGS)
class KeycloakFlowTests(TestCase):
    def start(self):
        response = self.client.get(reverse("auth-login"), {"target": "https://portal.example/emails"})
        self.assertEqual(response.status_code, 302)
        return parse_qs(urlparse(response.url).query)

    def claims(self, expected_nonce, **updates):
        return {"userid": "9001", "sabun": "1001", "loginid": "test.user", "nonce": expected_nonce,
                "resource_access": {"portal": {"roles": ["portal-all-apps"]}},
                "sub": "kc-1", "username": "테스트", "deptid": "ETCH", "groups": ["/SDWT-A/viewer"], **updates}

    def finish(self, params, claims=None):
        with patch.object(keycloak_oidc, "exchange_code", return_value={"id_token": "signed-token"}), patch.object(keycloak_oidc, "decode_id_token", return_value=claims or self.claims(params["nonce"][0])):
            return self.client.get(reverse("auth-keycloak-callback"), {"code": "one-time", "state": params["state"][0]})

    def test_login_uses_random_state_pkce_and_code(self):
        a = self.start(); b = self.start()
        self.assertNotEqual(a["state"], b["state"])
        self.assertEqual(b["response_type"], ["code"])
        self.assertEqual(b["code_challenge_method"], ["S256"])
        self.assertNotIn("portal.example", b["state"][0])

    def test_callback_me_and_logout(self):
        response = self.finish(self.start())
        self.assertEqual(response.url, "https://portal.example/emails")
        payload = self.client.get(reverse("auth-me")).json()
        self.assertEqual(payload["avatarId"], "9001")
        self.assertTrue(payload["hasAllAppsAccess"])
        self.assertFalse(payload["isPortalAdmin"])
        self.assertEqual(payload["sdwtAccess"], {"SDWT-A": "viewer"})
        self.assertTrue(payload["scopeAccess"]["emails"]["allowed"])
        self.assertIn(AUTHORIZATION_SESSION_KEY, self.client.session)
        response = self.client.post(reverse("auth-logout"))
        query = parse_qs(urlparse(response.json()["logoutUrl"]).query)
        self.assertEqual(query["id_token_hint"], ["signed-token"])
        self.assertNotIn(AUTHORIZATION_SESSION_KEY, self.client.session)

    def test_state_mismatch_never_exchanges_code(self):
        self.start()
        with patch.object(keycloak_oidc, "exchange_code") as exchange:
            response = self.client.get(reverse("auth-keycloak-callback"), {"code": "code", "state": "wrong"})
            exchange.assert_not_called()
        self.assertIn("invalid_state", response.url)

    def test_callback_is_single_use(self):
        params = self.start(); self.finish(params)
        self.assertIn("invalid_state", self.finish(params).url)

    def test_nonce_mismatch_missing_identity_and_epid_fallback(self):
        for update in [{"nonce": "wrong"}, {"userid": ""}, {"loginid": "", "preferred_username": "9001"}, {"sabun": ["1001"]}]:
            params = self.start()
            response = self.finish(params, self.claims(params["nonce"][0], **update))
            self.assertIn("error=", response.url)
            self.assertNotIn(AUTHORIZATION_SESSION_KEY, self.client.session)

    def test_cancel_consumes_login_transaction(self):
        params = self.start()
        response = self.client.get(reverse("auth-keycloak-callback"), {"error": "access_denied", "state": params["state"][0]})
        self.assertIn("login_cancelled", response.url)
        self.assertNotIn(keycloak_oidc.PKCE_SESSION_KEY, self.client.session)

    def test_network_failure_does_not_login(self):
        params = self.start()
        with patch.object(keycloak_oidc, "exchange_code", side_effect=keycloak_oidc.KeycloakOidcError()):
            response = self.client.get(reverse("auth-keycloak-callback"), {"code": "code", "state": params["state"][0]})
        self.assertIn("token_exchange_failed", response.url)
        self.assertNotIn(AUTHORIZATION_SESSION_KEY, self.client.session)

    def test_retired_write_endpoint(self):
        self.finish(self.start())
        response = self.client.post("/api/v1/account/access/request", data={})
        self.assertEqual(response.status_code, 410)
        self.assertIn("managed_by_keycloak", response.content.decode())

    def test_old_callback_and_post_are_not_supported(self):
        self.assertEqual(self.client.post("/auth/google/callback/").status_code, 404)
        self.assertEqual(self.client.post(reverse("auth-keycloak-callback")).status_code, 405)


@override_settings(**KEYCLOAK_SETTINGS)
class KeycloakSignedTokenTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def token(self, **updates):
        claims = {"iss": KEYCLOAK_SETTINGS["OIDC_ISSUER"], "aud": "portal", "sub": "kc-1",
                  "iat": int(time.time()), "exp": int(time.time()) + 60, "nonce": "nonce", **updates}
        return jwt.encode(claims, self.key, algorithm="RS256", headers={"kid": "key-1"})

    def decode(self, token):
        with patch.object(keycloak_oidc, "_jwks_client") as client:
            client.return_value.get_signing_key_from_jwt.return_value = Mock(key=self.key.public_key())
            return keycloak_oidc.decode_id_token(token)

    def test_valid_signed_token(self):
        self.assertEqual(self.decode(self.token())["sub"], "kc-1")

    def test_expired_wrong_issuer_audience_and_azp(self):
        for updates in [{"exp": 1}, {"iss": "https://other.example"}, {"aud": "other"}, {"azp": "other"}, {"aud": ["portal", "other"]}]:
            with self.assertRaises(jwt.PyJWTError):
                self.decode(self.token(**updates))

    def test_signature_is_required(self):
        other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        with self.assertRaises(jwt.PyJWTError):
            self.decode(jwt.encode({"sub": "fake"}, other, algorithm="RS256"))

@override_settings(**KEYCLOAK_SETTINGS)
class KeycloakSessionBoundaryTests(TestCase):
    """동일 사용자 여러 세션과 로컬 관리자 인증의 경계를 검증합니다."""

    start = KeycloakFlowTests.start
    claims = KeycloakFlowTests.claims
    finish = KeycloakFlowTests.finish

    def test_relogin_does_not_change_another_session_permissions(self):
        from django.test import Client
        original_client = self.client
        self.finish(self.start())
        self.client = Client()
        params = self.start()
        self.finish(params, self.claims(params["nonce"][0], deptid="OTHER", groups=[], resource_access={}))
        self.assertFalse(self.client.get(reverse("auth-me")).json()["scopeAccess"]["emails"]["allowed"])
        self.assertTrue(original_client.get(reverse("auth-me")).json()["scopeAccess"]["emails"]["allowed"])

    def test_local_superuser_and_basic_auth_cannot_access_business_api(self):
        import base64
        from django.contrib.auth import get_user_model
        user = get_user_model().objects.create_superuser(avatarid="emergency", sabun="emergency", password="local-only", knox_id="emergency")
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("emails-inbox")).status_code, 403)
        self.client.logout()
        header = "Basic " + base64.b64encode(b"emergency:local-only").decode()
        self.assertEqual(self.client.get(reverse("emails-inbox"), HTTP_AUTHORIZATION=header).status_code, 401)
