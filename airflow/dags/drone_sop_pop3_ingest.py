from __future__ import annotations

import os
from datetime import timedelta

import requests
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago

DRONE_SOP_POP3_INGEST_TRIGGER_URL = os.getenv("DRONE_SOP_POP3_INGEST_TRIGGER_URL") or ""
DRONE_SOP_POP3_INGEST_TRIGGER_TOKEN = os.getenv("DRONE_SOP_POP3_INGEST_TRIGGER_TOKEN") or ""
DRONE_SOP_POP3_INGEST_HTTP_TIMEOUT = int(os.getenv("DRONE_SOP_POP3_INGEST_HTTP_TIMEOUT") or "60")
DRONE_SOP_POP3_INGEST_SCHEDULE = os.getenv("DRONE_SOP_POP3_INGEST_SCHEDULE") or None


def run_drone_sop_pop3_ingest(**_context):
    if not DRONE_SOP_POP3_INGEST_TRIGGER_URL:
        raise ValueError("DRONE_SOP_POP3_INGEST_TRIGGER_URL is not set")

    headers = {"Accept": "application/json"}
    if DRONE_SOP_POP3_INGEST_TRIGGER_TOKEN:
        headers["Authorization"] = f"Bearer {DRONE_SOP_POP3_INGEST_TRIGGER_TOKEN}"

    response = requests.post(
        DRONE_SOP_POP3_INGEST_TRIGGER_URL,
        headers=headers,
        timeout=DRONE_SOP_POP3_INGEST_HTTP_TIMEOUT,
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
    dag_id="drone_sop_pop3_ingest",
    default_args=default_args,
    schedule=DRONE_SOP_POP3_INGEST_SCHEDULE,
    start_date=days_ago(1),
    catchup=False,
    max_active_runs=1,
    tags=["drone", "sop", "pop3"],
) as dag:
    ingest_pop3 = PythonOperator(
        task_id="ingest_pop3_drone_sop",
        python_callable=run_drone_sop_pop3_ingest,
    )
