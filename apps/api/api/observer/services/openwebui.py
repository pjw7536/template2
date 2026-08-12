# =============================================================================
# 모듈 설명: Observer 분석용 OpenWebUI Chat Completions 호출을 담당합니다.
# - 주요 클래스: ObserverOpenWebUIConfig, ObserverOpenWebUIError
# - 주요 함수: request_observer_analysis, stream_observer_analysis
# - 불변 조건: 기존 OPENWEBUI_* 설정을 그대로 사용하고 비밀값은 로그에 남기지 않습니다.
# =============================================================================

"""Observer 분석용 OpenWebUI transport입니다."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
from collections.abc import Iterator
from typing import Any

from django.conf import settings
import requests

logger = logging.getLogger(__name__)


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


def _extract_content(payload: object) -> str:
    """OpenAI 호환 Chat Completions 응답에서 최종 텍스트를 추출합니다."""

    if not isinstance(payload, dict):
        raise ObserverOpenWebUIError("OpenWebUI 응답이 JSON 객체가 아닙니다.")
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ObserverOpenWebUIError("OpenWebUI 응답 choices가 비어 있습니다.")
    choice = choices[0]
    message = choice.get("message") if isinstance(choice, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise ObserverOpenWebUIError("OpenWebUI 응답 content가 비어 있습니다.")
    return content.strip()


def _extract_stream_delta(payload: object) -> str:
    """OpenAI 호환 stream chunk에서 content 조각을 추출합니다."""

    if not isinstance(payload, dict):
        return ""
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    choice = choices[0]
    delta = choice.get("delta") if isinstance(choice, dict) else None
    content = delta.get("content") if isinstance(delta, dict) else None
    return content if isinstance(content, str) else ""


def request_observer_analysis(
    *,
    messages: list[dict[str, str]],
    config: ObserverOpenWebUIConfig | None = None,
    session: requests.Session | None = None,
) -> str:
    """기존 OpenWebUI endpoint에 Observer 분석 요청을 한 번 전송합니다.

    입력:
    - messages: Chat Completions system/user message 목록
    - config: 테스트 또는 별도 실행에서 주입할 설정
    - session: 테스트에서 주입할 requests session

    반환:
    - str: OpenWebUI의 최종 message content

    부작용:
    - OpenWebUI HTTP API를 호출합니다.

    오류:
    - 설정 누락, HTTP 실패, 비정상 응답이면 ObserverOpenWebUIError를 발생시킵니다.
    """

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
        "stream": False,
        "tool_choice": "none",
    }
    active_session = session or requests.Session()
    try:
        response = active_session.post(
            active_config.url,
            headers=_build_headers(active_config),
            json=payload,
            timeout=active_config.timeout_seconds,
            stream=False,
        )
        response.raise_for_status()
        return _extract_content(response.json())
    except requests.HTTPError as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        logger.warning("Observer OpenWebUI HTTP 오류: status=%s", status_code)
        raise ObserverOpenWebUIError(
            f"OpenWebUI HTTP 오류가 발생했습니다. status={status_code or 'unknown'}"
        ) from exc
    except (requests.RequestException, ValueError) as exc:
        logger.warning(
            "Observer OpenWebUI 요청 실패: exception_type=%s",
            type(exc).__name__,
        )
        raise ObserverOpenWebUIError("OpenWebUI 요청에 실패했습니다.") from exc
    finally:
        if session is None:
            active_session.close()


def stream_observer_analysis(
    *,
    messages: list[dict[str, str]],
    config: ObserverOpenWebUIConfig | None = None,
    session: requests.Session | None = None,
) -> Iterator[str]:
    """OpenWebUI SSE 응답을 Observer 분석 content 조각으로 변환합니다.

    입력:
    - messages: Observer 분석용 system/user message 목록
    - config: 테스트 또는 별도 실행에서 주입할 설정
    - session: 테스트에서 주입할 requests session

    반환:
    - Iterator[str]: 모델이 생성한 content 조각

    부작용:
    - OpenWebUI streaming HTTP 연결을 열고 종료 시 response와 내부 session을 닫습니다.

    오류:
    - 설정 누락, HTTP 실패, 비정상 stream이면 ObserverOpenWebUIError를 발생시킵니다.
    """

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
        "stream": True,
        "tool_choice": "none",
    }
    active_session = session or requests.Session()
    response = None
    saw_done = False
    try:
        response = active_session.post(
            active_config.url,
            headers={**_build_headers(active_config), "Accept": "text/event-stream"},
            json=payload,
            timeout=active_config.timeout_seconds,
            stream=True,
        )
        response.raise_for_status()
        for raw_line in response.iter_lines(chunk_size=1, decode_unicode=True):
            if not raw_line:
                continue
            line = (
                raw_line.decode("utf-8")
                if isinstance(raw_line, bytes)
                else raw_line
            )
            if not isinstance(line, str) or not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                saw_done = True
                break
            if not data:
                continue
            try:
                chunk = json.loads(data)
            except json.JSONDecodeError as exc:
                raise ObserverOpenWebUIError(
                    "OpenWebUI stream chunk 형식이 올바르지 않습니다."
                ) from exc
            delta = _extract_stream_delta(chunk)
            if delta:
                yield delta
        if not saw_done:
            raise ObserverOpenWebUIError(
                "OpenWebUI stream이 완료 신호 없이 종료되었습니다."
            )
    except requests.HTTPError as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        logger.warning("Observer OpenWebUI stream HTTP 오류: status=%s", status_code)
        raise ObserverOpenWebUIError(
            f"OpenWebUI HTTP 오류가 발생했습니다. status={status_code or 'unknown'}"
        ) from exc
    except requests.RequestException as exc:
        logger.warning(
            "Observer OpenWebUI stream 요청 실패: exception_type=%s",
            type(exc).__name__,
        )
        raise ObserverOpenWebUIError("OpenWebUI stream 요청에 실패했습니다.") from exc
    finally:
        if response is not None:
            response.close()
        if session is None:
            active_session.close()


__all__ = [
    "ObserverOpenWebUIConfig",
    "ObserverOpenWebUIError",
    "request_observer_analysis",
    "stream_observer_analysis",
]
