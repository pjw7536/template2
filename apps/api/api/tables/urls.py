# =============================================================================
# 모듈 설명: tables 도메인 라우팅을 제공합니다.
# - 주요 경로: /, /update
# - 불변 조건: 상위 URLConf에서 /api/v1/tables/ 프리픽스를 제공합니다.
# =============================================================================

from __future__ import annotations

from django.urls import path

from .views import TableUpdateView, TablesView

urlpatterns = [
    path("", TablesView.as_view(), name="tables"),
    path("update", TableUpdateView.as_view(), name="tables-update"),
]
