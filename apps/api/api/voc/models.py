from __future__ import annotations

from django.conf import settings
from django.db import models


class VocPost(models.Model):
    """VOC 게시글(제목/내용/상태/작성자)을 저장하는 모델입니다."""

    class Status(models.TextChoices):
        RECEIVED = "접수", "접수"
        IN_PROGRESS = "진행중", "진행중"
        DONE = "완료", "완료"
        REJECTED = "반려", "반려"

    title = models.CharField(max_length=255)
    content = models.TextField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.RECEIVED)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="voc_posts",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "voc_post"
        ordering = ["-created_at"]

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return f"[{self.status}] {self.title}"


class VocReply(models.Model):
    """VOC 게시글에 대한 답변(댓글) 모델입니다."""

    post = models.ForeignKey(VocPost, on_delete=models.CASCADE, related_name="replies")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="voc_replies",
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "voc_reply"
        ordering = ["created_at"]

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return f"Reply to {self.post_id}"


__all__ = ["VocPost", "VocReply"]
