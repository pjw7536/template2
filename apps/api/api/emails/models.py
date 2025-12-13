from __future__ import annotations

from django.db import models


class Email(models.Model):
    """수신 메일 저장 모델 (RAG doc 연동)."""

    message_id = models.CharField(max_length=255, unique=True)
    received_at = models.DateTimeField()
    subject = models.TextField()
    sender = models.TextField()
    sender_id = models.CharField(max_length=50, db_index=True)  # KNOX ID(loginid) 등 발신자 식별자
    recipient = models.TextField()

    user_sdwt_prod = models.CharField(max_length=64, null=True, blank=True, db_index=True)

    body_text = models.TextField(blank=True)  # RAG 검색/스니펫용 텍스트
    body_html_gzip = models.BinaryField(null=True, blank=True)  # UI 렌더용 gzip HTML

    rag_doc_id = models.CharField(max_length=255, null=True, blank=True, unique=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "emails_inbox"

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return f"{self.subject[:40]} ({self.sender} -> {self.recipient}) [{self.user_sdwt_prod or ''}]"


class SenderSdwtHistory(models.Model):
    """sender_id 기준 소속 이력 (시점별 line/user_sdwt_prod)."""

    sender_id = models.CharField(max_length=50, db_index=True)
    effective_from = models.DateTimeField()  # 이 시점부터 line/user_sdwt_prod 적용
    department = models.CharField(max_length=50, null=True, blank=True)
    line = models.CharField(max_length=64, null=True, blank=True)
    user_sdwt_prod = models.CharField(max_length=64, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=50, default="")

    class Meta:
        db_table = "emails_sender_sdwt_history"
        indexes = [
            models.Index(fields=["sender_id", "effective_from"], name="sender_sdwt_effective"),
            models.Index(fields=["user_sdwt_prod"], name="sender_sdwt_user_sdwt"),
        ]
        unique_together = ("sender_id", "effective_from")

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return f"{self.sender_id} -> {self.user_sdwt_prod or ''} ({self.effective_from.isoformat()})"


__all__ = ["Email", "SenderSdwtHistory"]
