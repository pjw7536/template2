# =============================================================================
# 모듈: Assistant 생성 실행 상태 서비스
# 주요 함수: finalize_assistant_generation
# 주요 가정: 사용자당 queued/streaming 실행은 DB constraint로 하나만 허용됩니다.
# =============================================================================
"""다중 탭에서도 일관된 Assistant 생성 lease와 종료 상태를 관리합니다."""

from __future__ import annotations

from django.utils import timezone

from ..models import AssistantGeneration

ACTIVE_GENERATION_STATUSES = (
    AssistantGeneration.Status.QUEUED,
    AssistantGeneration.Status.STREAMING,
)
TERMINAL_GENERATION_STATUSES = (
    AssistantGeneration.Status.COMPLETED,
    AssistantGeneration.Status.STOPPED,
    AssistantGeneration.Status.FAILED,
)


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
    "TERMINAL_GENERATION_STATUSES",
    "finalize_assistant_generation",
]
