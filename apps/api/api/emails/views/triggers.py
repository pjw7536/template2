# =============================================================================
# 모듈 설명: Emails POP3 수집과 Outbox 처리 trigger endpoint를 제공합니다.
# =============================================================================

from __future__ import annotations

import logging

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from api.common.services import (
    ensure_airflow_token,
    extract_bearer_token,
    parse_json_body_or_error_when_present,
)

from ..serializers import EmailRequestValidationError, parse_optional_positive_limit
from ..services import process_email_outbox_batch, run_pop3_ingest_from_settings
from ._shared import _validation_error_response

logger = logging.getLogger(__name__)

class EmailIngestTriggerView(APIView):
    """POP3 메일 수집을 백엔드에서 실행하도록 트리거."""

    permission_classes: tuple = ()

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """POP3 메일 수집을 트리거합니다.

        입력:
            바디: 없음.
            헤더 예시:
                - Authorization: Bearer <token> (AIRFLOW_TRIGGER_TOKEN 사용 시)
        반환:
            예시 응답: {"deleted": int, "reindexed": int}
        부작용:
            POP3 수집 및 Email 저장 수행.
        오류:
            - 401: 토큰/인증 실패
            - 400: 환경변수 누락 등 설정 오류
            - 500: 수집 실패
        예시 요청:
            예시 요청: POST /api/v1/emails/ingest/
        snake/camel 호환:
            해당 없음(요청 본문 없음).
        """
        expected_token = getattr(settings, "AIRFLOW_TRIGGER_TOKEN", "") or ""
        provided_token = extract_bearer_token(request)

        if expected_token:
            if provided_token != expected_token and not request.user.is_authenticated:
                return JsonResponse({"error": "Unauthorized"}, status=401)
        elif not request.user.is_authenticated:
            return JsonResponse({"error": "로그인이 필요합니다."}, status=401)
        try:
            result = run_pop3_ingest_from_settings() or {}
            return JsonResponse({"deleted": result.get("deleted", 0), "reindexed": result.get("reindexed", 0)})
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except Exception:
            logger.exception("Failed to trigger POP3 ingest")
            return JsonResponse({"error": "POP3 ingest failed"}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class EmailOutboxProcessTriggerView(APIView):
    """RAG Outbox 대기 항목 처리를 트리거합니다."""

    permission_classes: tuple = ()

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """Outbox 대기 항목 처리를 수행합니다.

        입력:
            바디 예시(JSON, 옵션):
                - limit: 처리 건수 제한
            쿼리(옵션):
                - limit: 처리 건수 제한
        반환:
            예시 응답: {"processed": int, "succeeded": int, "failed": int}
        부작용:
            Outbox 상태 업데이트 및 RAG 호출.
        오류:
            - 401: Airflow 트리거 토큰 인증 실패
            - 400: limit 파라미터 오류
            - 500: 처리 실패
        예시 요청:
            예시 요청: POST /api/v1/emails/outbox/process/
            예시 바디: {"limit": 50}
        snake/camel 호환:
            해당 없음(limit 키만 사용).
        """
        auth_response = ensure_airflow_token(request)
        if auth_response is not None:
            return auth_response
        content_type = request.META.get("CONTENT_TYPE", "")
        if content_type.startswith("application/json"):
            payload, payload_error = parse_json_body_or_error_when_present(request)
            if payload_error is not None:
                return payload_error
        else:
            payload = {}
        try:
            limit = parse_optional_positive_limit(
                body_value=payload.get("limit"),
                query_value=request.GET.get("limit"),
            )
        except EmailRequestValidationError as exc:
            return _validation_error_response(exc)
        try:
            if limit is None:
                result = process_email_outbox_batch()
            else:
                result = process_email_outbox_batch(limit=limit)
            return JsonResponse(result)
        except Exception:
            logger.exception("Failed to process email outbox")
            return JsonResponse({"error": "Email outbox processing failed"}, status=500)
