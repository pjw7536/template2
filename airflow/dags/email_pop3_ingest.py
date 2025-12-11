from __future__ import annotations

import os
from datetime import timedelta

import requests
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago

EMAIL_INGEST_TRIGGER_URL = os.getenv("EMAIL_INGEST_TRIGGER_URL") or ""
EMAIL_INGEST_TRIGGER_TOKEN = os.getenv("EMAIL_INGEST_TRIGGER_TOKEN") or ""
EMAIL_INGEST_HTTP_TIMEOUT = int(os.getenv("EMAIL_INGEST_HTTP_TIMEOUT") or "60")
EMAIL_INGEST_SCHEDULE = os.getenv("EMAIL_INGEST_SCHEDULE") or None


def run_email_ingest(**_context):
    if not EMAIL_INGEST_TRIGGER_URL:
        raise ValueError("EMAIL_INGEST_TRIGGER_URL is not set")

    headers = {"Accept": "application/json"}
    if EMAIL_INGEST_TRIGGER_TOKEN:
        headers["Authorization"] = f"Bearer {EMAIL_INGEST_TRIGGER_TOKEN}"

    response = requests.post(
        EMAIL_INGEST_TRIGGER_URL,
        headers=headers,
        timeout=EMAIL_INGEST_HTTP_TIMEOUT,
    )
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
    dag_id="email_pop3_ingest",
    default_args=default_args,
    schedule=EMAIL_INGEST_SCHEDULE,
    start_date=days_ago(1),
    catchup=False,
    max_active_runs=1,
    tags=["email", "rag", "pop3"],
) as dag:
    ingest_pop3 = PythonOperator(
        task_id="ingest_pop3_emails",
        python_callable=run_email_ingest,
    )
