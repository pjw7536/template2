"""Keycloak shadow User의 읽기 전용 Django admin 표시를 정의합니다."""

from django.contrib import admin

from .models import User


@admin.register(User)
class ShadowUserAdmin(admin.ModelAdmin):
    """Keycloak에서 동기화된 사용자 snapshot을 조회 전용으로 표시합니다."""

    list_display = (
        "sabun",
        "knox_id",
        "email",
        "keycloak_group_id",
        "keycloak_synced_at",
        "is_active",
    )
    list_filter = ("is_active",)
    search_fields = ("sabun", "knox_id", "email", "keycloak_subject")

    def get_readonly_fields(self, request, obj=None):
        """모든 shadow field를 읽기 전용으로 반환합니다."""

        return tuple(field.name for field in self.model._meta.fields)

    def has_add_permission(self, request):
        """Django에서 shadow User 생성을 차단합니다."""

        return False

    def has_change_permission(self, request, obj=None):
        """목록 조회만 허용하고 직접 변경을 차단합니다."""

        return obj is None and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        """Django에서 shadow User 삭제를 차단합니다."""

        return False
