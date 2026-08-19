# =============================================================================
# 모듈: OpenAI 호환 Chat Completions streaming transport
# 주요 함수: stream_openai_chat_completion
# 핵심 전제: 외부 오류 상세와 response 본문은 호출자에게 노출하지 않습니다.
# =============================================================================
"""OpenAI 호환 SSE chunk에서 검증된 assistant content만 순서대로 반환합니다."""

from __future__ import annotations

import json
import logging
from typing import Any, Iterator, Mapping

import requests

from .cancellation import ExternalCallCancellation, ExternalCallCancelled
from .external_http import (
    ExternalHttpError,
    ExternalHttpResponseError,
    ExternalHttpTimeout,
    request_external,
)

logger = logging.getLogger(__name__)


class OpenAIStreamError(RuntimeError):
    """OpenAI 호환 streaming transport가 안전하게 정규화한 오류입니다."""


def _parse_stream_content(raw_line: object) -> tuple[str, bool]:
    """SSE data 한 줄에서 content delta와 완료 여부를 반환합니다."""

    if isinstance(raw_line, bytes):
        line = raw_line.decode("utf-8", errors="replace").strip()
    else:
        line = str(raw_line or "").strip()
    if not line or line.startswith(":"):
        return "", False
    if not line.startswith("data:"):
        return "", False
    data = line[5:].strip()
    if data == "[DONE]":
        return "", True
    try:
        payload = json.loads(data)
    except (TypeError, json.JSONDecodeError) as exc:
        raise OpenAIStreamError("LLM streaming 응답 형식이 올바르지 않습니다.") from exc
    if not isinstance(payload, Mapping):
        raise OpenAIStreamError("LLM streaming 응답 형식이 올바르지 않습니다.")
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return "", False
    choice = choices[0]
    delta = choice.get("delta") if isinstance(choice, Mapping) else None
    content = delta.get("content") if isinstance(delta, Mapping) else None
    return (content if isinstance(content, str) else ""), False


def stream_openai_chat_completion(
    *,
    url: str,
    headers: Mapping[str, str],
    payload: Mapping[str, Any],
    timeout_seconds: int,
    cancellation: ExternalCallCancellation,
    session: requests.Session | None = None,
) -> Iterator[str]:
    """취소 가능한 OpenAI 호환 요청을 열고 content delta만 반환합니다."""

    active_session = session or requests.Session()
    unregister_session = cancellation.register_closer(active_session.close)
    response: requests.Response | None = None
    unregister_response = lambda: None
    try:
        cancellation.raise_if_cancelled()
        stream_payload = dict(payload)
        stream_payload["stream"] = True
        response = request_external(
            active_session.post,
            url,
            headers=dict(headers),
            json=stream_payload,
            timeout=max(1, int(timeout_seconds)),
            stream=True,
            cancellation=cancellation,
            raise_for_status=True,
        )
        unregister_response = cancellation.register_closer(response.close)
        completed = False
        for raw_line in response.iter_lines(decode_unicode=True):
            cancellation.raise_if_cancelled()
            content, is_done = _parse_stream_content(raw_line)
            if content:
                yield content
            if is_done:
                completed = True
                break
        cancellation.raise_if_cancelled()
        if not completed:
            raise OpenAIStreamError("LLM streaming 응답이 완료되지 않았습니다.")
    except ExternalCallCancelled:
        raise
    except ExternalHttpResponseError as exc:
        logger.warning("OpenAI 호환 streaming HTTP 오류: status=%s", exc.status_code)
        raise OpenAIStreamError("LLM 요청에 실패했습니다.") from exc
    except (ExternalHttpTimeout, ExternalHttpError) as exc:
        logger.warning(
            "OpenAI 호환 streaming 요청 실패: exception_type=%s",
            type(exc).__name__,
        )
        raise OpenAIStreamError("LLM 요청에 실패했습니다.") from exc
    finally:
        unregister_response()
        if response is not None:
            response.close()
        unregister_session()
        if session is None:
            active_session.close()


__all__ = ["OpenAIStreamError", "stream_openai_chat_completion"]
