"""API 서비스용 인증 헬퍼 모듈"""

from __future__ import annotations  # 미래 버전 호환 (타입 주석 등에서 문자열 참조 가능)

from rest_framework.authentication import SessionAuthentication  # DRF 기본 세션 인증 클래스


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """
    CSRF 검사를 생략하는 SessionAuthentication 커스텀 클래스

    [배경 설명]
    - 기본적으로 DRF의 SessionAuthentication은 POST/PATCH/DELETE 요청 시
      CSRF 토큰(Cross-Site Request Forgery token)이 없으면 요청을 거부합니다.
    - 하지만 SPA(React, Next.js 등) 프론트엔드는 보통 API 서버와 같은 도메인(리버스 프록시 뒤)에서
      동작하며, 이미 세션 쿠키로 인증된 상태에서 fetch 요청을 보냅니다.
    - 이 경우 굳이 CSRF 토큰까지 확인할 필요가 없습니다.

    [이 클래스의 역할]
    - CSRF 검사를 완전히 우회(bypass)하여,
      세션 쿠키 기반 인증은 유지하면서 CSRF 에러 없이 API 요청을 허용합니다.
    """

    def enforce_csrf(self, request):
        """
        CSRF 검사 단계 오버라이드 (무시)

        - DRF는 기본적으로 'enforce_csrf(request)' 내부에서
          request.user.is_authenticated 인 경우에도 CSRF 토큰을 강제 검사합니다.
        - 여기서는 아무 동작도 하지 않고 단순히 '통과'시킵니다.
        - 리버스 프록시(예: Nginx, Caddy) + 세션 쿠키 보안 설정으로
          외부 CSRF 공격을 충분히 방어할 수 있다는 전제하에 사용합니다.
        """

        return None  # CSRF 검사를 수행하지 않음


# 이 모듈에서 외부로 노출할 심볼을 명시
__all__ = ["CsrfExemptSessionAuthentication"]
