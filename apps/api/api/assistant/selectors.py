# =============================================================================
# 모듈: 어시스턴트 접근 권한 셀렉터
# 주요 함수: get_accessible_user_sdwt_prods_for_user
# 주요 가정: RAG 검색 범위는 Assistant 앱별 account 데이터 scope에서 결정합니다.
# =============================================================================
from __future__ import annotations

from typing import Any

import api.account.services as account_services


def get_accessible_user_sdwt_prods_for_user(*, user: Any) -> set[str]:
    """사용자가 접근 가능한 user_sdwt_prod 목록을 조회합니다.

    인자:
        user: Django 사용자 객체(익명/비인증 가능).

    반환:
        접근 가능한 user_sdwt_prod 문자열 집합.

    부작용:
        없음. 읽기 전용 조회입니다.
    """

    return account_services.get_accessible_user_sdwt_prods_for_scope(
        user=user,
        scope_key="assistant",
    )
