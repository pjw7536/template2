"""Session-backed authentication endpoints using an id_token-only OIDC flow."""
from __future__ import annotations

import uuid
from urllib.parse import urlencode

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model, login, logout
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt

from .oidc_utils import (
    ADFS_AUTH_URL,
    ADFS_LOGOUT_URL,
    ISSUER,
    OIDC_CLIENT_ID,
    PUB_KEY,
    REDIRECT_URI,
    b64d,
    b64e,
    is_allowed_redirect,
    pop_nonce,
    save_nonce,
)


def _session_max_age() -> int | None:
    try:
        raw = getattr(settings, "SESSION_COOKIE_AGE", None)
        if raw is None:
            return None
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def auth_config(request: HttpRequest) -> JsonResponse:
    """Expose minimal configuration needed by the frontend."""

    config = {
        "issuer": ISSUER,
        "clientId": OIDC_CLIENT_ID,
        "loginUrl": "/auth/login",
        "logoutUrl": "/auth/logout",
        "meUrl": "/auth/me",
        "callbackUrl": REDIRECT_URI,
        "responseMode": "form_post",
        "responseType": "id_token",
        "frontendRedirect": settings.FRONTEND_BASE_URL,
        "sessionMaxAgeSeconds": _session_max_age(),
        "providerConfigured": bool(settings.OIDC_PROVIDER_CONFIGURED),
    }
    return JsonResponse(config)


def auth_login(request: HttpRequest) -> HttpResponse:
    """Initiate an authorization request against the upstream ADFS server."""

    if not settings.OIDC_PROVIDER_CONFIGURED:
        return HttpResponseBadRequest("oidc not configured")

    target = request.GET.get("target") or request.GET.get("next")
    if not target or not is_allowed_redirect(target):
        return HttpResponseBadRequest("bad target")

    state = b64e(target)
    nonce = uuid.uuid4().hex
    save_nonce(request, nonce)

    params = {
        "client_id": OIDC_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_mode": "form_post",
        "response_type": "id_token",
        "scope": "openid profile email",
        "nonce": nonce,
        "state": state,
    }
    return redirect(f"{ADFS_AUTH_URL}?{urlencode(params)}")


@csrf_exempt
def auth_callback(request: HttpRequest) -> HttpResponse:
    """Handle the IdP form_post callback and establish a Django session."""

    if request.method != "POST":
        return HttpResponseBadRequest("form_post only")

    if not settings.OIDC_PROVIDER_CONFIGURED:
        return HttpResponseBadRequest("oidc not configured")

    id_token = request.POST.get("id_token")
    state = request.POST.get("state")
    if not id_token or not state:
        return HttpResponseBadRequest("missing id_token/state")

    try:
        target = b64d(state)
    except Exception:
        return HttpResponseBadRequest("invalid state")

    if not is_allowed_redirect(target):
        return HttpResponseBadRequest("forbidden target")

    expected_nonce = pop_nonce(request)
    try:
        decoded = jwt.decode(
            id_token,
            PUB_KEY,
            algorithms=["RS256"],
            audience=OIDC_CLIENT_ID,
            issuer=ISSUER,
            options={"verify_signature": True, "verify_exp": True},
        )
    except jwt.PyJWTError:
        return redirect(f"{target}?error=invalid_token")

    if expected_nonce is None or decoded.get("nonce") != expected_nonce:
        return redirect(f"{target}?error=invalid_nonce")

    usr_id = decoded.get("userid") or decoded.get("upn") or decoded.get("sub")
    name = decoded.get("username") or decoded.get("name") or ""
    email = decoded.get("mail") or decoded.get("email") or ""

    if not usr_id:
        return redirect(f"{target}?error=missing_userid")

    UserModel = get_user_model()
    user, created = UserModel.objects.get_or_create(
        username=usr_id,
        defaults={"email": email, "first_name": name},
    )
    updated = False
    if name and user.first_name != name:
        user.first_name = name
        updated = True
    if email and user.email != email:
        user.email = email
        updated = True
    if created or updated:
        user.save()

    login(request, user)
    return redirect(target)


def auth_me(request: HttpRequest) -> JsonResponse:
    """Return information about the currently authenticated user."""

    if not request.user.is_authenticated:
        return JsonResponse({"detail": "unauthorized"}, status=401)

    user = request.user
    payload = {
        "id": user.pk,
        "usr_id": user.get_username(),
        "username": user.get_username(),
        "name": user.first_name or user.get_username(),
        "email": user.email,
        "roles": [],
    }
    return JsonResponse(payload)


def auth_logout(request: HttpRequest) -> HttpResponse:
    """Terminate the local Django session and optionally trigger IdP logout."""

    logout(request)

    if request.method == "POST":
        response = JsonResponse({"logoutUrl": ADFS_LOGOUT_URL})
        response.delete_cookie(settings.SESSION_COOKIE_NAME)
        return response

    response = redirect(ADFS_LOGOUT_URL)
    response.delete_cookie(settings.SESSION_COOKIE_NAME)
    return response


__all__ = [
    "auth_config",
    "auth_login",
    "auth_callback",
    "auth_me",
    "auth_logout",
]
