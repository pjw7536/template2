from __future__ import annotations

from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.db import models


class Email(models.Model):
    """수신 메일 저장 모델 (RAG doc 연동)."""

    message_id = models.CharField(max_length=255, unique=True)
    received_at = models.DateTimeField()
    subject = models.TextField()
    sender = models.TextField()
    sender_id = models.CharField(max_length=50, db_index=True)  # KNOX ID(loginid) 등 발신자 식별자
    recipient = ArrayField(models.TextField(), null=True, blank=True)
    cc = ArrayField(models.TextField(), null=True, blank=True)
    participants_search = models.TextField(null=True, blank=True)

    user_sdwt_prod = models.CharField(max_length=64, null=True, blank=True, db_index=True)

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


__all__ = ["Email"]
