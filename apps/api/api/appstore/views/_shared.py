# =============================================================================
# 모듈 설명: AppStore HTTP view가 공유하는 조회·커버 응답 helper를 제공합니다.
# - 불변 조건: 권한 판정은 AppStore permission service에 위임합니다.
# =============================================================================
from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from django.http import HttpResponse
from django.urls import reverse

from ..selectors import get_app_by_id
from ..services.permissions import has_appstore_editor_permission

MAX_CATEGORY_LENGTH = 100
MAX_CONTACT_LENGTH = 255
COVER_CACHE_SECONDS = 60 * 60 * 24


def build_cover_path(app: Any) -> str:
    """앱 수정 시점 기반 커버 이미지 경로를 생성합니다."""

    path = reverse("appstore-app-cover", kwargs={"app_id": app.pk})
    updated_at = getattr(app, "updated_at", None)
    if not updated_at:
        return path
    version = str(int(updated_at.timestamp()))
    return f"{path}?{urlencode({'v': version})}"


def cover_etag(app: Any) -> str:
    """커버 이미지 캐시 검증용 ETag 값을 생성합니다."""

    updated_at = getattr(app, "updated_at", None)
    version = int(updated_at.timestamp()) if updated_at else 0
    return f'W/"appstore-cover-{app.pk}-{version}"'


def add_cover_cache_headers(response: HttpResponse, app: Any) -> HttpResponse:
    """커버 이미지 응답에 브라우저 캐시 헤더를 추가합니다."""

    response["Cache-Control"] = f"private, max-age={COVER_CACHE_SECONDS}, immutable"
    response["ETag"] = cover_etag(app)
    return response


def load_app(app_id: int) -> Any | None:
    """앱 id로 AppStoreApp을 조회합니다."""

    return get_app_by_id(app_id=app_id)


def resolve_appstore_admin(request: Any) -> bool:
    """현재 요청 사용자의 AppStore admin 여부를 한 번 계산합니다."""

    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return False
    return has_appstore_editor_permission(user, request=request)
