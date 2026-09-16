# =============================================================================
# 모듈: Profile·권한 인식 Assistant memory 조립
# 주요 함수: build_assistant_runtime_memory, resolve_message_memory_partition
# 핵심 전제: Profile allowlist 밖 partition과 권한 실패 항목은 Provider 입력에서 제외합니다.
# =============================================================================
"""현재 branch에서 실제 사용 가능한 message와 partition summary만 조립합니다."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from .. import selectors
from ..models import (
    AssistantConversation,
    AssistantConversationSummary,
    AssistantMessage,
)
from .access_requirements import empty_access_requirements, merge_access_requirements, validate_access_requirements
from .profiles import AssistantProfile


@dataclass(frozen=True)
class AssistantRuntimeMemory:
    """Provider에 전달할 검증된 history/summary와 실제 사용 요구사항입니다."""

    history: list[dict[str, str]]
    summary: str
    access_requirements: dict[str, object]


MAX_RUNTIME_HISTORY_MESSAGES = 20
MAX_RUNTIME_HISTORY_CHARS = 40_000


def resolve_message_memory_partition(message: AssistantMessage) -> str:
    """Run provenance가 명시한 partition만 반환하고 미연결 row는 잠급니다."""

    generation = message.generation
    if generation is not None and generation.memory_partition:
        return generation.memory_partition
    return "legacy-unresolved"


def build_assistant_runtime_memory(
    *,
    user: Any,
    conversation: AssistantConversation,
    profile: AssistantProfile,
    request: Any | None = None,
    limit: int = MAX_RUNTIME_HISTORY_MESSAGES,
    max_history_chars: int = MAX_RUNTIME_HISTORY_CHARS,
) -> AssistantRuntimeMemory:
    """현재 branch에서 Profile과 현재 권한을 모두 통과한 memory만 반환합니다.

    부작용:
        메시지, summary, Account/data scope를 읽기 전용으로 조회합니다.
    """

    requirements: list[object] = []
    summaries_by_partition: dict[str, AssistantConversationSummary] = {}
    for summary in selectors.list_assistant_conversation_summaries(
        conversation=conversation
    ):
        partition = summary.memory_partition
        if partition not in profile.read_partitions:
            continue
        decision = validate_access_requirements(
            user=user,
            requirements=summary.access_requirements,
            request=request,
        )
        if not decision.allowed or not summary.summary.strip():
            continue
        summaries_by_partition[partition] = summary

    summary_parts: list[tuple[str, str]] = []
    for partition in profile.read_partitions:
        summary = summaries_by_partition.get(partition)
        if summary is None:
            continue
        summary_parts.append((partition, summary.summary.strip()))
        requirements.append(summary.access_requirements)

    partition_positions: dict[str, int] = defaultdict(int)
    candidates: list[tuple[AssistantMessage, str]] = []
    for message in selectors.list_assistant_current_branch_messages(
        conversation=conversation
    ):
        partition = resolve_message_memory_partition(message)
        if partition not in profile.read_partitions:
            continue
        position = partition_positions[partition]
        partition_positions[partition] += 1
        summary = summaries_by_partition.get(partition)
        if summary is not None and position < max(0, int(summary.message_count)):
            continue
        decision = validate_access_requirements(
            user=user,
            requirements=message.access_requirements,
            request=request,
        )
        if decision.allowed and message.content.strip():
            candidates.append((message, message.content))

    selected: list[tuple[AssistantMessage, str]] = []
    remaining_chars = max(1, int(max_history_chars))
    safe_limit = max(1, min(int(limit), 100))
    for message, content in reversed(candidates):
        if len(selected) >= safe_limit or len(content) > remaining_chars:
            break
        selected.append((message, content))
        remaining_chars -= len(content)
    selected.reverse()
    history = [
        {"role": message.role, "content": content}
        for message, content in selected
    ]
    requirements.extend(message.access_requirements for message, _ in selected)

    return AssistantRuntimeMemory(
        history=history,
        summary=(
            summary_parts[0][1]
            if len(summary_parts) == 1
            else "\n\n".join(
                f"[{partition}]\n{content}"
                for partition, content in summary_parts
            )
        ),
        access_requirements=(
            merge_access_requirements(*requirements)
            if requirements
            else empty_access_requirements()
        ),
    )


def format_assistant_runtime_context(
    *,
    history: list[dict[str, str]],
    summary: str,
) -> str:
    """Email/Observer Provider용 summary와 요약 이후 history를 한 문맥으로 만듭니다."""

    parts: list[str] = []
    if summary.strip():
        parts.append(f"[장기 대화 요약]\n{summary.strip()}")
    if history:
        role_labels = {"user": "사용자", "assistant": "Assistant"}
        recent = "\n\n".join(
            f"{role_labels.get(item['role'], item['role'])}:\n{item['content']}"
            for item in history
        )
        parts.append(f"[요약 이후 최근 대화]\n{recent}")
    return "\n\n".join(parts)


__all__ = [
    "AssistantRuntimeMemory",
    "build_assistant_runtime_memory",
    "format_assistant_runtime_context",
    "resolve_message_memory_partition",
]
