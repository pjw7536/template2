# =============================================================================
# 모듈: Assistant 대화방과 메시지 쓰기 서비스
# 주요 함수: create_assistant_conversation, generate_assistant_conversation_title
# 주요 가정: 조회와 소유권 확인은 selector를 통해 수행합니다.
# =============================================================================
"""Assistant 대화방 생성·제목·삭제와 메시지 멱등 저장을 담당합니다."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping, Sequence

from django.db import IntegrityError, transaction
from django.utils import timezone

from ..models import (
    AssistantContextSnapshot,
    AssistantConversation,
    AssistantConversationSummary,
    AssistantGeneration,
    AssistantMessage,
    AssistantMessageFeedback,
    format_assistant_memory_content,
    is_chatwidget_shared_memory_context,
)
from .errors import AssistantRequestError
from .generations import finalize_assistant_generation
from .openwebui import (
    request_openwebui_conversation_summary,
    request_openwebui_conversation_title,
)

DEFAULT_CONVERSATION_TITLE_PATTERN = re.compile(r"^새 대화(?:\s+\d+)?$")


def create_assistant_conversation(
    *,
    user: Any,
    title: str = "새 대화",
) -> AssistantConversation:
    """사용자 소유의 새 대화방을 생성합니다.

    부작용:
        AssistantConversation 레코드를 생성합니다.
    """

    normalized_title = title.strip() if isinstance(title, str) else ""
    return AssistantConversation.objects.create(
        user=user,
        title=normalized_title[:120] or "새 대화",
    )


def delete_assistant_conversation(
    *,
    conversation: AssistantConversation,
) -> None:
    """대화방과 FK cascade 대상 메시지를 함께 삭제합니다."""

    conversation.delete()


def update_assistant_conversation(
    *,
    conversation: AssistantConversation,
    title: str | None = None,
    pinned: bool | None = None,
    archived: bool | None = None,
) -> AssistantConversation:
    """대화방 이름·고정·보관 상태 중 전달된 값만 갱신합니다."""

    update_fields: list[str] = []
    if title is not None:
        conversation.title = title.strip()[:120] or "새 대화"
        update_fields.append("title")
    if pinned is not None:
        conversation.pinned_at = timezone.now() if pinned else None
        update_fields.append("pinned_at")
    if archived is not None:
        conversation.archived_at = timezone.now() if archived else None
        update_fields.append("archived_at")
    if update_fields:
        conversation.save(update_fields=[*update_fields, "updated_at"])
    return conversation


def is_default_assistant_conversation_title(title: object) -> bool:
    """제목이 자동 생성 대상인 `새 대화` 계열인지 반환합니다."""

    return bool(
        isinstance(title, str)
        and DEFAULT_CONVERSATION_TITLE_PATTERN.fullmatch(title.strip())
    )


def generate_assistant_conversation_title(
    *,
    conversation: AssistantConversation,
    messages: Sequence[AssistantMessage],
) -> AssistantConversation:
    """기본 이름 대화방의 제목을 OpenWebUI로 한 번 생성해 저장합니다.

    입력:
        conversation: 제목을 갱신할 사용자 소유 대화방입니다.
        messages: selector가 조회한 저장 메시지 목록입니다.

    반환:
        제목이 반영된 AssistantConversation입니다.

    부작용:
        OpenWebUI를 호출하고 대화방 title과 updated_at을 갱신합니다.

    오류:
        사용자/Assistant 대화가 모두 없으면 ValueError, 제목 생성 실패 시
        AssistantRequestError를 발생시킵니다.
    """

    if not is_default_assistant_conversation_title(conversation.title):
        return conversation

    history = [
        {"role": message.role, "content": message.content}
        for message in messages
        if message.role in {AssistantMessage.Roles.USER, AssistantMessage.Roles.ASSISTANT}
        and message.content.strip()
    ]
    roles = {entry["role"] for entry in history}
    if not {AssistantMessage.Roles.USER, AssistantMessage.Roles.ASSISTANT}.issubset(roles):
        raise ValueError("제목 생성에는 사용자 질문과 Assistant 답변이 모두 필요합니다.")

    title = request_openwebui_conversation_title(history=history)
    if is_default_assistant_conversation_title(title):
        raise AssistantRequestError("OpenWebUI가 기본 대화방 이름을 반환했습니다.")

    updated_at = timezone.now()
    updated_count = AssistantConversation.objects.filter(
        id=conversation.id,
        title=conversation.title,
    ).update(
        title=title,
        updated_at=updated_at,
    )
    if updated_count != 1:
        raise ValueError("대화방 제목이 이미 변경되었거나 대화방이 삭제되었습니다.")

    conversation.title = title
    conversation.updated_at = updated_at
    return conversation


@transaction.atomic
def clear_assistant_messages(
    *,
    conversation: AssistantConversation,
) -> None:
    """대화방은 유지하고 그 안의 모든 메시지만 삭제합니다."""

    conversation.messages.all().delete()
    conversation.context_snapshots.all().delete()
    conversation.summaries.all().delete()
    conversation.current_message = None
    conversation.save(update_fields=["current_message", "updated_at"])


def _normalize_snapshot_value(value: object, *, depth: int = 0) -> object:
    """업무 문맥 JSON을 예측 가능한 크기와 깊이로 제한합니다."""

    if depth >= 4:
        return str(value)[:300]
    if isinstance(value, Mapping):
        max_items = 30 if depth == 0 else 10 if depth == 1 else 5
        return {
            str(key)[:100]: _normalize_snapshot_value(item, depth=depth + 1)
            for key, item in list(value.items())[:max_items]
        }
    if isinstance(value, (list, tuple)):
        max_items = 100 if depth == 0 else 20 if depth == 1 else 10
        return [
            _normalize_snapshot_value(item, depth=depth + 1)
            for item in list(value)[:max_items]
        ]
    if isinstance(value, str):
        return value[:1000]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:300]


def _fit_snapshot_section(value: object, *, max_chars: int) -> object:
    """정규화된 snapshot 최상위 section을 지정 JSON 문자 수 안에 맞춥니다."""

    if isinstance(value, dict):
        fitted: dict[str, object] = {}
        for key, item in value.items():
            fitted[key] = item
            if len(json.dumps(fitted, ensure_ascii=False, separators=(",", ":"))) > max_chars:
                fitted.pop(key)
        return fitted
    if isinstance(value, list):
        fitted_list: list[object] = []
        for item in value:
            fitted_list.append(item)
            if len(
                json.dumps(fitted_list, ensure_ascii=False, separators=(",", ":"))
            ) > max_chars:
                fitted_list.pop()
                break
        return fitted_list
    return value


def create_assistant_context_snapshot(
    *,
    conversation: AssistantConversation,
    context_key: str,
    payload: Mapping[str, object],
) -> AssistantContextSnapshot:
    """Observer 등 업무 화면의 제한된 분석 문맥 snapshot을 생성합니다."""

    scope = _fit_snapshot_section(
        _normalize_snapshot_value(payload.get("scope") or {}),
        max_chars=12000,
    )
    coverage = _fit_snapshot_section(
        _normalize_snapshot_value(payload.get("coverage") or {}),
        max_chars=12000,
    )
    evidence = _fit_snapshot_section(
        _normalize_snapshot_value(payload.get("evidence") or []),
        max_chars=40000,
    )
    canonical_payload = {
        "kind": str(payload.get("kind") or "generic")[:64],
        "scope": scope if isinstance(scope, dict) else {},
        "coverage": coverage if isinstance(coverage, dict) else {},
        "evidence": evidence if isinstance(evidence, list) else [],
    }
    payload_hash = hashlib.sha256(
        json.dumps(
            canonical_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return AssistantContextSnapshot.objects.create(
        conversation=conversation,
        context_key=context_key,
        payload_hash=payload_hash,
        **canonical_payload,
    )


def upsert_assistant_message_feedback(
    *,
    message: AssistantMessage,
    user: Any,
    rating: str,
    reason: str = "",
) -> AssistantMessageFeedback:
    """한 Assistant 답변에 대한 사용자 평가를 생성하거나 교체합니다."""

    feedback, _ = AssistantMessageFeedback.objects.update_or_create(
        message=message,
        defaults={
            "user": user,
            "rating": rating,
            "reason": reason.strip()[:1000],
        },
    )
    return feedback


def delete_assistant_message_feedback(*, message: AssistantMessage) -> None:
    """메시지에 연결된 평가가 있으면 삭제합니다."""

    AssistantMessageFeedback.objects.filter(message=message).delete()


def refresh_assistant_conversation_summary(
    *,
    conversation: AssistantConversation,
    existing_summary: AssistantConversationSummary | None,
    messages: Sequence[AssistantMessage],
    covered_message_count: int,
    context_key: str,
) -> AssistantConversationSummary:
    """새로 누적된 과거 메시지를 기존 장기 요약에 병합해 저장합니다.

    입력:
        conversation: 요약을 소유하는 사용자 대화방입니다.
        messages: 아직 요약되지 않은 과거 메시지 묶음입니다.
        covered_message_count: 이번 요약까지 포함된 전체 메시지 위치입니다.
        context_key: 대화 기억을 저장할 해석된 문맥 키입니다.

    반환:
        갱신된 기억 그룹별 AssistantConversationSummary입니다.

    부작용:
        OpenWebUI 저비용 요약 요청 후 기억 그룹별 summary row를 조건부 갱신합니다.
    """

    previous_message_count = existing_summary.message_count if existing_summary else 0
    if not messages or covered_message_count <= previous_message_count:
        if existing_summary is None:
            raise ValueError("갱신할 대화 요약 메시지가 없습니다.")
        return existing_summary
    summary = request_openwebui_conversation_summary(
        messages=[
            {
                "role": message.role,
                "content": (
                    format_assistant_memory_content(
                        context_key=message.context_key,
                        content=message.content,
                    )
                    if is_chatwidget_shared_memory_context(context_key)
                    else message.content
                ),
            }
            for message in messages
        ],
        existing_summary=existing_summary.summary if existing_summary else "",
    )
    if existing_summary is None:
        try:
            return AssistantConversationSummary.objects.create(
                conversation=conversation,
                context_key=context_key,
                summary=summary,
                message_count=covered_message_count,
            )
        except IntegrityError as exc:
            raise ValueError("대화 요약이 이미 생성되었거나 대화방이 삭제되었습니다.") from exc

    updated_at = timezone.now()
    updated_count = AssistantConversationSummary.objects.filter(
        id=existing_summary.id,
        message_count=existing_summary.message_count,
    ).update(
        summary=summary,
        message_count=covered_message_count,
        updated_at=updated_at,
    )
    if updated_count != 1:
        raise ValueError("대화 요약이 이미 갱신되었거나 대화방이 삭제되었습니다.")
    existing_summary.summary = summary
    existing_summary.message_count = covered_message_count
    existing_summary.updated_at = updated_at
    return existing_summary


@transaction.atomic
def append_assistant_messages(
    *,
    conversation: AssistantConversation,
    messages: Sequence[Mapping[str, object]],
) -> list[AssistantMessage]:
    """client_id 기준으로 메시지를 중복 없이 저장합니다.

    입력:
        conversation: 저장 대상 대화방.
        messages: serializer 검증을 통과한 메시지 목록.

    반환:
        입력 순서에 대응하는 저장 메시지 목록.

    부작용:
        AssistantMessage를 생성하고 대화방 updated_at을 갱신합니다.
    """

    stored_messages: list[AssistantMessage] = []
    generations_to_complete: dict[object, AssistantGeneration] = {}
    current_message = conversation.current_message
    summary_invalidated = False
    for message in messages:
        parent = current_message
        parent_client_id = message.get("parent_id")
        if "parent_id" in message:
            parent = None
            if parent_client_id:
                parent = AssistantMessage.objects.filter(
                    conversation=conversation,
                    client_id=str(parent_client_id),
                ).first()
                if parent is None:
                    raise ValueError("parentId 메시지를 현재 대화방에서 찾을 수 없습니다.")

        revision_of = None
        revision_client_id = message.get("revision_of_id")
        if revision_client_id:
            revision_of = AssistantMessage.objects.filter(
                conversation=conversation,
                client_id=str(revision_client_id),
            ).first()
            if revision_of is None:
                raise ValueError("revisionOfId 메시지를 현재 대화방에서 찾을 수 없습니다.")

        generation = None
        generation_id = message.get("generation_id")
        if generation_id:
            generation = AssistantGeneration.objects.filter(
                id=generation_id,
                conversation=conversation,
                user=conversation.user,
            ).first()
            if generation is None:
                raise ValueError("generationId를 현재 대화방에서 찾을 수 없습니다.")

        context_key = str(message.get("context_key") or "assistant")
        snapshot = None
        snapshot_payload = message.get("context_snapshot")
        if isinstance(snapshot_payload, Mapping):
            snapshot = create_assistant_context_snapshot(
                conversation=conversation,
                context_key=context_key,
                payload=snapshot_payload,
            )

        stored, created = AssistantMessage.objects.get_or_create(
            conversation=conversation,
            client_id=str(message["client_id"]),
            defaults={
                "role": str(message["role"]),
                "content": str(message["content"]),
                "context_key": context_key,
                "sources": message.get("sources") or [],
                "user_sdwt_prod": str(message.get("user_sdwt_prod") or ""),
                "parent": parent,
                "revision_of": revision_of,
                "generation": generation,
                "context_snapshot": snapshot,
            },
        )
        if not created and snapshot is not None:
            snapshot.delete()
        if created:
            if revision_of is not None or parent != current_message:
                summary_invalidated = True
            current_message = stored
        if (
            stored.role == AssistantMessage.Roles.ASSISTANT
            and generation is not None
            and stored.generation_id == generation.id
        ):
            generations_to_complete[generation.id] = generation
        stored_messages.append(stored)

    if stored_messages and current_message is not None:
        conversation.current_message = current_message
        update_fields = ["current_message", "updated_at"]
        if summary_invalidated:
            conversation.summaries.all().delete()
        conversation.save(update_fields=update_fields)
    for generation in generations_to_complete.values():
        finalize_assistant_generation(
            generation=generation,
            status=AssistantGeneration.Status.COMPLETED,
        )
    return stored_messages
