"""Auxiliary views that remain after migrating to the new OIDC flow."""
from __future__ import annotations

from django.http import HttpRequest, HttpResponseRedirect
from rest_framework.views import APIView

from .utils import resolve_frontend_target


class FrontendRedirectView(APIView):
    """Redirect requests to the configured frontend entrypoint."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> HttpResponseRedirect:  # type: ignore[override]
        target = resolve_frontend_target(request.GET.get("next"), request=request)
        return HttpResponseRedirect(target)


__all__ = ["FrontendRedirectView"]
