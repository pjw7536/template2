from __future__ import annotations

from typing import Any

from ..selectors import get_recent_activity_logs
from ..serializers import serialize_activity_log


def get_recent_activity_payload(*, limit: int) -> list[dict[str, Any]]:
    """최근 ActivityLog 목록을 직렬화해 반환합니다.

    Args:
        limit: 최대 반환 개수.

    Returns:
        직렬화된 activity log 리스트.

    Side effects:
        None. Read-only query.
    """

    logs = get_recent_activity_logs(limit=limit)
    return [serialize_activity_log(entry) for entry in logs]
