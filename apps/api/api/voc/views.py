"""VOC(Q&A) 게시판 CRUD 뷰.

- GET    /api/v1/voc/posts                          : 게시글 목록 조회
- POST   /api/v1/voc/posts                          : 새 게시글 생성
- PATCH  /api/v1/voc/posts/<id>                     : 제목/내용/상태 수정
- DELETE /api/v1/voc/posts/<id>                     : 게시글 삭제(작성자+관리자)
- POST   /api/v1/voc/posts/<id>/replies             : 답변 추가
"""
from __future__ import annotations

import logging

from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from api.common.activity_logging import (
    merge_activity_metadata,
    set_activity_new_state,
    set_activity_previous_state,
    set_activity_summary,
)
from api.common.utils import parse_json_body

from .selectors import (
    get_default_post_status,
    get_post_detail,
    get_post_list,
    get_status_counts,
    get_valid_post_statuses,
)
from .serializers import serialize_post, serialize_reply
from .services import add_reply, can_manage_post, create_post, delete_post, update_post

logger = logging.getLogger(__name__)

STATUS_SET = get_valid_post_statuses()
MAX_TITLE_LENGTH = 255


@method_decorator(csrf_exempt, name="dispatch")
class VocPostsView(APIView):
    """목록 조회 및 신규 작성."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        status_filter = request.GET.get("status")
        if status_filter:
            if status_filter not in STATUS_SET:
                return JsonResponse({"error": "Invalid status value"}, status=400)
        queryset = get_post_list(status=status_filter)

        posts = [serialize_post(post) for post in queryset]
        return JsonResponse(
            {
                "results": posts,
                "total": len(posts),
                "statusCounts": get_status_counts(),
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
        status = payload.get("status") or get_default_post_status()

        if not title:
            return JsonResponse({"error": "title is required"}, status=400)
        if len(title) > MAX_TITLE_LENGTH:
            return JsonResponse({"error": "title is too long"}, status=400)
        if not content:
            return JsonResponse({"error": "content is required"}, status=400)
        if status not in STATUS_SET:
            return JsonResponse({"error": "Invalid status value"}, status=400)

        try:
            post = create_post(
                title=title,
                content=content,
                status=status,
                author=request.user,
            )

            set_activity_summary(request, "Create VOC post")
            set_activity_new_state(request, serialize_post(post))
            merge_activity_metadata(request, resource="voc_post", entryId=post.pk)

            return JsonResponse(
                {"post": serialize_post(post), "statusCounts": get_status_counts()}, status=201
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
            post = get_post_detail(post_id=post_id)
        except Exception:
            post = None
        if not post:
            return JsonResponse({"error": "Post not found"}, status=404)

        if not can_manage_post(user=request.user, post=post):
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
            before = serialize_post(post)
            post = update_post(post=post, updates=updates)

            set_activity_summary(request, "Update VOC post")
            set_activity_previous_state(request, before)
            set_activity_new_state(request, serialize_post(post))
            merge_activity_metadata(request, resource="voc_post", entryId=post.pk)

            return JsonResponse({"post": serialize_post(post), "statusCounts": get_status_counts()})
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Failed to update VOC post")
            return JsonResponse({"error": "Failed to update post"}, status=500)

    def delete(self, request: HttpRequest, post_id: int, *args: object, **kwargs: object) -> JsonResponse:
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        try:
            post = get_post_detail(post_id=post_id)
        except Exception:
            post = None
        if not post:
            return JsonResponse({"error": "Post not found"}, status=404)

        if not can_manage_post(user=request.user, post=post):
            return JsonResponse({"error": "Forbidden"}, status=403)

        try:
            before = serialize_post(post)
            delete_post(post=post)

            set_activity_summary(request, "Delete VOC post")
            set_activity_previous_state(request, before)
            merge_activity_metadata(request, resource="voc_post", entryId=post_id)

            return JsonResponse({"success": True, "statusCounts": get_status_counts()})
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

        post = get_post_detail(post_id=post_id)
        if not post:
            return JsonResponse({"error": "Post not found"}, status=404)

        try:
            reply, refreshed_post = add_reply(post=post, author=request.user, content=content)

            set_activity_summary(request, "Add VOC reply")
            set_activity_new_state(request, serialize_reply(reply))
            merge_activity_metadata(request, resource="voc_reply", entryId=reply.pk, postId=post_id)

            return JsonResponse(
                {"reply": serialize_reply(reply), "post": serialize_post(refreshed_post)}, status=201
            )
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Failed to add VOC reply")
            return JsonResponse({"error": "Failed to add reply"}, status=500)


__all__ = ["VocPostsView", "VocPostDetailView", "VocReplyView"]
