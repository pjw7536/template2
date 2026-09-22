# =============================================================================
# 모듈 설명: observer 데이터 셀렉터를 제공합니다.
# - 주요 함수: 공통 직렬화와 DB 조회 헬퍼
# - 불변 조건: 로그별 소유 selector/DB를 통해 조회합니다.
# =============================================================================

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import hashlib
import json
import logging
import re
from time import perf_counter
from typing import Dict, List, Sequence
from urllib.parse import urlencode

from django.conf import settings
from django.db import connection

from api.data_movement.ctttm_workorder_list import selectors as ctttm_workorder_selectors
from api.data_movement.eqp_status_chg import selectors as eqp_status_chg_selectors
from api.data_movement.m_interlock import selectors as m_interlock_selectors
from api.data_movement.mi_tip_update_hist import selectors as mi_tip_update_hist_selectors
from api.data_movement.racb_list import selectors as racb_list_selectors
from api.drone import selectors as drone_selectors

from api.observer.serializers import encode_observer_cursor
from api.observer.services import (
    ANALYSIS_SOURCE_LIMIT,
    build_observer_evidence_id,
    observer_period_start,
    serialize_observer_datetime as _serialize_event_time,
)

DEFAULT_LOG_QUERY_DAYS = 60
MAX_LOG_LIMIT = 5000
TKIN_PREVENT_REGISTRATION_LEVELS = ("LEVEL1", "LEVEL2", "LEVEL3")
TKIN_PREVENT_LEVEL2_NAMES = {"LEVEL2", "LEVEL3"}

Row = Dict[str, object]
LogRows = List[Dict[str, object]]
LogFetcher = Callable[[str, object | None, object | None, int | None], LogRows]
CompactPageFetcher = Callable[..., tuple[list[Row], bool]]
CompactRowSerializer = Callable[[Row], dict[str, object]]
DetailFetcher = Callable[[str, int], Row | None]
DetailSerializer = Callable[[Row], dict[str, object]]


@dataclass(frozen=True)
class _ObserverLogSource:
    """Observer source의 전체 목록·page·detail 조회 계약을 보관합니다."""

    fetch_logs: LogFetcher
    fetch_page: CompactPageFetcher
    serialize_page_row: CompactRowSerializer
    cursor_time_field: str
    fetch_detail: DetailFetcher
    serialize_detail_row: DetailSerializer

logger = logging.getLogger(__name__)


# =============================================================================
# 내부 헬퍼
# =============================================================================


def _safe_text(value: object) -> str:
    """None 값을 안전하게 문자열로 정리합니다."""

    return "" if value is None else str(value)


def _comment_preview(value: object, *, limit: int = 200) -> tuple[str, bool]:
    """목록 payload에 사용할 comment preview와 잘림 여부를 반환합니다."""

    text = _safe_text(value)
    if len(text) <= limit:
        return text, False
    return text[:limit], True


OBSERVER_RESPONSE_TIME_FIELDS = (
    "eventTime",
    "endTime",
    "completedAt",
    "lastUpdateTime",
    "lastUpdateDate",
    "create_date",
    "due_date",
    "update_date",
    "created_at",
    "updated_at",
)


def _serialize_log_time_fields(log: dict[str, object]) -> dict[str, object]:
    """Observer 응답의 공통 시간 필드를 Asia/Seoul 문자열로 변환합니다."""

    serialized = dict(log)
    for field_name in OBSERVER_RESPONSE_TIME_FIELDS:
        value = serialized.get(field_name)
        if value is not None:
            serialized[field_name] = _serialize_event_time(value)
    return serialized


def _tip_page_log_id(row: Row) -> str:
    """기존 TIP Timeline ID와 호환되는 compact item ID를 생성합니다."""

    event_time = row.get("gpm_update_date")
    timestamp = (
        event_time.strftime("%Y%m%d%H%M%S%f")
        if hasattr(event_time, "strftime")
        else _safe_text(event_time).replace("-", "").replace(":", "").replace(" ", "")
    )
    comment_hash = hashlib.md5(
        _safe_text(row.get("tip_comment")).encode("utf-8")
    ).hexdigest()
    return "-".join(
        [
            "TIP",
            _safe_text(row.get("eqp_cb")),
            timestamp,
            _safe_text(row.get("event_type")),
            _safe_text(row.get("process_id")),
            _safe_text(row.get("step_seq")),
            _safe_text(row.get("ppid")),
            comment_hash,
        ]
    )


def _page_cursor_values(
    cursor_payload: dict[str, object] | None,
) -> tuple[object | None, int | None]:
    """검증된 cursor payload에서 source selector 경계를 추출합니다."""

    if not cursor_payload:
        return None, None
    try:
        cursor_id = int(cursor_payload["tieBreaker"])
    except (KeyError, TypeError, ValueError):
        return None, None
    return cursor_payload.get("eventTime"), cursor_id


def _build_page_cursor(
    *,
    eqp_id: str,
    log_type: str,
    range_key: str,
    event_time: object,
    tie_breaker: object,
) -> str:
    """다음 페이지용 opaque cursor를 생성합니다."""

    return encode_observer_cursor(
        {
            "eqpId": eqp_id,
            "logType": log_type,
            "range": range_key,
            "eventTime": _serialize_event_time(event_time),
            "tieBreaker": int(tie_breaker),
        }
    )


def serialize_compact_eqp_row(row: Row) -> dict[str, object]:
    """EQP source row를 compact log payload로 변환합니다."""

    preview, truncated = _comment_preview(row.get("chg_comment"))
    return {
        "id": f"EQP-{row.get('eqp_event_key')}",
        "detailId": row.get("id"),
        "sourceId": row.get("id"),
        "eqpId": row.get("eqp_cb"),
        "logType": "EQP",
        "eventType": row.get("eqp_status_type"),
        "eventTime": row.get("chg_time"),
        "operator": row.get("operator_emp_id"),
        "comment": preview,
        "commentTruncated": truncated,
    }


def serialize_compact_tip_row(row: Row) -> dict[str, object]:
    """TIP source row를 compact log payload로 변환합니다."""

    preview, truncated = _comment_preview(row.get("tip_comment"))
    register_name = _safe_text(row.get("register_name"))
    return {
        "id": _tip_page_log_id(row),
        "detailId": row.get("id"),
        "sourceId": row.get("id"),
        "eqpId": row.get("eqp_cb"),
        "logType": "TIP",
        "eventType": row.get("event_type"),
        "eventTime": row.get("gpm_update_date"),
        "operator": register_name.split("-", 1)[0] or None,
        "comment": preview,
        "commentTruncated": truncated,
        "lineId": row.get("line_id"),
        "process": row.get("process_id"),
        "step": row.get("step_seq"),
        "ppid": row.get("ppid"),
    }


def serialize_compact_interlock_row(
    row: Row,
    *,
    interlock_kind: str,
) -> dict[str, object]:
    """Interlock source row를 compact log payload로 변환합니다."""

    preview, truncated = _comment_preview(
        row.get("interlock_comment")
        or row.get("interlock_desc")
        or row.get("engr_comment")
    )
    source_id = row.get("id")
    event_type = (
        _safe_text(row.get("interlock_no")).strip()
        or _safe_text(row.get("interlock_type")).strip()
        or interlock_kind
    )
    log_type = f"{interlock_kind}_ITL"
    return {
        "id": f"{log_type}:{source_id}",
        "detailId": source_id,
        "sourceId": source_id,
        "eqpId": row.get("prod_eqp_id"),
        "logType": log_type,
        "eventType": event_type,
        "eventTime": row.get("event_time"),
        "operator": None,
        "comment": preview,
        "commentTruncated": truncated,
        "metroItem": row.get("metro_item"),
        "interlockType": row.get("interlock_type"),
        "interlockKind": interlock_kind,
    }


def serialize_compact_ctttm_row(
    row: Row,
    *,
    base_url: str,
) -> dict[str, object]:
    """CTTTM source row를 compact log payload로 변환합니다."""

    preview, truncated = _comment_preview(row.get("description"))
    return {
        "id": row.get("workorder_id"),
        "detailId": row.get("id"),
        "sourceId": row.get("id"),
        "eqpId": row.get("eqp_id"),
        "logType": "CTTTM",
        "eventType": row.get("work_type"),
        "eventTime": row.get("inprg_date"),
        "operator": None,
        "comment": preview,
        "commentTruncated": truncated,
        "url": f"{base_url}{row.get('workorder_id')}&lineId={row.get('line_id')}",
    }


def serialize_compact_racb_row(
    row: Row,
    *,
    report_base_url: str,
) -> dict[str, object]:
    """RACB source row를 compact log payload로 변환합니다."""

    preview, truncated = _comment_preview(row.get("title"))
    query = urlencode(
        {
            "racbId": row.get("c_racb_id"),
            "lineId": row.get("line_id") or "",
        }
    )
    return {
        "id": f"RACB-{row.get('c_racb_id')}-{row.get('eqp_cb')}",
        "detailId": row.get("id"),
        "sourceId": row.get("id"),
        "eqpId": row.get("eqp_cb"),
        "logType": "RACB",
        "eventType": f"{row.get('racb_type_cd') or ''}_{row.get('status_code') or ''}",
        "eventTime": row.get("update_date"),
        "operator": row.get("create_user"),
        "comment": preview,
        "commentTruncated": truncated,
        "lineId": row.get("line_id"),
        "url": f"{report_base_url}?{query}" if report_base_url else None,
    }


def serialize_compact_esop_row(row: Row) -> dict[str, object]:
    """ESOP source row를 defect map 파싱 없는 compact payload로 변환합니다."""

    preview, truncated = _comment_preview(row.get("comment"))
    return {
        "id": row.get("id"),
        "detailId": row.get("id"),
        "sourceId": row.get("id"),
        "logType": "ESOP",
        "eventType": row.get("sample_type"),
        "eventTime": row.get("created_at"),
        "operator": row.get("knox_id"),
        "status": row.get("status"),
        "comment": preview,
        "commentTruncated": truncated,
        "lineId": row.get("line_id"),
        "eqpId": row.get("eqp_id"),
        "eqpCb": f"{row.get('eqp_id') or '-'}-{row.get('chamber_ids') or '-'}",
        "lotId": row.get("lot_id"),
    }


def _period_date(days: int | None = None) -> str:
    """Asia/Seoul 기준 조회 시작 시각을 반환합니다."""

    query_days = (
        days
        if days is not None
        else getattr(settings, "OBSERVER_QUERY_DAYS", DEFAULT_LOG_QUERY_DAYS)
    )
    return observer_period_start(days=query_days)


def _fetch_all(query: str, params: Sequence[object] | None = None) -> List[Row]:
    """기본 DB에서 조회 결과를 dict 리스트로 반환합니다."""

    with connection.cursor() as cursor:
        cursor.execute(query, params or [])
        columns = [col[0] for col in (cursor.description or [])]
        rows = cursor.fetchall()

    return [dict(zip(columns, row)) for row in rows]


def _fetch_all_on_default(query: str, params: Sequence[object] | None = None) -> List[Row]:
    """기본 DB에서 조회 결과를 dict 리스트로 반환합니다."""

    return _fetch_all(query, params)


def _fetch_one(query: str, params: Sequence[object] | None = None) -> Row | None:
    """단일 행 조회를 반환합니다(없으면 None)."""

    rows = _fetch_all(query, params)
    return rows[0] if rows else None


def _normalize_filters(**values: str | None) -> Dict[str, str]:
    """조회 필터 값을 같은 규칙으로 정규화합니다."""

    return {key: normalize_id(value) for key, value in values.items()}


def _build_text_record(row: Row, field_map: Sequence[tuple[str, str]]) -> Dict[str, str]:
    """행 데이터를 응답 필드명 기준 문자열 dict로 변환합니다."""

    return {
        target_field: _safe_text(row.get(source_field))
        for target_field, source_field in field_map
    }


def _find_drone_target_for_sdwt(
    *,
    sdwt_id: str,
    preferred_line_id: str = "",
) -> Dict[str, str] | None:
    """Drone target 옵션에서 SDWT를 소유한 line/target 조합을 찾습니다."""

    sdwt_key = normalize_id(sdwt_id)
    preferred_line_key = normalize_id(preferred_line_id)
    if not sdwt_key:
        return None

    payload = drone_selectors.get_tip_status_line_sdwt_options_payload()
    rows = payload.get("lines") if isinstance(payload, dict) else []
    matches: list[Dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue

        line_id = _safe_text(row.get("lineId")).strip()
        values = row.get("userSdwtProds")
        if not line_id or not isinstance(values, list):
            continue

        for raw_value in values:
            target_value = _safe_text(raw_value).strip()
            if target_value and normalize_id(target_value) == sdwt_key:
                matches.append({"lineId": line_id, "sdwtId": target_value})

    if preferred_line_key:
        return next(
            (
                match
                for match in matches
                if normalize_id(match["lineId"]) == preferred_line_key
            ),
            None,
        )

    return next(
        iter(
            sorted(
                matches,
                key=lambda match: (
                    normalize_id(match["lineId"]),
                    normalize_id(match["sdwtId"]),
                ),
            )
        ),
        None,
    )


def _build_time_clause(
    field_name: str,
    *,
    start_at: object | None = None,
    end_at: object | None = None,
) -> tuple[str, List[object]]:
    """로그 조회 시간 조건과 파라미터를 생성합니다."""

    clause = f"{field_name} >= %s"
    params: List[object] = [start_at or _period_date()]
    if end_at is not None:
        clause += f" and {field_name} <= %s"
        params.append(end_at)
    return clause, params


def _build_limit_clause(limit: int | None = None) -> tuple[str, List[object]]:
    """선택적으로 SQL limit 절과 파라미터를 생성합니다."""

    if limit is None:
        return "", []
    return "limit %s", [limit]


# =============================================================================
# 공개 정규화 함수
# =============================================================================


def normalize_id(value: str | None) -> str:
    """입력 ID를 공백 제거 후 대문자로 정규화합니다.

    입력:
    - value: 원본 ID(None 허용)

    반환:
    - str: 정규화된 ID(없으면 빈 문자열)

    부작용:
    - 없음

    오류:
    - 없음
    """

    return (value or "").strip().upper()

__all__ = [
    'annotations',
    'Callable',
    'dataclass',
    'hashlib',
    'json',
    'logging',
    're',
    'perf_counter',
    'Dict',
    'List',
    'Sequence',
    'urlencode',
    'settings',
    'connection',
    'ctttm_workorder_selectors',
    'eqp_status_chg_selectors',
    'm_interlock_selectors',
    'mi_tip_update_hist_selectors',
    'racb_list_selectors',
    'drone_selectors',
    'encode_observer_cursor',
    'ANALYSIS_SOURCE_LIMIT',
    'build_observer_evidence_id',
    'observer_period_start',
    '_serialize_event_time',
    'DEFAULT_LOG_QUERY_DAYS',
    'MAX_LOG_LIMIT',
    'TKIN_PREVENT_REGISTRATION_LEVELS',
    'TKIN_PREVENT_LEVEL2_NAMES',
    'Row',
    'LogRows',
    'LogFetcher',
    'CompactPageFetcher',
    'CompactRowSerializer',
    'DetailFetcher',
    'DetailSerializer',
    '_ObserverLogSource',
    'logger',
    '_safe_text',
    '_comment_preview',
    'OBSERVER_RESPONSE_TIME_FIELDS',
    '_serialize_log_time_fields',
    '_tip_page_log_id',
    '_page_cursor_values',
    '_build_page_cursor',
    'serialize_compact_eqp_row',
    'serialize_compact_tip_row',
    'serialize_compact_interlock_row',
    'serialize_compact_ctttm_row',
    'serialize_compact_racb_row',
    'serialize_compact_esop_row',
    '_period_date',
    '_fetch_all',
    '_fetch_all_on_default',
    '_fetch_one',
    '_normalize_filters',
    '_build_text_record',
    '_find_drone_target_for_sdwt',
    '_build_time_clause',
    '_build_limit_clause',
    'normalize_id',
]
