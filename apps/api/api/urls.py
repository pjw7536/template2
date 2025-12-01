from __future__ import annotations

from django.urls import path

from .views import (
    ActivityLogView,
    DroneEarlyInformView,
    FrontendRedirectView,
    HealthView,
    LineHistoryView,
    LineIdListView,
    TableUpdateView,
    TablesView,
    VocPostDetailView,
    VocPostsView,
    VocReplyView,
)

urlpatterns = [
    path("", FrontendRedirectView.as_view(), name="frontend-redirect"),
    path("health/", HealthView.as_view(), name="health"),
    path("auth/activity", ActivityLogView.as_view(), name="auth-activity"),
    path("tables", TablesView.as_view(), name="tables"),
    path("tables/update", TableUpdateView.as_view(), name="tables-update"),
    path("line-dashboard/history", LineHistoryView.as_view(), name="line-dashboard-history"),
    path("line-dashboard/line-ids", LineIdListView.as_view(), name="line-dashboard-line-ids"),
    path("drone-early-inform", DroneEarlyInformView.as_view(), name="drone-early-inform"),
    path("voc/posts", VocPostsView.as_view(), name="voc-posts"),
    path("voc/posts/<int:post_id>", VocPostDetailView.as_view(), name="voc-post-detail"),
    path("voc/posts/<int:post_id>/replies", VocReplyView.as_view(), name="voc-post-reply"),
]
