# =============================================================================
# 모듈 설명: AppStore 앱 목록 조회와 생성을 제공합니다.
# =============================================================================
from __future__ import annotations

import logging
from typing import Sequence

from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from api.common.services import extract_first_error_message, parse_json_body

from ..selectors import get_app_list, get_liked_app_ids_for_user
from ..serializers import AppStoreAppCreateSerializer, serialize_app
from ..services import build_app_order_version, create_app
from ._shared import (
    MAX_CATEGORY_LENGTH,
    MAX_CONTACT_LENGTH,
    build_cover_path,
    resolve_appstore_admin,
)

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class AppStoreAppsView(APIView):
    """앱 목록 조회 및 신규 등록."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """앱 목록을 조회합니다.

        입력:
          - 요청: Django HttpRequest
          - args/kwargs: URL 라우팅 인자

        요청 예시:
          - 예시 요청: GET /api/v1/appstore/apps

        반환:
          - results: 앱 목록
          - total: 총 개수

        부작용:
          없음. 읽기 전용 조회입니다.

        오류:
          - 없음

        snake/camel 호환:
          - 해당 없음(요청 바디 없음)
        """
        # -----------------------------------------------------------------------------
        # 1) 기본 목록/좋아요 정보 조회
        # -----------------------------------------------------------------------------
        queryset = list(get_app_list())
        liked_ids: Sequence[int] = []
        user = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
        is_appstore_admin = resolve_appstore_admin(request)
        if user:
            liked_ids = get_liked_app_ids_for_user(user=user)

        # -----------------------------------------------------------------------------
        # 2) 응답 직렬화
        # -----------------------------------------------------------------------------
        apps = []
        for app in queryset:
            # 목록에서는 base64 데이터를 직접 내려보내지 않도록 커버 URL을 치환합니다.
            cover_src = ""
            if getattr(app, "screenshot_url", ""):
                cover_src = app.screenshot_url
            elif getattr(app, "screenshot_base64", ""):
                cover_src = request.build_absolute_uri(build_cover_path(app))
            apps.append(
                serialize_app(
                    app,
                    user,
                    liked_ids,
                    cover_src=cover_src,
                    is_appstore_admin=is_appstore_admin,
                )
            )

        # -----------------------------------------------------------------------------
        # 3) 응답 반환
        # -----------------------------------------------------------------------------
        return JsonResponse(
            {
                "results": apps,
                "total": len(apps),
                "orderVersion": build_app_order_version([app.pk for app in queryset]),
                "permissions": {"canReorder": is_appstore_admin},
            }
        )

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """앱을 신규 등록합니다.

        입력:
          - 요청: Django HttpRequest
          - args/kwargs: URL 라우팅 인자

        요청 예시:
          - 예시 요청: POST /api/v1/appstore/apps
            {
              예시 "name": "New App",
              예시 "category": "Tools",
              예시 "description": "desc",
              예시 "url": "https://example.com",
              예시 "manualUrl": "https://example.com/manual",
              예시 "screenshotUrls": ["https://example.com/cover.png"],
              예시 "coverScreenshotIndex": 0,
              예시 "screenshotUrl": "",
              예시 "contactName": "홍길동",
              예시 "contactKnoxid": "hong"
            }

        snake/camel 호환:
          - screenshotUrls / screenshot_urls (키 매핑)
          - coverScreenshotIndex / cover_screenshot_index (키 매핑)
          - screenshotUrl / screenshot_url (키 매핑)
          - manualUrl / manual_url (키 매핑)

        반환:
          - app: 생성된 앱 상세 payload

        부작용:
          AppStoreApp 레코드를 생성합니다.

        오류:
          - 401: 인증 실패
          - 400: 필수 필드 누락/JSON 파싱 실패
          - 500: 내부 오류
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        # -----------------------------------------------------------------------------
        # 2) JSON 파싱
        # -----------------------------------------------------------------------------
        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        # -----------------------------------------------------------------------------
        # 3) 입력 검증/정규화
        # -----------------------------------------------------------------------------
        serializer = AppStoreAppCreateSerializer(
            data=payload,
            context={
                "user": request.user,
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
        validated = serializer.validated_data

        # -----------------------------------------------------------------------------
        # 4) 생성 및 응답
        # -----------------------------------------------------------------------------
        try:
            app = create_app(
                owner=request.user,
                name=validated["name"],
                category=validated["category"],
                description=validated["description"],
                url=validated["url"],
                manual_url=validated["manual_url"],
                screenshot_urls=validated["screenshot_urls"],
                screenshot_url=validated["screenshot_url"],
                contact_name=validated["contact_name"],
                contact_knoxid=validated["contact_knoxid"],
            )
            liked_ids = get_liked_app_ids_for_user(user=request.user)
            is_appstore_admin = resolve_appstore_admin(request)
            return JsonResponse(
                {
                    "app": serialize_app(
                        app,
                        request.user,
                        liked_ids,
                        include_screenshots=True,
                        is_appstore_admin=is_appstore_admin,
                    )
                },
                status=201,
            )
        except Exception:  # 방어적 로깅(커버리지 제외): pragma: no cover
            logger.exception("Failed to create appstore app")
            return JsonResponse({"error": "Failed to create app"}, status=500)
