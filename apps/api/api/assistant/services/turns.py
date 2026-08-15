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
SAFE_ACCOUNT_SCOPES = frozenset(
    {"assistant", "emails", "observer", "appstore", "line-dashboard"}
)
AUTO_TOOL_PROFILE_KEYS = {
    "rag.search": "email-rag",
    "observer.analysis": "observer-analysis",
    "appstore.catalog": "appstore-context",
    "line-dashboard.snapshot": "line-dashboard-context",
}


class AssistantTurnError(RuntimeError):
    """연결 전에 JSON으로 반환할 안전한 Turn 오류입니다."""

    def __init__(
        self,
        code: str,
        *,
        status_code: int,
        message: str,
        missing_scopes: tuple[str, ...] = (),
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.message = message
        self.missing_scopes = tuple(
            scope for scope in missing_scopes if scope in SAFE_ACCOUNT_SCOPES
        )


@dataclass(frozen=True)
class PreparedAssistantTurn:
    """연결 전에 검증·저장된 Run과 실행 또는 replay 계약입니다."""

    generation: AssistantGeneration
    profile: AssistantProfile
    tool_inputs: dict[str, object]
    prompt: str
    assistant_client_id: str
    context_key: str
    input_message_id: int | None
    input_message_client_id: str | None
    memory: AssistantRuntimeMemory
    replay_message: AssistantMessage | None = None


def _request_hash(
    *,
    action: str,
    conversation_id: object,
    client_id: str,
    content: str,
    profile: AssistantProfile,
    tool_inputs: Mapping[str, object],
    target_message_id: object,
    retry_run_id: object,
    context_key: str,
) -> str:
    """최초 요청 계약만 canonical JSON으로 해시합니다."""

    payload = {
        "action": action,
        "conversationId": str(conversation_id),
        "message": {"clientId": client_id, "content": content},
        "profileKey": profile.key,
        "profileVersion": profile.version,
        "toolInputs": tool_inputs,
        "targetMessageId": str(target_message_id or ""),
        "retryRunId": str(retry_run_id or ""),
        "appContextKey": context_key,
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _assistant_client_id(*, client_request_id: str) -> str:
    """Run replay에서도 동일한 Assistant client ID를 결정적으로 생성합니다."""

    digest = hashlib.sha256(client_request_id.encode("utf-8")).hexdigest()[:32]
    return f"assistant-{digest}"


class AssistantTurnService:
    """현재 권한 하한부터 SSE 종료까지 Turn 수명주기를 관리합니다."""

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
        tool_inputs = self._filter_auto_tool_inputs(
            user=user,
            request=request,
            profile=profile,
            tool_inputs=tool_inputs,
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
            (
                access_requirements_for_scopes(())
                if profile.provider == "auto-knowledge"
                else self._tool_input_requirements(tool_inputs)
            ),
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

    def _resolve_action_contract(
        self,
        *,
        user: Any,
        request: Any,
        conversation: AssistantConversation,
        values: Mapping[str, object],
    ) -> dict[str, object]:
        """action 대상과 재사용할 의미 Profile/Tool/권한을 해석합니다."""

        action = str(values["action"])
        message_values = values["message"]
        profile = get_assistant_profile(
            profile_key=str(values["profile_key"]),
            profile_version=values.get("profile_version"),
        )
        contract: dict[str, object] = {
            "profile": profile,
            "prompt": str(message_values["content"]),
            "tool_inputs": dict(values.get("tool_inputs") or {}),
            "parent": conversation.current_message,
            "revision_of": None,
            "stored_requirements": access_requirements_for_scopes(()),
            "context_key": values.get("app_context_key"),
        }
        if action == "send":
            return contract

        target: AssistantMessage | None = None
        source_generation: AssistantGeneration | None = None
        if action in {"edit", "regenerate"}:
            target = selectors.get_assistant_message_for_user(
                user=user,
                conversation_id=conversation.id,
                client_id=str(values.get("target_message_id") or ""),
            )
        elif action == "retry":
            source_generation = selectors.get_assistant_generation_for_user(
                user=user,
                conversation_id=conversation.id,
                generation_id=values["retry_run_id"],
            )
            if source_generation is not None:
                target = selectors.get_assistant_generation_message(
                    generation=source_generation,
                    role=AssistantMessage.Roles.USER,
                )
        if target is None:
            raise AssistantTurnError(
                "target_not_found",
                status_code=404,
                message="재실행 대상 메시지 또는 Run을 찾을 수 없습니다.",
            )
        self._require_access(
            user=user,
            request=request,
            requirements=target.access_requirements,
        )
        if action == "edit":
            if target.role != AssistantMessage.Roles.USER:
                raise AssistantTurnError(
                    "invalid_target",
                    status_code=400,
                    message="edit 대상은 사용자 메시지여야 합니다.",
                )
            contract.update(parent=target.parent, revision_of=target)
            return contract

        original_user = target.parent if target.role == AssistantMessage.Roles.ASSISTANT else target
        source_generation = source_generation or target.generation
        if original_user is None or source_generation is None:
            raise AssistantTurnError(
                "invalid_target",
                status_code=409,
                message="재실행 provenance를 찾을 수 없습니다.",
            )
        self._require_access(
            user=user,
            request=request,
            requirements=source_generation.access_requirements,
        )
        semantic_profile = get_assistant_profile(
            profile_key=source_generation.profile_key,
            profile_version=source_generation.profile_version,
        )
        contract.update(
            profile=semantic_profile,
            prompt=original_user.content,
            tool_inputs=dict(source_generation.tool_inputs or {}),
            parent=original_user.parent,
            revision_of=original_user,
            stored_requirements=merge_access_requirements(
                source_generation.access_requirements,
                original_user.access_requirements,
            ),
            context_key=source_generation.context_key,
        )
        return contract

    def _normalize_tool_inputs(
        self,
        *,
        user: Any,
        profile: AssistantProfile,
        tool_inputs: Mapping[str, object],
    ) -> dict[str, object]:
        """Profile allowlist 안의 Tool 입력만 제한된 저장 계약으로 정규화합니다."""

        if set(tool_inputs) - set(profile.allowed_tools):
            raise AssistantTurnError(
                "tool_not_allowed",
                status_code=403,
                message="현재 Profile에서 허용하지 않는 Tool입니다.",
            )
        if profile.provider == "auto-knowledge":
            normalized_candidates: dict[str, object] = {}
            for tool_key, raw_input in tool_inputs.items():
                candidate_input = raw_input if isinstance(raw_input, Mapping) else {}
                if tool_key == "observer.analysis" and any(
                    not str(candidate_input.get(key) or "").strip()
                    for key in ("eqpId", "from", "to")
                ):
                    if set(candidate_input) - {
                        "eqpId",
                        "from",
                        "to",
                        "logTypes",
                        "tipGroups",
                    }:
                        raise AssistantTurnError(
                            "invalid_tool_input",
                            status_code=400,
                            message="observer.analysis에 지원하지 않는 입력이 있습니다.",
                        )
                    normalized_candidates[tool_key] = {}
                    continue
                if tool_key == "line-dashboard.snapshot" and not str(
                    candidate_input.get("lineId") or ""
                ).strip():
                    if set(candidate_input) - {"view", "lineId", "from", "to"}:
                        raise AssistantTurnError(
                            "invalid_tool_input",
                            status_code=400,
                            message="line-dashboard.snapshot에 지원하지 않는 입력이 있습니다.",
                        )
                    normalized_candidates[tool_key] = {}
                    continue
                candidate_profile = get_assistant_profile(
                    profile_key=AUTO_TOOL_PROFILE_KEYS[tool_key]
                )
                try:
                    normalized_candidates.update(
                        self._normalize_tool_inputs(
                            user=user,
                            profile=candidate_profile,
                            tool_inputs={tool_key: candidate_input},
                        )
                    )
                except AssistantTurnError as exc:
                    if exc.code != "permission_denied":
                        raise
            return normalized_candidates
        if profile.provider == "email-rag":
            raw = tool_inputs.get("rag.search")
            rag_input = raw if isinstance(raw, Mapping) else {}
            if set(rag_input) - {"permissionGroups", "ragIndexes"}:
                raise AssistantTurnError(
                    "invalid_tool_input",
                    status_code=400,
                    message="rag.search에 지원하지 않는 입력이 있습니다.",
                )
            for field_name in ("permissionGroups", "ragIndexes"):
                field_value = rag_input.get(field_name)
                if field_value is not None and not isinstance(field_value, list):
                    raise AssistantTurnError(
                        "invalid_tool_input",
                        status_code=400,
                        message=f"rag.search {field_name}는 배열이어야 합니다.",
                    )
            try:
                groups = resolve_permission_groups(
                    rag_input.get("permissionGroups"),
                    user,
                )
            except AssistantRequestError as exc:
                raise AssistantTurnError(
                    "permission_denied",
                    status_code=403,
                    message="현재 Email 검색 범위에 접근할 권한이 없습니다.",
                ) from exc
            indexes = resolve_rag_index_names(rag_input.get("ragIndexes"))
            accessible_mailboxes = (
                selectors.get_accessible_email_user_sdwt_prods_for_user(user=user)
            )
            mailboxes = [
                group for group in groups if group in accessible_mailboxes
            ]
            return {
                "rag.search": {
                    "permissionGroups": groups[:50],
                    "ragIndexes": indexes[:10],
                    "mailboxes": mailboxes[:50],
                }
            }
        if profile.provider == "observer-analysis":
            raw = tool_inputs.get("observer.analysis")
            observer_input = raw if isinstance(raw, Mapping) else {}
            required = ("eqpId", "from", "to")
            if any(not str(observer_input.get(key) or "").strip() for key in required):
                raise AssistantTurnError(
                    "invalid_tool_input",
                    status_code=400,
                    message="Observer 분석 조회 조건이 누락되었습니다.",
                )
            if not isinstance(observer_input.get("logTypes", []), list) or not isinstance(
                observer_input.get("tipGroups", []), list
            ):
                raise AssistantTurnError(
                    "invalid_tool_input",
                    status_code=400,
                    message="Observer logTypes/tipGroups는 배열이어야 합니다.",
                )
            return {
                "observer.analysis": {
                    "eqpId": str(observer_input["eqpId"]).strip()[:100],
                    "from": str(observer_input["from"]).strip()[:64],
                    "to": str(observer_input["to"]).strip()[:64],
                    "logTypes": list(observer_input.get("logTypes") or [])[:8],
                    "tipGroups": list(observer_input.get("tipGroups") or ["__ALL__"])[
                        :100
                    ],
                }
            }
        if profile.provider == "appstore-context":
            raw = tool_inputs.get("appstore.catalog")
            appstore_input = raw if isinstance(raw, Mapping) else {}
            if set(appstore_input) - {"query", "category", "selectedAppId"}:
                raise AssistantTurnError(
                    "invalid_tool_input",
                    status_code=400,
                    message="appstore.catalog에 지원하지 않는 입력이 있습니다.",
                )
            selected_app_id = appstore_input.get("selectedAppId")
            if selected_app_id in (None, ""):
                normalized_app_id = None
            else:
                try:
                    normalized_app_id = int(selected_app_id)
                except (TypeError, ValueError) as exc:
                    raise AssistantTurnError(
                        "invalid_tool_input",
                        status_code=400,
                        message="Appstore 선택 앱 ID가 올바르지 않습니다.",
                    ) from exc
                if normalized_app_id <= 0:
                    raise AssistantTurnError(
                        "invalid_tool_input",
                        status_code=400,
                        message="Appstore 선택 앱 ID가 올바르지 않습니다.",
                    )
            return {
                "appstore.catalog": {
                    "query": str(appstore_input.get("query") or "").strip()[:100],
                    "category": str(appstore_input.get("category") or "all").strip()[:100],
                    "selectedAppId": normalized_app_id,
                }
            }
        if profile.provider == "line-dashboard-context":
            raw = tool_inputs.get("line-dashboard.snapshot")
            dashboard_input = raw if isinstance(raw, Mapping) else {}
            if set(dashboard_input) - {"view", "lineId", "from", "to"}:
                raise AssistantTurnError(
                    "invalid_tool_input",
                    status_code=400,
                    message="line-dashboard.snapshot에 지원하지 않는 입력이 있습니다.",
                )
            view = str(dashboard_input.get("view") or "status").strip().lower()
            line_id = str(dashboard_input.get("lineId") or "").strip()[:50]
            if view not in {"status", "history"} or not line_id:
                raise AssistantTurnError(
                    "invalid_tool_input",
                    status_code=400,
                    message="ESOP Dashboard 화면 종류와 line ID가 필요합니다.",
                )
            normalized_dates: dict[str, str] = {}
            for field_name in ("from", "to"):
                value = str(dashboard_input.get(field_name) or "").strip()
                if not value:
                    continue
                try:
                    normalized_dates[field_name] = date.fromisoformat(
                        value[:10]
                    ).isoformat()
                except ValueError as exc:
                    raise AssistantTurnError(
                        "invalid_tool_input",
                        status_code=400,
                        message="ESOP Dashboard 조회 날짜 형식이 올바르지 않습니다.",
                    ) from exc
            return {
                "line-dashboard.snapshot": {
                    "view": view,
                    "lineId": line_id,
                    **normalized_dates,
                }
            }
        return {}

    def _filter_auto_tool_inputs(
        self,
        *,
        user: Any,
        request: Any,
        profile: AssistantProfile,
        tool_inputs: Mapping[str, object],
    ) -> dict[str, object]:
        """자동 Profile 후보 중 현재 사용자 권한이 확인된 Tool만 Runtime에 전달합니다."""

        if profile.provider != "auto-knowledge":
            return dict(tool_inputs)
        allowed: dict[str, object] = {}
        for tool_key, tool_input in tool_inputs.items():
            requirements = merge_access_requirements(
                access_requirements_for_scopes(
                    TOOL_AUTHORIZATION_FLOORS.get(tool_key, ())
                ),
                self._tool_input_requirements({tool_key: tool_input}),
            )
            if validate_access_requirements(
                user=user,
                requirements=requirements,
                request=request,
            ).allowed:
                allowed[tool_key] = tool_input
        return allowed

    def _current_authorization_floor(
        self,
        *,
        profile_key: str,
        tool_keys: tuple[str, ...],
    ) -> tuple[str, ...]:
        """현재 Profile과 Tool floor의 Account scope 합집합을 반환합니다."""

        scopes = set(get_current_assistant_profile(profile_key=profile_key).account_scopes)
        if profile_key != "auto-knowledge":
            for tool_key in tool_keys:
                scopes.update(TOOL_AUTHORIZATION_FLOORS.get(tool_key, ()))
        return tuple(sorted(scopes))

    def _tool_input_requirements(
        self,
        tool_inputs: Mapping[str, object],
    ) -> dict[str, object]:
        """실제 적용할 RAG group/mailbox 입력을 data claim으로 변환합니다."""

        rag_input = tool_inputs.get("rag.search")
        if not isinstance(rag_input, Mapping):
            return access_requirements_for_scopes(())
        return {
            "version": 1,
            "accountScopes": [],
            "dataClaims": {
                "ragPermissionGroups": list(rag_input.get("permissionGroups") or []),
                "mailboxes": list(rag_input.get("mailboxes") or []),
            },
        }

    def _require_access(
        self,
        *,
        user: Any,
        request: Any,
        requirements: object,
    ) -> None:
        """현재 요구사항이 하나라도 회수됐으면 전체 Turn을 403으로 차단합니다."""

        decision = validate_access_requirements(
            user=user,
            requirements=requirements,
            request=request,
        )
        if not decision.allowed:
            raise AssistantTurnError(
                "permission_denied",
                status_code=403,
                message="현재 이 답변에 접근할 권한이 없습니다.",
                missing_scopes=decision.missing_scopes,
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

    @transaction.atomic
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
                tool_keys=([] if profile.provider == "auto-knowledge" else list(tool_inputs)),
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
            if prepared.profile.provider != "auto-knowledge":
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
