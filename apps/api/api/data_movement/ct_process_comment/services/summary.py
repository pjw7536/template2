"""ct_process_comment OpenWebUI 요약 배치 서비스입니다."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from api.data_movement.ct_process_comment import selectors
from api.data_movement.ct_process_comment.models import CtProcessComment
from api.data_movement.ct_process_comment.services.summary_constants import (
    CORE_SUMMARY_REWRITE_PREFIX,
    NO_CORE_SUMMARY_SENTINEL,
    OPENWEBUI_DIAGNOSTIC_VERSION,
    OPENWEBUI_SAFE_RESPONSE_HEADERS,
    SUMMARY_LAST_ERROR_MAX_CHARS,
    SUMMARY_MAX_RETRY_COUNT,
    SUMMARY_SECTION_PREFIX_PATTERN,
    SUMMARY_STATUS_DRY_RUN,
    SUMMARY_STATUS_EXHAUSTED,
    SUMMARY_STATUS_FAILED,
    SUMMARY_STATUS_SKIPPED,
    SUMMARY_STATUS_SUCCESS,
    SUMMARY_TIME_LINE_PATTERN,
)
from api.data_movement.ct_process_comment.services.summary_prompts import (
    _build_summary_prompt_from_source,
    _build_timestamped_event_text,
    _normalize_summary_source_text,
    _split_summary_source_chunks,
    build_core_summary_prompt,
    build_core_summary_review_prompt,
    build_summary_prompt,
)
from api.data_movement.ctttm_workorder_list import selectors as ctttm_workorder_selectors

logger = logging.getLogger(__name__)


class OpenWebUIConfigError(RuntimeError):
    """OpenWebUI 설정이 부족할 때 발생합니다."""


class OpenWebUIRequestError(RuntimeError):
    """OpenWebUI 요청 또는 응답 처리에 실패했을 때 발생합니다."""


class _OpenWebUIRowResponseError(OpenWebUIRequestError):
    """동일 row에서 재현될 수 있는 최종 응답 오류입니다."""

    error_code = "row_response_error"


class _OpenWebUIEmptyContentResponseError(_OpenWebUIRowResponseError):
    """OpenWebUI가 저장할 최종 content 없이 종료했을 때 발생합니다."""

    error_code = "empty_content"


class _OpenWebUIReasoningOnlyResponseError(_OpenWebUIEmptyContentResponseError):
    """OpenWebUI가 최종 답변 없이 reasoning만 반환했을 때 발생합니다."""

    error_code = "reasoning_only"


class _OpenWebUIContentFilterResponseError(_OpenWebUIRowResponseError):
    """OpenWebUI가 content filter로 최종 답변을 차단했을 때 발생합니다."""

    error_code = "content_filter"


class _OpenWebUIRefusalResponseError(_OpenWebUIRowResponseError):
    """OpenWebUI 모델이 최종 답변 생성을 거절했을 때 발생합니다."""

    error_code = "refusal"


@dataclass(frozen=True)
class OpenWebUISummaryConfig:
    """OpenWebUI 요약 호출에 필요한 설정 묶음입니다."""

    url: str
    model: str
    api_token: str = ""
    common_headers: dict[str, str] = field(default_factory=dict)
    timeout_seconds: int = 120

    @classmethod
    def from_settings(cls) -> "OpenWebUISummaryConfig":
        """Django settings에서 OpenWebUI 설정을 로드합니다."""

        return cls(
            url=(getattr(settings, "OPENWEBUI_URL", "") or "").strip(),
            model=(getattr(settings, "OPENWEBUI_MODEL", "") or "").strip(),
            api_token=(getattr(settings, "OPENWEBUI_API_TOKEN", "") or "").strip(),
            common_headers=_parse_headers(
                getattr(settings, "OPENWEBUI_COMMON_HEADERS", "{}"),
                "OPENWEBUI_COMMON_HEADERS",
            ),
            timeout_seconds=max(1, int(getattr(settings, "OPENWEBUI_TIMEOUT_SECONDS", 120) or 120)),
        )


@dataclass(frozen=True)
class SummaryRowOutcome:
    """요약 batch에서 row 1건의 처리 결과를 표현합니다."""

    workorder_id: str
    status: str
    summary: str = ""
    error_message: str = ""


@dataclass(frozen=True)
class GeneratedSummary:
    """OpenWebUI가 생성한 핵심 요약과 시간순 요약을 분리해 보관합니다."""

    core_summary: str | None
    event_summary: str


@dataclass(frozen=True)
class SummaryRunSummary:
    """요약 batch 실행 결과 집계입니다."""

    outcomes: list[SummaryRowOutcome] = field(default_factory=list)

    @property
    def processed_count(self) -> int:
        """처리 결과가 기록된 row 수를 반환합니다."""

        return len(self.outcomes)

    @property
    def success_count(self) -> int:
        """요약 저장에 성공한 row 수를 반환합니다."""

        return sum(1 for outcome in self.outcomes if outcome.status == SUMMARY_STATUS_SUCCESS)

    @property
    def failure_count(self) -> int:
        """외부 호출 또는 저장에 실패한 row 수를 반환합니다."""

        return sum(1 for outcome in self.outcomes if outcome.status == SUMMARY_STATUS_FAILED)

    @property
    def all_failed(self) -> bool:
        """처리 대상이 있고 모든 row가 실패했는지 반환합니다."""

        return self.processed_count > 0 and self.failure_count == self.processed_count

    @property
    def skipped_count(self) -> int:
        """요약 요청 없이 건너뛴 row 수를 반환합니다."""

        return sum(1 for outcome in self.outcomes if outcome.status == SUMMARY_STATUS_SKIPPED)

    @property
    def dry_run_count(self) -> int:
        """dry-run으로 확인한 row 수를 반환합니다."""

        return sum(1 for outcome in self.outcomes if outcome.status == SUMMARY_STATUS_DRY_RUN)

    @property
    def exhausted_count(self) -> int:
        """재시도 한도를 소진해 완료한 row 수를 반환합니다."""

        return sum(1 for outcome in self.outcomes if outcome.status == SUMMARY_STATUS_EXHAUSTED)


def _parse_headers(raw: str | None, source: str) -> dict[str, str]:
    """JSON 문자열 기반 header 설정을 문자열 dict로 정규화합니다."""

    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        logger.warning("%s 환경변수를 JSON 객체로 파싱하지 못했습니다.", source)
        return {}
    if not isinstance(parsed, dict):
        logger.warning("%s 값이 JSON 객체 형식이 아닙니다.", source)
        return {}

    headers: dict[str, str] = {}
    for key, value in parsed.items():
        if not isinstance(key, str):
            continue
        if isinstance(value, (str, int, float, bool)):
            headers[key] = str(value)
    return headers


def _build_headers(config: OpenWebUISummaryConfig) -> dict[str, str]:
    """OpenWebUI 요청 header를 구성합니다."""

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        **config.common_headers,
    }
    if config.api_token:
        token = config.api_token
        headers["Authorization"] = token if token.lower().startswith("bearer ") else f"Bearer {token}"
    return headers


def _truncate_log_label(value: Any, *, max_length: int = 80) -> str:
    """응답 메타데이터 이름을 로그에 안전한 제한 길이로 변환합니다."""

    label = str(value).replace("\n", "\\n").replace("\r", "\\r")
    if len(label) <= max_length:
        return label
    return f"{label[:max_length]}..."


def _describe_response_value(value: Any) -> str:
    """응답 본문 값은 노출하지 않고 타입과 크기만 설명합니다."""

    if value is None:
        return "NoneType"
    if isinstance(value, str):
        return f"str(len={len(value)})"
    if isinstance(value, list):
        return f"list(len={len(value)})"
    if isinstance(value, dict):
        keys = sorted(_truncate_log_label(key) for key in value)[:10]
        suffix = ",..." if len(value) > len(keys) else ""
        return f"dict(keys=[{','.join(keys)}{suffix}])"
    return type(value).__name__


def _format_response_metadata(value: Any) -> str:
    """응답 식별 메타데이터만 제한된 길이로 로그 문자열화합니다."""

    if value is None or isinstance(value, (bool, int, float)):
        return repr(value)
    if isinstance(value, str):
        return repr(_truncate_log_label(value, max_length=120))
    return f"<{type(value).__name__}>"


def _redact_endpoint_url(value: Any) -> str:
    """endpoint URL에서 인증정보, query, fragment를 제거합니다."""

    if not isinstance(value, str) or not value.strip():
        return "unavailable"
    try:
        parsed = urlsplit(value.strip())
        hostname = parsed.hostname or ""
        if not hostname:
            return "invalid"
        if ":" in hostname:
            hostname = f"[{hostname}]"
        port = parsed.port
        netloc = f"{hostname}:{port}" if port is not None else hostname
        return urlunsplit((parsed.scheme, netloc, parsed.path or "/", "", ""))
    except ValueError:
        return "invalid"


def _format_request_message_shape(messages: list[dict[str, str]]) -> str:
    """prompt 본문 없이 role과 content 길이만 진단용으로 표현합니다."""

    message_shapes: list[str] = []
    for message in messages:
        role = _truncate_log_label(message.get("role", "unknown"), max_length=24)
        message_shapes.append(f"{role}:{_describe_response_value(message.get('content'))}")
    return f"[{','.join(message_shapes)}]"


def _format_safe_response_headers(response: requests.Response | None) -> str:
    """운영 추적에 필요한 allowlist 응답 header만 진단 문자열로 변환합니다."""

    headers = getattr(response, "headers", None)
    if not hasattr(headers, "get"):
        return "{}"

    header_parts: list[str] = []
    for name in OPENWEBUI_SAFE_RESPONSE_HEADERS:
        value = headers.get(name)
        if value in (None, ""):
            continue
        header_parts.append(f"{name.lower()}:{_format_response_metadata(value)}")
    return f"{{{','.join(header_parts)}}}"


def _format_response_elapsed_ms(response: requests.Response | None) -> str:
    """requests 응답 elapsed를 millisecond 문자열로 변환합니다."""

    elapsed = getattr(response, "elapsed", None)
    total_seconds = getattr(elapsed, "total_seconds", None)
    if not callable(total_seconds):
        return "unavailable"
    try:
        elapsed_seconds = total_seconds()
    except (TypeError, ValueError, OverflowError):
        return "unavailable"
    if not isinstance(elapsed_seconds, (int, float)) or isinstance(elapsed_seconds, bool):
        return "unavailable"
    return str(max(0, round(elapsed_seconds * 1000)))


def _build_attempt_context(
    *,
    response: requests.Response | None,
    config: OpenWebUISummaryConfig,
    messages: list[dict[str, str]],
    stage: str,
    attempt: str,
) -> str:
    """OpenWebUI 호출 한 번의 요청/transport 정보를 비밀값 없이 구성합니다."""

    status_code = getattr(response, "status_code", None)
    if not isinstance(status_code, int) or isinstance(status_code, bool):
        status_code = "unavailable"
    response_url = getattr(response, "url", None)
    request_headers = _build_headers(config)
    request_header_names = sorted(_truncate_log_label(name) for name in request_headers)

    return ", ".join(
        [
            f"diagnostic_version='{OPENWEBUI_DIAGNOSTIC_VERSION}'",
            f"attempt='{attempt}'",
            f"stage={stage}",
            f"endpoint={_format_response_metadata(_redact_endpoint_url(config.url))}",
            f"requested_model={_format_response_metadata(config.model)}",
            "request_stream=False",
            "http_read_stream=False",
            f"request_accept={_format_response_metadata(request_headers.get('Accept'))}",
            f"request_content_type={_format_response_metadata(request_headers.get('Content-Type'))}",
            f"request_header_names=[{','.join(request_header_names)}]",
            f"request_authorization_present={bool(request_headers.get('Authorization'))}",
            f"request_timeout_seconds={config.timeout_seconds}",
            "request_temperature=1.0",
            "request_top_p=1.0",
            "request_reasoning_effort='low'",
            "request_include_reasoning=omitted",
            "request_tool_choice='none'",
            f"request_messages={_format_request_message_shape(messages)}",
            f"response_status={status_code}",
            f"response_url={_format_response_metadata(_redact_endpoint_url(response_url))}",
            f"response_headers={_format_safe_response_headers(response)}",
            f"response_elapsed_ms={_format_response_elapsed_ms(response)}",
        ]
    )


def _with_attempt_context(
    exc: OpenWebUIRequestError,
    *,
    response: requests.Response | None,
    config: OpenWebUISummaryConfig,
    messages: list[dict[str, str]],
    stage: str,
    attempt: str,
) -> OpenWebUIRequestError:
    """기존 오류 subtype을 유지하면서 호출 attempt 진단을 덧붙입니다."""

    error_class = type(exc)
    error_text = str(exc)
    diagnosis_hints: list[str] = []
    response_headers = getattr(response, "headers", None)
    response_content_type = (
        response_headers.get("Content-Type", "") if hasattr(response_headers, "get") else ""
    )
    if "response_object='chat.completion.chunk'" in error_text:
        diagnosis_hints.append("upstream_ignored_stream_false")
    if (
        isinstance(response_content_type, str)
        and "text/event-stream" in response_content_type.lower()
    ):
        diagnosis_hints.append("upstream_returned_sse_for_non_stream_request")
    if isinstance(exc, _OpenWebUIReasoningOnlyResponseError):
        diagnosis_hints.append("reasoning_only_without_final_content")
    elif isinstance(exc, _OpenWebUIEmptyContentResponseError):
        diagnosis_hints.append("stop_without_final_content")
        completion_tokens_match = re.search(r"(?:^|[,{}])completion_tokens=(\d+)", error_text)
        if completion_tokens_match and int(completion_tokens_match.group(1)) > 0:
            diagnosis_hints.append("completion_tokens_without_final_content")
        if "provider_specific_fields:dict(keys=[" in error_text:
            diagnosis_hints.append("provider_output_fields_empty_or_stripped")
    if not diagnosis_hints:
        diagnosis_hints.append("inspect_attempt_transport_and_response_shape")

    attempt_context = _build_attempt_context(
        response=response,
        config=config,
        messages=messages,
        stage=stage,
        attempt=attempt,
    )
    return error_class(
        f"{exc}; diagnosis_hints=[{','.join(diagnosis_hints)}]; "
        f"attempt_context={{{attempt_context}}}"
    )


def _format_token_usage(resp_json: dict[str, Any]) -> str:
    """민감한 본문 없이 알려진 token 사용량만 로그용으로 정리합니다."""

    usage = resp_json.get("usage")
    if not isinstance(usage, dict):
        return "unavailable"

    usage_parts: list[str] = []
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = usage.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            usage_parts.append(f"{key}={value}")

    completion_details = usage.get("completion_tokens_details")
    if isinstance(completion_details, dict):
        for key in (
            "reasoning_tokens",
            "audio_tokens",
            "accepted_prediction_tokens",
            "rejected_prediction_tokens",
        ):
            value = completion_details.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                usage_parts.append(f"{key}={value}")

    return ",".join(usage_parts) if usage_parts else "unavailable"


def _build_response_context(
    resp_json: dict[str, Any],
    choice: dict[str, Any],
    message: dict[str, Any],
    *,
    stage: str,
) -> str:
    """Airflow 오류 분석에 필요한 비민감 OpenWebUI 응답 정보를 구성합니다."""

    response_fields = sorted(
        _truncate_log_label(key)
        for key in resp_json
        if not str(key).startswith("_diagnostic_")
    )[:12]
    choice_fields = sorted(_truncate_log_label(key) for key in choice)[:12]
    message_items = sorted(message.items(), key=lambda item: str(item[0]))[:12]
    message_field_types = ",".join(
        f"{_truncate_log_label(key)}:{_describe_response_value(value)}"
        for key, value in message_items
    )
    if len(message) > len(message_items):
        message_field_types = f"{message_field_types},..."

    return ", ".join(
        [
            f"stage={stage}",
            f"response_id={_format_response_metadata(resp_json.get('id'))}",
            f"response_object={_format_response_metadata(resp_json.get('object'))}",
            f"response_model={_format_response_metadata(resp_json.get('model'))}",
            f"response_fields=[{','.join(response_fields)}]",
            f"choices_count={len(resp_json.get('choices', []))}",
            f"choice_index={_format_response_metadata(choice.get('index', 0))}",
            f"choice_fields=[{','.join(choice_fields)}]",
            f"finish_reason={_format_response_metadata(choice.get('finish_reason'))}",
            f"content_type={type(message.get('content')).__name__}",
            f"message_field_types={{{message_field_types}}}",
            f"usage={{{_format_token_usage(resp_json)}}}",
        ]
    )


def _find_reasoning_value(message: dict[str, Any]) -> Any:
    """표준 및 provider 확장 필드에서 reasoning 값 존재 여부를 찾습니다."""

    for key in ("reasoning_content", "reasoning", "thinking"):
        value = message.get(key)
        if value not in (None, ""):
            return value

    provider_fields = message.get("provider_specific_fields")
    if isinstance(provider_fields, dict):
        for key in ("reasoning_content", "reasoning", "thinking"):
            value = provider_fields.get(key)
            if value not in (None, ""):
                return value
    return None


def _extract_reply_content(resp_json: Any, *, stage: str) -> str:
    """OpenAI 호환 응답에서 텍스트를 추출하고 비텍스트 종료 원인을 구분합니다.

    Chat Completions의 최종 ``message.content``는 문자열 또는 null일 수 있습니다.
    요약 배치는 텍스트만 저장하므로 tool call, 거절, 필터링, audio 응답은
    원문을 임의 변환하지 않고 호출 단계가 포함된 오류로 반환합니다.
    """

    if not isinstance(resp_json, dict):
        raise OpenWebUIRequestError(
            f"OpenWebUI 응답이 JSON 객체가 아닙니다. stage={stage}, response_type={type(resp_json).__name__}"
        )

    choices = resp_json.get("choices")
    if not isinstance(choices, list):
        raise OpenWebUIRequestError(
            f"OpenWebUI 응답 choices가 배열이 아닙니다. stage={stage}, choices_type={type(choices).__name__}"
        )
    if not choices:
        raise OpenWebUIRequestError(f"OpenWebUI 응답 choices가 비어 있습니다. stage={stage}")

    choice = choices[0]
    if not isinstance(choice, dict):
        raise OpenWebUIRequestError(
            f"OpenWebUI 응답 choice가 객체가 아닙니다. stage={stage}, choice_type={type(choice).__name__}"
        )

    message = choice.get("message")
    if not isinstance(message, dict):
        raise OpenWebUIRequestError(
            f"OpenWebUI 응답 message가 객체가 아닙니다. stage={stage}, message_type={type(message).__name__}"
        )

    finish_reason = choice.get("finish_reason")
    content = message.get("content")
    reasoning_value = _find_reasoning_value(message)
    response_context = _build_response_context(resp_json, choice, message, stage=stage)

    if finish_reason == "length":
        raise OpenWebUIRequestError(f"OpenWebUI 응답이 token limit으로 잘렸습니다. {response_context}")

    tool_calls = message.get("tool_calls")
    function_call = message.get("function_call")
    if finish_reason in {"tool_calls", "function_call"} or tool_calls or function_call:
        tool_call_count = (
            len(tool_calls) if isinstance(tool_calls, list) else int(bool(tool_calls or function_call))
        )
        raise OpenWebUIRequestError(
            f"OpenWebUI가 텍스트 대신 tool call을 반환했습니다. "
            f"tool_call_count={tool_call_count}, {response_context}"
        )

    if finish_reason == "content_filter":
        raise _OpenWebUIContentFilterResponseError(
            f"OpenWebUI 응답이 content filter로 차단되었습니다. {response_context}"
        )

    refusal = message.get("refusal")
    if refusal not in (None, ""):
        raise _OpenWebUIRefusalResponseError(
            f"OpenWebUI 모델이 응답 생성을 거절했습니다. {response_context}"
        )

    if message.get("audio") is not None:
        raise OpenWebUIRequestError(f"OpenWebUI가 지원하지 않는 audio 응답을 반환했습니다. {response_context}")

    if content is None:
        error_class = (
            _OpenWebUIReasoningOnlyResponseError
            if reasoning_value is not None
            else _OpenWebUIEmptyContentResponseError
        )
        raise error_class(f"OpenWebUI 응답에 저장할 텍스트가 없습니다. {response_context}")
    if not isinstance(content, str):
        raise OpenWebUIRequestError(
            f"OpenWebUI 응답 content 타입이 OpenAI 호환 계약과 다릅니다. {response_context}"
        )

    summary = content.strip()
    if not summary:
        error_class = (
            _OpenWebUIReasoningOnlyResponseError
            if reasoning_value is not None
            else _OpenWebUIEmptyContentResponseError
        )
        raise error_class(f"OpenWebUI 응답 content가 비어 있습니다. {response_context}")
    return summary


def _format_summary_event_line(raw_line: str) -> str:
    """요약 이벤트 한 줄을 Log Detail 표시 형식으로 정규화합니다."""

    line = raw_line.strip().strip("-•, ")
    if not line:
        return ""
    if line.startswith("["):
        return line

    match = SUMMARY_TIME_LINE_PATTERN.match(line)
    if match:
        return f"[{match.group('time')}] {match.group('event').strip()}"
    return line


def _normalize_summary_text(summary: str) -> str:
    """OpenWebUI 응답을 짧은 streaming 표시용 요약 문자열로 정리합니다."""

    normalized_lines: list[str] = []
    for raw_line in summary.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        split_by_comma = False
        if line.startswith("시간순 요약:"):
            line = line.split(":", 1)[1].strip()
            split_by_comma = True
        if not line or SUMMARY_SECTION_PREFIX_PATTERN.match(line):
            continue

        candidates = [part.strip() for part in line.split(",") if part.strip()] if split_by_comma else [line]
        for candidate in candidates:
            event_line = _format_summary_event_line(candidate)
            if event_line:
                normalized_lines.append(event_line)

    return "\n".join(normalized_lines) or summary.strip()


def _normalize_core_summary_text(summary: str) -> str | None:
    """핵심 요약 응답을 llm_core_summary 저장 형식으로 정규화합니다."""

    lines = [line.strip().strip("-• ") for line in summary.splitlines() if line.strip()]
    compact = " ".join(lines).strip()
    if compact.startswith("핵심 요약:"):
        compact = compact.split(":", 1)[1].strip()
    if compact.upper() == NO_CORE_SUMMARY_SENTINEL:
        return None
    return compact or None


def _normalize_reviewed_core_summary_text(review: str, candidate: str) -> str | None:
    """AI 검수 응답을 최종 llm_core_summary 값으로 정규화합니다."""

    lines = [line.strip().strip("-• ") for line in review.splitlines() if line.strip()]
    compact = " ".join(lines).strip()
    upper_compact = compact.upper()
    if upper_compact == "KEEP":
        return candidate
    if upper_compact == NO_CORE_SUMMARY_SENTINEL:
        return None
    if compact.startswith(CORE_SUMMARY_REWRITE_PREFIX):
        return _normalize_core_summary_text(compact[len(CORE_SUMMARY_REWRITE_PREFIX):].strip())
    return _normalize_core_summary_text(compact)


def _parse_chat_completion_response(response: requests.Response, *, stage: str) -> str:
    """non-stream JSON chat completion 응답을 해석합니다."""

    try:
        resp_json = response.json()
    except (json.JSONDecodeError, ValueError) as exc:
        response_text = getattr(response, "text", "")
        text_length = len(response_text) if isinstance(response_text, str) else "unavailable"
        raise OpenWebUIRequestError(
            f"OpenWebUI 응답 JSON 파싱 실패: status={response.status_code}, "
            f"text_type={type(response_text).__name__}, text_length={text_length}"
        ) from exc
    return _extract_reply_content(resp_json, stage=stage)


def _post_chat_completion_once(
    *,
    session: requests.Session,
    config: OpenWebUISummaryConfig,
    messages: list[dict[str, str]],
    stage: str,
    attempt: str,
) -> str:
    """OpenWebUI chat completions API를 non-stream 방식으로 한 번 호출합니다."""

    if not config.url:
        raise OpenWebUIConfigError("OPENWEBUI_URL 설정이 비어 있습니다.")
    if not config.model:
        raise OpenWebUIConfigError("OPENWEBUI_MODEL 설정이 비어 있습니다.")

    payload = {
        "model": config.model,
        "messages": messages,
        # gpt-oss 권장 sampling과 단순 요약용 reasoning 강도를 명시합니다.
        "temperature": 1.0,
        "top_p": 1.0,
        "reasoning_effort": "low",
        "stream": False,
        "tool_choice": "none",
    }

    response: requests.Response | None = None
    try:
        response = session.post(
            config.url,
            headers=_build_headers(config),
            json=payload,
            timeout=config.timeout_seconds,
            stream=False,
        )
        response.raise_for_status()
        return _parse_chat_completion_response(response, stage=stage)
    except OpenWebUIRequestError as exc:
        raise _with_attempt_context(
            exc,
            response=response,
            config=config,
            messages=messages,
            stage=stage,
            attempt=attempt,
        ) from exc
    except requests.HTTPError as exc:
        status = getattr(response, "status_code", "unavailable")
        request_error = OpenWebUIRequestError(f"OpenWebUI HTTP 오류: status={status}")
        raise _with_attempt_context(
            request_error,
            response=response,
            config=config,
            messages=messages,
            stage=stage,
            attempt=attempt,
        ) from exc
    except requests.RequestException as exc:
        exception_message = str(exc)
        request_error = OpenWebUIRequestError(
            f"OpenWebUI 요청 실패: exception_type={type(exc).__name__}, "
            f"exception_message_length={len(exception_message)}"
        )
        raise _with_attempt_context(
            request_error,
            response=response,
            config=config,
            messages=messages,
            stage=stage,
            attempt=attempt,
        ) from exc


def _post_chat_completion(
    *,
    session: requests.Session,
    config: OpenWebUISummaryConfig,
    messages: list[dict[str, str]],
    stage: str,
) -> str:
    """추측성 fallback 없이 non-stream chat completion을 한 번 호출합니다."""

    return _post_chat_completion_once(
        session=session,
        config=config,
        messages=messages,
        stage=stage,
        attempt="single_non_stream",
    )


def _request_event_summary(
    *,
    session: requests.Session,
    config: OpenWebUISummaryConfig,
    contents_text: str,
    workorder_title: str = "",
    default_event_time: datetime | None = None,
) -> str:
    """큰 contents_text를 이벤트 묶음으로 나눠 시간순 요약을 생성합니다."""

    normalized_contents_text = _normalize_summary_source_text(contents_text)
    timestamped_events = _build_timestamped_event_text(
        normalized_contents_text,
        default_event_time=default_event_time,
    )
    prompt_source = timestamped_events or normalized_contents_text
    source_label = "timestamped_events" if timestamped_events else "contents_text"
    chunks = _split_summary_source_chunks(prompt_source) or [prompt_source]
    summary_chunks: list[str] = []

    for chunk in chunks:
        chunk_summary = _normalize_summary_text(
            _post_chat_completion(
                session=session,
                config=config,
                messages=_build_summary_prompt_from_source(
                    source_label=source_label,
                    prompt_source=chunk,
                    workorder_title=workorder_title,
                ),
                stage="event_summary",
            )
        )
        if chunk_summary:
            summary_chunks.append(chunk_summary)

    return "\n".join(summary_chunks)


def request_summary(
    *,
    session: requests.Session,
    config: OpenWebUISummaryConfig,
    contents_text: str,
    workorder_title: str = "",
    default_event_time: datetime | None = None,
) -> GeneratedSummary:
    """OpenWebUI로 시간순 상세 요약과 핵심 요약을 분리해 반환합니다."""

    event_summary = _request_event_summary(
        session=session,
        config=config,
        contents_text=contents_text,
        workorder_title=workorder_title,
        default_event_time=default_event_time,
    )

    try:
        core_summary = _normalize_core_summary_text(
            _post_chat_completion(
                session=session,
                config=config,
                messages=build_core_summary_prompt(event_summary),
                stage="core_summary",
            )
        )
    except _OpenWebUIRowResponseError as exc:
        logger.warning(
            "OpenWebUI 핵심요약 응답 오류로 시간순 요약만 저장합니다. %s",
            exc,
        )
        return GeneratedSummary(core_summary=None, event_summary=event_summary)

    if core_summary is None:
        return GeneratedSummary(core_summary=None, event_summary=event_summary)

    try:
        reviewed_core_summary = _normalize_reviewed_core_summary_text(
            _post_chat_completion(
                session=session,
                config=config,
                messages=build_core_summary_review_prompt(event_summary, core_summary),
                stage="core_review",
            ),
            core_summary,
        )
    except _OpenWebUIRowResponseError as exc:
        logger.warning(
            "OpenWebUI 핵심요약 검수 응답 오류로 시간순 요약만 저장합니다. %s",
            exc,
        )
        return GeneratedSummary(core_summary=None, event_summary=event_summary)

    return GeneratedSummary(core_summary=reviewed_core_summary, event_summary=event_summary)


def _get_summary_error_code(exc: OpenWebUIConfigError | OpenWebUIRequestError) -> str:
    """저장할 수 있는 안정적인 요약 오류 코드를 반환합니다."""

    if isinstance(exc, _OpenWebUIRowResponseError):
        return exc.error_code
    if isinstance(exc, OpenWebUIConfigError):
        return "config_error"
    return "openwebui_error"


def _record_summary_failure(
    *,
    comment: CtProcessComment,
    exc: OpenWebUIConfigError | OpenWebUIRequestError,
) -> bool:
    """마지막 오류를 기록하고 row 응답 오류만 재시도 횟수에 반영합니다.

    반환값은 이번 오류로 재시도 한도를 소진해 배치 대상에서 제외됐는지 나타냅니다.
    실패 갱신은 원본 변경 순서를 보존하기 위해 ``updated_at``을 변경하지 않습니다.
    """

    error_code = _get_summary_error_code(exc)
    error_message = str(exc)[:SUMMARY_LAST_ERROR_MAX_CHARS]
    queryset = CtProcessComment.objects.filter(
        pk=comment.pk,
        contents_text=comment.contents_text,
        update_flag="Y",
    )

    if not isinstance(exc, _OpenWebUIRowResponseError):
        queryset.update(
            summary_last_error_code=error_code,
            summary_last_error=error_message,
        )
        return False

    current_retry_count = comment.summary_retry_count
    next_retry_count = min(current_retry_count + 1, SUMMARY_MAX_RETRY_COUNT)
    exhausted = next_retry_count >= SUMMARY_MAX_RETRY_COUNT
    updated_count = queryset.filter(summary_retry_count=current_retry_count).update(
        summary_retry_count=next_retry_count,
        summary_last_error_code=error_code,
        summary_last_error=error_message,
        update_flag="N" if exhausted else "Y",
    )
    return updated_count == 1 and exhausted


def summarize_pending_ct_process_comments(
    *,
    limit: int | None = None,
    workorder_id: str | None = None,
    dry_run: bool = False,
    session: requests.Session | None = None,
    config: OpenWebUISummaryConfig | None = None,
) -> SummaryRunSummary:
    """요약 대상 comment row를 OpenWebUI로 요약하고 성공 row의 flag를 완료 처리합니다."""

    resolved_limit = limit or int(getattr(settings, "OPENWEBUI_SUMMARY_BATCH_SIZE", 100) or 100)
    if resolved_limit < 1:
        raise ValueError("limit은 1 이상이어야 합니다.")

    active_session = session or requests.Session()
    active_config = config or OpenWebUISummaryConfig.from_settings()
    outcomes: list[SummaryRowOutcome] = []

    pending_comments = list(selectors.list_pending_summary_comments(limit=resolved_limit, workorder_id=workorder_id))
    workorder_titles = ctttm_workorder_selectors.load_workorder_descriptions_by_ids(
        workorder_ids=[comment.workorder_id for comment in pending_comments]
    )

    for comment in pending_comments:
        contents_text = (comment.contents_text or "").strip()
        if not contents_text:
            if not dry_run:
                CtProcessComment.objects.filter(
                    pk=comment.pk,
                    contents_text=comment.contents_text,
                    update_flag="Y",
                ).update(
                    summary_retry_count=0,
                    summary_last_error_code=None,
                    summary_last_error=None,
                    update_flag="N",
                    updated_at=timezone.now(),
                )
            outcomes.append(
                SummaryRowOutcome(
                    workorder_id=comment.workorder_id,
                    status=SUMMARY_STATUS_SKIPPED,
                    error_message="contents_text가 비어 있습니다.",
                )
            )
            continue

        if dry_run:
            outcomes.append(SummaryRowOutcome(workorder_id=comment.workorder_id, status=SUMMARY_STATUS_DRY_RUN))
            continue

        try:
            summary = request_summary(
                session=active_session,
                config=active_config,
                contents_text=contents_text,
                workorder_title=workorder_titles.get(comment.workorder_id, ""),
                default_event_time=comment.create_date,
            )
            with transaction.atomic():
                updated_count = CtProcessComment.objects.filter(
                    pk=comment.pk,
                    contents_text=comment.contents_text,
                    update_flag="Y",
                ).update(
                    llm_summary=summary.event_summary,
                    llm_core_summary=summary.core_summary,
                    summary_retry_count=0,
                    summary_last_error_code=None,
                    summary_last_error=None,
                    update_flag="N",
                    updated_at=timezone.now(),
                )
            if updated_count != 1:
                raise OpenWebUIRequestError("요약 저장 대상 row가 이미 변경되었습니다.")
            outcomes.append(
                SummaryRowOutcome(
                    workorder_id=comment.workorder_id,
                    status=SUMMARY_STATUS_SUCCESS,
                    summary=summary.event_summary,
                )
            )
        except _OpenWebUIRowResponseError as exc:
            exhausted = _record_summary_failure(comment=comment, exc=exc)
            outcomes.append(
                SummaryRowOutcome(
                    workorder_id=comment.workorder_id,
                    status=SUMMARY_STATUS_EXHAUSTED if exhausted else SUMMARY_STATUS_FAILED,
                    error_message=str(exc),
                )
            )
        except (OpenWebUIConfigError, OpenWebUIRequestError) as exc:
            _record_summary_failure(comment=comment, exc=exc)
            outcomes.append(
                SummaryRowOutcome(
                    workorder_id=comment.workorder_id,
                    status=SUMMARY_STATUS_FAILED,
                    error_message=str(exc),
                )
            )

    return SummaryRunSummary(outcomes=outcomes)
