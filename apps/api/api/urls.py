from __future__ import annotations

from django.urls import path

from api.activity.views import ActivityLogView
from api.appstore.views import (
    AppStoreAppDetailView,
    AppStoreAppsView,
    AppStoreCommentDetailView,
    AppStoreCommentsView,
    AppStoreLikeToggleView,
    AppStoreViewIncrementView,
)
from api.assistant.views import AssistantChatView
from api.auth.views import FrontendRedirectView
from api.drone.views import DroneEarlyInformView
from api.emails.views import (
    EmailBulkDeleteView,
    EmailDetailView,
    EmailHtmlView,
    EmailIngestTriggerView,
    EmailListView,
)
from api.health.views import HealthView
from api.line_dashboard.views import LineHistoryView, LineIdListView
from api.tables.views import TableUpdateView, TablesView
from api.timeline.views import (
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
from api.voc.views import VocPostDetailView, VocPostsView, VocReplyView

urlpatterns = [
    path("", FrontendRedirectView.as_view(), name="frontend-redirect"),
    path("health/", HealthView.as_view(), name="health"),
    path("auth/activity", ActivityLogView.as_view(), name="auth-activity"),
    path("tables", TablesView.as_view(), name="tables"),
    path("tables/update", TableUpdateView.as_view(), name="tables-update"),
    path("line-dashboard/history", LineHistoryView.as_view(), name="line-dashboard-history"),
    path("line-dashboard/line-ids", LineIdListView.as_view(), name="line-dashboard-line-ids"),
    path("drone-early-inform", DroneEarlyInformView.as_view(), name="drone-early-inform"),
    path("api/v1/assistant/chat", AssistantChatView.as_view(), name="assistant-chat"),
    path("api/v1/timeline/lines", TimelineLinesView.as_view(), name="timeline-lines"),
    path("api/v1/timeline/sdwts", TimelineSdwtView.as_view(), name="timeline-sdwts"),
    path("api/v1/timeline/prc-groups", TimelinePrcGroupView.as_view(), name="timeline-prc-groups"),
    path("api/v1/timeline/equipments", TimelineEquipmentsView.as_view(), name="timeline-equipments"),
    path(
        "api/v1/timeline/equipment-info/<str:line_id>/<str:eqp_id>",
        TimelineEquipmentInfoView.as_view(),
        name="timeline-equipment-info-line",
    ),
    path(
        "api/v1/timeline/equipment-info/<str:eqp_id>",
        TimelineEquipmentInfoView.as_view(),
        name="timeline-equipment-info",
    ),
    path("api/v1/timeline/logs", TimelineLogsView.as_view(), name="timeline-logs"),
    path("api/v1/timeline/logs/eqp", TimelineEqpLogsView.as_view(), name="timeline-logs-eqp"),
    path("api/v1/timeline/logs/tip", TimelineTipLogsView.as_view(), name="timeline-logs-tip"),
    path("api/v1/timeline/logs/ctttm", TimelineCtttmLogsView.as_view(), name="timeline-logs-ctttm"),
    path("api/v1/timeline/logs/racb", TimelineRacbLogsView.as_view(), name="timeline-logs-racb"),
    path("api/v1/timeline/logs/jira", TimelineJiraLogsView.as_view(), name="timeline-logs-jira"),
    path("api/v1/emails/", EmailListView.as_view(), name="emails-list"),
    path("api/v1/emails/ingest/", EmailIngestTriggerView.as_view(), name="emails-ingest"),
    path("api/v1/emails/bulk-delete/", EmailBulkDeleteView.as_view(), name="emails-bulk-delete"),
    path("api/v1/emails/<int:email_id>/", EmailDetailView.as_view(), name="emails-detail"),
    path("api/v1/emails/<int:email_id>/html/", EmailHtmlView.as_view(), name="emails-html"),
    path("api/v1/appstore/apps", AppStoreAppsView.as_view(), name="appstore-apps"),
    path("api/v1/appstore/apps/<int:app_id>", AppStoreAppDetailView.as_view(), name="appstore-app-detail"),
    path("api/v1/appstore/apps/<int:app_id>/like", AppStoreLikeToggleView.as_view(), name="appstore-app-like"),
    path("api/v1/appstore/apps/<int:app_id>/view", AppStoreViewIncrementView.as_view(), name="appstore-app-view"),
    path(
        "api/v1/appstore/apps/<int:app_id>/comments",
        AppStoreCommentsView.as_view(),
        name="appstore-app-comments",
    ),
    path(
        "api/v1/appstore/apps/<int:app_id>/comments/<int:comment_id>",
        AppStoreCommentDetailView.as_view(),
        name="appstore-app-comment-detail",
    ),
    path("voc/posts", VocPostsView.as_view(), name="voc-posts"),
    path("voc/posts/<int:post_id>", VocPostDetailView.as_view(), name="voc-post-detail"),
    path("voc/posts/<int:post_id>/replies", VocReplyView.as_view(), name="voc-post-reply"),
]
