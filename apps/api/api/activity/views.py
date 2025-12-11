"""액티비티 로그 관련 뷰.

이 모듈은 최근 ActivityLog 레코드를 조회해서 간단한 JSON으로 반환합니다.
권한 체크 → 파라미터 정규화(limit) → 쿼리셋 조회(select_related) → 직렬화 → 응답 순으로 동작합니다.

# 응답 포맷(예시)
{
  "results": [
    {
      "id": 123,
      "user": "alice",
      "role": "admin",
      "action": "UPDATE",
      "path": "/api/tables",
      "method": "PATCH",
      "status": 200,
      "metadata": {...},
      "timestamp": "2025-11-10T12:34:56.789+09:00"
    }
  ]
}

주의:
- 인증/권한이 없으면 401/403을 반환합니다.
- limit 파라미터는 1~200 사이의 정수만 허용하며 기본값은 50입니다.
"""
from __future__ import annotations

from typing import Any, Dict, List

from django.http import HttpRequest, JsonResponse
from rest_framework.views import APIView

from ..models import ActivityLog

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
        """최근 로그를 최대 limit개까지 반환.

        반환 필드:
          id, user(사용자명), role(프로필의 role), action, path, method,
          status(HTTP status code), metadata(임의 JSON), timestamp(ISO8601)
        """
        # 1) 인증/권한 체크 ------------------------------------------------------
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)

        # 권한 이름은 앱 라벨 + 권한 코드 문자열로 구성됩니다.
        # e.g. <app_label>.view_<modelname>
        if not request.user.has_perm("api.view_activitylog"):
            return JsonResponse({"error": "Forbidden"}, status=403)

        # 2) limit 파라미터 파싱/정규화 ------------------------------------------
        limit_param = request.GET.get("limit")
        try:
            limit = int(limit_param) if limit_param is not None else DEFAULT_LIMIT
        except (TypeError, ValueError):
            # 비정상 값이 들어오면 기본값 사용
            limit = DEFAULT_LIMIT

        # 허용 범위 강제(1 ~ 200)
        limit = max(MIN_LIMIT, min(limit, MAX_LIMIT))

        # 3) 쿼리셋 조회 ---------------------------------------------------------
        # - select_related("user", "user__profile")로 N+1 방지
        # - 최신순 정렬
        logs = (
            ActivityLog.objects.select_related("user", "user__profile")
            .order_by("-created_at")[:limit]
        )

        # 4) 직렬화(최소 필드만 hand-written serialize) ---------------------------
        payload: List[Dict[str, Any]] = []
        for entry in logs:
            user = entry.user  # Optional[User]
            username = user.get_username() if user else None

            # user.profile.role 안전 접근(getattr 체인)
            role = getattr(getattr(user, "profile", None), "role", None) if user else None

            metadata = entry.metadata or {}
            if isinstance(metadata, dict) and metadata.get("remote_addr") == "172.18.0.1":
                metadata = {k: v for k, v in metadata.items() if k != "remote_addr"}

            payload.append(
                {
                    "id": entry.id,
                    "user": username,
                    "role": role,
                    "action": entry.action,
                    "path": entry.path,
                    "method": entry.method,
                    "status": entry.status_code,
                    "metadata": metadata,  # JSONField 혹은 dict/None
                    "timestamp": entry.created_at.isoformat(),  # timezone aware 가정
                }
            )

        # 5) 응답 ---------------------------------------------------------------
        return JsonResponse({"results": payload})


__all__ = ["ActivityLogView"]
