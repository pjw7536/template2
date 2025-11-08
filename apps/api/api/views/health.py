"""헬스 체크 관련 뷰."""
from __future__ import annotations

from django.http import HttpRequest, JsonResponse
from django.views import View


class HealthView(View):
    """단순 헬스 체크 엔드포인트."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        return JsonResponse(
            {
                "status": "ok",
                "application": "template2-api",
            }
        )
