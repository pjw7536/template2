# =============================================================================
# 모듈 설명: emails 서비스에서 사용하는 문자열 정규화 유틸을 제공합니다.
# - 주요 함수: _normalize_participants, _build_participants_search
# - 불변 조건: 중복 제거는 대소문자 무시 기준으로 수행합니다.
# =============================================================================

from __future__ import annotations

from typing import Sequence


def _normalize_participants(values: Sequence[str] | None) -> list[str]:
    """참여자(수신/참조) 문자열 리스트를 trim/dedup하여 반환합니다.

    입력:
        values: 참여자 문자열 목록.
    반환:
        공백 제거 + 대소문자 무시 중복 제거된 문자열 리스트.
    부작용:
        없음.
    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 유효성 확인
    # -----------------------------------------------------------------------------
    if not values:
        return []

    # -----------------------------------------------------------------------------
    # 2) 공백 정규화 및 중복 제거
    # -----------------------------------------------------------------------------
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
    """recipient/cc를 합쳐 부분검색용 텍스트를 생성합니다(소문자 정규화).

    입력:
        recipient: 수신자 목록.
        cc: 참조 목록.
    반환:
        줄바꿈으로 결합된 소문자 문자열 또는 None.
    부작용:
        없음.
    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) 참여자 목록 통합 및 정규화
    # -----------------------------------------------------------------------------
    combined = _normalize_participants(list(recipient or []) + list(cc or []))
    if not combined:
        return None
    # -----------------------------------------------------------------------------
    # 2) 검색용 문자열 생성
    # -----------------------------------------------------------------------------
    return "\n".join([value.lower() for value in combined])
