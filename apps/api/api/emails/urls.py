from __future__ import annotations

from django.urls import path

from .views import (
    EmailBulkDeleteView,
    EmailDetailView,
    EmailHtmlView,
    EmailIngestTriggerView,
    EmailListView,
)

urlpatterns = [
    path("", EmailListView.as_view(), name="emails-list"),
    path("ingest/", EmailIngestTriggerView.as_view(), name="emails-ingest"),
    path("bulk-delete/", EmailBulkDeleteView.as_view(), name="emails-bulk-delete"),
    path("<int:email_id>/", EmailDetailView.as_view(), name="emails-detail"),
    path("<int:email_id>/html/", EmailHtmlView.as_view(), name="emails-html"),
]

