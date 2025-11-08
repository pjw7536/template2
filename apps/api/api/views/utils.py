"""여러 뷰에서 공용으로 활용하는 유틸리티 함수 모음."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

from django.conf import settings
from django.http import HttpRequest
from django.utils.http import url_has_allowed_host_and_scheme

from ..db import run_query
from .constants import (
    DATE_COLUMN_CANDIDATES,
    DATE_ONLY_REGEX,
    LINE_SDWT_TABLE_NAME,
    SAFE_IDENTIFIER,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 문자열/날짜 정규화
# ---------------------------------------------------------------------------
def sanitize_identifier(value: Any, fallback: Optional[str] = None) -> Optional[str]:
    """테이블/컬럼명 등 식별자를 안전하게 정규식으로 검증."""

    if not isinstance(value, str):
        return fallback
    candidate = value.strip()
    return candidate if SAFE_IDENTIFIER.match(candidate) else fallback


def normalize_date_only(value: Any) -> Optional[str]:
    """YYYY-MM-DD 형식을 만족하면 그대로, 아니면 None."""

    if not isinstance(value, str):
        return None
    candidate = value.strip()
    return candidate if DATE_ONLY_REGEX.match(candidate) else None


def to_int(value: Any) -> int:
    """정수 변환 유틸(실패 시 0)."""

    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return 0


def parse_json_body(request: HttpRequest) -> Optional[Dict[str, Any]]:
    """요청 바디(JSON) 파싱 유틸."""

    try:
        body = request.body.decode("utf-8")
    except UnicodeDecodeError:
        return None
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


# ---------------------------------------------------------------------------
# DB 메타 정보/필터링 로직
# ---------------------------------------------------------------------------
def find_column(column_names: Iterable[str], target: str) -> Optional[str]:
    """컬럼 이름 목록에서 대소문자 무시하고 정확 매칭."""

    target_lower = target.lower()
    for name in column_names:
        if isinstance(name, str) and name.lower() == target_lower:
            return name
    return None


def pick_base_timestamp_column(column_names: Sequence[str]) -> Optional[str]:
    """통계/필터의 기준이 되는 타임스탬프 컬럼 선택."""

    for candidate in DATE_COLUMN_CANDIDATES:
        found = find_column(column_names, candidate)
        if found:
            return found
    return None


def _get_user_sdwt_prod_values(line_id: str) -> List[str]:
    """line_sdwt 테이블에서 line_id에 해당하는 user_sdwt_prod 목록 조회."""

    rows = run_query(
        """
        SELECT DISTINCT user_sdwt_prod
        FROM {table}
        WHERE line_id = %s
          AND user_sdwt_prod IS NOT NULL
          AND user_sdwt_prod <> ''
        """.format(table=LINE_SDWT_TABLE_NAME),
        [line_id],
    )
    values: List[str] = []
    for row in rows:
        raw = row.get("user_sdwt_prod")
        if isinstance(raw, str):
            trimmed = raw.strip()
            if trimmed:
                values.append(trimmed)
    return values


def list_table_columns(table_name: str) -> List[str]:
    """현재 스키마에서 주어진 테이블의 컬럼 목록 조회."""

    rows = run_query(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND LOWER(table_name) = %s
        ORDER BY ordinal_position
        """,
        [table_name.lower()],
    )
    column_names: List[str] = []
    for row in rows:
        value: Optional[str] = None
        for key in ("column_name", "COLUMN_NAME", "Field"):
            raw = row.get(key)
            if isinstance(raw, str) and raw.strip():
                value = raw.strip()
                break
        if value:
            column_names.append(value)
    return column_names


def build_line_filters(column_names: Sequence[str], line_id: Optional[str]) -> Dict[str, Any]:
    """lineId 필터 SQL 조각 생성."""

    filters: List[str] = []
    params: List[Any] = []

    if not line_id:
        return {"filters": filters, "params": params}

    usdwt_col = find_column(column_names, "user_sdwt_prod")
    if usdwt_col:
        values = _get_user_sdwt_prod_values(line_id)
        if values:
            placeholders = ", ".join(["%s"] * len(values))
            filters.append(f"{usdwt_col} IN ({placeholders})")
            params.extend(values)
            return {"filters": filters, "params": params}

    line_col = find_column(column_names, "line_id")
    if line_col:
        filters.append(f"{line_col} = %s")
        params.append(line_id)

    return {"filters": filters, "params": params}


# ---------------------------------------------------------------------------
# URL 헬퍼
# ---------------------------------------------------------------------------
def resolve_frontend_target(next_value: Optional[str]) -> str:
    """프론트엔드 베이스 URL과 next 값을 조합하여 안전한 리다이렉트 주소 생성."""

    base = (settings.FRONTEND_BASE_URL or "http://localhost:3000").strip() or "http://localhost:3000"
    base = base.rstrip("/")
    parsed_base = urlparse(base if "://" in base else f"http://{base.lstrip('/')}")
    allowed_hosts = {parsed_base.netloc} if parsed_base.netloc else set()

    if next_value:
        candidate = str(next_value).strip()
        if candidate:
            if url_has_allowed_host_and_scheme(candidate, allowed_hosts=allowed_hosts, require_https=False):
                return candidate
            if candidate.startswith("/"):
                trimmed = candidate.lstrip("/")
                return f"{base}/{trimmed}" if trimmed else base
            return urljoin(f"{base}/", candidate)

    return base


def append_query_params(url: str, params: Dict[str, Optional[str]]) -> str:
    """기존 URL에 쿼리 파라미터를 병합."""

    if not params:
        return url

    parsed = urlparse(url)
    existing = dict(parse_qsl(parsed.query, keep_blank_values=True))

    for key, value in params.items():
        if value is None:
            continue
        existing[key] = str(value)

    new_query = urlencode(existing, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


__all__ = [
    "append_query_params",
    "build_line_filters",
    "find_column",
    "list_table_columns",
    "normalize_date_only",
    "parse_json_body",
    "pick_base_timestamp_column",
    "resolve_frontend_target",
    "sanitize_identifier",
    "to_int",
]
