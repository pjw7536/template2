# =============================================================================
# 모듈 설명: id_token 기반 OIDC 세션 인증 서비스 흐름을 제공합니다.
# - 주요 대상: 인증 설정, 로그인 URL 생성, callback 검증, 로그아웃 URL
# - 불변 조건: 외부 API 응답 형식과 세션 계약은 view 계층에서 그대로 보존합니다.
# =============================================================================

"""Keycloak authorization code flow를 사용하는 세션 기반 인증 서비스.

- 주요 대상: auth_config, auth_login, auth_callback, auth_me, auth_logout
- 주요 함수: 설정 페이로드 생성, authorize URL 생성, callback 검증/사용자 upsert
- 가정/불변 조건: Keycloak OIDC 설정은 settings/env에서 주입됨
"""
from __future__ import annotations

import uuid
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import jwt
from django.conf import settings
from django.http import HttpRequest

import api.auth.selectors as auth_selectors
from .oidc_claims import (
    extract_user_info_from_claims,
    upsert_user_from_keycloak_identity,
    upsert_user_from_claims,
)
from .keycloak import (
    KeycloakError,
    build_authorize_url,
    decode_id_token,
    exchange_code,
    identity_from_claims,
    refresh_session_if_needed,
)
from .oidc_utils import (
    ADFS_LOGOUT_URL,
    ISSUER,
    OIDC_CLIENT_ID,
    REDIRECT_URI,
    b64e,
    pop_nonce,
    save_nonce,
)
from .oidc_validation import (
    decode_state_to_target,
    map_token_error,
    resolve_safe_redirect_target,
    validate_nonce,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OidcLoginResult:
    """로그인 시작 서비스 결과입니다.

    입력:
    - authorize_url: ADFS authorize URL
    - bad_request_message: 설정 오류 시 기존 400 응답 메시지

    반환:
    - dataclass 인스턴스

    부작용:
    - 없음

    오류:
    - 없음
    """

    authorize_url: Optional[str] = None
    bad_request_message: Optional[str] = None


@dataclass(frozen=True)
class OidcCallbackResult:
    """OIDC callback 처리 결과입니다.

    입력:
    - target: 최종 redirect target
    - user: 세션 로그인할 사용자 객체
    - error_code: redirect target에 붙일 기존 error 코드
    - bad_request_message: 400으로 반환할 기존 오류 메시지

    반환:
    - dataclass 인스턴스

    부작용:
    - 없음

    오류:
    - 없음
    """

    target: Optional[str] = None
    user: Any = None
    error_code: Optional[str] = None
    bad_request_message: Optional[str] = None
    token_set: Optional[Dict[str, Any]] = None


def _session_max_age() -> Optional[int]:
    """SESSION_COOKIE_AGE 설정을 안전하게 정수로 변환합니다.

    입력:
    - 없음(settings 사용)

    반환:
    - Optional[int]: 양수일 때만 값, 그 외 None

    부작용:
    - 없음

    오류:
    - 없음(변환 실패 시 None 반환)
    """
    try:
        raw = getattr(settings, "SESSION_COOKIE_AGE", None)
        if raw is None:
            return None
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _provider_configured() -> bool:
    """OIDC_PROVIDER_CONFIGURED 설정 여부를 bool로 반환합니다.

    입력:
    - 없음(settings 사용)

    반환:
    - bool: 설정 값의 불리언 표현

    부작용:
    - 없음

    오류:
    - 없음
    """
    return bool(getattr(settings, "OIDC_PROVIDER_CONFIGURED", False))


def auth_config() -> Dict[str, Any]:
    """프런트엔드에 필요한 최소 OIDC 설정 페이로드를 생성합니다.

    입력:
    - 없음(settings 사용)

    반환:
    - Dict[str, Any]: 기존 `/api/v1/auth/config` 응답 페이로드

    부작용:
    - 없음

    오류:
    - 없음
    """
    return {
        "issuer": ISSUER,
        "clientId": OIDC_CLIENT_ID,
        "loginUrl": "/api/v1/auth/login",
        "logoutUrl": "/api/v1/auth/logout",
        "meUrl": "/api/v1/auth/me",
        "callbackUrl": REDIRECT_URI,
        "responseMode": "query",
        "responseType": "code",
        "frontendRedirect": settings.FRONTEND_BASE_URL,
        "sessionMaxAgeSeconds": _session_max_age(),
        "providerConfigured": _provider_configured(),
        "locale": getattr(settings, "LANGUAGE_CODE", "") or "",
        "timeZone": getattr(settings, "TIME_ZONE", "") or "",
    }


def auth_login(*, requested_target: Optional[str], request: HttpRequest) -> OidcLoginResult:
    """ADFS authorize URL과 세션 nonce를 준비합니다.

    입력:
    - requested_target: target 또는 next 쿼리 파라미터
    - request: Django HttpRequest

    반환:
    - OidcLoginResult: authorize URL 또는 기존 400 메시지

    부작용:
    - 세션에 `oidc_nonce` 저장

    오류:
    - 없음
    """
    if not _provider_configured():
        return OidcLoginResult(bad_request_message="oidc not configured")

    target = resolve_safe_redirect_target(requested_target, request)
    state = b64e(target)
    nonce = uuid.uuid4().hex
    save_nonce(request, nonce)

    return OidcLoginResult(
        authorize_url=build_authorize_url(
            request=request,
            state=state,
            nonce=nonce,
        )
    )


def auth_callback(
    *,
    request: HttpRequest,
    code: str,
    state: str,
) -> OidcCallbackResult:
    """OIDC callback 값을 검증하고 세션 로그인 대상 사용자를 반환합니다.

    입력:
    - request: Django HttpRequest
    - raw_id_token: form_post로 전달된 id_token
    - state: form_post로 전달된 state

    반환:
    - OidcCallbackResult: 성공 시 target/user, 실패 시 target/error_code 또는 400 메시지

    부작용:
    - 세션 nonce pop
    - 사용자 생성/갱신

    오류:
    - RuntimeError: 공개키 설정이 없을 때
    """
    if not _provider_configured():
        return OidcCallbackResult(bad_request_message="oidc not configured")

    raw_target = decode_state_to_target(state, request)
    target = resolve_safe_redirect_target(raw_target, request)
    expected_nonce = pop_nonce(request)

    try:
        token_set = exchange_code(request=request, code=code)
        raw_id_token = str(token_set.get("id_token") or "")
        raw_access_token = str(token_set.get("access_token") or "")
        if not raw_id_token or not raw_access_token:
            raise KeycloakError("Keycloak ID/access token이 없습니다.")
        decoded = decode_id_token(raw_id_token)
        access_claims = decode_id_token(raw_access_token, require_subject=False)
        identity = identity_from_claims({**decoded, **access_claims})
    except jwt.PyJWTError as exc:
        logger.warning("Keycloak JWT 검증 실패", exc_info=exc)
        return OidcCallbackResult(target=target, error_code=map_token_error(exc))
    except KeycloakError as exc:
        logger.warning("Keycloak identity 검증 실패", exc_info=exc)
        return OidcCallbackResult(target=target, error_code="invalid_keycloak_identity")

    if not validate_nonce(claims=decoded, expected_nonce=expected_nonce):
        return OidcCallbackResult(target=target, error_code="invalid_nonce")

    user, _created = upsert_user_from_keycloak_identity(identity=identity)
    return OidcCallbackResult(target=target, user=user, token_set=token_set)


def auth_me(*, request: HttpRequest, user: Any) -> Dict[str, Any]:
    """현재 로그인한 사용자 응답 payload를 조회합니다.

    입력:
    - user: 인증된 Django 사용자 객체

    반환:
    - Dict[str, Any]: 기존 `/api/v1/auth/me` 응답 payload

    부작용:
    - 외부망 dev 자동 소속 플래그가 켜져 있으면 기본 개발 소속을 보장함

    오류:
    - 없음
    """
    if getattr(user, "keycloak_subject", None):
        token_set = refresh_session_if_needed(request=request)
        if token_set is None:
            raise KeycloakError("Keycloak session이 만료되었습니다.")
        raw_access_token = str(token_set.get("access_token") or "")
        raw_id_token = str(token_set.get("id_token") or "")
        if not raw_access_token or not raw_id_token:
            raise KeycloakError("Keycloak ID/access token이 없습니다.")
        try:
            id_claims = decode_id_token(raw_id_token)
            access_claims = decode_id_token(
                raw_access_token,
                require_subject=False,
            )
            identity = identity_from_claims(
                {**id_claims, **access_claims}
            )
        except jwt.PyJWTError as exc:
            raise KeycloakError("Keycloak access token 검증에 실패했습니다.") from exc
        user, _created = upsert_user_from_keycloak_identity(identity=identity)
    return auth_selectors.get_current_user_payload(user=user)


def auth_logout(*, grist_logout_completed: bool = False) -> str:
    """필요하면 Grist 세션을 먼저 종료하고 최종 IdP 로그아웃 URL을 반환합니다.

    입력:
    - grist_logout_completed: Grist 세션 종료 후 돌아온 요청인지 여부

    반환:
    - str: Grist 또는 기존 ADFS logout URL

    부작용:
    - 없음

    오류:
    - 없음
    """
    should_clear_grist_session = bool(
        getattr(settings, "WORK_HUB_ENABLED", False)
        or getattr(settings, "GRIST_LOGOUT_ENABLED", False)
    )
    if should_clear_grist_session and not grist_logout_completed:
        public_url = str(getattr(settings, "GRIST_PUBLIC_URL", "") or "").strip()
        parsed = urlparse(public_url)
        if (
            parsed.scheme in {"http", "https"}
            and parsed.netloc
            and parsed.username is None
            and parsed.password is None
            and not parsed.query
            and not parsed.fragment
        ):
            return f"{public_url.rstrip('/')}/logout"
    return ADFS_LOGOUT_URL


__all__ = [
    "auth_config",
    "auth_login",
    "auth_callback",
    "auth_me",
    "auth_logout",
]


_extract_user_info_from_claims = extract_user_info_from_claims
_upsert_user_from_claims = upsert_user_from_claims
