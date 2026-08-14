"""Keycloak 세션 refresh와 shadow 사용자 갱신 계약을 검증합니다."""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from api.auth.services.oidc import auth_me


class KeycloakSessionRefreshTests(SimpleTestCase):
    """5분 token 갱신 뒤 최신 역할 snapshot 반영을 검증합니다."""

    @patch("api.auth.services.oidc.auth_selectors.get_current_user_payload")
    @patch("api.auth.services.oidc.upsert_user_from_keycloak_identity")
    @patch("api.auth.services.oidc.identity_from_claims")
    @patch("api.auth.services.oidc.decode_id_token")
    @patch("api.auth.services.oidc.refresh_session_if_needed")
    def test_auth_me_syncs_shadow_user_from_current_access_token(
        self,
        refresh_session,
        decode_token,
        identity_from_claims,
        upsert_user,
        get_payload,
    ):
        """현재 access token의 group/client role을 shadow User에 다시 저장합니다."""

        request = SimpleNamespace()
        original_user = SimpleNamespace(keycloak_subject="subject-old")
        refreshed_user = SimpleNamespace(keycloak_subject="subject-new")
        refresh_session.return_value = {
            "id_token": "signed-id-token",
            "access_token": "signed-access-token",
        }
        decode_token.side_effect = [
            {"sub": "subject-new"},
            {"groups": ["/affiliations/ALPHA/member"]},
        ]
        identity_from_claims.return_value = SimpleNamespace(subject="subject-new")
        upsert_user.return_value = (refreshed_user, False)
        get_payload.return_value = {"keycloak_subject": "subject-new"}

        payload = auth_me(request=request, user=original_user)

        self.assertEqual(
            decode_token.call_args_list[0].args,
            ("signed-id-token",),
        )
        self.assertEqual(
            decode_token.call_args_list[1].args,
            ("signed-access-token",),
        )
        self.assertEqual(
            decode_token.call_args_list[1].kwargs,
            {"require_subject": False},
        )
        upsert_user.assert_called_once_with(identity=identity_from_claims.return_value)
        get_payload.assert_called_once_with(user=refreshed_user)
        self.assertEqual(payload["keycloak_subject"], "subject-new")
