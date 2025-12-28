"""Appstore CRUD/interaction endpoints.

- GET    /api/v1/appstore/apps                    : 앱 목록 조회
- POST   /api/v1/appstore/apps                    : 앱 등록
- GET    /api/v1/appstore/apps/<id>               : 단일 앱 상세(+댓글)
- PATCH  /api/v1/appstore/apps/<id>               : 앱 정보 수정
- DELETE /api/v1/appstore/apps/<id>               : 앱 삭제 (작성자+superuser)
- POST   /api/v1/appstore/apps/<id>/like          : 좋아요 토글
- POST   /api/v1/appstore/apps/<id>/view          : 조회수 증가
- GET    /api/v1/appstore/apps/<id>/comments      : 댓글 목록
- POST   /api/v1/appstore/apps/<id>/comments      : 댓글 작성
- PATCH  /api/v1/appstore/apps/<id>/comments/<cid>: 댓글 수정
- DELETE /api/v1/appstore/apps/<id>/comments/<cid>: 댓글 삭제
- POST   /api/v1/appstore/apps/<id>/comments/<cid>/like: 댓글 좋아요 토글
"""
from __future__ import annotations

import logging
from typing import Any, Sequence

from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from api.common.utils import parse_json_body

from .selectors import (
    get_app_by_id,
    get_app_detail,
    get_app_list,
    get_comment_by_id,
    get_comments_for_app,
    get_liked_app_ids_for_user,
    get_liked_comment_ids_for_user,
)
from .serializers import (
    apply_cover_index,
    can_manage_app,
    can_manage_comment,
    default_contact,
    sanitize_screenshot_urls,
    sanitize_tags,
    serialize_app,
    serialize_comment,
)
from .services import (
    create_app,
    create_comment,
    delete_app,
    delete_comment,
    increment_view_count,
    toggle_comment_like,
    toggle_like,
    update_app,
    update_comment,
)

logger = logging.getLogger(__name__)

MAX_BADGE_LENGTH = 64
MAX_CATEGORY_LENGTH = 100
MAX_CONTACT_LENGTH = 255


def _load_app(app_id: int) -> Any | None:
    """앱 id로 AppStoreApp을 조회합니다."""

    return get_app_by_id(app_id=app_id)


@method_decorator(csrf_exempt, name="dispatch")
class AppStoreAppsView(APIView):
    """앱 목록 조회 및 신규 등록."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        queryset = get_app_list()
        liked_ids: Sequence[int] = []
        user = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
        if user:
            liked_ids = get_liked_app_ids_for_user(user=user)

        apps = [serialize_app(app, user, liked_ids) for app in queryset]
        return JsonResponse({"results": apps, "total": len(apps)})

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        name = str(payload.get("name") or "").strip()
        category = str(payload.get("category") or "").strip()[:MAX_CATEGORY_LENGTH]
        description = str(payload.get("description") or "").strip()
        url = str(payload.get("url") or "").strip()
        badge = str(payload.get("badge") or "").strip()[:MAX_BADGE_LENGTH]
        tags = sanitize_tags(payload.get("tags"))
        screenshot_urls = sanitize_screenshot_urls(payload.get("screenshotUrls") or payload.get("screenshot_urls"))
        screenshot_urls = apply_cover_index(
            screenshot_urls,
            payload.get("coverScreenshotIndex") or payload.get("cover_screenshot_index"),
        )
        screenshot_url = str(payload.get("screenshotUrl") or payload.get("screenshot_url") or "").strip()
        contact_name = str(payload.get("contactName") or "").strip()[:MAX_CONTACT_LENGTH]
        contact_knoxid = str(payload.get("contactKnoxid") or "").strip()[:MAX_CONTACT_LENGTH]

        if not name:
            return JsonResponse({"error": "name is required"}, status=400)
        if not category:
            return JsonResponse({"error": "category is required"}, status=400)
        if not url:
            return JsonResponse({"error": "url is required"}, status=400)

        if not contact_name or not contact_knoxid:
            default_name, default_knoxid = default_contact(request.user)
            contact_name = contact_name or default_name
            contact_knoxid = contact_knoxid or default_knoxid

        try:
            app = create_app(
                owner=request.user,
                name=name,
                category=category,
                description=description,
                url=url,
                badge=badge,
                tags=tags,
                screenshot_urls=screenshot_urls,
                screenshot_url=screenshot_url,
                contact_name=contact_name,
                contact_knoxid=contact_knoxid,
            )
            liked_ids = get_liked_app_ids_for_user(user=request.user)
            return JsonResponse(
                {"app": serialize_app(app, request.user, liked_ids, include_screenshots=True)},
                status=201,
            )
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Failed to create appstore app")
            return JsonResponse({"error": "Failed to create app"}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class AppStoreAppDetailView(APIView):
    """앱 단건 조회/수정/삭제."""

    def get(self, request: HttpRequest, app_id: int, *args: object, **kwargs: object) -> JsonResponse:
        app = get_app_detail(app_id=app_id)
        if not app:
            return JsonResponse({"error": "App not found"}, status=404)
        liked_ids: Sequence[int] = []
        user = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
        liked_comment_ids: set[int] = set()
        if user:
            liked_ids = get_liked_app_ids_for_user(user=user)
            liked_comment_ids = set(get_liked_comment_ids_for_user(user=user, app_id=app.pk))

        return JsonResponse(
            {
                "app": serialize_app(
                    app,
                    user,
                    liked_ids,
                    include_comments=True,
                    include_screenshots=True,
                    liked_comment_ids=liked_comment_ids,
                )
            }
        )

    def patch(self, request: HttpRequest, app_id: int, *args: object, **kwargs: object) -> JsonResponse:
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        app = _load_app(app_id)
        if not app:
            return JsonResponse({"error": "App not found"}, status=404)

        if not can_manage_app(request.user, app):
            return JsonResponse({"error": "Forbidden"}, status=403)

        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        updates: dict[str, Any] = {}

        if "name" in payload:
            name = str(payload.get("name") or "").strip()
            if not name:
                return JsonResponse({"error": "name is required"}, status=400)
            updates["name"] = name

        if "category" in payload:
            category = str(payload.get("category") or "").strip()[:MAX_CATEGORY_LENGTH]
            if not category:
                return JsonResponse({"error": "category is required"}, status=400)
            updates["category"] = category

        if "description" in payload:
            updates["description"] = str(payload.get("description") or "").strip()

        if "url" in payload:
            url = str(payload.get("url") or "").strip()
            if not url:
                return JsonResponse({"error": "url is required"}, status=400)
            updates["url"] = url

        if "screenshotUrl" in payload or "screenshot_url" in payload:
            updates["screenshot_url"] = str(payload.get("screenshotUrl") or payload.get("screenshot_url") or "").strip()

        screenshot_urls = None
        if "screenshotUrls" in payload or "screenshot_urls" in payload:
            screenshot_urls = sanitize_screenshot_urls(payload.get("screenshotUrls") or payload.get("screenshot_urls"))
            screenshot_urls = apply_cover_index(
                screenshot_urls,
                payload.get("coverScreenshotIndex") or payload.get("cover_screenshot_index"),
            )
            updates.pop("screenshot_url", None)
            updates["screenshot_urls"] = screenshot_urls

        if "badge" in payload:
            updates["badge"] = str(payload.get("badge") or "").strip()[:MAX_BADGE_LENGTH]

        if "tags" in payload:
            updates["tags"] = sanitize_tags(payload.get("tags"))

        if "contactName" in payload:
            updates["contact_name"] = str(payload.get("contactName") or "").strip()[:MAX_CONTACT_LENGTH]

        if "contactKnoxid" in payload:
            updates["contact_knoxid"] = str(payload.get("contactKnoxid") or "").strip()[:MAX_CONTACT_LENGTH]

        if not updates:
            return JsonResponse({"error": "No changes provided"}, status=400)

        try:
            app = update_app(app=app, updates=updates)
            liked_ids = get_liked_app_ids_for_user(user=request.user)
            return JsonResponse({"app": serialize_app(app, request.user, liked_ids, include_screenshots=True)})
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Failed to update appstore app")
            return JsonResponse({"error": "Failed to update app"}, status=500)

    def delete(self, request: HttpRequest, app_id: int, *args: object, **kwargs: object) -> JsonResponse:
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        app = _load_app(app_id)
        if not app:
            return JsonResponse({"error": "App not found"}, status=404)

        if not can_manage_app(request.user, app):
            return JsonResponse({"error": "Forbidden"}, status=403)

        try:
            delete_app(app=app)
            return JsonResponse({"success": True})
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Failed to delete appstore app")
            return JsonResponse({"error": "Failed to delete app"}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class AppStoreLikeToggleView(APIView):
    """좋아요 토글."""

    def post(self, request: HttpRequest, app_id: int, *args: object, **kwargs: object) -> JsonResponse:
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        app = _load_app(app_id)
        if not app:
            return JsonResponse({"error": "App not found"}, status=404)

        try:
            liked, like_count = toggle_like(app=app, user=request.user)
            return JsonResponse(
                {"liked": liked, "likeCount": like_count, "appId": app.pk},
                status=200,
            )
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Failed to toggle like for appstore app %s", app_id)
            return JsonResponse({"error": "Failed to toggle like"}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class AppStoreViewIncrementView(APIView):
    """조회수 증가."""

    def post(self, request: HttpRequest, app_id: int, *args: object, **kwargs: object) -> JsonResponse:
        app = _load_app(app_id)
        if not app:
            return JsonResponse({"error": "App not found"}, status=404)

        view_count = increment_view_count(app=app)
        return JsonResponse({"viewCount": view_count, "appId": app.pk})


@method_decorator(csrf_exempt, name="dispatch")
class AppStoreCommentsView(APIView):
    """댓글 목록 조회/작성."""

    def get(self, request: HttpRequest, app_id: int, *args: object, **kwargs: object) -> JsonResponse:
        app = _load_app(app_id)
        if not app:
            return JsonResponse({"error": "App not found"}, status=404)

        comments = get_comments_for_app(app_id=app.pk)
        liked_comment_ids: set[int] = set()
        if request.user.is_authenticated:
            liked_comment_ids = set(get_liked_comment_ids_for_user(user=request.user, app_id=app.pk))
        payload = [serialize_comment(comment, request.user, liked_comment_ids) for comment in comments]
        return JsonResponse({"comments": payload, "total": len(payload)})

    def post(self, request: HttpRequest, app_id: int, *args: object, **kwargs: object) -> JsonResponse:
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        app = _load_app(app_id)
        if not app:
            return JsonResponse({"error": "App not found"}, status=404)

        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        content = str(payload.get("content") or "").strip()
        if not content:
            return JsonResponse({"error": "content is required"}, status=400)

        parent_comment: Any | None = None
        raw_parent_id = payload.get("parentCommentId") or payload.get("parent_comment_id")
        if raw_parent_id is not None and str(raw_parent_id).strip():
            try:
                parent_id = int(raw_parent_id)
            except (TypeError, ValueError):
                return JsonResponse({"error": "parentCommentId must be an integer"}, status=400)

            parent_comment = get_comment_by_id(app_id=app.pk, comment_id=parent_id)
            if not parent_comment:
                return JsonResponse({"error": "Parent comment not found"}, status=404)

        try:
            comment = create_comment(app=app, user=request.user, content=content, parent_comment=parent_comment)
            return JsonResponse(
                {"comment": serialize_comment(comment, request.user, set())},
                status=201,
            )
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Failed to create appstore comment")
            return JsonResponse({"error": "Failed to create comment"}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class AppStoreCommentDetailView(APIView):
    """댓글 수정/삭제."""

    def patch(
        self, request: HttpRequest, app_id: int, comment_id: int, *args: object, **kwargs: object
    ) -> JsonResponse:
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        app = _load_app(app_id)
        if not app:
            return JsonResponse({"error": "App not found"}, status=404)

        comment = get_comment_by_id(app_id=app.pk, comment_id=comment_id)
        if not comment:
            return JsonResponse({"error": "Comment not found"}, status=404)

        if not can_manage_comment(request.user, comment):
            return JsonResponse({"error": "Forbidden"}, status=403)

        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        if "content" not in payload:
            return JsonResponse({"error": "content is required"}, status=400)

        content = str(payload.get("content") or "").strip()
        if not content:
            return JsonResponse({"error": "content is required"}, status=400)

        try:
            comment = update_comment(comment=comment, content=content)
            liked_comment_ids: set[int] = set()
            if request.user.is_authenticated:
                liked_comment_ids = set(get_liked_comment_ids_for_user(user=request.user, app_id=app.pk))
            return JsonResponse({"comment": serialize_comment(comment, request.user, liked_comment_ids)})
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Failed to update appstore comment %s", comment_id)
            return JsonResponse({"error": "Failed to update comment"}, status=500)

    def delete(
        self, request: HttpRequest, app_id: int, comment_id: int, *args: object, **kwargs: object
    ) -> JsonResponse:
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        app = _load_app(app_id)
        if not app:
            return JsonResponse({"error": "App not found"}, status=404)

        comment = get_comment_by_id(app_id=app.pk, comment_id=comment_id)
        if not comment:
            return JsonResponse({"error": "Comment not found"}, status=404)

        if not can_manage_comment(request.user, comment):
            return JsonResponse({"error": "Forbidden"}, status=403)

        try:
            delete_comment(comment=comment)
            return JsonResponse({"success": True})
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Failed to delete appstore comment %s", comment_id)
            return JsonResponse({"error": "Failed to delete comment"}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class AppStoreCommentLikeToggleView(APIView):
    """댓글 좋아요 토글."""

    def post(
        self, request: HttpRequest, app_id: int, comment_id: int, *args: object, **kwargs: object
    ) -> JsonResponse:
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        app = _load_app(app_id)
        if not app:
            return JsonResponse({"error": "App not found"}, status=404)

        comment = get_comment_by_id(app_id=app.pk, comment_id=comment_id)
        if not comment:
            return JsonResponse({"error": "Comment not found"}, status=404)

        try:
            liked, like_count = toggle_comment_like(comment=comment, user=request.user)
            return JsonResponse(
                {
                    "appId": app.pk,
                    "commentId": comment.pk,
                    "liked": liked,
                    "likeCount": like_count,
                },
                status=200,
            )
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Failed to toggle comment like for app %s comment %s", app_id, comment_id)
            return JsonResponse({"error": "Failed to toggle comment like"}, status=500)


__all__ = [
    "AppStoreAppsView",
    "AppStoreAppDetailView",
    "AppStoreLikeToggleView",
    "AppStoreViewIncrementView",
    "AppStoreCommentsView",
    "AppStoreCommentDetailView",
    "AppStoreCommentLikeToggleView",
]
