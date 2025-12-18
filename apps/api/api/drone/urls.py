from __future__ import annotations

from django.urls import path

from .views import (
    DroneEarlyInformView,
    DroneSopInstantInformView,
    DroneSopJiraTriggerView,
    DroneSopPop3IngestTriggerView,
    LineHistoryView,
    LineIdListView,
)

urlpatterns = [
    path("early-inform", DroneEarlyInformView.as_view(), name="drone-early-inform"),
    path("history", LineHistoryView.as_view(), name="line-dashboard-history"),
    path("line-ids", LineIdListView.as_view(), name="line-dashboard-line-ids"),
    path(
        "sop/<int:sop_id>/instant-inform",
        DroneSopInstantInformView.as_view(),
        name="drone-sop-instant-inform",
    ),
    path(
        "sop/ingest/pop3/trigger",
        DroneSopPop3IngestTriggerView.as_view(),
        name="drone-sop-pop3-ingest-trigger",
    ),
    path(
        "sop/jira/trigger",
        DroneSopJiraTriggerView.as_view(),
        name="drone-sop-jira-trigger",
    ),
]
