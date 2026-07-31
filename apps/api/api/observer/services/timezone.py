"""Observer의 Asia/Seoul 시간 계약을 제공합니다."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

SEOUL_TIMEZONE = ZoneInfo("Asia/Seoul")


def normalize_observer_datetime(
    value: object,
    *,
    is_end: bool = False,
) -> datetime:
    """Observer 시각을 Asia/Seoul aware datetime으로 정규화합니다."""

    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, time.max if is_end else time.min)
    else:
        raw_value = str(value or "").strip()
        parsed_date = parse_date(raw_value)
        if parsed_date is not None and len(raw_value) == 10:
            parsed = datetime.combine(
                parsed_date,
                time.max if is_end else time.min,
            )
        else:
            parsed = parse_datetime(raw_value)
            if parsed is None:
                raise ValueError("Observer 시각 형식이 올바르지 않습니다.")

    if timezone.is_naive(parsed):
        return parsed.replace(tzinfo=SEOUL_TIMEZONE)
    return parsed.astimezone(SEOUL_TIMEZONE)


def serialize_observer_datetime(value: object) -> str:
    """Observer 시각을 +09:00 offset이 포함된 ISO 문자열로 변환합니다."""

    try:
        return normalize_observer_datetime(value).isoformat()
    except ValueError:
        return str(value or "")


def observer_period_start(*, days: int) -> str:
    """Asia/Seoul 오늘을 기준으로 지정 일수 전 자정 ISO 문자열을 반환합니다."""

    local_date = timezone.now().astimezone(SEOUL_TIMEZONE).date() - timedelta(
        days=days
    )
    return datetime.combine(
        local_date,
        time.min,
        tzinfo=SEOUL_TIMEZONE,
    ).isoformat()
