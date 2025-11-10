"""인증 및 사용자 관련 뷰 모음."""
from __future__ import annotations

from django.conf import settings
from django.contrib.auth import logout
from django.http import HttpRequest, HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from .utils import (
    append_query_params,      # URL 뒤에 ?a=1 같은 쿼리 파라미터를 붙이는 유틸
    build_public_api_url,     # API의 절대 URL을 만들어주는 유틸 (리버스 프록시/호스트 고려)
    resolve_frontend_target,  # next 값 검증/정규화를 통해 안전한 프론트 URL 생성
)


# ---------------------------------------------------------------------------
# 설정/프론트 리다이렉트
# ---------------------------------------------------------------------------
class AuthConfigurationView(APIView):
    """프론트엔드가 사용할 인증 관련 설정값 제공."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        # OIDC 제공자(SSO 등) 구성 여부: 로그인 버튼 활성화 판단에 사용
        provider_configured = bool(getattr(settings, "OIDC_PROVIDER_CONFIGURED", False))

        # 세션 만료(초) — 프런트가 "자동로그아웃 예정" 안내 등에 사용할 수 있음
        session_max_age = getattr(settings, "SESSION_COOKIE_AGE", None)
        try:
            session_max_age = int(session_max_age) if session_max_age is not None else None
        except (TypeError, ValueError):
            session_max_age = None  # 잘못된 값이면 무시

        # 백엔드가 노출하는 로그인 진입점 (아래 LoginRedirectView로 라우팅)
        login_entry_url = reverse("auth-login")

        return JsonResponse(
            {
                "loginUrl": login_entry_url,                          # 백엔드의 로그인 엔트리 포인트
                "frontendRedirect": settings.FRONTEND_BASE_URL,       # 프론트 베이스 URL (안전 리다이렉트 기준)
                "sessionMaxAgeSeconds": session_max_age,              # 세션 유효기간(초)
                "providerConfigured": provider_configured,            # 외부 IdP 구성 여부
            }
        )


class FrontendRedirectView(APIView):
    """프론트엔드 베이스 URL로 안전하게 리다이렉트."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> HttpResponseRedirect:
        # ?next=/dashboard 처럼 들어온 값을 안전하게 정규화(오픈 리다이렉트 방지)
        target = resolve_frontend_target(request.GET.get("next"), request=request)
        return HttpResponseRedirect(target)


# ---------------------------------------------------------------------------
# 현 사용자 정보/로그아웃
# ---------------------------------------------------------------------------
class CurrentUserView(APIView):
    """현재 로그인한 사용자 정보 조회."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        # 세션에 로그인 된 사용자가 아니면 401
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)

        user = request.user
        profile = getattr(user, "profile", None)
        role = profile.role if profile else "viewer"  # 프로필 없으면 기본 뷰어 권한

        # 프런트에서 권한별 UI 제어에 사용할 수 있는 플래그들
        permissions = {
            "is_staff": user.is_staff,
            "is_superuser": user.is_superuser,
            "role": role,
            "canViewActivity": user.has_perm("api.view_activitylog"),
        }

        return JsonResponse(
            {
                "id": user.pk,
                "username": user.get_username(),
                "name": user.get_full_name() or user.get_username(),  # 풀네임 없으면 username으로 대체
                "email": user.email,
                "permissions": permissions,
            }
        )


class LogoutView(APIView):
    """로그아웃 처리."""

    @method_decorator(csrf_exempt)
    def dispatch(self, *args: object, **kwargs: object):  # type: ignore[override]
        # 간단한 로그아웃 엔드포인트이므로 CSRF 제외
        return super().dispatch(*args, **kwargs)

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        # 로그인 상태면 세션 클리어
        if request.user.is_authenticated:
            logout(request)

        # 응답과 함께 세션 쿠키 삭제(클라이언트 측 쿠키 지우기)
        response = JsonResponse({"status": "ok"})
        response.delete_cookie(settings.SESSION_COOKIE_NAME)
        return response




class LoginRedirectView(APIView):
    """환경에 따라 알맞은 로그인 엔드포인트로 안내."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> HttpResponseRedirect:
        next_value = request.GET.get("next")

        login_url = settings.LOGIN_URL or "/auth/google/authenticate/"

        # 절대 URL 보장(리버스 프록시 환경에서 Location 헤더 정확도↑)
        if not login_url.startswith("http"):
            login_url = build_public_api_url(login_url, request=request, absolute=True)

        # next 전달
        target = append_query_params(login_url, {"next": next_value})
        return HttpResponseRedirect(target)


__all__ = [
    "AuthConfigurationView",
    "CurrentUserView",
    "FrontendRedirectView",
    "LoginRedirectView",
    "LogoutView",
]
