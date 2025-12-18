from __future__ import annotations

from django.http import HttpRequest


def extract_bearer_token(request: HttpRequest) -> str:
    """Authorization 헤더에서 Bearer 토큰을 추출합니다."""

    auth_header = request.headers.get("Authorization") or request.META.get("HTTP_AUTHORIZATION") or ""
    if not isinstance(auth_header, str):
        return ""

    normalized = auth_header.strip()
    if normalized.lower().startswith("bearer "):
        return normalized[7:].strip()
    return normalized


__all__ = ["extract_bearer_token"]

