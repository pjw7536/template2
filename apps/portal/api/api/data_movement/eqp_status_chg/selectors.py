"""eqp_status_chg 조회 selector입니다."""

from __future__ import annotations

from datetime import datetime, time
from typing import Iterable, List

from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from api.data_movement.eqp_status_chg.models import EqpStatusChg


def _lookup_key(value: str) -> str:
    """조회용 정규화 키를 생성합니다."""

    return (value or "").strip().upper()


def _normalize_datetime_filter(value: object | None, *, is_end: bool = False) -> object | None:
    """문자열 시간 경계를 DateTimeField filter에 안전한 값으로 변환합니다."""

    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = parse_datetime(value)
        if parsed is None:
            parsed_date = parse_date(value)
            if parsed_date is None:
                return value
            parsed = datetime.combine(parsed_date, time.max if is_end else time.min)
    else:
        return value

    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed, timezone.get_default_timezone())
    return parsed


def fetch_eqp_timeline_logs(
    *,
    eqp_id: str,
    start_at: object | None = None,
    end_at: object | None = None,
    limit: int | None = None,
    statuses: Iterable[str] | None = None,
) -> List[dict[str, object]]:
    """timeline EQP 로그 응답 형태로 상태 변경 이력을 반환합니다.

    입력:
    - eqp_id: 정규화가 끝난 EQP-CB ID
    - start_at/end_at: 조회 시간 경계
    - limit: 선택 row 제한

    반환:
    - List[dict[str, object]]: observer EQP log payload

    부작용:
    - 없음(DB 조회)

    오류:
    - DB 연결 실패 시 예외
    """

    normalized_start_at = _normalize_datetime_filter(start_at)
    normalized_end_at = _normalize_datetime_filter(end_at, is_end=True)

    queryset = EqpStatusChg.objects.filter(eqp_cb_lookup=_lookup_key(eqp_id))
    normalized_statuses = {
        _lookup_key(status) for status in (statuses or []) if _lookup_key(status)
    }
    if normalized_statuses:
        status_query = Q()
        for status in sorted(normalized_statuses):
            status_query |= Q(eqp_status_type__iexact=status)
        queryset = queryset.filter(status_query)
    if normalized_start_at is not None:
        queryset = queryset.filter(chg_time__gte=normalized_start_at)
    if normalized_end_at is not None:
        queryset = queryset.filter(chg_time__lte=normalized_end_at)
    queryset = queryset.order_by("-chg_time")
    if limit is not None:
        queryset = queryset[:limit]

    return [
        {
            "id": f"EQP-{row.eqp_event_key}",
            "eqpId": row.eqp_cb,
            "logType": "EQP",
            "eventType": row.eqp_status_type,
            "eventTime": row.chg_time,
            "operator": row.operator_emp_id,
            "comment": row.chg_comment,
        }
        for row in queryset
    ]


def fetch_eqp_timeline_page(
    *,
    eqp_id: str,
    start_at: object,
    end_at: object,
    page_size: int,
    cursor_time: object | None = None,
    cursor_id: int | None = None,
) -> tuple[list[dict[str, object]], bool]:
    """Observer EQP compact log 한 페이지를 keyset 방식으로 반환합니다.

    입력:
    - eqp_id: 정규화 대상 설비 ID
    - start_at/end_at: 조회 시간 경계
    - page_size: 응답 최대 row 수
    - cursor_time/cursor_id: 이전 페이지의 마지막 정렬 경계

    반환:
    - tuple[list[dict], bool]: compact row와 다음 페이지 존재 여부

    부작용:
    - 없음(DB 조회)
    """

    normalized_start_at = _normalize_datetime_filter(start_at)
    normalized_end_at = _normalize_datetime_filter(end_at, is_end=True)
    queryset = EqpStatusChg.objects.filter(
        eqp_cb_lookup=_lookup_key(eqp_id),
        chg_time__gte=normalized_start_at,
        chg_time__lte=normalized_end_at,
    )
    normalized_cursor_time = _normalize_datetime_filter(cursor_time)
    if normalized_cursor_time is not None and cursor_id is not None:
        queryset = queryset.filter(
            Q(chg_time__lt=normalized_cursor_time)
            | Q(chg_time=normalized_cursor_time, id__lt=cursor_id)
        )

    rows = list(
        queryset.order_by("-chg_time", "-id")
        .values(
            "id",
            "eqp_event_key",
            "eqp_cb",
            "eqp_status_type",
            "chg_time",
            "operator_emp_id",
            "chg_comment",
        )[: page_size + 1]
    )
    has_more = len(rows) > page_size
    return rows[:page_size], has_more


def get_eqp_timeline_detail(*, eqp_id: str, log_id: str) -> dict[str, object] | None:
    """Observer EQP log ID와 설비가 일치하는 상세 row를 반환합니다."""

    try:
        source_id = int(str(log_id or "").strip())
    except (TypeError, ValueError):
        return None
    return (
        EqpStatusChg.objects.filter(
            id=source_id,
            eqp_cb_lookup=_lookup_key(eqp_id),
        )
        .values(
            "id",
            "eqp_event_key",
            "eqp_cb",
            "line_id",
            "chg_time",
            "eqp_code",
            "eqp_mode_type",
            "eqp_status_type",
            "chg_comment",
            "operator_emp_id",
            "last_update_time",
        )
        .first()
    )


__all__ = [
    "fetch_eqp_timeline_logs",
    "fetch_eqp_timeline_page",
    "get_eqp_timeline_detail",
]
