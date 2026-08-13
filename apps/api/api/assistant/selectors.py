# =============================================================================
# 모듈: 어시스턴트 접근 권한 셀렉터
# 주요 함수: get_accessible_user_sdwt_prods_for_user
# 주요 가정: RAG 검색 범위는 Assistant 앱별 account 데이터 scope에서 결정합니다.
# =============================================================================
from __future__ import annotations

from typing import Any
from uuid import UUID

from django.db.models import Case, IntegerField, Q, QuerySet, Value, When
from django.utils import timezone
from django.utils.dateparse import parse_datetime

import api.account.services as account_services

from .models import (
    ASSISTANT_DEFAULT_CONTEXT_KEY,
    ASSISTANT_OPENWEBUI_CONTEXT_KEY,
    ASSISTANT_OPENWEBUI_CONTEXT_PREFIX,
    CHATWIDGET_SHARED_CONTEXT_KEY,
    OBSERVER_CONTEXT_PREFIX,
    AssistantConversation,
    AssistantConversationSummary,
    AssistantGeneration,
    AssistantMessage,
    resolve_assistant_memory_context_key,
)
from .serializers import encode_assistant_cursor


def list_assistant_conversations_for_user(
    *,
    user: Any,
) -> QuerySet[AssistantConversation]:
    """사용자가 소유한 대화방을 최근 활동 순으로 반환합니다."""

    return AssistantConversation.objects.filter(user=user).order_by(
        "-updated_at",
        "-created_at",
    )


def get_assistant_conversation_for_user(
    *,
    user: Any,
    conversation_id: UUID,
) -> AssistantConversation | None:
    """사용자와 UUID가 모두 일치하는 대화방 하나를 반환합니다."""

    return AssistantConversation.objects.filter(
        user=user,
        id=conversation_id,
    ).first()


def list_recent_assistant_messages(
    *,
    conversation: AssistantConversation,
    limit: int = 20,
) -> list[AssistantMessage]:
    """대화방의 최근 메시지를 시간 오름차순으로 반환합니다."""

    safe_limit = max(1, min(int(limit), 100))
    branch_ids = _get_current_branch_message_ids(conversation=conversation)
    recent = list(
        AssistantMessage.objects.filter(id__in=branch_ids)
        .select_related(
            "parent",
            "revision_of",
            "generation",
            "context_snapshot",
            "feedback",
        )
        .order_by("-created_at", "-id")[:safe_limit]
    )
    recent.reverse()
    return recent


def _get_current_branch_message_ids(
    *,
    conversation: AssistantConversation,
) -> list[int]:
    """현재 leaf에서 root까지 parent를 따라 활성 분기 ID를 반환합니다."""

    current_message_id = conversation.current_message_id
    if current_message_id is None:
        current_message_id = (
            AssistantMessage.objects.filter(conversation=conversation)
            .order_by("-created_at", "-id")
            .values_list("id", flat=True)
            .first()
        )
    if current_message_id is None:
        return []

    parent_by_id = dict(
        AssistantMessage.objects.filter(conversation=conversation).values_list(
            "id",
            "parent_id",
        )
    )
    branch_ids: list[int] = []
    seen: set[int] = set()
    message_id: int | None = current_message_id
    while message_id is not None and message_id not in seen:
        seen.add(message_id)
        branch_ids.append(message_id)
        message_id = parent_by_id.get(message_id)
    branch_ids.reverse()
    return branch_ids


def list_assistant_current_branch_messages(
    *,
    conversation: AssistantConversation,
) -> list[AssistantMessage]:
    """대화방의 현재 활성 분기 전체를 시간순으로 반환합니다."""

    branch_ids = _get_current_branch_message_ids(conversation=conversation)
    return list(
        AssistantMessage.objects.filter(id__in=branch_ids)
        .select_related(
            "parent",
            "revision_of",
            "generation",
            "context_snapshot",
            "feedback",
        )
        .order_by("created_at", "id")
    )


def list_assistant_conversation_page(
    *,
    user: Any,
    search: str = "",
    cursor_payload: dict[str, object] | None = None,
    limit: int = 20,
    archived: bool = False,
) -> dict[str, object]:
    """사용자 대화방을 고정 우선, 최근순 cursor page로 반환합니다."""

    safe_limit = max(1, min(int(limit), 50))
    queryset = AssistantConversation.objects.filter(user=user)
    queryset = queryset.filter(
        archived_at__isnull=not archived,
    )
    if search:
        queryset = queryset.filter(
            Q(title__icontains=search) | Q(messages__content__icontains=search)
        ).distinct()
    queryset = queryset.annotate(
        _pinned_order=Case(
            When(pinned_at__isnull=False, then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        )
    )
    if cursor_payload:
        cursor_time = parse_datetime(str(cursor_payload.get("updatedAt") or ""))
        cursor_created_at = parse_datetime(
            str(cursor_payload.get("createdAt") or "")
        )
        cursor_id = cursor_payload.get("id")
        cursor_pinned = bool(cursor_payload.get("pinned"))
        if cursor_time and cursor_created_at and cursor_id:
            position_filter = (
                Q(updated_at__lt=cursor_time)
                | Q(updated_at=cursor_time, created_at__lt=cursor_created_at)
                | Q(
                    updated_at=cursor_time,
                    created_at=cursor_created_at,
                    id__lt=cursor_id,
                )
            )
            same_bucket_filter = Q(pinned_at__isnull=not cursor_pinned)
            queryset = queryset.filter(
                (
                    Q(pinned_at__isnull=True)
                    | (same_bucket_filter & position_filter)
                )
                if cursor_pinned
                else same_bucket_filter & position_filter
            )
    rows = list(
        queryset.order_by(
            "-_pinned_order",
            "-updated_at",
            "-created_at",
            "-id",
        )[: safe_limit + 1]
    )
    has_more = len(rows) > safe_limit
    results = rows[:safe_limit]
    next_cursor = None
    if has_more and results:
        boundary = results[-1]
        next_cursor = encode_assistant_cursor(
            "conversations",
            {
                "updatedAt": boundary.updated_at.isoformat(),
                "createdAt": boundary.created_at.isoformat(),
                "id": str(boundary.id),
                "pinned": boundary.pinned_at is not None,
                "search": search,
                "archived": archived,
            },
        )
    return {"results": results, "nextCursor": next_cursor, "hasMore": has_more}


def list_assistant_message_page(
    *,
    conversation: AssistantConversation,
    cursor_payload: dict[str, object] | None = None,
    limit: int = 20,
) -> dict[str, object]:
    """대화방 메시지를 최신 page부터 시간 오름차순으로 반환합니다."""

    safe_limit = max(1, min(int(limit), 50))
    branch_ids = _get_current_branch_message_ids(conversation=conversation)
    queryset = AssistantMessage.objects.filter(id__in=branch_ids).select_related(
        "parent",
        "revision_of",
        "generation",
        "context_snapshot",
        "feedback",
    )
    if cursor_payload:
        cursor_time = parse_datetime(str(cursor_payload.get("createdAt") or ""))
        cursor_id = cursor_payload.get("id")
        if cursor_time and cursor_id:
            queryset = queryset.filter(
                Q(created_at__lt=cursor_time)
                | Q(created_at=cursor_time, id__lt=cursor_id)
            )
    rows = list(queryset.order_by("-created_at", "-id")[: safe_limit + 1])
    has_more = len(rows) > safe_limit
    results = rows[:safe_limit]
    results.reverse()
    next_cursor = None
    if has_more and results:
        boundary = results[0]
        next_cursor = encode_assistant_cursor(
            "messages",
            {
                "createdAt": boundary.created_at.isoformat(),
                "id": boundary.id,
                "conversationId": str(conversation.id),
            },
        )
    return {"results": results, "nextCursor": next_cursor, "hasMore": has_more}


def get_assistant_summary_batch(
    *,
    conversation: AssistantConversation,
    context_key: str,
    trigger_count: int = 12,
    keep_recent_count: int = 10,
    max_batch_count: int = 50,
) -> dict[str, object]:
    """같은 기억 그룹의 최근 문맥을 제외한 미요약 메시지를 반환합니다."""

    branch_ids = _get_current_branch_message_ids(conversation=conversation)
    memory_context_key = resolve_assistant_memory_context_key(context_key)
    queryset = AssistantMessage.objects.filter(id__in=branch_ids)
    if memory_context_key == CHATWIDGET_SHARED_CONTEXT_KEY:
        queryset = queryset.filter(
            Q(context_key=ASSISTANT_DEFAULT_CONTEXT_KEY)
            | Q(context_key=ASSISTANT_OPENWEBUI_CONTEXT_KEY)
            | Q(context_key__startswith=ASSISTANT_OPENWEBUI_CONTEXT_PREFIX)
            | Q(context_key__startswith=OBSERVER_CONTEXT_PREFIX)
        )
    else:
        queryset = queryset.filter(context_key=memory_context_key)
    total_count = queryset.count()
    target_count = max(0, total_count - max(1, keep_recent_count))
    summary = get_assistant_conversation_summary(
        conversation=conversation,
        context_key=memory_context_key,
    )
    current_count = min(summary.message_count, target_count) if summary else 0
    if target_count - current_count < max(1, trigger_count):
        return {
            "messages": [],
            "coveredMessageCount": current_count,
            "totalMessageCount": total_count,
            "summary": summary,
            "contextKey": memory_context_key,
        }
    covered_count = min(target_count, current_count + max(1, max_batch_count))
    messages = list(
        queryset.order_by("created_at", "id")[current_count:covered_count]
    )
    return {
        "messages": messages,
        "coveredMessageCount": covered_count,
        "totalMessageCount": total_count,
        "summary": summary,
        "contextKey": memory_context_key,
    }


def get_assistant_conversation_summary(
    *,
    conversation: AssistantConversation,
    context_key: str,
) -> AssistantConversationSummary | None:
    """대화방과 해석된 기억 키가 일치하는 장기 요약 하나를 반환합니다."""

    return AssistantConversationSummary.objects.filter(
        conversation=conversation,
        context_key=resolve_assistant_memory_context_key(context_key),
    ).first()


def get_assistant_conversation_summary_for_user(
    *,
    user: Any,
    conversation_id: UUID,
    context_key: str,
) -> AssistantConversationSummary | None:
    """사용자 소유 대화방의 해석된 기억 키 요약만 반환합니다."""

    return AssistantConversationSummary.objects.filter(
        conversation__user=user,
        conversation_id=conversation_id,
        context_key=resolve_assistant_memory_context_key(context_key),
    ).first()


def get_assistant_message_for_user(
    *,
    user: Any,
    conversation_id: UUID,
    client_id: str,
) -> AssistantMessage | None:
    """사용자·대화방·client ID가 모두 일치하는 메시지를 반환합니다."""

    return (
        AssistantMessage.objects.filter(
            conversation__user=user,
            conversation_id=conversation_id,
            client_id=client_id,
        )
        .select_related(
            "conversation",
            "parent",
            "revision_of",
            "generation",
            "context_snapshot",
            "feedback",
        )
        .first()
    )


def get_active_assistant_generation_for_user(
    *,
    user: Any,
) -> AssistantGeneration | None:
    """아직 lease가 유효한 사용자 활성 generation을 반환합니다."""

    return (
        AssistantGeneration.objects.filter(
            user=user,
            expires_at__gt=timezone.now(),
            status__in=(
                AssistantGeneration.Status.QUEUED,
                AssistantGeneration.Status.STREAMING,
            ),
        )
        .select_related("conversation")
        .order_by("-created_at")
        .first()
    )


def get_assistant_generation_for_user(
    *,
    user: Any,
    generation_id: UUID,
) -> AssistantGeneration | None:
    """사용자 소유 generation 하나를 반환합니다."""

    return (
        AssistantGeneration.objects.filter(user=user, id=generation_id)
        .select_related("conversation")
        .first()
    )


def get_accessible_user_sdwt_prods_for_user(*, user: Any) -> set[str]:
    """사용자가 접근 가능한 user_sdwt_prod 목록을 조회합니다.

    인자:
        user: Django 사용자 객체(익명/비인증 가능).

    반환:
        접근 가능한 user_sdwt_prod 문자열 집합.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    return account_services.get_accessible_user_sdwt_prods_for_scope(
        user=user,
        scope_key="assistant",
    )
