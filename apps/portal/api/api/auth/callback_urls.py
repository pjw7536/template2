# =============================================================================
# 모듈 설명: OIDC 콜백 전용 URL 라우팅을 제공합니다.
# - 주요 대상: auth_callback
# - 불변 조건: provider별 callback 경로를 명시적으로 유지합니다.
# =============================================================================

"""OIDC provider별 콜백 URL 라우팅 모음.

- 주요 대상: 기존 ADFS와 Keycloak 콜백 경로
- 주요 엔드포인트/클래스: auth_callback
- 가정/불변 조건: 기존 Google 명칭 경로는 호환성을 위해 유지됨
"""
from __future__ import annotations

from django.urls import path

from .views import auth_callback

urlpatterns = [
    path("google/callback/", auth_callback, name="auth-callback"),
    path("keycloak/callback/", auth_callback, name="auth-keycloak-callback"),
]
