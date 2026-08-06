from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import requests
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago

from failure_alerts import notify_airflow_task_failure

logger = logging.getLogger(__name__)

AIRFLOW_API_BASE_URL = (os.getenv("AIRFLOW_API_BASE_URL") or "http://api:8000").strip().rstrip("/")
AIRFLOW_TRIGGER_TOKEN = os.getenv("AIRFLOW_TRIGGER_TOKEN") or ""
ERROR_RESPONSE_PREVIEW_MAX_CHARS = 20000
FAILURE_ERROR_GROUP_LIMIT = 2
FAILURE_ERROR_PREVIEW_MAX_CHARS = 8000
FAILURE_WORKORDER_SAMPLE_LIMIT = 5


def _parse_optional_int(value: Any) -> int | None:
    """환경 변수 값을 양의 정수 옵션으로 변환합니다."""

    if value in (None, ""):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _parse_bool(value: Any) -> bool:
    """환경 변수 값을 boolean 옵션으로 변환합니다."""

    if value in (None, ""):
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _build_failure_group_key(error_message: str) -> str:
    """응답 ID가 달라도 같은 원인과 stage의 실패를 한 그룹으로 묶습니다."""

    reason = error_message.split(". ", 1)[0].strip() or "<missing-error-message>"
    stages = sorted(set(re.findall(r"\bstage=([a-z_]+)", error_message)))
    stage_label = ",".join(stages) if stages else "unknown"
    return f"{reason[:240]}|stage={stage_label}"


def _summarize_failed_outcomes(outcomes: list[Any]) -> dict[str, Any]:
    """반복 실패를 원인별 건수와 대표 진단으로 압축합니다."""

    grouped: dict[str, dict[str, Any]] = {}
    failed_outcome_count = 0
    for outcome in outcomes:
        if not isinstance(outcome, dict):
            continue
        if outcome.get("status") != "failed" and not outcome.get("error_message"):
            continue

        failed_outcome_count += 1
        raw_error_message = outcome.get("error_message")
        error_message = (
            raw_error_message if isinstance(raw_error_message, str) else "<missing-error-message>"
        )
        group_key = _build_failure_group_key(error_message)
        group = grouped.setdefault(
            group_key,
            {
                "failure_count": 0,
                "sample_workorder_ids": [],
                "representative_error": error_message[:FAILURE_ERROR_PREVIEW_MAX_CHARS],
            },
        )
        group["failure_count"] += 1

        workorder_id = outcome.get("workorder_id")
        sample_workorder_ids = group["sample_workorder_ids"]
        if (
            isinstance(workorder_id, str)
            and workorder_id
            and len(sample_workorder_ids) < FAILURE_WORKORDER_SAMPLE_LIMIT
        ):
            sample_workorder_ids.append(workorder_id)

    failure_groups = list(grouped.values())
    visible_groups = failure_groups[:FAILURE_ERROR_GROUP_LIMIT]
    return {
        "failed_outcome_count": failed_outcome_count,
        "failure_group_count": len(failure_groups),
        "failure_groups": visible_groups,
        "omitted_failure_group_count": max(0, len(failure_groups) - len(visible_groups)),
    }


def _format_error_response(response: requests.Response) -> str:
    """API 실패 응답에서 운영 분석에 필요한 정보만 문자열로 변환합니다."""

    try:
        payload = response.json()
    except ValueError:
        response_text = response.text.strip() or "<empty>"
        return response_text[:ERROR_RESPONSE_PREVIEW_MAX_CHARS]

    if not isinstance(payload, dict):
        return json.dumps(payload, ensure_ascii=False, default=str)[:ERROR_RESPONSE_PREVIEW_MAX_CHARS]

    error_detail = {
        key: payload[key]
        for key in ("error", "table_name", "processed_count", "success_count", "failure_count")
        if key in payload
    }
    outcomes = payload.get("outcomes")
    if isinstance(outcomes, list):
        failure_summary = _summarize_failed_outcomes(outcomes)
        if failure_summary["failed_outcome_count"]:
            error_detail.update(failure_summary)

    detail_payload = error_detail or payload
    detail_text = json.dumps(detail_payload, ensure_ascii=False, default=str)
    if len(detail_text) <= ERROR_RESPONSE_PREVIEW_MAX_CHARS:
        return detail_text
    omitted_chars = len(detail_text) - ERROR_RESPONSE_PREVIEW_MAX_CHARS
    return f"{detail_text[:ERROR_RESPONSE_PREVIEW_MAX_CHARS]}...<truncated_chars={omitted_chars}>"


def _raise_for_status_with_detail(response: requests.Response) -> None:
    """HTTP 오류 상태와 API 실패 상세를 Airflow task log에 남깁니다."""

    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        error_message = (
            "ct_process_comment 요약 API 호출 실패: "
            f"status={response.status_code}, url={response.url}, detail={_format_error_response(response)}"
        )
        logger.error(error_message)
        raise RuntimeError(error_message) from exc


def run_ct_process_comment_summary(**_context):
    """ct_process_comment OpenWebUI 요약 API를 호출합니다."""

    if not AIRFLOW_API_BASE_URL:
        raise ValueError("AIRFLOW_API_BASE_URL is not set")
    if not AIRFLOW_TRIGGER_TOKEN:
        raise ValueError("AIRFLOW_TRIGGER_TOKEN is not set")

    payload: dict[str, object] = {}
    limit = _parse_optional_int(os.getenv("DATA_MOVEMENT_CT_PROCESS_COMMENT_SUMMARY_LIMIT"))
    if limit is not None:
        payload["limit"] = limit
    if _parse_bool(os.getenv("DATA_MOVEMENT_CT_PROCESS_COMMENT_SUMMARY_DRY_RUN")):
        payload["dry_run"] = True

    response = requests.post(
        f"{AIRFLOW_API_BASE_URL}/api/v1/data-movement/ct_process_comment/summarize/",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {AIRFLOW_TRIGGER_TOKEN}",
            "X-Forwarded-Proto": "https",
        },
        json=payload or None,
        timeout=1800,
    )
    _raise_for_status_with_detail(response)

    try:
        return response.json()
    except ValueError:
        return {"status_code": response.status_code}


default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "on_failure_callback": notify_airflow_task_failure,
}

with DAG(
    dag_id="ct_process_comment_summary",
    default_args=default_args,
    # 1분에 한 번 실행합니다.
    schedule="*/1 * * * *",
    start_date=days_ago(1),
    catchup=False,
    max_active_runs=1,
    tags=["data_movement", "summary"],
) as dag:
    summarize_ct_process_comment = PythonOperator(
        task_id="summarize_ct_process_comment",
        python_callable=run_ct_process_comment_summary,
    )
