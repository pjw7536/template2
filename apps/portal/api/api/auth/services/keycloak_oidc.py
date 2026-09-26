# =============================================================================
# 모듈 설명: Keycloak 로그인 전용 OIDC code flow를 제공합니다.
# - 주요 대상: PKCE authorize URL, code 교환, JWKS id_token 검증, SSO logout
# - 불변 조건: Keycloak은 로그인과 권한의 원천이며 검증된 권한은 세션에 저장합니다.
# =============================================================================

"""Keycloak authorization code + PKCE 로그인 헬퍼입니다.

- 주요 대상: 로그인 URL 생성, token endpoint 교환, JWKS 서명 검증
- 주요 함수: build_authorize_url, exchange_code, decode_id_token, build_logout_url
- 가정/불변 조건: 공개 issuer와 cluster 내부 token/JWKS URL을 분리할 수 있음
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from functools import lru_cache
from typing import Any
from urllib.parse import urlencode

import jwt
import requests
from django.conf import settings
from django.http import HttpRequest


PKCE_SESSION_KEY = "oidc_pkce_verifier"
ID_TOKEN_SESSION_KEY = "oidc_id_token"


class KeycloakOidcError(RuntimeError):
    """Keycloak 설정 또는 token endpoint 계약 오류입니다."""


def _timeout() -> tuple[int, int]:
    """Keycloak HTTP 연결과 응답 제한 시간을 반환합니다.

    입력:
    - 없음(settings 사용)

    반환:
    - tuple[int, int]: 연결 제한 시간과 응답 제한 시간

    부작용:
    - 없음

    오류:
    - 없음
    """

    return (
        int(getattr(settings, "OIDC_CONNECT_TIMEOUT_SECONDS", 3)),
        int(getattr(settings, "OIDC_READ_TIMEOUT_SECONDS", 10)),
    )


def _create_pkce_pair() -> tuple[str, str]:
    """RFC 7636 S256 verifier와 challenge를 생성합니다.

    입력:
    - 없음

    반환:
    - tuple[str, str]: verifier와 challenge

    부작용:
    - 안전한 난수 생성

    오류:
    - 없음
    """

    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def build_authorize_url(*, request: HttpRequest, state: str, nonce: str) -> str:
    """PKCE 값을 세션에 저장하고 Keycloak authorize URL을 반환합니다.

    입력:
    - request: Django 요청과 세션
    - state: 로그인 트랜잭션에 연결된 일회용 난수
    - nonce: id_token 재사용을 막는 세션 난수

    반환:
    - str: 브라우저가 이동할 Keycloak authorize URL

    부작용:
    - 세션에 PKCE verifier 저장

    오류:
    - 없음
    """

    verifier, challenge = _create_pkce_pair()
    request.session[PKCE_SESSION_KEY] = verifier
    params = {
        "client_id": settings.OIDC_CLIENT_ID,
        "redirect_uri": settings.OIDC_REDIRECT_URI,
        "response_mode": "query",
        "response_type": "code",
        "scope": "openid profile email",
        "nonce": nonce,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return f"{settings.OIDC_AUTH_URL}?{urlencode(params)}"


def exchange_code(*, request: HttpRequest, code: str) -> dict[str, Any]:
    """authorization code를 Keycloak token set으로 교환합니다.

    입력:
    - request: PKCE verifier가 저장된 Django 요청
    - code: Keycloak이 callback에 전달한 일회용 code

    반환:
    - dict[str, Any]: 검증 전 token endpoint JSON

    부작용:
    - 세션에서 PKCE verifier 제거
    - Keycloak token endpoint 호출

    오류:
    - KeycloakOidcError: verifier 누락, HTTP 실패 또는 응답 계약 오류
    """

    verifier = str(request.session.pop(PKCE_SESSION_KEY, "") or "")
    if not verifier:
        raise KeycloakOidcError("PKCE verifier가 없습니다.")

    try:
        response = requests.post(
            settings.OIDC_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "client_id": settings.OIDC_CLIENT_ID,
                "client_secret": settings.OIDC_CLIENT_SECRET,
                "redirect_uri": settings.OIDC_REDIRECT_URI,
                "code": code,
                "code_verifier": verifier,
            },
            timeout=_timeout(),
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise KeycloakOidcError(
            "Keycloak token endpoint 호출에 실패했습니다."
        ) from exc

    if not isinstance(payload, dict) or not str(payload.get("id_token") or ""):
        raise KeycloakOidcError("Keycloak token 응답에 id_token이 없습니다.")
    return payload


def decode_id_token(raw_id_token: str) -> dict[str, Any]:
    """Keycloak JWKS로 id_token의 표준 보안 조건을 검증합니다.

    입력:
    - raw_id_token: Keycloak token endpoint가 반환한 JWT

    반환:
    - dict[str, Any]: 검증된 id_token claims

    부작용:
    - JWKS 캐시가 비었거나 갱신될 때 Keycloak JWKS endpoint 호출

    오류:
    - jwt.PyJWTError: 서명, issuer, audience, 만료 또는 필수 claim 오류
    """

    jwks_client = _jwks_client(settings.OIDC_JWKS_URL, settings.OIDC_JWKS_CACHE_SECONDS,
                               settings.OIDC_READ_TIMEOUT_SECONDS)
    signing_key = jwks_client.get_signing_key_from_jwt(raw_id_token)
    claims = jwt.decode(
        raw_id_token,
        signing_key.key,
        algorithms=["RS256"],
        audience=settings.OIDC_CLIENT_ID,
        issuer=settings.OIDC_ISSUER,
        options={"require": ["exp", "iat", "iss", "sub", "aud", "nonce"]},
    )

    audience = claims.get("aud")
    if (claims.get("azp") not in (None, settings.OIDC_CLIENT_ID)
            or (isinstance(audience, list) and len(audience) > 1 and claims.get("azp") != settings.OIDC_CLIENT_ID)):
        raise jwt.InvalidAudienceError("invalid azp")
    return claims


@lru_cache(maxsize=8)
def _jwks_client(url: str, lifespan: int, timeout: int) -> jwt.PyJWKClient:
    """URL과 설정별 JWKS 캐시를 공유합니다."""
    return jwt.PyJWKClient(url, cache_keys=False, lifespan=lifespan, timeout=timeout)


def save_id_token(*, request: HttpRequest, raw_id_token: str) -> None:
    """Keycloak SSO logout에 사용할 id_token을 서버 세션에 저장합니다.

    입력:
    - request: Django 요청과 세션
    - raw_id_token: 검증을 통과한 Keycloak id_token

    반환:
    - 없음

    부작용:
    - Django 세션 변경

    오류:
    - 없음
    """

    request.session[ID_TOKEN_SESSION_KEY] = raw_id_token


def build_logout_url(*, request: HttpRequest) -> str:
    """Keycloak SSO 세션까지 종료하는 logout URL을 생성합니다.

    입력:
    - request: id_token이 저장된 Django 요청과 세션

    반환:
    - str: Keycloak logout endpoint와 안전한 사후 이동 URL

    부작용:
    - 세션에서 저장된 id_token 제거

    오류:
    - 없음
    """

    raw_id_token = str(request.session.pop(ID_TOKEN_SESSION_KEY, "") or "")
    params = {
        "client_id": settings.OIDC_CLIENT_ID,
        "post_logout_redirect_uri": settings.FRONTEND_BASE_URL,
    }
    if raw_id_token:
        params["id_token_hint"] = raw_id_token
    return f"{settings.OIDC_LOGOUT_URL}?{urlencode(params)}"


__all__ = [
    "KeycloakOidcError",
    "build_authorize_url",
    "build_logout_url",
    "decode_id_token",
    "exchange_code",
    "save_id_token",
]
