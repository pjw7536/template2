"""Keycloak code+PKCE 로그인과 세션별 권한 snapshot을 처리합니다."""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Any

import jwt
from django.conf import settings
from django.db import IntegrityError, DataError
from django.http import HttpRequest

from api.account import services as account_services
from api.auth import selectors as auth_selectors
from . import keycloak_oidc
from .oidc_claims import extract_user_info_from_claims, upsert_user_from_claims
from .oidc_validation import (
    map_token_error, resolve_safe_redirect_target, validate_nonce, validate_required_identity,
)

TRANSACTION_SESSION_KEY = "oidc_transaction"


@dataclass(frozen=True)
class OidcLoginResult:
    """HTTP 계층에 전달하는 로그인 시작 결과입니다."""
    authorize_url: str | None = None
    bad_request_message: str | None = None


@dataclass(frozen=True)
class OidcCallbackResult:
    """검증된 사용자와 세션 권한 또는 오류를 전달합니다."""
    target: str | None = None
    user: Any = None
    raw_id_token: str | None = None
    authorization: dict | None = None
    error_code: str | None = None
    bad_request_message: str | None = None


def auth_config() -> dict[str, Any]:
    """프론트에 공개 가능한 인증 설정만 반환합니다."""
    return {
        "issuer": settings.OIDC_ISSUER, "clientId": settings.OIDC_CLIENT_ID,
        "loginUrl": "/api/v1/auth/login", "logoutUrl": "/api/v1/auth/logout",
        "meUrl": "/api/v1/auth/me", "callbackUrl": settings.OIDC_REDIRECT_URI,
        "responseMode": "query", "responseType": "code",
        "frontendRedirect": settings.FRONTEND_BASE_URL,
        "sessionMaxAgeSeconds": settings.SESSION_COOKIE_AGE,
        "providerConfigured": settings.OIDC_PROVIDER_CONFIGURED,
        "authorizationSource": "keycloak", "locale": settings.LANGUAGE_CODE,
        "timeZone": settings.TIME_ZONE,
    }


def auth_login(*, requested_target: str | None, request: HttpRequest) -> OidcLoginResult:
    """일회용 state·nonce·복귀 주소를 세션에 저장하고 authorize URL을 생성합니다."""
    if not settings.OIDC_PROVIDER_CONFIGURED:
        return OidcLoginResult(bad_request_message="oidc not configured")
    target = resolve_safe_redirect_target(requested_target, request)
    state, nonce = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    request.session[TRANSACTION_SESSION_KEY] = {"state": state, "nonce": nonce, "target": target}
    return OidcLoginResult(authorize_url=keycloak_oidc.build_authorize_url(
        request=request, state=state, nonce=nonce))


def auth_callback(*, request: HttpRequest, code: str | None = None, state: str,
                  error: str | None = None) -> OidcCallbackResult:
    """state·token·신원을 검증한 뒤 EPID 계정을 갱신합니다. 실패 시 세션 권한은 부여하지 않습니다."""
    if not settings.OIDC_PROVIDER_CONFIGURED:
        return OidcCallbackResult(bad_request_message="oidc not configured")
    tx = request.session.pop(TRANSACTION_SESSION_KEY, {})
    fallback = resolve_safe_redirect_target(None, request)
    expected_state = tx.get("state") if isinstance(tx, dict) else None
    if not isinstance(expected_state, str) or not state or not secrets.compare_digest(expected_state, state):
        request.session.pop(keycloak_oidc.PKCE_SESSION_KEY, None)
        return OidcCallbackResult(target=fallback, error_code="invalid_state")
    target = resolve_safe_redirect_target(tx.get("target"), request)
    if error or not code:
        request.session.pop(keycloak_oidc.PKCE_SESSION_KEY, None)
        return OidcCallbackResult(target=target, error_code="login_cancelled" if error else "missing_code")
    try:
        token_set = keycloak_oidc.exchange_code(request=request, code=code)
        raw_id_token = token_set["id_token"]
        decoded = keycloak_oidc.decode_id_token(raw_id_token)
    except keycloak_oidc.KeycloakOidcError:
        return OidcCallbackResult(target=target, error_code="token_exchange_failed")
    except jwt.PyJWTError as exc:
        return OidcCallbackResult(target=target, error_code=map_token_error(exc))
    if not validate_nonce(claims=decoded, expected_nonce=tx.get("nonce")):
        return OidcCallbackResult(target=target, error_code="invalid_nonce")
    try:
        info = extract_user_info_from_claims(decoded)
        sabun, knox_id, identity_error = validate_required_identity(info)
        if identity_error:
            return OidcCallbackResult(target=target, error_code=identity_error)
        snapshot = account_services.build_authorization_snapshot(decoded)
        info["identity_profile"] = {"user_sdwt_prod": snapshot["userSdwtProd"],
                                    "line_id": snapshot["line"], "authorization": snapshot}
        user, _created = upsert_user_from_claims(info=info, sabun=sabun, knox_id=knox_id)
    except (ValueError, IntegrityError, DataError):
        return OidcCallbackResult(target=target, error_code="invalid_identity")
    return OidcCallbackResult(target=target, user=user, raw_id_token=raw_id_token, authorization=snapshot)


def auth_me(*, user: Any) -> dict[str, Any]:
    """현재 세션의 사용자·권한을 반환하며 권한을 갱신하지 않습니다."""
    return auth_selectors.get_current_user_payload(user=user)


def auth_logout(*, request: HttpRequest) -> str:
    """서버 세션 종료 전에 Keycloak SSO 종료 주소를 생성합니다."""
    return keycloak_oidc.build_logout_url(request=request)


_extract_user_info_from_claims = extract_user_info_from_claims
_upsert_user_from_claims = upsert_user_from_claims
