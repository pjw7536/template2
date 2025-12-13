from __future__ import annotations

from django.conf import settings
from django.db import models


class AppStoreApp(models.Model):
    """내부 Appstore 앱 메타데이터."""

    name = models.CharField(max_length=255)
    category = models.CharField(max_length=100)
    description = models.TextField(blank=True, default="")
    url = models.TextField()
    tags = models.JSONField(default=list, blank=True)
    badge = models.CharField(max_length=64, blank=True, default="")
    contact_name = models.CharField(max_length=255, blank=True, default="")
    contact_knoxid = models.CharField(max_length=255, blank=True, default="")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appstore_apps",
    )
    view_count = models.PositiveIntegerField(default=0)
    like_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "appstore_app"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["category"], name="appstore_app_category_idx"),
            models.Index(fields=["name"], name="appstore_app_name_idx"),
        ]

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return self.name


class AppStoreLike(models.Model):
    """앱 좋아요(토글) 기록."""

    app = models.ForeignKey(
        AppStoreApp,
        on_delete=models.CASCADE,
        related_name="likes",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="appstore_likes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "appstore_like"
        unique_together = ("app", "user")
        indexes = [
            models.Index(fields=["user"], name="appstore_like_user_idx"),
            models.Index(fields=["app"], name="appstore_like_app_idx"),
        ]

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return f"{self.user_id} -> {self.app_id}"


class AppStoreComment(models.Model):
    """앱 댓글."""

    app = models.ForeignKey(
        AppStoreApp,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appstore_comments",
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "appstore_comment"
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(fields=["app"], name="appstore_comment_app_idx"),
            models.Index(fields=["app", "created_at"], name="appstore_comment_created_idx"),
        ]

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return f"Comment {self.pk} on app {self.app_id}"


__all__ = [
    "AppStoreApp",
    "AppStoreComment",
    "AppStoreLike",
]

