from __future__ import annotations

import json
import logging
import os
from typing import Any

import requests
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago

from failure_alerts import notify_airflow_task_failure

logger = logging.getLogger(__name__)

AIRFLOW_API_BASE_URL = (os.getenv("AIRFLOW_API_BASE_URL") or "http://api:8000").strip().rstrip("/")
AIRFLOW_TRIGGER_TOKEN = os.getenv("AIRFLOW_TRIGGER_TOKEN") or ""
ERROR_RESPONSE_PREVIEW_MAX_CHARS = 4000


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
        failed_outcomes = []
        for outcome in outcomes:
            if not isinstance(outcome, dict):
                continue
            if outcome.get("status") != "failed" and not outcome.get("error_message"):
                continue
            failed_outcomes.append(
                {
                    key: outcome[key]
                    for key in ("workorder_id", "status", "error_message")
                    if key in outcome
                }
            )
        if failed_outcomes:
            error_detail["failed_outcomes"] = failed_outcomes

    detail_payload = error_detail or payload
    return json.dumps(detail_payload, ensure_ascii=False, default=str)[:ERROR_RESPONSE_PREVIEW_MAX_CHARS]


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
