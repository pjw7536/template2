"""Google OAuth based authentication entrypoints."""
from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.http import HttpRequest, HttpResponseRedirect
from django.urls import reverse
from django.views import View

from ..models import ensure_user_profile
from ..views.utils import append_query_params, resolve_frontend_target

logger = logging.getLogger(__name__)


@dataclass
class GoogleOAuthResult:
    access_token: str
    id_token: Optional[str]
    refresh_token: Optional[str]


class GoogleOAuthException(Exception):
    """Internal helper for consistent error propagation."""

    def __init__(self, message: str, error_code: str = "oauth_error"):
        super().__init__(message)
        self.error_code = error_code


def _callback_uri(request: HttpRequest) -> str:
    override = str(getattr(settings, "GOOGLE_OAUTH_REDIRECT_URI", "") or "").strip()
    if override:
        return override
    return request.build_absolute_uri(reverse("google-oauth-callback"))


def _build_frontend_redirect(
    request: HttpRequest,
    *,
    next_value: Optional[str] = None,
    error: Optional[str] = None,
) -> HttpResponseRedirect:
    target = resolve_frontend_target(next_value, request=request)
    if error:
        target = append_query_params(target, {"authError": error})
    return HttpResponseRedirect(target)


def _exchange_code_for_tokens(request: HttpRequest, code: str) -> GoogleOAuthResult:
    payload = {
        "code": code,
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
        "redirect_uri": _callback_uri(request),
        "grant_type": "authorization_code",
    }
    try:
        response = requests.post(
            settings.GOOGLE_OAUTH_TOKEN_ENDPOINT,
            data=payload,
            timeout=10,
        )
    except requests.RequestException as exc:
        raise GoogleOAuthException("token_request_failed", "token_request_failed") from exc

    if response.status_code >= 400:
        logger.warning(
            "Google token request failed",
            extra={"status": response.status_code, "body": response.text[:200]},
        )
        raise GoogleOAuthException("token_request_failed", "token_request_failed")

    try:
        data = response.json()
    except ValueError as exc:
        raise GoogleOAuthException("token_parse_error", "token_parse_error") from exc
    access_token = data.get("access_token")
    if not access_token:
        raise GoogleOAuthException("token_missing", "token_missing")

    return GoogleOAuthResult(
        access_token=access_token,
        id_token=data.get("id_token"),
        refresh_token=data.get("refresh_token"),
    )


def _fetch_user_info(access_token: str) -> Dict[str, Any]:
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        response = requests.get(
            settings.GOOGLE_OAUTH_USERINFO_ENDPOINT,
            headers=headers,
            timeout=10,
        )
    except requests.RequestException as exc:
        raise GoogleOAuthException("userinfo_failed", "userinfo_failed") from exc

    if response.status_code >= 400:
        logger.warning(
            "Google userinfo request failed",
            extra={"status": response.status_code, "body": response.text[:200]},
        )
        raise GoogleOAuthException("userinfo_failed", "userinfo_failed")

    try:
        return response.json()
    except ValueError as exc:
        raise GoogleOAuthException("userinfo_failed", "userinfo_failed") from exc


def _upsert_user(user_info: Dict[str, Any]):
    email = user_info.get("email")
    if not isinstance(email, str) or not email:
        raise GoogleOAuthException("email_missing", "email_missing")

    UserModel = get_user_model()
    user = UserModel.objects.filter(email__iexact=email).first()
    if user is None:
        username = email.split("@")[0] or email
        user = UserModel.objects.create_user(
            username=username,
            email=email,
        )

    first_name = user_info.get("given_name") or user_info.get("name")
    last_name = user_info.get("family_name") or ""

    updated = False
    if isinstance(first_name, str) and first_name.strip() and user.first_name != first_name.strip():
        user.first_name = first_name.strip()
        updated = True
    if isinstance(last_name, str) and user.last_name != last_name.strip():
        user.last_name = last_name.strip()
        updated = True

    if updated:
        user.save(update_fields=["first_name", "last_name"])

    ensure_user_profile(user)
    return user


class GoogleOAuthStartView(View):
    """Initiate the Google OAuth flow."""

    def get(self, request: HttpRequest) -> HttpResponseRedirect:
        if not settings.GOOGLE_OIDC_CONFIGURED:
            return _build_frontend_redirect(request, error="provider_not_configured")

        state = secrets.token_urlsafe(32)
        request.session["google_oauth_state"] = state

        next_value = request.GET.get("next")
        if next_value:
            request.session["google_oauth_next"] = str(next_value)
        else:
            request.session.pop("google_oauth_next", None)

        params = {
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "response_type": "code",
            "scope": settings.GOOGLE_OAUTH_SCOPE,
            "redirect_uri": _callback_uri(request),
            "state": state,
            "access_type": settings.GOOGLE_OAUTH_ACCESS_TYPE,
            "prompt": settings.GOOGLE_OAUTH_PROMPT,
        }
        auth_url = f"{settings.GOOGLE_OAUTH_AUTH_ENDPOINT}?{urlencode(params)}"
        return HttpResponseRedirect(auth_url)


class GoogleOAuthCallbackView(View):
    """Handle the Google OAuth callback and log the user in."""

    def get(self, request: HttpRequest) -> HttpResponseRedirect:
        next_value = request.session.pop("google_oauth_next", None)

        if not settings.GOOGLE_OIDC_CONFIGURED:
            return _build_frontend_redirect(request, next_value=next_value, error="provider_not_configured")

        error_param = request.GET.get("error")
        if error_param:
            logger.warning("Google OAuth returned error", extra={"error": error_param})
            return _build_frontend_redirect(request, next_value=next_value, error="access_denied")

        state = request.GET.get("state")
        stored_state = request.session.pop("google_oauth_state", None)
        if not state or not stored_state or state != stored_state:
            return _build_frontend_redirect(request, next_value=next_value, error="invalid_state")

        code = request.GET.get("code")
        if not code:
            return _build_frontend_redirect(request, next_value=next_value, error="missing_code")

        try:
            tokens = _exchange_code_for_tokens(request, code)
            user_info = _fetch_user_info(tokens.access_token)
            user = _upsert_user(user_info)
        except GoogleOAuthException as exc:
            logger.exception("Google OAuth callback failed: %s", exc)
            return _build_frontend_redirect(request, next_value=next_value, error=exc.error_code)

        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return _build_frontend_redirect(request, next_value=next_value)


__all__ = [
    "GoogleOAuthCallbackView",
    "GoogleOAuthStartView",
]
