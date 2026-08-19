# =============================================================================
# 모듈 설명: Emails OCR claim·update 내부 endpoint를 제공합니다.
# =============================================================================

from __future__ import annotations

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from ..serializers import EmailAssetOcrClaimSerializer, EmailAssetOcrUpdateSerializer
from ..services import claim_email_asset_ocr_tasks, update_email_asset_ocr_results
from ._shared import _parse_optional_json_body, _parse_required_json_body


def _ensure_internal_token(request: HttpRequest) -> JsonResponse | None:
    """내부 OCR token을 검증합니다."""

    expected = (getattr(settings, "EMAIL_OCR_INTERNAL_TOKEN", "") or "").strip()
    if not expected:
        return JsonResponse({"error": "EMAIL_OCR_INTERNAL_TOKEN not configured"}, status=500)
    provided = request.headers.get("X-Internal-Token") or request.META.get("HTTP_X_INTERNAL_TOKEN") or ""
    if not isinstance(provided, str):
        provided = ""
    if provided.strip() != expected:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    return None


class EmailAssetOcrClaimView(APIView):
    """OCR 작업 클레임을 제공합니다."""

    permission_classes: tuple = ()

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """OCR 작업을 클레임합니다.

        입력:
            헤더:
                - X-Internal-Token: 내부 OCR 인증 토큰
            바디 예시(JSON):
                - limit: 최대 클레임 개수(옵션)
                - lease_seconds: 잠금 유지 시간(초, 옵션)
                - worker_id: 작업자 식별자(옵션)
        반환:
            예시 응답: {"tasks":[{"asset_id":1,"email_id":10,"sequence":1,"source_type":"CID","object_key":"...","bucket":"...","external_url":null,"content_type":"image/png","size_bytes":1234,"lock_token":"...","lock_expires_at":"...","attempt_count":1}]}
        부작용:
            EmailAsset 락 및 상태 갱신.
        오류:
            - 401: 내부 토큰 인증 실패
            - 400: 요청 본문 오류
        예시 요청:
            예시 요청: POST /api/v1/emails/assets/ocr/claim/
            예시 바디: {"limit":50,"lease_seconds":1800,"worker_id":"gpu-01"}
        snake/camel 호환:
            snake_case만 사용합니다.
        """
        auth_response = _ensure_internal_token(request)
        if auth_response is not None:
            return auth_response
        payload, payload_error = _parse_optional_json_body(request)
        if payload_error is not None:
            return payload_error

        serializer = EmailAssetOcrClaimSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse(serializer.errors, status=400)
        default_limit = getattr(settings, "EMAIL_OCR_CLAIM_LIMIT", 50) or 50
        default_lease_seconds = getattr(settings, "EMAIL_OCR_LEASE_SECONDS", 1800) or 1800
        max_attempts = getattr(settings, "EMAIL_OCR_MAX_ATTEMPTS", 3) or 3

        limit = serializer.validated_data.get("limit") or default_limit
        lease_seconds = serializer.validated_data.get("lease_seconds") or default_lease_seconds
        worker_id = serializer.validated_data.get("worker_id")
        tasks = claim_email_asset_ocr_tasks(
            limit=limit,
            lease_seconds=lease_seconds,
            max_attempts=max_attempts,
            worker_id=worker_id,
        )
        return JsonResponse({"tasks": tasks})


@method_decorator(csrf_exempt, name="dispatch")
class EmailAssetOcrUpdateView(APIView):
    """OCR 결과를 EmailAsset에 반영하고 RAG 재인덱싱을 요청합니다."""

    permission_classes: tuple = ()

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """OCR 결과 업데이트를 처리합니다.

        입력:
            헤더:
                - X-Internal-Token: 내부 OCR 인증 토큰
            바디 예시(JSON):
                - results: OCR 결과 목록
                    - asset_id: EmailAsset 기본 키
                    - lock_token: 클레임 시 받은 토큰
                    - status: DONE | FAILED 상태
                    - text: OCR 텍스트(옵션)
                    - error_code: 실패 코드(옵션)
                    - error_message: 실패 사유(옵션)
                    - ocr_model: 사용 모델(옵션)
                    - ocr_duration_ms: 처리 시간(ms, 옵션)
                    - processed_at: 처리 완료 시각(옵션, ISO)
        반환:
            예시 응답: {"updated": int, "rejected": int, "ragQueued": int, "ragFailed": int, "ragSkipped": int}
        부작용:
            EmailAsset 업데이트 및 RAG Outbox 적재.
        오류:
            - 401: 내부 토큰 인증 실패
            - 400: 요청 본문 오류
        예시 요청:
            예시 요청: POST /api/v1/emails/assets/ocr/update/
            예시 바디: {"results":[{"asset_id":1,"lock_token":"token","status":"DONE","text":"..."}]}
        snake/camel 호환:
            snake_case만 사용합니다.
        """
        auth_response = _ensure_internal_token(request)
        if auth_response is not None:
            return auth_response
        payload, payload_error = _parse_required_json_body(request)
        if payload_error is not None:
            return payload_error

        serializer = EmailAssetOcrUpdateSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse(serializer.errors, status=400)
        max_attempts = getattr(settings, "EMAIL_OCR_MAX_ATTEMPTS", 3) or 3
        results = serializer.validated_data.get("results") or []
        result = update_email_asset_ocr_results(results=results, max_attempts=max_attempts)
        return JsonResponse(result)
