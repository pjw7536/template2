# =============================================================================
# 모듈 설명: Activity 조회 결과와 앱 접속 통계 집계를 생성합니다.
# - 불변 조건: 조회는 selector에 위임하고 이 모듈은 응답 조합만 수행합니다.
# =============================================================================
from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from ..selectors import (
    get_external_app_usage_sync_state,
    get_recent_activity_logs,
    summarize_external_app_access_by_app,
    summarize_external_app_access_by_date,
    summarize_external_app_access_totals,
    summarize_app_access_by_app,
    summarize_app_access_by_date,
    summarize_app_access_totals,
)
from ..serializers import serialize_activity_log
from ._shared import (
    KST,
    normalize_app_name,
    safe_text,
    serialize_date,
    serialize_datetime,
    serialize_kst_date_end,
)
from .external_sync import EXTERNAL_USAGE_SYNC_KEY, _serialize_external_usage_sync_state
from .manual_import import MANUAL_SOURCE_TYPE

DEFAULT_STATS_DAYS = 7
MAX_STATS_DAYS = 90
DEFAULT_STATS_PERIOD = "day"
ALLOWED_STATS_PERIODS = {"day", "week", "month"}


def _parse_iso_date(value: str | None, *, field_name: str) -> date | None:
    """YYYY-MM-DD 문자열을 date로 변환합니다."""

    if value is None or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValueError(f"{field_name} must be YYYY-MM-DD") from exc


def _resolve_stats_range(
    *,
    from_value: str | None,
    to_value: str | None,
    now: datetime | None = None,
) -> tuple[date, date, datetime, datetime]:
    """KST 날짜 범위를 UTC datetime boundary로 변환합니다."""

    current = now or datetime.now(tz=UTC)
    today_kst = current.astimezone(KST).date()
    to_date = _parse_iso_date(to_value, field_name="to") or today_kst
    from_date = _parse_iso_date(from_value, field_name="from") or (to_date - timedelta(days=DEFAULT_STATS_DAYS - 1))

    if from_date > to_date:
        raise ValueError("from must be earlier than or equal to to")

    if (to_date - from_date).days + 1 > MAX_STATS_DAYS:
        raise ValueError(f"date range must be {MAX_STATS_DAYS} days or less")

    start_local = datetime.combine(from_date, time.min, tzinfo=KST)
    end_local = datetime.combine(to_date + timedelta(days=1), time.min, tzinfo=KST)
    return from_date, to_date, start_local.astimezone(UTC), end_local.astimezone(UTC)


def _resolve_stats_period(value: str | None) -> str:
    """통계 집계 단위를 정규화합니다."""

    if value is None or not value.strip():
        return DEFAULT_STATS_PERIOD
    period = value.strip().lower()
    if period not in ALLOWED_STATS_PERIODS:
        raise ValueError("period must be one of day, week, month")
    return period


def _get_period_start(value: date, *, period: str) -> date:
    """날짜가 속한 집계 기간의 시작일을 반환합니다."""

    if period == "week":
        return value - timedelta(days=value.weekday())
    if period == "month":
        return value.replace(day=1)
    return value


def safe_text(value: Any, fallback: str) -> str:
    """집계 row의 문자열 값을 안전하게 반환합니다."""

    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def serialize_datetime(value: Any) -> str | None:
    """datetime 값을 ISO 문자열로 변환합니다."""

    if isinstance(value, datetime):
        return value.astimezone(KST).isoformat()
    return None


def serialize_date(value: Any) -> str:
    """date 값을 ISO 문자열로 변환합니다."""

    if isinstance(value, date):
        return value.isoformat()
    return ""


def serialize_kst_date_end(value: Any) -> str | None:
    """KST 날짜의 종료 시각을 ISO 문자열로 변환합니다."""

    if isinstance(value, date):
        return datetime.combine(value, time.max, tzinfo=KST).isoformat()
    return None


def _merge_source_labels(existing: set[str], value: str) -> str:
    """집계 row의 source label을 병합해 단일 표시값을 반환합니다."""

    existing.add(value)
    if len(existing) == 1:
        return next(iter(existing))
    return "mixed"


def _append_app_summary(
    *,
    merged: dict[str, dict[str, Any]],
    app_id: str,
    app_name: str,
    access_count: int,
    unique_user_count: int,
    last_accessed_at: str | None,
    source_type: str,
    source_name: str,
) -> None:
    """앱별 집계 row를 app_id 기준으로 누적합니다."""

    row = merged.setdefault(
        app_id,
        {
            "appId": app_id,
            "appName": app_name,
            "accessCount": 0,
            "uniqueUserCount": 0,
            "avgAccessPerUser": 0,
            "lastAccessedAt": None,
            "sourceType": source_type,
            "sourceName": source_name,
            "_sourceTypes": set(),
            "_sourceNames": set(),
        },
    )
    row["accessCount"] += access_count
    row["uniqueUserCount"] += unique_user_count
    row["sourceType"] = _merge_source_labels(row["_sourceTypes"], source_type)
    row["sourceName"] = _merge_source_labels(row["_sourceNames"], source_name)
    if last_accessed_at and (row["lastAccessedAt"] is None or last_accessed_at > row["lastAccessedAt"]):
        row["lastAccessedAt"] = last_accessed_at


def _finalize_app_summaries(merged: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """누적된 앱별 집계 row를 API 응답 형태로 정리합니다."""

    apps = []
    for row in merged.values():
        access_count = int(row["accessCount"] or 0)
        unique_user_count = int(row["uniqueUserCount"] or 0)
        row["avgAccessPerUser"] = round(access_count / unique_user_count, 1) if unique_user_count else 0
        row.pop("_sourceTypes", None)
        row.pop("_sourceNames", None)
        apps.append(row)
    return sorted(apps, key=lambda item: (-item["accessCount"], item["appName"], item["appId"]))


def _append_series_summary(
    *,
    merged: dict[tuple[str, str], dict[str, Any]],
    bucket_date: str,
    app_id: str,
    app_name: str,
    access_count: int,
    source_type: str,
    source_name: str,
) -> None:
    """날짜/앱별 집계 row를 누적합니다."""

    key = (bucket_date, app_id)
    row = merged.setdefault(
        key,
        {
            "date": bucket_date,
            "appId": app_id,
            "appName": app_name,
            "accessCount": 0,
            "sourceType": source_type,
            "sourceName": source_name,
            "_sourceTypes": set(),
            "_sourceNames": set(),
        },
    )
    row["accessCount"] += access_count
    row["sourceType"] = _merge_source_labels(row["_sourceTypes"], source_type)
    row["sourceName"] = _merge_source_labels(row["_sourceNames"], source_name)


def _finalize_series_summaries(merged: dict[tuple[str, str], dict[str, Any]]) -> list[dict[str, Any]]:
    """누적된 날짜/앱별 집계 row를 API 응답 형태로 정리합니다."""

    rows = []
    for row in merged.values():
        row.pop("_sourceTypes", None)
        row.pop("_sourceNames", None)
        rows.append(row)
    return sorted(rows, key=lambda item: (item["date"], item["appName"], item["appId"]))


def get_recent_activity_payload(*, limit: int) -> list[dict[str, Any]]:
    """최근 ActivityLog 목록을 직렬화해 반환합니다.

    입력:
    - limit: 최대 반환 개수

    반환:
    - list[dict[str, Any]]: 직렬화된 activity log 리스트

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    logs = get_recent_activity_logs(limit=limit)
    return [serialize_activity_log(entry) for entry in logs]


def get_app_access_stats_payload(
    *,
    from_value: str | None,
    to_value: str | None,
    app_id: str | None = None,
    period_value: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """앱별 접속 통계 payload를 생성합니다.

    입력:
    - from_value/to_value: KST 기준 YYYY-MM-DD 쿼리 문자열
    - app_id: 특정 앱 id 필터(선택)
    - period_value: chart series 집계 단위(day/week/month)
    - now: 테스트용 현재 시각(선택)

    반환:
    - dict[str, Any]: 대시보드 API 응답 payload

    부작용:
    - 없음(읽기 전용)

    오류:
    - ValueError: 날짜 형식/범위가 유효하지 않을 때
    """

    clean_app_id = app_id.strip() if isinstance(app_id, str) and app_id.strip() else None
    external_app_id = normalize_app_name(clean_app_id) if clean_app_id else None
    period = _resolve_stats_period(period_value)
    from_date, to_date, start_at, end_at = _resolve_stats_range(
        from_value=from_value,
        to_value=to_value,
        now=now,
    )
    app_rows = summarize_app_access_by_app(start_at=start_at, end_at=end_at, app_id=clean_app_id)
    external_app_rows = summarize_external_app_access_by_app(
        start_date=from_date,
        end_date=to_date,
        app_id=external_app_id,
    )
    series_rows = summarize_app_access_by_date(start_at=start_at, end_at=end_at, app_id=clean_app_id)
    external_series_rows = summarize_external_app_access_by_date(
        start_date=from_date,
        end_date=to_date,
        app_id=external_app_id,
    )
    totals = summarize_app_access_totals(start_at=start_at, end_at=end_at, app_id=clean_app_id)
    external_totals = summarize_external_app_access_totals(
        start_date=from_date,
        end_date=to_date,
        app_id=external_app_id,
    )
    merged_apps: dict[str, dict[str, Any]] = {}
    for row in app_rows:
        app_key = safe_text(row.get("metadata__app_id"), "unknown")
        app_name = safe_text(row.get("metadata__app_name"), app_key)
        access_count = int(row.get("access_count") or 0)
        unique_user_count = int(row.get("unique_user_count") or 0)
        _append_app_summary(
            merged=merged_apps,
            app_id=app_key,
            app_name=app_name,
            access_count=access_count,
            unique_user_count=unique_user_count,
            last_accessed_at=serialize_datetime(row.get("last_accessed_at")),
            source_type="internal",
            source_name="portal",
        )

    for row in external_app_rows:
        app_key = safe_text(row.get("app_id"), "unknown")
        app_name = safe_text(row.get("app_name"), app_key)
        _append_app_summary(
            merged=merged_apps,
            app_id=app_key,
            app_name=app_name,
            access_count=int(row.get("access_count") or 0),
            unique_user_count=int(row.get("unique_user_count") or 0),
            last_accessed_at=serialize_kst_date_end(row.get("last_stat_date")),
            source_type=safe_text(row.get("source_type"), MANUAL_SOURCE_TYPE),
            source_name=safe_text(row.get("source_name"), MANUAL_SOURCE_TYPE),
        )

    apps = _finalize_app_summaries(merged_apps)

    merged_series: dict[tuple[str, str], dict[str, Any]] = {}
    for row in series_rows:
        app_key = safe_text(row.get("metadata__app_id"), "unknown")
        local_date = row.get("local_date")
        bucket_date = _get_period_start(local_date, period=period) if isinstance(local_date, date) else None
        _append_series_summary(
            merged=merged_series,
            bucket_date=serialize_date(bucket_date),
            app_id=app_key,
            app_name=safe_text(row.get("metadata__app_name"), app_key),
            access_count=int(row.get("access_count") or 0),
            source_type="internal",
            source_name="portal",
        )

    for row in external_series_rows:
        app_key = safe_text(row.get("app_id"), "unknown")
        stat_date = row.get("stat_date")
        bucket_date = _get_period_start(stat_date, period=period) if isinstance(stat_date, date) else None
        _append_series_summary(
            merged=merged_series,
            bucket_date=serialize_date(bucket_date),
            app_id=app_key,
            app_name=safe_text(row.get("app_name"), app_key),
            access_count=int(row.get("access_count") or 0),
            source_type=safe_text(row.get("source_type"), MANUAL_SOURCE_TYPE),
            source_name=safe_text(row.get("source_name"), MANUAL_SOURCE_TYPE),
        )

    series = _finalize_series_summaries(merged_series)

    top_app = apps[0] if apps else None
    sync_state = get_external_app_usage_sync_state(sync_key=EXTERNAL_USAGE_SYNC_KEY)

    return {
        "timezone": "Asia/Seoul",
        "period": period,
        "range": {
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
        },
        "summary": {
            "totalAccessCount": totals["access_count"] + external_totals["access_count"],
            "uniqueUserCount": totals["unique_user_count"] + external_totals["unique_user_count"],
            "activeAppCount": len(apps),
            "topApp": top_app,
        },
        "externalUsage": _serialize_external_usage_sync_state(sync_state),
        "apps": apps,
        "series": series,
    }
