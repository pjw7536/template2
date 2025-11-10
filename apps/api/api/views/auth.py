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
    append_query_params,
    build_public_api_url,
    parse_json_body,
    resolve_frontend_target,
)


# ---------------------------------------------------------------------------
# 설정/프론트 리다이렉트
# ---------------------------------------------------------------------------
class AuthConfigurationView(APIView):
    """프론트엔드가 사용할 인증 관련 설정값 제공."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        provider_configured = bool(getattr(settings, "OIDC_PROVIDER_CONFIGURED", False))
        dev_login_enabled = bool(getattr(settings, "OIDC_DEV_LOGIN_ENABLED", False) and not provider_configured)
        session_max_age = getattr(settings, "SESSION_COOKIE_AGE", None)
        try:
            session_max_age = int(session_max_age) if session_max_age is not None else None
        except (TypeError, ValueError):
            session_max_age = None
        login_entry_url = reverse("auth-login")

        return JsonResponse(
            {
                "devLoginEnabled": dev_login_enabled,
                "loginUrl": login_entry_url,
                "frontendRedirect": settings.FRONTEND_BASE_URL,
                "sessionMaxAgeSeconds": session_max_age,
            }
        )


class FrontendRedirectView(APIView):
    """프론트엔드 베이스 URL로 안전하게 리다이렉트."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> HttpResponseRedirect:
        target = resolve_frontend_target(request.GET.get("next"), request=request)
        return HttpResponseRedirect(target)


# ---------------------------------------------------------------------------
# 현 사용자 정보/로그아웃
# ---------------------------------------------------------------------------
class CurrentUserView(APIView):
    """현재 로그인한 사용자 정보 조회."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)
        user = request.user
        profile = getattr(user, "profile", None)
        role = profile.role if profile else "viewer"
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
                "name": user.get_full_name() or user.get_username(),
                "email": user.email,
                "permissions": permissions,
            }
        )


class LogoutView(APIView):
    """로그아웃 처리."""

    @method_decorator(csrf_exempt)
    def dispatch(self, *args: object, **kwargs: object):  # type: ignore[override]
        return super().dispatch(*args, **kwargs)

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        if request.user.is_authenticated:
            logout(request)
        response = JsonResponse({"status": "ok"})
        response.delete_cookie(settings.SESSION_COOKIE_NAME)
        return response


# ---------------------------------------------------------------------------
# 개발용 로그인 및 리다이렉트
# ---------------------------------------------------------------------------
class DevelopmentLoginView(APIView):
    """개발용 더미 로그인 엔드포인트."""

    http_method_names = ["get", "post"]

    @method_decorator(csrf_exempt)
    def dispatch(self, *args: object, **kwargs: object):  # type: ignore[override]
        return super().dispatch(*args, **kwargs)

    def _is_enabled(self) -> bool:
        return bool(settings.DEBUG) and not bool(settings.OIDC_RP_CLIENT_ID)

    def _login_dummy_user(
        self,
        request: HttpRequest,
        *,
        email: Optional[str] = None,
        name: Optional[str] = None,
        role: Optional[str] = None,
    ):
        data_email = email or os.environ.get("AUTH_DUMMY_EMAIL", "demo@example.com")
        if not isinstance(data_email, str) or "@" not in data_email:
            data_email = "demo@example.com"

        data_name = name or os.environ.get("AUTH_DUMMY_NAME", "Demo User")
        if not isinstance(data_name, str) or not data_name.strip():
            data_name = "Demo User"

        data_role = role or "viewer"

        User = get_user_model()
        username = (
            data_email.split("@")[0]
            if isinstance(data_email, str) and "@" in data_email
            else (data_email or "dev-user")
        )

        user, created = User.objects.get_or_create(
            email=data_email,
            defaults={"username": username, "first_name": data_name},
        )
        if created:
            user.set_unusable_password()
            user.save()
        else:
            if user.first_name != data_name:
                user.first_name = data_name
                user.last_name = ""
                user.save(update_fields=["first_name", "last_name"])

        profile = ensure_user_profile(user)
        if data_role in dict(profile.Roles.choices):
            profile.role = data_role
            profile.save(update_fields=["role"])

        login(request, user, backend="django.contrib.auth.backends.ModelBackend")

        return user, profile

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> HttpResponseRedirect:
        if not self._is_enabled():
            return HttpResponseRedirect(settings.LOGIN_URL)

        self._login_dummy_user(request)
        target = resolve_frontend_target(request.GET.get("next"), request=request)
        return HttpResponseRedirect(target)

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        if not self._is_enabled():
            return JsonResponse({"error": "Development login disabled"}, status=404)

        data = parse_json_body(request) or {}
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
        provider_configured = bool(getattr(settings, "OIDC_PROVIDER_CONFIGURED", False))
        dev_login_enabled = bool(getattr(settings, "OIDC_DEV_LOGIN_ENABLED", False))

        next_value = request.GET.get("next")

        if dev_login_enabled and not provider_configured:
            target = build_public_api_url(
                reverse("auth-dev-login"), request=request
            )
            target = append_query_params(target, {"next": next_value})
            return HttpResponseRedirect(target)

        login_url = settings.LOGIN_URL or "/oidc/authenticate/"
        if not login_url.startswith("http"):
            login_url = build_public_api_url(login_url, request=request, absolute=True)
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
