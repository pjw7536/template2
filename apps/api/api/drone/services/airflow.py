# =============================================================================
# 모듈: Line Dashboard Airflow 조회 client
# 주요 기능: DAG 목록과 최근 실행을 Airflow REST API에서 조회·정규화
# 핵심 전제: Airflow Basic Auth credential은 API 서버 환경변수에만 보관합니다.
# =============================================================================
"""Line Dashboard가 사용할 Airflow DAG overview를 서버에서 구성합니다."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

AIRFLOW_DAG_LIMIT = 200
AIRFLOW_LATEST_RUN_WORKERS = 8


class AirflowOverviewError(RuntimeError):
    """Airflow overview 조회 실패의 공통 예외입니다."""


class AirflowConfigurationError(AirflowOverviewError):
    """필수 Airflow 서버 설정이 누락된 경우 발생합니다."""


class AirflowUpstreamError(AirflowOverviewError):
    """Airflow REST API 호출 또는 응답 검증에 실패한 경우 발생합니다."""


def _required_setting(name: str) -> str:
    """문자열 설정을 정규화하고 비어 있으면 설정 오류를 발생시킵니다."""

    value = getattr(settings, name, "")
    normalized = str(value or "").strip()
    if not normalized:
        raise AirflowConfigurationError(f"{name} 설정이 필요합니다.")
    return normalized


def _request_json(url: str, *, params: dict[str, object] | None = None) -> dict[str, Any]:
    """서버에 보관된 Basic Auth로 Airflow JSON object를 조회합니다.

    인자:
        url: 호출할 Airflow REST API URL.
        params: 선택 query parameter.

    반환:
        JSON object 응답.

    부작용:
        Airflow 서버로 HTTP GET 요청을 전송합니다.

    오류:
        AirflowConfigurationError: URL 또는 credential이 비어 있는 경우.
        AirflowUpstreamError: 네트워크, HTTP status, JSON 형태가 잘못된 경우.
    """

    username = _required_setting("AIRFLOW_USERNAME")
    password = _required_setting("AIRFLOW_PASSWORD")
    timeout = int(getattr(settings, "AIRFLOW_REQUEST_TIMEOUT_SECONDS", 10) or 10)

    try:
        response = requests.get(
            url,
            params=params,
            auth=(username, password),
            headers={"Accept": "application/json"},
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise AirflowUpstreamError("Airflow API에 연결할 수 없습니다.") from exc

    try:
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise AirflowUpstreamError("Airflow API 응답을 처리할 수 없습니다.") from exc
    finally:
        response.close()

    if not isinstance(payload, dict):
        raise AirflowUpstreamError("Airflow API 응답은 JSON object여야 합니다.")
    return payload


def _normalize_tags(raw_tags: object) -> list[str]:
    """Airflow tag 목록을 문자열 목록으로 정규화합니다."""

    if not isinstance(raw_tags, list):
        return []
    normalized: list[str] = []
    for tag in raw_tags:
        if isinstance(tag, str):
            normalized.append(tag)
        elif isinstance(tag, dict) and isinstance(tag.get("name"), str):
            normalized.append(tag["name"])
    return normalized


def _normalize_owners(raw_owners: object) -> list[str]:
    """Airflow owner 목록에서 문자열만 반환합니다."""

    if not isinstance(raw_owners, list):
        return []
    return [owner for owner in raw_owners if isinstance(owner, str)]


def _timetable_description(dag: dict[str, Any]) -> str:
    """Airflow timetable 또는 schedule interval을 표시 문자열로 변환합니다."""

    description = dag.get("timetable_description")
    if isinstance(description, str) and description:
        return description

    interval = dag.get("schedule_interval")
    if isinstance(interval, str):
        return interval
    if not isinstance(interval, dict):
        return ""

    interval_type = interval.get("__type") or interval.get("type")
    value = interval.get("value") or interval.get("days") or interval.get("seconds")
    if interval_type and value:
        return f"{interval_type} ({value})"
    return str(value) if value else ""


def _fetch_latest_run(base_url: str, dag_id: str) -> dict[str, Any] | None:
    """단일 DAG의 최근 실행을 조회하며 실패를 해당 DAG에만 격리합니다."""

    encoded_dag_id = quote(dag_id, safe="")
    try:
        payload = _request_json(
            f"{base_url}/api/v1/dags/{encoded_dag_id}/dagRuns",
            params={"limit": 1, "order_by": "-execution_date"},
        )
    except AirflowOverviewError:
        logger.warning("Airflow 최근 DAG 실행 조회에 실패했습니다: dag_id=%s", dag_id)
        return None

    raw_runs = payload.get("dag_runs")
    if not isinstance(raw_runs, list) or not raw_runs or not isinstance(raw_runs[0], dict):
        return None
    latest = raw_runs[0]
    return {
        "runId": latest.get("dag_run_id"),
        "state": latest.get("state"),
        "executionDate": latest.get("execution_date"),
        "startDate": latest.get("start_date"),
        "endDate": latest.get("end_date"),
    }


def _normalize_dag(dag: dict[str, Any], latest_run: dict[str, Any] | None) -> dict[str, Any]:
    """Airflow DAG object를 기존 Web overview 계약으로 변환합니다."""

    is_paused = bool(dag.get("is_paused"))
    raw_is_active = dag.get("is_active")
    is_active = bool(raw_is_active) if raw_is_active is not None else not is_paused
    return {
        "dagId": str(dag.get("dag_id") or ""),
        "description": str(dag.get("description") or ""),
        "isPaused": is_paused,
        "isActive": is_active,
        "owners": _normalize_owners(dag.get("owners")),
        "tags": _normalize_tags(dag.get("tags")),
        "timetable": _timetable_description(dag),
        "nextRun": dag.get("next_dagrun"),
        "nextRunCreateAfter": dag.get("next_dagrun_create_after"),
        "latestRun": latest_run,
    }


def get_airflow_dag_overview() -> dict[str, Any]:
    """Airflow DAG 목록과 최근 실행을 조회해 Line Dashboard payload를 반환합니다.

    반환:
        기존 Web 계약과 같은 ``baseUrl``, ``fetchedAt``, ``totals``, ``dags`` object.

    부작용:
        Airflow REST API를 호출합니다.

    오류:
        AirflowConfigurationError: 필수 설정이 없는 경우.
        AirflowUpstreamError: DAG 목록 조회가 실패한 경우.
    """

    base_url = _required_setting("AIRFLOW_BASE_URL").rstrip("/")
    public_base_url = str(
        getattr(settings, "AIRFLOW_PUBLIC_BASE_URL", "/airflow") or "/airflow"
    ).rstrip("/")
    payload = _request_json(
        f"{base_url}/api/v1/dags",
        params={"limit": AIRFLOW_DAG_LIMIT},
    )
    raw_dag_payload = payload.get("dags")
    raw_dags = (
        [dag for dag in raw_dag_payload if isinstance(dag, dict)]
        if isinstance(raw_dag_payload, list)
        else []
    )
    dag_ids = [str(dag.get("dag_id") or "") for dag in raw_dags]

    latest_runs: list[dict[str, Any] | None] = [None] * len(raw_dags)
    nonempty_dag_ids = [(index, dag_id) for index, dag_id in enumerate(dag_ids) if dag_id]
    if nonempty_dag_ids:
        worker_count = min(AIRFLOW_LATEST_RUN_WORKERS, len(nonempty_dag_ids))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                index: executor.submit(_fetch_latest_run, base_url, dag_id)
                for index, dag_id in nonempty_dag_ids
            }
            for index, future in futures.items():
                latest_runs[index] = future.result()

    dags = [
        _normalize_dag(dag, latest_runs[index])
        for index, dag in enumerate(raw_dags)
    ]
    totals = {
        "total": len(dags),
        "active": sum(1 for dag in dags if dag["isActive"] and not dag["isPaused"]),
        "paused": sum(1 for dag in dags if dag["isPaused"]),
        "failed": sum(
            1
            for dag in dags
            if str((dag.get("latestRun") or {}).get("state") or "").lower() == "failed"
        ),
    }
    fetched_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "baseUrl": public_base_url or "/airflow",
        "fetchedAt": fetched_at,
        "totals": totals,
        "dags": dags,
    }


__all__ = [
    "AirflowConfigurationError",
    "AirflowOverviewError",
    "AirflowUpstreamError",
    "get_airflow_dag_overview",
]
