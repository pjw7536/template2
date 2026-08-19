# =============================================================================
# 모듈 설명: 인증(Auth) 관련 HTTP 엔드포인트와 보조 뷰를 제공합니다.
# - 주요 대상: auth_config/auth_login/auth_callback/auth_me/auth_logout, FrontendRedirectView
# - 불변 조건: 리다이렉트 대상은 안전 검사 후 결정합니다.
# =============================================================================

"""인증(Auth) 관련 HTTP 엔드포인트 및 보조 뷰 모음.

- 주요 대상: auth_* 함수형 엔드포인트, FrontendRedirectView
- 주요 엔드포인트/클래스: auth_config/auth_login/auth_callback/auth_me/auth_logout, FrontendRedirectView
- 가정/불변 조건: 프론트엔드 베이스 URL은 settings 또는 요청에서 결정됨
"""
from __future__ import annotations

from django.conf import settings
from django.contrib.auth import login, logout
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from rest_framework.views import APIView

from api.auth import services as auth_services
from api.auth.services.oidc_validation import append_error_to_target
from api.common.services import api_error_response, resolve_frontend_target


class FrontendRedirectView(APIView):
    """요청을 canonical target의 프론트엔드 엔트리포인트로 리다이렉트합니다."""

    def get(  # 타입 검사 생략: type: ignore[override]
        self, request: HttpRequest, *args: object, **kwargs: object
    ) -> HttpResponse:
        """target 파라미터를 기준으로 안전한 리다이렉트 응답을 반환합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - HttpResponseRedirect: 302 리다이렉트 응답

        부작용:
        - 없음

        오류:
        - 없음

        예시 요청:
        - 예시 요청: GET /api/v1/auth/?target=/dashboard

        예시 응답:
        - 예시 응답: 302 Location: https://<frontend-base>/dashboard

        query 계약:
        - target만 허용
        """
        # -----------------------------------------------------------------------------
        unexpected_fields = sorted(set(request.GET) - {"target"})
        if unexpected_fields:
            return api_error_response(
                code="invalid_request",
                message="Unsupported query fields were provided.",
                field_errors={"unexpectedFields": unexpected_fields},
                status=400,
            )

        # 1) target 파라미터 추출
        # -----------------------------------------------------------------------------
        target = resolve_frontend_target(request.GET.get("target"), request=request)
        # -----------------------------------------------------------------------------
        # 2) 리다이렉트 응답 반환
        # -----------------------------------------------------------------------------
        return HttpResponseRedirect(target)


def auth_config(request: HttpRequest):
    """프런트엔드에 필요한 최소 OIDC 설정을 제공합니다.

    입력:
    - 요청: Django HttpRequest

    반환:
    - JsonResponse: OIDC 설정 값

    부작용:
    - 없음

    오류:
    - 없음

    예시 요청:
    - 예시 요청: GET /api/v1/auth/config

    예시 응답:
    - 예시 응답: 200 {"issuer": "...", "clientId": "...", "loginUrl": "...", "locale": "ko-KR", "timeZone": "Asia/Seoul"}

    snake/camel 호환:
    - 해당 없음(요청 바디 없음)
    """

    return JsonResponse(auth_services.auth_config())


def auth_login(request: HttpRequest):
    """ADFS 로그인 시작 엔드포인트입니다.

    입력:
    - 요청: Django HttpRequest

    반환:
    - HttpResponse: ADFS authorize로 리다이렉트 응답

    부작용:
    - 세션에 nonce 저장

    오류:
    - 400: OIDC 설정이 비활성화된 경우

    예시 요청:
    - 예시 요청: GET /api/v1/auth/login?target=/dashboard

    예시 응답:
    - 예시 응답: 302 Location: https://<adfs-auth>/?client_id=...

    query 계약:
    - target만 허용
    """

    unexpected_fields = sorted(set(request.GET) - {"target"})
    if unexpected_fields:
        return api_error_response(
            code="invalid_request",
            message="Unsupported query fields were provided.",
            field_errors={"unexpectedFields": unexpected_fields},
            status=400,
        )
    requested_target = request.GET.get("target")
    result = auth_services.auth_login(requested_target=requested_target, request=request)
    if result.bad_request_message:
        return api_error_response(
            code="external_dependency_error",
            message="OIDC provider is not configured.",
            details={"reason": result.bad_request_message},
            status=503,
        )
    return redirect(result.authorize_url)


@csrf_exempt
def auth_callback(request: HttpRequest):
    """ADFS form_post 콜백을 처리하고 세션 로그인을 수행합니다.

    입력:
    - 요청: Django HttpRequest (form_post)

    반환:
    - HttpResponse: 리다이렉트 또는 오류 응답

    부작용:
    - 사용자 생성/갱신 및 세션 로그인

    오류:
    - 400: 잘못된 메서드, 설정 비활성화, 파라미터 누락
    - 302: 토큰 오류/nonce 오류 시 error 쿼리를 포함해 리다이렉트

    예시 요청:
    - 예시 요청: POST /api/v1/auth/callback
      폼 예시: id_token=<jwt>&state=<b64url>

    예시 응답:
    - 예시 응답: 302 Location: https://<frontend>/?error=invalid_token

    snake/camel 호환:
    - 해당 없음(form_post 키를 그대로 사용)
    """

    if request.method != "POST":
        return api_error_response(
            code="invalid_request",
            message="OIDC callback requires form_post.",
            field_errors={"method": ["POST is required."]},
            status=400,
        )

    id_token = request.POST.get("id_token")
    state = request.POST.get("state")
    if not id_token or not state:
        field_errors = {}
        if not id_token:
            field_errors["id_token"] = ["This field is required."]
        if not state:
            field_errors["state"] = ["This field is required."]
        return api_error_response(
            code="invalid_request",
            message="Required OIDC callback fields are missing.",
            field_errors=field_errors,
            status=400,
        )

    result = auth_services.auth_callback(
        request=request,
        raw_id_token=id_token,
        state=state,
    )
    if result.bad_request_message:
        return api_error_response(
            code="external_dependency_error",
            message="OIDC provider is not configured.",
            details={"reason": result.bad_request_message},
            status=503,
        )
    if result.error_code:
        return redirect(append_error_to_target(str(result.target), result.error_code))

    login(request, result.user)
    return redirect(result.target)


@api_view(["GET"])
def auth_me(request: HttpRequest):
    """현재 로그인한 사용자 정보를 반환합니다.

    입력:
    - 요청: Django HttpRequest

    반환:
    - JsonResponse: 사용자 정보 또는 에러

    부작용:
    - 없음

    오류:
    - 401: 미인증 사용자

    예시 요청:
    - 예시 요청: GET /api/v1/auth/me

    예시 응답:
    - 예시 응답: 200 {"id": 1, "knoxId": "...", "username": "...", "scopeAccess": {"portal": {...}}}

    snake/camel 호환:
    - 해당 없음(요청 바디 없음)
    """

    if not request.user.is_authenticated:
        return api_error_response(
            code="authentication_required",
            message="Authentication is required.",
            status=401,
        )

    return JsonResponse(auth_services.auth_me(user=request.user))


def auth_logout(request: HttpRequest):
    """로컬 세션 종료 후 IdP 로그아웃 URL을 안내하거나 리다이렉트합니다.

    입력:
    - 요청: Django HttpRequest

    반환:
    - HttpResponse: JSON 응답 또는 리다이렉트

    부작용:
    - Django 세션 종료 및 세션 쿠키 삭제

    오류:
    - 없음

    예시 요청:
    - 예시 요청: POST /api/v1/auth/logout
    - 예시 요청: GET /api/v1/auth/logout

    예시 응답:
    - 예시 응답: 200 {"logoutUrl": "https://<adfs-logout>"}
    - 예시 응답: 302 Location: https://<adfs-logout>

    snake/camel 호환:
    - 해당 없음(요청 바디 없음)
    """

    logout_url = auth_services.auth_logout()
    logout(request)

    def _delete_session_cookie(response: HttpResponse) -> HttpResponse:
        """세션 쿠키를 삭제한 응답을 반환합니다."""

        response.delete_cookie(settings.SESSION_COOKIE_NAME)
        return response

    if request.method == "POST":
        response = JsonResponse({"logoutUrl": logout_url})
        return _delete_session_cookie(response)

    response = redirect(logout_url)
    return _delete_session_cookie(response)


__all__ = [
    "FrontendRedirectView",
    "auth_callback",
    "auth_config",
    "auth_login",
    "auth_logout",
    "auth_me",
]
