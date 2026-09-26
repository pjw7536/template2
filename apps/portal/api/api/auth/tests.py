"""유지되는 인증 HTTP·클레임 계약을 검증합니다. Keycloak 흐름은 전용 테스트에서 검증합니다."""
from __future__ import annotations
import base64
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test.utils import override_settings
from django.utils import timezone
from django.urls import reverse
import api.account.services as account_services
from api.account import selectors as account_selectors
from api.auth.services.oidc import _extract_user_info_from_claims, _upsert_user_from_claims
from api.common.permissions import (
    is_portal_access_protected_path,
    resolve_api_route_access_policy,
    resolve_app_access_scope_for_path,
)

class AuthContractTests(TestCase):
    def test_auth_me_requires_login(self) -> None:
        """미인증 요청은 401을 반환해야 합니다."""
        response = self.client.get(reverse("auth-me"))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "authentication_required")

    def test_login_rejects_removed_next_query(self) -> None:
        """로그인 시작 endpoint는 제거된 next 별칭을 명시적으로 거절합니다."""

        response = self.client.get(reverse("auth-login"), {"next": "/account"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "invalid_request")
        self.assertEqual(response.json()["fieldErrors"]["unexpectedFields"], ["next"])

    def test_frontend_redirect_rejects_removed_next_query(self) -> None:
        """프론트 redirect 보조 endpoint도 target만 허용합니다."""

        response = self.client.get(reverse("frontend-redirect"), {"next": "/account"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["fieldErrors"]["unexpectedFields"], ["next"])

    @override_settings(OIDC_PROVIDER_CONFIGURED=False)
    def test_auth_login_returns_bad_request_when_not_configured(self) -> None:
        """OIDC 설정이 비활성화되면 login이 canonical 503을 반환해야 합니다."""
        response = self.client.get(reverse("auth-login"))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "external_dependency_error")

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

    def test_app_api_path_mapping_covers_internal_app_endpoints(self) -> None:
        """내부 앱 API 경로가 올바른 app scope로 매핑되어야 합니다."""

        cases = {
            "/api/v1/appstore/apps": "appstore",
            "/api/v1/line-dashboard/summary": "line-dashboard",
            "/api/v1/l3_spider/meta": "l3-spider",
            "/api/v1/pm_spider/meta": "pm-spider",
            "/api/v1/tttm_spider/combo/options": "tttm-spider",
            "/api/v1/assistant/turns/stream": "assistant",
            "/api/v1/observer/lines": "observer",
            "/api/v1/emails/inbox/": "emails",
            "/api/v1/l0_spider/hard-spec/meta": "l0-spider",
            "/api/v1/fdc-trend/hard-spec/meta": "l0-spider",
            "/api/v1/voc/posts": "voc",
            "/api/v1/activity/app-access-stats": "access-stats",
        }
        for path, expected_scope in cases.items():
            with self.subTest(path=path):
                self.assertEqual(resolve_app_access_scope_for_path(path), expected_scope)

        self.assertIsNone(resolve_app_access_scope_for_path("/api/v1/activity/app-access"))

    def test_api_route_registry_drives_runtime_access_policy(self) -> None:
        """루트 registry와 하위 override가 런타임 권한 판정의 단일 기준이어야 합니다."""

        cases = {
            "/api/v1/auth/me": "public",
            "/api/v1/data-movement/m_tkin_prevent/load": "token",
            "/api/v1/account/overview": "portal",
            "/api/v1/appstore/apps": "app:appstore",
            "/api/v1/tttm_spider/dashboard/data": "app:tttm-spider",
            "/api/v1/activity/app-access": "portal",
            "/api/v1/activity/app-access-stats": "app:access-stats",
        }
        for path, expected_policy in cases.items():
            with self.subTest(path=path):
                self.assertEqual(resolve_api_route_access_policy(path), expected_policy)

        self.assertIsNone(resolve_api_route_access_policy("/api/v1/unknown/items"))
        self.assertFalse(is_portal_access_protected_path("/api/v1/data-movement/jobs"))
        self.assertTrue(is_portal_access_protected_path("/api/v1/appstore/apps"))
        self.assertTrue(is_portal_access_protected_path("/api/v1/unknown/items"))

    def test_extract_user_info_maps_avatarid(self) -> None:
        """userid 클레임이 avatarid 필드로 매핑되어야 합니다."""
        claims = {
            "loginid": "KNOX-123",
            "sabun": "S12345",
            "username": "홍길동",
            "mail": "hong@example.com",
            "userid": "U-12345",
        }

        info = _extract_user_info_from_claims(claims)

        self.assertEqual(info.get("avatarid"), "U-12345")

    def test_extract_user_info_maps_loginid_to_knox_id(self) -> None:
        """loginid가 knox_id로 매핑되는지 확인합니다."""
        claims = {
            "loginid": "knox-user",
            "sabun": "12345",
            "username": "홍길동",
            "deptname": "Engineering",
            "mail": "user@example.com",
        }

        info = _extract_user_info_from_claims(claims)
        self.assertEqual(info["knox_id"], "knox-user")
        self.assertEqual(info["sabun"], "12345")
        self.assertEqual(info["department"], "Engineering")
        self.assertEqual(info["email"], "user@example.com")

    def test_extract_user_info_sets_korean_and_english_names(self) -> None:
        """한글/영문 이름 필드가 기대대로 채워지는지 확인합니다."""
        claims = {
            "loginid": "knox-user",
            "sabun": "12345",
            "username": "홍길동",
            "givenname": "John",
            "surname": "Doe",
        }

        info = _extract_user_info_from_claims(claims)
        self.assertEqual(info["first_name"], "길동")
        self.assertEqual(info["last_name"], "홍")
        self.assertEqual(info["givenname"], "John")
        self.assertEqual(info["surname"], "Doe")
