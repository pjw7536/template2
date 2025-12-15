from __future__ import annotations

from typing import Any, Dict, Tuple

from django.db import transaction
from django.db.models import F
from django.db.models.functions import Greatest

from .selectors import get_app_by_id, get_comment_by_id
from .models import AppStoreApp, AppStoreComment, AppStoreCommentLike, AppStoreLike


def _normalize_screenshot_input(value: str) -> tuple[str, str, str]:
    """스크린샷 입력을 (url, base64, mime_type)로 정규화합니다."""

    raw = (value or "").strip()
    if not raw:
        return "", "", ""

    if not raw.startswith("data:"):
        return raw, "", ""

    if "," not in raw:
        return raw, "", ""

    meta, data = raw.split(",", 1)
    meta = meta[5:]  # remove leading "data:"
    parts = [part.strip() for part in meta.split(";")]
    if not any(part.lower() == "base64" for part in parts):
        return raw, "", ""

    mime_type = parts[0] if parts else ""
    return "", data, mime_type


def create_app(
    *,
    owner,
    name: str,
    category: str,
    description: str,
    url: str,
    badge: str,
    tags: list[str],
    screenshot_url: str,
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
        screenshot_url: Screenshot external URL or data URL (base64).
        contact_name: Contact person name.
        contact_knoxid: Contact knoxid.

    Returns:
        Created AppStoreApp (reloaded with comment_count).

    Side effects:
        Inserts a new AppStoreApp row.
    """

    normalized_url, screenshot_base64, screenshot_mime_type = _normalize_screenshot_input(screenshot_url)
    app = AppStoreApp.objects.create(
        name=name,
        category=category,
        description=description,
        url=url,
        screenshot_url=normalized_url,
        screenshot_base64=screenshot_base64,
        screenshot_mime_type=screenshot_mime_type,
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

    screenshot_input: str | None = None
    if "screenshot_url" in updates:
        screenshot_input = str(updates.pop("screenshot_url") or "")

    for field, value in updates.items():
        setattr(app, field, value)

    if screenshot_input is not None:
        normalized_url, screenshot_base64, screenshot_mime_type = _normalize_screenshot_input(screenshot_input)
        app.screenshot_url = normalized_url
        app.screenshot_base64 = screenshot_base64
        app.screenshot_mime_type = screenshot_mime_type

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


def create_comment(
    *,
    app: AppStoreApp,
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
