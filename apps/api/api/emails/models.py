from __future__ import annotations

from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django.utils import timezone


class Email(models.Model):
    """수신 메일 저장 모델 (RAG doc 연동)."""

    class ClassificationSource(models.TextChoices):
        CONFIRMED_USER = "CONFIRMED_USER", "Confirmed User"
        PREDICTED_EXTERNAL = "PREDICTED_EXTERNAL", "Predicted External"
        UNASSIGNED = "UNASSIGNED", "Unassigned"

    class RagIndexStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        INDEXED = "INDEXED", "Indexed"
        SKIPPED = "SKIPPED", "Skipped"

    message_id = models.CharField(max_length=255, unique=True)
    received_at = models.DateTimeField()
    subject = models.TextField()
    sender = models.TextField()
    sender_id = models.CharField(max_length=50, db_index=True)  # KNOX ID(loginid) 등 발신자 식별자
    recipient = ArrayField(models.TextField(), null=True, blank=True)
    cc = ArrayField(models.TextField(), null=True, blank=True)
    participants_search = models.TextField(null=True, blank=True)

    user_sdwt_prod = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    classification_source = models.CharField(
        max_length=24,
        choices=ClassificationSource.choices,
        default=ClassificationSource.UNASSIGNED,
    )
    rag_index_status = models.CharField(
        max_length=16,
        choices=RagIndexStatus.choices,
        default=RagIndexStatus.SKIPPED,
    )

    body_text = models.TextField(blank=True)  # RAG 검색/스니펫용 텍스트
    body_html_gzip = models.BinaryField(null=True, blank=True)  # UI 렌더용 gzip HTML

    rag_doc_id = models.CharField(max_length=255, null=True, blank=True, unique=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "emails_inbox"
        indexes = [
            GinIndex(fields=["recipient"], name="idx_emails_inbox_recipient_gin"),
            GinIndex(fields=["cc"], name="idx_emails_inbox_cc_gin"),
            GinIndex(
                fields=["participants_search"],
                name="idx_emails_inbox_part_trgm",
                opclasses=["gin_trgm_ops"],
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        recipient_text = ", ".join(self.recipient or [])
        return f"{self.subject[:40]} ({self.sender} -> {recipient_text}) [{self.user_sdwt_prod or ''}]"

class EmailOutbox(models.Model):
    """RAG 인덱싱/삭제 요청을 비동기 처리하기 위한 Outbox 모델."""

    class Action(models.TextChoices):
        INDEX = "INDEX", "Index"
        DELETE = "DELETE", "Delete"
        RECLASSIFY = "RECLASSIFY", "Reclassify"
        RECLASSIFY_ALL = "RECLASSIFY_ALL", "Reclassify All"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PROCESSING = "PROCESSING", "Processing"
        DONE = "DONE", "Done"
        FAILED = "FAILED", "Failed"

    email = models.ForeignKey(Email, null=True, blank=True, on_delete=models.SET_NULL, related_name="outbox_items")
    action = models.CharField(max_length=16, choices=Action.choices)
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    retry_count = models.PositiveIntegerField(default=0)
    available_at = models.DateTimeField(default=timezone.now)
    last_error = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "emails_outbox"
        indexes = [
            models.Index(fields=["status", "available_at"], name="idx_emails_outbox_status_time"),
        ]


__all__ = ["Email", "EmailOutbox"]
