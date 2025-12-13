"""Auxiliary views that remain after migrating to the new OIDC flow."""
from __future__ import annotations

from django.http import HttpRequest, HttpResponseRedirect
from rest_framework.views import APIView

from api.common.utils import resolve_frontend_target


class FrontendRedirectView(APIView):
    """요청을 프론트엔드 엔트리포인트(next 포함)로 리다이렉트합니다.

    Redirect requests to the configured frontend entrypoint.
    """

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> HttpResponseRedirect:  # type: ignore[override]
        target = resolve_frontend_target(request.GET.get("next"), request=request)
        return HttpResponseRedirect(target)


__all__ = ["FrontendRedirectView"]
