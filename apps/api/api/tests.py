from __future__ import annotations

from django.test import SimpleTestCase

from api.auth.oidc import _extract_user_info_from_claims


class OidcClaimExtractionTests(SimpleTestCase):
    """OIDC 클레임에서 사용자 정보 추출 로직을 검증합니다."""

    def test_extract_user_info_maps_loginid_to_knox_id(self) -> None:
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
        self.assertEqual(info["deptname"], "Engineering")
        self.assertEqual(info["mail"], "user@example.com")

    def test_extract_user_info_prefers_givenname_surname(self) -> None:
        claims = {
            "loginid": "knox-user",
            "sabun": "12345",
            "givenname": "John",
            "surname": "Doe",
            "deptname": "Engineering",
            "mail": "user@example.com",
        }

        info = _extract_user_info_from_claims(claims)
        self.assertEqual(info["first_name"], "John")
        self.assertEqual(info["last_name"], "Doe")
