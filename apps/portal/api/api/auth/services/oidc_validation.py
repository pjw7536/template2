# =============================================================================
# 모듈 설명: OIDC state/nonce/id_token 검증 헬퍼를 제공합니다.
# - 주요 대상: redirect target 정규화, id_token 디코드, nonce/필수 클레임 검증
# - 불변 조건: redirect target은 허용 목록 검증을 통과해야 합니다.
# =============================================================================

"""OIDC callback 검증 헬퍼 모음.

- 주요 대상: 안전한 redirect target 계산, nonce·신원 검증
- 주요 함수: resolve_safe_redirect_target, validate_nonce, validate_required_identity
- 가정/불변 조건: 세션 nonce와 id_token nonce가 일치해야 로그인 가능함
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import jwt
from django.conf import settings
from django.http import HttpRequest

from api.common.services import resolve_frontend_target
from . import keycloak_oidc
from .oidc_utils import is_allowed_redirect


def resolve_safe_redirect_target(target: Optional[str], request: HttpRequest) -> str:
    """target을 안전한 리다이렉트 URL로 정규화합니다.

    입력:
    - target: 요청된 리다이렉트 대상
    - 요청: Django HttpRequest

    반환:
    - str: 허용 목록 검증을 통과한 URL

    부작용:
    - 없음

    오류:
    - 없음
    """
    resolved = resolve_frontend_target(target, request=request)
    if not is_allowed_redirect(resolved):
        return resolve_frontend_target(None, request=request)
    return resolved


def decode_id_token(raw_id_token: str) -> Dict[str, Any]:
    """Keycloak JWKS와 필수 표준 claim을 검증합니다."""
    return keycloak_oidc.decode_id_token(raw_id_token)


def map_token_error(exc: jwt.PyJWTError) -> str:
    """PyJWT 예외를 기존 redirect error 코드로 변환합니다.

    입력:
    - exc: PyJWT 예외 객체

    반환:
    - str: 기존 프론트엔드가 해석하는 error 코드

    부작용:
    - 없음

    오류:
    - 없음
    """
    if isinstance(exc, jwt.ExpiredSignatureError):
        return "token_expired"
    if isinstance(exc, jwt.InvalidIssuerError):
        return "invalid_iss"
    if isinstance(exc, jwt.InvalidAudienceError):
        return "invalid_aud"
    return "invalid_token"


def validate_nonce(*, claims: Dict[str, Any], expected_nonce: Optional[str]) -> bool:
    """세션 nonce와 id_token nonce가 일치하는지 확인합니다.

    입력:
    - claims: id_token 클레임
    - expected_nonce: 세션에서 꺼낸 nonce

    반환:
    - bool: nonce 일치 여부

    부작용:
    - 없음

    오류:
    - 없음
    """
    return expected_nonce is not None and claims.get("nonce") == expected_nonce


def validate_required_identity(
    info: Dict[str, Optional[str]],
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """로그인에 필요한 EPID/sabun/knox_id 값을 검증합니다.

    입력:
    - info: 클레임에서 추출한 사용자 정보

    반환:
    - tuple[Optional[str], Optional[str], Optional[str]]: sabun, knox_id, error_code

    부작용:
    - 없음

    오류:
    - 없음
    """
    if not info.get("avatarid"):
        return None, None, "missing_userid"
    sabun = info.get("sabun")
    knox_id = info.get("knox_id")
    if not sabun:
        return None, None, "missing_sabun"
    if not knox_id:
        return str(sabun), None, "missing_loginid"
    return str(sabun), str(knox_id), None


def append_error_to_target(target: str, error_code: str) -> str:
    """리다이렉트 target에 기존 error 쿼리 형식으로 오류 코드를 붙입니다.

    입력:
    - target: 안전한 리다이렉트 대상 URL
    - error_code: 오류 코드 문자열

    반환:
    - str: error 쿼리가 추가된 URL

    부작용:
    - 없음

    오류:
    - 없음
    """
    separator = "&" if "?" in target else "?"
    return f"{target}{separator}error={error_code}"


__all__ = [
    "append_error_to_target",
    "decode_id_token",
    "map_token_error",
    "resolve_safe_redirect_target",
    "validate_nonce",
    "validate_required_identity",
]
