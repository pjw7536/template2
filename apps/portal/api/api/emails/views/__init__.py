# =============================================================================
# 모듈 설명: Emails HTTP view의 명시적 public facade입니다.
# =============================================================================

from .content import EmailAssetView, EmailDetailView, EmailHtmlView
from .lists import EmailInboxListView, EmailSentListView
from .mailboxes import (
    EmailMailboxListView,
    EmailMailboxMembersView,
    EmailMailboxSummaryView,
    EmailUnassignedClaimView,
    EmailUnassignedSummaryView,
)
from .mutations import EmailBulkDeleteView, EmailMoveView
from .ocr import EmailAssetOcrClaimView, EmailAssetOcrUpdateView
from .triggers import EmailIngestTriggerView, EmailOutboxProcessTriggerView

__all__ = [
    "EmailAssetOcrClaimView",
    "EmailAssetOcrUpdateView",
    "EmailAssetView",
    "EmailBulkDeleteView",
    "EmailDetailView",
    "EmailHtmlView",
    "EmailIngestTriggerView",
    "EmailInboxListView",
    "EmailMailboxListView",
    "EmailMailboxMembersView",
    "EmailMailboxSummaryView",
    "EmailMoveView",
    "EmailOutboxProcessTriggerView",
    "EmailSentListView",
    "EmailUnassignedClaimView",
    "EmailUnassignedSummaryView",
]
