# =============================================================================
# 모듈 설명: 활동 로그 조회 셀렉터를 제공합니다.
# - 주요 함수: get_recent_activity_logs
# - 불변 조건: 최신순 정렬과 최소 1건 제한을 유지합니다.
# =============================================================================
from __future__ import annotations

from django.db.models import QuerySet

from .models import ActivityLog


def get_recent_activity_logs(*, limit: int) -> QuerySet[ActivityLog]:
    """최근 활동 로그를 최신순으로 조회합니다.

    입력:
    - limit: 반환할 최대 건수

    반환:
    - QuerySet[ActivityLog]: 최신순 ActivityLog QuerySet(사용자/프로필 포함)

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    safe_limit = max(1, limit)
    return ActivityLog.objects.select_related("user", "user__profile").order_by("-created_at")[:safe_limit]
