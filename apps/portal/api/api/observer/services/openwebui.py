# =============================================================================
# 모듈 설명: Observer 분석용 OpenWebUI Chat Completions 호출을 담당합니다.
# - 주요 클래스: ObserverOpenWebUIConfig, ObserverOpenWebUIError
# - 주요 함수: stream_observer_analysis
# - 불변 조건: 기존 OPENWEBUI_* 설정을 그대로 사용하고 비밀값은 로그에 남기지 않습니다.
# =============================================================================

"""Observer 분석용 OpenWebUI transport입니다."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any, Iterator

from django.conf import settings
import requests

from api.common.services import (
    ExternalCallCancellation,
    OpenAIStreamError,
    stream_openai_chat_completion,
)

class ObserverOpenWebUIError(RuntimeError):
    """Observer OpenWebUI 분석 요청 또는 응답 오류입니다."""


@dataclass(frozen=True)
class ObserverOpenWebUIConfig:
    """Observer 분석에서 재사용할 기존 OpenWebUI 설정입니다."""

    url: str
    model: str
    api_token: str = ""
    common_headers: dict[str, str] = field(default_factory=dict)
    timeout_seconds: int = 120

    @classmethod
    def from_settings(cls) -> "ObserverOpenWebUIConfig":
        """Django settings의 기존 `OPENWEBUI_*` 값을 읽습니다."""

        raw_headers = getattr(settings, "OPENWEBUI_COMMON_HEADERS", "{}") or "{}"
        try:
            parsed_headers = json.loads(raw_headers)
        except (TypeError, json.JSONDecodeError):
            parsed_headers = {}
        if not isinstance(parsed_headers, dict):
            parsed_headers = {}
        common_headers = {
            str(key): str(value)
            for key, value in parsed_headers.items()
            if isinstance(key, str)
            and isinstance(value, (str, int, float, bool))
        }
        return cls(
            url=str(getattr(settings, "OPENWEBUI_URL", "") or "").strip(),
            model=str(getattr(settings, "OPENWEBUI_MODEL", "") or "").strip(),
            api_token=str(
                getattr(settings, "OPENWEBUI_API_TOKEN", "") or ""
            ).strip(),
            common_headers=common_headers,
            timeout_seconds=max(
                1,
                int(getattr(settings, "OPENWEBUI_TIMEOUT_SECONDS", 120) or 120),
            ),
        )


def _build_headers(config: ObserverOpenWebUIConfig) -> dict[str, str]:
    """OpenWebUI 요청 header를 기존 요약 배치와 동일한 규칙으로 구성합니다."""

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        **config.common_headers,
    }
    if config.api_token:
        token = config.api_token
        headers["Authorization"] = (
            token if token.lower().startswith("bearer ") else f"Bearer {token}"
        )
    return headers


def stream_observer_analysis(
    *,
    messages: list[dict[str, str]],
    cancellation: ExternalCallCancellation,
    config: ObserverOpenWebUIConfig | None = None,
    session: requests.Session | None = None,
) -> Iterator[str]:
    """Observer 구조화 응답을 취소 가능한 OpenAI 호환 stream으로 읽습니다."""

    active_config = config or ObserverOpenWebUIConfig.from_settings()
    if not active_config.url:
        raise ObserverOpenWebUIError("OPENWEBUI_URL 설정이 비어 있습니다.")
    if not active_config.model:
        raise ObserverOpenWebUIError("OPENWEBUI_MODEL 설정이 비어 있습니다.")
    payload: dict[str, Any] = {
        "model": active_config.model,
        "messages": messages,
        "temperature": 1.0,
        "top_p": 1.0,
        "reasoning_effort": "medium",
        "tool_choice": "none",
    }
    try:
        yield from stream_openai_chat_completion(
            url=active_config.url,
            headers=_build_headers(active_config),
            payload=payload,
            timeout_seconds=active_config.timeout_seconds,
            cancellation=cancellation,
            session=session,
        )
    except OpenAIStreamError as exc:
        raise ObserverOpenWebUIError("OpenWebUI 요청에 실패했습니다.") from exc


__all__ = [
    "ObserverOpenWebUIConfig",
    "ObserverOpenWebUIError",
    "stream_observer_analysis",
]
