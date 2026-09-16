# =============================================================================
# 모듈 설명: Emails 삭제·이동 HTTP endpoint를 제공합니다.
# =============================================================================

from __future__ import annotations

import logging

from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.exceptions import NotFound
from rest_framework.views import APIView

from api.common.services import extract_first_error_message

from ..serializers import EmailBulkDeleteInputSerializer, EmailMoveInputSerializer
from ..services import bulk_delete_emails, move_emails_for_user
from ._shared import _error_response, _parse_required_json_body, _resolve_email_access_control

logger = logging.getLogger(__name__)

class EmailBulkDeleteView(APIView):
    """여러 메일 삭제 (모두 성공 시 반영)."""

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """여러 메일을 일괄 삭제합니다.

        입력:
            바디 예시(JSON):
                - emailIds: 삭제할 Email id 목록
        반환:
            예시 응답: {"deleted": int}
        부작용:
            Email 삭제 및 RAG 삭제 Outbox 적재.
        오류:
            - 401: 인증 실패
            - 403: 권한 부족/UNASSIGNED 삭제 금지
            - 400: 잘못된 JSON/파라미터
            - 404: 대상 메일 없음
            - 500: 기타 서버 오류
        예시 요청:
            예시 요청: POST /api/v1/emails/bulk-delete/
            예시 바디: {"emailIds":[1,2,3]}
        입력 표기:
            HTTP JSON은 camelCase만 지원합니다.
        """
        is_privileged, accessible, auth_error = _resolve_email_access_control(request)
        if auth_error is not None:
            return auth_error
        payload, payload_error = _parse_required_json_body(request)
        if payload_error is not None:
            return payload_error
        serializer = EmailBulkDeleteInputSerializer(data=payload)
        if not serializer.is_valid():
            return _error_response(
                extract_first_error_message(serializer.errors),
                status=400,
            )
        normalized_ids = serializer.validated_data["normalized_email_ids"]
        try:
            deleted_count = bulk_delete_emails(
                normalized_ids,
                user=request.user,
                is_privileged=is_privileged,
                accessible_user_sdwt_prods=accessible,
            )
            return JsonResponse({"deleted": deleted_count})
        except PermissionError:
            return _error_response("forbidden", status=403)
        except NotFound as exc:
            return JsonResponse({"error": str(exc)}, status=404)
        except Exception:  # pragma: no cover  테스트 제외
            # 방어적 로깅
            logger.exception("Failed to bulk delete emails")
            return JsonResponse({"error": "Failed to delete emails"}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class EmailMoveView(APIView):
    """메일 이동 (user_sdwt_prod 변경 + RAG 재등록)."""

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """메일함을 다른 user_sdwt_prod로 이동합니다.

        입력:
            바디 예시(JSON):
                - emailIds: 이동할 Email id 목록
                - toUserSdwtProd: 대상 메일함
        반환:
            예시 응답: {"moved": int, "ragRegistered": int, "ragFailed": int, "ragMissing": int}
        부작용:
            Email.user_sdwt_prod 업데이트 및 RAG 인덱싱 큐 적재.
        오류:
            - 401: 인증 실패
            - 403: 권한 부족
            - 400: 잘못된 입력
            - 500: 기타 서버 오류
        예시 요청:
            예시 요청: POST /api/v1/emails/move/
            예시 바디: {"emailIds":[1,2], "toUserSdwtProd":"group-b"}
        입력 표기:
            HTTP JSON은 camelCase만 지원합니다.
        """
        is_privileged, accessible, auth_error = _resolve_email_access_control(request)
        if auth_error is not None:
            return auth_error
        user = request.user
        payload, payload_error = _parse_required_json_body(request)
        if payload_error is not None:
            return payload_error
        serializer = EmailMoveInputSerializer(data=payload)
        if not serializer.is_valid():
            return _error_response(
                extract_first_error_message(serializer.errors),
                status=400,
            )
        normalized_ids = serializer.validated_data["normalized_email_ids"]
        target_user_sdwt_prod = serializer.validated_data[
            "normalized_to_user_sdwt_prod"
        ]
        try:
            result = move_emails_for_user(
                user=user,
                email_ids=normalized_ids,
                to_user_sdwt_prod=target_user_sdwt_prod,
                is_privileged=is_privileged,
                accessible_user_sdwt_prods=accessible,
            )
            return JsonResponse(result)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except PermissionError:
            return _error_response("forbidden", status=403)
        except Exception:  # pragma: no cover  테스트 제외
            # 방어적 로깅
            logger.exception("Failed to move emails")
            return JsonResponse({"error": "Failed to move emails"}, status=500)
