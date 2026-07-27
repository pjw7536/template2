# =============================================================================
# 모듈: TTTM Spider 라우팅
# 주요 경로: combo/options, combo/types, combo/data-types, dashboard/data
# 주요 가정: 전역 prefix(api/v1/tttm_spider)는 api.urls에서만 선언한다.
# =============================================================================
from __future__ import annotations

from django.urls import path

from .views import (
    TttmSpiderComboDataTypesView,
    TttmSpiderComboOptionsView,
    TttmSpiderComboTypesView,
    TttmSpiderChambersView,
    TttmSpiderDashboardDataView,
    TttmSpiderEqpsView,
    TttmSpiderGoldenLotwfView,
    TttmSpiderLotwfView,
    TttmSpiderResultStatusView,
    TttmSpiderSensorTraceView,
)

urlpatterns = [
    path("combo/options", TttmSpiderComboOptionsView.as_view(), name="tttm-spider-combo-options"),
    path("combo/types", TttmSpiderComboTypesView.as_view(), name="tttm-spider-combo-types"),
    path("combo/data-types", TttmSpiderComboDataTypesView.as_view(), name="tttm-spider-combo-data-types"),
    path("targets/eqps", TttmSpiderEqpsView.as_view(), name="tttm-spider-eqps"),
    path("targets/chambers", TttmSpiderChambersView.as_view(), name="tttm-spider-chambers"),
    path("targets/lotwf", TttmSpiderLotwfView.as_view(), name="tttm-spider-lotwf"),
    path("targets/golden", TttmSpiderGoldenLotwfView.as_view(), name="tttm-spider-golden"),
    path("targets/result-status", TttmSpiderResultStatusView.as_view(), name="tttm-spider-result-status"),
    path("dashboard/data", TttmSpiderDashboardDataView.as_view(), name="tttm-spider-dashboard-data"),
    path("sensor-trace", TttmSpiderSensorTraceView.as_view(), name="tttm-spider-sensor-trace"),
]
