from __future__ import annotations

from django.urls import path

from .views import (
    TimelineCtttmLogsView,
    TimelineEquipmentInfoView,
    TimelineEqpLogsView,
    TimelineEquipmentsView,
    TimelineJiraLogsView,
    TimelineLinesView,
    TimelineLogsView,
    TimelinePrcGroupView,
    TimelineRacbLogsView,
    TimelineSdwtView,
    TimelineTipLogsView,
)

urlpatterns = [
    path("lines", TimelineLinesView.as_view(), name="timeline-lines"),
    path("sdwts", TimelineSdwtView.as_view(), name="timeline-sdwts"),
    path("prc-groups", TimelinePrcGroupView.as_view(), name="timeline-prc-groups"),
    path("equipments", TimelineEquipmentsView.as_view(), name="timeline-equipments"),
    path(
        "equipment-info/<str:line_id>/<str:eqp_id>",
        TimelineEquipmentInfoView.as_view(),
        name="timeline-equipment-info-line",
    ),
    path(
        "equipment-info/<str:eqp_id>",
        TimelineEquipmentInfoView.as_view(),
        name="timeline-equipment-info",
    ),
    path("logs", TimelineLogsView.as_view(), name="timeline-logs"),
    path("logs/eqp", TimelineEqpLogsView.as_view(), name="timeline-logs-eqp"),
    path("logs/tip", TimelineTipLogsView.as_view(), name="timeline-logs-tip"),
    path("logs/ctttm", TimelineCtttmLogsView.as_view(), name="timeline-logs-ctttm"),
    path("logs/racb", TimelineRacbLogsView.as_view(), name="timeline-logs-racb"),
    path("logs/jira", TimelineJiraLogsView.as_view(), name="timeline-logs-jira"),
]

