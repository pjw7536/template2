# =============================================================================
# 모듈: Assistant Runtime worker와 SSE heartbeat lifecycle
# 주요 함수: stream_assistant_runtime_execution
# 핵심 전제: generator 종료·timeout은 같은 cancellation token을 통해 upstream을 닫습니다.
# =============================================================================
"""동기 Provider transport를 취소 가능한 worker에서 실행하고 event로 전달합니다."""

from __future__ import annotations

from dataclasses import dataclass
import queue
import threading
import time
from typing import Any, Iterator, Mapping, Sequence

from api.common.services import ExternalCallCancellation, ExternalCallCancelled
from django.db import close_old_connections

from .profiles import AssistantProfile
from .runtime import AssistantRuntime, AssistantRuntimeResult

RUNTIME_HEARTBEAT_SECONDS = 1.0
RUNTIME_WORKER_JOIN_SECONDS = 1.0


class AssistantRuntimeTimeout(RuntimeError):
    """Profile timeout 안에 Runtime 실행이 끝나지 않았음을 나타냅니다."""


@dataclass(frozen=True)
class AssistantRuntimeExecutionEvent:
    """worker가 Turn SSE lifecycle에 전달하는 내부 event입니다."""

    kind: str
    delta: str = ""
    result: AssistantRuntimeResult | None = None
    error: BaseException | None = None


def stream_assistant_runtime_execution(
    *,
    runtime: AssistantRuntime,
    profile: AssistantProfile,
    prompt: str,
    history: Sequence[Mapping[str, str]],
    conversation_summary: str,
    tool_inputs: Mapping[str, object],
    user_header_id: str | None,
    context_key: str,
) -> Iterator[AssistantRuntimeExecutionEvent]:
    """Runtime을 worker에서 실행하고 delta/result/heartbeat를 순서대로 반환합니다."""

    cancellation = ExternalCallCancellation()
    events: queue.Queue[AssistantRuntimeExecutionEvent] = queue.Queue()

    def emit_delta(delta: str) -> None:
        """Provider worker의 표시 가능한 delta를 queue에 넣습니다."""

        if delta and not cancellation.cancelled:
            events.put(AssistantRuntimeExecutionEvent(kind="delta", delta=delta))

    def run() -> None:
        """Runtime 결과 또는 예외 하나를 terminal worker event로 전달합니다."""

        close_old_connections()
        try:
            result = runtime.execute(
                profile=profile,
                prompt=prompt,
                history=history,
                conversation_summary=conversation_summary,
                tool_inputs=tool_inputs,
                user_header_id=user_header_id,
                context_key=context_key,
                cancellation=cancellation,
                on_delta=emit_delta,
            )
        except BaseException as exc:
            events.put(AssistantRuntimeExecutionEvent(kind="failed", error=exc))
            close_old_connections()
            return
        events.put(AssistantRuntimeExecutionEvent(kind="completed", result=result))
        close_old_connections()

    worker = threading.Thread(
        target=run,
        name=f"assistant-runtime-{profile.key}",
        daemon=True,
    )
    deadline = time.monotonic() + max(1, int(profile.timeout_seconds))
    worker.start()
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                cancellation.cancel()
                raise AssistantRuntimeTimeout("Assistant 실행 제한 시간을 초과했습니다.")
            try:
                event = events.get(timeout=min(RUNTIME_HEARTBEAT_SECONDS, remaining))
            except queue.Empty:
                yield AssistantRuntimeExecutionEvent(kind="heartbeat")
                continue
            if event.kind == "failed":
                if isinstance(event.error, ExternalCallCancelled) and cancellation.cancelled:
                    raise event.error
                if event.error is not None:
                    raise event.error
                raise RuntimeError("Assistant Runtime 실행에 실패했습니다.")
            yield event
            if event.kind == "completed":
                return
    finally:
        cancellation.cancel()
        worker.join(timeout=RUNTIME_WORKER_JOIN_SECONDS)


__all__ = [
    "AssistantRuntimeExecutionEvent",
    "AssistantRuntimeTimeout",
    "stream_assistant_runtime_execution",
]
