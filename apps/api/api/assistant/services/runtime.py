# =============================================================================
# 모듈: 저장 책임이 없는 Assistant Runtime 실행 코어
# 주요 대상: AssistantRuntime, AssistantRuntimeResult
# 핵심 전제: 권한·Run·메시지·branch 저장은 호출자인 Turn service가 담당합니다.
# =============================================================================
"""Profile에 고정된 Tool과 Provider 호출을 실행하고 결과를 정규화합니다."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any, Mapping, Sequence

import api.appstore.selectors as appstore_selectors
import api.drone.selectors as drone_selectors
from api.assistant.models import ASSISTANT_OPENWEBUI_CONTEXT_PREFIX
from api.common.services import ExternalCallCancellation
from api.observer.selectors import OBSERVER_LOG_KEYS
from api.observer.services import (
    MAX_OBSERVER_QUERY_DAYS,
    analyze_observer_logs_stream,
    normalize_observer_datetime,
)

from .access_requirements import access_requirements_for_scopes, merge_access_requirements
from .chat import AssistantChatService
from .knowledge_intent import (
    KnowledgeRouteDecision,
    decide_app_knowledge_use,
    decide_auto_knowledge_route,
)
from .openwebui import build_openwebui_grounded_system_message, stream_openwebui_chat
from .profiles import AssistantProfile, get_assistant_profile
from .runtime_memory import format_assistant_runtime_context


TOOL_AUTHORIZATION_FLOORS: dict[str, tuple[str, ...]] = {
    "rag.search": ("assistant", "emails"),
    "observer.analysis": ("assistant", "observer"),
    "appstore.catalog": ("assistant", "appstore"),
    "line-dashboard.snapshot": ("assistant", "line-dashboard"),
}
MAX_RUNTIME_SOURCES = 50
MAX_RUNTIME_SOURCE_ID_CHARS = 200
MAX_RUNTIME_SOURCE_TITLE_CHARS = 500
AUTO_APP_TOOL_KEYS = {
    "emails": "rag.search",
    "observer": "observer.analysis",
    "appstore": "appstore.catalog",
    "line-dashboard": "line-dashboard.snapshot",
}
AUTO_APP_PROFILE_KEYS = {
    "emails": "email-rag",
    "observer": "observer-analysis",
    "appstore": "appstore-context",
    "line-dashboard": "line-dashboard-context",
}


def _normalize_runtime_sources(
    sources: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Provider source 원문을 저장하지 않고 ID와 제한된 제목만 보존합니다."""

    normalized: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    for source in sources:
        doc_id = str(source.get("doc_id") or "").strip()[:MAX_RUNTIME_SOURCE_ID_CHARS]
        if not doc_id or doc_id in seen_ids:
            continue
        seen_ids.add(doc_id)
        normalized.append(
            {
                "doc_id": doc_id,
                "title": str(source.get("title") or "").strip()[
                    :MAX_RUNTIME_SOURCE_TITLE_CHARS
                ],
            }
        )
        if len(normalized) >= MAX_RUNTIME_SOURCES:
            break
    return normalized


@dataclass(frozen=True)
class AssistantRuntimeResult:
    """Provider 응답과 파생 message 본문·출처·권한 metadata입니다."""

    content: str
    blocks: list[dict[str, object]] = field(default_factory=list)
    sources: list[dict[str, object]] = field(default_factory=list)
    tool_keys: list[str] = field(default_factory=list)
    access_requirements: dict[str, object] = field(default_factory=dict)
    execution_metadata: dict[str, object] = field(default_factory=dict)
    context_snapshot: dict[str, object] | None = None


class AssistantRuntime:
    """DB 상태를 변경하지 않고 Profile별 실행을 수행합니다."""

    def __init__(self, *, email_chat_service: AssistantChatService | None = None) -> None:
        """테스트에서 Provider 구현을 주입할 수 있도록 Runtime을 초기화합니다."""

        self.email_chat_service = email_chat_service or AssistantChatService()

    def execute(
        self,
        *,
        profile: AssistantProfile,
        prompt: str,
        history: Sequence[Mapping[str, str]],
        conversation_summary: str,
        tool_inputs: Mapping[str, object],
        user_header_id: str | None,
        context_key: str,
        cancellation: ExternalCallCancellation,
        on_delta: Callable[[str], None] | None = None,
    ) -> AssistantRuntimeResult:
        """Profile의 허용 Tool과 Provider를 실행해 저장 가능한 결과를 반환합니다.

        입력:
            profile: registry에서 해석한 지원 Profile 버전입니다.
            history/summary: 권한 검증을 통과한 서버 메모리만 포함합니다.
            tool_inputs: serializer가 제한한 Tool별 입력입니다.

        부작용:
            선택한 RAG/OpenWebUI/Observer 외부 호출과 Observer 현재 데이터 재조회가 발생합니다.

        오류:
            Provider/Tool 설정 또는 외부 호출 오류는 기존 domain 예외를 전달합니다.
        """

        if profile.provider == "openwebui":
            return self._execute_openwebui(
                profile=profile,
                prompt=prompt,
                history=history,
                conversation_summary=conversation_summary,
                context_key=context_key,
                cancellation=cancellation,
                on_delta=on_delta,
            )
        if profile.provider == "email-rag":
            return self._execute_email_rag(
                profile=profile,
                prompt=prompt,
                conversation_summary=conversation_summary,
                history=history,
                tool_inputs=tool_inputs,
                user_header_id=user_header_id,
                cancellation=cancellation,
                on_delta=on_delta,
            )
        if profile.provider == "observer-analysis":
            return self._execute_observer(
                profile=profile,
                prompt=prompt,
                conversation_summary=conversation_summary,
                history=history,
                tool_inputs=tool_inputs,
                user_header_id=user_header_id,
                cancellation=cancellation,
                on_delta=on_delta,
            )
        if profile.provider == "appstore-context":
            return self._execute_appstore_context(
                profile=profile,
                prompt=prompt,
                history=history,
                conversation_summary=conversation_summary,
                tool_inputs=tool_inputs,
                user_header_id=user_header_id,
                cancellation=cancellation,
                on_delta=on_delta,
            )
        if profile.provider == "line-dashboard-context":
            return self._execute_line_dashboard_context(
                profile=profile,
                prompt=prompt,
                history=history,
                conversation_summary=conversation_summary,
                tool_inputs=tool_inputs,
                user_header_id=user_header_id,
                cancellation=cancellation,
                on_delta=on_delta,
            )
        if profile.provider == "auto-knowledge":
            return self._execute_auto_knowledge(
                profile=profile,
                prompt=prompt,
                history=history,
                conversation_summary=conversation_summary,
                tool_inputs=tool_inputs,
                user_header_id=user_header_id,
                context_key=context_key,
                cancellation=cancellation,
                on_delta=on_delta,
            )
        raise ValueError("지원하지 않는 Assistant Provider입니다.")

    def _execute_openwebui(
        self,
        *,
        profile: AssistantProfile,
        prompt: str,
        history: Sequence[Mapping[str, str]],
        conversation_summary: str,
        context_key: str,
        cancellation: ExternalCallCancellation,
        on_delta: Callable[[str], None] | None,
        execution_metadata: Mapping[str, object] | None = None,
    ) -> AssistantRuntimeResult:
        """Portal OpenWebUI 응답을 일반 text block으로 정규화합니다."""

        request_history = [*history, {"role": "user", "content": prompt}]
        content_parts: list[str] = []
        remaining_chars = profile.max_output_chars
        for raw_delta in stream_openwebui_chat(
            history=request_history,
            conversation_summary=conversation_summary,
            context_key=context_key,
            cancellation=cancellation,
        ):
            delta = raw_delta[:remaining_chars]
            if not delta:
                break
            content_parts.append(delta)
            remaining_chars -= len(delta)
            if on_delta is not None:
                on_delta(delta)
        content = "".join(content_parts)
        return AssistantRuntimeResult(
            content=content,
            blocks=[{"type": "text", "content": content, "sourceIds": []}],
            access_requirements=access_requirements_for_scopes(profile.account_scopes),
            execution_metadata={
                **dict(execution_metadata or {}),
                "outputChars": len(content),
            },
        )

    def _auto_active_app_key(self, context_key: str) -> str:
        """검증된 OpenWebUI context key에서 현재 앱 key를 추출합니다."""

        if not context_key.startswith(ASSISTANT_OPENWEBUI_CONTEXT_PREFIX):
            return ""
        return context_key[len(ASSISTANT_OPENWEBUI_CONTEXT_PREFIX) :]

    def _auto_available_app_keys(
        self,
        tool_inputs: Mapping[str, object],
    ) -> tuple[str, ...]:
        """권한 필터링 후 남은 Tool 입력을 자동 라우터 앱 key로 변환합니다."""

        return tuple(
            app_key
            for app_key, tool_key in AUTO_APP_TOOL_KEYS.items()
            if tool_key in tool_inputs
        )

    def _auto_target_tool_inputs(
        self,
        *,
        decision: KnowledgeRouteDecision,
        tool_inputs: Mapping[str, object],
    ) -> dict[str, object] | None:
        """라우터의 명시 범위를 현재 화면 범위에 덮어써 단일 Tool 입력을 만듭니다."""

        target_app = decision.target_app
        tool_key = AUTO_APP_TOOL_KEYS.get(target_app)
        if not tool_key or tool_key not in tool_inputs:
            return None
        raw_input = tool_inputs.get(tool_key)
        merged = dict(raw_input) if isinstance(raw_input, Mapping) else {}
        hints = decision.scope_hints

        if target_app == "observer":
            for field_name in ("eqpId", "from", "to", "logTypes", "tipGroups"):
                if field_name in hints:
                    merged[field_name] = hints[field_name]
            if any(not str(merged.get(key) or "").strip() for key in ("eqpId", "from", "to")):
                return None
            if not list(merged.get("logTypes") or []):
                return None
            merged.setdefault("tipGroups", ["__ALL__"])
        elif target_app == "line-dashboard":
            for field_name in ("lineId", "view", "from", "to"):
                if field_name in hints:
                    merged[field_name] = hints[field_name]
            if not str(merged.get("lineId") or "").strip():
                return None
            merged.setdefault("view", "status")
        elif target_app == "appstore":
            for field_name in ("query", "category"):
                if field_name in hints:
                    merged[field_name] = hints[field_name]
            if "query" in hints:
                merged["selectedAppId"] = None
            merged.setdefault("category", "all")

        return {tool_key: merged}

    def _auto_clarification_reply(
        self,
        *,
        profile: AssistantProfile,
        target_app: str,
        on_delta: Callable[[str], None] | None,
    ) -> AssistantRuntimeResult:
        """필수 조회 범위가 없을 때 도구 호출 없이 안전한 명확화 질문을 반환합니다."""

        messages = {
            "observer": (
                "Observer 분석에 필요한 범위가 부족합니다. 분석할 장비, 기간, 로그 유형을 "
                "알려주세요. 예: EQP-01, 지난 2시간, FDC Interlock 로그"
            ),
            "line-dashboard": (
                "Line Dashboard 조회에 필요한 Line ID가 없습니다. 조회할 Line과 상태 또는 "
                "이력 범위를 알려주세요."
            ),
            "emails": "현재 요청에서 사용할 수 있는 Email 검색 범위를 확인할 수 없습니다.",
            "appstore": "현재 요청에서 사용할 수 있는 Appstore 조회 범위를 확인할 수 없습니다.",
        }
        content = messages.get(
            target_app,
            "요청한 업무 지식의 대상을 조금 더 구체적으로 알려주세요.",
        )
        if on_delta is not None:
            on_delta(content)
        return AssistantRuntimeResult(
            content=content,
            blocks=[{"type": "text", "content": content, "sourceIds": []}],
            access_requirements=access_requirements_for_scopes(profile.account_scopes),
            execution_metadata={
                "knowledgeRequested": False,
                "routingAction": "clarify",
                "selectedKnowledgeApp": target_app,
                "outputChars": len(content),
            },
        )

    def _with_auto_route_metadata(
        self,
        result: AssistantRuntimeResult,
        *,
        decision: KnowledgeRouteDecision,
    ) -> AssistantRuntimeResult:
        """선택된 하위 Profile 결과에 자동 라우팅 provenance를 추가합니다."""

        return replace(
            result,
            execution_metadata={
                **result.execution_metadata,
                "routingAction": decision.action,
                "selectedKnowledgeApp": decision.target_app,
                "routingFallback": decision.used_fallback,
            },
        )

    def _execute_auto_target(
        self,
        *,
        decision: KnowledgeRouteDecision,
        prompt: str,
        history: Sequence[Mapping[str, str]],
        conversation_summary: str,
        selected_tool_inputs: Mapping[str, object],
        user_header_id: str | None,
        cancellation: ExternalCallCancellation,
        on_delta: Callable[[str], None] | None,
    ) -> AssistantRuntimeResult:
        """자동 라우터가 선택한 앱의 기존 v1 실행 의미를 내부적으로 재사용합니다."""

        child_profile = get_assistant_profile(
            profile_key=AUTO_APP_PROFILE_KEYS[decision.target_app],
            profile_version=1,
        )
        common = {
            "profile": child_profile,
            "prompt": prompt,
            "history": history,
            "conversation_summary": conversation_summary,
            "tool_inputs": selected_tool_inputs,
            "user_header_id": user_header_id,
            "cancellation": cancellation,
            "on_delta": on_delta,
        }
        if decision.target_app == "emails":
            result = self._execute_email_rag(**common)
        elif decision.target_app == "observer":
            result = self._execute_observer(**common)
        elif decision.target_app == "appstore":
            result = self._execute_appstore_context(**common)
        else:
            result = self._execute_line_dashboard_context(**common)
        return self._with_auto_route_metadata(result, decision=decision)

    def _execute_auto_knowledge(
        self,
        *,
        profile: AssistantProfile,
        prompt: str,
        history: Sequence[Mapping[str, str]],
        conversation_summary: str,
        tool_inputs: Mapping[str, object],
        user_header_id: str | None,
        context_key: str,
        cancellation: ExternalCallCancellation,
        on_delta: Callable[[str], None] | None,
    ) -> AssistantRuntimeResult:
        """현재 앱 우선 상위 라우터로 일반 답변 또는 하나의 앱 지식을 실행합니다."""

        active_app_key = self._auto_active_app_key(context_key)
        available_app_keys = self._auto_available_app_keys(tool_inputs)
        decision = decide_auto_knowledge_route(
            prompt,
            active_app_key=active_app_key,
            available_app_keys=available_app_keys,
            conversation_context=format_assistant_runtime_context(
                history=[dict(item) for item in history],
                summary=conversation_summary,
            ),
            cancellation=cancellation,
            user_header_id=user_header_id,
        )
        if decision.action == "general" or (
            decision.action == "current_app" and active_app_key not in AUTO_APP_TOOL_KEYS
        ):
            result = self._execute_openwebui(
                profile=profile,
                prompt=prompt,
                history=history,
                conversation_summary=conversation_summary,
                context_key=context_key,
                cancellation=cancellation,
                on_delta=on_delta,
                execution_metadata={
                    "knowledgeRequested": False,
                    "routingAction": decision.action,
                    "selectedKnowledgeApp": (
                        active_app_key if decision.action == "current_app" else ""
                    ),
                    "routingFallback": decision.used_fallback,
                },
            )
            return result
        if decision.action == "clarify":
            return self._auto_clarification_reply(
                profile=profile,
                target_app=decision.target_app,
                on_delta=on_delta,
            )
        selected_tool_inputs = self._auto_target_tool_inputs(
            decision=decision,
            tool_inputs=tool_inputs,
        )
        if selected_tool_inputs is None:
            return self._auto_clarification_reply(
                profile=profile,
                target_app=decision.target_app,
                on_delta=on_delta,
            )
        return self._execute_auto_target(
            decision=decision,
            prompt=prompt,
            history=history,
            conversation_summary=conversation_summary,
            selected_tool_inputs=selected_tool_inputs,
            user_header_id=user_header_id,
            cancellation=cancellation,
            on_delta=on_delta,
        )

    def _should_use_app_knowledge(
        self,
        *,
        profile: AssistantProfile,
        app_key: str,
        prompt: str,
        history: Sequence[Mapping[str, str]],
        conversation_summary: str,
        user_header_id: str | None,
        cancellation: ExternalCallCancellation,
    ) -> bool:
        """Profile 버전과 질문 의도에 따라 앱의 동적 데이터 도구 사용 여부를 반환합니다."""

        if profile.version < 2:
            return True
        decision = decide_app_knowledge_use(
            app_key,
            prompt,
            conversation_context=format_assistant_runtime_context(
                history=[dict(item) for item in history],
                summary=conversation_summary,
            ),
            cancellation=cancellation,
            user_header_id=user_header_id,
        )
        return decision.use_knowledge

    def _execute_app_general_reply(
        self,
        *,
        profile: AssistantProfile,
        app_key: str,
        prompt: str,
        history: Sequence[Mapping[str, str]],
        conversation_summary: str,
        cancellation: ExternalCallCancellation,
        on_delta: Callable[[str], None] | None,
    ) -> AssistantRuntimeResult:
        """동적 앱 데이터 없이 현재 앱의 수동적 설명만 허용한 일반 답변을 생성합니다."""

        return self._execute_openwebui(
            profile=profile,
            prompt=prompt,
            history=history,
            conversation_summary=conversation_summary,
            context_key=f"assistant:openwebui:{app_key}",
            cancellation=cancellation,
            on_delta=on_delta,
            execution_metadata={"knowledgeRequested": False},
        )

    def _execute_grounded_openwebui(
        self,
        *,
        profile: AssistantProfile,
        app_key: str,
        tool_key: str,
        snapshot: Mapping[str, object],
        prompt: str,
        history: Sequence[Mapping[str, str]],
        conversation_summary: str,
        cancellation: ExternalCallCancellation,
        on_delta: Callable[[str], None] | None,
        execution_metadata: Mapping[str, object],
    ) -> AssistantRuntimeResult:
        """서버 조회 snapshot을 system message에 넣어 OpenWebUI 답변을 생성합니다."""

        request_history = [*history, {"role": "user", "content": prompt}]
        system_message = build_openwebui_grounded_system_message(
            app_key=app_key,
            snapshot=snapshot,
        )
        content_parts: list[str] = []
        remaining_chars = profile.max_output_chars
        for raw_delta in stream_openwebui_chat(
            history=request_history,
            conversation_summary=conversation_summary,
            system_message=system_message,
            context_key=None,
            cancellation=cancellation,
        ):
            delta = raw_delta[:remaining_chars]
            if not delta:
                break
            content_parts.append(delta)
            remaining_chars -= len(delta)
            if on_delta is not None:
                on_delta(delta)
        content = "".join(content_parts)
        return AssistantRuntimeResult(
            content=content,
            blocks=[{"type": "text", "content": content, "sourceIds": []}],
            tool_keys=[tool_key],
            access_requirements=access_requirements_for_scopes(profile.account_scopes),
            execution_metadata={
                **dict(execution_metadata),
                "outputChars": len(content),
            },
        )

    def _execute_appstore_context(
        self,
        *,
        profile: AssistantProfile,
        prompt: str,
        history: Sequence[Mapping[str, str]],
        conversation_summary: str,
        tool_inputs: Mapping[str, object],
        user_header_id: str | None,
        cancellation: ExternalCallCancellation,
        on_delta: Callable[[str], None] | None,
    ) -> AssistantRuntimeResult:
        """현재 Appstore 필터에 맞는 제한된 앱 카탈로그로 답변합니다."""

        if not self._should_use_app_knowledge(
            profile=profile,
            app_key="appstore",
            prompt=prompt,
            history=history,
            conversation_summary=conversation_summary,
            user_header_id=user_header_id,
            cancellation=cancellation,
        ):
            return self._execute_app_general_reply(
                profile=profile,
                app_key="appstore",
                prompt=prompt,
                history=history,
                conversation_summary=conversation_summary,
                cancellation=cancellation,
                on_delta=on_delta,
            )

        raw_input = tool_inputs.get("appstore.catalog")
        catalog_input = raw_input if isinstance(raw_input, Mapping) else {}
        snapshot = appstore_selectors.get_appstore_assistant_catalog(
            query=str(catalog_input.get("query") or ""),
            category=str(catalog_input.get("category") or "all"),
            selected_app_id=catalog_input.get("selectedAppId"),
        )
        return self._execute_grounded_openwebui(
            profile=profile,
            app_key="appstore",
            tool_key="appstore.catalog",
            snapshot=snapshot,
            prompt=prompt,
            history=history,
            conversation_summary=conversation_summary,
            cancellation=cancellation,
            on_delta=on_delta,
            execution_metadata={
                "knowledgeRequested": True,
                "resultCount": int(snapshot.get("count") or 0),
                "truncated": bool(snapshot.get("truncated")),
            },
        )

    def _execute_line_dashboard_context(
        self,
        *,
        profile: AssistantProfile,
        prompt: str,
        history: Sequence[Mapping[str, str]],
        conversation_summary: str,
        tool_inputs: Mapping[str, object],
        user_header_id: str | None,
        cancellation: ExternalCallCancellation,
        on_delta: Callable[[str], None] | None,
    ) -> AssistantRuntimeResult:
        """현재 ESOP line·기간의 집계 snapshot으로 답변합니다."""

        if not self._should_use_app_knowledge(
            profile=profile,
            app_key="line-dashboard",
            prompt=prompt,
            history=history,
            conversation_summary=conversation_summary,
            user_header_id=user_header_id,
            cancellation=cancellation,
        ):
            return self._execute_app_general_reply(
                profile=profile,
                app_key="line-dashboard",
                prompt=prompt,
                history=history,
                conversation_summary=conversation_summary,
                cancellation=cancellation,
                on_delta=on_delta,
            )

        raw_input = tool_inputs.get("line-dashboard.snapshot")
        dashboard_input = raw_input if isinstance(raw_input, Mapping) else {}
        snapshot = drone_selectors.get_line_dashboard_assistant_snapshot(
            line_id=dashboard_input.get("lineId"),
            view=dashboard_input.get("view"),
            from_value=dashboard_input.get("from"),
            to_value=dashboard_input.get("to"),
        )
        return self._execute_grounded_openwebui(
            profile=profile,
            app_key="line-dashboard",
            tool_key="line-dashboard.snapshot",
            snapshot=snapshot,
            prompt=prompt,
            history=history,
            conversation_summary=conversation_summary,
            cancellation=cancellation,
            on_delta=on_delta,
            execution_metadata={
                "knowledgeRequested": True,
                "resultCount": int(snapshot.get("totalCount") or 0),
                "from": str(snapshot.get("from") or ""),
                "to": str(snapshot.get("to") or ""),
            },
        )

    def _execute_email_rag(
        self,
        *,
        profile: AssistantProfile,
        prompt: str,
        conversation_summary: str,
        history: Sequence[Mapping[str, str]],
        tool_inputs: Mapping[str, object],
        user_header_id: str | None,
        cancellation: ExternalCallCancellation,
        on_delta: Callable[[str], None] | None,
    ) -> AssistantRuntimeResult:
        """Email RAG 검색과 Provider 결과를 block/source reference 형태로 정규화합니다."""

        rag_input = tool_inputs.get("rag.search")
        normalized_input = rag_input if isinstance(rag_input, Mapping) else {}
        permission_groups = list(normalized_input.get("permissionGroups") or [])
        mailboxes = list(normalized_input.get("mailboxes") or [])
        rag_indexes = list(normalized_input.get("ragIndexes") or [])
        chat_kwargs = {
            "user_header_id": user_header_id,
            "rag_index_names": rag_indexes,
            "permission_groups": permission_groups,
            "conversation_context": format_assistant_runtime_context(
                history=[dict(item) for item in history],
                summary=conversation_summary,
            ),
        }
        result = self.email_chat_service.generate_reply_stream(
            prompt,
            cancellation=cancellation,
            auto_route_knowledge=profile.version >= 2,
            **chat_kwargs,
        )
        knowledge_requested = bool(getattr(result, "knowledge_requested", True))
        rag_search_performed = bool(
            getattr(result, "rag_search_performed", True)
        )
        actual_mailboxes = {
            str(source.get("_mailbox") or "").strip()
            for source in result.retrieved_sources
            if isinstance(source, Mapping)
            and str(source.get("_mailbox") or "").strip()
        }
        sources = _normalize_runtime_sources(result.sources)
        blocks: list[dict[str, object]] = []
        remaining_chars = profile.max_output_chars
        used_source_ids: set[str] = set()
        for segment in result.segments[:20]:
            segment_content = str(segment.get("reply") or "")[:remaining_chars]
            if not segment_content:
                break
            source_ids = [
                str(source.get("doc_id") or "").strip()
                for source in segment.get("sources", [])
                if str(source.get("doc_id") or "").strip()
                and str(source.get("doc_id") or "").strip() not in used_source_ids
            ][: max(0, 50 - len(used_source_ids))]
            used_source_ids.update(source_ids)
            blocks.append(
                {
                    "type": "text",
                    "content": segment_content,
                    "sourceIds": source_ids,
                }
            )
            remaining_chars -= len(segment_content)
        content = str(result.reply or "")[: profile.max_output_chars]
        if not blocks:
            blocks = [{"type": "text", "content": content, "sourceIds": []}]
        else:
            content = "\n\n".join(str(block["content"]) for block in blocks)
        if on_delta is not None and content:
            on_delta(content)
        claims = {
            "version": 1,
            "accountScopes": [],
            "dataClaims": {
                "ragPermissionGroups": permission_groups,
                "mailboxes": sorted({*mailboxes, *actual_mailboxes}),
            },
        }
        access_requirements = access_requirements_for_scopes(profile.account_scopes)
        if rag_search_performed:
            access_requirements = merge_access_requirements(
                access_requirements,
                claims,
            )
        return AssistantRuntimeResult(
            content=content,
            blocks=blocks,
            sources=sources,
            tool_keys=["rag.search"] if rag_search_performed else [],
            access_requirements=access_requirements,
            execution_metadata={
                "knowledgeRequested": knowledge_requested,
                "ragSearchPerformed": rag_search_performed,
                "contextCount": len(result.contexts),
                "sourceCount": len(sources),
                "outputChars": len(content),
            },
        )

    def _execute_observer(
        self,
        *,
        profile: AssistantProfile,
        prompt: str,
        conversation_summary: str,
        history: Sequence[Mapping[str, str]],
        tool_inputs: Mapping[str, object],
        user_header_id: str | None,
        cancellation: ExternalCallCancellation,
        on_delta: Callable[[str], None] | None,
    ) -> AssistantRuntimeResult:
        """제한된 조회 조건으로 Observer 현재 데이터를 재조회하고 분석합니다."""

        if not self._should_use_app_knowledge(
            profile=profile,
            app_key="observer",
            prompt=prompt,
            history=history,
            conversation_summary=conversation_summary,
            user_header_id=user_header_id,
            cancellation=cancellation,
        ):
            return self._execute_app_general_reply(
                profile=profile,
                app_key="observer",
                prompt=prompt,
                history=history,
                conversation_summary=conversation_summary,
                cancellation=cancellation,
                on_delta=on_delta,
            )

        raw_input = tool_inputs.get("observer.analysis")
        observer_input = raw_input if isinstance(raw_input, Mapping) else {}
        start_at = normalize_observer_datetime(observer_input.get("from"))
        end_at = normalize_observer_datetime(observer_input.get("to"), is_end=True)
        if not isinstance(start_at, datetime) or not isinstance(end_at, datetime):
            raise ValueError("Observer 분석 날짜 범위가 올바르지 않습니다.")
        if start_at > end_at:
            raise ValueError("Observer 분석 시작일은 종료일보다 늦을 수 없습니다.")
        if (end_at - start_at).days >= MAX_OBSERVER_QUERY_DAYS:
            raise ValueError(
                f"Observer 분석 조회 기간은 최대 {MAX_OBSERVER_QUERY_DAYS}일입니다."
            )
        log_types = list(observer_input.get("logTypes") or [])
        if not log_types or any(
            item not in OBSERVER_LOG_KEYS
            for item in log_types
        ):
            raise ValueError("Observer 분석 log type이 올바르지 않습니다.")
        analysis_kwargs = {
            "eqp_id": str(observer_input.get("eqpId") or "").strip(),
            "start_at": start_at,
            "end_at": end_at,
            "log_types": log_types,
            "selected_tip_groups": list(
                observer_input.get("tipGroups") or ["__ALL__"]
            ),
            "question": prompt,
            "conversation_summary": format_assistant_runtime_context(
                history=[dict(item) for item in history],
                summary=conversation_summary,
            ),
        }
        payload = analyze_observer_logs_stream(
            cancellation=cancellation,
            **analysis_kwargs,
        )
        analysis = payload.get("analysis") if isinstance(payload, Mapping) else {}
        analysis = analysis if isinstance(analysis, Mapping) else {}
        parts = [
            (
                f"### {str(analysis.get('headline') or '').strip()}"
                if str(analysis.get("headline") or "").strip()
                else ""
            ),
            str(analysis.get("summary") or "").strip(),
        ]
        findings = analysis.get("findings")
        if isinstance(findings, list) and findings:
            parts.append("#### 주요 분석")
            for finding in findings[:5]:
                if not isinstance(finding, Mapping):
                    continue
                label = " · ".join(
                    value
                    for value in (
                        str(finding.get("category") or "").strip(),
                        str(finding.get("target") or "").strip(),
                    )
                    if value
                )
                assessment = str(finding.get("assessment") or "").strip()
                if assessment:
                    parts.append(f"- **{label}**: {assessment}" if label else f"- {assessment}")
        limitations = analysis.get("limitations")
        if isinstance(limitations, list) and limitations:
            parts.append(
                f"> 분석 한계: {' '.join(str(item) for item in limitations[:3])}"
            )
        content = "\n\n".join(part for part in parts if part)[: profile.max_output_chars]
        if on_delta is not None and content:
            on_delta(content)
        evidence = []
        for finding in findings if isinstance(findings, list) else []:
            if not isinstance(finding, Mapping):
                continue
            evidence.append(
                {
                    "category": str(finding.get("category") or "")[:30],
                    "target": str(finding.get("target") or "")[:200],
                    "evidenceIds": list(finding.get("evidenceIds") or [])[:50],
                }
            )
        return AssistantRuntimeResult(
            content=content,
            blocks=[{"type": "text", "content": content, "sourceIds": []}],
            tool_keys=["observer.analysis"],
            access_requirements=access_requirements_for_scopes(profile.account_scopes),
            execution_metadata={
                "knowledgeRequested": True,
                "outputChars": len(content),
                "evidenceCount": int(payload.get("meta", {}).get("sourceCount") or 0),
            },
            context_snapshot={
                "kind": "observer",
                "scope": dict(payload.get("scope") or {}),
                "coverage": dict(payload.get("meta") or {}),
                "evidence": evidence,
            },
        )


assistant_runtime = AssistantRuntime()


__all__ = [
    "AssistantRuntime",
    "AssistantRuntimeResult",
    "TOOL_AUTHORIZATION_FLOORS",
    "assistant_runtime",
]
