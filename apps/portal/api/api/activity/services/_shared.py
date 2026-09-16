# =============================================================================
# 모듈 설명: Activity 서비스 사이에서 공유하는 순수 변환 함수를 제공합니다.
# - 불변 조건: DB 조회나 쓰기, 외부 호출을 수행하지 않습니다.
# =============================================================================
from __future__ import annotations

from datetime import date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


def normalize_app_name(value: Any) -> str:
    """외부 사용량의 앱 이름을 정규화합니다."""

    if not isinstance(value, str):
        return ""
    return value.strip().upper()[:120]


def safe_text(value: Any, fallback: str) -> str:
    """문자열 값을 정리하고 비어 있으면 기본값을 반환합니다."""

    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def serialize_date(value: Any) -> str:
    """date 값을 ISO 문자열로 변환합니다."""

    if isinstance(value, date):
        return value.isoformat()
    return ""


def serialize_datetime(value: Any) -> str | None:
    """datetime 값을 KST ISO 문자열로 변환합니다."""

    if isinstance(value, datetime):
        return value.astimezone(KST).isoformat()
    return None


def serialize_kst_date_end(value: Any) -> str | None:
    """KST 날짜의 종료 시각을 ISO 문자열로 변환합니다."""

    if isinstance(value, date):
        return datetime.combine(value, time.max, tzinfo=KST).isoformat()
    return None
