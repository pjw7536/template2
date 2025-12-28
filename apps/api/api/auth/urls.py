# =============================================================================
# 모듈 설명: 인증 관련 URL 라우팅을 제공합니다.
# - 주요 대상: auth_login/auth_logout/auth_me/auth_config/FrontendRedirectView
# - 불변 조건: 상위 URLConf에서 /api/v1/auth/ 프리픽스를 제공합니다.
# =============================================================================

"""인증 관련 URL 라우팅 모음.

- 주요 대상: 로그인/로그아웃/내 정보/설정/프론트 리다이렉트
- 주요 엔드포인트/클래스: auth_login, auth_logout, auth_me, auth_config, FrontendRedirectView
- 가정/불변 조건: 상위 URLConf에서 /api/v1/auth/ 프리픽스를 제공함
"""
from __future__ import annotations

from django.urls import path

from api.auth import oidc

from .views import FrontendRedirectView

urlpatterns = [
    path("login", oidc.auth_login, name="auth-login"),
    path("logout", oidc.auth_logout, name="auth-logout"),
    path("me", oidc.auth_me, name="auth-me"),
    path("config", oidc.auth_config, name="auth-config"),
    path("", FrontendRedirectView.as_view(), name="frontend-redirect"),
]
