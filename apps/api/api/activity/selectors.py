from __future__ import annotations

from django.db.models import QuerySet

from .models import ActivityLog


def get_recent_activity_logs(*, limit: int) -> QuerySet[ActivityLog]:
    """최근 활동 로그를 최신순으로 조회합니다.

    Return the most recent activity logs.

    Args:
        limit: Maximum number of rows to return.

    Returns:
        QuerySet ordered by newest first, with related user/profile loaded.

    Side effects:
        None. Read-only query.
    """

    safe_limit = max(1, limit)
    return ActivityLog.objects.select_related("user", "user__profile").order_by("-created_at")[:safe_limit]
