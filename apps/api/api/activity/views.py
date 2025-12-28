# =============================================================================
# 모듈 설명: 활동 로그 조회 APIView를 제공합니다.
# - 주요 클래스: ActivityLogView
# - 불변 조건: 권한 확인 후 최근 로그만 반환합니다.
# =============================================================================

"""액티비티 로그 조회 엔드포인트를 제공합니다.

이 모듈은 최근 ActivityLog 레코드를 조회해 간단한 JSON으로 반환합니다.
처리 흐름은 권한 확인 → limit 파라미터 정규화 → 조회/직렬화 → 응답 순서로 진행됩니다.

# 응답 포맷(예시)
{
  예시 "results": [
    {
      예시 "id": 123,
      예시 "user": "alice",
      예시 "role": "admin",
      예시 "action": "UPDATE",
      예시 "path": "/api/tables",
      예시 "method": "PATCH",
      예시 "status": 200,
      예시 "metadata": {...},
      예시 "timestamp": "2025-11-10T12:34:56.789+09:00"
    }
  ]
}

주의:
- 인증/권한이 없으면 401/403을 반환합니다.
- limit 파라미터는 1~200 사이의 정수만 허용하며 기본값은 50입니다.
"""
from __future__ import annotations

from django.http import HttpRequest, JsonResponse
from rest_framework.views import APIView

from .services import get_recent_activity_payload

# 조회 건수 관련 상수(한 곳에서 관리)
DEFAULT_LIMIT: int = 50
MAX_LIMIT: int = 200
MIN_LIMIT: int = 1


class ActivityLogView(APIView):
    """최근 액티비티 로그 조회.

    - 인증 필요
    - 권한 코드: "api.view_activitylog"
    - GET 파라미터:
        - limit (int, optional): 반환 개수. 기본 50, 최소 1, 최대 200.
    """

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """최근 로그를 최대 limit개까지 반환합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: {"results": [...]} 형태의 응답

        부작용:
        - 없음(읽기 전용)

        오류:
        - 401: 인증 실패
        - 403: 권한 없음

        예시 요청:
        - 예시 요청: GET /api/v1/activity/logs?limit=50

        응답 필드:
        - 필드: id, user, role, action, path, method, status, metadata, timestamp

        snake/camel 호환:
        - 해당 없음(쿼리 파라미터 limit만 사용)
        """
        # -----------------------------------------------------------------------------
        # 1) 인증/권한 체크
        # -----------------------------------------------------------------------------
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)

        # 권한 이름은 앱 라벨 + 권한 코드 문자열로 구성됩니다.
        # 예: <app_label>.view_<modelname>
        # 리팩토링 과정에서 앱 라벨이 api -> activity로 변경될 수 있어 둘 다 허용합니다.
        if not (
            request.user.has_perm("activity.view_activitylog")
            or request.user.has_perm("api.view_activitylog")
        ):
            return JsonResponse({"error": "Forbidden"}, status=403)

        # -----------------------------------------------------------------------------
        # 2) limit 파라미터 파싱/정규화
        # -----------------------------------------------------------------------------
        limit_param = request.GET.get("limit")
        try:
            limit = int(limit_param) if limit_param is not None else DEFAULT_LIMIT
        except (TypeError, ValueError):
            # 비정상 값이 들어오면 기본값 사용
            limit = DEFAULT_LIMIT

        # 허용 범위 강제(1 ~ 200)
        limit = max(MIN_LIMIT, min(limit, MAX_LIMIT))

        # -----------------------------------------------------------------------------
        # 3) payload 생성
        # -----------------------------------------------------------------------------
        payload = get_recent_activity_payload(limit=limit)

        # -----------------------------------------------------------------------------
        # 4) 응답 반환
        # -----------------------------------------------------------------------------
        return JsonResponse({"results": payload})


__all__ = ["ActivityLogView"]
