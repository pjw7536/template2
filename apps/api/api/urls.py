from __future__ import annotations

from django.urls import path

from .views import (
    ActivityLogView,
    AuthConfigurationView,
    CurrentUserView,
    DevelopmentLoginView,
    DroneEarlyInformView,
    HealthView,
    LineHistoryView,
    LineIdListView,
    LogoutView,
    FrontendRedirectView,
    TableUpdateView,
    TablesView,
)

urlpatterns = [
    path("", FrontendRedirectView.as_view(), name="frontend-redirect"),
    path("health/", HealthView.as_view(), name="health"),
    path("auth/me", CurrentUserView.as_view(), name="auth-me"),
    path("auth/config", AuthConfigurationView.as_view(), name="auth-config"),
    path("auth/logout", LogoutView.as_view(), name="auth-logout"),
    path("auth/dev-login", DevelopmentLoginView.as_view(), name="auth-dev-login"),
    path("auth/activity", ActivityLogView.as_view(), name="auth-activity"),
    path("tables", TablesView.as_view(), name="tables"),
    path("tables/update", TableUpdateView.as_view(), name="tables-update"),
    path("line-dashboard/history", LineHistoryView.as_view(), name="line-dashboard-history"),
    path("line-dashboard/line-ids", LineIdListView.as_view(), name="line-dashboard-line-ids"),
    path("drone-early-inform", DroneEarlyInformView.as_view(), name="drone-early-inform"),
]
