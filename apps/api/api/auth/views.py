from __future__ import annotations  # 미래 버전 호환: 타입 힌트에서 문자열로 클래스 이름 사용 가능

from django.conf import settings  # Django 설정 파일에 접근하기 위한 모듈
from django.contrib import auth  # Django의 인증(authenticate, login 등) 관련 기능
from django.http import HttpResponseRedirect, JsonResponse  # HTTP 응답 객체
from django.shortcuts import resolve_url  # URL 이름이나 경로를 실제 URL로 변환

# Mozilla에서 제공하는 Django용 OIDC(인증 표준) 뷰와 도우미 함수
from mozilla_django_oidc.views import (
    OIDCAuthenticationRequestView,  # 기본 OIDC 로그인 요청 처리 클래스
    get_next_url,                   # 로그인 후 이동할 URL을 결정하는 함수
)


class ConditionalOIDCAuthenticationRequestView(OIDCAuthenticationRequestView):
    """
    OIDC 인증 요청을 처리하는 커스텀 뷰 클래스
    - 기본적으로는 OpenID Connect(OIDC) 인증 절차를 수행
    - 하지만 개발 환경(dev)에서는 OIDC 서버가 없어도 로그인 가능하도록 예외 처리
    """

    def get(self, request):
        """
        GET 요청 시 호출됨 (보통 /auth/login 처럼 로그인 버튼을 눌렀을 때)
        """
        # OIDC 설정값 가져오기
        client_id = getattr(settings, "OIDC_RP_CLIENT_ID", None)
        auth_endpoint = getattr(settings, "OIDC_OP_AUTHORIZATION_ENDPOINT", None)
        dev_login_enabled = bool(getattr(settings, "OIDC_DEV_LOGIN_ENABLED", False))

        # 🔹 만약 OIDC 서버 설정이 되어 있지 않다면...
        if not client_id or not auth_endpoint:
            # ✅ 개발용 로그인(dev-login)이 활성화된 경우
            if dev_login_enabled:
                # 개발 환경용 인증 시도 (예: DevelopmentLoginBackend 등)
                user = auth.authenticate(request=request)
                if user is not None:
                    # 로그인 성공 시 세션에 사용자 정보 저장
                    auth.login(request, user)

                    # 로그인 후 이동할 URL(next 파라미터)을 가져옴
                    redirect_field_name = self.get_settings("OIDC_REDIRECT_FIELD_NAME", "next")
                    next_target = get_next_url(request, redirect_field_name)

                    # next 파라미터가 없으면 기본 리디렉션 URL로 이동
                    if not next_target:
                        next_target = resolve_url(self.get_settings("LOGIN_REDIRECT_URL", "/"))

                    # 로그인 성공 → 해당 페이지로 리다이렉트
                    return HttpResponseRedirect(next_target)

            # ⚠️ 개발 로그인도 비활성화되어 있고, OIDC 설정도 없음 → 오류 응답 반환
            return JsonResponse({"error": "OIDC provider is not configured"}, status=503)

        # 🔹 OIDC 설정이 정상적으로 되어 있으면 기본 OIDC 로그인 흐름 수행
        return super().get(request)
