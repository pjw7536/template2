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
