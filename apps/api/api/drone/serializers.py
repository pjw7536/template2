from __future__ import annotations

from typing import Any

from .models import DroneEarlyInformV3


def serialize_early_inform_entry(entry: DroneEarlyInformV3) -> dict[str, Any]:
    """DroneEarlyInformV3 모델을 API 응답 형태로 직렬화합니다."""

    updated_at = entry.updated_at
    return {
        "id": int(entry.id),
        "lineId": entry.line_id,
        "mainStep": entry.main_step,
        "customEndStep": entry.custom_end_step,
        "updatedBy": entry.updated_by,
        "updatedAt": updated_at.isoformat() if hasattr(updated_at, "isoformat") and updated_at else None,
    }

