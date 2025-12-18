from __future__ import annotations

from django.urls import include, path

urlpatterns = [
    path("auth/", include("api.auth.callback_urls")),
    path("api/v1/health/", include("api.health.urls")),
    path("api/v1/auth/", include("api.auth.urls")),
    path("api/v1/activity/", include("api.activity.urls")),
    path("api/v1/tables/", include("api.tables.urls")),
    path("api/v1/line-dashboard/", include("api.drone.urls")),
    path("api/v1/assistant/", include("api.assistant.urls")),
    path("api/v1/timeline/", include("api.timeline.urls")),
    path("api/v1/emails/", include("api.emails.urls")),
    path("api/v1/appstore/", include("api.appstore.urls")),
    path("api/v1/account/", include("api.account.urls")),
    path("api/v1/voc/", include("api.voc.urls")),
]
