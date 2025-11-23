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
    ADFS_AUTH_URL,         # ADFS authorize endpoint (…/adfs/oauth2/authorize)
    ADFS_LOGOUT_URL,       # ADFS logout endpoint
    ISSUER,                # 토큰 발급자(iss)
    OIDC_CLIENT_ID,        # audience 검증에 사용
    PUB_KEY,               # RS256 공개키(PEM 문자열 또는 공개키 객체)
    REDIRECT_URI,          # 콜백 URL (ADFS 등록값과 완전히 동일해야 함)
    b64d,                  # urlsafe base64 decode (bytes 반환)
    b64e,                  # urlsafe base64 encode (str 반환)
    is_allowed_redirect,   # 화이트리스트 기반 리다이렉트 검증
    pop_nonce,             # 세션에서 nonce pop
    save_nonce,            # 세션에 nonce 저장
)
from .views.utils import resolve_frontend_target


# ---------------------------------------------------------------------------
# 내부 유틸: 설정 값과 타입/상태를 조기에 점검해 500을 예방
# ---------------------------------------------------------------------------

def _session_max_age() -> int | None:
    """SESSION_COOKIE_AGE가 양의 정수일 때만 반환."""
    try:
        raw = getattr(settings, "SESSION_COOKIE_AGE", None)
        if raw is None:
            return None
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _provider_configured() -> bool:
    """OIDC_PROVIDER_CONFIGURED를 안전하게 읽기 (누락 시 False)."""
    return bool(getattr(settings, "OIDC_PROVIDER_CONFIGURED", False))


def _decode_state_to_str(state: str, request: HttpRequest) -> str:
    """
    state(b64url)를 안전하게 디코드하여 문자열로 반환.
    실패 시, 안전한 기본 프런트엔드 경로로 폴백.
    """
    try:
        target_bytes = b64d(state)  # bytes
        try:
            return target_bytes.decode("utf-8")
        except Exception:
            # 비표준 인코딩일 경우 최대한 복구
            return str(target_bytes, "utf-8", errors="ignore")
    except Exception:
        # state 자체가 유효하지 않으면 기본 프런트엔드로 보냄
        return resolve_frontend_target(None, request=request)


def _safe_redirect_target(target: str | None, request: HttpRequest) -> str:
    """
    target이 유효하지 않거나 화이트리스트에서 벗어나면
    안전한 프런트엔드 경로로 대체.
    """
    resolved = resolve_frontend_target(target, request=request)
    if not is_allowed_redirect(resolved):
        resolved = resolve_frontend_target(None, request=request)
    return resolved


def _ensure_pubkey_ready() -> None:
    """
    PUB_KEY가 올바르게 준비되지 않으면 조기 예외로 명확히 알림.
    - PEM 문자열 또는 공개키 객체여야 함.
    """
    if not PUB_KEY:
        raise RuntimeError("OIDC public key (PUB_KEY) is not configured.")
    # 추가로 타입검사를 원하면 여기에 수행 가능 (예: isinstance(PUB_KEY, str))


# ---------------------------------------------------------------------------
# Public endpoints
# ---------------------------------------------------------------------------

def auth_config(request: HttpRequest) -> JsonResponse:
    """프런트엔드에서 필요한 최소 설정 제공."""
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
        "providerConfigured": _provider_configured(),
    }
    return JsonResponse(config)


def auth_login(request: HttpRequest) -> HttpResponse:
    """
    ADFS 로그인 시작.
    - target(next) 파라미터를 받아 state로 인코딩
    - nonce를 세션에 저장
    - ADFS authorize 엔드포인트로 리다이렉트 (response_mode=form_post, response_type=id_token)
    """
    if not _provider_configured():
        return HttpResponseBadRequest("oidc not configured")

    requested_target = request.GET.get("target") or request.GET.get("next")
    target = _safe_redirect_target(requested_target, request)
    state = b64e(target)

    nonce = uuid.uuid4().hex
    save_nonce(request, nonce)  # 콜백에서 pop하여 재사용 방지

    params = {
        "client_id": OIDC_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,           # ADFS에 등록된 redirect_uri와 완전히 일치해야 함
        "response_mode": "form_post",           # 폼 POST로 id_token 전달
        "response_type": "id_token",            # implicit id_token-only
        "scope": "openid profile email",
        "nonce": nonce,
        "state": state,
    }
    return redirect(f"{ADFS_AUTH_URL}?{urlencode(params)}")


@csrf_exempt
def auth_callback(request: HttpRequest) -> HttpResponse:
    """
    ADFS로부터의 form_post 콜백 처리:
    - state 복원 및 redirect 타깃 검증
    - session nonce vs id_token.nonce 비교
    - id_token 서명/만료/iss/aud 검증
    - 사용자 생성/업데이트 후 Django 세션 로그인
    """
    if request.method != "POST":
        return HttpResponseBadRequest("form_post only")

    if not _provider_configured():
        return HttpResponseBadRequest("oidc not configured")

    # form_post에서 넘어온 파라미터
    id_token = request.POST.get("id_token")
    state = request.POST.get("state")
    if not id_token or not state:
        return HttpResponseBadRequest("missing id_token/state")

    # state 복원 → target 문자열
    target = _decode_state_to_str(state, request)
    target = _safe_redirect_target(target, request)

    # 세션에서 nonce를 꺼내 검증 준비
    expected_nonce = pop_nonce(request)

    # 공개키 준비 확인(오동작 시 500으로 숨지 않게 명확한 오류)
    _ensure_pubkey_ready()

    # RS256 서명/만료/iss/aud 검증
    try:
        decoded = jwt.decode(
            id_token,
            PUB_KEY,
            algorithms=["RS256"],
            options={
                "verify_signature": False,
                "verify_exp": False,
                "verify_aud": False,   
                "verify_iss": False,
            },
        )
    except jwt.ExpiredSignatureError:
        return redirect(f"{target}?error=token_expired")
    except jwt.InvalidIssuerError:
        return redirect(f"{target}?error=invalid_iss")
    except jwt.InvalidAudienceError:
        return redirect(f"{target}?error=invalid_aud")
    except jwt.PyJWTError:
        # 기타 서명/포맷 오류 등
        return redirect(f"{target}?error=invalid_token")

    # nonce 일치 여부 확인 (재전송/재사용 방지)
    if expected_nonce is None or decoded.get("nonce") != expected_nonce:
        return redirect(f"{target}?error=invalid_nonce")

    # 사용자 식별 정보 추출(ADFS 클레임 다양성 대비)
    usr_id = decoded.get("userid") or decoded.get("upn") or decoded.get("sub")
    name = decoded.get("username") or decoded.get("name") or ""
    email = decoded.get("mail") or decoded.get("email") or ""

    if not usr_id:
        return redirect(f"{target}?error=missing_userid")

    # Django 유저 생성/업데이트
    UserModel = get_user_model()
    user, created = UserModel.objects.get_or_create(
        username=str(usr_id),
        defaults={"email": email, "first_name": name},
    )

    # 필요한 필드만 갱신
    update_fields = []
    if name and user.first_name != name:
        user.first_name = name
        update_fields.append("first_name")
    if email and user.email != email:
        user.email = email
        update_fields.append("email")
    if created or update_fields:
        user.save(update_fields=update_fields or None)

    # 세션 로그인 후 프런트로 리다이렉트
    login(request, user)
    return redirect(target)


def auth_me(request: HttpRequest) -> JsonResponse:
    """현재 로그인한 사용자 정보 반환 (미로그인 시 401)."""
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "unauthorized"}, status=401)

    user = request.user
    payload = {
        "id": user.pk,
        "usr_id": user.get_username(),
        "username": user.get_username(),
        "name": user.first_name or user.get_username(),
        "email": user.email,
        "roles": [],  # 필요 시 롤/권한 매핑
    }
    return JsonResponse(payload)


def auth_logout(request: HttpRequest) -> HttpResponse:
    """
    로컬 Django 세션 종료 후, IdP 로그아웃 URL 안내/리다이렉트.
    - POST: JSON으로 logoutUrl 반환 (SPA가 직접 이동)
    - GET: 서버에서 바로 IdP 로그아웃으로 리다이렉트
    """
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
