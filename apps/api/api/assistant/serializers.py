# =============================================================================
# 모듈: 어시스턴트 요청 직렬화/검증
# 주요 클래스: AssistantTurnRequestSerializer
# =============================================================================
"""어시스턴트 요청 입력 검증을 담당합니다."""
from __future__ import annotations

import json
from typing import Any, Dict

from django.core import signing
from rest_framework import serializers

from .models import (
    AssistantConversation,
    AssistantMessage,
    AssistantMessageFeedback,
)

ASSISTANT_CURSOR_SALT = "assistant.cursor.v1"
MAX_ASSISTANT_MESSAGE_CHARS = 10_000
MAX_ASSISTANT_BLOCKS_JSON_BYTES = 50 * 1024


def _json_size_bytes(value: object) -> int:
    """JSON 값을 전송 기준 UTF-8 byte 크기로 계산합니다."""

    return len(
        json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )


def _has_current_access(*, user: object, requirements: object, request: object) -> bool:
    """순환 import 없이 현재 access requirements 검증 결과를 반환합니다."""

    from .services.access_requirements import validate_access_requirements

    return validate_access_requirements(
        user=user,
        requirements=requirements,
        request=request,
    ).allowed


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


class AssistantConversationSummaryRequestSerializer(serializers.Serializer):
    """rolling summary를 분리할 메시지 contextKey를 검증합니다."""

    contextKey = serializers.ChoiceField(
        source="context_key",
        choices=(
            "profile:portal-default",
            "profile:email-rag",
            "profile:observer-analysis",
            "profile:appstore-context",
            "profile:line-dashboard-context",
            "profile:auto-knowledge",
        ),
    )


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

    def to_representation(self, instance: AssistantConversation) -> dict[str, object]:
        """권한이 회수된 자동·legacy 제목을 일반 제목으로 대체합니다."""

        payload = super().to_representation(instance)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if (
            user is not None
            and instance.title_source not in {"default", "user"}
            and not _has_current_access(
                user=user,
                requirements=instance.title_access_requirements,
                request=request,
            )
        ):
            payload["name"] = "권한이 필요한 대화"
            payload["titleAccessState"] = "locked"
        else:
            payload["titleAccessState"] = "available"
        return payload

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
    accessState = serializers.SerializerMethodField()

    def _has_access(self, obj: AssistantMessage) -> bool:
        """serializer 요청 사용자의 현재 권한으로 메시지 노출 여부를 판정합니다."""

        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user is None:
            return True
        return _has_current_access(
            user=user,
            requirements=obj.access_requirements,
            request=request,
        )

    def get_accessState(self, obj: AssistantMessage) -> str:
        """메시지 본문 접근 상태를 반환합니다."""

        return "available" if self._has_access(obj) else "locked"

    def to_representation(self, instance: AssistantMessage) -> dict[str, object]:
        """잠긴 메시지는 chronology와 branch 관계만 남긴 placeholder로 반환합니다."""

        payload = super().to_representation(instance)
        if self._has_access(instance):
            return payload
        allowed_keys = {
            "id",
            "role",
            "parentId",
            "revisionOfId",
            "generationId",
            "createdAt",
            "accessState",
        }
        return {key: value for key, value in payload.items() if key in allowed_keys}

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
            "blocks",
            "contextKey",
            "sources",
            "userSdwtProd",
            "parentId",
            "revisionOfId",
            "generationId",
            "contextSnapshot",
            "feedback",
            "accessState",
            "createdAt",
        )


class AssistantTurnMessageSerializer(serializers.Serializer):
    """Turn 요청이 새로 저장할 사용자 메시지 식별자와 본문을 검증합니다."""

    client_id = serializers.CharField(max_length=128)
    content = serializers.CharField(max_length=MAX_ASSISTANT_MESSAGE_CHARS, trim_whitespace=True)

    def to_internal_value(self, data: Any) -> Dict[str, Any]:
        """clientId를 내부 snake_case 이름으로 정규화합니다."""

        if not isinstance(data, dict):
            raise serializers.ValidationError("message must be an object")
        normalized = {
            "client_id": data.get("clientId"),
            "content": data.get("content"),
        }
        return super().to_internal_value(normalized)


class AssistantTurnRequestSerializer(serializers.Serializer):
    """표준 Turn send/edit/regenerate/retry 요청 계약을 검증합니다."""

    action = serializers.ChoiceField(choices=("send", "edit", "regenerate", "retry"))
    conversation_id = serializers.UUIDField()
    client_request_id = serializers.CharField(max_length=128)
    profile_key = serializers.ChoiceField(
        choices=(
            "portal-default",
            "email-rag",
            "observer-analysis",
            "appstore-context",
            "line-dashboard-context",
            "auto-knowledge",
        )
    )
    profile_version = serializers.IntegerField(required=False, min_value=1)
    app_context_key = serializers.CharField(required=False, max_length=512)
    message = AssistantTurnMessageSerializer()
    target_message_id = serializers.CharField(required=False, max_length=128)
    retry_run_id = serializers.UUIDField(required=False)
    tool_inputs = serializers.JSONField(required=False, default=dict)

    def to_internal_value(self, data: Any) -> Dict[str, Any]:
        """Turn API camelCase 입력을 내부 이름으로 정규화합니다."""

        if not isinstance(data, dict):
            raise serializers.ValidationError("Invalid JSON body")
        normalized = {
            "action": data.get("action"),
            "message": data.get("message"),
        }
        for external, internal in (
            ("conversationId", "conversation_id"),
            ("clientRequestId", "client_request_id"),
            ("profileKey", "profile_key"),
            ("profileVersion", "profile_version"),
            ("appContextKey", "app_context_key"),
            ("targetMessageId", "target_message_id"),
            ("retryRunId", "retry_run_id"),
            ("toolInputs", "tool_inputs"),
        ):
            if external in data:
                normalized[internal] = data.get(external)
        return super().to_internal_value(normalized)

    def validate_tool_inputs(self, value: object) -> dict[str, object]:
        """Tool 입력을 허용 key와 50KB 상한으로 제한합니다."""

        if not isinstance(value, dict):
            raise serializers.ValidationError("toolInputs must be an object")
        if set(value) - {
            "rag.search",
            "observer.analysis",
            "appstore.catalog",
            "line-dashboard.snapshot",
        }:
            raise serializers.ValidationError("지원하지 않는 Tool 입력입니다.")
        if _json_size_bytes(value) > MAX_ASSISTANT_BLOCKS_JSON_BYTES:
            raise serializers.ValidationError("toolInputs 크기는 최대 50KB까지 허용됩니다.")
        return value

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """action별 target/retry 계약과 새 client ID 요구사항을 확인합니다."""

        action = attrs["action"]
        if action in {"send", "edit"} and not str(
            attrs.get("app_context_key") or ""
        ).strip():
            raise serializers.ValidationError(
                {"appContextKey": "appContextKey가 필요합니다."}
            )
        if action in {"edit", "regenerate"} and not attrs.get("target_message_id"):
            raise serializers.ValidationError({"targetMessageId": "targetMessageId가 필요합니다."})
        if action == "retry" and not attrs.get("retry_run_id"):
            raise serializers.ValidationError({"retryRunId": "retryRunId가 필요합니다."})
        return attrs


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
    "AssistantConversationCreateSerializer",
    "AssistantConversationListQuerySerializer",
    "AssistantConversationExportQuerySerializer",
    "AssistantConversationSummaryRequestSerializer",
    "AssistantConversationSerializer",
    "AssistantConversationUpdateSerializer",
    "AssistantMessageListQuerySerializer",
    "AssistantMessageSerializer",
    "AssistantMessageFeedbackSerializer",
    "AssistantTurnRequestSerializer",
    "decode_assistant_cursor",
    "encode_assistant_cursor",
]
