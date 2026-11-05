from __future__ import annotations

import os
from datetime import datetime, timezone

import requests
from airflow.sdk import DAG
from airflow.providers.standard.operators.python import PythonOperator

from failure_alerts import notify_airflow_task_failure

AIRFLOW_API_BASE_URL = (os.getenv("AIRFLOW_API_BASE_URL") or "http://api:8000").strip().rstrip("/")
AIRFLOW_TRIGGER_TOKEN = os.getenv("AIRFLOW_TRIGGER_TOKEN") or ""
EMAIL_INGEST_TRIGGER_URL = f"{AIRFLOW_API_BASE_URL}/api/v1/emails/ingest/"


def run_email_ingest(**_context):
    if not AIRFLOW_API_BASE_URL:
        raise ValueError("AIRFLOW_API_BASE_URL is not set")

    headers = {"Accept": "application/json", "X-Forwarded-Proto": "https"}
    if AIRFLOW_TRIGGER_TOKEN:
        headers["Authorization"] = f"Bearer {AIRFLOW_TRIGGER_TOKEN}"

    response = requests.post(
        EMAIL_INGEST_TRIGGER_URL,
        headers=headers,
        timeout=60,
    )
    response.raise_for_status()

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
    dag_id="email_pop3_ingest",
    default_args=default_args,
    # 1분에 한 번 실행합니다.
    schedule="*/1 * * * *",
    start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    tags=["email", "rag", "pop3"],
) as dag:
    ingest_pop3 = PythonOperator(
        task_id="ingest_pop3_emails",
        python_callable=run_email_ingest,
    )
