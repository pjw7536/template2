from __future__ import annotations

from django.urls import path

from .views import (
    DroneEarlyInformView,
    HealthView,
    LineHistoryView,
    LineIdListView,
    TableUpdateView,
    TablesView,
)

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("tables", TablesView.as_view(), name="tables"),
    path("tables/update", TableUpdateView.as_view(), name="tables-update"),
    path("line-dashboard/history", LineHistoryView.as_view(), name="line-dashboard-history"),
    path("line-dashboard/line-ids", LineIdListView.as_view(), name="line-dashboard-line-ids"),
    path("drone-early-inform", DroneEarlyInformView.as_view(), name="drone-early-inform"),
]
