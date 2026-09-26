"""명시적으로 준비한 임시 Keycloak에서 실제 code+PKCE·JWKS를 검증합니다."""
import html
import os
import re
from urllib.parse import urlparse, parse_qs
from unittest import skipUnless

import requests
from django.test import TestCase, override_settings


@skipUnless(os.environ.get("PORTAL_LIVE_KEYCLOAK_URL"), "임시 Keycloak 통합 테스트 환경이 필요합니다.")
@override_settings(
    OIDC_PROVIDER_CONFIGURED=True, OIDC_CLIENT_ID="portal", OIDC_CLIENT_SECRET="portal-local-secret",
    OIDC_ISSUER="http://localhost:18180/realms/portal",
    OIDC_AUTH_URL="http://localhost:18180/realms/portal/protocol/openid-connect/auth",
    OIDC_LOGOUT_URL="http://localhost:18180/realms/portal/protocol/openid-connect/logout",
    OIDC_REDIRECT_URI="http://localhost:8080/auth/keycloak/callback/",
    FRONTEND_BASE_URL="http://localhost:8080", ALLOWED_REDIRECT_HOSTS=["localhost:8080"],
    DJANGO_SECURE=False,
)
class KeycloakLiveTests(TestCase):
    def test_real_login_roles_claims_and_logout(self):
        internal = os.environ["PORTAL_LIVE_KEYCLOAK_URL"].rstrip("/")
        protocol = internal + "/realms/portal/protocol/openid-connect"
        for epid, email_access, assistant_access, admin in [
            ("90000001", True, True, False), ("90000002", True, False, False),
            ("90000003", True, True, False), ("90000004", True, True, True),
            ("90000005", False, False, False),
        ]:
            with self.subTest(epid=epid), self.settings(OIDC_TOKEN_URL=protocol+"/token", OIDC_JWKS_URL=protocol+"/certs"):
                self.client.logout()
                start = self.client.get("/api/v1/auth/login")
                self.assertEqual(start.status_code, 302)
                browser = requests.Session()
                page = browser.get(start.url.replace("http://localhost:18180", internal), timeout=15)
                action = re.search(r'<form[^>]+action="([^"]+)"', page.text)
                self.assertIsNotNone(action, page.text[:200])
                response = browser.post(html.unescape(action.group(1)).replace("http://localhost:18180", internal),
                    data={"username": epid, "password": "dummy-user-change-me", "credentialId": ""},
                    allow_redirects=False, timeout=15)
                self.assertEqual(response.status_code, 302, response.text[:200])
                callback = urlparse(response.headers["Location"])
                self.assertIn("code", parse_qs(callback.query))
                completed = self.client.get(callback.path + "?" + callback.query)
                self.assertEqual(completed.status_code, 302)
                self.assertNotIn("error=", completed.url)
                me = self.client.get("/api/v1/auth/me").json()
                self.assertEqual(me["avatarId"], epid)
                self.assertTrue(me["knoxId"])
                self.assertNotEqual(me["knoxId"], epid)
                self.assertEqual(me["scopeAccess"]["emails"]["allowed"], email_access)
                self.assertEqual(me["scopeAccess"]["assistant"]["allowed"], assistant_access)
                self.assertEqual(me["isPortalAdmin"], admin)
                end = self.client.post("/api/v1/auth/logout").json()["logoutUrl"]
                response = browser.get(end.replace("http://localhost:18180", internal), allow_redirects=False, timeout=15)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.headers["Location"].rstrip("/"), "http://localhost:8080")
