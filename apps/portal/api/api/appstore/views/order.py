# =============================================================================
# 모듈 설명: AppStore 앱 노출 순서 변경 API를 제공합니다.
# =============================================================================
from __future__ import annotations

import logging

from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from api.common.services import extract_first_error_message, parse_json_body

from ..serializers import AppStoreAppOrderSerializer
from ..services import AppOrderConflictError, reorder_apps
from ._shared import resolve_appstore_admin

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class AppStoreAppOrderView(APIView):
    """관리자 전용 Appstore 앱 노출 순서 변경 endpoint입니다."""

    def put(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """전체 앱 ID 목록을 받아 노출 순서를 일괄 교체합니다.

        입력:
          - 요청: Django HttpRequest
          - args/kwargs: URL 라우팅 인자

        요청 예시:
          - 예시 요청: PUT /api/v1/appstore/apps/order
            {"appIds": [3, 1, 2], "orderVersion": "opaque-version"}

        반환:
          - appIds: 저장된 전체 앱 PK 목록
          - orderVersion: 저장 후 노출 순서 버전
          - updated: 갱신한 앱 개수

        부작용:
          모든 AppStoreApp 레코드의 display_order를 원자적으로 갱신합니다.

        오류:
          - 401: 인증 실패
          - 403: Appstore admin 권한 없음
          - 400: 요청 형식 또는 앱 ID 중복 오류
          - 409: 편집 이후 앱 목록 또는 순서 변경 충돌
          - 500: 내부 오류

        snake/camel 호환:
          - appIds / app_ids
          - orderVersion / order_version
        """

        # -----------------------------------------------------------------------------
        # 1) 인증 및 Appstore 관리자 권한 확인
        # -----------------------------------------------------------------------------
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)
        if not resolve_appstore_admin(request):
            return JsonResponse({"error": "Forbidden"}, status=403)

        # -----------------------------------------------------------------------------
        # 2) JSON 요청 검증
        # -----------------------------------------------------------------------------
        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)
        serializer = AppStoreAppOrderSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse(
                {
                    "error": extract_first_error_message(serializer.errors),
                    "details": serializer.errors,
                },
                status=400,
            )

        # -----------------------------------------------------------------------------
        # 3) 원자적 순서 저장 및 충돌 응답 매핑
        # -----------------------------------------------------------------------------
        validated = serializer.validated_data
        try:
            app_ids, order_version = reorder_apps(
                app_ids=validated["app_ids"],
                expected_order_version=validated["order_version"],
            )
        except AppOrderConflictError:
            return JsonResponse(
                {"error": "App list or order changed. Refresh and try again."},
                status=409,
            )
        except Exception:  # 방어적 로깅(커버리지 제외): pragma: no cover
            logger.exception("Failed to reorder appstore apps")
            return JsonResponse({"error": "Failed to reorder apps"}, status=500)

        return JsonResponse(
            {
                "appIds": app_ids,
                "orderVersion": order_version,
                "updated": len(app_ids),
            }
        )
