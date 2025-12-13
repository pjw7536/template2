from __future__ import annotations

from django.urls import path

from .views import DroneEarlyInformView, LineHistoryView, LineIdListView

urlpatterns = [
    path("early-inform", DroneEarlyInformView.as_view(), name="drone-early-inform"),
    path("history", LineHistoryView.as_view(), name="line-dashboard-history"),
    path("line-ids", LineIdListView.as_view(), name="line-dashboard-line-ids"),
]
