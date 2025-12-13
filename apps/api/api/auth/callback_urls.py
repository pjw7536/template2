from __future__ import annotations

from django.urls import path

from api.auth import oidc

urlpatterns = [
    path("google/callback/", oidc.auth_callback, name="auth-callback"),
]

