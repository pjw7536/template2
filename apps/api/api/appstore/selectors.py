from __future__ import annotations

from django.db.models import Count, QuerySet

from .models import AppStoreApp, AppStoreComment, AppStoreLike


def get_app_list() -> QuerySet[AppStoreApp]:
    """AppStore 앱 목록 조회용 QuerySet을 반환합니다.

    Return the app list for the AppStore API.

    Returns:
        QuerySet ordered by newest first, annotated with comment_count.

    Side effects:
        None. Read-only query.
    """

    return (
        AppStoreApp.objects.select_related("owner")
        .annotate(comment_count=Count("comments"))
        .order_by("-created_at", "-id")
    )


def get_app_by_id(*, app_id: int) -> AppStoreApp | None:
    """앱 단건(소유자/댓글수 포함)을 조회합니다.

    Return an app with owner and comment_count.

    Args:
        app_id: App primary key.

    Returns:
        AppStoreApp when found, otherwise None.

    Side effects:
        None. Read-only query.
    """

    try:
        return (
            AppStoreApp.objects.select_related("owner")
            .annotate(comment_count=Count("comments"))
            .get(pk=app_id)
        )
    except AppStoreApp.DoesNotExist:
        return None


def get_app_detail(*, app_id: int) -> AppStoreApp | None:
    """상세 화면용으로 댓글까지 prefetch한 앱을 조회합니다.

    Return an app with comments prefetched for detail view.

    Args:
        app_id: App primary key.

    Returns:
        AppStoreApp when found, otherwise None.

    Side effects:
        None. Read-only query.
    """

    try:
        return (
            AppStoreApp.objects.select_related("owner")
            .prefetch_related("comments__user")
            .annotate(comment_count=Count("comments"))
            .get(pk=app_id)
        )
    except AppStoreApp.DoesNotExist:
        return None


def get_liked_app_ids_for_user(*, user) -> list[int]:
    """사용자가 좋아요한 앱 id 목록을 반환합니다.

    Return liked app ids for user.

    Args:
        user: Django user instance.

    Returns:
        List of app ids liked by the user.

    Side effects:
        None. Read-only query.
    """

    return list(AppStoreLike.objects.filter(user=user).values_list("app_id", flat=True))


def get_comments_for_app(*, app_id: int) -> QuerySet[AppStoreComment]:
    """앱의 댓글 목록을 오래된 순으로 조회합니다.

    Return comments for app ordered by oldest first.

    Args:
        app_id: App primary key.

    Returns:
        QuerySet of comments with user selected.

    Side effects:
        None. Read-only query.
    """

    return (
        AppStoreComment.objects.filter(app_id=app_id)
        .select_related("user")
        .order_by("created_at", "id")
    )


def get_comment_by_id(*, app_id: int, comment_id: int) -> AppStoreComment | None:
    """앱의 댓글 단건을 조회합니다.

    Return a single comment for an app.

    Args:
        app_id: Parent app id.
        comment_id: Comment id.

    Returns:
        AppStoreComment when found, otherwise None.

    Side effects:
        None. Read-only query.
    """

    try:
        return AppStoreComment.objects.select_related("user", "app").get(pk=comment_id, app_id=app_id)
    except AppStoreComment.DoesNotExist:
        return None
