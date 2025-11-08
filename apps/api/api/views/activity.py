"""액티비티 로그 관련 뷰."""
from __future__ import annotations

from typing import Any, Dict, List

from django.http import HttpRequest, JsonResponse
from rest_framework.views import APIView

from ..models import ActivityLog


class ActivityLogView(APIView):
    """최근 액티비티 로그 조회."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)
        if not request.user.has_perm("api.view_activitylog"):
            return JsonResponse({"error": "Forbidden"}, status=403)

        limit_param = request.GET.get("limit")
        try:
            limit = int(limit_param) if limit_param is not None else 50
        except (TypeError, ValueError):
            limit = 50
        limit = max(1, min(limit, 200))

        logs = (
            ActivityLog.objects.select_related("user", "user__profile")
            .order_by("-created_at")
            [:limit]
        )

        payload: List[Dict[str, Any]] = []
        for entry in logs:
            payload.append(
                {
                    "id": entry.id,
                    "user": entry.user.get_username() if entry.user else None,
                    "role": getattr(getattr(entry.user, "profile", None), "role", None) if entry.user else None,
                    "action": entry.action,
                    "path": entry.path,
                    "method": entry.method,
                    "status": entry.status_code,
                    "metadata": entry.metadata,
                    "timestamp": entry.created_at.isoformat(),
                }
            )

        return JsonResponse({"results": payload})


__all__ = ["ActivityLogView"]
