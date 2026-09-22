"""Observer HTTP query 파싱 공통 헬퍼입니다."""

from __future__ import annotations

from datetime import datetime

from django.http import HttpRequest, JsonResponse

from . import selectors
from api.observer.services import normalize_observer_datetime


def _query_id(request: HttpRequest, key: str) -> str:
    """query string ID 값을 동일한 규칙으로 정규화합니다."""

    return selectors.normalize_id(request.GET.get(key))


def _missing_query_response(message: str) -> JsonResponse:
    """필수 query 누락 응답을 생성합니다."""

    return JsonResponse({"error": message}, status=400)


def _required_query_id(
    request: HttpRequest,
    key: str,
    message: str,
) -> tuple[str, JsonResponse | None]:
    """필수 query ID를 정규화하고 누락 응답을 함께 반환합니다."""

    value = _query_id(request, key)
    if not value:
        return "", _missing_query_response(message)
    return value, None


def _parse_log_limit(request: HttpRequest) -> tuple[int | None, JsonResponse | None]:
    """로그 조회 limit 값을 검증하고, 입력된 경우에만 최대값 안으로 보정합니다."""

    raw_limit = (request.GET.get("limit") or "").strip()
    if not raw_limit:
        return None, None

    try:
        limit = int(raw_limit)
    except ValueError:
        return 0, _missing_query_response("limit must be a positive integer")

    if limit <= 0:
        return 0, _missing_query_response("limit must be a positive integer")
    return min(limit, selectors.MAX_LOG_LIMIT), None


def _parse_log_datetime(
    request: HttpRequest,
    key: str,
    *,
    is_end: bool = False,
) -> tuple[str | None, datetime | None, JsonResponse | None]:
    """로그 조회 시각 파라미터를 ISO 문자열과 비교용 datetime으로 변환합니다."""

    raw_value = (request.GET.get(key) or "").strip()
    if not raw_value:
        return None, None, None

    try:
        value = normalize_observer_datetime(raw_value, is_end=is_end)
    except ValueError:
        value = None
    if value is not None:
        return value.isoformat(), value, None

    return (
        None,
        None,
        _missing_query_response(f"{key} must be a valid date or datetime"),
    )


def _log_query_options(
    request: HttpRequest,
) -> tuple[dict[str, object], JsonResponse | None]:
    """로그 조회 공통 query option을 파싱합니다."""

    limit, limit_error = _parse_log_limit(request)
    if limit_error:
        return {}, limit_error

    start_at, start_comparable, start_error = _parse_log_datetime(request, "from")
    if start_error:
        return {}, start_error

    end_at, end_comparable, end_error = _parse_log_datetime(request, "to", is_end=True)
    if end_error:
        return {}, end_error

    if start_comparable and end_comparable and start_comparable > end_comparable:
        return {}, _missing_query_response("from must be earlier than or equal to to")

    return {"start_at": start_at, "end_at": end_at, "limit": limit}, None
