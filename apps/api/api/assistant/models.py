# =============================================================================
# 모듈: Assistant 대화방과 메시지 모델
# 주요 클래스: AssistantConversation, AssistantConversationSummary, AssistantMessage
# 주요 가정: 대화방은 한 사용자에게만 속하고 삭제 시 메시지도 함께 삭제됩니다.
# =============================================================================
"""사용자별 Assistant 대화방과 메시지 영구 저장 모델입니다."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

ASSISTANT_DEFAULT_CONTEXT_KEY = "assistant"
ASSISTANT_OPENWEBUI_CONTEXT_KEY = "assistant:openwebui"
CHATWIDGET_SHARED_CONTEXT_KEY = "chatwidget:shared"
OBSERVER_CONTEXT_PREFIX = "observer:"


def normalize_assistant_context_key(context_key: object) -> str:
    """빈 문맥 키를 Email RAG 기본 문맥으로 정규화합니다."""

    normalized = str(context_key or "").strip()
    return normalized or ASSISTANT_DEFAULT_CONTEXT_KEY


def resolve_assistant_memory_context_key(context_key: object) -> str:
    """요청 문맥 키를 rolling summary와 최근 이력의 기억 키로 변환합니다."""

    normalized = normalize_assistant_context_key(context_key)
    if normalized == CHATWIDGET_SHARED_CONTEXT_KEY:
        return normalized
    if (
        normalized == ASSISTANT_OPENWEBUI_CONTEXT_KEY
        or normalized.startswith(OBSERVER_CONTEXT_PREFIX)
    ):
        return CHATWIDGET_SHARED_CONTEXT_KEY
    return normalized


def is_chatwidget_shared_memory_context(context_key: object) -> bool:
    """문맥 키가 일반 Chat·Observer 공유 기억에 속하는지 반환합니다."""

    return (
        resolve_assistant_memory_context_key(context_key)
        == CHATWIDGET_SHARED_CONTEXT_KEY
    )


def format_assistant_memory_content(*, context_key: object, content: str) -> str:
    """공유 요약에서 일반 Chat과 Observer 메시지 출처를 구분합니다."""

    normalized = normalize_assistant_context_key(context_key)
    if normalized == ASSISTANT_OPENWEBUI_CONTEXT_KEY:
        return f"[대화 출처: 일반 Chat]\n{content}"
    if normalized.startswith(OBSERVER_CONTEXT_PREFIX):
        return f"[대화 출처: Observer]\n{content}"
    return content


class AssistantConversation(models.Model):
    """로그인 사용자가 소유하는 하나의 Assistant 대화방입니다."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="assistant_conversations",
    )
    title = models.CharField(max_length=120, default="새 대화")
    current_message = models.ForeignKey(
        "AssistantMessage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    pinned_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """대화방 테이블명과 사용자별 최근순 조회 index를 정의합니다."""

        db_table = "assistant_conversation"
        ordering = ("-updated_at", "-created_at")
        indexes = [
            models.Index(
                fields=("user", "-updated_at"),
                name="idx_asst_conv_user_updated",
            )
        ]


class AssistantConversationSummary(models.Model):
    """대화방의 기억 그룹별 장기 요약과 포함 메시지 위치를 저장합니다."""

    conversation = models.ForeignKey(
        AssistantConversation,
        on_delete=models.CASCADE,
        related_name="summaries",
    )
    context_key = models.CharField(max_length=512)
    summary = models.TextField(blank=True, default="")
    message_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """한 대화방에서 같은 기억 그룹 요약이 중복되지 않도록 제한합니다."""

        db_table = "assistant_conversation_summary"
        constraints = [
            models.UniqueConstraint(
                fields=("conversation", "context_key"),
                name="uniq_asst_sum_conv_ctx",
            )
        ]


class AssistantGeneration(models.Model):
    """사용자당 하나만 활성화되는 Assistant 답변 생성 실행입니다."""

    class Status(models.TextChoices):
        """생성 실행의 수명주기 상태입니다."""

        QUEUED = "queued", "대기"
        STREAMING = "streaming", "생성 중"
        COMPLETED = "completed", "완료"
        STOPPED = "stopped", "중단"
        FAILED = "failed", "실패"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="assistant_generations",
    )
    conversation = models.ForeignKey(
        AssistantConversation,
        on_delete=models.CASCADE,
        related_name="generations",
    )
    client_request_id = models.CharField(max_length=128)
    context_key = models.CharField(max_length=512, default="assistant")
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.QUEUED,
    )
    error_code = models.CharField(max_length=64, blank=True, default="")
    provider = models.CharField(max_length=64, blank=True, default="")
    model_name = models.CharField(max_length=200, blank=True, default="")
    expires_at = models.DateTimeField()
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """활성 생성 단일화와 idempotency constraint를 정의합니다."""

        db_table = "assistant_generation"
        constraints = [
            models.UniqueConstraint(
                fields=("user",),
                condition=Q(status__in=("queued", "streaming")),
                name="uniq_asst_gen_user_active",
            ),
            models.UniqueConstraint(
                fields=("user", "client_request_id"),
                name="uniq_asst_gen_user_request",
            ),
        ]
        indexes = [
            models.Index(
                fields=("user", "-created_at"),
                name="idx_asst_gen_user_created",
            )
        ]


class AssistantContextSnapshot(models.Model):
    """업무 화면 분석에 사용된 제한된 scope·coverage·근거 snapshot입니다."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        AssistantConversation,
        on_delete=models.CASCADE,
        related_name="context_snapshots",
    )
    context_key = models.CharField(max_length=512)
    kind = models.CharField(max_length=64, default="generic")
    scope = models.JSONField(default=dict)
    coverage = models.JSONField(default=dict)
    evidence = models.JSONField(default=list)
    payload_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """대화방과 생성 시각 기준 snapshot 조회 index를 정의합니다."""

        db_table = "assistant_context_snapshot"
        indexes = [
            models.Index(
                fields=("conversation", "-created_at"),
                name="idx_asst_snap_conv_created",
            )
        ]


class AssistantMessage(models.Model):
    """대화방에 속하는 사용자 또는 Assistant 메시지입니다."""

    class Roles(models.TextChoices):
        """모델에 전달할 수 있는 메시지 role 목록입니다."""

        USER = "user", "사용자"
        ASSISTANT = "assistant", "Assistant"

    id = models.BigAutoField(primary_key=True)
    conversation = models.ForeignKey(
        AssistantConversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    client_id = models.CharField(max_length=128)
    role = models.CharField(max_length=16, choices=Roles.choices)
    content = models.TextField()
    context_key = models.CharField(max_length=512, default="assistant")
    sources = models.JSONField(default=list)
    user_sdwt_prod = models.CharField(max_length=128, blank=True, default="")
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
    )
    revision_of = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="revisions",
    )
    generation = models.ForeignKey(
        AssistantGeneration,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="messages",
    )
    context_snapshot = models.ForeignKey(
        AssistantContextSnapshot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="messages",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """메시지 테이블명, 정렬, 멱등 constraint와 조회 index를 정의합니다."""

        db_table = "assistant_message"
        ordering = ("created_at", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("conversation", "client_id"),
                name="uniq_asst_msg_conv_client",
            )
        ]
        indexes = [
            models.Index(
                fields=("conversation", "created_at"),
                name="idx_asst_msg_conv_created",
            )
        ]


class AssistantMessageFeedback(models.Model):
    """사용자가 Assistant 답변에 남긴 단일 평가입니다."""

    class Rating(models.TextChoices):
        """지원하는 평가 방향입니다."""

        UP = "up", "도움됨"
        DOWN = "down", "도움 안 됨"

    message = models.OneToOneField(
        AssistantMessage,
        on_delete=models.CASCADE,
        related_name="feedback",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="assistant_message_feedbacks",
    )
    rating = models.CharField(max_length=8, choices=Rating.choices)
    reason = models.CharField(max_length=1000, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """메시지 평가 테이블과 사용자 조회 index를 정의합니다."""

        db_table = "assistant_message_feedback"
        indexes = [
            models.Index(
                fields=("user", "-updated_at"),
                name="idx_asst_feedback_user_upd",
            )
        ]
