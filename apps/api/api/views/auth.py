"""인증 및 사용자 관련 뷰 모음."""
from __future__ import annotations

import os
from typing import Optional

from django.conf import settings
from django.contrib.auth import get_user_model, login, logout
from django.http import HttpRequest, HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from ..models import ensure_user_profile
from .utils import (
    append_query_params,      # URL 뒤에 ?a=1 같은 쿼리 파라미터를 붙이는 유틸
    build_public_api_url,     # API의 절대 URL을 만들어주는 유틸 (리버스 프록시/호스트 고려)
    parse_json_body,          # 요청 바디를 JSON으로 파싱 (실패 시 None)
    resolve_frontend_target,  # next 값 검증/정규화를 통해 안전한 프론트 URL 생성
)


# ---------------------------------------------------------------------------
# 설정/프론트 리다이렉트
# ---------------------------------------------------------------------------
class AuthConfigurationView(APIView):
    """프론트엔드가 사용할 인증 관련 설정값 제공."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        # OIDC 제공자(SSO 등) 구성 여부: 프런트가 로그인 버튼 노출 로직에 사용
        provider_configured = bool(getattr(settings, "OIDC_PROVIDER_CONFIGURED", False))
        # 개발 로그인 허용 여부: OIDC가 없을 때만 true가 되도록 안전장치
        dev_login_enabled = bool(getattr(settings, "OIDC_DEV_LOGIN_ENABLED", False) and not provider_configured)

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
                "devLoginEnabled": dev_login_enabled,                 # 개발 로그인 가능 여부
                "loginUrl": login_entry_url,                          # 백엔드의 로그인 엔트리 포인트
                "frontendRedirect": settings.FRONTEND_BASE_URL,       # 프론트 베이스 URL (안전 리다이렉트 기준)
                "sessionMaxAgeSeconds": session_max_age,              # 세션 유효기간(초)
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


# ---------------------------------------------------------------------------
# 개발용 로그인 및 리다이렉트
# ---------------------------------------------------------------------------
class DevelopmentLoginView(APIView):
    """개발용 더미 로그인 엔드포인트."""

    http_method_names = ["get", "post"]  # GET: 리다이렉트 기반 / POST: JSON 응답 기반

    @method_decorator(csrf_exempt)
    def dispatch(self, *args: object, **kwargs: object):  # type: ignore[override]
        # 개발 편의 엔드포인트이므로 CSRF 제외 (운영에서 노출되지 않도록 조건이 있음)
        return super().dispatch(*args, **kwargs)

    def _is_enabled(self) -> bool:
        provider_configured = bool(getattr(settings, "GOOGLE_OIDC_CONFIGURED", False))
        dev_login_enabled = bool(getattr(settings, "OIDC_DEV_LOGIN_ENABLED", False))
        return dev_login_enabled and not provider_configured

    def _login_dummy_user(
        self,
        request: HttpRequest,
        *,
        email: Optional[str] = None,
        name: Optional[str] = None,
        role: Optional[str] = None,
    ):
        """
        개발 편의를 위한 더미 사용자 로그인:
        - 이메일/이름/권한(role)을 파라미터 또는 환경변수로 받아 생성/업데이트
        - 세션에 로그인 상태를 심고, 프로필/역할 저장
        """
        # 이메일 결정 (환경변수 기본값 보정)
        data_email = email or os.environ.get("AUTH_DUMMY_EMAIL", "demo@example.com")
        if not isinstance(data_email, str) or "@" not in data_email:
            data_email = "demo@example.com"

        # 이름 결정 (환경변수 기본값 보정)
        data_name = name or os.environ.get("AUTH_DUMMY_NAME", "Demo User")
        if not isinstance(data_name, str) or not data_name.strip():
            data_name = "Demo User"

        data_role = role or "viewer"  # 기본 역할

        User = get_user_model()
        # username 은 이메일 @ 앞부분을 기본으로 사용(형식 비정상이면 fallback)
        username = (
            data_email.split("@")[0]
            if isinstance(data_email, str) and "@" in data_email
            else (data_email or "dev-user")
        )

        # 이메일 기준으로 유저 생성/조회
        user, created = User.objects.get_or_create(
            email=data_email,
            defaults={"username": username, "first_name": data_name},
        )
        if created:
            # 개발 전용 계정: 비밀번호 사용 안함 (외부 인증 없음)
            user.set_unusable_password()
            user.save()
        else:
            # 이름 변경사항 반영 (성은 비움)
            if user.first_name != data_name:
                user.first_name = data_name
                user.last_name = ""
                user.save(update_fields=["first_name", "last_name"])

        # 프로필 보장 및 역할 저장(정의된 choices 내의 값만 허용)
        profile = ensure_user_profile(user)
        if data_role in dict(profile.Roles.choices):
            profile.role = data_role
            profile.save(update_fields=["role"])

        # 세션 로그인 (명시적으로 ModelBackend 지정)
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")

        return user, profile

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> HttpResponseRedirect:
        """
        GET /auth/dev-login?next=/...
        - 개발로그인이 비활성화면 공식 LOGIN_URL로 돌려보냄
        - 활성화면 더미 로그인 후 next(또는 기본 프론트)로 리다이렉트
        """
        if not self._is_enabled():
            return HttpResponseRedirect(settings.LOGIN_URL)

        self._login_dummy_user(request)
        target = resolve_frontend_target(request.GET.get("next"), request=request)
        return HttpResponseRedirect(target)

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """
        POST /auth/dev-login
        - 바디(JSON)로 email/name/role을 받아 더미 로그인 처리
        - JSON 형태로 현재 사용자 정보를 반환 (프론트에서 상태 갱신에 사용)
        """
        if not self._is_enabled():
            return JsonResponse({"error": "Development login disabled"}, status=404)

        data = parse_json_body(request) or {}
        # 문자열일 때만 사용(타입 안전)
        email = data.get("email") if isinstance(data.get("email"), str) else None
        name = data.get("name") if isinstance(data.get("name"), str) else None
        role = data.get("role") if isinstance(data.get("role"), str) else None

        user, profile = self._login_dummy_user(
            request,
            email=email,
            name=name,
            role=role,
        )

        return JsonResponse(
            {
                "status": "ok",
                "user": {
                    "id": user.pk,
                    "username": user.get_username(),
                    "name": user.get_full_name() or user.first_name,
                    "email": user.email,
                    "role": profile.role,
                },
            }
        )


class LoginRedirectView(APIView):
    """환경에 따라 알맞은 로그인 엔드포인트로 안내."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> HttpResponseRedirect:
        # 운영/개발 모드에 따라 어디로 보낼지 결정
        provider_configured = bool(getattr(settings, "OIDC_PROVIDER_CONFIGURED", False))
        dev_login_enabled = bool(getattr(settings, "OIDC_DEV_LOGIN_ENABLED", False))

        next_value = request.GET.get("next")

        # OIDC 미구성 + 개발 로그인 허용 → 개발 로그인 URL로 안내
        if dev_login_enabled and not provider_configured:
            target = build_public_api_url(
                reverse("auth-dev-login"), request=request
            )
            target = append_query_params(target, {"next": next_value})
            return HttpResponseRedirect(target)

        # 그 외: 운영 로그인(예: /auth/google/authenticate/ 또는 settings.LOGIN_URL)로 안내
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
    "DevelopmentLoginView",
    "FrontendRedirectView",
    "LoginRedirectView",
    "LogoutView",
]
