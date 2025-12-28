from __future__ import annotations

from typing import Sequence


def _normalize_participants(values: Sequence[str] | None) -> list[str]:
    """참여자(수신/참조) 문자열 리스트를 trim/dedup하여 반환합니다."""

    if not values:
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = " ".join(str(value or "").split()).strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(cleaned)
    return normalized


def _build_participants_search(*, recipient: Sequence[str] | None, cc: Sequence[str] | None) -> str | None:
    """recipient/cc를 합쳐 부분검색용 텍스트를 생성합니다(소문자 정규화)."""

    combined = _normalize_participants(list(recipient or []) + list(cc or []))
    if not combined:
        return None
    return "\n".join([value.lower() for value in combined])
