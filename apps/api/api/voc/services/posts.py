# =============================================================================
# 모듈 설명: VOC 게시글과 답변의 쓰기 동작을 제공합니다.
# - 주요 함수: create_post, update_post, delete_post, add_reply, can_manage_post
# - 불변 조건: 입력 schema 검증과 읽기 query는 각각 serializer와 selector가 담당합니다.
# =============================================================================

from __future__ import annotations

from typing import Any

from api.account import services as account_services

from ..models import VocPost, VocReply
from ..selectors import get_post_detail


def create_post(*, author: Any, title: str, content: str, status: str, app: str) -> VocPost:
    """검증된 값으로 VOC 게시글을 생성합니다.

    부작용:
    - `VocPost` 레코드 한 건을 생성합니다.
    """

    return VocPost.objects.create(
        title=title,
        content=content,
        status=status,
        app=app,
        author=author,
    )


def update_post(*, post: VocPost, updates: dict[str, Any]) -> VocPost:
    """검증된 변경 필드로 VOC 게시글을 갱신합니다.

    부작용:
    - 대상 `VocPost` 레코드를 한 번 저장합니다.
    """

    for field, value in updates.items():
        setattr(post, field, value)
    post.save(update_fields=[*updates.keys(), "updated_at"])
    return post


def delete_post(*, post: VocPost) -> None:
    """VOC 게시글과 연결된 답변을 삭제합니다.

    부작용:
    - 대상 `VocPost`와 cascade 관계인 `VocReply`를 삭제합니다.
    """

    post.delete()


def add_reply(*, post: VocPost, author: Any, content: str) -> tuple[VocReply, VocPost]:
    """VOC 답변을 생성하고 갱신된 게시글을 반환합니다.

    부작용:
    - `VocReply` 레코드 한 건을 생성합니다.

    예외:
    - 답변 생성 직후 게시글을 다시 찾을 수 없으면 `VocPost.DoesNotExist`를 발생시킵니다.
    """

    reply = VocReply.objects.create(post=post, author=author, content=content)
    refreshed_post = get_post_detail(post_id=post.pk)
    if refreshed_post is None:
        raise VocPost.DoesNotExist(post.pk)
    return reply, refreshed_post


def can_manage_post(*, user: Any, post: VocPost, request: Any | None = None) -> bool:
    """사용자가 VOC 게시글을 수정하거나 삭제할 수 있는지 반환합니다."""

    return bool(
        account_services.has_scope_role(
            user=user,
            scope_key="voc",
            request=request,
        )
        or (user and getattr(user, "pk", None) == post.author_id)
    )
