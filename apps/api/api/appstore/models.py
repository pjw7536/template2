from __future__ import annotations

from django.conf import settings
from django.db import models


class AppStoreApp(models.Model):
    """내부 Appstore 앱 메타데이터."""

    name = models.CharField(max_length=255)
    category = models.CharField(max_length=100)
    description = models.TextField(blank=True, default="")
    url = models.TextField()
    screenshot_url = models.TextField(blank=True, default="")
    screenshot_base64 = models.TextField(blank=True, default="")
    screenshot_mime_type = models.CharField(max_length=100, blank=True, default="")
    screenshot_gallery = models.JSONField(default=list, blank=True)
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

    @property
    def screenshot_src(self) -> str:
        """스크린샷 표시용 src(data url 또는 외부 URL)를 반환합니다."""

        if self.screenshot_url:
            return self.screenshot_url
        if self.screenshot_base64:
            mime_type = self.screenshot_mime_type or "image/png"
            return f"data:{mime_type};base64,{self.screenshot_base64}"
        return ""

    def screenshot_gallery_srcs(self) -> list[str]:
        """갤러리(추가 스크린샷) 표시용 src 목록을 반환합니다."""

        raw = self.screenshot_gallery
        if not isinstance(raw, list):
            return []

        srcs: list[str] = []
        for item in raw:
            if not isinstance(item, dict):
                continue

            url = item.get("url")
            if isinstance(url, str) and url.strip():
                srcs.append(url.strip())
                continue

            base64_value = item.get("base64")
            if isinstance(base64_value, str) and base64_value.strip():
                mime_type = item.get("mime_type")
                if not isinstance(mime_type, str) or not mime_type.strip():
                    mime_type = "image/png"
                srcs.append(f"data:{mime_type};base64,{base64_value.strip()}")

        return srcs

    def screenshot_srcs(self) -> list[str]:
        """대표 스크린샷 + 갤러리 스크린샷 src 목록을 반환합니다."""

        cover = self.screenshot_src
        gallery = self.screenshot_gallery_srcs()
        if cover:
            return [cover, *gallery]
        return gallery


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
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="replies",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appstore_comments",
    )
    content = models.TextField()
    like_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "appstore_comment"
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(fields=["app"], name="appstore_comment_app_idx"),
            models.Index(fields=["app", "created_at"], name="appstore_comment_created_idx"),
            models.Index(fields=["parent"], name="appstore_comment_parent_idx"),
        ]

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return f"Comment {self.pk} on app {self.app_id}"


class AppStoreCommentLike(models.Model):
    """댓글 좋아요(토글) 기록."""

    comment = models.ForeignKey(
        AppStoreComment,
        on_delete=models.CASCADE,
        related_name="likes",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="appstore_comment_likes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "appstore_comment_like"
        constraints = [
            models.UniqueConstraint(
                fields=["comment", "user"],
                name="uniq_appstore_cmtlike_cmt_user",
            ),
        ]
        indexes = [
            models.Index(fields=["user"], name="idx_appstore_cmtlike_user"),
            models.Index(fields=["comment"], name="idx_appstore_cmtlike_comment"),
        ]

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return f"{self.user_id} -> {self.comment_id}"


__all__ = [
    "AppStoreApp",
    "AppStoreComment",
    "AppStoreCommentLike",
    "AppStoreLike",
]
