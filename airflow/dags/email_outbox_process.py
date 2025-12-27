from __future__ import annotations

import os
from datetime import timedelta

import requests
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago

EMAIL_OUTBOX_PROCESS_TRIGGER_URL = os.getenv("EMAIL_OUTBOX_PROCESS_TRIGGER_URL") or ""
EMAIL_OUTBOX_PROCESS_TRIGGER_TOKEN = os.getenv("EMAIL_OUTBOX_PROCESS_TRIGGER_TOKEN") or ""
EMAIL_OUTBOX_PROCESS_HTTP_TIMEOUT = int(os.getenv("EMAIL_OUTBOX_PROCESS_HTTP_TIMEOUT") or "60")
EMAIL_OUTBOX_PROCESS_SCHEDULE = os.getenv("EMAIL_OUTBOX_PROCESS_SCHEDULE") or "*/5 * * * *"
EMAIL_OUTBOX_PROCESS_LIMIT = int(os.getenv("EMAIL_OUTBOX_PROCESS_LIMIT") or "1000")


def run_email_outbox_process(**_context):
    if not EMAIL_OUTBOX_PROCESS_TRIGGER_URL:
        raise ValueError("EMAIL_OUTBOX_PROCESS_TRIGGER_URL is not set")

    headers = {"Accept": "application/json"}
    if EMAIL_OUTBOX_PROCESS_TRIGGER_TOKEN:
        headers["Authorization"] = f"Bearer {EMAIL_OUTBOX_PROCESS_TRIGGER_TOKEN}"

    request_kwargs = {
        "url": EMAIL_OUTBOX_PROCESS_TRIGGER_URL,
        "headers": headers,
        "timeout": EMAIL_OUTBOX_PROCESS_HTTP_TIMEOUT,
    }
    if EMAIL_OUTBOX_PROCESS_LIMIT > 0:
        request_kwargs["json"] = {"limit": EMAIL_OUTBOX_PROCESS_LIMIT}

    response = requests.post(**request_kwargs)
    response.raise_for_status()

    try:
        return response.json()
    except ValueError:
        return {"status_code": response.status_code}


default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="email_outbox_process",
    default_args=default_args,
    schedule=EMAIL_OUTBOX_PROCESS_SCHEDULE,
    start_date=days_ago(1),
    catchup=False,
    max_active_runs=1,
    tags=["email", "rag", "outbox"],
) as dag:
    process_outbox = PythonOperator(
        task_id="process_email_outbox",
        python_callable=run_email_outbox_process,
    )
