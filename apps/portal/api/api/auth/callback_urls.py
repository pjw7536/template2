"""Keycloak 인증 callback만 노출합니다."""
from django.urls import path
from .views import auth_callback

urlpatterns = [path("keycloak/callback/", auth_callback, name="auth-keycloak-callback")]
