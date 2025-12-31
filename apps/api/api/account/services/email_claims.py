# =============================================================================
# 모듈 설명: account 도메인에서 emails 교차 호출을 래핑합니다.
# - 주요 대상: claim_unassigned_emails_for_user
# - 불변 조건: 실제 이메일 이동 로직은 emails 서비스에 위임합니다.
# =============================================================================

"""account ↔ emails 교차 서비스 래퍼 모음.

- 주요 대상: claim_unassigned_emails_for_user
- 주요 엔드포인트/클래스: 없음
- 가정/불변 조건: 이메일 처리 로직은 emails 서비스가 담당
"""
from __future__ import annotations

from typing import Any, Dict

import api.emails.services as email_services


def claim_unassigned_emails_for_user(*, user: Any) -> Dict[str, int]:
    """UNASSIGNED 메일을 사용자의 현재 user_sdwt_prod로 귀속합니다.

    입력:
    - user: Django User 또는 유사 객체

    반환:
    - Dict[str, int]: moved/ragRegistered/ragFailed/ragMissing 카운트 dict

    부작용:
    - Email.user_sdwt_prod 업데이트
    - RAG 인덱싱 Outbox 적재

    오류:
    - PermissionError: knox_id 미설정
    - ValueError: user_sdwt_prod 미설정 또는 UNASSIGNED 대상
    """

    return email_services.claim_unassigned_emails_for_user(user=user)
