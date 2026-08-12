# =============================================================================
# 모듈: Assistant 생성 실행 상태 서비스
# 주요 함수: acquire_assistant_generation, finalize_assistant_generation
# 주요 가정: 사용자당 queued/streaming 실행은 DB constraint로 하나만 허용됩니다.
# =============================================================================
"""다중 탭에서도 일관된 Assistant 생성 lease와 종료 상태를 관리합니다."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from ..models import AssistantConversation, AssistantGeneration

GENERATION_LEASE_SECONDS = 180
ACTIVE_GENERATION_STATUSES = (
    AssistantGeneration.Status.QUEUED,
    AssistantGeneration.Status.STREAMING,
)
TERMINAL_GENERATION_STATUSES = (
    AssistantGeneration.Status.COMPLETED,
    AssistantGeneration.Status.STOPPED,
    AssistantGeneration.Status.FAILED,
)


class AssistantGenerationBusyError(RuntimeError):
    """같은 사용자의 다른 생성 lease가 아직 활성 상태일 때 발생합니다."""


@transaction.atomic
def acquire_assistant_generation(
    *,
    user: Any,
    conversation: AssistantConversation,
    client_request_id: str,
    context_key: str,
    provider: str = "",
    model_name: str = "",
) -> AssistantGeneration:
    """사용자당 하나의 생성 lease를 idempotent하게 획득합니다.

    입력:
        user/conversation: 생성 소유자와 대화방입니다.
        client_request_id: 브라우저 재시도를 구분하는 idempotency 키입니다.
        context_key: 화면 또는 Observer 조회 조건 문맥입니다.

    반환:
        새로 생성했거나 동일 요청으로 이미 존재하는 generation입니다.

    부작용:
        만료된 활성 실행을 failed 처리하고 새 streaming row를 생성합니다.

    오류:
        다른 활성 실행이 있으면 AssistantGenerationBusyError를 발생시킵니다.
    """

    now = timezone.now()
    AssistantGeneration.objects.filter(
        user=user,
        status__in=ACTIVE_GENERATION_STATUSES,
        expires_at__lte=now,
    ).update(
        status=AssistantGeneration.Status.FAILED,
        error_code="lease_expired",
        finished_at=now,
        updated_at=now,
    )
    normalized_provider = provider[:64]
    normalized_model_name = model_name[:200]
    existing = AssistantGeneration.objects.filter(
        user=user,
        client_request_id=client_request_id,
    ).first()
    if existing is not None:
        same_contract = (
            existing.conversation_id == conversation.id
            and existing.context_key == context_key
            and existing.provider == normalized_provider
            and existing.model_name == normalized_model_name
        )
        if not same_contract:
            raise AssistantGenerationBusyError(
                "같은 요청 ID를 다른 생성 조건에 재사용할 수 없습니다."
            )
        if (
            existing.status not in ACTIVE_GENERATION_STATUSES
            or existing.expires_at <= now
        ):
            raise AssistantGenerationBusyError(
                "이미 종료된 요청 ID입니다. 새 요청 ID를 사용해주세요."
            )
        return existing

    try:
        return AssistantGeneration.objects.create(
            user=user,
            conversation=conversation,
            client_request_id=client_request_id,
            context_key=context_key,
            provider=normalized_provider,
            model_name=normalized_model_name,
            status=AssistantGeneration.Status.STREAMING,
            started_at=now,
            expires_at=now + timedelta(seconds=GENERATION_LEASE_SECONDS),
        )
    except IntegrityError as exc:
        raise AssistantGenerationBusyError(
            "이미 다른 대화방에서 답변을 생성하고 있습니다."
        ) from exc


def finalize_assistant_generation(
    *,
    generation: AssistantGeneration,
    status: str,
    error_code: str = "",
) -> AssistantGeneration:
    """활성 generation을 완료·중단·실패 중 하나로 idempotent하게 종료합니다."""

    if status not in TERMINAL_GENERATION_STATUSES:
        raise ValueError("생성 종료 상태가 올바르지 않습니다.")
    if generation.status in TERMINAL_GENERATION_STATUSES:
        return generation
    finished_at = timezone.now()
    updated_count = AssistantGeneration.objects.filter(
        id=generation.id,
        status__in=ACTIVE_GENERATION_STATUSES,
    ).update(
        status=status,
        error_code=error_code[:64],
        finished_at=finished_at,
        updated_at=finished_at,
    )
    if updated_count:
        generation.status = status
        generation.error_code = error_code[:64]
        generation.finished_at = finished_at
        generation.updated_at = finished_at
    return generation


__all__ = [
    "ACTIVE_GENERATION_STATUSES",
    "AssistantGenerationBusyError",
    "TERMINAL_GENERATION_STATUSES",
    "acquire_assistant_generation",
    "finalize_assistant_generation",
]
