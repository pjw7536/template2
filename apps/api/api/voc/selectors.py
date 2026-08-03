# =============================================================================
# 모듈 설명: VOC 게시글 읽기 전용 query를 제공합니다.
# - 주요 함수: get_post_list, get_post_detail
# - 불변 조건: 모든 ORM query는 읽기 전용입니다.
# =============================================================================

from __future__ import annotations

from django.db.models import QuerySet

from .models import VocPost


def get_post_list() -> QuerySet[VocPost]:
    """작성자와 답변을 함께 읽은 VOC 게시글 목록을 반환합니다.

    반환값:
    - 최신 글부터 정렬된 `QuerySet[VocPost]`

    부작용:
    - 없음
    """

    return (
        VocPost.objects.select_related("author")
        .prefetch_related("replies__author")
        .order_by("-created_at", "-id")
    )


def get_post_detail(*, post_id: int) -> VocPost | None:
    """작성자와 답변을 함께 읽은 VOC 게시글 한 건을 반환합니다.

    입력값:
    - post_id: 조회할 게시글 기본 키

    반환값:
    - 게시글이 있으면 `VocPost`, 없으면 `None`

    부작용:
    - 없음
    """

    try:
        return (
            VocPost.objects.select_related("author")
            .prefetch_related("replies__author")
            .get(pk=post_id)
        )
    except VocPost.DoesNotExist:
        return None
