"""ctttm_workorder_list 읽기 전용 selector입니다."""

from __future__ import annotations

from django.db.models import Q, QuerySet
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from api.data_movement.ctttm_workorder_list.models import CtttmWorkorderList, CtttmWorkorderListLoadJob


def _observer_datetime(value: object) -> object:
    """Observer 문자열 시각을 CTTTM DateTimeField 조회값으로 정규화합니다."""

    if hasattr(value, "tzinfo"):
        parsed = value
    else:
        parsed = parse_datetime(str(value or ""))
    if parsed is None:
        return value
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed, timezone.get_default_timezone())
    return parsed


def list_recent_load_jobs(*, limit: int = 20) -> QuerySet[CtttmWorkorderListLoadJob]:
    """최근 적재 이력을 최신순으로 반환합니다."""

    return CtttmWorkorderListLoadJob.objects.order_by("-created_at", "-id")[:limit]


def load_workorder_descriptions_by_ids(*, workorder_ids: list[str]) -> dict[str, str]:
    """workorder_id별 CTTTM 작업 설명을 반환합니다."""

    normalized_ids = [workorder_id for workorder_id in dict.fromkeys(workorder_ids) if workorder_id]
    if not normalized_ids:
        return {}

    rows = (
        CtttmWorkorderList.objects.filter(workorder_id__in=normalized_ids)
        .exclude(description__isnull=True)
        .exclude(description="")
        .order_by("workorder_id", "-inprg_date", "-id")
        .values("workorder_id", "description")
    )
    descriptions: dict[str, str] = {}
    for row in rows:
        workorder_id = str(row["workorder_id"])
        if workorder_id not in descriptions:
            descriptions[workorder_id] = str(row["description"])
    return descriptions


def fetch_ctttm_timeline_page(
    *,
    eqp_id: str,
    start_at: object,
    end_at: object,
    page_size: int,
    cursor_time: object | None = None,
    cursor_id: int | None = None,
) -> tuple[list[dict[str, object]], bool]:
    """Observer CTTTM compact log 한 페이지를 keyset 방식으로 반환합니다."""

    eqp_key = str(eqp_id or "").strip().upper()
    queryset = CtttmWorkorderList.objects.filter(
        eqp_id_lookup=eqp_key,
        inprg_date__gte=_observer_datetime(start_at),
        inprg_date__lte=_observer_datetime(end_at),
    )
    parsed_cursor_time = (
        _observer_datetime(cursor_time) if cursor_time is not None else None
    )
    if parsed_cursor_time is not None and cursor_id is not None:
        queryset = queryset.filter(
            Q(inprg_date__lt=parsed_cursor_time)
            | Q(inprg_date=parsed_cursor_time, id__lt=cursor_id)
        )

    rows = list(
        queryset.order_by("-inprg_date", "-id")
        .values(
            "id",
            "workorder_id",
            "line_id",
            "eqp_id",
            "work_type",
            "description",
            "inprg_date",
        )[: page_size + 1]
    )
    has_more = len(rows) > page_size
    return rows[:page_size], has_more


def get_ctttm_timeline_detail(
    *,
    eqp_id: str,
    source_id: int,
) -> dict[str, object] | None:
    """설비와 source PK가 일치하는 CTTTM 상세 원천 row를 반환합니다."""

    return (
        CtttmWorkorderList.objects.filter(
            id=source_id,
            eqp_id_lookup=str(eqp_id or "").strip().upper(),
        )
        .values(
            "id",
            "workorder_id",
            "line_id",
            "eqp_id",
            "work_type",
            "description",
            "inprg_date",
            "comp_date",
        )
        .first()
    )
