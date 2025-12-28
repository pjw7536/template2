from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Mapping

from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime


def parse_int(value: Any, default: int) -> int:
    """입력 값을 정수로 파싱하고 실패/0 이하일 때 기본값을 반환합니다.

    Side effects:
        None. Pure parsing.
    """

    try:
        parsed = int(value)
        if parsed <= 0:
            return default
        return parsed
    except (TypeError, ValueError):
        return default


def parse_datetime_value(value: str | None) -> datetime | None:
    """날짜/일시 문자열을 timezone-aware datetime(UTC)으로 파싱합니다.

    Side effects:
        None. Pure parsing.
    """

    if not value:
        return None
    dt = parse_datetime(value)
    if dt:
        return dt
    date_only = parse_date(value)
    if date_only:
        return datetime.combine(date_only, datetime.min.time(), tzinfo=timezone.utc)
    return None


def parse_mailbox_user_sdwt_prod(params: Mapping[str, Any]) -> str:
    """요청 쿼리에서 mailbox(user_sdwt_prod) 값을 추출/정규화합니다.

    Side effects:
        None. Pure parsing.
    """

    raw = params.get("user_sdwt_prod") or params.get("userSdwtProd") or ""
    return raw.strip() if isinstance(raw, str) else ""


def build_email_filters(
    *, params: Mapping[str, Any], default_page_size: int, max_page_size: int
) -> Dict[str, Any]:
    """이메일 목록 필터 값을 일관되게 정규화합니다.

    Side effects:
        None. Pure normalization.
    """

    return {
        "mailbox_user_sdwt_prod": parse_mailbox_user_sdwt_prod(params),
        "search": (params.get("q") or "").strip(),
        "sender": (params.get("sender") or "").strip(),
        "recipient": (params.get("recipient") or "").strip(),
        "date_from": parse_datetime_value(params.get("date_from")),
        "date_to": parse_datetime_value(params.get("date_to")),
        "page": parse_int(params.get("page"), 1),
        "page_size": min(parse_int(params.get("page_size"), default_page_size), max_page_size),
    }
