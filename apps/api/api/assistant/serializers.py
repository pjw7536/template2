# =============================================================================
# 모듈: 어시스턴트 요청 직렬화/검증
# 주요 클래스: AssistantChatRequestSerializer
# =============================================================================
"""어시스턴트 요청 입력 검증을 담당합니다."""
from __future__ import annotations

import json
from typing import Any, Dict

from django.core import signing
from rest_framework import serializers

from .models import (
    AssistantConversation,
    AssistantGeneration,
    AssistantMessage,
    AssistantMessageFeedback,
)

ASSISTANT_CURSOR_SALT = "assistant.cursor.v1"
MAX_ASSISTANT_MESSAGE_CHARS = 10_000
MAX_ASSISTANT_MESSAGE_BATCH_SIZE = 20
MAX_ASSISTANT_HISTORY_MESSAGES = 20
MAX_ASSISTANT_SOURCES = 50
MAX_ASSISTANT_SOURCES_JSON_BYTES = 50 * 1024
MAX_ASSISTANT_CONTEXT_SNAPSHOT_JSON_BYTES = 100 * 1024


def _json_size_bytes(value: object) -> int:
    """JSON 값을 전송 기준 UTF-8 byte 크기로 계산합니다."""

    return len(
        json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )


def encode_assistant_cursor(kind: str, payload: dict[str, object]) -> str:
    """페이지 종류를 포함한 opaque signed cursor를 생성합니다."""

    return signing.dumps(
        {"kind": kind, **payload},
        salt=ASSISTANT_CURSOR_SALT,
        compress=True,
    )


def decode_assistant_cursor(value: str, *, expected_kind: str) -> dict[str, object]:
    """signed cursor를 검증하고 요청 페이지 종류와 일치하는 payload를 반환합니다."""

    try:
        payload = signing.loads(value, salt=ASSISTANT_CURSOR_SALT)
    except signing.BadSignature as exc:
        raise serializers.ValidationError("cursor 형식이 올바르지 않습니다.") from exc
    if not isinstance(payload, dict) or payload.get("kind") != expected_kind:
        raise serializers.ValidationError("현재 목록에서 사용할 수 없는 cursor입니다.")
    return payload


class AssistantChatHistoryMessageSerializer(serializers.Serializer):
    """모델에 전달할 이전 대화 한 건을 검증합니다."""

    role = serializers.CharField(trim_whitespace=True, max_length=16)
    content = serializers.CharField(
        trim_whitespace=True,
        max_length=MAX_ASSISTANT_MESSAGE_CHARS,
    )


class AssistantChatRequestSerializer(serializers.Serializer):
    """어시스턴트 채팅 요청을 검증합니다."""

    prompt = serializers.CharField(
        allow_blank=True,
        trim_whitespace=True,
        max_length=MAX_ASSISTANT_MESSAGE_CHARS,
        error_messages={"required": "prompt is required"},
    )
    room_id = serializers.JSONField(required=False)
    permission_groups = serializers.JSONField(required=False)
    rag_index_name = serializers.JSONField(required=False)
    history = AssistantChatHistoryMessageSerializer(
        many=True,
        required=False,
        allow_empty=True,
        max_length=MAX_ASSISTANT_HISTORY_MESSAGES,
    )
    context_key = serializers.CharField(
        required=False,
        allow_blank=False,
        max_length=512,
        default="assistant",
    )

    def to_internal_value(self, data: Any) -> Dict[str, Any]:
        """카멜/스네이크 케이스 입력을 내부 필드로 정규화합니다."""

        if not isinstance(data, dict):
            raise serializers.ValidationError("Invalid JSON body")

        normalized: Dict[str, Any] = {}

        if "prompt" in data:
            prompt_value = data.get("prompt")
            if prompt_value is None or not isinstance(prompt_value, str):
                raise serializers.ValidationError({"prompt": ["prompt is required"]})
            normalized["prompt"] = prompt_value

        if "roomId" in data:
            room_id_value = data.get("roomId")
            if room_id_value is not None:
                normalized["room_id"] = room_id_value
        elif "room_id" in data:
            room_id_value = data.get("room_id")
            if room_id_value is not None:
                normalized["room_id"] = room_id_value

        if "permissionGroups" in data:
            permission_groups_value = data.get("permissionGroups")
            if permission_groups_value is not None:
                normalized["permission_groups"] = permission_groups_value
        elif "permission_groups" in data:
            permission_groups_value = data.get("permission_groups")
            if permission_groups_value is not None:
                normalized["permission_groups"] = permission_groups_value

        if "ragIndexName" in data:
            rag_index_value = data.get("ragIndexName")
            if rag_index_value is not None:
                normalized["rag_index_name"] = rag_index_value
        elif "rag_index_name" in data:
            rag_index_value = data.get("rag_index_name")
            if rag_index_value is not None:
                normalized["rag_index_name"] = rag_index_value

        if "history" in data:
            history_value = data.get("history")
            if history_value is not None:
                normalized["history"] = history_value

        if "contextKey" in data:
            context_key_value = data.get("contextKey")
            if context_key_value is not None:
                normalized["context_key"] = context_key_value
        elif "context_key" in data:
            context_key_value = data.get("context_key")
            if context_key_value is not None:
                normalized["context_key"] = context_key_value

        return super().to_internal_value(normalized)

    def validate_prompt(self, value: object) -> str:
        """prompt가 공백/빈 문자열이 아닌지 확인합니다."""

        if not isinstance(value, str):
            raise serializers.ValidationError("prompt is required")
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError("prompt is required")
        return cleaned


class AssistantConversationSummaryRequestSerializer(serializers.Serializer):
    """rolling summary를 분리할 메시지 contextKey를 검증합니다."""

    context_key = serializers.CharField(
        required=False,
        allow_blank=False,
        max_length=512,
        default="assistant",
    )

    def to_internal_value(self, data: Any) -> Dict[str, Any]:
        """camelCase contextKey를 내부 snake_case 필드로 정규화합니다."""

        if not isinstance(data, dict):
            raise serializers.ValidationError("Invalid JSON body")
        normalized = dict(data)
        if "contextKey" in data:
            normalized["context_key"] = data.get("contextKey")
        return super().to_internal_value(normalized)


class AssistantConversationCreateSerializer(serializers.Serializer):
    """대화방 생성 요청의 선택적 이름을 검증합니다."""

    name = serializers.CharField(
        required=False,
        allow_blank=True,
        trim_whitespace=True,
        max_length=120,
    )


class AssistantConversationListQuerySerializer(serializers.Serializer):
    """대화방 검색과 cursor pagination query를 검증합니다."""

    search = serializers.CharField(required=False, allow_blank=True, max_length=120)
    cursor = serializers.CharField(required=False, allow_blank=False, max_length=2048)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=50, default=20)
    archived = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """cursor를 해석해 selector 전용 payload로 추가합니다."""

        raw_cursor = attrs.get("cursor")
        attrs["cursor_payload"] = (
            decode_assistant_cursor(raw_cursor, expected_kind="conversations")
            if raw_cursor
            else None
        )
        attrs["search"] = str(attrs.get("search") or "").strip()
        if (
            attrs["cursor_payload"]
            and str(attrs["cursor_payload"].get("search") or "") != attrs["search"]
        ):
            raise serializers.ValidationError(
                {"cursor": "cursor와 현재 검색 조건이 일치하지 않습니다."}
            )
        if (
            attrs["cursor_payload"]
            and bool(attrs["cursor_payload"].get("archived")) != attrs["archived"]
        ):
            raise serializers.ValidationError(
                {"cursor": "cursor와 현재 보관 조건이 일치하지 않습니다."}
            )
        return attrs


class AssistantMessageListQuerySerializer(serializers.Serializer):
    """이전 메시지 cursor pagination query를 검증합니다."""

    before = serializers.CharField(required=False, allow_blank=False, max_length=2048)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=50, default=20)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """before cursor를 해석해 selector 전용 payload로 추가합니다."""

        raw_cursor = attrs.get("before")
        attrs["cursor_payload"] = (
            decode_assistant_cursor(raw_cursor, expected_kind="messages")
            if raw_cursor
            else None
        )
        return attrs


class AssistantConversationSerializer(serializers.ModelSerializer):
    """대화방 metadata를 frontend camelCase 형태로 반환합니다."""

    name = serializers.CharField(source="title")
    createdAt = serializers.DateTimeField(source="created_at")
    updatedAt = serializers.DateTimeField(source="updated_at")
    pinned = serializers.SerializerMethodField()
    archived = serializers.SerializerMethodField()
    pinnedAt = serializers.DateTimeField(source="pinned_at", allow_null=True)
    archivedAt = serializers.DateTimeField(source="archived_at", allow_null=True)

    def get_pinned(self, obj: AssistantConversation) -> bool:
        """고정 시각 존재 여부를 boolean으로 반환합니다."""

        return obj.pinned_at is not None

    def get_archived(self, obj: AssistantConversation) -> bool:
        """보관 시각 존재 여부를 boolean으로 반환합니다."""

        return obj.archived_at is not None

    class Meta:
        """대화방 공개 필드만 정의합니다."""

        model = AssistantConversation
        fields = (
            "id",
            "name",
            "pinned",
            "archived",
            "pinnedAt",
            "archivedAt",
            "createdAt",
            "updatedAt",
        )


class AssistantConversationUpdateSerializer(serializers.Serializer):
    """수동 이름 변경과 고정·보관 상태 갱신을 검증합니다."""

    name = serializers.CharField(
        required=False,
        allow_blank=False,
        trim_whitespace=True,
        max_length=120,
    )
    pinned = serializers.BooleanField(required=False)
    archived = serializers.BooleanField(required=False)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """하나 이상의 갱신 필드를 요구합니다."""

        if not attrs:
            raise serializers.ValidationError("변경할 항목이 없습니다.")
        return attrs


class AssistantMessageInputSerializer(serializers.Serializer):
    """한 개의 대화 메시지 저장 요청을 검증합니다."""

    client_id = serializers.CharField(max_length=128)
    role = serializers.ChoiceField(choices=AssistantMessage.Roles.values)
    content = serializers.CharField(
        trim_whitespace=True,
        max_length=MAX_ASSISTANT_MESSAGE_CHARS,
    )
    context_key = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=512,
        default="assistant",
    )
    sources = serializers.JSONField(required=False, default=list)
    user_sdwt_prod = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=128,
        default="",
    )
    parent_id = serializers.CharField(
        required=False,
        allow_blank=False,
        allow_null=True,
        max_length=128,
    )
    revision_of_id = serializers.CharField(
        required=False,
        allow_blank=False,
        allow_null=True,
        max_length=128,
    )
    generation_id = serializers.UUIDField(required=False, allow_null=True)
    context_snapshot = serializers.JSONField(required=False, allow_null=True)

    def to_internal_value(self, data: Any) -> Dict[str, Any]:
        """메시지의 camelCase 입력을 내부 snake_case 필드로 정규화합니다."""

        if not isinstance(data, dict):
            raise serializers.ValidationError("message must be an object")
        normalized = dict(data)
        if "clientId" in data:
            normalized["client_id"] = data.get("clientId")
        if "contextKey" in data:
            normalized["context_key"] = data.get("contextKey")
        if "userSdwtProd" in data:
            normalized["user_sdwt_prod"] = data.get("userSdwtProd")
        if "parentId" in data:
            normalized["parent_id"] = data.get("parentId")
        if "revisionOfId" in data:
            normalized["revision_of_id"] = data.get("revisionOfId")
        if "generationId" in data:
            normalized["generation_id"] = data.get("generationId")
        if "contextSnapshot" in data:
            normalized["context_snapshot"] = data.get("contextSnapshot")
        return super().to_internal_value(normalized)

    def validate_content(self, value: str) -> str:
        """공백 메시지 저장을 거부합니다."""

        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError("content is required")
        return cleaned

    def validate_sources(self, value: object) -> list[object]:
        """출처 배열의 개수와 직렬화 크기를 제한합니다."""

        if not isinstance(value, list):
            raise serializers.ValidationError("sources must be an array")
        if len(value) > MAX_ASSISTANT_SOURCES:
            raise serializers.ValidationError(
                f"sources는 최대 {MAX_ASSISTANT_SOURCES}개까지 저장할 수 있습니다."
            )
        if _json_size_bytes(value) > MAX_ASSISTANT_SOURCES_JSON_BYTES:
            raise serializers.ValidationError("sources 크기는 최대 50KB까지 허용됩니다.")
        return value

    def validate_context_snapshot(self, value: object) -> dict[str, object] | None:
        """분석 문맥 snapshot은 object 또는 null만 허용합니다."""

        if value is None:
            return None
        if not isinstance(value, dict):
            raise serializers.ValidationError("contextSnapshot must be an object")
        if _json_size_bytes(value) > MAX_ASSISTANT_CONTEXT_SNAPSHOT_JSON_BYTES:
            raise serializers.ValidationError(
                "contextSnapshot 크기는 최대 100KB까지 허용됩니다."
            )
        return value


class AssistantMessageBatchSerializer(serializers.Serializer):
    """대화방에 저장할 하나 이상의 메시지 배열을 검증합니다."""

    messages = AssistantMessageInputSerializer(
        many=True,
        allow_empty=False,
        max_length=MAX_ASSISTANT_MESSAGE_BATCH_SIZE,
    )


class AssistantMessageSerializer(serializers.ModelSerializer):
    """저장 메시지를 ChatWidget에서 사용하는 형태로 반환합니다."""

    id = serializers.CharField(source="client_id")
    contextKey = serializers.CharField(source="context_key")
    userSdwtProd = serializers.CharField(source="user_sdwt_prod")
    createdAt = serializers.DateTimeField(source="created_at")
    parentId = serializers.CharField(source="parent.client_id", allow_null=True)
    revisionOfId = serializers.CharField(
        source="revision_of.client_id",
        allow_null=True,
    )
    generationId = serializers.UUIDField(source="generation_id", allow_null=True)
    contextSnapshot = serializers.SerializerMethodField()
    feedback = serializers.SerializerMethodField()

    def get_contextSnapshot(self, obj: AssistantMessage) -> dict[str, object] | None:
        """업무 분석 snapshot을 frontend 증거 패널 형태로 반환합니다."""

        snapshot = obj.context_snapshot
        if snapshot is None:
            return None
        return {
            "id": str(snapshot.id),
            "kind": snapshot.kind,
            "scope": snapshot.scope,
            "coverage": snapshot.coverage,
            "evidence": snapshot.evidence,
            "createdAt": snapshot.created_at.isoformat(),
        }

    def get_feedback(self, obj: AssistantMessage) -> dict[str, object] | None:
        """현재 메시지의 사용자 평가를 반환합니다."""

        try:
            feedback = obj.feedback
        except AssistantMessageFeedback.DoesNotExist:
            return None
        return {"rating": feedback.rating, "reason": feedback.reason}

    class Meta:
        """메시지 공개 필드와 camelCase 매핑을 정의합니다."""

        model = AssistantMessage
        fields = (
            "id",
            "role",
            "content",
            "contextKey",
            "sources",
            "userSdwtProd",
            "parentId",
            "revisionOfId",
            "generationId",
            "contextSnapshot",
            "feedback",
            "createdAt",
        )


class AssistantGenerationCreateSerializer(serializers.Serializer):
    """답변 생성 lease 획득 요청을 검증합니다."""

    conversation_id = serializers.UUIDField()
    client_request_id = serializers.CharField(max_length=128)
    context_key = serializers.CharField(max_length=512, default="assistant")
    provider = serializers.CharField(required=False, allow_blank=True, max_length=64)
    model_name = serializers.CharField(required=False, allow_blank=True, max_length=200)

    def to_internal_value(self, data: Any) -> Dict[str, Any]:
        """generation 요청의 camelCase 입력을 정규화합니다."""

        if not isinstance(data, dict):
            raise serializers.ValidationError("Invalid JSON body")
        normalized = dict(data)
        for external, internal in (
            ("conversationId", "conversation_id"),
            ("clientRequestId", "client_request_id"),
            ("contextKey", "context_key"),
            ("modelName", "model_name"),
        ):
            if external in data:
                normalized[internal] = data.get(external)
        return super().to_internal_value(normalized)


class AssistantGenerationFinalizeSerializer(serializers.Serializer):
    """답변 생성 lease 종료 상태를 검증합니다."""

    status = serializers.ChoiceField(
        choices=(
            AssistantGeneration.Status.COMPLETED,
            AssistantGeneration.Status.STOPPED,
            AssistantGeneration.Status.FAILED,
        )
    )
    error_code = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=64,
        default="",
    )

    def to_internal_value(self, data: Any) -> Dict[str, Any]:
        """errorCode 입력을 내부 이름으로 정규화합니다."""

        if not isinstance(data, dict):
            raise serializers.ValidationError("Invalid JSON body")
        normalized = dict(data)
        if "errorCode" in data:
            normalized["error_code"] = data.get("errorCode")
        return super().to_internal_value(normalized)


class AssistantGenerationSerializer(serializers.ModelSerializer):
    """generation 상태를 frontend camelCase 형태로 반환합니다."""

    conversationId = serializers.UUIDField(source="conversation_id")
    clientRequestId = serializers.CharField(source="client_request_id")
    contextKey = serializers.CharField(source="context_key")
    errorCode = serializers.CharField(source="error_code")
    modelName = serializers.CharField(source="model_name")
    expiresAt = serializers.DateTimeField(source="expires_at")
    startedAt = serializers.DateTimeField(source="started_at", allow_null=True)
    finishedAt = serializers.DateTimeField(source="finished_at", allow_null=True)

    class Meta:
        """generation 공개 필드만 정의합니다."""

        model = AssistantGeneration
        fields = (
            "id",
            "conversationId",
            "clientRequestId",
            "contextKey",
            "status",
            "errorCode",
            "provider",
            "modelName",
            "expiresAt",
            "startedAt",
            "finishedAt",
        )


class AssistantMessageFeedbackSerializer(serializers.Serializer):
    """답변 도움 여부와 선택적 사유를 검증합니다."""

    rating = serializers.ChoiceField(choices=AssistantMessageFeedback.Rating.values)
    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        trim_whitespace=True,
        max_length=1000,
        default="",
    )


class AssistantConversationExportQuerySerializer(serializers.Serializer):
    """대화 내보내기 형식을 검증합니다."""

    format = serializers.ChoiceField(choices=("markdown", "csv"), default="markdown")


__all__ = [
    "AssistantChatRequestSerializer",
    "AssistantConversationCreateSerializer",
    "AssistantConversationListQuerySerializer",
    "AssistantConversationExportQuerySerializer",
    "AssistantConversationSummaryRequestSerializer",
    "AssistantConversationSerializer",
    "AssistantConversationUpdateSerializer",
    "AssistantGenerationCreateSerializer",
    "AssistantGenerationFinalizeSerializer",
    "AssistantGenerationSerializer",
    "AssistantMessageBatchSerializer",
    "AssistantMessageListQuerySerializer",
    "AssistantMessageSerializer",
    "AssistantMessageFeedbackSerializer",
    "decode_assistant_cursor",
    "encode_assistant_cursor",
]
