# =============================================================================
# 모듈 설명: VOC 게시판 HTTP 요청과 응답을 조립합니다.
# - 주요 클래스: VocPostsView, VocPostDetailView, VocReplyView
# - 불변 조건: view는 인증, serializer, selector/service 호출과 응답 변환만 담당합니다.
# =============================================================================

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import serializers
from rest_framework.exceptions import ParseError, UnsupportedMediaType
from rest_framework.request import Request
from rest_framework.views import APIView

from api.common.services import (
    extract_first_error_message,
    merge_activity_metadata,
    set_activity_new_state,
    set_activity_previous_state,
    set_activity_summary,
)

from .selectors import get_post_detail, get_post_list
from .serializers import (
    VocPostCreateInputSerializer,
    VocPostOutputSerializer,
    VocPostUpdateInputSerializer,
    VocReplyCreateInputSerializer,
    VocReplyOutputSerializer,
)
from .services import add_reply, can_manage_post, create_post, delete_post, update_post


def _json_error(message: str, *, status: int) -> JsonResponse:
    """VOC의 canonical 오류 payload를 반환합니다."""

    return JsonResponse({"error": message}, status=status)


def _read_request_data(request: Request) -> tuple[dict[str, Any] | None, JsonResponse | None]:
    """DRF parser로 JSON 객체를 읽고 기존 오류 envelope로 변환합니다."""

    try:
        payload = request.data
    except (ParseError, UnsupportedMediaType):
        return None, _json_error("Invalid JSON body", status=400)

    if not isinstance(payload, Mapping):
        return None, _json_error("Invalid JSON body", status=400)
    return dict(payload), None


def _validated_data(
    serializer: serializers.Serializer,
) -> tuple[dict[str, Any] | None, JsonResponse | None]:
    """serializer 검증 결과를 service 입력 또는 400 응답으로 변환합니다."""

    if serializer.is_valid():
        return dict(serializer.validated_data), None
    message = extract_first_error_message(serializer.errors)
    return None, _json_error(message, status=400)


def _serialize_post(post: Any) -> dict[str, Any]:
    """게시글 객체를 canonical camelCase payload로 변환합니다."""

    return dict(VocPostOutputSerializer(post).data)


def _serialize_reply(reply: Any) -> dict[str, Any]:
    """답변 객체를 canonical camelCase payload로 변환합니다."""

    return dict(VocReplyOutputSerializer(reply).data)


@method_decorator(csrf_exempt, name="dispatch")
class VocPostsView(APIView):
    """VOC 게시글 목록 조회와 생성을 처리합니다."""

    def get(self, request: Request, *args: object, **kwargs: object) -> JsonResponse:
        """VOC 게시글 전체 목록을 반환합니다.

        예시 요청:
        - `GET /api/v1/voc/posts`

        응답 계약:
        - `{"results": VocPost[]}` camelCase 계약만 제공합니다.
        """

        posts = [_serialize_post(post) for post in get_post_list()]
        return JsonResponse({"results": posts})

    def post(self, request: Request, *args: object, **kwargs: object) -> JsonResponse:
        """검증된 JSON payload로 VOC 게시글을 생성합니다.

        예시 요청:
        - `POST /api/v1/voc/posts`
        - `{"title":"제목","content":"내용","status":"접수","app":"기타"}`

        호환 정책:
        - request key는 canonical 필드만 허용하며 snake_case 별칭은 제공하지 않습니다.
        """

        if not request.user.is_authenticated:
            return _json_error("Authentication required", status=401)

        payload, error_response = _read_request_data(request)
        if error_response:
            return error_response
        post_data, error_response = _validated_data(
            VocPostCreateInputSerializer(data=payload)
        )
        if error_response:
            return error_response

        post = create_post(author=request.user, **(post_data or {}))
        serialized = _serialize_post(post)
        set_activity_summary(request, "Create VOC post")
        set_activity_new_state(request, serialized)
        merge_activity_metadata(request, resource="voc_post", entryId=post.pk)
        return JsonResponse({"post": serialized}, status=201)


@method_decorator(csrf_exempt, name="dispatch")
class VocPostDetailView(APIView):
    """VOC 게시글 수정과 삭제를 처리합니다."""

    def patch(
        self,
        request: Request,
        post_id: int,
        *args: object,
        **kwargs: object,
    ) -> JsonResponse:
        """작성자 또는 VOC 관리자의 게시글을 수정합니다.

        예시 요청:
        - `PATCH /api/v1/voc/posts/1`
        - `{"title":"수정 제목","status":"진행중"}`

        호환 정책:
        - title/content/status/app canonical 필드만 허용합니다.
        """

        if not request.user.is_authenticated:
            return _json_error("Authentication required", status=401)

        payload, error_response = _read_request_data(request)
        if error_response:
            return error_response
        post = get_post_detail(post_id=post_id)
        if post is None:
            return _json_error("Post not found", status=404)
        if not can_manage_post(user=request.user, post=post, request=request):
            return _json_error("Forbidden", status=403)

        updates, error_response = _validated_data(
            VocPostUpdateInputSerializer(data=payload)
        )
        if error_response:
            return error_response

        before = _serialize_post(post)
        updated_post = update_post(post=post, updates=updates or {})
        serialized = _serialize_post(updated_post)
        set_activity_summary(request, "Update VOC post")
        set_activity_previous_state(request, before)
        set_activity_new_state(request, serialized)
        merge_activity_metadata(request, resource="voc_post", entryId=updated_post.pk)
        return JsonResponse({"post": serialized})

    def delete(
        self,
        request: Request,
        post_id: int,
        *args: object,
        **kwargs: object,
    ) -> JsonResponse:
        """작성자 또는 VOC 관리자의 게시글을 삭제합니다.

        예시 요청:
        - `DELETE /api/v1/voc/posts/1`

        호환 정책:
        - 요청 바디가 없으며 `{"success": true}`만 반환합니다.
        """

        if not request.user.is_authenticated:
            return _json_error("Authentication required", status=401)

        post = get_post_detail(post_id=post_id)
        if post is None:
            return _json_error("Post not found", status=404)
        if not can_manage_post(user=request.user, post=post, request=request):
            return _json_error("Forbidden", status=403)

        before = _serialize_post(post)
        delete_post(post=post)
        set_activity_summary(request, "Delete VOC post")
        set_activity_previous_state(request, before)
        merge_activity_metadata(request, resource="voc_post", entryId=post_id)
        return JsonResponse({"success": True})


@method_decorator(csrf_exempt, name="dispatch")
class VocReplyView(APIView):
    """VOC 게시글 답변 생성을 처리합니다."""

    def post(
        self,
        request: Request,
        post_id: int,
        *args: object,
        **kwargs: object,
    ) -> JsonResponse:
        """인증 사용자의 답변을 생성합니다.

        예시 요청:
        - `POST /api/v1/voc/posts/1/replies`
        - `{"content":"답변 내용"}`

        호환 정책:
        - content canonical 필드만 허용합니다.
        """

        if not request.user.is_authenticated:
            return _json_error("Authentication required", status=401)

        payload, error_response = _read_request_data(request)
        if error_response:
            return error_response
        reply_data, error_response = _validated_data(
            VocReplyCreateInputSerializer(data=payload)
        )
        if error_response:
            return error_response

        post = get_post_detail(post_id=post_id)
        if post is None:
            return _json_error("Post not found", status=404)

        reply, refreshed_post = add_reply(
            post=post,
            author=request.user,
            content=str((reply_data or {})["content"]),
        )
        serialized_reply = _serialize_reply(reply)
        set_activity_summary(request, "Add VOC reply")
        set_activity_new_state(request, serialized_reply)
        merge_activity_metadata(request, resource="voc_reply", entryId=reply.pk, postId=post_id)
        return JsonResponse(
            {"reply": serialized_reply, "post": _serialize_post(refreshed_post)},
            status=201,
        )


__all__ = ["VocPostsView", "VocPostDetailView", "VocReplyView"]
