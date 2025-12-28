from __future__ import annotations

from typing import Any, Iterable


def _normalize_screenshot_input(value: str) -> tuple[str, str, str]:
    """스크린샷 입력을 (url, base64, mime_type)로 정규화합니다."""

    raw = (value or "").strip()
    if not raw:
        return "", "", ""

    if not raw.startswith("data:"):
        return raw, "", ""

    if "," not in raw:
        return raw, "", ""

    meta, data = raw.split(",", 1)
    meta = meta[5:]  # remove leading "data:"
    parts = [part.strip() for part in meta.split(";")]
    if not any(part.lower() == "base64" for part in parts):
        return raw, "", ""

    mime_type = parts[0] if parts else ""
    return "", data, mime_type


def _sanitize_screenshot_urls(values: Iterable[Any] | None) -> list[str]:
    """스크린샷 입력을 문자열 배열로 정규화합니다."""

    if not values:
        return []

    cleaned: list[str] = []
    for raw in values:
        if not isinstance(raw, str):
            continue
        value = raw.strip()
        if not value:
            continue
        cleaned.append(value)
    return cleaned


def _normalize_screenshot_gallery(values: list[str]) -> list[dict[str, str]]:
    """갤러리(추가 스크린샷) 입력을 저장 형태로 정규화합니다."""

    normalized: list[dict[str, str]] = []
    for value in values:
        url, base64_value, mime_type = _normalize_screenshot_input(value)
        if not url and not base64_value:
            continue
        normalized.append(
            {
                "url": url,
                "base64": base64_value,
                "mime_type": mime_type,
            }
        )
    return normalized


def _split_cover_and_gallery(screenshot_urls: list[str]) -> tuple[str, list[str]]:
    """대표 이미지(첫번째)와 갤러리(나머지)로 분리합니다."""

    cleaned = _sanitize_screenshot_urls(screenshot_urls)
    if not cleaned:
        return "", []
    return cleaned[0], cleaned[1:]
