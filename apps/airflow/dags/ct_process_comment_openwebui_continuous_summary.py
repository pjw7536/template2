"""ct_process_comment 요약 API를 연속 호출하는 Airflow DAG입니다."""

from __future__ import annotations

import os
import time
from typing import Any

import requests
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago

from failure_alerts import notify_airflow_task_failure


AIRFLOW_API_BASE_URL = (os.getenv("AIRFLOW_API_BASE_URL") or "http://api:8000").strip().rstrip("/")
AIRFLOW_TRIGGER_TOKEN = os.getenv("AIRFLOW_TRIGGER_TOKEN") or ""


def _positive_int_env(name: str, default: int) -> int:
    """양의 정수 환경 설정을 읽고 잘못된 값은 기본값으로 대체합니다."""

    try:
        parsed = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _request_summary_batch(*, limit: int) -> dict[str, Any]:
    """Django가 소유하는 summary endpoint에서 한 batch를 처리합니다."""

    if not AIRFLOW_TRIGGER_TOKEN:
        raise ValueError("AIRFLOW_TRIGGER_TOKEN is not set")
    response = requests.post(
        f"{AIRFLOW_API_BASE_URL}/api/v1/data-movement/ct_process_comment/summarize/",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {AIRFLOW_TRIGGER_TOKEN}",
            "X-Forwarded-Proto": "https",
        },
        json={"limit": limit},
        timeout=1800,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("ct_process_comment 요약 API가 JSON object를 반환하지 않았습니다.")
    return payload


def run_ct_process_comment_openwebui_continuous_summary() -> dict[str, int]:
    """설정된 실행 시간 동안 pending summary batch를 API로 처리합니다."""

    duration_seconds = _positive_int_env(
        "DATA_MOVEMENT_CT_PROCESS_COMMENT_CONTINUOUS_DURATION_SECONDS",
        3600,
    )
    idle_interval_seconds = _positive_int_env(
        "DATA_MOVEMENT_CT_PROCESS_COMMENT_CONTINUOUS_IDLE_SECONDS",
        10,
    )
    limit = _positive_int_env("DATA_MOVEMENT_CT_PROCESS_COMMENT_SUMMARY_LIMIT", 100)
    deadline = time.monotonic() + duration_seconds
    batch_count = 0
    processed_count = 0
    failure_count = 0

    while time.monotonic() < deadline:
        payload = _request_summary_batch(limit=limit)
        batch_count += 1
        current_processed = int(payload.get("processedCount") or 0)
        processed_count += current_processed
        failure_count += int(payload.get("failureCount") or 0)
        if current_processed == 0:
            remaining_seconds = deadline - time.monotonic()
            if remaining_seconds <= 0:
                break
            time.sleep(min(idle_interval_seconds, remaining_seconds))

    return {
        "batchCount": batch_count,
        "processedCount": processed_count,
        "failureCount": failure_count,
    }


with DAG(
    dag_id="ct_process_comment_openwebui_continuous_summary",
    description="Django API를 통해 ct_process_comment pending 요약을 연속 처리합니다.",
    schedule="@continuous",
    start_date=days_ago(1),
    catchup=False,
    max_active_runs=1,
    is_paused_upon_creation=True,
    default_args={
        "owner": "data-movement",
        "retries": 0,
        "on_failure_callback": notify_airflow_task_failure,
    },
    tags=["data_movement", "openwebui", "summary"],
) as dag:
    PythonOperator(
        task_id="run_continuous_summary",
        python_callable=run_ct_process_comment_openwebui_continuous_summary,
    )
