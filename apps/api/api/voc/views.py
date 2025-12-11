"""VOC(Q&A) 게시판 CRUD 뷰.

- GET    /voc/posts                          : 게시글 목록 조회
- POST   /voc/posts                          : 새 게시글 생성
- PATCH  /voc/posts/<id>                     : 제목/내용/상태 수정
- DELETE /voc/posts/<id>                     : 게시글 삭제(작성자+관리자)
- POST   /voc/posts/<id>/replies             : 답변 추가
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, Optional

from django.db.models import Count
from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from api.common.utils import parse_json_body

from ..activity_logging import (
    merge_activity_metadata,
    set_activity_new_state,
    set_activity_previous_state,
    set_activity_summary,
)
from ..models import UserProfile, VocPost, VocReply

logger = logging.getLogger(__name__)

STATUS_VALUES: Iterable[str] = [choice[0] for choice in VocPost.Status.choices]
STATUS_SET = set(STATUS_VALUES)
MAX_TITLE_LENGTH = 255


def _user_payload(user) -> Optional[Dict[str, Any]]:
    """작성자 정보를 API 응답 형태로 직렬화."""

    if not user:
        return None
    name = (user.get_full_name() or "").strip() or user.get_username() or user.email
    payload = {"id": user.pk, "name": name or "사용자"}
    if user.email:
        payload["email"] = user.email
    return payload


def _reply_payload(reply: VocReply) -> Dict[str, Any]:
    return {
        "id": reply.pk,
        "postId": reply.post_id,
        "content": reply.content,
        "createdAt": reply.created_at.isoformat(),
        "author": _user_payload(getattr(reply, "author", None)),
    }


def _post_payload(post: VocPost) -> Dict[str, Any]:
    replies = [*_prefetched_replies(post)]
    return {
        "id": post.pk,
        "title": post.title,
        "content": post.content,
        "status": post.status,
        "createdAt": post.created_at.isoformat(),
        "updatedAt": post.updated_at.isoformat(),
        "author": _user_payload(getattr(post, "author", None)),
        "replies": replies,
    }


def _prefetched_replies(post: VocPost) -> Iterable[Dict[str, Any]]:
    """prefetch_related 결과를 활용해 답변을 직렬화."""

    related = getattr(post, "replies", None)
    if not related:
        return []
    return [_reply_payload(reply) for reply in related.all()]


def _status_counts() -> Dict[str, int]:
    base = {status: 0 for status in STATUS_SET}
    for row in VocPost.objects.values("status").annotate(total=Count("id")):
        status = row.get("status")
        if status in base:
            base[status] = int(row.get("total") or 0)
    return base


def _is_admin(user) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
        return True
    profile = getattr(user, "profile", None)
    role = getattr(profile, "role", None) if profile else None
    return role == UserProfile.Roles.ADMIN


def _can_manage_post(user, post: VocPost) -> bool:
    return _is_admin(user) or (user and getattr(user, "pk", None) == post.author_id)


@method_decorator(csrf_exempt, name="dispatch")
class VocPostsView(APIView):
    """목록 조회 및 신규 작성."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        status_filter = request.GET.get("status")
        queryset = (
            VocPost.objects.select_related("author")
            .prefetch_related("replies__author")
            .order_by("-created_at", "-id")
        )
        if status_filter:
            if status_filter not in STATUS_SET:
                return JsonResponse({"error": "Invalid status value"}, status=400)
            queryset = queryset.filter(status=status_filter)

        posts = [_post_payload(post) for post in queryset]
        return JsonResponse(
            {
                "results": posts,
                "total": len(posts),
                "statusCounts": _status_counts(),
            }
        )

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        title = str(payload.get("title") or "").strip()
        content = str(payload.get("content") or "").strip()
        status = payload.get("status") or VocPost.Status.RECEIVED

        if not title:
            return JsonResponse({"error": "title is required"}, status=400)
        if len(title) > MAX_TITLE_LENGTH:
            return JsonResponse({"error": "title is too long"}, status=400)
        if not content:
            return JsonResponse({"error": "content is required"}, status=400)
        if status not in STATUS_SET:
            return JsonResponse({"error": "Invalid status value"}, status=400)

        try:
            post = VocPost.objects.create(
                title=title,
                content=content,
                status=status,
                author=request.user,
            )
            post = (
                VocPost.objects.select_related("author")
                .prefetch_related("replies__author")
                .get(pk=post.pk)
            )

            set_activity_summary(request, "Create VOC post")
            set_activity_new_state(request, _post_payload(post))
            merge_activity_metadata(request, resource="voc_post", entryId=post.pk)

            return JsonResponse(
                {"post": _post_payload(post), "statusCounts": _status_counts()}, status=201
            )
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Failed to create VOC post")
            return JsonResponse({"error": "Failed to create post"}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class VocPostDetailView(APIView):
    """단일 게시글 수정/삭제."""

    def patch(self, request: HttpRequest, post_id: int, *args: object, **kwargs: object) -> JsonResponse:
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        try:
            post = (
                VocPost.objects.select_related("author")
                .prefetch_related("replies__author")
                .get(pk=post_id)
            )
        except VocPost.DoesNotExist:
            return JsonResponse({"error": "Post not found"}, status=404)

        if not _can_manage_post(request.user, post):
            return JsonResponse({"error": "Forbidden"}, status=403)

        updates = {}
        if "title" in payload:
            title = str(payload.get("title") or "").strip()
            if not title:
                return JsonResponse({"error": "title is required"}, status=400)
            if len(title) > MAX_TITLE_LENGTH:
                return JsonResponse({"error": "title is too long"}, status=400)
            updates["title"] = title

        if "content" in payload:
            content = str(payload.get("content") or "").strip()
            if not content:
                return JsonResponse({"error": "content is required"}, status=400)
            updates["content"] = content

        if "status" in payload:
            status = payload.get("status")
            if status not in STATUS_SET:
                return JsonResponse({"error": "Invalid status value"}, status=400)
            updates["status"] = status

        if not updates:
            return JsonResponse({"error": "No changes provided"}, status=400)

        try:
            before = _post_payload(post)
            for field, value in updates.items():
                setattr(post, field, value)
            post.save(update_fields=list(updates.keys()) + ["updated_at"])
            post.refresh_from_db()
            post = (
                VocPost.objects.select_related("author")
                .prefetch_related("replies__author")
                .get(pk=post.pk)
            )

            set_activity_summary(request, "Update VOC post")
            set_activity_previous_state(request, before)
            set_activity_new_state(request, _post_payload(post))
            merge_activity_metadata(request, resource="voc_post", entryId=post.pk)

            return JsonResponse({"post": _post_payload(post), "statusCounts": _status_counts()})
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Failed to update VOC post")
            return JsonResponse({"error": "Failed to update post"}, status=500)

    def delete(self, request: HttpRequest, post_id: int, *args: object, **kwargs: object) -> JsonResponse:
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        try:
            post = VocPost.objects.select_related("author").get(pk=post_id)
        except VocPost.DoesNotExist:
            return JsonResponse({"error": "Post not found"}, status=404)

        if not _can_manage_post(request.user, post):
            return JsonResponse({"error": "Forbidden"}, status=403)

        try:
            before = _post_payload(post)
            post.delete()

            set_activity_summary(request, "Delete VOC post")
            set_activity_previous_state(request, before)
            merge_activity_metadata(request, resource="voc_post", entryId=post_id)

            return JsonResponse({"success": True, "statusCounts": _status_counts()})
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Failed to delete VOC post")
            return JsonResponse({"error": "Failed to delete post"}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class VocReplyView(APIView):
    """답변 추가."""

    def post(self, request: HttpRequest, post_id: int, *args: object, **kwargs: object) -> JsonResponse:
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        content = str(payload.get("content") or "").strip()
        if not content:
            return JsonResponse({"error": "content is required"}, status=400)

        try:
            post = VocPost.objects.get(pk=post_id)
        except VocPost.DoesNotExist:
            return JsonResponse({"error": "Post not found"}, status=404)

        try:
            reply = VocReply.objects.create(post=post, author=request.user, content=content)
            reply = VocReply.objects.select_related("author", "post").get(pk=reply.pk)

            set_activity_summary(request, "Add VOC reply")
            set_activity_new_state(request, _reply_payload(reply))
            merge_activity_metadata(request, resource="voc_reply", entryId=reply.pk, postId=post_id)

            refreshed_post = (
                VocPost.objects.select_related("author")
                .prefetch_related("replies__author")
                .get(pk=post_id)
            )

            return JsonResponse({"reply": _reply_payload(reply), "post": _post_payload(refreshed_post)}, status=201)
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Failed to add VOC reply")
            return JsonResponse({"error": "Failed to add reply"}, status=500)


__all__ = ["VocPostsView", "VocPostDetailView", "VocReplyView"]
