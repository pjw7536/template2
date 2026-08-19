# =============================================================================
# 모듈: Assistant Turn 권한·Run·branch·저장·SSE orchestration
# 주요 대상: AssistantTurnService, AssistantTurnError
# 핵심 전제: 완료 replay는 어떤 대화 상태도 변경하지 않습니다.
# =============================================================================
"""표준 Assistant Turn의 준비, 실행, 저장과 replay 이벤트를 관리합니다."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import hashlib
import json
import logging
from typing import Any, Iterator, Mapping

from django.db import IntegrityError, transaction
from django.utils import timezone

import api.emails.selectors as email_selectors

from .. import selectors
from ..models import AssistantConversation, AssistantGeneration, AssistantMessage
from ..serializers import AssistantMessageSerializer
from .access_requirements import (
    access_requirements_for_scopes,
    merge_access_requirements,
    validate_access_requirements,
)
from .conversations import append_assistant_messages
from .context import resolve_assistant_turn_context_key
from .errors import AssistantRequestError
from .generations import finalize_assistant_generation
from .normalization import resolve_permission_groups, resolve_rag_index_names, validate_user_identity
from .profiles import AssistantProfile, get_assistant_profile, get_current_assistant_profile
from .runtime import TOOL_AUTHORIZATION_FLOORS, AssistantRuntime, assistant_runtime
from .runtime_execution import (
    AssistantRuntimeTimeout,
    stream_assistant_runtime_execution,
)
from .runtime_memory import AssistantRuntimeMemory, build_assistant_runtime_memory
from .turn_persistence import (
    AssistantRunFencedError,
    commit_assistant_turn_result,
)

logger = logging.getLogger(__name__)
TURN_PERSISTENCE_GRACE_SECONDS = 10
LINE_DASHBOARD_FILTER_MODES = frozenset(
    {"target_user_sdwt_prod", "user_sdwt_prod", "sdwt_prod"}
)
LINE_DASHBOARD_RECENT_HOURS_MAX = 168
SAFE_ACCOUNT_SCOPES = frozenset(
    {"assistant", "emails", "observer", "appstore", "line-dashboard"}
)

from .turn_contracts import (
    AssistantTurnError,
    AssistantTurnValidationMixin,
    PreparedAssistantTurn,
    _assistant_client_id,
    _request_hash,
)


class AssistantTurnService(AssistantTurnValidationMixin):
    """준비부터 SSE 저장 종료까지 Turn 수명주기를 조율합니다."""

    def __init__(self, *, runtime: AssistantRuntime | None = None) -> None:
        """테스트 Provider를 주입할 수 있도록 service를 초기화합니다."""

        self.runtime = runtime or assistant_runtime

    def prepare_turn(
        self,
        *,
        user: Any,
        request: Any,
        values: Mapping[str, object],
    ) -> PreparedAssistantTurn:
        """연결 전에 권한·idempotency·branch를 검증하고 Run/user message를 생성합니다.

        오류:
            입력 대상, 현재 권한, idempotency, 활성 Run 충돌은 AssistantTurnError입니다.
        """

        conversation = selectors.get_assistant_conversation_for_user(
            user=user,
            conversation_id=values["conversation_id"],
        )
        if conversation is None:
            raise AssistantTurnError(
                "conversation_not_found",
                status_code=404,
                message="대화방을 찾을 수 없습니다.",
            )

        action_contract = self._resolve_action_contract(
            user=user,
            request=request,
            conversation=conversation,
            values=values,
        )
        profile = action_contract["profile"]
        prompt = action_contract["prompt"]
        tool_inputs = self._normalize_tool_inputs(
            user=user,
            profile=profile,
            tool_inputs=action_contract["tool_inputs"],
        )
        context_key = resolve_assistant_turn_context_key(
            profile=profile,
            raw_context_key=action_contract["context_key"],
            tool_inputs=tool_inputs,
        )
        current_floor = self._current_authorization_floor(
            profile_key=profile.key,
            tool_keys=tuple(tool_inputs),
        )
        stored_requirements = action_contract["stored_requirements"]
        memory = build_assistant_runtime_memory(
            user=user,
            conversation=conversation,
            profile=profile,
            request=request,
        )
        initial_requirements = merge_access_requirements(
            access_requirements_for_scopes(current_floor),
            stored_requirements,
            memory.access_requirements,
            self._tool_input_requirements(tool_inputs),
        )
        self._require_access(
            user=user,
            request=request,
            requirements=initial_requirements,
        )

        message_values = values["message"]
        request_hash = _request_hash(
            action=str(values["action"]),
            conversation_id=conversation.id,
            client_id=str(message_values["client_id"]),
            content=prompt,
            profile=profile,
            tool_inputs=tool_inputs,
            target_message_id=values.get("target_message_id"),
            retry_run_id=values.get("retry_run_id"),
            context_key=context_key,
        )
        existing = AssistantGeneration.objects.filter(
            user=user,
            client_request_id=values["client_request_id"],
        ).first()
        if existing is not None:
            return self._prepare_replay(
                existing=existing,
                request_hash=request_hash,
                user=user,
                request=request,
                profile=profile,
                memory=memory,
            )

        return self._create_turn(
            user=user,
            conversation=conversation,
            values=values,
            action_contract=action_contract,
            profile=profile,
            prompt=prompt,
            tool_inputs=tool_inputs,
            memory=memory,
            access_requirements=initial_requirements,
            request_hash=request_hash,
            context_key=context_key,
        )

    def _prepare_replay(
        self,
        *,
        existing: AssistantGeneration,
        request_hash: str,
        user: Any,
        request: Any,
        profile: AssistantProfile,
        memory: AssistantRuntimeMemory,
    ) -> PreparedAssistantTurn:
        """동일 완료 Run을 현재 권한으로 재검증하고 저장 답변 replay를 준비합니다."""

        if existing.request_hash != request_hash:
            raise AssistantTurnError(
                "idempotency_conflict",
                status_code=409,
                message="같은 요청 ID를 다른 계약에 재사용할 수 없습니다.",
            )
        if existing.status != AssistantGeneration.Status.COMPLETED:
            raise AssistantTurnError(
                "run_not_replayable",
                status_code=409,
                message="완료되지 않은 Run은 replay할 수 없습니다.",
            )
        floor = access_requirements_for_scopes(
            self._current_authorization_floor(
                profile_key=existing.profile_key,
                tool_keys=tuple(existing.tool_keys or ()),
            )
        )
        self._require_access(
            user=user,
            request=request,
            requirements=merge_access_requirements(floor, existing.access_requirements),
        )
        message = selectors.get_assistant_generation_message(
            generation=existing,
            role=AssistantMessage.Roles.ASSISTANT,
            latest=True,
        )
        if message is None:
            raise AssistantTurnError(
                "run_output_missing",
                status_code=409,
                message="완료 Run의 저장 답변을 찾을 수 없습니다.",
            )
        return PreparedAssistantTurn(
            generation=existing,
            profile=profile,
            tool_inputs=dict(existing.tool_inputs or {}),
            prompt="",
            assistant_client_id=message.client_id,
            context_key=existing.context_key,
            input_message_id=None,
            input_message_client_id=None,
            memory=memory,
            replay_message=message,
        )

    def _create_turn(
        self,
        *,
        user: Any,
        conversation: AssistantConversation,
        values: Mapping[str, object],
        action_contract: Mapping[str, object],
        profile: AssistantProfile,
        prompt: str,
        tool_inputs: dict[str, object],
        memory: AssistantRuntimeMemory,
        access_requirements: dict[str, object],
        request_hash: str,
        context_key: str,
    ) -> PreparedAssistantTurn:
        """Run과 하나의 새 user branch revision을 같은 transaction에 생성합니다."""

        now = timezone.now()
        AssistantGeneration.objects.filter(
            user=user,
            status__in=(AssistantGeneration.Status.QUEUED, AssistantGeneration.Status.STREAMING),
            expires_at__lte=now,
        ).update(
            status=AssistantGeneration.Status.FAILED,
            error_code="lease_expired",
            finished_at=now,
            updated_at=now,
        )
        try:
            generation = AssistantGeneration.objects.create(
                user=user,
                conversation=conversation,
                client_request_id=values["client_request_id"],
                context_key=context_key,
                status=AssistantGeneration.Status.STREAMING,
                provider=profile.provider,
                profile_key=profile.key,
                profile_version=profile.version,
                tool_keys=list(tool_inputs),
                tool_inputs=tool_inputs,
                memory_partition=profile.write_partition,
                access_requirements=access_requirements,
                request_hash=request_hash,
                started_at=now,
                expires_at=now
                + timedelta(
                    seconds=profile.timeout_seconds
                    + TURN_PERSISTENCE_GRACE_SECONDS
                ),
            )
        except IntegrityError as exc:
            raise AssistantTurnError(
                "run_conflict",
                status_code=409,
                message="이미 다른 답변을 생성하고 있습니다.",
            ) from exc

        message_values = values["message"]
        try:
            stored = append_assistant_messages(
                conversation=conversation,
                messages=[
                    {
                        "client_id": message_values["client_id"],
                        "role": AssistantMessage.Roles.USER,
                        "content": prompt,
                        "context_key": context_key,
                        "generation_id": generation.id,
                        "parent_id": (
                            action_contract["parent"].client_id
                            if action_contract.get("parent") is not None
                            else None
                        ),
                        "revision_of_id": (
                            action_contract["revision_of"].client_id
                            if action_contract.get("revision_of") is not None
                            else None
                        ),
                        "access_requirements": access_requirements,
                    }
                ],
            )[0]
        except (IntegrityError, ValueError) as exc:
            raise AssistantTurnError(
                "message_conflict",
                status_code=409,
                message="새 사용자 메시지 ID 또는 branch가 충돌했습니다.",
            ) from exc
        if stored.generation_id != generation.id:
            raise AssistantTurnError(
                "message_conflict",
                status_code=409,
                message="새 user client ID가 필요합니다.",
            )
        return PreparedAssistantTurn(
            generation=generation,
            profile=profile,
            tool_inputs=tool_inputs,
            prompt=prompt,
            assistant_client_id=_assistant_client_id(
                client_request_id=str(values["client_request_id"])
            ),
            context_key=context_key,
            input_message_id=stored.id,
            input_message_client_id=stored.client_id,
            memory=memory,
        )

    def stream_turn(
        self,
        *,
        prepared: PreparedAssistantTurn,
        request: Any,
    ) -> Iterator[tuple[str, dict[str, object]]]:
        """준비된 Turn을 표준 event payload로 실행하거나 완료 답변을 replay합니다."""

        generation = prepared.generation
        yield (
            "run.started",
            {
                "runId": str(generation.id),
                "assistantClientId": prepared.assistant_client_id,
                "profileKey": prepared.profile.key,
                "profileVersion": prepared.profile.version,
                "replay": prepared.replay_message is not None,
            },
        )
        if prepared.replay_message is not None:
            serialized = AssistantMessageSerializer(
                prepared.replay_message,
                context={"request": request},
            ).data
            yield "message.completed", dict(serialized)
            yield "run.completed", {"runId": str(generation.id), "replay": True}
            return

        try:
            for tool_key in prepared.tool_inputs:
                yield "tool.started", {"runId": str(generation.id), "toolKey": tool_key}
            _, user_header_id = validate_user_identity(request.user)
            execution = stream_assistant_runtime_execution(
                runtime=self.runtime,
                profile=prepared.profile,
                prompt=prepared.prompt,
                history=prepared.memory.history,
                conversation_summary=prepared.memory.summary,
                tool_inputs=prepared.tool_inputs,
                user_header_id=user_header_id,
                context_key=prepared.context_key,
            )
            result = None
            try:
                for runtime_event in execution:
                    if runtime_event.kind == "heartbeat":
                        yield "run.heartbeat", {"runId": str(generation.id)}
                    elif runtime_event.kind == "delta":
                        yield (
                            "message.delta",
                            {
                                "runId": str(generation.id),
                                "assistantClientId": prepared.assistant_client_id,
                                "content": runtime_event.delta,
                            },
                        )
                    elif runtime_event.kind == "completed":
                        result = runtime_event.result
            finally:
                execution.close()
            if result is None:
                raise RuntimeError("Assistant Runtime 결과가 없습니다.")
            yield "run.heartbeat", {"runId": str(generation.id)}
            if prepared.input_message_id is None or prepared.input_message_client_id is None:
                raise AssistantRunFencedError("Turn 입력 provenance가 없습니다.")
            self._require_access(
                user=request.user,
                request=request,
                requirements=merge_access_requirements(
                    generation.access_requirements,
                    result.access_requirements,
                ),
            )
            generation, message = commit_assistant_turn_result(
                generation_id=generation.id,
                input_message_id=prepared.input_message_id,
                input_message_client_id=prepared.input_message_client_id,
                assistant_client_id=prepared.assistant_client_id,
                context_key=prepared.context_key,
                result=result,
            )
            for tool_key in result.tool_keys:
                yield (
                    "tool.completed",
                    {
                        "runId": str(generation.id),
                        "toolKey": tool_key,
                        "stats": result.execution_metadata,
                    },
                )
            serialized = AssistantMessageSerializer(
                message,
                context={"request": request},
            ).data
            yield "message.completed", dict(serialized)
            yield "run.completed", {"runId": str(generation.id), "replay": False}
        except GeneratorExit:
            finalize_assistant_generation(
                generation=generation,
                status=AssistantGeneration.Status.STOPPED,
                error_code="client_disconnected",
            )
            raise
        except Exception as exc:
            error_code = (
                "runtime_timeout"
                if isinstance(exc, AssistantRuntimeTimeout)
                else "run_fenced"
                if isinstance(exc, AssistantRunFencedError)
                else exc.code
                if isinstance(exc, AssistantTurnError)
                else "runtime_failed"
            )
            finalize_assistant_generation(
                generation=generation,
                status=AssistantGeneration.Status.FAILED,
                error_code=error_code,
            )
            logger.exception(
                "Assistant Turn 실행 실패: run_id=%s error_code=%s",
                generation.id,
                error_code,
            )
            yield (
                "run.failed",
                {
                    "runId": str(generation.id),
                    "code": error_code,
                    "message": "Assistant 실행에 실패했습니다. 잠시 후 다시 시도해주세요.",
                },
            )


assistant_turn_service = AssistantTurnService()


__all__ = [
    "AssistantTurnError",
    "AssistantTurnService",
    "PreparedAssistantTurn",
    "assistant_turn_service",
]
