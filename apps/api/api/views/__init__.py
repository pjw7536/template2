"""API 앱의 Django 뷰 모듈 모음."""
from __future__ import annotations

from .activity import ActivityLogView
from .assistant import AssistantChatView
from .auth import FrontendRedirectView
from .drone_early_inform import DroneEarlyInformView
from .health import HealthView
from .line_dashboard import LineHistoryView, LineIdListView
from .timeline import (
    TimelineCtttmLogsView,
    TimelineEqpLogsView,
    TimelineEquipmentInfoView,
    TimelineJiraLogsView,
    TimelineLinesView,
    TimelineLogsView,
    TimelinePrcGroupView,
    TimelineRacbLogsView,
    TimelineSdwtView,
    TimelineTipLogsView,
    TimelineEquipmentsView,
)
from .tables import TableUpdateView, TablesView
from .voc import VocPostDetailView, VocPostsView, VocReplyView

__all__ = [
    "ActivityLogView",
    "AssistantChatView",
    "FrontendRedirectView",
    "DroneEarlyInformView",
    "HealthView",
    "LineHistoryView",
    "LineIdListView",
    "TimelineCtttmLogsView",
    "TimelineEqpLogsView",
    "TimelineEquipmentInfoView",
    "TimelineJiraLogsView",
    "TimelineLinesView",
    "TimelineLogsView",
    "TimelinePrcGroupView",
    "TimelineRacbLogsView",
    "TimelineSdwtView",
    "TimelineTipLogsView",
    "TimelineEquipmentsView",
    "TableUpdateView",
    "TablesView",
    "VocPostDetailView",
    "VocPostsView",
    "VocReplyView",
]
