# =============================================================================
# 모듈: 드론 직렬화 유틸
# 주요 함수: serialize_early_inform_entry
# 주요 가정: 응답 키는 camelCase로 반환합니다.
# =============================================================================
from __future__ import annotations

from typing import Any

from .models import DroneEarlyInform


def serialize_early_inform_entry(entry: DroneEarlyInform) -> dict[str, Any]:
    """DroneEarlyInform 모델을 API 응답 형태로 직렬화합니다.

    인자:
        entry: DroneEarlyInform 인스턴스.

    반환:
        직렬화된 dict.

    부작용:
        없음. 읽기 전용 변환입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 업데이트 시각 정규화
    # -----------------------------------------------------------------------------
    updated_at = entry.updated_at
    return {
        "id": int(entry.id),
        "lineId": entry.line_id,
        "mainStep": entry.main_step,
        "customEndStep": entry.custom_end_step,
        "updatedBy": entry.updated_by,
        "updatedAt": updated_at.isoformat() if hasattr(updated_at, "isoformat") and updated_at else None,
    }
