from __future__ import annotations

from django.urls import path

from .views import (
    EmailBulkDeleteView,
    EmailDetailView,
    EmailHtmlView,
    EmailIngestTriggerView,
    EmailInboxListView,
    EmailMailboxListView,
    EmailMailboxMembersView,
    EmailMoveView,
    EmailOutboxProcessTriggerView,
    EmailSentListView,
    EmailUnassignedClaimView,
    EmailUnassignedSummaryView,
)

urlpatterns = [
    path("inbox/", EmailInboxListView.as_view(), name="emails-inbox"),
    path("sent/", EmailSentListView.as_view(), name="emails-sent"),
    path("mailboxes/", EmailMailboxListView.as_view(), name="emails-mailboxes"),
    path("mailboxes/members/", EmailMailboxMembersView.as_view(), name="emails-mailbox-members"),
    path("unassigned/", EmailUnassignedSummaryView.as_view(), name="emails-unassigned-summary"),
    path("unassigned/claim/", EmailUnassignedClaimView.as_view(), name="emails-unassigned-claim"),
    path("ingest/", EmailIngestTriggerView.as_view(), name="emails-ingest"),
    path("outbox/process/", EmailOutboxProcessTriggerView.as_view(), name="emails-outbox-process"),
    path("bulk-delete/", EmailBulkDeleteView.as_view(), name="emails-bulk-delete"),
    path("move/", EmailMoveView.as_view(), name="emails-move"),
    path("<int:email_id>/", EmailDetailView.as_view(), name="emails-detail"),
    path("<int:email_id>/html/", EmailHtmlView.as_view(), name="emails-html"),
]
