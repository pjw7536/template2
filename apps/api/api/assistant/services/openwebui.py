# =============================================================================
# 모듈: Assistant 일반 대화와 대화방 제목용 OpenWebUI 호출
# 주요 클래스: AssistantOpenWebUIConfig
# 주요 함수: request_openwebui_chat, request_openwebui_conversation_title
# 주요 가정: OpenWebUI는 OpenAI 호환 Chat Completions 응답을 반환합니다.
# =============================================================================
"""Assistant 일반 대화와 대화방 제목 생성을 OpenWebUI로 전달합니다."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
import re
import unicodedata
from collections.abc import Iterator
from typing import Any, Mapping, Sequence

from django.conf import settings
import requests

from .errors import AssistantConfigError, AssistantRequestError

logger = logging.getLogger(__name__)

OPENWEBUI_SYSTEM_MESSAGE = (
    "당신은 Etch 기술팀의 AI Assistant입니다. 항상 한국어로 명확하고 간결하게 "
    "답변하되 코드, 명령어, 제품명과 고유명사는 원문을 유지하세요. 확인할 수 없는 "
    "사실은 추측하지 말고 필요한 정보를 사용자에게 요청하세요."
)
OPENWEBUI_TITLE_SYSTEM_MESSAGE = (
    "당신은 업무용 AI 채팅의 대화방 제목을 작성합니다. 대화의 핵심 업무 주제만 "
    "한국어 명사형 2~7어절로 요약하세요. 장비명, 상태명, 기술 용어와 고유명사는 "
    "원문을 유지하세요. 최대 40자로 작성하고 따옴표, Markdown, 이모지, 마침표, "
    "설명, '제목:' 접두어 없이 제목 한 줄만 출력하세요."
)
OPENWEBUI_SUMMARY_SYSTEM_MESSAGE = (
    "당신은 장기 대화 기억을 갱신합니다. 기존 요약과 새 대화를 결합해 이후 질문에 "
    "필요한 사실, 결정, 장비명, 상태명, 원인, 미해결 항목만 한국어로 간결하게 "
    "정리하세요. 추측을 추가하지 말고 최대 2000자로 작성하세요."
)
OPENWEBUI_TITLE_MAX_LENGTH = 40
OPENWEBUI_SUMMARY_MAX_LENGTH = 2000


@dataclass(frozen=True)
class AssistantOpenWebUIConfig:
    """기존 `OPENWEBUI_*` 설정을 일반 Assistant 대화에 제공합니다."""

    url: str
    model: str
    api_token: str = ""
    common_headers: dict[str, str] = field(default_factory=dict)
    timeout_seconds: int = 120

    @classmethod
    def from_settings(cls) -> "AssistantOpenWebUIConfig":
        """Django settings에서 OpenWebUI 연결 설정을 읽습니다."""

        raw_headers = getattr(settings, "OPENWEBUI_COMMON_HEADERS", "{}") or "{}"
        try:
            parsed_headers = json.loads(raw_headers)
        except (TypeError, json.JSONDecodeError):
            parsed_headers = {}
        if not isinstance(parsed_headers, dict):
            parsed_headers = {}

        return cls(
            url=str(getattr(settings, "OPENWEBUI_URL", "") or "").strip(),
            model=str(getattr(settings, "OPENWEBUI_MODEL", "") or "").strip(),
            api_token=str(
                getattr(settings, "OPENWEBUI_API_TOKEN", "") or ""
            ).strip(),
            common_headers={
                str(key): str(value)
                for key, value in parsed_headers.items()
                if isinstance(key, str)
                and isinstance(value, (str, int, float, bool))
            },
            timeout_seconds=max(
                1,
                int(getattr(settings, "OPENWEBUI_TIMEOUT_SECONDS", 120) or 120),
            ),
        )


def _build_headers(config: AssistantOpenWebUIConfig) -> dict[str, str]:
    """OpenWebUI 요청 header를 구성하고 token은 Bearer 형식으로 정규화합니다."""

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        **config.common_headers,
    }
    if config.api_token:
        headers["Authorization"] = (
            config.api_token
            if config.api_token.lower().startswith("bearer ")
            else f"Bearer {config.api_token}"
        )
    return headers


def _build_stream_headers(config: AssistantOpenWebUIConfig) -> dict[str, str]:
    """OpenWebUI SSE 응답을 요청하는 header를 구성합니다."""

    return {**_build_headers(config), "Accept": "text/event-stream"}


def build_openwebui_messages(
    history: Sequence[Mapping[str, object]],
    *,
    system_message: str = OPENWEBUI_SYSTEM_MESSAGE,
    conversation_summary: str = "",
) -> list[dict[str, str]]:
    """사용자/Assistant 대화만 허용하고 고정 system message를 앞에 추가합니다."""

    normalized_summary = (
        conversation_summary.strip()
        if isinstance(conversation_summary, str)
        else ""
    )
    summary_suffix = (
        "\n\n이전 대화 요약:\n"
        f"{normalized_summary}\n"
        "요약 이후의 최근 대화와 함께 참고하되, 최신 사용자 요청을 우선하세요."
        if normalized_summary
        else ""
    )
    messages = [{"role": "system", "content": f"{system_message}{summary_suffix}"}]
    for entry in history:
        role = entry.get("role")
        content = entry.get("content")
        if role not in {"user", "assistant"}:
            continue
        if not isinstance(content, str) or not content.strip():
            continue
        messages.append({"role": str(role), "content": content.strip()})
    return messages


def _extract_stream_delta(payload: object) -> str:
    """OpenAI 호환 stream chunk에서 사용자에게 표시할 content만 추출합니다."""

    if not isinstance(payload, dict):
        return ""
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    choice = choices[0]
    if not isinstance(choice, dict):
        return ""
    delta = choice.get("delta")
    if not isinstance(delta, dict):
        return ""
    content = delta.get("content")
    return content if isinstance(content, str) else ""


def stream_openwebui_chat(
    *,
    history: Sequence[Mapping[str, object]],
    conversation_summary: str = "",
    config: AssistantOpenWebUIConfig | None = None,
    session: requests.Session | None = None,
    system_message: str = OPENWEBUI_SYSTEM_MESSAGE,
    temperature: float = 1.0,
    top_p: float = 1.0,
    reasoning_effort: str = "medium",
) -> Iterator[str]:
    """OpenWebUI Chat Completions SSE를 답변 content 조각 iterator로 변환합니다.

    입력:
        history: 최근 사용자/Assistant 대화입니다.
        conversation_summary: 최근 이력 이전의 장기 대화 요약입니다.

    반환:
        화면에 즉시 이어 붙일 content 문자열 iterator입니다.

    부작용:
        OpenWebUI streaming HTTP 연결을 열고 iterator 종료 시 즉시 닫습니다.

    오류:
        설정 누락 또는 upstream HTTP/stream 형식 오류 시 Assistant 계층 예외를 발생시킵니다.
    """

    active_config = config or AssistantOpenWebUIConfig.from_settings()
    if not active_config.url:
        raise AssistantConfigError("OPENWEBUI_URL 설정이 비어 있습니다.")
    if not active_config.model:
        raise AssistantConfigError("OPENWEBUI_MODEL 설정이 비어 있습니다.")

    payload: dict[str, Any] = {
        "model": active_config.model,
        "messages": build_openwebui_messages(
            history,
            system_message=system_message,
            conversation_summary=conversation_summary,
        ),
        "temperature": temperature,
        "top_p": top_p,
        "reasoning_effort": reasoning_effort,
        "stream": True,
        "tool_choice": "none",
    }
    active_session = session or requests.Session()
    response = None
    saw_done = False
    try:
        response = active_session.post(
            active_config.url,
            headers=_build_stream_headers(active_config),
            json=payload,
            timeout=active_config.timeout_seconds,
            stream=True,
        )
        response.raise_for_status()
        for raw_line in response.iter_lines(chunk_size=1, decode_unicode=True):
            if not raw_line:
                continue
            line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
            if not isinstance(line, str) or not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if not data or data == "[DONE]":
                if data == "[DONE]":
                    saw_done = True
                    break
                continue
            try:
                chunk = json.loads(data)
            except json.JSONDecodeError as exc:
                raise AssistantRequestError("OpenWebUI stream chunk 형식이 올바르지 않습니다.") from exc
            delta = _extract_stream_delta(chunk)
            if delta:
                yield delta
        if not saw_done:
            raise AssistantRequestError(
                "OpenWebUI stream이 완료 신호 없이 종료되었습니다."
            )
    except requests.HTTPError as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        logger.warning("Assistant OpenWebUI stream HTTP 오류: status=%s", status_code)
        raise AssistantRequestError(
            f"OpenWebUI HTTP 오류가 발생했습니다. status={status_code or 'unknown'}"
        ) from exc
    except requests.RequestException as exc:
        logger.warning(
            "Assistant OpenWebUI stream 요청 실패: exception_type=%s",
            type(exc).__name__,
        )
        raise AssistantRequestError("OpenWebUI stream 요청에 실패했습니다.") from exc
    finally:
        if response is not None:
            response.close()
        if session is None:
            active_session.close()


def _extract_content(payload: object) -> str:
    """OpenAI 호환 응답에서 첫 번째 최종 답변을 추출합니다."""

    if not isinstance(payload, dict):
        raise AssistantRequestError("OpenWebUI 응답이 JSON 객체가 아닙니다.")
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise AssistantRequestError("OpenWebUI 응답 choices가 비어 있습니다.")
    choice = choices[0]
    message = choice.get("message") if isinstance(choice, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise AssistantRequestError("OpenWebUI 응답 content가 비어 있습니다.")
    return content.strip()


def request_openwebui_chat(
    *,
    history: Sequence[Mapping[str, object]],
    conversation_summary: str = "",
    config: AssistantOpenWebUIConfig | None = None,
    session: requests.Session | None = None,
    system_message: str = OPENWEBUI_SYSTEM_MESSAGE,
    temperature: float = 1.0,
    top_p: float = 1.0,
    reasoning_effort: str = "medium",
) -> str:
    """대화 이력을 기존 OpenWebUI endpoint로 전송하고 최종 답변을 반환합니다.

    부작용:
        OpenWebUI HTTP API를 호출합니다.

    오류:
        설정 누락 시 AssistantConfigError, 요청/응답 실패 시 AssistantRequestError를 발생시킵니다.
    """

    active_config = config or AssistantOpenWebUIConfig.from_settings()
    if not active_config.url:
        raise AssistantConfigError("OPENWEBUI_URL 설정이 비어 있습니다.")
    if not active_config.model:
        raise AssistantConfigError("OPENWEBUI_MODEL 설정이 비어 있습니다.")

    payload: dict[str, Any] = {
        "model": active_config.model,
        "messages": build_openwebui_messages(
            history,
            system_message=system_message,
            conversation_summary=conversation_summary,
        ),
        "temperature": temperature,
        "top_p": top_p,
        "reasoning_effort": reasoning_effort,
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
        logger.warning("Assistant OpenWebUI HTTP 오류: status=%s", status_code)
        raise AssistantRequestError(
            f"OpenWebUI HTTP 오류가 발생했습니다. status={status_code or 'unknown'}"
        ) from exc
    except (requests.RequestException, ValueError) as exc:
        logger.warning(
            "Assistant OpenWebUI 요청 실패: exception_type=%s",
            type(exc).__name__,
        )
        raise AssistantRequestError("OpenWebUI 요청에 실패했습니다.") from exc
    finally:
        if session is None:
            active_session.close()


def normalize_openwebui_conversation_title(raw_title: object) -> str:
    """OpenWebUI 제목 응답에서 설명과 장식을 제거하고 최대 40자로 제한합니다."""

    if not isinstance(raw_title, str):
        return ""
    cleaned = re.sub(r"<think>.*?</think>", " ", raw_title, flags=re.DOTALL | re.IGNORECASE)
    cleaned = cleaned.strip()
    if cleaned.startswith("{"):
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict) and isinstance(parsed.get("title"), str):
            cleaned = parsed["title"].strip()

    first_line = next((line.strip() for line in cleaned.splitlines() if line.strip()), "")
    first_line = first_line.strip("`#*_- \t\"'“”‘’")
    first_line = re.sub(r"^(?:제목|title)\s*[:：]\s*", "", first_line, flags=re.IGNORECASE)
    first_line = first_line.strip("`#*_- \t\"'“”‘’")
    first_line = "".join(
        character
        for character in first_line
        if unicodedata.category(character) not in {"So", "Sk"}
        and character not in {"\u200d", "\ufe0f"}
    )
    first_line = first_line.strip()
    first_line = re.sub(r"[.!?。！？]+$", "", first_line).strip()
    first_line = re.sub(r"\s+", " ", first_line)
    return first_line[:OPENWEBUI_TITLE_MAX_LENGTH].rstrip()


def request_openwebui_conversation_title(
    *,
    history: Sequence[Mapping[str, object]],
    config: AssistantOpenWebUIConfig | None = None,
    session: requests.Session | None = None,
) -> str:
    """저장된 대화 일부를 OpenWebUI에 전달해 업무용 대화방 제목을 생성합니다.

    입력:
        history: 사용자와 Assistant 메시지 목록입니다.

    반환:
        장식이 제거된 최대 40자의 제목입니다.

    부작용:
        기존 OpenWebUI HTTP API를 한 번 호출합니다.

    오류:
        제목이 비어 있으면 AssistantRequestError를 발생시킵니다.
    """

    transcript_entries: list[str] = []
    for entry in history[-6:]:
        role = entry.get("role")
        content = entry.get("content")
        if role not in {"user", "assistant"}:
            continue
        if not isinstance(content, str) or not content.strip():
            continue
        role_label = "사용자" if role == "user" else "Assistant"
        transcript_entries.append(f"{role_label}: {content.strip()[:600]}")

    raw_title = request_openwebui_chat(
        history=[
            {
                "role": "user",
                "content": "다음 대화의 업무용 제목을 작성하세요.\n\n"
                + "\n".join(transcript_entries),
            }
        ],
        config=config,
        session=session,
        system_message=OPENWEBUI_TITLE_SYSTEM_MESSAGE,
        temperature=0.2,
        top_p=0.9,
        reasoning_effort="low",
    )
    title = normalize_openwebui_conversation_title(raw_title)
    if not title:
        raise AssistantRequestError("OpenWebUI 대화방 제목이 비어 있습니다.")
    return title


def request_openwebui_conversation_summary(
    *,
    messages: Sequence[Mapping[str, object]],
    existing_summary: str = "",
    config: AssistantOpenWebUIConfig | None = None,
    session: requests.Session | None = None,
) -> str:
    """기존 요약과 새 대화를 합쳐 장기 기억용 요약을 생성합니다."""

    transcript_entries: list[str] = []
    for entry in messages:
        role = entry.get("role")
        content = entry.get("content")
        if role not in {"user", "assistant"}:
            continue
        if not isinstance(content, str) or not content.strip():
            continue
        role_label = "사용자" if role == "user" else "Assistant"
        transcript_entries.append(f"{role_label}: {content.strip()[:1200]}")

    normalized_existing = (
        existing_summary.strip() if isinstance(existing_summary, str) else ""
    )
    prompt = (
        f"기존 요약:\n{normalized_existing or '(없음)'}\n\n"
        "새로 반영할 대화:\n"
        + "\n".join(transcript_entries)
    )
    raw_summary = request_openwebui_chat(
        history=[{"role": "user", "content": prompt}],
        config=config,
        session=session,
        system_message=OPENWEBUI_SUMMARY_SYSTEM_MESSAGE,
        temperature=0.2,
        top_p=0.9,
        reasoning_effort="low",
    )
    cleaned = re.sub(
        r"<think>.*?</think>",
        " ",
        raw_summary,
        flags=re.DOTALL | re.IGNORECASE,
    ).strip()
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    if not cleaned:
        raise AssistantRequestError("OpenWebUI 대화 요약이 비어 있습니다.")
    return cleaned[:OPENWEBUI_SUMMARY_MAX_LENGTH].rstrip()


__all__ = [
    "AssistantOpenWebUIConfig",
    "build_openwebui_messages",
    "normalize_openwebui_conversation_title",
    "request_openwebui_chat",
    "request_openwebui_conversation_summary",
    "request_openwebui_conversation_title",
    "stream_openwebui_chat",
]
