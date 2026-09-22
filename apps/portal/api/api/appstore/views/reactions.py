# =============================================================================
# 모듈 설명: AppStore 앱 좋아요와 조회수 변경 API를 제공합니다.
# =============================================================================
from __future__ import annotations

import logging

from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from ..services import increment_view_count, toggle_like
from ._shared import load_app

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class AppStoreLikeToggleView(APIView):
    """좋아요 토글."""

    def post(self, request: HttpRequest, app_id: int, *args: object, **kwargs: object) -> JsonResponse:
        """앱 좋아요를 토글합니다.

        입력:
          - 요청: Django HttpRequest
          - app_id: 앱 PK
          - args/kwargs: URL 라우팅 인자

        요청 예시:
          - 예시 요청: POST /api/v1/appstore/apps/123/like

        반환:
          - liked: 좋아요 여부
          - likeCount: 최신 좋아요 수
          - appId: 앱 id

        부작용:
          AppStoreLike 생성/삭제 및 like_count 갱신이 발생합니다.

        오류:
          - 401: 인증 실패
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
        # 2) 앱 조회
        # -----------------------------------------------------------------------------
        app = load_app(app_id)
        if not app:
            return JsonResponse({"error": "App not found"}, status=404)

        # -----------------------------------------------------------------------------
        # 3) 좋아요 토글
        # -----------------------------------------------------------------------------
        try:
            liked, like_count = toggle_like(app=app, user=request.user)
            return JsonResponse(
                {"liked": liked, "likeCount": like_count, "appId": app.pk},
                status=200,
            )
        except Exception:  # 방어적 로깅(커버리지 제외): pragma: no cover
            logger.exception("Failed to toggle like for appstore app %s", app_id)
            return JsonResponse({"error": "Failed to toggle like"}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class AppStoreViewIncrementView(APIView):
    """조회수 증가."""

    def post(self, request: HttpRequest, app_id: int, *args: object, **kwargs: object) -> JsonResponse:
        """앱 조회수를 증가시킵니다.

        입력:
          - 요청: Django HttpRequest
          - app_id: 앱 PK
          - args/kwargs: URL 라우팅 인자

        요청 예시:
          - 예시 요청: POST /api/v1/appstore/apps/123/view

        반환:
          - viewCount: 최신 조회수
          - appId: 앱 id

        부작용:
          AppStoreApp.view_count를 갱신합니다.

        오류:
          - 404: 앱 없음

        snake/camel 호환:
          - 해당 없음(요청 바디 없음)
        """
        # -----------------------------------------------------------------------------
        # 1) 앱 조회
        # -----------------------------------------------------------------------------
        app = load_app(app_id)
        if not app:
            return JsonResponse({"error": "App not found"}, status=404)

        # -----------------------------------------------------------------------------
        # 2) 조회수 증가
        # -----------------------------------------------------------------------------
        view_count = increment_view_count(app=app)
        return JsonResponse({"viewCount": view_count, "appId": app.pk})
