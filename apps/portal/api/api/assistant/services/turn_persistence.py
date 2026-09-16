# =============================================================================
# 모듈: Assistant Turn 결과의 fenced persistence
# 주요 함수: commit_assistant_turn_result
# 핵심 전제: 활성 Run·lease·예상 branch head가 모두 일치할 때만 답변을 저장합니다.
# =============================================================================
"""늦게 도착한 Provider 결과가 현재 branch를 덮지 못하게 원자 저장합니다."""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from .. import selectors
from ..models import AssistantGeneration, AssistantMessage
from .access_requirements import merge_access_requirements
from .conversations import append_assistant_messages
from .runtime import AssistantRuntimeResult


class AssistantRunFencedError(RuntimeError):
    """Run lease 또는 branch 소유권을 잃은 결과가 저장을 시도했음을 나타냅니다."""


@transaction.atomic
def commit_assistant_turn_result(
    *,
    generation_id: object,
    input_message_id: int,
    input_message_client_id: str,
    assistant_client_id: str,
    context_key: str,
    result: AssistantRuntimeResult,
) -> tuple[AssistantGeneration, AssistantMessage]:
    """현재 active Run의 결과만 metadata·메시지·branch와 함께 저장합니다."""

    generation, conversation = selectors.lock_assistant_generation_with_conversation(
        generation_id=generation_id,
    )
    now = timezone.now()
    if (
        generation is None
        or conversation is None
        or generation.status != AssistantGeneration.Status.STREAMING
        or generation.expires_at <= now
        or conversation.current_message_id != input_message_id
    ):
        raise AssistantRunFencedError("현재 Run이 결과 저장 권한을 잃었습니다.")
    final_requirements = merge_access_requirements(
        generation.access_requirements,
        result.access_requirements,
    )
    generation.tool_keys = list(result.tool_keys)
    generation.access_requirements = final_requirements
    generation.execution_metadata = dict(result.execution_metadata)
    generation.save(
        update_fields=[
            "tool_keys",
            "access_requirements",
            "execution_metadata",
            "updated_at",
        ]
    )
    message = append_assistant_messages(
        conversation=conversation,
        messages=[
            {
                "client_id": assistant_client_id,
                "role": AssistantMessage.Roles.ASSISTANT,
                "content": result.content,
                "blocks": result.blocks,
                "sources": result.sources,
                "context_key": context_key,
                "generation_id": generation.id,
                "parent_id": input_message_client_id,
                "access_requirements": final_requirements,
                "context_snapshot": result.context_snapshot,
            }
        ],
    )[0]
    return generation, message


__all__ = ["AssistantRunFencedError", "commit_assistant_turn_result"]
