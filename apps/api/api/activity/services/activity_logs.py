# =============================================================================
# 모듈 설명: 활동 로그 서비스 로직을 제공합니다.
# - 주요 함수: get_recent_activity_payload
# - 불변 조건: 조회는 셀렉터를 통해 수행합니다.
# =============================================================================
from __future__ import annotations

from typing import Any

from ..selectors import get_recent_activity_logs
from ..serializers import serialize_activity_log


def get_recent_activity_payload(*, limit: int) -> list[dict[str, Any]]:
    """최근 ActivityLog 목록을 직렬화해 반환합니다.

    입력:
    - limit: 최대 반환 개수

    반환:
    - list[dict[str, Any]]: 직렬화된 activity log 리스트

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    logs = get_recent_activity_logs(limit=limit)
    return [serialize_activity_log(entry) for entry in logs]
