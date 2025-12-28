# =============================================================================
# 모듈 설명: activity 도메인 라우팅을 제공합니다.
# - 주요 경로: logs
# - 불변 조건: 상위 URLConf에서 /api/v1/activity/ 프리픽스를 제공합니다.
# =============================================================================
from __future__ import annotations

from django.urls import path

from .views import ActivityLogView

urlpatterns = [
    path("logs", ActivityLogView.as_view(), name="activity-logs"),
]
