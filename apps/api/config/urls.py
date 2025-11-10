"""URL configuration for the Django backend."""
from __future__ import annotations

from django.contrib import admin
from django.urls import include, path

from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from api.auth.views import GoogleOAuthCallbackView, GoogleOAuthStartView

swagger_view = SpectacularSwaggerView.as_view(url_name="api-schema")

schema_view = SpectacularAPIView.as_view()

urlpatterns = [
    path("admin/", admin.site.urls),
    path("auth/google/authenticate/", GoogleOAuthStartView.as_view(), name="google-oauth-start"),
    path("auth/google/callback/", GoogleOAuthCallbackView.as_view(), name="google-oauth-callback"),
    path("api/schema/", schema_view, name="api-schema"),
    path("schema/", schema_view, name="schema-proxied"),
    path("api/docs/", swagger_view, name="api-docs"),
    path("docs", swagger_view, name="docs"),
    path("docs/", swagger_view, name="docs-slash"),
    path("", include("api.urls")),
]
