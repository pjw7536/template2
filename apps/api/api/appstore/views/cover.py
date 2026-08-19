# =============================================================================
# 모듈 설명: AppStore 대표 스크린샷 응답 API를 제공합니다.
# =============================================================================
from __future__ import annotations

import logging

from django.http import HttpRequest, HttpResponse, HttpResponseNotModified, HttpResponseRedirect
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from ..selectors import get_app_by_id
from ..services.screenshots import resolve_cover_image
from ._shared import add_cover_cache_headers, cover_etag

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class AppStoreAppCoverView(APIView):
    """앱 대표 스크린샷 바이너리를 제공합니다."""

    def get(self, request: HttpRequest, app_id: int, *args: object, **kwargs: object) -> HttpResponse:
        """앱 대표 스크린샷을 반환합니다.

        입력:
          - 요청: Django HttpRequest
          - app_id: 앱 PK
          - args/kwargs: URL 라우팅 인자

        요청 예시:
          - 예시 요청: GET /api/v1/appstore/apps/123/cover

        반환:
          - 이미지 바이너리(Content-Type: image/*)

        부작용:
          없음. 읽기 전용 조회입니다.

        오류:
          - 404: 앱 또는 스크린샷 없음
          - 400: 스크린샷 디코딩 실패

        snake/camel 호환:
          - 해당 없음(요청 바디 없음)
        """
        # -----------------------------------------------------------------------------
        # 1) 앱 조회
        # -----------------------------------------------------------------------------
        app = get_app_by_id(app_id=app_id)
        if not app:
            return HttpResponse(status=404)

        # -----------------------------------------------------------------------------
        # 2) 커버 이미지 해석 및 HTTP 응답 매핑
        # -----------------------------------------------------------------------------
        etag = cover_etag(app)
        if request.META.get("HTTP_IF_NONE_MATCH") == etag:
            return add_cover_cache_headers(HttpResponseNotModified(), app)

        cover = resolve_cover_image(app)
        if cover.is_redirect:
            return HttpResponseRedirect(cover.redirect_url)
        if cover.has_binary:
            return add_cover_cache_headers(
                HttpResponse(cover.binary, content_type=cover.content_type),
                app,
            )
        if cover.status_code == 400:
            logger.error("Failed to decode appstore screenshot for app %s", app_id)
        return HttpResponse(status=cover.status_code)
