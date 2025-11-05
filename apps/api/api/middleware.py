from __future__ import annotations

import logging
from typing import Any, Dict

from django.utils.deprecation import MiddlewareMixin

from .models import ActivityLog

logger = logging.getLogger(__name__)


class ActivityLoggingMiddleware(MiddlewareMixin):
    """Persist a lightweight activity trail for authenticated users."""

    def process_response(self, request, response):
        try:
            self._record(request, response)
        except Exception:  # pragma: no cover - do not break responses
            logger.exception("Failed to record activity log")
        return response

    def _record(self, request, response) -> None:
        if request.method == "OPTIONS":
            return
        path = getattr(request, "path", "") or ""
        if path.startswith("/admin/") or path.startswith("/__"):  # skip admin/system paths
            return

        user = getattr(request, "user", None)
        if user is not None and not getattr(user, "is_authenticated", False):
            user = None

        metadata: Dict[str, Any] = {
            "query": request.GET.dict() if hasattr(request, "GET") else {},
            "remote_addr": request.META.get("REMOTE_ADDR"),
        }

        ActivityLog.objects.create(
            user=user,
            action=request.resolver_match.view_name if getattr(request, "resolver_match", None) else "",  # type: ignore[attr-defined]
            path=path,
            method=getattr(request, "method", "GET"),
            status_code=getattr(response, "status_code", 200),
            metadata=metadata,
        )
