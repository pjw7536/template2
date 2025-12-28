# =============================================================================
# 모듈: 드론 인증 유틸
# 주요 함수: extract_bearer_token
# 주요 가정: Authorization 헤더는 "Bearer <token>" 형식을 사용합니다.
# =============================================================================
from __future__ import annotations

from django.http import HttpRequest


def extract_bearer_token(request: HttpRequest) -> str:
    """Authorization 헤더에서 Bearer 토큰을 추출합니다.

    인자:
        요청: Django HttpRequest 객체.

    반환:
        Bearer 토큰 문자열(없으면 빈 문자열).

    부작용:
        없음. 순수 문자열 파싱입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 헤더 값 추출
    # -----------------------------------------------------------------------------
    auth_header = request.headers.get("Authorization") or request.META.get("HTTP_AUTHORIZATION") or ""
    if not isinstance(auth_header, str):
        return ""

    # -----------------------------------------------------------------------------
    # 2) Bearer 접두사 처리
    # -----------------------------------------------------------------------------
    normalized = auth_header.strip()
    if normalized.lower().startswith("bearer "):
        return normalized[7:].strip()
    return normalized


__all__ = ["extract_bearer_token"]
