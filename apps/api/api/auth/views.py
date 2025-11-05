from __future__ import annotations

from django.conf import settings
from django.contrib import auth
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import resolve_url

from mozilla_django_oidc.views import (
    OIDCAuthenticationRequestView,
    get_next_url,
)


class ConditionalOIDCAuthenticationRequestView(OIDCAuthenticationRequestView):
    """OIDC authenticate endpoint that supports a development fallback."""

    def get(self, request):
        client_id = getattr(settings, "OIDC_RP_CLIENT_ID", None)
        auth_endpoint = getattr(settings, "OIDC_OP_AUTHORIZATION_ENDPOINT", None)
        dev_login_enabled = bool(getattr(settings, "OIDC_DEV_LOGIN_ENABLED", False))

        if not client_id or not auth_endpoint:
            if dev_login_enabled:
                user = auth.authenticate(request=request)
                if user is not None:
                    auth.login(request, user)
                    redirect_field_name = self.get_settings("OIDC_REDIRECT_FIELD_NAME", "next")
                    next_target = get_next_url(request, redirect_field_name)
                    if not next_target:
                        next_target = resolve_url(self.get_settings("LOGIN_REDIRECT_URL", "/"))
                    return HttpResponseRedirect(next_target)
            return JsonResponse({"error": "OIDC provider is not configured"}, status=503)

        return super().get(request)
