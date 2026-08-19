# =============================================================================
# 모듈 설명: Emails 상세 본문·자산 HTTP endpoint를 제공합니다.
# =============================================================================

from __future__ import annotations

import logging

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.exceptions import NotFound
from rest_framework.views import APIView

from ..selectors import get_email_asset_by_email_and_sequence, get_email_by_id
from ..serializers import serialize_email_detail
from ..services import delete_single_email, load_email_asset, load_email_html
from ._shared import _check_email_access, _error_response, _resolve_email_access_control

logger = logging.getLogger(__name__)

class EmailDetailView(APIView):
    """단일 메일 상세 조회 (텍스트)."""

    def get(self, request: HttpRequest, email_id: int, *args: object, **kwargs: object) -> JsonResponse:
        """단일 메일 상세 정보를 조회합니다.

        입력:
            경로:
                - email_id: 메일 PK
        반환:
            Email 상세 JSON (camelCase 키).
        부작용:
            없음. 조회 전용.
        오류:
            - 401: 인증 실패
            - 403: 접근 권한 없음
            - 404: 메일 없음
        예시 요청:
            예시 요청: GET /api/v1/emails/123/
        snake/camel 호환:
            해당 없음(경로 파라미터만 사용).
        """
        is_privileged, accessible, auth_error = _resolve_email_access_control(request)
        if auth_error is not None:
            return auth_error
        email = get_email_by_id(email_id=email_id)
        access_error = _check_email_access(
            request=request,
            email=email,
            is_privileged=is_privileged,
            accessible=accessible,
        )
        if access_error:
            return access_error
        return JsonResponse(serialize_email_detail(email))

    def delete(self, request: HttpRequest, email_id: int, *args: object, **kwargs: object) -> JsonResponse:
        """단일 메일을 삭제합니다(RAG 삭제는 Outbox 처리).

        입력:
            경로:
                - email_id: 메일 PK
        반환:
            예시 응답: {"status": "ok"}
        부작용:
            Email 삭제 및 RAG 삭제 Outbox 적재.
        오류:
            - 401: 인증 실패
            - 403: 접근 권한 없음
            - 404: 메일 없음
            - 500: 기타 서버 오류
        예시 요청:
            예시 요청: DELETE /api/v1/emails/123/
        snake/camel 호환:
            해당 없음(경로 파라미터만 사용).
        """
        is_privileged, accessible, auth_error = _resolve_email_access_control(request)
        if auth_error is not None:
            return auth_error
        email = get_email_by_id(email_id=email_id)
        access_error = _check_email_access(
            request=request,
            email=email,
            is_privileged=is_privileged,
            accessible=accessible,
        )
        if access_error:
            return access_error
        try:
            delete_single_email(
                email_id,
                user=request.user,
                is_privileged=is_privileged,
                accessible_user_sdwt_prods=accessible,
            )
            return JsonResponse({"status": "ok"})
        except PermissionError:
            return _error_response("forbidden", status=403)
        except NotFound as exc:
            return JsonResponse({"error": str(exc)}, status=404)
        except Exception:  # pragma: no cover  테스트 제외
            # 방어적 로깅
            logger.exception("Failed to delete email id=%s", email_id)
            return JsonResponse({"error": "Failed to delete email"}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class EmailHtmlView(APIView):
    """MinIO 저장된 HTML 본문을 반환합니다."""

    def get(self, request: HttpRequest, email_id: int, *args: object, **kwargs: object) -> HttpResponse:
        """MinIO에 저장된 HTML 본문을 반환합니다.

        입력:
            경로:
                - email_id: 메일 PK
        반환:
            HTML 본문(HttpResponse) 또는 204 응답.
        부작용:
            없음. 조회 전용.
        오류:
            - 401: 인증 실패
            - 403: 접근 권한 없음
            - 404: 메일 없음
            - 500: HTML 로드 실패
        예시 요청:
            예시 요청: GET /api/v1/emails/123/html/
        snake/camel 호환:
            해당 없음(경로 파라미터만 사용).
        """
        is_privileged, accessible, auth_error = _resolve_email_access_control(request)
        if auth_error is not None:
            return auth_error
        email = get_email_by_id(email_id=email_id)
        access_error = _check_email_access(
            request=request,
            email=email,
            is_privileged=is_privileged,
            accessible=accessible,
        )
        if access_error:
            return access_error
        try:
            html_bytes = load_email_html(email=email)
        except Exception:  # pragma: no cover  테스트 제외
            logger.exception("Failed to load email HTML (id=%s)", email_id)
            return JsonResponse({"error": "Failed to load HTML body"}, status=500)

        if not html_bytes:
            return HttpResponse("", status=204)

        response = HttpResponse(html_bytes, content_type="text/html; charset=utf-8")
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, max-age=300"
        return response


@method_decorator(csrf_exempt, name="dispatch")
class EmailAssetView(APIView):
    """MinIO에 저장된 이메일 이미지 자산을 반환합니다."""

    def get(
        self,
        request: HttpRequest,
        email_id: int,
        sequence: int,
        *args: object,
        **kwargs: object,
    ) -> HttpResponse:
        """이메일 이미지 자산을 반환합니다.

        입력:
            경로:
                - email_id: 메일 PK
                - sequence: 이미지 순번
        반환:
            이미지(HttpResponse) 또는 404 응답.
        부작용:
            없음. 조회 전용.
        오류:
            - 401: 인증 실패
            - 403: 접근 권한 없음
            - 404: 메일/자산/오브젝트 없음
            - 500: 자산 로드 실패
        예시 요청:
            예시 요청: GET /api/v1/emails/123/assets/1/
        snake/camel 호환:
            해당 없음(경로 파라미터만 사용).
        """
        is_privileged, accessible, auth_error = _resolve_email_access_control(request)
        if auth_error is not None:
            return auth_error
        email = get_email_by_id(email_id=email_id)
        access_error = _check_email_access(
            request=request,
            email=email,
            is_privileged=is_privileged,
            accessible=accessible,
        )
        if access_error:
            return access_error
        asset = get_email_asset_by_email_and_sequence(email_id=email_id, sequence=sequence)
        if asset is None:
            return JsonResponse({"error": "Email asset not found"}, status=404)
        try:
            asset_bytes = load_email_asset(asset=asset)
        except Exception:  # pragma: no cover  테스트 제외
            logger.exception("Failed to load email asset (email_id=%s sequence=%s)", email_id, sequence)
            return JsonResponse({"error": "Failed to load email asset"}, status=500)

        if not asset_bytes:
            return JsonResponse({"error": "Email asset not found"}, status=404)

        content_type = asset.content_type or "application/octet-stream"
        response = HttpResponse(asset_bytes, content_type=content_type)
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, max-age=3600"
        return response
