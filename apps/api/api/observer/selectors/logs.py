"""Observer canonical 로그 page, detail, 분석 selector입니다."""

from ._shared import *  # noqa: F403
from .sources import *  # noqa: F403


def _fetch_compact_log_page(
    *,
    source: _ObserverLogSource,
    eqp_id: str,
    start_at: object,
    end_at: object,
    page_size: int,
    cursor_payload: dict[str, object] | None,
) -> tuple[list[dict[str, object]], bool, object | None, int | None]:
    """source 정의에 따라 compact row와 다음 cursor 경계를 반환합니다."""

    cursor_time, cursor_id = _page_cursor_values(cursor_payload)
    rows, has_more = source.fetch_page(
        eqp_id=eqp_id,
        start_at=start_at,
        end_at=end_at,
        page_size=page_size,
        cursor_time=cursor_time,
        cursor_id=cursor_id,
    )
    items = [source.serialize_page_row(row) for row in rows]
    last_row = rows[-1] if rows else None
    return (
        items,
        has_more,
        last_row.get(source.cursor_time_field) if last_row else None,
        int(last_row["id"]) if last_row else None,
    )


def get_log_page(
    *,
    eqp_id: str,
    log_key: str,
    start_at: object,
    end_at: object,
    page_size: int,
    range_key: str,
    cursor_payload: dict[str, object] | None = None,
) -> dict[str, object]:
    """유형별 Observer compact log 한 페이지를 반환합니다."""

    type_key = (log_key or "").strip().lower()
    source = _OBSERVER_LOG_SOURCES.get(type_key)
    if source is None:
        raise ValueError(f"지원하지 않는 Observer log type입니다: {type_key}")

    normalized_eqp_id = normalize_id(eqp_id)
    result = _fetch_compact_log_page(
        source=source,
        eqp_id=normalized_eqp_id,
        start_at=start_at,
        end_at=end_at,
        page_size=page_size,
        cursor_payload=cursor_payload,
    )
    items, has_more, next_time, next_id = result
    items = [_serialize_log_time_fields(item) for item in items]
    next_cursor = None
    if has_more and next_time is not None and next_id is not None:
        next_cursor = _build_page_cursor(
            eqp_id=normalized_eqp_id,
            log_type=type_key,
            range_key=range_key,
            event_time=next_time,
            tie_breaker=next_id,
        )
    return {
        "items": items,
        "page": {
            "nextCursor": next_cursor,
            "hasMore": bool(next_cursor),
            "pageSize": page_size,
        },
        "meta": {
            "logType": type_key,
            "from": _serialize_event_time(start_at),
            "to": _serialize_event_time(end_at),
        },
    }


def get_log_pages(
    *,
    eqp_id: str,
    log_types: Sequence[str],
    start_at: object,
    end_at: object,
    page_size: int,
    range_key: str,
) -> dict[str, object]:
    """최초 화면에 필요한 유형별 compact page를 부분 실패 허용으로 조회합니다."""

    data: dict[str, object] = {}
    failed_count = 0
    for log_type in log_types:
        started_at = perf_counter()
        try:
            page = get_log_page(
                eqp_id=eqp_id,
                log_key=log_type,
                start_at=start_at,
                end_at=end_at,
                page_size=page_size,
                range_key=range_key,
            )
            data[log_type] = {
                "items": page["items"],
                "nextCursor": page["page"]["nextCursor"],
                "hasMore": page["page"]["hasMore"],
                "error": None,
            }
            logger.info(
                "Observer page source 조회 완료",
                extra={
                    "log_type": log_type,
                    "elapsed_ms": round((perf_counter() - started_at) * 1000, 2),
                    "row_count": len(page["items"]),
                    "has_more": page["page"]["hasMore"],
                },
            )
        except Exception:
            failed_count += 1
            logger.exception(
                "Observer page source 조회 실패",
                extra={
                    "log_type": log_type,
                    "elapsed_ms": round((perf_counter() - started_at) * 1000, 2),
                },
            )
            data[log_type] = {
                "items": [],
                "nextCursor": None,
                "hasMore": False,
                "error": {
                    "code": "SOURCE_QUERY_FAILED",
                    "message": f"{log_type} 로그 조회에 실패했습니다.",
                },
            }
    return {
        "data": data,
        "meta": {
            "from": _serialize_event_time(start_at),
            "to": _serialize_event_time(end_at),
            "pageSize": page_size,
            "partial": 0 < failed_count < len(log_types),
            "allFailed": failed_count == len(log_types),
        },
    }


def get_log_detail(
    *,
    eqp_id: str,
    log_key: str,
    log_id: str,
) -> dict[str, object] | None:
    """설비와 source PK가 일치하는 Observer 상세 payload를 반환합니다."""

    type_key = (log_key or "").strip().lower()
    source_id = _numeric_detail_id(log_id)
    source = _OBSERVER_LOG_SOURCES.get(type_key)
    if source_id is None or source is None:
        return None

    row = source.fetch_detail(eqp_id, source_id)
    return source.serialize_detail_row(row) if row else None


def _fetch_logs_by_type_normalized(
    *,
    eqp_key: str,
    type_key: str,
    start_at: object | None = None,
    end_at: object | None = None,
    limit: int | None = None,
) -> LogRows:
    """정규화가 끝난 설비 ID로 타입별 로그를 조회합니다."""

    fetcher = OBSERVER_LOG_FETCHERS.get(type_key)
    if fetcher is None:
        return []
    return [
        _serialize_log_time_fields(log)
        for log in fetcher(eqp_key, start_at, end_at, limit)
    ]


def get_analysis_logs_by_type(
    *,
    eqp_id: str,
    log_key: str,
    start_at: object,
    end_at: object,
    limit: int,
) -> List[Dict[str, object]]:
    """AI 분석에 필요한 관심 상태와 주변 로그만 조회합니다.

    EQP/TIP는 대량의 제외 상태가 조회 상한을 차지하지 않도록 DB에서 먼저
    관심 상태를 제한하고, 나머지 유형은 기존 Observer payload를 재사용합니다.
    """

    eqp_key = normalize_id(eqp_id)
    type_key = (log_key or "").strip().lower()
    if type_key == "eqp":
        logs = eqp_status_chg_selectors.fetch_eqp_timeline_logs(
            eqp_id=eqp_key,
            start_at=start_at,
            end_at=end_at,
            limit=limit,
            statuses=("DOWN", "IDLE", "LOCAL"),
        )
        return [_serialize_log_time_fields(log) for log in logs]
    if type_key == "tip":
        logs = mi_tip_update_hist_selectors.fetch_tip_timeline_logs(
            eqp_id=eqp_key,
            start_at=start_at,
            end_at=end_at,
            limit=limit,
            event_type_pattern=r"^L.*_TIP$",
        )
        return [_serialize_log_time_fields(log) for log in logs]
    return _fetch_logs_by_type_normalized(
        eqp_key=eqp_key,
        type_key=type_key,
        start_at=start_at,
        end_at=end_at,
        limit=limit,
    )


def get_analysis_evidence_log(
    *,
    eqp_id: str,
    log_key: str,
    evidence_id: str,
    start_at: object,
    end_at: object,
) -> dict[str, object] | None:
    """분석 당시 source 규칙으로 evidence ID에 일치하는 로그를 반환합니다.

    입력:
    - eqp_id/log_key: 분석 대상 설비와 로그 유형
    - evidence_id: AI 분석 결과에 저장된 event ID
    - start_at/end_at: 분석 당시 조회 범위

    반환:
    - dict | None: 일치하는 원본 로그 또는 미존재

    부작용:
    - 없음(DB read-only)
    """

    normalized_evidence_id = str(evidence_id or "").strip()
    if not normalized_evidence_id:
        return None

    logs = get_analysis_logs_by_type(
        eqp_id=eqp_id,
        log_key=log_key,
        start_at=start_at,
        end_at=end_at,
        limit=ANALYSIS_SOURCE_LIMIT,
    )
    for log in logs:
        if build_observer_evidence_id(log) == normalized_evidence_id:
            return log
    return None

__all__ = [
    '_fetch_compact_log_page',
    'get_log_page',
    'get_log_pages',
    'get_log_detail',
    '_fetch_logs_by_type_normalized',
    'get_analysis_logs_by_type',
    'get_analysis_evidence_log',
]
