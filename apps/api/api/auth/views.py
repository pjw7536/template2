"""Google OAuth based authentication entrypoints.

이 모듈은 Google OAuth/OIDC 로그인 플로우의 시작(authorization request)과
콜백 처리(token 교환 → userinfo 조회 → 로컬 유저 upsert → 세션 로그인)를 담당합니다.

# 전체 흐름(요약)
1) /auth/google/start (GoogleOAuthStartView)
   - state 생성 후 세션에 저장
   - (선택) next 쿼리 파라미터를 세션에 저장
   - Google Authorization Endpoint로 302 리다이렉트

2) /auth/google/callback (GoogleOAuthCallbackView)
   - 에러 파라미터 있으면 즉시 프론트엔드로 에러 리다이렉트
   - state 검증(세션에서 꺼낸 값과 비교) → CSRF 방어
   - code로 토큰 교환(authorization_code grant)
   - access_token으로 userinfo 호출
   - email 기준으로 로컬 유저 upsert(없으면 생성/있으면 프로필 갱신)
   - Django session 로그인 후 프론트엔드로 최종 리다이렉트

# 필수 settings (예시)
GOOGLE_OIDC_CONFIGURED = True
GOOGLE_OAUTH_CLIENT_ID = "..."
GOOGLE_OAUTH_CLIENT_SECRET = "..."
GOOGLE_OAUTH_SCOPE = "openid email profile"
GOOGLE_OAUTH_ACCESS_TYPE = "offline"   # refresh_token 필요 시
GOOGLE_OAUTH_PROMPT = "consent"        # 매번 동의화면 강제 필요 시
GOOGLE_OAUTH_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_OAUTH_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_OAUTH_USERINFO_ENDPOINT = "https://openidconnect.googleapis.com/v1/userinfo"
# (선택) 콜백 URI 고정 필요 시(리버스 프록시/도메인 불일치 문제 대응):
# GOOGLE_OAUTH_REDIRECT_URI = "https://example.com/auth/google/callback"

주의: 프록시 뒤에 있을 경우 Django의 SECURE_PROXY_SSL_HEADER, USE_X_FORWARDED_HOST
등이 정확히 설정되어야 request.build_absolute_uri 가 올바른 https URL을 만듭니다.
"""
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
    """Google 토큰 응답에서 사용하는 핵심 필드만 담아두는 DTO."""
    access_token: str
    id_token: Optional[str]
    refresh_token: Optional[str]


class GoogleOAuthException(Exception):
    """콜백 처리 중 발생하는 내부 예외.

    - message: 로그용/디버깅용 메시지
    - error_code: 프론트엔드에 쿼리 파라미터로 넘길 짧은 에러 코드
    """
    def __init__(self, message: str, error_code: str = "oauth_error"):
        super().__init__(message)
        self.error_code = error_code


def _callback_uri(request: HttpRequest) -> str:
    """리다이렉트(콜백) URI를 결정.

    1) settings.GOOGLE_OAUTH_REDIRECT_URI 가 설정되어 있으면 우선 사용
       - 프록시/도메인 불일치로 인해 build_absolute_uri가 깨지는 경우 유용
    2) 없으면 reverse("google-oauth-callback") 기준으로 현재 요청의 호스트로 절대경로 생성
    """
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
    """최종적으로 프론트엔드로 이동할 URL을 만들어 302 응답.

    - next_value: 로그인 전 프론트에서 전달한 다음 페이지 경로(세션에 저장해둠)
    - error: 에러가 있다면 authError 쿼리 스트링으로 전달
    """
    target = resolve_frontend_target(next_value, request=request)
    if error:
        target = append_query_params(target, {"authError": error})
    return HttpResponseRedirect(target)


def _exchange_code_for_tokens(request: HttpRequest, code: str) -> GoogleOAuthResult:
    """Authorization Code를 Access Token 등으로 교환.

    Google OAuth Token Endpoint 에 요청:
      grant_type=authorization_code
      code, client_id, client_secret, redirect_uri 포함

    예외 처리:
    - 네트워크/타임아웃: token_request_failed
    - 4xx/5xx: token_request_failed
    - JSON 파싱 실패: token_parse_error
    - access_token 누락: token_missing
    """
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
            timeout=10,  # 네트워크 대기 상한
        )
    except requests.RequestException as exc:
        # 네트워크/연결 관련 오류
        raise GoogleOAuthException("token_request_failed", "token_request_failed") from exc

    if response.status_code >= 400:
        # 토큰 교환 실패(잘못된 code, 클라이언트 비밀 오류 등)
        logger.warning(
            "Google token request failed",
            extra={"status": response.status_code, "body": response.text[:200]},
        )
        raise GoogleOAuthException("token_request_failed", "token_request_failed")

    try:
        data = response.json()
    except ValueError as exc:
        # JSON 디코딩 실패
        raise GoogleOAuthException("token_parse_error", "token_parse_error") from exc

    access_token = data.get("access_token")
    if not access_token:
        # 정상 교환이면 필수
        raise GoogleOAuthException("token_missing", "token_missing")

    return GoogleOAuthResult(
        access_token=access_token,
        id_token=data.get("id_token"),              # OIDC ID Token (필요 시 검증 추가 가능)
        refresh_token=data.get("refresh_token"),    # offline 액세스 시 발급
    )


def _fetch_user_info(access_token: str) -> Dict[str, Any]:
    """Access Token으로 Google UserInfo(OpenID) 조회.

    - 성공 시: email, given_name, family_name 등 포함한 dict 반환
    - 실패 시: userinfo_failed

    참고: OIDC의 표준 userinfo 엔드포인트를 사용
    """
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
    """Google userinfo를 바탕으로 로컬 유저를 생성/갱신.

    - 식별 키: email (없으면 실패)
    - 신규: username은 email의 @ 앞부분을 기본값으로 사용
    - 갱신: given_name/family_name 정보를 first_name/last_name에 반영
    - ensure_user_profile(user): 프로필 보조 테이블 보장(없으면 생성)

    반환: Django User 인스턴스
    """
    email = user_info.get("email")
    if not isinstance(email, str) or not email:
        # 이메일은 로컬 계정 식별에 필수
        raise GoogleOAuthException("email_missing", "email_missing")

    UserModel = get_user_model()
    user = UserModel.objects.filter(email__iexact=email).first()
    if user is None:
        # 신규 사용자 생성
        username = email.split("@")[0] or email
        user = UserModel.objects.create_user(
            username=username,
            email=email,
        )

    # 사용자 이름 갱신 로직(있을 때만 덮어쓰기)
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

    # 유저 프로필 보조 모델 생성/보장(앱마다 정의 다름)
    ensure_user_profile(user)
    return user


class GoogleOAuthStartView(View):
    """Google OAuth 인증 플로우 시작 엔드포인트(GET).

    - provider 구성 여부(settings.GOOGLE_OIDC_CONFIGURED) 확인
    - CSRF 방어용 state를 세션에 저장
    - (선택) next 파라미터를 세션에 저장해 콜백 완료 후 프론트 이동에 사용
    - Google Authorization Endpoint로 리다이렉트
    """

    def get(self, request: HttpRequest) -> HttpResponseRedirect:
        if not settings.GOOGLE_OIDC_CONFIGURED:
            # 서버 측에 Provider 설정이 안 된 경우
            return _build_frontend_redirect(request, error="provider_not_configured")

        # CSRF 방어용 state(세션 저장 → 콜백에서 일치 여부 확인)
        state = secrets.token_urlsafe(32)
        request.session["google_oauth_state"] = state

        # 로그인 완료 후 돌아갈 프론트 경로(next)를 세션에 저장(없으면 삭제)
        next_value = request.GET.get("next")
        if next_value:
            request.session["google_oauth_next"] = str(next_value)
        else:
            request.session.pop("google_oauth_next", None)

        # Google Authorization Request 파라미터 구성
        params = {
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "response_type": "code",                      # Authorization Code Flow
            "scope": settings.GOOGLE_OAUTH_SCOPE,         # "openid email profile" 등
            "redirect_uri": _callback_uri(request),
            "state": state,
            "access_type": settings.GOOGLE_OAUTH_ACCESS_TYPE,  # "offline" 시 refresh_token
            "prompt": settings.GOOGLE_OAUTH_PROMPT,            # "consent" 등
        }
        auth_url = f"{settings.GOOGLE_OAUTH_AUTH_ENDPOINT}?{urlencode(params)}"
        return HttpResponseRedirect(auth_url)


class GoogleOAuthCallbackView(View):
    """Google OAuth 콜백 엔드포인트(GET).

    - 에러 파라미터가 있으면 즉시 종료
    - state 검증(세션과 비교)로 요청 위조 방지
    - code 없으면 에러
    - 토큰 교환 → userinfo 조회 → 로컬 유저 upsert
    - Django 인증 세션(login) 설정 후 프론트엔드로 리다이렉트
    """

    def get(self, request: HttpRequest) -> HttpResponseRedirect:
        # start에서 저장해둔 next 값을 회수(일회성 → pop)
        next_value = request.session.pop("google_oauth_next", None)

        if not settings.GOOGLE_OIDC_CONFIGURED:
            return _build_frontend_redirect(request, next_value=next_value, error="provider_not_configured")

        # 사용자가 동의를 거부하거나 기타 오류가 발생했을 때
        error_param = request.GET.get("error")
        if error_param:
            logger.warning("Google OAuth returned error", extra={"error": error_param})
            return _build_frontend_redirect(request, next_value=next_value, error="access_denied")

        # CSRF 방어: start에서 만든 state와 일치해야 함
        state = request.GET.get("state")
        stored_state = request.session.pop("google_oauth_state", None)
        if not state or not stored_state or state != stored_state:
            return _build_frontend_redirect(request, next_value=next_value, error="invalid_state")

        # Authorization Code 필수
        code = request.GET.get("code")
        if not code:
            return _build_frontend_redirect(request, next_value=next_value, error="missing_code")

        try:
            # 1) code → token 교환
            tokens = _exchange_code_for_tokens(request, code)
            # 2) access_token → userinfo 조회
            user_info = _fetch_user_info(tokens.access_token)
            # 3) 로컬 유저 upsert
            user = _upsert_user(user_info)
        except GoogleOAuthException as exc:
            # 예측 가능한 오류: 간단 코드로 프론트에 전달
            logger.exception("Google OAuth callback failed: %s", exc)
            return _build_frontend_redirect(request, next_value=next_value, error=exc.error_code)

        # 세션 로그인: 기본 ModelBackend 사용
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return _build_frontend_redirect(request, next_value=next_value)


__all__ = [
    "GoogleOAuthCallbackView",
    "GoogleOAuthStartView",
]
