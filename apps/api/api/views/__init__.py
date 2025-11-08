"""API 앱의 Django 뷰 모듈 모음."""
from __future__ import annotations

from .activity import ActivityLogView
from .auth import (
    AuthConfigurationView,
    CurrentUserView,
    DevelopmentLoginView,
    FrontendRedirectView,
    LoginRedirectView,
    LogoutView,
)
from .drone_early_inform import DroneEarlyInformView
from .health import HealthView
from .line_dashboard import LineHistoryView, LineIdListView
from .tables import TableUpdateView, TablesView

__all__ = [
    "ActivityLogView",
    "AuthConfigurationView",
    "CurrentUserView",
    "DevelopmentLoginView",
    "FrontendRedirectView",
    "LoginRedirectView",
    "LogoutView",
    "DroneEarlyInformView",
    "HealthView",
    "LineHistoryView",
    "LineIdListView",
    "TableUpdateView",
    "TablesView",
]
