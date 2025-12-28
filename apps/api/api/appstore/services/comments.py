from __future__ import annotations

from typing import Tuple

from django.db import transaction
from django.db.models import F
from django.db.models.functions import Greatest

from ..selectors import get_comment_by_id
from ..models import AppStoreComment, AppStoreCommentLike


def create_comment(
    *,
    app,
    user,
    content: str,
    parent_comment: AppStoreComment | None = None,
) -> AppStoreComment:
    """앱에 댓글을 생성합니다.

    Create a comment for an app.

    Args:
        app: Target app instance.
        user: Django user instance.
        content: Comment body.
        parent_comment: Optional parent comment for replies.

    Side effects:
        Inserts an AppStoreComment row.
    """

    if parent_comment and parent_comment.app_id != app.pk:
        raise ValueError("Parent comment must belong to the same app.")

    comment = AppStoreComment.objects.create(app=app, user=user, content=content, parent=parent_comment)
    return get_comment_by_id(app_id=app.pk, comment_id=comment.pk) or comment


def update_comment(*, comment: AppStoreComment, content: str) -> AppStoreComment:
    """댓글 내용을 수정합니다.

    Update a comment content.

    Side effects:
        Updates AppStoreComment.content.
    """

    comment.content = content
    comment.save(update_fields=["content", "updated_at"])
    return get_comment_by_id(app_id=comment.app_id, comment_id=comment.pk) or comment


def delete_comment(*, comment: AppStoreComment) -> None:
    """댓글을 삭제합니다.

    Delete a comment.

    Side effects:
        Deletes AppStoreComment row.
    """

    comment.delete()


@transaction.atomic
def toggle_comment_like(*, comment: AppStoreComment, user) -> Tuple[bool, int]:
    """댓글 좋아요를 토글하고 like_count를 갱신합니다.

    Toggle like for a comment and update cached like_count.

    Returns:
        (liked, like_count)

    Side effects:
        Inserts/deletes AppStoreCommentLike and updates AppStoreComment.like_count.
    """

    like, created = AppStoreCommentLike.objects.select_for_update().get_or_create(comment=comment, user=user)
    if created:
        AppStoreComment.objects.filter(pk=comment.pk).update(like_count=F("like_count") + 1)
        liked = True
    else:
        like.delete()
        AppStoreComment.objects.filter(pk=comment.pk).update(like_count=Greatest(F("like_count") - 1, 0))
        liked = False

    comment.refresh_from_db(fields=["like_count"])
    return liked, int(comment.like_count or 0)
