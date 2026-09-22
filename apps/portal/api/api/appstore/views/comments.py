# =============================================================================
# 모듈 설명: AppStore 댓글 CRUD와 댓글 좋아요 API를 제공합니다.
# =============================================================================
from __future__ import annotations

import logging

from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from api.common.services import extract_first_error_message, parse_json_body

from ..selectors import (
    get_comment_by_id,
    get_comments_for_app,
    get_liked_comment_ids_for_user,
)
from ..serializers import (
    AppStoreCommentCreateSerializer,
    AppStoreCommentUpdateSerializer,
    serialize_comment,
)
from ..services import (
    create_comment,
    delete_comment,
    toggle_comment_like,
    update_comment,
)
from ..services.permissions import can_manage_comment
from ._shared import load_app, resolve_appstore_admin

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class AppStoreCommentsView(APIView):
    """댓글 목록 조회/작성."""

    def get(self, request: HttpRequest, app_id: int, *args: object, **kwargs: object) -> JsonResponse:
        """댓글 목록을 조회합니다.

        입력:
          - 요청: Django HttpRequest
          - app_id: 앱 PK
          - args/kwargs: URL 라우팅 인자

        요청 예시:
          - 예시 요청: GET /api/v1/appstore/apps/123/comments

        반환:
          - comments: 댓글 목록
          - total: 총 개수

        부작용:
          없음. 읽기 전용 조회입니다.

        오류:
          - 404: 앱 없음

        snake/camel 호환:
          - 해당 없음(요청 바디 없음)
        """
        # -----------------------------------------------------------------------------
        # 1) 앱 조회
        # -----------------------------------------------------------------------------
        app = load_app(app_id)
        if not app:
            return JsonResponse({"error": "App not found"}, status=404)

        # -----------------------------------------------------------------------------
        # 2) 댓글/좋아요 목록 조회
        # -----------------------------------------------------------------------------
        comments = get_comments_for_app(app_id=app.pk)
        liked_comment_ids: set[int] = set()
        is_appstore_admin = resolve_appstore_admin(request)
        if request.user.is_authenticated:
            liked_comment_ids = set(get_liked_comment_ids_for_user(user=request.user, app_id=app.pk))
        payload = [
            serialize_comment(
                comment,
                request.user,
                liked_comment_ids,
                is_appstore_admin=is_appstore_admin,
            )
            for comment in comments
        ]
        # -----------------------------------------------------------------------------
        # 3) 응답 반환
        # -----------------------------------------------------------------------------
        return JsonResponse({"comments": payload, "total": len(payload)})

    def post(self, request: HttpRequest, app_id: int, *args: object, **kwargs: object) -> JsonResponse:
        """댓글을 작성합니다.

        입력:
          - 요청: Django HttpRequest
          - app_id: 앱 PK
          - args/kwargs: URL 라우팅 인자

        요청 예시:
          - 예시 요청: POST /api/v1/appstore/apps/123/comments
            예시 바디: {"content": "댓글입니다", "parentCommentId": 10}

        snake/camel 호환:
          - parentCommentId / parent_comment_id (키 매핑)

        반환:
          - comment: 생성된 댓글 payload

        부작용:
          AppStoreComment 레코드를 생성합니다.

        오류:
          - 401: 인증 실패
          - 404: 앱/부모 댓글 없음
          - 400: 입력 오류/JSON 파싱 실패
          - 500: 내부 오류
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        # -----------------------------------------------------------------------------
        # 2) 앱 조회
        # -----------------------------------------------------------------------------
        app = load_app(app_id)
        if not app:
            return JsonResponse({"error": "App not found"}, status=404)

        # -----------------------------------------------------------------------------
        # 3) JSON 파싱 및 입력 검증
        # -----------------------------------------------------------------------------
        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        serializer = AppStoreCommentCreateSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse(
                {
                    "error": extract_first_error_message(serializer.errors),
                    "details": serializer.errors,
                },
                status=400,
            )
        validated = serializer.validated_data

        # -----------------------------------------------------------------------------
        # 4) 부모 댓글 확인(대댓글)
        # -----------------------------------------------------------------------------
        parent_comment: Any | None = None
        parent_id = validated.get("parent_comment_id")
        if parent_id is not None:
            parent_comment = get_comment_by_id(app_id=app.pk, comment_id=parent_id)
            if not parent_comment:
                return JsonResponse({"error": "Parent comment not found"}, status=404)

        # -----------------------------------------------------------------------------
        # 5) 댓글 생성
        # -----------------------------------------------------------------------------
        try:
            comment = create_comment(
                app=app,
                user=request.user,
                content=validated["content"],
                parent_comment=parent_comment,
            )
            is_appstore_admin = resolve_appstore_admin(request)
            return JsonResponse(
                {
                    "comment": serialize_comment(
                        comment,
                        request.user,
                        set(),
                        is_appstore_admin=is_appstore_admin,
                    )
                },
                status=201,
            )
        except Exception:  # 방어적 로깅(커버리지 제외): pragma: no cover
            logger.exception("Failed to create appstore comment")
            return JsonResponse({"error": "Failed to create comment"}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class AppStoreCommentDetailView(APIView):
    """댓글 수정/삭제."""

    def patch(
        self, request: HttpRequest, app_id: int, comment_id: int, *args: object, **kwargs: object
    ) -> JsonResponse:
        """댓글 내용을 수정합니다.

        입력:
          - 요청: Django HttpRequest
          - app_id: 앱 PK
          - comment_id: 댓글 PK
          - args/kwargs: URL 라우팅 인자

        요청 예시:
          - 예시 요청: PATCH /api/v1/appstore/apps/123/comments/456
            예시 바디: {"content": "수정 내용"}

        반환:
          - comment: 수정된 댓글 payload

        부작용:
          AppStoreComment 레코드를 업데이트합니다.

        오류:
          - 401: 인증 실패
          - 403: 권한 없음
          - 404: 앱/댓글 없음
          - 400: 입력 오류/JSON 파싱 실패
          - 500: 내부 오류

        snake/camel 호환:
          - 해당 없음(요청 바디 키는 content만 사용)
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        # -----------------------------------------------------------------------------
        # 2) 앱/댓글 조회 및 권한 확인
        # -----------------------------------------------------------------------------
        app = load_app(app_id)
        if not app:
            return JsonResponse({"error": "App not found"}, status=404)

        comment = get_comment_by_id(app_id=app.pk, comment_id=comment_id)
        if not comment:
            return JsonResponse({"error": "Comment not found"}, status=404)

        is_appstore_admin = resolve_appstore_admin(request)
        if not can_manage_comment(
            request.user,
            comment,
            is_appstore_admin=is_appstore_admin,
        ):
            return JsonResponse({"error": "Forbidden"}, status=403)

        # -----------------------------------------------------------------------------
        # 3) JSON 파싱 및 입력 검증
        # -----------------------------------------------------------------------------
        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        serializer = AppStoreCommentUpdateSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse(
                {
                    "error": extract_first_error_message(serializer.errors),
                    "details": serializer.errors,
                },
                status=400,
            )
        validated = serializer.validated_data

        # -----------------------------------------------------------------------------
        # 4) 댓글 업데이트
        # -----------------------------------------------------------------------------
        try:
            comment = update_comment(comment=comment, content=validated["content"])
            liked_comment_ids: set[int] = set()
            if request.user.is_authenticated:
                liked_comment_ids = set(get_liked_comment_ids_for_user(user=request.user, app_id=app.pk))
            return JsonResponse(
                {
                    "comment": serialize_comment(
                        comment,
                        request.user,
                        liked_comment_ids,
                        is_appstore_admin=is_appstore_admin,
                    )
                }
            )
        except Exception:  # 방어적 로깅(커버리지 제외): pragma: no cover
            logger.exception("Failed to update appstore comment %s", comment_id)
            return JsonResponse({"error": "Failed to update comment"}, status=500)

    def delete(
        self, request: HttpRequest, app_id: int, comment_id: int, *args: object, **kwargs: object
    ) -> JsonResponse:
        """댓글을 삭제합니다.

        입력:
          - 요청: Django HttpRequest
          - app_id: 앱 PK
          - comment_id: 댓글 PK
          - args/kwargs: URL 라우팅 인자

        요청 예시:
          - 예시 요청: DELETE /api/v1/appstore/apps/123/comments/456

        반환:
          - 예시 응답: success: true

        부작용:
          AppStoreComment 레코드를 삭제합니다.

        오류:
          - 401: 인증 실패
          - 403: 권한 없음
          - 404: 앱/댓글 없음
          - 500: 내부 오류

        snake/camel 호환:
          - 해당 없음(요청 바디 없음)
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        # -----------------------------------------------------------------------------
        # 2) 앱/댓글 조회 및 권한 확인
        # -----------------------------------------------------------------------------
        app = load_app(app_id)
        if not app:
            return JsonResponse({"error": "App not found"}, status=404)

        comment = get_comment_by_id(app_id=app.pk, comment_id=comment_id)
        if not comment:
            return JsonResponse({"error": "Comment not found"}, status=404)

        if not can_manage_comment(
            request.user,
            comment,
            is_appstore_admin=resolve_appstore_admin(request),
        ):
            return JsonResponse({"error": "Forbidden"}, status=403)

        # -----------------------------------------------------------------------------
        # 3) 삭제 수행
        # -----------------------------------------------------------------------------
        try:
            delete_comment(comment=comment)
            return JsonResponse({"success": True})
        except Exception:  # 방어적 로깅(커버리지 제외): pragma: no cover
            logger.exception("Failed to delete appstore comment %s", comment_id)
            return JsonResponse({"error": "Failed to delete comment"}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class AppStoreCommentLikeToggleView(APIView):
    """댓글 좋아요 토글."""

    def post(
        self, request: HttpRequest, app_id: int, comment_id: int, *args: object, **kwargs: object
    ) -> JsonResponse:
        """댓글 좋아요를 토글합니다.

        입력:
          - 요청: Django HttpRequest
          - app_id: 앱 PK
          - comment_id: 댓글 PK
          - args/kwargs: URL 라우팅 인자

        요청 예시:
          - 예시 요청: POST /api/v1/appstore/apps/123/comments/456/like

        반환:
          - liked: 좋아요 여부
          - likeCount: 최신 좋아요 수
          - appId / commentId (식별자 키)

        부작용:
          AppStoreCommentLike 생성/삭제 및 like_count 갱신이 발생합니다.

        오류:
          - 401: 인증 실패
          - 404: 앱/댓글 없음
          - 500: 내부 오류

        snake/camel 호환:
          - 해당 없음(요청 바디 없음)
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        # -----------------------------------------------------------------------------
        # 2) 앱/댓글 조회
        # -----------------------------------------------------------------------------
        app = load_app(app_id)
        if not app:
            return JsonResponse({"error": "App not found"}, status=404)

        comment = get_comment_by_id(app_id=app.pk, comment_id=comment_id)
        if not comment:
            return JsonResponse({"error": "Comment not found"}, status=404)

        # -----------------------------------------------------------------------------
        # 3) 좋아요 토글
        # -----------------------------------------------------------------------------
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
        except Exception:  # 방어적 로깅(커버리지 제외): pragma: no cover
            logger.exception("Failed to toggle comment like for app %s comment %s", app_id, comment_id)
            return JsonResponse({"error": "Failed to toggle comment like"}, status=500)
