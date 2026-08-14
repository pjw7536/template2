"""Work Hub의 Grist 실행 상태를 보관하는 모델입니다."""

from __future__ import annotations

from django.db import models
from django.utils import timezone


class GristDocumentScope(models.Model):
    """Portal 소속과 Grist document/table 식별자를 연결합니다."""

    affiliation = models.ForeignKey(
        "account.Affiliation",
        on_delete=models.PROTECT,
        related_name="grist_document_scopes",
    )
    workspace_id = models.PositiveBigIntegerField()
    doc_id = models.CharField(max_length=128)
    equipment_table_id = models.CharField(max_length=64, default="Equipment")
    worklog_table_id = models.CharField(max_length=64, default="WorkLog")
    task_table_id = models.CharField(max_length=64, default="Task")
    launch_url = models.URLField(max_length=500)
    template_revision = models.CharField(max_length=64, default="grist-work-hub-v1")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "work_hub_grist_document_scope"
        constraints = [
            models.UniqueConstraint(
                fields=["affiliation"],
                name="uniq_wrk_hub_doc_scp_aff",
            ),
            models.UniqueConstraint(
                fields=["doc_id"],
                name="uniq_wrk_hub_doc_scp_doc",
            ),
        ]
        indexes = [
            models.Index(fields=["is_active"], name="idx_wrk_hub_doc_scp_act"),
        ]

    def __str__(self) -> str:
        """관리 화면에 소속과 Grist document ID를 표시합니다."""

        return f"{self.affiliation.user_sdwt_prod} -> {self.doc_id}"


class GristAccessSyncOutbox(models.Model):
    """Portal 소속 권한을 Grist에 재시도 가능하게 투영하는 Outbox입니다."""

    class Status(models.TextChoices):
        """접근 권한 동기화 작업 상태입니다."""

        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"
        TERMINAL = "terminal", "Terminal"

    document_scope = models.ForeignKey(
        GristDocumentScope,
        on_delete=models.CASCADE,
        related_name="access_sync_outbox_items",
    )
    reason = models.CharField(max_length=64, default="portal_access_changed")
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    retry_count = models.PositiveIntegerField(default=0)
    available_at = models.DateTimeField(default=timezone.now)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "work_hub_grist_access_sync_outbox"
        indexes = [
            models.Index(
                fields=["status", "available_at"],
                name="idx_wrk_hub_gr_acc_sts",
            ),
            models.Index(
                fields=["document_scope", "created_at"],
                name="idx_wrk_hub_gr_acc_scp",
            ),
        ]

    def __str__(self) -> str:
        """관리 화면에 document와 동기화 상태를 표시합니다."""

        return f"{self.document_scope.doc_id} ({self.status})"


class GristWebhookReceipt(models.Model):
    """Grist Webhook의 비동기 payload와 멱등 처리 상태를 보관합니다."""

    class Status(models.TextChoices):
        """Webhook 처리 상태입니다."""

        RECEIVED = "received", "Received"
        PROCESSING = "processing", "Processing"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"
        TERMINAL = "terminal", "Terminal"

    event_id = models.CharField(max_length=128, unique=True)
    event_type = models.CharField(max_length=64, default="rows.changed")
    doc_id = models.CharField(max_length=128)
    table_id = models.CharField(max_length=64)
    row_id = models.PositiveBigIntegerField(null=True, blank=True)
    payload_hash = models.CharField(max_length=64)
    payload = models.JSONField(default=dict)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.RECEIVED,
    )
    attempt_count = models.PositiveIntegerField(default=0)
    available_at = models.DateTimeField(default=timezone.now)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "work_hub_grist_webhook_receipt"
        indexes = [
            models.Index(
                fields=["status", "processed_at"],
                name="idx_wrk_hub_hook_sts_prc",
            ),
            models.Index(
                fields=["status", "available_at"],
                name="idx_wrk_hub_hook_sts_avl",
            ),
            models.Index(
                fields=["doc_id", "table_id", "row_id"],
                name="idx_wrk_hub_hook_doc_tbl_row",
            ),
        ]

    def __str__(self) -> str:
        """관리 화면에 event ID와 상태를 표시합니다."""

        return f"{self.event_id} ({self.status})"


class GristTaskLink(models.Model):
    """WorkLog row와 자동 생성된 Task row의 멱등 연결을 저장합니다."""

    document_scope = models.ForeignKey(
        GristDocumentScope,
        on_delete=models.CASCADE,
        related_name="task_links",
    )
    worklog_row_id = models.PositiveBigIntegerField()
    task_row_id = models.PositiveBigIntegerField(null=True, blank=True)
    task_key = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "work_hub_grist_task_link"
        constraints = [
            models.UniqueConstraint(
                fields=["document_scope", "worklog_row_id"],
                name="uniq_wrk_hub_task_scp_wrk",
            ),
        ]
        indexes = [
            models.Index(fields=["worklog_row_id"], name="idx_wrk_hub_task_wrk"),
        ]

    def __str__(self) -> str:
        """관리 화면에 WorkLog와 Task row ID를 표시합니다."""

        return f"{self.worklog_row_id} -> {self.task_row_id}"
