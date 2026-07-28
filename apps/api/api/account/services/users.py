# =============================================================================
# 모듈 설명: 사용자 관련 서비스 헬퍼를 제공합니다.
# - 주요 대상: get_user_by_knox_id
# - 불변 조건: 사용자 조회 입력은 공백 제거 후 처리합니다.
# =============================================================================

"""사용자 관련 서비스 헬퍼 모음.

- 주요 대상: Knox ID 조회
- 주요 엔드포인트/클래스: get_user_by_knox_id
- 가정/불변 조건: 사용자 조회 입력은 공백 제거 후 처리함
"""
from __future__ import annotations

from typing import Any

from .. import selectors


def get_user_by_knox_id(*, knox_id: str) -> Any | None:
    """knox_id로 사용자를 조회합니다.

    입력:
    - knox_id: 사용자 knox_id 문자열

    반환:
    - Any | None: 사용자 객체 또는 None

    부작용:
    - 없음

    오류:
    - 없음
    """

    normalized_knox_id = (knox_id or "").strip()
    if not normalized_knox_id:
        return None
    return selectors.get_user_by_knox_id(knox_id=normalized_knox_id)
