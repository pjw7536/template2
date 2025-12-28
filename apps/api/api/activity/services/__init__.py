"""Activity feature service facade."""

from __future__ import annotations

from .activity_logs import get_recent_activity_payload

__all__ = ["get_recent_activity_payload"]
