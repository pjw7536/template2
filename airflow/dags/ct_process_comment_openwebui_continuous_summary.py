"""ct_process_comment 데이터를 사용하는 OpenWebUI 연속 요약 DAG입니다."""

from __future__ import annotations

import itertools
import logging
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import requests
from airflow import DAG
from airflow.hooks.base import BaseHook
from airflow.models.param import Param
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago

logger = logging.getLogger(__name__)

DATABASE_CONNECTION_ID = os.getenv(
    "CT_PROCESS_SUMMARY_DB_CONNECTION_ID",
    "ct_process_comment_summary_db",
)
OPENWEBUI_CONNECTION_ID = os.getenv(
    "CT_PROCESS_SUMMARY_OPENWEBUI_CONNECTION_ID",
    "openwebui_continuous_summary",
)

SUMMARY_CHUNK_MAX_EVENTS = 40
SUMMARY_CHUNK_MAX_CHARS = 8000
CONTENTS_EVENT_HEADER_PATTERN = re.compile(
    r"^\[\s*(?P<time>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s*/\s*(?P<author>[^\]]+?)\s*\]\s*$"
)

SUMMARY_SYSTEM_PROMPT = """당신은 설비 점검 이력 요약기입니다.
입력으로 제공된 이벤트 목록에 실제로 포함된 사실만 사용하세요.
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
9. 출력 형식 외의 설명, 추론 과정, 사과문, 안내문은 쓰지 마세요."""

CORE_SUMMARY_SYSTEM_PROMPT = """당신은 설비 점검 이력 핵심 요약기입니다.
입력으로 제공된 시간순 요약에 실제로 포함된 사실만 사용하세요.
입력에 없는 원인, 조치사항, 결과, 시간, 장비 상태를 절대로 추정하거나 생성하지 마세요.
입력된 전체 흐름을 "핵심 요약: "으로 시작하는 1~2문장으로 매우 짧게 요약하세요.
설명, 추론 과정, 사과문, 안내문, markdown은 쓰지 마세요."""

CORE_SUMMARY_REVIEW_SYSTEM_PROMPT = """당신은 설비 점검 이력 핵심요약 검수자입니다.
입력으로 시간순 요약과 후보 핵심요약이 제공됩니다.
시간순 요약에 실제로 포함된 사실만 사용하세요.
후보가 사실과 충돌하지 않으면 KEEP, 고쳐야 하면 REWRITE: 뒤에 수정 요약,
저장할 사실이 없으면 NO_CORE_SUMMARY만 출력하세요."""


@dataclass(frozen=True)
class SummarySourceRow:
    """연속 요약 요청에 사용할 ct_process_comment 읽기 모델입니다."""

    workorder_id: str
    contents_text: str
    create_date: datetime | None


@dataclass(frozen=True)
class OpenWebUIRequestConfig:
    """Airflow Connection에서 읽은 OpenWebUI 요청 설정입니다."""

    endpoint: str
    model: str
    api_token: str
    headers: dict[str, str]
    timeout_seconds: int


@dataclass
class WorkerStats:
    """worker별 연속 요약 처리량과 지연시간 집계입니다."""

    row_count: int = 0
    request_count: int = 0
    failure_count: int = 0
    total_latency_seconds: float = 0.0
    max_latency_seconds: float = 0.0

    def record_success(self, latency_seconds: float) -> None:
        """성공한 OpenWebUI 요청 지표를 누적합니다."""

        self.request_count += 1
        self.total_latency_seconds += latency_seconds
        self.max_latency_seconds = max(self.max_latency_seconds, latency_seconds)

    def record_failure(self, latency_seconds: float) -> None:
        """실패한 OpenWebUI 요청 지표를 누적합니다."""

        self.request_count += 1
        self.failure_count += 1
        self.total_latency_seconds += latency_seconds
        self.max_latency_seconds = max(self.max_latency_seconds, latency_seconds)


class OpenWebUIRequestError(RuntimeError):
    """OpenWebUI 요청이 성공 응답을 반환하지 않을 때 발생합니다."""


def _normalize_source_text(value: str) -> str:
    """이스케이프된 개행을 복원하고 빈 줄을 축약합니다."""

    normalized = (
        value.replace("\\r\\n", "\n")
        .replace("\\n", "\n")
        .replace("\\r", "\n")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )
    return re.sub(r"\n(?:[ \t]*\n)+", "\n", normalized).strip()


def _build_timestamped_event_text(row: SummarySourceRow) -> str:
    """원문의 시간 header를 유지한 요약 입력 문자열을 만듭니다."""

    events: list[str] = []
    current_time = ""
    current_lines: list[str] = []

    def flush_current_event() -> None:
        if not current_time or not current_lines:
            return
        event_text = " ".join(" ".join(current_lines).split())
        if event_text:
            events.append(f"[{current_time}] {event_text}")

    normalized = _normalize_source_text(row.contents_text)
    for raw_line in normalized.splitlines():
        line = raw_line.strip()
        match = CONTENTS_EVENT_HEADER_PATTERN.match(line)
        if match:
            flush_current_event()
            current_time = match.group("time")
            current_lines = []
        elif current_time and line:
            current_lines.append(line)

    flush_current_event()
    if events:
        return "\n".join(events)
    if row.create_date is not None:
        return f"[{row.create_date.strftime('%Y-%m-%d %H:%M')}] {normalized}"
    return normalized


def _split_source_chunks(source_text: str) -> list[str]:
    """실서비스와 같은 이벤트 수와 글자 수 기준으로 입력을 분할합니다."""

    lines = [line for line in source_text.splitlines() if line.strip()]
    if not lines:
        return []

    chunks: list[str] = []
    current_lines: list[str] = []
    current_chars = 0
    for line in lines:
        projected_chars = current_chars + len(line) + (1 if current_lines else 0)
        should_flush = bool(current_lines) and (
            len(current_lines) >= SUMMARY_CHUNK_MAX_EVENTS
            or projected_chars > SUMMARY_CHUNK_MAX_CHARS
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


def _read_openwebui_config() -> OpenWebUIRequestConfig:
    """전용 Airflow Connection에서 endpoint와 비밀값을 읽습니다."""

    connection = BaseHook.get_connection(OPENWEBUI_CONNECTION_ID)
    extra = connection.extra_dejson
    endpoint = str(extra.get("endpoint") or connection.host or "").strip()
    model = str(extra.get("model") or "").strip()
    if not endpoint:
        raise ValueError(f"{OPENWEBUI_CONNECTION_ID} Connection의 endpoint가 비어 있습니다.")
    if not model:
        raise ValueError(f"{OPENWEBUI_CONNECTION_ID} Connection의 model이 비어 있습니다.")
    if not endpoint.startswith(("http://", "https://")):
        raise ValueError("OpenWebUI endpoint는 http:// 또는 https://로 시작해야 합니다.")

    raw_headers = extra.get("headers") or {}
    if not isinstance(raw_headers, dict):
        raise ValueError("OpenWebUI Connection의 headers는 JSON 객체여야 합니다.")
    headers = {
        str(key): str(value)
        for key, value in raw_headers.items()
        if isinstance(key, str) and isinstance(value, (str, int, float, bool))
    }
    timeout_seconds = max(1, min(int(extra.get("timeout_seconds") or 120), 1800))
    return OpenWebUIRequestConfig(
        endpoint=endpoint,
        model=model,
        api_token=(connection.password or "").strip(),
        headers=headers,
        timeout_seconds=timeout_seconds,
    )


def _read_summary_rows(*, row_limit: int) -> list[SummarySourceRow]:
    """전용 DB Connection으로 ct_process_comment를 읽기 전용 조회합니다."""

    import psycopg2

    connection = BaseHook.get_connection(DATABASE_CONNECTION_ID)
    connect_kwargs: dict[str, Any] = {
        "dbname": connection.schema or "dashboard",
        "user": connection.login,
        "password": connection.password,
        "host": connection.host,
        "connect_timeout": 10,
        "application_name": "ct_process_comment_openwebui_continuous_summary",
    }
    if connection.port:
        connect_kwargs["port"] = connection.port

    db_connection = psycopg2.connect(**connect_kwargs)
    try:
        db_connection.set_session(readonly=True, autocommit=False)
        with db_connection.cursor() as cursor:
            cursor.execute(
                """
                select workorder_id, contents_text, create_date
                from ct_process_comment
                where contents_text is not null
                  and btrim(contents_text) <> ''
                order by updated_at desc, id desc
                limit %s
                """,
                (row_limit,),
            )
            rows = [
                SummarySourceRow(
                    workorder_id=str(workorder_id),
                    contents_text=str(contents_text),
                    create_date=create_date,
                )
                for workorder_id, contents_text, create_date in cursor.fetchall()
            ]
        db_connection.rollback()
        return rows
    finally:
        db_connection.close()


def _build_headers(config: OpenWebUIRequestConfig) -> dict[str, str]:
    """비밀값을 log에 노출하지 않고 OpenWebUI 요청 header를 구성합니다."""

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        **config.headers,
    }
    if config.api_token:
        token = config.api_token
        headers["Authorization"] = token if token.lower().startswith("bearer ") else f"Bearer {token}"
    return headers


def _extract_response_content(response: requests.Response) -> str:
    """다음 요약 단계 입력에 사용할 OpenAI 호환 content를 추출합니다."""

    try:
        payload = response.json()
    except ValueError as exc:
        raise OpenWebUIRequestError("OpenWebUI 응답 JSON 파싱에 실패했습니다.") from exc
    if not isinstance(payload, dict):
        raise OpenWebUIRequestError("OpenWebUI 응답이 JSON 객체가 아닙니다.")

    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise OpenWebUIRequestError("OpenWebUI 응답 choices가 비어 있습니다.")
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise OpenWebUIRequestError("OpenWebUI 응답 message가 없습니다.")
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()
    if isinstance(content, list):
        text_parts = [
            str(part.get("text")).strip()
            for part in content
            if isinstance(part, dict) and isinstance(part.get("text"), str) and part.get("text").strip()
        ]
        if text_parts:
            return "\n".join(text_parts)
    raise OpenWebUIRequestError("OpenWebUI 응답 content가 비어 있습니다.")


def _post_completion(
    *,
    session: requests.Session,
    config: OpenWebUIRequestConfig,
    messages: list[dict[str, str]],
) -> tuple[str, float]:
    """실서비스와 같은 non-stream chat completion 요청을 한 번 보냅니다."""

    started_at = time.monotonic()
    response: requests.Response | None = None
    try:
        response = session.post(
            config.endpoint,
            headers=_build_headers(config),
            json={
                "model": config.model,
                "messages": messages,
                "temperature": 1.0,
                "top_p": 1.0,
                "reasoning_effort": "low",
                "stream": False,
                "tool_choice": "none",
            },
            timeout=config.timeout_seconds,
        )
        response.raise_for_status()
        return _extract_response_content(response), time.monotonic() - started_at
    except requests.HTTPError as exc:
        status_code = response.status_code if response is not None else "unavailable"
        raise OpenWebUIRequestError(
            f"OpenWebUI HTTP 오류가 발생했습니다: status={status_code}"
        ) from exc
    except requests.RequestException as exc:
        raise OpenWebUIRequestError(
            f"OpenWebUI transport 오류가 발생했습니다: type={type(exc).__name__}"
        ) from exc


def _request_row_summary(
    *,
    session: requests.Session,
    config: OpenWebUIRequestConfig,
    row: SummarySourceRow,
    stats: WorkerStats,
) -> None:
    """시간순 요약, 핵심 요약, 검수 요청을 수행하고 결과는 폐기합니다."""

    source_text = _build_timestamped_event_text(row)
    chunks = _split_source_chunks(source_text) or [source_text]
    event_summaries: list[str] = []
    for chunk in chunks:
        event_summary, latency_seconds = _post_completion(
            session=session,
            config=config,
            messages=[
                {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"timestamped_events:\n<<<\n{chunk}\n>>>",
                },
            ],
        )
        stats.record_success(latency_seconds)
        event_summaries.append(event_summary)

    event_summary_text = "\n".join(event_summaries)
    core_summary, latency_seconds = _post_completion(
        session=session,
        config=config,
        messages=[
            {"role": "system", "content": CORE_SUMMARY_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"time_ordered_summary:\n<<<\n{event_summary_text}\n>>>",
            },
        ],
    )
    stats.record_success(latency_seconds)

    _, latency_seconds = _post_completion(
        session=session,
        config=config,
        messages=[
            {"role": "system", "content": CORE_SUMMARY_REVIEW_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"time_ordered_summary:\n<<<\n{event_summary_text}\n>>>\n\n"
                    f"candidate_core_summary:\n<<<\n{core_summary}\n>>>"
                ),
            },
        ],
    )
    stats.record_success(latency_seconds)
    stats.row_count += 1


def _run_worker(
    *,
    worker_id: int,
    rows: list[SummarySourceRow],
    config: OpenWebUIRequestConfig,
    deadline: float,
    stop_event: threading.Event,
    max_consecutive_failures: int,
) -> WorkerStats:
    """할당된 row를 순환하며 종료 시각까지 고정 동시성을 유지합니다."""

    stats = WorkerStats()
    consecutive_failures = 0
    with requests.Session() as session:
        for row in itertools.cycle(rows):
            if stop_event.is_set() or time.monotonic() >= deadline:
                break
            request_started_at = time.monotonic()
            try:
                _request_row_summary(session=session, config=config, row=row, stats=stats)
                consecutive_failures = 0
            except OpenWebUIRequestError as exc:
                stats.record_failure(time.monotonic() - request_started_at)
                consecutive_failures += 1
                logger.warning(
                    "OpenWebUI 연속 요약 요청 실패: worker=%s, consecutive_failures=%s, reason=%s",
                    worker_id,
                    consecutive_failures,
                    exc,
                )
                if consecutive_failures >= max_consecutive_failures:
                    stop_event.set()
                    raise RuntimeError(
                        f"worker {worker_id}에서 연속 실패 {consecutive_failures}회가 발생했습니다."
                    ) from exc
    return stats


def run_ct_process_comment_openwebui_continuous_summary(**context: Any) -> dict[str, Any]:
    """ct_process_comment 기반 OpenWebUI 연속 요약을 실행합니다."""

    params = context["params"]
    concurrency = int(params["concurrency"])
    duration_minutes = int(params["duration_minutes"])
    row_limit = int(params["row_limit"])
    max_consecutive_failures = int(params["max_consecutive_failures"])

    config = _read_openwebui_config()
    rows = _read_summary_rows(row_limit=row_limit)
    if not rows:
        raise ValueError("연속 요약에 사용할 ct_process_comment row가 없습니다.")

    worker_rows = [rows[worker_id::concurrency] or rows for worker_id in range(concurrency)]
    stop_event = threading.Event()
    deadline = time.monotonic() + duration_minutes * 60
    logger.info(
        "OpenWebUI 연속 요약을 시작합니다: concurrency=%s, duration_minutes=%s, row_count=%s",
        concurrency,
        duration_minutes,
        len(rows),
    )

    stats_by_worker: list[WorkerStats] = []
    worker_errors: list[str] = []
    with ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="ct-process-load") as executor:
        futures = [
            executor.submit(
                _run_worker,
                worker_id=worker_id,
                rows=worker_rows[worker_id],
                config=config,
                deadline=deadline,
                stop_event=stop_event,
                max_consecutive_failures=max_consecutive_failures,
            )
            for worker_id in range(concurrency)
        ]
        for future in as_completed(futures):
            try:
                stats_by_worker.append(future.result())
            except Exception as exc:
                stop_event.set()
                worker_errors.append(str(exc))

    total_rows = sum(stats.row_count for stats in stats_by_worker)
    total_requests = sum(stats.request_count for stats in stats_by_worker)
    total_failures = sum(stats.failure_count for stats in stats_by_worker)
    total_latency = sum(stats.total_latency_seconds for stats in stats_by_worker)
    max_latency = max((stats.max_latency_seconds for stats in stats_by_worker), default=0.0)
    summary = {
        "concurrency": concurrency,
        "duration_minutes": duration_minutes,
        "source_row_count": len(rows),
        "completed_row_count": total_rows,
        "request_count": total_requests,
        "failure_count": total_failures,
        "average_latency_seconds": round(total_latency / total_requests, 3) if total_requests else 0.0,
        "max_latency_seconds": round(max_latency, 3),
    }
    logger.info("OpenWebUI 연속 요약을 종료합니다: %s", summary)
    if worker_errors:
        raise RuntimeError(f"OpenWebUI 연속 요약 worker 실패: {worker_errors[:3]}")
    return summary


with DAG(
    dag_id="ct_process_comment_openwebui_continuous_summary",
    description="ct_process_comment 실제 입력으로 OpenWebUI 연속 요약을 실행합니다.",
    schedule="@continuous",
    start_date=days_ago(1),
    catchup=False,
    max_active_runs=1,
    is_paused_upon_creation=True,
    default_args={"owner": "data-movement", "retries": 0},
    params={
        "concurrency": Param(3, type="integer", minimum=1, maximum=64),
        "duration_minutes": Param(360, type="integer", minimum=1, maximum=10080),
        "row_limit": Param(300, type="integer", minimum=1, maximum=10000),
        "max_consecutive_failures": Param(5, type="integer", minimum=1, maximum=100),
    },
    tags=["data_movement", "openwebui", "summary"],
    doc_md="""
### ct_process_comment OpenWebUI

- `ct_process_comment_summary_db`: PostgreSQL host, port, database, login, password
- `openwebui_continuous_summary`: password에 API token, Extra에 아래 JSON 입력

```json
{
  "endpoint": "https://openwebui.example/api/chat/completions",
  "model": "model-name",
  "headers": {},
  "timeout_seconds": 120
}
```

기본값은 동시성 3, 6시간이며 DAG 실행 설정에서 변경할 수 있습니다.
실행 중 GPU 상태는 LLM 서버 Grafana에서 확인합니다.
DAG를 활성화하면 이전 실행의 성공 여부와 관계없이 종료 직후 다음 실행을 시작합니다.
DAG를 일시중지하면 새로운 실행이 생성되지 않습니다.
""",
) as dag:
    PythonOperator(
        task_id="run_continuous_summary",
        python_callable=run_ct_process_comment_openwebui_continuous_summary,
    )
