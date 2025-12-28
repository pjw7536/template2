from __future__ import annotations

from typing import Any

from .models import ActivityLog


def serialize_activity_log(entry: ActivityLog) -> dict[str, Any]:
    """ActivityLog 모델을 API 응답 형식으로 직렬화합니다.

    Side effects:
        None. Read-only mapping.
    """

    user = entry.user
    username = user.get_username() if user else None
    role = getattr(getattr(user, "profile", None), "role", None) if user else None

    metadata = entry.metadata or {}
    if isinstance(metadata, dict) and metadata.get("remote_addr") == "172.18.0.1":
        metadata = {key: value for key, value in metadata.items() if key != "remote_addr"}

    return {
        "id": entry.id,
        "user": username,
        "role": role,
        "action": entry.action,
        "path": entry.path,
        "method": entry.method,
        "status": entry.status_code,
        "metadata": metadata,
        "timestamp": entry.created_at.isoformat(),
    }


__all__ = ["serialize_activity_log"]
