# =============================================================================
# 모듈 설명: VOC API의 입력 검증과 출력 계약을 정의합니다.
# - 주요 클래스: 게시글/답변 입력 serializer, 게시글/답변 출력 serializer
# - 불변 조건: HTTP JSON 필드는 camelCase 계약 하나만 사용합니다.
# =============================================================================

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from rest_framework import serializers

from .models import VocPost


def _build_user_display_name(user: Any) -> str:
    """사용자 이름과 Knox ID로 VOC 작성자 표시 이름을 생성합니다."""

    username = getattr(user, "username", None)
    username = username.strip() if isinstance(username, str) else ""
    knox_id = getattr(user, "knox_id", None)
    knox_id = knox_id.strip() if isinstance(knox_id, str) else ""

    if username and knox_id:
        return f"{username}({knox_id})"
    return username or knox_id


class StrictSerializer(serializers.Serializer):
    """VOC의 canonical 계약에 선언되지 않은 입력 필드를 거절합니다."""

    def to_internal_value(self, data):
        """알 수 없는 필드를 검증한 뒤 DRF 기본 변환을 수행합니다."""

        if isinstance(data, Mapping):
            unexpected_fields = sorted(set(data) - set(self.fields))
            if unexpected_fields:
                raise serializers.ValidationError(
                    {
                        field: ["This field is not allowed."]
                        for field in unexpected_fields
                    }
                )
        return super().to_internal_value(data)


class VocPostCreateInputSerializer(StrictSerializer):
    """VOC 게시글 생성 payload를 검증합니다."""

    title = serializers.CharField(
        max_length=VocPost._meta.get_field("title").max_length,
        error_messages={
            "blank": "title is required",
            "required": "title is required",
            "max_length": "title is too long",
        },
    )
    content = serializers.CharField(
        error_messages={"blank": "content is required", "required": "content is required"}
    )
    status = serializers.ChoiceField(
        choices=VocPost.Status.choices,
        default=VocPost.Status.RECEIVED,
        error_messages={"invalid_choice": "Invalid status value"},
    )


class VocPostUpdateInputSerializer(StrictSerializer):
    """VOC 게시글에서 변경할 필드만 검증합니다."""

    title = serializers.CharField(
        required=False,
        max_length=VocPost._meta.get_field("title").max_length,
        error_messages={"blank": "title is required", "max_length": "title is too long"},
    )
    content = serializers.CharField(
        required=False,
        error_messages={"blank": "content is required"},
    )
    status = serializers.ChoiceField(
        required=False,
        choices=VocPost.Status.choices,
        error_messages={"invalid_choice": "Invalid status value"},
    )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """변경 필드가 하나 이상인지 확인합니다."""

        if not attrs:
            raise serializers.ValidationError("No changes provided")
        return attrs


class VocReplyCreateInputSerializer(StrictSerializer):
    """VOC 답변 생성 payload를 검증합니다."""

    content = serializers.CharField(
        error_messages={"blank": "content is required", "required": "content is required"}
    )


class VocUserOutputSerializer(serializers.Serializer):
    """VOC 작성자를 canonical 응답 형태로 직렬화합니다."""

    id = serializers.IntegerField(read_only=True)
    name = serializers.SerializerMethodField()

    def get_name(self, user: Any) -> str:
        """작성자 표시 이름을 반환합니다."""

        return _build_user_display_name(user)


class VocReplyOutputSerializer(serializers.Serializer):
    """VOC 답변을 canonical 응답 형태로 직렬화합니다."""

    id = serializers.IntegerField(read_only=True)
    postId = serializers.IntegerField(source="post_id", read_only=True)
    content = serializers.CharField(read_only=True)
    createdAt = serializers.SerializerMethodField()
    author = serializers.SerializerMethodField()

    def get_createdAt(self, reply: Any) -> str:  # noqa: N802 - HTTP camelCase 계약
        """답변 생성 시각을 ISO 8601 문자열로 반환합니다."""

        return reply.created_at.isoformat()

    def get_author(self, reply: Any) -> dict[str, Any] | None:
        """답변 작성자 payload를 반환합니다."""

        author = getattr(reply, "author", None)
        return VocUserOutputSerializer(author).data if author else None


class VocPostOutputSerializer(serializers.Serializer):
    """VOC 게시글을 canonical 응답 형태로 직렬화합니다."""

    id = serializers.IntegerField(read_only=True)
    title = serializers.CharField(read_only=True)
    content = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    createdAt = serializers.SerializerMethodField()
    updatedAt = serializers.SerializerMethodField()
    author = serializers.SerializerMethodField()
    replies = serializers.SerializerMethodField()

    def get_createdAt(self, post: Any) -> str:  # noqa: N802 - HTTP camelCase 계약
        """게시글 생성 시각을 ISO 8601 문자열로 반환합니다."""

        return post.created_at.isoformat()

    def get_updatedAt(self, post: Any) -> str:  # noqa: N802 - HTTP camelCase 계약
        """게시글 수정 시각을 ISO 8601 문자열로 반환합니다."""

        return post.updated_at.isoformat()

    def get_author(self, post: Any) -> dict[str, Any] | None:
        """게시글 작성자 payload를 반환합니다."""

        author = getattr(post, "author", None)
        return VocUserOutputSerializer(author).data if author else None

    def get_replies(self, post: Any) -> list[dict[str, Any]]:
        """게시글 답변 목록을 생성 순서대로 반환합니다."""

        related = getattr(post, "replies", None)
        if related is None:
            return []
        return list(VocReplyOutputSerializer(related.all(), many=True).data)


__all__ = [
    "VocPostCreateInputSerializer",
    "VocPostOutputSerializer",
    "VocPostUpdateInputSerializer",
    "VocReplyCreateInputSerializer",
    "VocReplyOutputSerializer",
]
