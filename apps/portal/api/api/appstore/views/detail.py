# =============================================================================
# 모듈 설명: AppStore 앱 상세 조회·수정·삭제 API를 제공합니다.
# =============================================================================
from __future__ import annotations

import logging
from typing import Sequence

from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from api.common.services import extract_first_error_message, parse_json_body

from ..selectors import (
    get_app_detail,
    get_liked_app_ids_for_user,
    get_liked_comment_ids_for_user,
)
from ..serializers import AppStoreAppUpdateSerializer, serialize_app
from ..services import delete_app, update_app
from ..services.permissions import can_manage_app
from ._shared import (
    MAX_CATEGORY_LENGTH,
    MAX_CONTACT_LENGTH,
    load_app,
    resolve_appstore_admin,
)

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class AppStoreAppDetailView(APIView):
    """앱 단건 조회/수정/삭제."""

    def get(self, request: HttpRequest, app_id: int, *args: object, **kwargs: object) -> JsonResponse:
        """앱 상세 정보를 조회합니다(댓글/스크린샷 포함).

        입력:
          - 요청: Django HttpRequest
          - app_id: 앱 PK
          - args/kwargs: URL 라우팅 인자

        요청 예시:
          - 예시 요청: GET /api/v1/appstore/apps/123

        반환:
          - app: 앱 상세 payload

        부작용:
          없음. 읽기 전용 조회입니다.

        오류:
          - 404: 앱 없음

        snake/camel 호환:
          - 해당 없음(요청 바디 없음)
        """
        # -----------------------------------------------------------------------------
        # 1) 앱 조회
        # -----------------------------------------------------------------------------
        app = get_app_detail(app_id=app_id)
        if not app:
            return JsonResponse({"error": "App not found"}, status=404)
        # -----------------------------------------------------------------------------
        # 2) 좋아요/댓글 좋아요 목록 조회
        # -----------------------------------------------------------------------------
        liked_ids: Sequence[int] = []
        user = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
        is_appstore_admin = resolve_appstore_admin(request)
        liked_comment_ids: set[int] = set()
        if user:
            liked_ids = get_liked_app_ids_for_user(user=user)
            liked_comment_ids = set(get_liked_comment_ids_for_user(user=user, app_id=app.pk))

        # -----------------------------------------------------------------------------
        # 3) 응답 반환
        # -----------------------------------------------------------------------------
        return JsonResponse(
            {
                "app": serialize_app(
                    app,
                    user,
                    liked_ids,
                    include_comments=True,
                    include_screenshots=True,
                    liked_comment_ids=liked_comment_ids,
                    is_appstore_admin=is_appstore_admin,
                )
            }
        )

    def patch(self, request: HttpRequest, app_id: int, *args: object, **kwargs: object) -> JsonResponse:
        """앱 정보를 부분 수정합니다.

        입력:
          - 요청: Django HttpRequest
          - app_id: 앱 PK
          - args/kwargs: URL 라우팅 인자

        요청 예시:
          - 예시 요청: PATCH /api/v1/appstore/apps/123
            예시 바디: {"description": "updated"}

        snake/camel 호환:
          - screenshotUrls / screenshot_urls (키 매핑)
          - coverScreenshotIndex / cover_screenshot_index (키 매핑)
          - screenshotUrl / screenshot_url (키 매핑)
          - manualUrl / manual_url (키 매핑)

        반환:
          - app: 업데이트된 앱 payload

        부작용:
          AppStoreApp 레코드를 업데이트합니다.

        오류:
          - 401: 인증 실패
          - 403: 권한 없음
          - 404: 앱 없음
          - 400: 입력 오류/변경 사항 없음
          - 500: 내부 오류
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        # -----------------------------------------------------------------------------
        # 2) 앱 조회 및 권한 확인
        # -----------------------------------------------------------------------------
        app = load_app(app_id)
        if not app:
            return JsonResponse({"error": "App not found"}, status=404)

        is_appstore_admin = resolve_appstore_admin(request)
        if not can_manage_app(
            request.user,
            app,
            is_appstore_admin=is_appstore_admin,
        ):
            return JsonResponse({"error": "Forbidden"}, status=403)

        # -----------------------------------------------------------------------------
        # 3) JSON 파싱
        # -----------------------------------------------------------------------------
        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        # -----------------------------------------------------------------------------
        # 4) 입력 검증/업데이트 필드 구성
        # -----------------------------------------------------------------------------
        serializer = AppStoreAppUpdateSerializer(
            data=payload,
            context={
                "max_category_length": MAX_CATEGORY_LENGTH,
                "max_contact_length": MAX_CONTACT_LENGTH,
            },
        )
        if not serializer.is_valid():
            return JsonResponse(
                {
                    "error": extract_first_error_message(serializer.errors),
                    "details": serializer.errors,
                },
                status=400,
            )
        updates = serializer.validated_data

        # -----------------------------------------------------------------------------
        # 5) 업데이트 수행
        # -----------------------------------------------------------------------------
        try:
            app = update_app(app=app, updates=updates)
            liked_ids = get_liked_app_ids_for_user(user=request.user)
            return JsonResponse(
                {
                    "app": serialize_app(
                        app,
                        request.user,
                        liked_ids,
                        include_screenshots=True,
                        is_appstore_admin=is_appstore_admin,
                    )
                }
            )
        except Exception:  # 방어적 로깅(커버리지 제외): pragma: no cover
            logger.exception("Failed to update appstore app")
            return JsonResponse({"error": "Failed to update app"}, status=500)

    def delete(self, request: HttpRequest, app_id: int, *args: object, **kwargs: object) -> JsonResponse:
        """앱을 삭제합니다.

        입력:
          - 요청: Django HttpRequest
          - app_id: 앱 PK
          - args/kwargs: URL 라우팅 인자

        요청 예시:
          - 예시 요청: DELETE /api/v1/appstore/apps/123

        반환:
          - 예시 응답: success: true

        부작용:
          AppStoreApp 레코드를 삭제합니다.

        오류:
          - 401: 인증 실패
          - 403: 권한 없음
          - 404: 앱 없음
          - 500: 내부 오류

        snake/camel 호환:
          - 해당 없음(요청 바디 없음)
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        # -----------------------------------------------------------------------------
        # 2) 앱 조회 및 권한 확인
        # -----------------------------------------------------------------------------
        app = load_app(app_id)
        if not app:
            return JsonResponse({"error": "App not found"}, status=404)

        if not can_manage_app(
            request.user,
            app,
            is_appstore_admin=resolve_appstore_admin(request),
        ):
            return JsonResponse({"error": "Forbidden"}, status=403)

        # -----------------------------------------------------------------------------
        # 3) 삭제 수행
        # -----------------------------------------------------------------------------
        try:
            delete_app(app=app)
            return JsonResponse({"success": True})
        except Exception:  # 방어적 로깅(커버리지 제외): pragma: no cover
            logger.exception("Failed to delete appstore app")
            return JsonResponse({"error": "Failed to delete app"}, status=500)
