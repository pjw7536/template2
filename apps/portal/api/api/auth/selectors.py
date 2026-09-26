# =============================================================================
# 모듈 설명: auth 도메인 읽기 전용 셀렉터를 제공합니다.
# - 주요 대상: 사용자 조회, 현재 사용자 응답 payload 조립
# - 불변 조건: 모든 조회는 부작용 없이 수행합니다.
# =============================================================================

"""auth 도메인 읽기 전용 셀렉터 모음.

- 주요 대상: 사용자 조회, 현재 사용자 응답 payload 조립
- 주요 엔드포인트/클래스: 없음(셀렉터 함수만 제공)
- 가정/불변 조건: 읽기 전용 ORM 접근만 수행함
"""
from __future__ import annotations

from typing import Any, Dict

import api.account.selectors as account_selectors
import api.account.services as account_services


def get_current_user_payload(*, user: Any) -> Dict[str, Any]:
    """현재 로그인 세션의 권한과 소속을 공개 사용자 응답으로 반환합니다."""
    ctx = account_services.get_authorization_context(user=user)
    return {
        "id": user.pk, "knoxId": user.knox_id, "avatarId": user.avatarid,
        "username": user.username or "", "email": user.email,
        "department": ctx.department, "line": ctx.line, "userSdwtProd": ctx.user_sdwt_prod,
        "authorizationSource": "keycloak", "hasAllAppsAccess": ctx.all_apps,
        "isPortalAdmin": ctx.portal_admin, "pendingUserSdwtProd": None,
        "hasPendingAffiliation": False,
        "scopeAccess": account_services.get_scope_access_payloads(user=user, context=ctx),
        "sdwtAccess": dict(ctx.sdwt_roles),
    }
