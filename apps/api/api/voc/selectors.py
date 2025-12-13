from __future__ import annotations

from django.db.models import Count, QuerySet

from .models import VocPost, VocReply


def get_valid_post_statuses() -> set[str]:
    """VocPost.status로 사용할 수 있는 값 집합을 반환합니다.

    Return the set of valid VocPost.status values.

    Side effects:
        None. Read-only.
    """

    return {choice[0] for choice in VocPost.Status.choices}


def get_default_post_status() -> str:
    """신규 VOC 게시글의 기본 상태 값을 반환합니다.

    Return the default status for new VOC posts.
    """

    return VocPost.Status.RECEIVED


def get_post_list(*, status: str | None = None) -> QuerySet[VocPost]:
    """VOC 게시글 목록을 조회합니다(선택적으로 status 필터 적용).

    Return the VOC post list, optionally filtered by status.

    Args:
        status: Optional status filter.

    Returns:
        QuerySet of VocPost with author + replies prefetched.

    Side effects:
        None. Read-only query.
    """

    queryset = (
        VocPost.objects.select_related("author")
        .prefetch_related("replies__author")
        .order_by("-created_at", "-id")
    )
    if status:
        queryset = queryset.filter(status=status)
    return queryset


def get_post_detail(*, post_id: int) -> VocPost | None:
    """답변까지 prefetch한 VOC 게시글 단건을 조회합니다.

    Return a single VOC post with replies prefetched.

    Args:
        post_id: VocPost primary key.

    Returns:
        VocPost when found, otherwise None.

    Side effects:
        None. Read-only query.
    """

    try:
        return (
            VocPost.objects.select_related("author")
            .prefetch_related("replies__author")
            .get(pk=post_id)
        )
    except VocPost.DoesNotExist:
        return None


def get_reply_by_id(*, reply_id: int) -> VocReply | None:
    """author/post를 select_related한 답변 단건을 조회합니다.

    Return a single reply with author and post selected.

    Args:
        reply_id: VocReply primary key.

    Returns:
        VocReply when found, otherwise None.

    Side effects:
        None. Read-only query.
    """

    try:
        return VocReply.objects.select_related("author", "post").get(pk=reply_id)
    except VocReply.DoesNotExist:
        return None


def get_status_counts() -> dict[str, int]:
    """VOC 게시글 상태(status)별 개수를 반환합니다.

    Return counts per status for VOC posts.

    Side effects:
        None. Read-only query.
    """

    status_set = get_valid_post_statuses()
    base = {status: 0 for status in status_set}
    for row in VocPost.objects.values("status").annotate(total=Count("id")):
        status = row.get("status")
        if status in base:
            base[status] = int(row.get("total") or 0)
    return base


def is_admin_user(*, user) -> bool:
    """사용자가 VOC 게시글을 관리할 권한이 있는지 반환합니다.

    Return whether user can administer VOC posts.

    Side effects:
        May read user.profile (read-only).
    """

    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
        return True
    profile = getattr(user, "profile", None)
    role = getattr(profile, "role", None) if profile else None
    return role == "admin"
