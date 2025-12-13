from __future__ import annotations

from django.urls import path

from .views import (
    EmailBulkDeleteView,
    EmailDetailView,
    EmailHtmlView,
    EmailIngestTriggerView,
    EmailListView,
    EmailMailboxListView,
    EmailUnassignedClaimView,
    EmailUnassignedSummaryView,
)

urlpatterns = [
    path("", EmailListView.as_view(), name="emails-list"),
    path("mailboxes/", EmailMailboxListView.as_view(), name="emails-mailboxes"),
    path("unassigned/", EmailUnassignedSummaryView.as_view(), name="emails-unassigned-summary"),
    path("unassigned/claim/", EmailUnassignedClaimView.as_view(), name="emails-unassigned-claim"),
    path("ingest/", EmailIngestTriggerView.as_view(), name="emails-ingest"),
    path("bulk-delete/", EmailBulkDeleteView.as_view(), name="emails-bulk-delete"),
    path("<int:email_id>/", EmailDetailView.as_view(), name="emails-detail"),
    path("<int:email_id>/html/", EmailHtmlView.as_view(), name="emails-html"),
]
