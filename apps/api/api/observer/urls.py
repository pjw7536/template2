# =============================================================================
# 모듈 설명: observer 더미 엔드포인트 라우팅을 정의합니다.
# - 주요 경로: lines, sdwts, prc-groups, equipments, logs
# - 불변 조건: 상대 경로만 선언합니다.
# =============================================================================

from __future__ import annotations

from django.urls import path

from .views import (
    ObserverEquipmentInfoView,
    ObserverEquipmentsView,
    ObserverLinesView,
    ObserverEvidenceLogView,
    ObserverLogDetailView,
    ObserverLogsByTypePageView,
    ObserverLogsPageView,
    ObserverPrcGroupView,
    ObserverSdwtView,
    ObserverTkinPreventMatrixView,
    ObserverTkinPreventPrcGroupsView,
    ObserverTkinPreventProcessesView,
    ObserverTkinPreventStepSeqsView,
)

urlpatterns = [
    path("lines", ObserverLinesView.as_view(), name="observer-lines"),
    path("sdwts", ObserverSdwtView.as_view(), name="observer-sdwts"),
    path("prc-groups", ObserverPrcGroupView.as_view(), name="observer-prc-groups"),
    path("equipments", ObserverEquipmentsView.as_view(), name="observer-equipments"),
    path(
        "equipment-info/<str:eqp_id>",
        ObserverEquipmentInfoView.as_view(),
        name="observer-equipment-info",
    ),
    path("logs/page", ObserverLogsPageView.as_view(), name="observer-logs-page"),
    path(
        "logs/<str:log_key>/page",
        ObserverLogsByTypePageView.as_view(),
        name="observer-logs-type-page",
    ),
    path(
        "logs/<str:log_key>/detail",
        ObserverLogDetailView.as_view(),
        name="observer-log-detail",
    ),
    path(
        "logs/<str:log_key>/evidence",
        ObserverEvidenceLogView.as_view(),
        name="observer-evidence-log",
    ),
    path(
        "tkin-prevent/prc-groups",
        ObserverTkinPreventPrcGroupsView.as_view(),
        name="observer-tkin-prevent-prc-groups",
    ),
    path(
        "tkin-prevent/processes",
        ObserverTkinPreventProcessesView.as_view(),
        name="observer-tkin-prevent-processes",
    ),
    path(
        "tkin-prevent/step-seqs",
        ObserverTkinPreventStepSeqsView.as_view(),
        name="observer-tkin-prevent-step-seqs",
    ),
    path(
        "tkin-prevent/matrix",
        ObserverTkinPreventMatrixView.as_view(),
        name="observer-tkin-prevent-matrix",
    ),
]
