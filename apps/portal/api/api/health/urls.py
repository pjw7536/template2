# =============================================================================
# 모듈 설명: health 도메인 라우팅을 제공합니다.
# - 주요 경로: /
# - 불변 조건: 상위 URLConf에서 /api/v1/health/ 프리픽스를 제공합니다.
# =============================================================================

from __future__ import annotations

from django.urls import path

from .views import HealthView

urlpatterns = [
    path("", HealthView.as_view(), name="health"),
]
