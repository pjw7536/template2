from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class ActivityLog(models.Model):
    """사용자 요청/응답의 핵심 정보를 저장하는 활동 로그 모델입니다."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=255)
    path = models.CharField(max_length=512)
    method = models.CharField(max_length=10)
    status_code = models.PositiveIntegerField(default=200)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = "activity_log"
        ordering = ["-created_at"]

    def __str__(self) -> str:  # pragma: no cover - debugging helper
        username = self.user.get_username() if self.user else "anonymous"
        return f"{self.method} {self.path} by {username} -> {self.status_code}"


__all__ = ["ActivityLog"]
