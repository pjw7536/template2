# =============================================================================
# 모듈 설명: OIDC 연동 이후 보조 뷰를 제공합니다.
# - 주요 클래스: FrontendRedirectView
# - 불변 조건: 리다이렉트 대상은 안전 검사 후 결정합니다.
# =============================================================================

"""OIDC 전환 이후 남은 보조 뷰 모음.

- 주요 대상: FrontendRedirectView
- 주요 엔드포인트/클래스: FrontendRedirectView
- 가정/불변 조건: 프론트엔드 베이스 URL은 settings 또는 요청에서 결정됨
"""
from __future__ import annotations

from django.http import HttpRequest, HttpResponseRedirect
from rest_framework.views import APIView

from api.common.utils import resolve_frontend_target


class FrontendRedirectView(APIView):
    """요청을 프론트엔드 엔트리포인트(next 포함)로 리다이렉트합니다."""

    def get(  # 타입 검사 생략: type: ignore[override]
        self, request: HttpRequest, *args: object, **kwargs: object
    ) -> HttpResponseRedirect:
        """next 파라미터를 기준으로 안전한 리다이렉트 응답을 반환합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - HttpResponseRedirect: 302 리다이렉트 응답

        부작용:
        - 없음

        오류:
        - 없음

        예시 요청:
        - 예시 요청: GET /api/v1/auth/redirect/?next=/dashboard

        예시 응답:
        - 예시 응답: 302 Location: https://<frontend-base>/dashboard

        snake/camel 호환:
        - 해당 없음(쿼리 파라미터 next만 사용)
        """
        # -----------------------------------------------------------------------------
        # 1) next 파라미터 추출
        # -----------------------------------------------------------------------------
        target = resolve_frontend_target(request.GET.get("next"), request=request)
        # -----------------------------------------------------------------------------
        # 2) 리다이렉트 응답 반환
        # -----------------------------------------------------------------------------
        return HttpResponseRedirect(target)


__all__ = ["FrontendRedirectView"]
