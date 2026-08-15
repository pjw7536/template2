"""Work Hub 연동 상태를 확인하는 Django admin 설정입니다."""

from django.contrib import admin

from .models import (
    GristAccessSyncOutbox,
    GristDocumentScope,
    GristTaskLink,
    GristWebhookReceipt,
)


class ReadOnlyWorkHubAdmin(admin.ModelAdmin):
    """Work Hub 운영 상태를 서비스 경로 밖에서 변경하지 못하게 합니다."""

    def get_readonly_fields(self, request, obj=None):
        """모델의 모든 DB field를 상세 화면에서 조회 전용으로 표시합니다."""

        return tuple(field.name for field in self.model._meta.fields)

    def has_add_permission(self, request):
        """검증과 Outbox 적재를 우회하는 Admin 생성을 차단합니다."""

        return False

    def has_change_permission(self, request, obj=None):
        """목록 조회 권한은 유지하되 개별 레코드 직접 변경은 차단합니다."""

        if obj is not None:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        """운영 이력과 mapping의 Admin 직접 삭제를 차단합니다."""

        return False


@admin.register(GristDocumentScope)
class GristDocumentScopeAdmin(ReadOnlyWorkHubAdmin):
    """소속별 Grist document mapping을 조회합니다."""

    list_display = ("keycloak_group_id", "doc_id", "template_revision", "is_active", "updated_at")
    list_filter = ("is_active", "template_revision")
    search_fields = ("keycloak_group_id", "doc_id")


@admin.register(GristAccessSyncOutbox)
class GristAccessSyncOutboxAdmin(ReadOnlyWorkHubAdmin):
    """Portal 기준 Grist 접근 권한 동기화 상태를 조회합니다."""

    list_display = (
        "document_scope",
        "reason",
        "status",
        "retry_count",
        "available_at",
        "updated_at",
    )
    list_filter = ("status", "reason")
    search_fields = ("document_scope__doc_id", "document_scope__keycloak_group_id")


@admin.register(GristWebhookReceipt)
class GristWebhookReceiptAdmin(ReadOnlyWorkHubAdmin):
    """Webhook 멱등 처리 결과를 읽기 중심으로 제공합니다."""

    list_display = (
        "event_id",
        "event_type",
        "doc_id",
        "table_id",
        "row_id",
        "status",
        "attempt_count",
        "available_at",
    )
    list_filter = ("status", "event_type")
    search_fields = ("event_id", "doc_id")


@admin.register(GristTaskLink)
class GristTaskLinkAdmin(ReadOnlyWorkHubAdmin):
    """WorkLog와 Task의 자동 연결을 조회합니다."""

    list_display = ("document_scope", "worklog_row_id", "task_row_id", "updated_at")
    search_fields = ("task_key",)
