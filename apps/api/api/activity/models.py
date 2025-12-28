# =============================================================================
# 모듈 설명: 활동 로그 모델을 정의합니다.
# - 주요 클래스: ActivityLog
# - 불변 조건: created_at은 타임존 인식(UTC) 값입니다.
# =============================================================================
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

    def __str__(self) -> str:  # 디버깅용 문자열(커버리지 제외): pragma: no cover
        """디버깅용 표시 문자열을 반환합니다."""
        username = self.user.get_username() if self.user else "anonymous"
        return f"{self.method} {self.path} by {username} -> {self.status_code}"


__all__ = ["ActivityLog"]
