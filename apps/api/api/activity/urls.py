from __future__ import annotations

from django.urls import path

from .views import ActivityLogView

urlpatterns = [
    path("logs", ActivityLogView.as_view(), name="activity-logs"),
]
