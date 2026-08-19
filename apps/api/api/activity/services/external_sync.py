# =============================================================================
# 모듈 설명: 외부 앱 사용량 API 동기화와 저장을 담당합니다.
# - 불변 조건: 설정된 sourceName별 결과와 동기화 상태를 함께 보존합니다.
# =============================================================================
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from api.common.services import ExternalHttpError, request_external

from ..models import ExternalAppAccessDailyStat, ExternalAppUsageSyncState
from ._shared import KST, normalize_app_name, safe_text, serialize_date, serialize_datetime

EXTERNAL_USAGE_SOURCE_TYPE = "external_api"
EXTERNAL_USAGE_SYNC_KEY = "external_app_usage"
EXTERNAL_USAGE_SYNC_THROTTLE = timedelta(hours=6)
EXTERNAL_USAGE_SYNC_LOOKBACK_DAYS = 365


def _normalize_external_usage_source_name(value: Any) -> str:
    """외부 사용량 API sourceName을 정규화합니다."""

    if not isinstance(value, str):
        return ""
    return value.strip()[:80]


def _read_external_usage_api_config() -> tuple[list[dict[str, str]], int, str | None]:
    """외부 앱 사용량 API 설정을 Django settings에서 읽습니다."""

    urls_raw = getattr(settings, "EXTERNAL_APP_USAGE_API_URLS", "") or ""
    timeout = getattr(settings, "EXTERNAL_APP_USAGE_API_TIMEOUT_SECONDS", 10) or 10
    try:
        timeout_seconds = int(timeout)
    except (TypeError, ValueError):
        timeout_seconds = 10

    if str(urls_raw).strip():
        try:
            parsed = json.loads(str(urls_raw))
        except ValueError as exc:
            return [], max(timeout_seconds, 1), f"EXTERNAL_APP_USAGE_API_URLS JSON 형식이 올바르지 않습니다: {exc}"
        if not isinstance(parsed, list):
            return [], max(timeout_seconds, 1), "EXTERNAL_APP_USAGE_API_URLS는 JSON 배열이어야 합니다."

        sources: list[dict[str, str]] = []
        for index, item in enumerate(parsed, start=1):
            if not isinstance(item, dict):
                return [], max(timeout_seconds, 1), f"EXTERNAL_APP_USAGE_API_URLS[{index}]는 객체여야 합니다."
            source_name = _normalize_external_usage_source_name(item.get("sourceName"))
            url = str(item.get("url") or "").strip()
            if not source_name or not url:
                return [], max(timeout_seconds, 1), f"EXTERNAL_APP_USAGE_API_URLS[{index}]에는 sourceName과 url이 필요합니다."
            sources.append({"sourceName": source_name, "url": url})
        return sources, max(timeout_seconds, 1), None

    return [], max(timeout_seconds, 1), None


def normalize_app_name(value: Any) -> str:
    """외부 사용량 row의 앱 이름을 정규화합니다."""

    if not isinstance(value, str):
        return ""
    return value.strip().upper()[:120]


def _parse_external_usage_date(value: Any) -> date | None:
    """외부 사용량 row의 날짜 값을 date로 변환합니다."""

    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


def _parse_external_usage_access_count(value: Any) -> int | None:
    """외부 사용량 row의 accessCount 값을 0 이상의 정수로 변환합니다."""

    if isinstance(value, bool) or value is None:
        return None
    try:
        parsed = int(str(value).replace(",", "").strip())
    except ValueError:
        return None
    if parsed < 0:
        return None
    return parsed


def _normalize_external_usage_rows(
    *,
    payload: Any,
    from_date: date,
    to_date: date,
    app_id: str | None,
    source_name: str,
) -> tuple[list[dict[str, Any]], int]:
    """외부 사용량 API 응답을 기존 통계 집계 row 형태로 정규화합니다."""

    if not isinstance(payload, list):
        raise ValueError("External usage API response must be a list")

    rows: list[dict[str, Any]] = []
    skipped_count = 0
    for raw_row in payload:
        if not isinstance(raw_row, dict):
            skipped_count += 1
            continue

        app_name = normalize_app_name(raw_row.get("appName"))
        stat_date = _parse_external_usage_date(raw_row.get("date"))
        access_count = _parse_external_usage_access_count(raw_row.get("accessCount"))
        app_key = app_name
        if not app_name or stat_date is None or access_count is None:
            skipped_count += 1
            continue
        if stat_date < from_date or stat_date > to_date:
            continue
        if app_id and app_key != app_id:
            continue

        rows.append(
            {
                "app_id": app_key,
                "app_name": app_name,
                "stat_date": stat_date,
                "access_count": access_count,
                "unique_user_count": 0,
                "source_type": EXTERNAL_USAGE_SOURCE_TYPE,
                "source_name": source_name,
            }
        )

    return rows, skipped_count


def _load_external_usage_rows(
    *,
    from_date: date,
    to_date: date,
    app_id: str | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """외부 사용량 API에서 앱별 사용량 row를 가져옵니다."""

    sources, timeout_seconds, config_error = _read_external_usage_api_config()
    status = {
        "enabled": bool(sources),
        "rowCount": 0,
        "skippedRows": 0,
        "error": None,
        "sources": [],
    }
    if config_error:
        status["error"] = config_error
        return [], status
    if not sources:
        return [], status

    all_rows: list[dict[str, Any]] = []
    source_errors = 0
    source_successes = 0
    for source in sources:
        source_status = {
            "sourceName": source["sourceName"],
            "rowCount": 0,
            "skippedRows": 0,
            "error": None,
        }
        try:
            response = request_external(
                requests.get,
                source["url"],
                timeout=timeout_seconds,
                verify=False,
                raise_for_status=True,
            )
            rows, skipped_count = _normalize_external_usage_rows(
                payload=response.json(),
                from_date=from_date,
                to_date=to_date,
                app_id=app_id,
                source_name=source["sourceName"],
            )
        except (ExternalHttpError, ValueError) as exc:
            source_status["error"] = f"외부 사용량 API 요청에 실패했습니다: {exc}"
            source_errors += 1
        else:
            source_successes += 1
            source_status["rowCount"] = len(rows)
            source_status["skippedRows"] = skipped_count
            all_rows.extend(rows)
        status["sources"].append(source_status)

    status["rowCount"] = sum(source["rowCount"] for source in status["sources"])
    status["skippedRows"] = sum(source["skippedRows"] for source in status["sources"])
    if source_errors and not source_successes:
        status["error"] = "외부 사용량 API 요청에 실패해 외부 API 통계를 제외했습니다."
        status["rowCount"] = 0
        status["skippedRows"] = 0
        return [], status
    return all_rows, status


def _get_external_usage_sync_window(now: datetime) -> tuple[date, date]:
    """수동 동기화 대상 날짜 범위를 계산합니다."""

    today_kst = now.astimezone(KST).date()
    return today_kst - timedelta(days=EXTERNAL_USAGE_SYNC_LOOKBACK_DAYS), today_kst


def _serialize_external_usage_sync_state(state: ExternalAppUsageSyncState | None) -> dict[str, Any]:
    """외부 API 동기화 상태를 응답 payload 형태로 변환합니다."""

    last_synced_at = state.last_synced_at if state else None
    last_attempted_at = state.updated_at if state else None
    next_sync_available_at = (
        last_attempted_at + EXTERNAL_USAGE_SYNC_THROTTLE if last_attempted_at is not None else None
    )
    return {
        "syncKey": EXTERNAL_USAGE_SYNC_KEY,
        "lastSyncedAt": serialize_datetime(last_synced_at),
        "lastAttemptedAt": serialize_datetime(last_attempted_at),
        "nextSyncAvailableAt": serialize_datetime(next_sync_available_at),
        "lastStatus": state.last_status if state else "never",
        "lastError": state.last_error if state else "",
    }


def _is_external_usage_sync_throttled(
    *,
    state: ExternalAppUsageSyncState,
    now: datetime,
) -> bool:
    """마지막 동기화 시도 후 6시간이 지나지 않았는지 확인합니다."""

    if state.updated_at is None:
        return False
    return now - state.updated_at < EXTERNAL_USAGE_SYNC_THROTTLE


def _upsert_external_usage_rows(
    *,
    rows: list[dict[str, Any]],
    user: Any | None,
) -> dict[str, int]:
    """외부 API row를 일별 집계 테이블에 저장합니다."""

    created_count = 0
    updated_count = 0
    with transaction.atomic():
        for row in rows:
            _, created = ExternalAppAccessDailyStat.objects.update_or_create(
                app_id=safe_text(row.get("app_id"), "unknown"),
                stat_date=row["stat_date"],
                source_name=safe_text(row.get("source_name"), EXTERNAL_USAGE_SOURCE_TYPE),
                defaults={
                    "app_name": safe_text(row.get("app_name"), safe_text(row.get("app_id"), "unknown")),
                    "access_count": int(row.get("access_count") or 0),
                    "unique_user_count": int(row.get("unique_user_count") or 0),
                    "source_type": EXTERNAL_USAGE_SOURCE_TYPE,
                    "memo": "외부 API 수동 동기화",
                    "raw_payload": {
                        **row,
                        "stat_date": serialize_date(row.get("stat_date")),
                    },
                    "updated_by": user if getattr(user, "is_authenticated", False) else None,
                    "created_by": user if getattr(user, "is_authenticated", False) else None,
                },
            )
            if created:
                created_count += 1
            else:
                updated_count += 1
    return {"createdRows": created_count, "updatedRows": updated_count}


def sync_external_app_usage_stats(
    *,
    user: Any | None = None,
    now: datetime | None = None,
    bypass_throttle: bool = False,
) -> dict[str, Any]:
    """외부 앱 사용량 API를 수동 동기화합니다.

    입력:
    - user: 동기화 요청 사용자
    - now: 테스트용 현재 시각
    - bypass_throttle: 관리자 요청의 6시간 제한 우회 여부

    반환:
    - dict[str, Any]: 동기화 결과와 마지막 상태

    부작용:
    - 외부 API를 호출하고 ExternalAppAccessDailyStat/ExternalAppUsageSyncState를 갱신합니다.

    오류:
    - 없음. 실패 정보는 payload의 error/status에 담습니다.
    """

    current = now or timezone.now()
    with transaction.atomic():
        state, created = ExternalAppUsageSyncState.objects.select_for_update().get_or_create(
            sync_key=EXTERNAL_USAGE_SYNC_KEY,
            defaults={"last_status": "never"},
        )
        if (
            not created
            and not bypass_throttle
            and _is_external_usage_sync_throttled(state=state, now=current)
        ):
            return {
                "synced": False,
                "skipped": True,
                "reason": "최근 6시간 내 외부 API 동기화 이력이 있습니다.",
                "syncState": _serialize_external_usage_sync_state(state),
                "commit": {"createdRows": 0, "updatedRows": 0},
            }
        state.last_status = "running"
        state.last_error = ""
        state.save(update_fields=["last_status", "last_error", "updated_at"])

    from_date, to_date = _get_external_usage_sync_window(current)
    rows, status = _load_external_usage_rows(from_date=from_date, to_date=to_date, app_id=None)
    if status.get("error"):
        with transaction.atomic():
            state = ExternalAppUsageSyncState.objects.select_for_update().get(sync_key=EXTERNAL_USAGE_SYNC_KEY)
            state.last_status = "failed"
            state.last_error = str(status["error"])
            state.save(update_fields=["last_status", "last_error", "updated_at"])
        return {
            "synced": False,
            "skipped": False,
            "reason": str(status["error"]),
            "syncState": _serialize_external_usage_sync_state(state),
            "externalUsage": status,
            "commit": {"createdRows": 0, "updatedRows": 0},
        }

    commit = _upsert_external_usage_rows(rows=rows, user=user)
    with transaction.atomic():
        state = ExternalAppUsageSyncState.objects.select_for_update().get(sync_key=EXTERNAL_USAGE_SYNC_KEY)
        state.last_synced_at = current
        state.last_status = "success"
        state.last_error = ""
        state.save(update_fields=["last_synced_at", "last_status", "last_error", "updated_at"])

    return {
        "synced": True,
        "skipped": False,
        "reason": "",
        "syncState": _serialize_external_usage_sync_state(state),
        "externalUsage": status,
        "commit": commit,
    }
