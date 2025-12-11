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
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from django.db import transaction
from django.db.models import Count, F
from django.db.models.functions import Greatest
from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from api.common.utils import parse_json_body
from api.models import AppStoreApp, AppStoreComment, AppStoreLike

logger = logging.getLogger(__name__)

MAX_TAGS = 20
MAX_TAG_LENGTH = 64
MAX_BADGE_LENGTH = 64
MAX_CATEGORY_LENGTH = 100
MAX_CONTACT_LENGTH = 255


def _user_display_name(user) -> str:
    if not user:
        return ""
    full_name = f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}".strip()
    if full_name:
        return full_name
    username = getattr(user, "username", "") or ""
    if username:
        return username
    return getattr(user, "email", "").split("@")[0]


def _user_knoxid(user) -> str:
    if not user:
        return ""
    email = getattr(user, "email", "")
    if isinstance(email, str) and "@" in email:
        return email.split("@", 1)[0]
    return getattr(user, "username", "") or ""


def _user_payload(user) -> Optional[Dict[str, Any]]:
    if not user:
        return None
    return {
        "id": user.pk,
        "name": _user_display_name(user) or "사용자",
        "knoxid": _user_knoxid(user),
    }


def _default_contact(user) -> Tuple[str, str]:
    return (_user_display_name(user) or "사용자").strip(), _user_knoxid(user)


def _sanitize_tags(tags: Any) -> List[str]:
    if not isinstance(tags, Iterable) or isinstance(tags, (str, bytes)):
        return []
    cleaned: List[str] = []
    seen = set()
    for raw in tags:
        if not isinstance(raw, str):
            continue
        tag = raw.strip()
        if not tag:
            continue
        normalized = tag[:MAX_TAG_LENGTH]
        if normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(normalized)
        if len(cleaned) >= MAX_TAGS:
            break
    return cleaned


def _can_manage_app(user, app: AppStoreApp) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    return getattr(user, "pk", None) is not None and app.owner_id == user.pk


def _can_manage_comment(user, comment: AppStoreComment) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    return getattr(user, "pk", None) is not None and comment.user_id == user.pk


def _comment_payload(comment: AppStoreComment, current_user) -> Dict[str, Any]:
    author = getattr(comment, "user", None)
    return {
        "id": comment.pk,
        "appId": comment.app_id,
        "content": comment.content,
        "createdAt": comment.created_at.isoformat(),
        "updatedAt": comment.updated_at.isoformat(),
        "author": _user_payload(author),
        "canEdit": _can_manage_comment(current_user, comment),
        "canDelete": _can_manage_comment(current_user, comment),
    }


def _app_payload(
    app: AppStoreApp,
    current_user,
    liked_app_ids: Optional[Sequence[int]] = None,
    *,
    include_comments: bool = False,
) -> Dict[str, Any]:
    liked = False
    if current_user and getattr(current_user, "is_authenticated", False):
        if liked_app_ids is not None:
            liked = app.id in liked_app_ids
        else:
            liked = AppStoreLike.objects.filter(app=app, user=current_user).exists()

    comments: Optional[List[Dict[str, Any]]] = None
    if include_comments:
        related = getattr(app, "comments", None)
        comments_qs = related.all() if related is not None else AppStoreComment.objects.filter(app=app)
        comments = [_comment_payload(comment, current_user) for comment in comments_qs]

    owner_payload = _user_payload(getattr(app, "owner", None))

    return {
        "id": app.pk,
        "name": app.name,
        "category": app.category,
        "description": app.description,
        "url": app.url,
        "tags": app.tags if isinstance(app.tags, list) else [],
        "badge": app.badge,
        "contactName": app.contact_name,
        "contactKnoxid": app.contact_knoxid,
        "viewCount": app.view_count,
        "likeCount": app.like_count,
        "commentCount": getattr(app, "comment_count", None)
        if getattr(app, "comment_count", None) is not None
        else app.comments.count(),
        "createdAt": app.created_at.isoformat(),
        "updatedAt": app.updated_at.isoformat(),
        "owner": owner_payload,
        "liked": liked,
        "canEdit": _can_manage_app(current_user, app),
        "canDelete": _can_manage_app(current_user, app),
        **({"comments": comments} if comments is not None else {}),
    }


def _load_app(app_id: int) -> Optional[AppStoreApp]:
    try:
        return (
            AppStoreApp.objects.select_related("owner")
            .annotate(comment_count=Count("comments"))
            .get(pk=app_id)
        )
    except AppStoreApp.DoesNotExist:
        return None


@method_decorator(csrf_exempt, name="dispatch")
class AppStoreAppsView(APIView):
    """앱 목록 조회 및 신규 등록."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        queryset = (
            AppStoreApp.objects.select_related("owner")
            .annotate(comment_count=Count("comments"))
            .order_by("-created_at", "-id")
        )
        liked_ids: Sequence[int] = []
        user = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
        if user:
            liked_ids = list(
                AppStoreLike.objects.filter(user=user).values_list("app_id", flat=True)
            )

        apps = [_app_payload(app, user, liked_ids) for app in queryset]
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
        tags = _sanitize_tags(payload.get("tags"))
        contact_name = str(payload.get("contactName") or "").strip()[:MAX_CONTACT_LENGTH]
        contact_knoxid = str(payload.get("contactKnoxid") or "").strip()[:MAX_CONTACT_LENGTH]

        if not name:
            return JsonResponse({"error": "name is required"}, status=400)
        if not category:
            return JsonResponse({"error": "category is required"}, status=400)
        if not url:
            return JsonResponse({"error": "url is required"}, status=400)

        if not contact_name or not contact_knoxid:
            default_name, default_knoxid = _default_contact(request.user)
            contact_name = contact_name or default_name
            contact_knoxid = contact_knoxid or default_knoxid

        try:
            app = AppStoreApp.objects.create(
                name=name,
                category=category,
                description=description,
                url=url,
                badge=badge,
                tags=tags,
                contact_name=contact_name,
                contact_knoxid=contact_knoxid,
                owner=request.user,
            )
            app.refresh_from_db()
            app.comment_count = 0
            return JsonResponse({"app": _app_payload(app, request.user)}, status=201)
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Failed to create appstore app")
            return JsonResponse({"error": "Failed to create app"}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class AppStoreAppDetailView(APIView):
    """앱 단건 조회/수정/삭제."""

    def get(self, request: HttpRequest, app_id: int, *args: object, **kwargs: object) -> JsonResponse:
        try:
            app = (
                AppStoreApp.objects.select_related("owner")
                .prefetch_related("comments__user")
                .annotate(comment_count=Count("comments"))
                .get(pk=app_id)
            )
        except AppStoreApp.DoesNotExist:
            return JsonResponse({"error": "App not found"}, status=404)
        liked_ids: Sequence[int] = []
        user = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
        if user:
            liked_ids = list(
                AppStoreLike.objects.filter(user=user).values_list("app_id", flat=True)
            )

        return JsonResponse({"app": _app_payload(app, user, liked_ids, include_comments=True)})

    def patch(self, request: HttpRequest, app_id: int, *args: object, **kwargs: object) -> JsonResponse:
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        app = _load_app(app_id)
        if not app:
            return JsonResponse({"error": "App not found"}, status=404)

        if not _can_manage_app(request.user, app):
            return JsonResponse({"error": "Forbidden"}, status=403)

        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        updated = False

        if "name" in payload:
            name = str(payload.get("name") or "").strip()
            if not name:
                return JsonResponse({"error": "name is required"}, status=400)
            app.name = name
            updated = True

        if "category" in payload:
            category = str(payload.get("category") or "").strip()[:MAX_CATEGORY_LENGTH]
            if not category:
                return JsonResponse({"error": "category is required"}, status=400)
            app.category = category
            updated = True

        if "description" in payload:
            app.description = str(payload.get("description") or "").strip()
            updated = True

        if "url" in payload:
            url = str(payload.get("url") or "").strip()
            if not url:
                return JsonResponse({"error": "url is required"}, status=400)
            app.url = url
            updated = True

        if "badge" in payload:
            app.badge = str(payload.get("badge") or "").strip()[:MAX_BADGE_LENGTH]
            updated = True

        if "tags" in payload:
            app.tags = _sanitize_tags(payload.get("tags"))
            updated = True

        if "contactName" in payload:
            app.contact_name = str(payload.get("contactName") or "").strip()[:MAX_CONTACT_LENGTH]
            updated = True

        if "contactKnoxid" in payload:
            app.contact_knoxid = str(payload.get("contactKnoxid") or "").strip()[:MAX_CONTACT_LENGTH]
            updated = True

        if not updated:
            return JsonResponse({"error": "No changes provided"}, status=400)

        try:
            app.save()
            app.refresh_from_db()
            app.comment_count = app.comments.count()
            return JsonResponse({"app": _app_payload(app, request.user)})
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Failed to update appstore app")
            return JsonResponse({"error": "Failed to update app"}, status=500)

    def delete(self, request: HttpRequest, app_id: int, *args: object, **kwargs: object) -> JsonResponse:
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        app = _load_app(app_id)
        if not app:
            return JsonResponse({"error": "App not found"}, status=404)

        if not _can_manage_app(request.user, app):
            return JsonResponse({"error": "Forbidden"}, status=403)

        try:
            app.delete()
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
            with transaction.atomic():
                like, created = AppStoreLike.objects.select_for_update().get_or_create(
                    app=app, user=request.user
                )
                if created:
                    AppStoreApp.objects.filter(pk=app.pk).update(like_count=F("like_count") + 1)
                    liked = True
                else:
                    like.delete()
                    AppStoreApp.objects.filter(pk=app.pk).update(
                        like_count=Greatest(F("like_count") - 1, 0)
                    )
                    liked = False

            app.refresh_from_db(fields=["like_count"])
            return JsonResponse(
                {"liked": liked, "likeCount": app.like_count, "appId": app.pk},
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

        AppStoreApp.objects.filter(pk=app.pk).update(view_count=F("view_count") + 1)
        app.refresh_from_db(fields=["view_count"])
        return JsonResponse({"viewCount": app.view_count, "appId": app.pk})


@method_decorator(csrf_exempt, name="dispatch")
class AppStoreCommentsView(APIView):
    """댓글 목록 조회/작성."""

    def get(self, request: HttpRequest, app_id: int, *args: object, **kwargs: object) -> JsonResponse:
        app = _load_app(app_id)
        if not app:
            return JsonResponse({"error": "App not found"}, status=404)

        comments = (
            AppStoreComment.objects.filter(app=app)
            .select_related("user")
            .order_by("created_at", "id")
        )
        payload = [_comment_payload(comment, request.user) for comment in comments]
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

        try:
            comment = AppStoreComment.objects.create(app=app, user=request.user, content=content)
            return JsonResponse(
                {"comment": _comment_payload(comment, request.user)},
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

        try:
            comment = AppStoreComment.objects.select_related("user", "app").get(
                pk=comment_id, app_id=app.pk
            )
        except AppStoreComment.DoesNotExist:
            return JsonResponse({"error": "Comment not found"}, status=404)

        if not _can_manage_comment(request.user, comment):
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
            comment.content = content
            comment.save(update_fields=["content", "updated_at"])
            comment.refresh_from_db()
            return JsonResponse({"comment": _comment_payload(comment, request.user)})
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

        try:
            comment = AppStoreComment.objects.get(pk=comment_id, app_id=app.pk)
        except AppStoreComment.DoesNotExist:
            return JsonResponse({"error": "Comment not found"}, status=404)

        if not _can_manage_comment(request.user, comment):
            return JsonResponse({"error": "Forbidden"}, status=403)

        try:
            comment.delete()
            return JsonResponse({"success": True})
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Failed to delete appstore comment %s", comment_id)
            return JsonResponse({"error": "Failed to delete comment"}, status=500)


__all__ = [
    "AppStoreAppsView",
    "AppStoreAppDetailView",
    "AppStoreLikeToggleView",
    "AppStoreViewIncrementView",
    "AppStoreCommentsView",
    "AppStoreCommentDetailView",
]
