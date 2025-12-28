# =============================================================================
# 모듈 설명: AppStore 스크린샷 정규화 유틸을 제공합니다.
# - 주요 함수: _normalize_screenshot_input, _split_cover_and_gallery
# - 불변 조건: data URL 형식은 data:<mime>;base64,<data> 입니다.
# =============================================================================
from __future__ import annotations

from typing import Any, Iterable


def _normalize_screenshot_input(value: str) -> tuple[str, str, str]:
    """스크린샷 입력을 (url, base64, mime_type)로 정규화합니다.

    인자:
        value: 스크린샷 입력 문자열.

    반환:
        (url, base64, mime_type) 튜플.

    부작용:
        없음. 읽기 전용 정규화입니다.

    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 기본 정리
    # -----------------------------------------------------------------------------
    raw = (value or "").strip()
    if not raw:
        return "", "", ""

    # -----------------------------------------------------------------------------
    # 2) data URL 여부 판별
    # -----------------------------------------------------------------------------
    if not raw.startswith("data:"):
        return raw, "", ""

    if "," not in raw:
        return raw, "", ""

    # -----------------------------------------------------------------------------
    # 3) data URL 파싱
    # -----------------------------------------------------------------------------
    meta, data = raw.split(",", 1)
    meta = meta[5:]  # "data:" 접두어 제거
    parts = [part.strip() for part in meta.split(";")]
    if not any(part.lower() == "base64" for part in parts):
        return raw, "", ""

    mime_type = parts[0] if parts else ""
    return "", data, mime_type


def _sanitize_screenshot_urls(values: Iterable[Any] | None) -> list[str]:
    """스크린샷 입력을 문자열 배열로 정규화합니다.

    인자:
        values: 스크린샷 입력 iterable.

    반환:
        공백 제거된 문자열 리스트.

    부작용:
        없음. 읽기 전용 정규화입니다.

    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 유효성 확인
    # -----------------------------------------------------------------------------
    if not values:
        return []

    # -----------------------------------------------------------------------------
    # 2) 문자열만 정리
    # -----------------------------------------------------------------------------
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
    """갤러리(추가 스크린샷) 입력을 저장 형태로 정규화합니다.

    인자:
        values: 스크린샷 입력 리스트.

    반환:
        DB 저장용 갤러리 dict 리스트.

    부작용:
        없음. 읽기 전용 정규화입니다.

    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력별 URL/base64 분리
    # -----------------------------------------------------------------------------
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
    """대표 이미지(첫번째)와 갤러리(나머지)로 분리합니다.

    인자:
        screenshot_urls: 스크린샷 URL 목록.

    반환:
        (대표 이미지, 갤러리 목록) 튜플.

    부작용:
        없음. 읽기 전용 정규화입니다.

    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) 문자열 목록 정리
    # -----------------------------------------------------------------------------
    cleaned = _sanitize_screenshot_urls(screenshot_urls)
    if not cleaned:
        return "", []
    # -----------------------------------------------------------------------------
    # 2) 대표/갤러리 분리
    # -----------------------------------------------------------------------------
    return cleaned[0], cleaned[1:]
