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
from api.data_movement.ctttm_workorder_list import selectors as ctttm_workorder_selectors

logger = logging.getLogger(__name__)


SUMMARY_STATUS_SUCCESS = "success"
SUMMARY_STATUS_FAILED = "failed"
SUMMARY_STATUS_SKIPPED = "skipped"
SUMMARY_STATUS_DRY_RUN = "dry_run"
NO_CORE_SUMMARY_SENTINEL = "NO_CORE_SUMMARY"
SUMMARY_CHUNK_MAX_EVENTS = 40
SUMMARY_CHUNK_MAX_CHARS = 8000
CONTENTS_EVENT_HEADER_PATTERN = re.compile(
    r"^\[\s*(?P<time>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s*/\s*(?P<author>[^\]]+?)\s*\]\s*$"
)
SUMMARY_SECTION_PREFIX_PATTERN = re.compile(r"^(원인|조치사항|결과)\s*:")
SUMMARY_TIME_LINE_PATTERN = re.compile(
    r"^(?P<time>(?:\d{4}[-/.]\d{2}[-/.]\d{2}\s+)?\d{1,2}:\d{2}(?::\d{2})?)\s+(?P<event>.+)$"
)
CORE_SUMMARY_REWRITE_PREFIX = "REWRITE:"
OPENWEBUI_DIAGNOSTIC_VERSION = "ctpc-openwebui-v3"
OPENWEBUI_SAFE_RESPONSE_HEADERS = (
    "Content-Type",
    "Content-Length",
    "Transfer-Encoding",
    "Server",
    "Via",
    "X-Request-ID",
    "X-OpenAI-Request-ID",
    "X-Correlation-ID",
    "Traceparent",
    "CF-Ray",
    "X-Envoy-Upstream-Service-Time",
)

SUMMARY_SYSTEM_PROMPT = """당신은 설비 점검 이력 요약기입니다.
입력으로 제공된 이벤트 목록에 실제로 포함된 사실만 사용하세요.
workorder_title은 사람이 작성한 작업 제목 또는 작업 목적 설명입니다.
workorder_title이 제공되면 이벤트 의미를 파악하는 보조 정보로 반영하세요.
입력에 없는 원인, 조치사항, 결과, 시간, 장비 상태를 절대로 추정하거나 생성하지 마세요.

작업:
1. 설비 점검 이력을 확인 가능한 시간 순서대로 정리하세요.
2. 입력 이벤트는 모두 출력하되, 각 시간 이벤트의 내용만 한 줄로 짧게 요약하세요.
3. 이벤트 설명은 핵심 상태나 조치만 남기고 가능하면 35자 이내로 쓰세요.
4. 각 줄은 반드시 "[YYYY-MM-DD HH:MM] 이벤트" 형식으로 쓰세요.
5. 한 줄에는 하나의 이벤트만 쓰고, 이벤트 사이에는 줄바꿈만 사용하세요.
6. 대괄호 안 시간은 입력 이벤트의 시간을 그대로 사용하세요.
7. 입력 이벤트끼리 합치거나 누락하지 마세요.
8. 같은 시간 이벤트 안에서 같은 의미의 중복 내용만 합치세요.
9. 출력 형식 외의 설명, 추론 과정, 사과문, 안내문은 쓰지 마세요.

출력 형식:
[2026-06-19 13:44] 점검 시작
[2026-06-19 18:37] 조치 완료"""

CORE_SUMMARY_SYSTEM_PROMPT = """당신은 설비 점검 이력 핵심 요약기입니다.
입력으로 제공된 시간순 요약에 실제로 포함된 사실만 사용하세요.
입력에 없는 원인, 조치사항, 결과, 시간, 장비 상태를 절대로 추정하거나 생성하지 마세요.

작업:
1. 입력된 시간순 요약 전체 흐름을 1~2문장으로 매우 짧게 요약하세요.
2. 시간순 요약이 한 줄이거나 단순 점검/확인/알람 내용이어도 확인된 사실을 그대로 짧게 요약하세요.
3. 문제가 해결, 완료, 정상화, 복구되었다는 표현은 입력에 명시된 경우에만 쓰세요.
4. 입력에 해결 여부가 명시되지 않았다면 확인된 진행 상황만 있는 그대로 요약하세요.
5. 단순 점검, 확인, 조치 진행, 알람 확인만으로 문제가 해결되었다고 추정하지 마세요.
6. 구체 장비명, 부품명, 알람명, 작업명, 상태, 결과가 있으면 우선 포함하세요.
7. 구체 대상이 없어도 입력에 있는 일반 표현만으로 짧게 요약할 수 있으면 "NO_CORE_SUMMARY"를 쓰지 마세요.
8. 입력이 비어 있거나 내용 없음, 확인 불가, 해당 없음처럼 저장할 사실이 없을 때만 정확히 "NO_CORE_SUMMARY"를 출력하세요.
9. 핵심요약을 작성할 때 첫 줄은 반드시 "핵심 요약: "으로 시작하세요.
10. 출력은 핵심 요약 한 줄 또는 "NO_CORE_SUMMARY"만 작성하세요.
11. 설명, 추론 과정, 사과문, 안내문, markdown은 쓰지 마세요.

출력 형식:
핵심 요약: 점검 시작 후 알람을 확인했고 조치 내용이 기록되었습니다."""

CORE_SUMMARY_REVIEW_SYSTEM_PROMPT = """당신은 설비 점검 이력 핵심요약 검수자입니다.
입력으로 시간순 요약과 후보 핵심요약이 제공됩니다.
시간순 요약에 실제로 포함된 사실만 사용하세요.
입력에 없는 원인, 조치사항, 결과, 시간, 장비 상태를 절대로 추정하거나 생성하지 마세요.

판단 기준:
1. 후보 핵심요약이 시간순 요약의 사실과 충돌하지 않으면 단순하거나 일반적인 표현이어도 "KEEP"만 출력하세요.
2. 후보가 모호하지만 시간순 요약에서 더 구체적으로 바꿀 수 있으면 "REWRITE: " 뒤에 구체 핵심요약을 한 줄로 작성하세요.
3. 후보가 시간순 요약에 없는 사실을 추가했거나 시간순 요약에 저장할 사실이 없을 때만 정확히 "NO_CORE_SUMMARY"를 출력하세요.
4. 해결, 완료, 정상화, 복구 표현은 시간순 요약에 명시된 경우에만 쓰세요.
5. 판단이 애매하면 버리지 말고 "KEEP"을 출력하세요.
6. 설명, 추론 과정, 사과문, 안내문, markdown은 쓰지 마세요.

출력 형식:
KEEP
REWRITE: TMP 센서 알람 후 CH-A 밸브 탈착 및 장착이 완료되었습니다.
NO_CORE_SUMMARY"""


class OpenWebUIConfigError(RuntimeError):
    """OpenWebUI 설정이 부족할 때 발생합니다."""


class OpenWebUIRequestError(RuntimeError):
    """OpenWebUI 요청 또는 응답 처리에 실패했을 때 발생합니다."""


class _OpenWebUIEmptyContentResponseError(OpenWebUIRequestError):
    """OpenWebUI가 저장할 최종 content 없이 종료했을 때 발생합니다."""


class _OpenWebUIReasoningOnlyResponseError(_OpenWebUIEmptyContentResponseError):
    """OpenWebUI가 최종 답변 없이 reasoning만 반환했을 때 발생합니다."""


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


def _normalize_summary_source_text(value: str) -> str:
    """이스케이프된 개행을 복원하고 연속된 줄바꿈을 하나로 축약합니다."""

    normalized = (
        value.replace("\\r\\n", "\n")
        .replace("\\n", "\n")
        .replace("\\r", "\n")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )
    return re.sub(r"\n(?:[ \t]*\n)+", "\n", normalized).strip()


def _build_timestamped_event_text(
    contents_text: str,
    *,
    default_event_time: datetime | None = None,
) -> str:
    """comment header 또는 기본 시간으로 timestamp 확정 이벤트를 생성합니다."""

    events: list[str] = []
    current_time = ""
    current_lines: list[str] = []

    def flush_current_event() -> None:
        if not current_time or not current_lines:
            return
        event_text = " ".join(" ".join(current_lines).split())
        if event_text:
            events.append(f"[{current_time}] {event_text}")

    for raw_line in contents_text.splitlines():
        line = raw_line.strip()
        match = CONTENTS_EVENT_HEADER_PATTERN.match(line)
        if match:
            flush_current_event()
            current_time = match.group("time")
            current_lines = []
            continue
        if current_time and line:
            current_lines.append(line)

    flush_current_event()
    if events or default_event_time is None:
        return "\n".join(events)

    if not contents_text:
        return ""
    return f"[{default_event_time.strftime('%Y-%m-%d %H:%M')}] {contents_text}"


def _split_summary_source_chunks(source_text: str) -> list[str]:
    """큰 요약 입력을 OpenWebUI가 처리하기 쉬운 이벤트 묶음으로 나눕니다."""

    lines = [line for line in source_text.splitlines() if line.strip()]
    if not lines:
        return []

    chunks: list[str] = []
    current_lines: list[str] = []
    current_chars = 0

    for line in lines:
        projected_chars = current_chars + len(line) + (1 if current_lines else 0)
        should_flush = bool(current_lines) and (
            len(current_lines) >= SUMMARY_CHUNK_MAX_EVENTS or projected_chars > SUMMARY_CHUNK_MAX_CHARS
        )
        if should_flush:
            chunks.append("\n".join(current_lines))
            current_lines = []
            current_chars = 0

        current_lines.append(line)
        current_chars += len(line) + (1 if len(current_lines) > 1 else 0)

    if current_lines:
        chunks.append("\n".join(current_lines))
    return chunks


def _build_summary_prompt_from_source(
    *,
    source_label: str,
    prompt_source: str,
    workorder_title: str = "",
) -> list[dict[str, str]]:
    """요약 source를 OpenWebUI chat completions용 message 목록으로 감쌉니다."""

    content_parts: list[str] = []
    if workorder_title.strip():
        content_parts.extend(
            [
                "workorder_title:",
                "<<<",
                workorder_title.strip(),
                ">>>",
                "",
            ]
        )
    content_parts.extend(
        [
            f"{source_label}:",
            "<<<",
            prompt_source,
            ">>>",
        ]
    )

    return [
        {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": "\n".join(content_parts),
        },
    ]


def build_summary_prompt(
    contents_text: str,
    workorder_title: str = "",
    default_event_time: datetime | None = None,
) -> list[dict[str, str]]:
    """OpenWebUI chat completions용 고정 message 목록을 생성합니다."""

    normalized_contents_text = _normalize_summary_source_text(contents_text)
    timestamped_events = _build_timestamped_event_text(
        normalized_contents_text,
        default_event_time=default_event_time,
    )
    return _build_summary_prompt_from_source(
        source_label="timestamped_events" if timestamped_events else "contents_text",
        prompt_source=timestamped_events or normalized_contents_text,
        workorder_title=workorder_title,
    )


def build_core_summary_prompt(event_summary: str) -> list[dict[str, str]]:
    """시간순 요약 결과를 핵심 요약 생성용 message 목록으로 변환합니다."""

    return [
        {"role": "system", "content": CORE_SUMMARY_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": "\n".join(
                [
                    "time_ordered_summary:",
                    "<<<",
                    event_summary,
                    ">>>",
                ]
            ),
        },
    ]


def build_core_summary_review_prompt(event_summary: str, core_summary: str) -> list[dict[str, str]]:
    """핵심 요약 후보를 검수하는 OpenWebUI message 목록을 생성합니다."""

    return [
        {"role": "system", "content": CORE_SUMMARY_REVIEW_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": "\n".join(
                [
                    "time_ordered_summary:",
                    "<<<",
                    event_summary,
                    ">>>",
                    "",
                    "candidate_core_summary:",
                    "<<<",
                    core_summary,
                    ">>>",
                ]
            ),
        },
    ]


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
        raise OpenWebUIRequestError(f"OpenWebUI 응답이 content filter로 차단되었습니다. {response_context}")

    refusal = message.get("refusal")
    if refusal not in (None, ""):
        raise OpenWebUIRequestError(f"OpenWebUI 모델이 응답 생성을 거절했습니다. {response_context}")

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
    except _OpenWebUIEmptyContentResponseError as exc:
        logger.warning(
            "OpenWebUI 핵심요약 응답이 비어 시간순 요약만 저장합니다. %s",
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
    except _OpenWebUIEmptyContentResponseError as exc:
        logger.warning(
            "OpenWebUI 핵심요약 검수 응답이 비어 시간순 요약만 저장합니다. %s",
            exc,
        )
        return GeneratedSummary(core_summary=None, event_summary=event_summary)

    return GeneratedSummary(core_summary=reviewed_core_summary, event_summary=event_summary)


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
                CtProcessComment.objects.filter(pk=comment.pk, update_flag="Y").update(
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
                updated_count = CtProcessComment.objects.filter(pk=comment.pk, update_flag="Y").update(
                    llm_summary=summary.event_summary,
                    llm_core_summary=summary.core_summary,
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
        except (OpenWebUIConfigError, OpenWebUIRequestError) as exc:
            outcomes.append(
                SummaryRowOutcome(
                    workorder_id=comment.workorder_id,
                    status=SUMMARY_STATUS_FAILED,
                    error_message=str(exc),
                )
            )

    return SummaryRunSummary(outcomes=outcomes)
