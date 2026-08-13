# =============================================================================
# 모듈: Assistant Turn prompt provenance 검증
# 주요 함수: resolve_assistant_turn_context_key
# 핵심 전제: context key는 prompt 출처일 뿐 권한 판정에 사용하지 않습니다.
# =============================================================================
"""Profile과 정규화된 Tool 입력으로 저장 가능한 app context를 검증합니다."""

from __future__ import annotations

import hashlib
import json
from typing import Mapping

from ..models import ASSISTANT_APP_LABELS, ASSISTANT_OPENWEBUI_CONTEXT_PREFIX
from .profiles import AssistantProfile


def _normalize_string_list(value: object) -> list[str]:
    """문자열 배열을 공백 제거·중복 제거·정렬한 목록으로 반환합니다."""

    if not isinstance(value, list):
        return []
    return sorted(
        {
            str(item).strip()
            for item in value
            if isinstance(item, str) and str(item).strip()
        }
    )


def _build_observer_context_key(tool_inputs: Mapping[str, object]) -> str:
    """프론트와 동일한 정규화 scope signature로 Observer context key를 만듭니다."""

    raw_input = tool_inputs.get("observer.analysis")
    observer_input = raw_input if isinstance(raw_input, Mapping) else {}
    signature = {
        "eqpId": str(observer_input.get("eqpId") or "").strip().upper(),
        "from": str(observer_input.get("from") or "").strip()[:10],
        "to": str(observer_input.get("to") or "").strip()[:10],
        "logTypes": _normalize_string_list(observer_input.get("logTypes")),
        "tipGroups": _normalize_string_list(observer_input.get("tipGroups")),
    }
    encoded = json.dumps(
        signature,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"observer:v1:{hashlib.sha256(encoded).hexdigest()}"


def resolve_assistant_turn_context_key(
    *,
    profile: AssistantProfile,
    raw_context_key: object,
    tool_inputs: Mapping[str, object],
) -> str:
    """Profile별 허용 규칙으로 app context를 검증하고 canonical key를 반환합니다."""

    context_key = str(raw_context_key or "").strip()
    if profile.provider == "openwebui":
        if not context_key.startswith(ASSISTANT_OPENWEBUI_CONTEXT_PREFIX):
            raise ValueError("Portal appContextKey가 올바르지 않습니다.")
        app_key = context_key[len(ASSISTANT_OPENWEBUI_CONTEXT_PREFIX) :]
        if app_key not in ASSISTANT_APP_LABELS:
            raise ValueError("지원하지 않는 Portal appContextKey입니다.")
        return f"{ASSISTANT_OPENWEBUI_CONTEXT_PREFIX}{app_key}"
    if profile.provider == "email-rag":
        if context_key != "assistant":
            raise ValueError("Email appContextKey가 올바르지 않습니다.")
        return "assistant"
    if profile.provider == "observer-analysis":
        expected = _build_observer_context_key(tool_inputs)
        if context_key != expected:
            raise ValueError("Observer appContextKey가 현재 조회 조건과 일치하지 않습니다.")
        return expected
    if profile.provider == "appstore-context":
        if context_key != "appstore:v1" or "appstore.catalog" not in tool_inputs:
            raise ValueError("Appstore appContextKey가 현재 조회 조건과 일치하지 않습니다.")
        return context_key
    if profile.provider == "line-dashboard-context":
        if context_key != "line-dashboard:v1" or "line-dashboard.snapshot" not in tool_inputs:
            raise ValueError("ESOP Dashboard appContextKey가 현재 조회 조건과 일치하지 않습니다.")
        return context_key
    raise ValueError("지원하지 않는 Assistant Profile입니다.")


__all__ = ["resolve_assistant_turn_context_key"]
