from __future__ import annotations

import json
import os
from typing import List, Optional, Sequence

from django.conf import settings


def _read_setting(name: str, fallback: Optional[str] = None) -> Optional[str]:
    """Django settings 또는 환경변수에서 설정 값을 문자열로 읽습니다."""

    value = getattr(settings, name, None)
    if value is None:
        value = os.environ.get(name, fallback)
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _parse_int(value: Optional[str], default: int) -> int:
    """문자열 값을 양의 정수로 파싱하고 실패 시 기본값을 반환합니다."""

    if value is None:
        return default
    try:
        parsed = int(str(value).strip())
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default


def _parse_float(value: Optional[str], default: float) -> float:
    """문자열 값을 float로 파싱하고 실패 시 기본값을 반환합니다."""

    if value is None:
        return default
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def _parse_bool(value: Optional[str], default: bool = False) -> bool:
    """문자열 값을 boolean으로 파싱합니다(1/true/yes/on=True)."""

    if value is None:
        return default
    normalized = str(value).strip().lower()
    return normalized in {"1", "true", "yes", "on"}


def _parse_string_list(raw: Optional[str]) -> List[str]:
    """JSON 배열/개행 문자열 등을 문자열 리스트로 정규화합니다."""

    if not raw:
        return []

    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        parsed = None

    if isinstance(parsed, Sequence) and not isinstance(parsed, (str, bytes)):
        return [str(item).strip() for item in parsed if str(item).strip()]

    if isinstance(raw, str):
        if "\n" in raw:
            return [item.strip() for item in raw.splitlines() if item.strip()]
        return [raw.strip()]

    return []


def _normalize_string_list(raw: Optional[Sequence[str] | str]) -> List[str]:
    """문자열 또는 문자열 리스트를 정규화합니다."""

    if not raw:
        return []

    if isinstance(raw, str):
        values = [raw]
    elif isinstance(raw, Sequence):
        values = list(raw)
    else:
        return []

    normalized: List[str] = []
    for item in values:
        if item is None:
            continue
        cleaned = str(item).strip()
        if cleaned:
            normalized.append(cleaned)
    return list(dict.fromkeys(normalized))
