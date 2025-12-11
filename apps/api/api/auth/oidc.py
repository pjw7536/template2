"""Session-backed authentication endpoints using an id_token-only OIDC flow."""
from __future__ import annotations

import uuid
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model, login, logout
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseBadRequest,
    JsonResponse,
)
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt

from api.common.utils import resolve_frontend_target
from api.oidc_utils import (
    ADFS_AUTH_URL,       # ADFS authorize endpoint (…/adfs/oauth2/authorize)
    ADFS_LOGOUT_URL,     # ADFS logout endpoint
    ISSUER,              # 토큰 발급자(iss)
    OIDC_CLIENT_ID,      # audience 검증에 사용
    PUB_KEY,             # RS256 공개키(PEM 문자열 또는 공개키 객체)
    REDIRECT_URI,        # 콜백 URL (ADFS 등록값과 완전히 동일해야 함)
    b64d,                # urlsafe base64 decode (bytes 반환)
    b64e,                # urlsafe base64 encode (str 반환)
    is_allowed_redirect, # 화이트리스트 기반 리다이렉트 검증
    pop_nonce,           # 세션에서 nonce pop
    save_nonce,          # 세션에 nonce 저장
)


# =============================================================================
# 내부 유틸: 설정 값 및 공통 처리
# =============================================================================


def _session_max_age() -> Optional[int]:
    """
    SESSION_COOKIE_AGE를 안전하게 정수로 변환해서 반환.
    - 양수일 때만 반환
    - 그 외에는 None
    """
    try:
        raw = getattr(settings, "SESSION_COOKIE_AGE", None)
        if raw is None:
            return None
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _provider_configured() -> bool:
    """
    OIDC_PROVIDER_CONFIGURED 값을 안전하게 bool로 변환해서 반환.
    설정이 없거나 False면 False 반환.
    """
    return bool(getattr(settings, "OIDC_PROVIDER_CONFIGURED", False))


def _decode_state_to_str(state: str, request: HttpRequest) -> str:
    """
    state(b64url)를 문자열로 디코드.
    - 디코드 실패 시: 안전한 기본 프론트엔드 경로로 폴백.
    """
    try:
        decoded_state = b64d(state)
    except Exception:
        # state 자체가 깨졌다면 기본 프론트엔드로
        return resolve_frontend_target(None, request=request)

    if isinstance(decoded_state, str):
        return decoded_state

    try:
        return decoded_state.decode("utf-8")
    except Exception:
        # 인코딩 문제 시 최대한 복구
        return str(decoded_state, "utf-8", errors="ignore")


def _safe_redirect_target(target: Optional[str], request: HttpRequest) -> str:
    """
    target이 None이거나 화이트리스트에서 벗어나면
    안전한 프런트엔드 경로로 대체해서 반환.
    """
    resolved = resolve_frontend_target(target, request=request)
    if not is_allowed_redirect(resolved):
        return resolve_frontend_target(None, request=request)
    return resolved


def _ensure_pubkey_ready() -> None:
    """
    PUB_KEY가 준비되지 않은 경우 RuntimeError 발생.
    - 잘못된 설정으로 인한 500을 "조기에" 명확하게 터뜨리기 위함.
    """
    if not PUB_KEY:
        raise RuntimeError("OIDC public key (PUB_KEY) is not configured.")
    # 필요하다면 PUB_KEY 타입 검사 추가 가능 (예: isinstance(PUB_KEY, str))


def _redirect_with_error(target: str, error_code: str) -> HttpResponse:
    """
    공통 에러 리다이렉트 생성.
    - target: 이미 _safe_redirect_target 를 거친 URL 이어야 함.
    """
    separator = "&" if "?" in target else "?"
    return redirect(f"{target}{separator}error={error_code}")


def _decode_id_token(raw_id_token: str) -> Dict[str, Any]:
    """
    id_token(JWT)을 디코드해서 클레임 딕셔너리 반환.

    현재는 verify 옵션을 False로 둔 상태(ADFS 연결/키 이슈 등 디버깅 단계 가정)지만,
    향후 실제 운영 시에는 verify_* 옵션을 True 쪽으로 올리는 게 안전함.
    """
    return jwt.decode(
        raw_id_token,
        PUB_KEY,
        algorithms=["RS256"],
        options={
            # TODO: 운영 환경에서는 아래 옵션들을 True로 설정하고
            #       적절한 leeway/clock_skew 조정 및 iss/aud 검증을 켜는 것이 안전함.
            "verify_signature": False,
            "verify_exp": False,
            "verify_aud": False,
            "verify_iss": False,
        },
    )


def _split_display_name(display_name: str) -> Tuple[str, str]:
    """
    '홍길동' 같은 값을 first_name='홍', last_name='길동' 으로 잘라주는 함수.

    - 공백이 있을 경우: 서양식 이름 가정 → 첫 토큰을 first_name, 나머지를 last_name.
    - 공백이 없을 경우: 한국식 이름 가정 → 첫 글자(성)를 first_name, 나머지를 last_name.
    """
    name = (display_name or "").strip()
    if not name:
        return "", ""

    if " " in name:
        parts = name.split()
        if len(parts) == 1:
            return parts[0], ""
        return parts[0], " ".join(parts[1:])

    # 공백이 없는 경우(예: 홍길동)
    if len(name) == 1:
        return name, ""
    return name[0], name[1:]


def _extract_user_info_from_claims(claims: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """
    IdP(ADFS)에서 내려주는 고정 클레임 패턴 기반으로 사용자 정보 추출.

    - username : '홍길동' 형태의 이름
    - deptname : 부서명
    - sabun    : 사번 (Django username 필드로 사용)
    - mail     : 이메일
    """
    raw_username = claims.get("username") or ""
    deptname = claims.get("deptname") or ""
    sabun = claims.get("sabun") or ""
    email = claims.get("mail") or ""

    first_name, last_name = _split_display_name(raw_username)

    return {
        "raw_username": raw_username,
        "first_name": first_name,
        "last_name": last_name,
        "deptname": deptname,
        "sabun": sabun,
        "email": email,
    }


# =============================================================================
# Public endpoints
# =============================================================================


def auth_config(request: HttpRequest) -> JsonResponse:
    """
    프런트엔드에서 필요한 최소 설정 제공.
    SPA가 로그인/로그아웃/콜백 경로를 알 수 있게 해준다.
    """
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
    ADFS 로그인 시작 엔드포인트.

    - target(next) 파라미터를 받아 state로 인코딩
    - nonce를 세션에 저장
    - ADFS authorize 엔드포인트로 리다이렉트
      (response_mode=form_post, response_type=id_token)
    """
    if not _provider_configured():
        return HttpResponseBadRequest("oidc not configured")

    requested_target = request.GET.get("target") or request.GET.get("next")
    target = _safe_redirect_target(requested_target, request)
    state = b64e(target)

    nonce = uuid.uuid4().hex
    save_nonce(request, nonce)  # 콜백에서 pop 하여 재사용 방지

    params = {
        "client_id": OIDC_CLIENT_ID,
        # ADFS에 등록된 redirect_uri와 완전히 일치해야 함
        "redirect_uri": REDIRECT_URI,
        "response_mode": "form_post",  # 폼 POST로 id_token 전달
        "response_type": "id_token",   # implicit id_token-only
        "scope": "openid profile email",
        "nonce": nonce,
        "state": state,
    }
    return redirect(f"{ADFS_AUTH_URL}?{urlencode(params)}")


@csrf_exempt
def auth_callback(request: HttpRequest) -> HttpResponse:
    """
    ADFS로부터의 form_post 콜백 처리:

    1. HTTP 메서드 검증 (POST만 허용)
    2. id_token / state 파라미터 확인
    3. state 복원 → target 문자열 → 안전한 redirect 타깃으로 정규화
    4. 세션 nonce vs id_token.nonce 비교
    5. id_token 디코드 (현재 verify 옵션은 False 상태)
    6. username / deptname / sabun / mail 기반으로 유저 매핑
    7. Django 세션 로그인 후 target으로 리다이렉트
    """
    if request.method != "POST":
        return HttpResponseBadRequest("form_post only")

    if not _provider_configured():
        return HttpResponseBadRequest("oidc not configured")

    # form_post에서 넘어온 필수 파라미터
    id_token = request.POST.get("id_token")
    state = request.POST.get("state")
    if not id_token or not state:
        return HttpResponseBadRequest("missing id_token/state")

    # state 복원 → target 문자열 → 안전한 redirect 경로로 정규화
    raw_target = _decode_state_to_str(state, request)
    target = _safe_redirect_target(raw_target, request)

    # 세션에서 nonce를 꺼내 검증 준비
    expected_nonce = pop_nonce(request)

    # 공개키 준비 확인 (설정 누락 시 조기에 에러 발생)
    _ensure_pubkey_ready()

    # id_token 디코드
    try:
        decoded = _decode_id_token(id_token)
    except jwt.ExpiredSignatureError:
        return _redirect_with_error(target, "token_expired")
    except jwt.InvalidIssuerError:
        return _redirect_with_error(target, "invalid_iss")
    except jwt.InvalidAudienceError:
        return _redirect_with_error(target, "invalid_aud")
    except jwt.PyJWTError:
        # 기타 서명/포맷 오류 등
        return _redirect_with_error(target, "invalid_token")

    # nonce 일치 여부 확인 (재전송/재사용 방지)
    if expected_nonce is None or decoded.get("nonce") != expected_nonce:
        return _redirect_with_error(target, "invalid_nonce")

    # username / deptname / sabun / mail 기반 사용자 정보 추출
    info = _extract_user_info_from_claims(decoded)
    first_name = info["first_name"]
    last_name = info["last_name"]
    deptname = info["deptname"]
    sabun = info["sabun"]
    email = info["email"]

    # Django username 필드는 sabun을 사용 (항상 온다고 가정)
    if not sabun:
        return _redirect_with_error(target, "missing_sabun")

    # Django 유저 생성/업데이트
    UserModel = get_user_model()
    user, created = UserModel.objects.get_or_create(
        username=str(sabun),  # 사번 = Django username
        defaults={
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
        },
    )

    update_fields = []

    # 이름 / 이메일 갱신
    if first_name and user.first_name != first_name:
        user.first_name = first_name
        update_fields.append("first_name")

    if last_name and getattr(user, "last_name", None) != last_name:
        try:
            user.last_name = last_name
            update_fields.append("last_name")
        except Exception:
            # CustomUser에 last_name 이 없을 수도 있으니 방어적으로 처리
            pass

    if email and user.email != email:
        user.email = email
        update_fields.append("email")

    # deptname 필드가 User 모델에 있다면 같이 업데이트
    if hasattr(user, "department") and deptname and user.department != deptname:
        user.department = deptname
        update_fields.append("department")

    if created or update_fields:
        user.save(update_fields=update_fields or None)

    # 세션 로그인 후 프런트로 리다이렉트
    login(request, user)
    return redirect(target)


def auth_me(request: HttpRequest) -> JsonResponse:
    """
    현재 로그인한 사용자 정보 반환.
    - 미로그인 시: 401 unauthorized
    """
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "unauthorized"}, status=401)

    user = request.user
    payload = {
        "id": user.pk,
        "usr_id": user.get_username(),     # = 사번
        "username": user.get_username(),   # = 사번
        "name": (user.first_name or "") + (user.last_name or ""),
        "email": user.email,
        "roles": [],  # 필요 시 롤/권한 매핑 로직 추가
        "department": getattr(user, "department", None),
        "line": getattr(user, "line", None),
        "sdwt": getattr(user, "sdwt", None),
    }
    return JsonResponse(payload)


def auth_logout(request: HttpRequest) -> HttpResponse:
    """
    로컬 Django 세션 종료 후, IdP 로그아웃 URL 안내/리다이렉트.

    - POST: JSON으로 logoutUrl 반환 (SPA가 클라이언트에서 직접 이동)
    - GET: 서버에서 바로 IdP 로그아웃으로 리다이렉트
    """
    logout(request)

    # 세션 쿠키 제거
    def _delete_session_cookie(resp: HttpResponse) -> HttpResponse:
        resp.delete_cookie(settings.SESSION_COOKIE_NAME)
        return resp

    if request.method == "POST":
        response = JsonResponse({"logoutUrl": ADFS_LOGOUT_URL})
        return _delete_session_cookie(response)

    response = redirect(ADFS_LOGOUT_URL)
    return _delete_session_cookie(response)


__all__ = [
    "auth_config",
    "auth_login",
    "auth_callback",
    "auth_me",
    "auth_logout",
]
