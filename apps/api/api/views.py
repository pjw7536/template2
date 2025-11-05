from __future__ import annotations

from django.http import JsonResponse
from django.views import View


class HealthView(View):
    """Simple health probe returning application metadata."""

    def get(self, request, *args, **kwargs):  # type: ignore[override]
        return JsonResponse({
            "status": "ok",
            "application": "template2-api",
        })
