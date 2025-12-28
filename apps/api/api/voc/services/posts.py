from __future__ import annotations

from typing import Any, Dict, Tuple

from ..selectors import get_post_detail, get_reply_by_id, is_admin_user
from ..models import VocPost, VocReply


def create_post(*, author, title: str, content: str, status: str) -> VocPost:
    """VOC 게시글을 생성하고 관계(prefetch)까지 포함해 반환합니다.

    Create a VOC post and return it with relations loaded.

    Side effects:
        Inserts a VocPost row.
    """

    post = VocPost.objects.create(
        title=title,
        content=content,
        status=status,
        author=author,
    )
    return get_post_detail(post_id=post.pk) or post


def update_post(*, post: VocPost, updates: Dict[str, Any]) -> VocPost:
    """VOC 게시글을 수정하고 관계(prefetch)까지 포함해 반환합니다.

    Update a VOC post and return it with relations loaded.

    Side effects:
        Updates VocPost row.
    """

    for field, value in updates.items():
        setattr(post, field, value)
    post.save(update_fields=list(updates.keys()) + ["updated_at"])
    return get_post_detail(post_id=post.pk) or post


def delete_post(*, post: VocPost) -> None:
    """VOC 게시글을 삭제합니다.

    Delete a VOC post.

    Side effects:
        Deletes VocPost row.
    """

    post.delete()


def add_reply(*, post: VocPost, author, content: str) -> Tuple[VocReply, VocPost]:
    """게시글에 답변을 추가하고 (reply, refreshed_post)를 반환합니다.

    Add a reply to a post and return (reply, refreshed_post).

    Side effects:
        Inserts a VocReply row.
    """

    reply = VocReply.objects.create(post=post, author=author, content=content)
    loaded_reply = get_reply_by_id(reply_id=reply.pk) or reply
    refreshed_post = get_post_detail(post_id=post.pk) or post
    return loaded_reply, refreshed_post


def can_manage_post(*, user: Any, post: VocPost) -> bool:
    """게시글 수정/삭제 가능 여부(관리자 또는 작성자)를 판별합니다.

    Side effects:
        None. Pure calculation.
    """

    return is_admin_user(user=user) or (user and getattr(user, "pk", None) == post.author_id)
