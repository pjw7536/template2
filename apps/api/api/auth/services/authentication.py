# =============================================================================
# 모듈 설명: API 인증 헬퍼를 제공합니다.
# - 주요 클래스: CsrfExemptSessionAuthentication
# - 불변 조건: 사내망 환경에서 세션 쿠키 인증을 사용합니다.
# =============================================================================

"""API 서비스용 인증 헬퍼 모듈.

- 주요 대상: CsrfExemptSessionAuthentication
- 주요 엔드포인트/클래스: CsrfExemptSessionAuthentication
- 가정/불변 조건: 사내망 환경에서 세션 쿠키 기반 인증을 사용함
"""

from __future__ import annotations  # 미래 버전 호환 (타입 주석 등에서 문자열 참조 가능)

from rest_framework.authentication import SessionAuthentication  # DRF 기본 세션 인증 클래스


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """CSRF 검사를 생략하는 SessionAuthentication 커스텀 클래스입니다.

    역할:
    - 세션 쿠키 인증은 유지하면서 CSRF 검사를 우회합니다.
    - 사내망 전용 환경에서 프론트엔드 요청 편의를 높입니다.
    """

    def enforce_csrf(self, request):
        """CSRF 검사 단계를 오버라이드하여 검사를 생략합니다.

        입력:
        - 요청: Django HttpRequest

        반환:
        - None: 항상 통과

        부작용:
        - CSRF 검사가 수행되지 않음

        오류:
        - 없음
        """

        return None  # CSRF 검사를 수행하지 않음


# 이 모듈에서 외부로 노출할 심볼을 명시
__all__ = ["CsrfExemptSessionAuthentication"]
