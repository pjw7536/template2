"""URL configuration for the Django backend."""
from __future__ import annotations

from django.contrib import admin
from django.urls import include, path

from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from api.auth import oidc

swagger_view = SpectacularSwaggerView.as_view(url_name="api-schema")

schema_view = SpectacularAPIView.as_view()

urlpatterns = [
    path("admin/", admin.site.urls),
    path("auth/login", oidc.auth_login, name="auth-login"),
    path("auth/logout", oidc.auth_logout, name="auth-logout"),
    path("auth/me", oidc.auth_me, name="auth-me"),
    path("auth/config", oidc.auth_config, name="auth-config"),
    path("auth/google/callback/", oidc.auth_callback, name="auth-callback"),
    path("api/schema/", schema_view, name="api-schema"),
    path("schema/", schema_view, name="schema-proxied"),
    path("api/docs/", swagger_view, name="api-docs"),
    path("docs", swagger_view, name="docs"),
    path("docs/", swagger_view, name="docs-slash"),
    path("", include("api.urls")),
]
