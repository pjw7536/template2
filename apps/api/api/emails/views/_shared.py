# =============================================================================
# 모듈 설명: Emails HTTP view 공통 검증과 응답 helper를 제공합니다.
# =============================================================================

from __future__ import annotations

from typing import Any, Iterable, Optional

from django.http import HttpRequest, JsonResponse

from api.common.services import parse_json_body

from ..permissions import resolve_access_control, resolve_email_access_denial
from ..serializers import EmailRequestValidationError, serialize_email_page

def _check_email_access(
    *,
    request: HttpRequest,
    email: Any,
    is_privileged: bool,
    accessible: Optional[set[str]],
) -> Optional[JsonResponse]:
    """공통 이메일 접근 검증 결과를 HTTP 에러 응답으로 변환합니다.

    입력:
        요청: Django HttpRequest.
        email: Email 인스턴스 또는 None.
        is_privileged: 특권 사용자 여부.
        accessible: 접근 가능한 user_sdwt_prod 집합.
    반환:
        에러 응답(JsonResponse) 또는 None(접근 허용).
    부작용:
        없음.
    오류:
        없음(에러는 JsonResponse로 반환).
    """
    denial = resolve_email_access_denial(
        user=request.user,
        email=email,
        is_privileged=is_privileged,
        accessible=accessible,
    )
    if denial == "not_found":
        return JsonResponse({"error": "Email not found"}, status=404)
    if denial == "forbidden":
        return JsonResponse({"error": "forbidden"}, status=403)
    return None


def _build_email_list_response(qs: Any, page: int, page_size: int) -> JsonResponse:
    """메일 목록 직렬화 결과를 JsonResponse로 감쌉니다.

    입력:
        qs: Email QuerySet 또는 iterable.
        page: 요청 페이지 번호.
        page_size: 페이지 크기.
    반환:
        페이지네이션 정보가 포함된 JsonResponse.
    부작용:
        없음.
    오류:
        없음.
    """
    return JsonResponse(serialize_email_page(qs, page=page, page_size=page_size))


def _error_response(message: str, *, status: int) -> JsonResponse:
    """공통 에러 응답을 생성합니다."""

    return JsonResponse({"error": message}, status=status)


def _validation_error_response(exc: EmailRequestValidationError) -> JsonResponse:
    """요청 검증 예외를 JsonResponse로 변환합니다."""

    return _error_response(str(exc), status=exc.status_code)


def _ensure_authenticated_user(request: HttpRequest) -> JsonResponse | None:
    """요청 사용자의 로그인 여부를 확인합니다."""

    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return _error_response("unauthorized", status=401)
    return None


def _resolve_email_access_control(
    request: HttpRequest,
) -> tuple[bool, set[str] | None, JsonResponse | None]:
    """이메일 접근 컨텍스트를 계산하고 미인증 응답을 함께 반환합니다."""

    is_authenticated, is_privileged, accessible = resolve_access_control(request)
    if not is_authenticated:
        return is_privileged, accessible, _error_response("unauthorized", status=401)
    return is_privileged, accessible, None


def _parse_required_json_body(request: HttpRequest) -> tuple[dict[str, Any], JsonResponse | None]:
    """필수 JSON 본문을 dict로 파싱합니다."""

    payload = parse_json_body(request)
    if not isinstance(payload, dict):
        return {}, _error_response("Invalid JSON body", status=400)
    return payload, None


def _parse_optional_json_body(request: HttpRequest) -> tuple[dict[str, Any], JsonResponse | None]:
    """비어 있는 본문을 허용하는 JSON 본문을 dict로 파싱합니다."""

    payload = parse_json_body(request)
    if payload is None:
        if not request.body:
            return {}, None
        return {}, _error_response("Invalid JSON body", status=400)
    if not isinstance(payload, dict):
        return {}, _error_response("Invalid JSON body", status=400)
    return payload, None

def validate_query_params(
    request: HttpRequest,
    *,
    allowed: Iterable[str],
) -> JsonResponse | None:
    """허용 목록 밖의 query key를 canonical 입력 오류로 거부합니다."""

    allowed_keys = set(allowed)
    unknown = sorted(set(request.GET.keys()) - allowed_keys)
    if not unknown:
        return None
    return _error_response(
        f"unsupported query parameters: {', '.join(unknown)}",
        status=400,
    )
