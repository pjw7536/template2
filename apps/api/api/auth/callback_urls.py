# =============================================================================
# 모듈 설명: OIDC 콜백 전용 URL 라우팅을 제공합니다.
# - 주요 대상: auth_callback
# - 불변 조건: 콜백은 authorization code와 state를 전달합니다.
# =============================================================================

"""OIDC 콜백 전용 URL 라우팅 모음.

- 주요 대상: Keycloak 콜백 경로
- 주요 엔드포인트/클래스: auth_callback
- 가정/불변 조건: 콜백은 authorization code와 state를 전달함
"""
from __future__ import annotations

from django.urls import path

from .views import auth_callback

urlpatterns = [
    path("keycloak/callback/", auth_callback, name="auth-callback"),
]
