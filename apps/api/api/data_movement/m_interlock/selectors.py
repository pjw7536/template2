"""m_interlock 조회 전용 selector를 제공합니다."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from django.db.models.functions import Trim, Upper
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from .models import MInterlock

SEOUL_TIMEZONE = ZoneInfo("Asia/Seoul")
SOURCE_TIME_FORMAT = "%Y%m%d %H%M%S"
VALID_INTERLOCK_KINDS = frozenset({"SPC", "FDC"})

TIMELINE_VALUE_FIELDS = (
    "id",
    "line_id",
    "interlock_no",
    "item_value",
    "interlock_type",
    "interlock_comment",
    "ppid",
    "usl",
    "spec_target",
    "lsl",
    "ucl",
    "cl",
    "lcl",
    "batch_id",
    "metro_item",
    "interlock_desc",
    "area_name",
    "process_id",
    "interlock_kind",
    "lot_id",
    "prod_step_seq",
    "prod_progs_time",
    "prod_eqp_type",
    "prod_bay_name",
    "prod_chamber_id",
    "metro_step_seq",
    "metro_progs_time",
    "intlk_occur_week",
    "intlk_occur_year_m",
    "metro_eqp_id",
    "prod_eqp_id",
    "last_update_date",
    "wafer_id",
    "eqp_process_phase",
    "eqp_detail_comment",
    "engr_comment",
)


def _normalize_datetime(value: object, *, is_end: bool = False) -> datetime:
    """조회 경계를 Asia/Seoul aware datetime으로 정규화합니다."""

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
                raise ValueError("로그 조회 시간 형식이 올바르지 않습니다.")

    if timezone.is_naive(parsed):
        return parsed.replace(tzinfo=SEOUL_TIMEZONE)
    return parsed.astimezone(SEOUL_TIMEZONE)


def _format_boundary(value: object, *, is_end: bool = False) -> str:
    """조회 경계를 원천 prod_progs_time 문자열 형식으로 변환합니다."""

    return _normalize_datetime(value, is_end=is_end).strftime(SOURCE_TIME_FORMAT)


def _parse_source_time(value: object) -> datetime | None:
    """원천 prod_progs_time을 Asia/Seoul aware datetime으로 변환합니다."""

    raw_value = str(value or "").strip()
    try:
        parsed = datetime.strptime(raw_value, SOURCE_TIME_FORMAT)
    except ValueError:
        return None
    return parsed.replace(tzinfo=SEOUL_TIMEZONE)


def fetch_interlock_timeline_rows(
    *,
    eqp_id: str,
    interlock_kind: str,
    start_at: object,
    end_at: object | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """설비와 interlock 종류 기준으로 유효한 timeline 원천 행을 반환합니다."""

    eqp_key = str(eqp_id or "").strip().upper()
    kind_key = str(interlock_kind or "").strip().upper()
    if not eqp_key or kind_key not in VALID_INTERLOCK_KINDS:
        return []

    queryset = (
        MInterlock.objects.annotate(
            prod_eqp_key=Upper(Trim("prod_eqp_id")),
            interlock_kind_key=Upper(Trim("interlock_kind")),
        )
        .filter(
            prod_eqp_key=eqp_key,
            interlock_kind_key=kind_key,
            prod_progs_time__gte=_format_boundary(start_at),
            prod_progs_time__regex=r"^\d{8} \d{6}$",
        )
        .order_by("-prod_progs_time", "-id")
        .values(*TIMELINE_VALUE_FIELDS)
    )
    if end_at is not None:
        queryset = queryset.filter(
            prod_progs_time__lte=_format_boundary(end_at, is_end=True),
        )

    rows: list[dict[str, Any]] = []
    for row in queryset.iterator(chunk_size=1000):
        event_time = _parse_source_time(row.get("prod_progs_time"))
        if event_time is None:
            continue
        row["event_time"] = event_time
        rows.append(row)
        if limit is not None and len(rows) >= limit:
            break
    return rows


__all__ = [
    "SEOUL_TIMEZONE",
    "SOURCE_TIME_FORMAT",
    "fetch_interlock_timeline_rows",
]
