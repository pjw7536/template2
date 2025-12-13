from __future__ import annotations

import logging
from typing import Any, Dict, Tuple

from django.db import transaction
from django.db.models import F
from django.db.models.functions import Greatest

from .selectors import get_app_by_id, get_comment_by_id
from .models import AppStoreApp, AppStoreComment, AppStoreLike

logger = logging.getLogger(__name__)


def create_app(
    *,
    owner,
    name: str,
    category: str,
    description: str,
    url: str,
    badge: str,
    tags: list[str],
    contact_name: str,
    contact_knoxid: str,
) -> AppStoreApp:
    """AppStore 앱을 생성합니다.

    Create an AppStore app.

    Args:
        owner: App owner (Django user).
        name: App name.
        category: App category.
        description: App description.
        url: App URL.
        badge: Optional badge label.
        tags: Tag list.
        contact_name: Contact person name.
        contact_knoxid: Contact knoxid.

    Returns:
        Created AppStoreApp (reloaded with comment_count).

    Side effects:
        Inserts a new AppStoreApp row.
    """

    app = AppStoreApp.objects.create(
        name=name,
        category=category,
        description=description,
        url=url,
        badge=badge,
        tags=tags,
        contact_name=contact_name,
        contact_knoxid=contact_knoxid,
        owner=owner,
    )
    return get_app_by_id(app_id=app.pk) or app


def update_app(*, app: AppStoreApp, updates: Dict[str, Any]) -> AppStoreApp:
    """AppStore 앱 정보를 업데이트합니다.

    Update an AppStore app.

    Args:
        app: Target app instance (must exist).
        updates: Dict of model-field updates.

    Returns:
        Updated AppStoreApp (reloaded with comment_count).

    Side effects:
        Updates AppStoreApp row.
    """

    for field, value in updates.items():
        setattr(app, field, value)
    app.save()
    return get_app_by_id(app_id=app.pk) or app


def delete_app(*, app: AppStoreApp) -> None:
    """AppStore 앱을 삭제합니다.

    Delete an AppStore app.

    Side effects:
        Deletes the AppStoreApp row.
    """

    app.delete()


@transaction.atomic
def toggle_like(*, app: AppStoreApp, user) -> Tuple[bool, int]:
    """앱 좋아요를 토글하고 like_count를 갱신합니다.

    Toggle like for an app and update cached like_count.

    Returns:
        (liked, like_count)

    Side effects:
        Inserts/deletes AppStoreLike and updates AppStoreApp.like_count.
    """

    like, created = AppStoreLike.objects.select_for_update().get_or_create(app=app, user=user)
    if created:
        AppStoreApp.objects.filter(pk=app.pk).update(like_count=F("like_count") + 1)
        liked = True
    else:
        like.delete()
        AppStoreApp.objects.filter(pk=app.pk).update(like_count=Greatest(F("like_count") - 1, 0))
        liked = False

    app.refresh_from_db(fields=["like_count"])
    return liked, int(app.like_count or 0)


def increment_view_count(*, app: AppStoreApp) -> int:
    """조회수를 증가시키고 최신 값을 반환합니다.

    Increment view_count and return the new value.

    Side effects:
        Updates AppStoreApp.view_count.
    """

    AppStoreApp.objects.filter(pk=app.pk).update(view_count=F("view_count") + 1)
    app.refresh_from_db(fields=["view_count"])
    return int(app.view_count or 0)


def create_comment(*, app: AppStoreApp, user, content: str) -> AppStoreComment:
    """앱에 댓글을 생성합니다.

    Create a comment for an app.

    Side effects:
        Inserts an AppStoreComment row.
    """

    comment = AppStoreComment.objects.create(app=app, user=user, content=content)
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
