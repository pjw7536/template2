from __future__ import annotations

import os
from typing import Any, Dict

from django.conf import settings
from django.contrib.auth import get_user_model
from mozilla_django_oidc.auth import OIDCAuthenticationBackend

from ..models import ensure_user_profile


class RPAuthenticationBackend(OIDCAuthenticationBackend):
    """OIDC authentication backend with development fallbacks."""

    def filter_users_by_claims(self, claims: Dict[str, Any]):
        email = claims.get("email")
        if not email:
            return self.UserModel.objects.none()
        return self.UserModel.objects.filter(email__iexact=email)

    def create_user(self, claims: Dict[str, Any]):
        user = super().create_user(claims)
        return self.update_user(user, claims)

    def update_user(self, user, claims: Dict[str, Any]):
        user.email = claims.get("email") or user.email
        full_name = claims.get("name") or ""
        if full_name:
            parts = full_name.split()
            if len(parts) >= 2:
                user.first_name = parts[0]
                user.last_name = " ".join(parts[1:])
            else:
                user.first_name = full_name
        user.save()
        ensure_user_profile(user)
        return user

    def authenticate(self, request, **kwargs):
        if settings.DEBUG and not getattr(settings, "OIDC_RP_CLIENT_ID", None):
            dummy_email = os.environ.get("AUTH_DUMMY_EMAIL", "demo@example.com")
            dummy_name = os.environ.get("AUTH_DUMMY_NAME", "Demo User")
            user_model = get_user_model()
            username = dummy_email.split("@")[0] if "@" in dummy_email else dummy_email
            user, created = user_model.objects.get_or_create(
                email=dummy_email,
                defaults={"username": username or "dev-user", "first_name": dummy_name},
            )
            if created:
                user.set_unusable_password()
                user.save()
            ensure_user_profile(user)
            return user
        return super().authenticate(request, **kwargs)

    def get_settings(self, attr, default=None):
        return getattr(settings, attr, default)

    def verify_claims(self, claims: Dict[str, Any]):
        if settings.DEBUG and not getattr(settings, "OIDC_RP_CLIENT_ID", None):
            return claims
        return super().verify_claims(claims)

    def user_can_authenticate(self, user):
        if not user.is_active:
            return False
        return super().user_can_authenticate(user)
