"""m_interlock 조회 전용 selector를 제공합니다."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from .models import MInterlock

SEOUL_TIMEZONE = ZoneInfo("Asia/Seoul")
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

TIMELINE_PAGE_VALUE_FIELDS = (
    "id",
    "interlock_no",
    "interlock_type",
    "interlock_comment",
    "interlock_desc",
    "engr_comment",
    "interlock_kind",
    "prod_eqp_id",
    "metro_item",
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
        MInterlock.objects.filter(
            prod_eqp_id_lookup=eqp_key,
            interlock_kind_lookup=kind_key,
            prod_progs_at__gte=_normalize_datetime(start_at),
        )
        .order_by("-prod_progs_at", "-id")
        .values(*TIMELINE_VALUE_FIELDS, "prod_progs_at")
    )
    if end_at is not None:
        queryset = queryset.filter(
            prod_progs_at__lte=_normalize_datetime(end_at, is_end=True),
        )

    rows: list[dict[str, Any]] = []
    for row in queryset.iterator(chunk_size=1000):
        row["event_time"] = row.pop("prod_progs_at")
        rows.append(row)
        if limit is not None and len(rows) >= limit:
            break
    return rows


def fetch_interlock_timeline_page(
    *,
    eqp_id: str,
    interlock_kind: str,
    start_at: object,
    end_at: object,
    page_size: int,
    cursor_time: object | None = None,
    cursor_id: int | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    """Observer Interlock compact log 한 페이지를 keyset 방식으로 반환합니다."""

    eqp_key = str(eqp_id or "").strip().upper()
    kind_key = str(interlock_kind or "").strip().upper()
    if not eqp_key or kind_key not in VALID_INTERLOCK_KINDS:
        return [], False

    queryset = MInterlock.objects.filter(
        prod_eqp_id_lookup=eqp_key,
        interlock_kind_lookup=kind_key,
        prod_progs_at__gte=_normalize_datetime(start_at),
        prod_progs_at__lte=_normalize_datetime(end_at, is_end=True),
    )
    parsed_cursor_time = None
    if cursor_time:
        try:
            parsed_cursor_time = _normalize_datetime(cursor_time)
        except ValueError:
            parsed_cursor_time = None
    if parsed_cursor_time is not None and cursor_id is not None:
        queryset = queryset.filter(
            Q(prod_progs_at__lt=parsed_cursor_time)
            | Q(prod_progs_at=parsed_cursor_time, id__lt=cursor_id)
        )

    raw_rows = list(
        queryset.order_by("-prod_progs_at", "-id")
        .values(*TIMELINE_PAGE_VALUE_FIELDS, "prod_progs_at")[: page_size + 1]
    )
    has_more = len(raw_rows) > page_size
    rows: list[dict[str, Any]] = []
    for row in raw_rows[:page_size]:
        row["event_time"] = row.pop("prod_progs_at")
        rows.append(row)
    return rows, has_more


def get_interlock_timeline_detail(
    *,
    eqp_id: str,
    interlock_kind: str,
    source_id: int,
) -> dict[str, Any] | None:
    """설비, 종류, source PK가 일치하는 Interlock 상세 row를 반환합니다."""

    eqp_key = str(eqp_id or "").strip().upper()
    kind_key = str(interlock_kind or "").strip().upper()
    if not eqp_key or kind_key not in VALID_INTERLOCK_KINDS:
        return None

    row = (
        MInterlock.objects.filter(
            id=source_id,
            prod_eqp_id_lookup=eqp_key,
            interlock_kind_lookup=kind_key,
        )
        .values(*TIMELINE_VALUE_FIELDS, "prod_progs_at")
        .first()
    )
    if row is None:
        return None
    row["event_time"] = row.pop("prod_progs_at")
    return row


__all__ = [
    "SEOUL_TIMEZONE",
    "fetch_interlock_timeline_page",
    "fetch_interlock_timeline_rows",
    "get_interlock_timeline_detail",
]
