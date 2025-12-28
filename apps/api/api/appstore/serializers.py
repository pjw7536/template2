from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

MAX_TAGS = 20
MAX_TAG_LENGTH = 64


def _user_display_name(user) -> str:
    """사용자 표시 이름(이름/username/email)을 계산합니다."""

    if not user:
        return ""
    full_name = f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}".strip()
    if full_name:
        return full_name
    username = getattr(user, "username", "") or ""
    if username:
        return username
    return getattr(user, "email", "").split("@")[0]


def _user_knoxid(user) -> str:
    """사용자의 knox id(이메일 로컬파트 등)를 추출합니다."""

    if not user:
        return ""
    email = getattr(user, "email", "")
    if isinstance(email, str) and "@" in email:
        return email.split("@", 1)[0]
    return getattr(user, "username", "") or ""


def serialize_user(user) -> Optional[Dict[str, Any]]:
    """사용자 정보를 API 응답 형태로 직렬화합니다."""

    if not user:
        return None
    return {
        "id": user.pk,
        "name": _user_display_name(user) or "사용자",
        "knoxid": _user_knoxid(user),
    }


def default_contact(user) -> Tuple[str, str]:
    """연락처 기본값(contact_name, contact_knoxid)을 계산합니다."""

    return (_user_display_name(user) or "사용자").strip(), _user_knoxid(user)


def sanitize_tags(tags: Any) -> List[str]:
    """태그 목록을 길이/개수 제한에 맞게 정규화합니다."""

    if not isinstance(tags, Iterable) or isinstance(tags, (str, bytes)):
        return []
    cleaned: List[str] = []
    seen = set()
    for raw in tags:
        if not isinstance(raw, str):
            continue
        tag = raw.strip()
        if not tag:
            continue
        normalized = tag[:MAX_TAG_LENGTH]
        if normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(normalized)
        if len(cleaned) >= MAX_TAGS:
            break
    return cleaned


def sanitize_screenshot_urls(value: Any) -> List[str]:
    """스크린샷 URL 목록을 정규화합니다."""

    if not isinstance(value, list):
        return []

    cleaned: List[str] = []
    for raw in value:
        if not isinstance(raw, str):
            continue
        url = raw.strip()
        if not url:
            continue
        cleaned.append(url)
    return cleaned


def apply_cover_index(screenshot_urls: List[str], cover_index: Any) -> List[str]:
    """cover_index를 반영해 대표 이미지를 0번으로 이동합니다."""

    if not screenshot_urls:
        return []

    try:
        index = int(cover_index)
    except (TypeError, ValueError):
        return screenshot_urls

    if index < 0 or index >= len(screenshot_urls):
        return screenshot_urls

    if index == 0:
        return screenshot_urls

    cover = screenshot_urls[index]
    remaining = [item for i, item in enumerate(screenshot_urls) if i != index]
    return [cover, *remaining]


def can_manage_app(user, app: Any) -> bool:
    """현재 사용자가 앱을 수정/삭제할 수 있는지 검사합니다."""

    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    return getattr(user, "pk", None) is not None and app.owner_id == user.pk


def can_manage_comment(user, comment: Any) -> bool:
    """현재 사용자가 댓글을 수정/삭제할 수 있는지 검사합니다."""

    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    return getattr(user, "pk", None) is not None and comment.user_id == user.pk


def serialize_comment(comment: Any, current_user, liked_comment_ids: set[int]) -> Dict[str, Any]:
    """댓글을 API 응답 형태로 직렬화합니다."""

    author = getattr(comment, "user", None)
    liked = False
    if current_user and getattr(current_user, "is_authenticated", False):
        liked = comment.pk in liked_comment_ids
    return {
        "id": comment.pk,
        "appId": comment.app_id,
        "parentCommentId": getattr(comment, "parent_id", None),
        "content": comment.content,
        "createdAt": comment.created_at.isoformat(),
        "updatedAt": comment.updated_at.isoformat(),
        "author": serialize_user(author),
        "likeCount": int(getattr(comment, "like_count", 0) or 0),
        "liked": liked,
        "canEdit": can_manage_comment(current_user, comment),
        "canDelete": can_manage_comment(current_user, comment),
    }


def serialize_app(
    app: Any,
    current_user,
    liked_app_ids: Sequence[int],
    *,
    include_comments: bool = False,
    include_screenshots: bool = False,
    liked_comment_ids: set[int] | None = None,
) -> Dict[str, Any]:
    """앱을 API 응답 형태로 직렬화합니다(선호 시 댓글 포함)."""

    liked = False
    if current_user and getattr(current_user, "is_authenticated", False):
        liked = app.id in liked_app_ids

    liked_comment_ids = liked_comment_ids or set()

    comments: Optional[List[Dict[str, Any]]] = None
    if include_comments:
        related = getattr(app, "comments", None)
        if related is not None:
            comments = [serialize_comment(comment, current_user, liked_comment_ids) for comment in related.all()]
        else:
            comments = []

    owner_payload = serialize_user(getattr(app, "owner", None))
    comment_count = getattr(app, "comment_count", 0) or 0

    payload: Dict[str, Any] = {
        "id": app.pk,
        "name": app.name,
        "category": app.category,
        "description": app.description,
        "url": app.url,
        "screenshotUrl": getattr(app, "screenshot_src", ""),
        "tags": app.tags if isinstance(app.tags, list) else [],
        "badge": app.badge,
        "contactName": app.contact_name,
        "contactKnoxid": app.contact_knoxid,
        "viewCount": app.view_count,
        "likeCount": app.like_count,
        "commentCount": int(comment_count),
        "createdAt": app.created_at.isoformat(),
        "updatedAt": app.updated_at.isoformat(),
        "owner": owner_payload,
        "liked": liked,
        "canEdit": can_manage_app(current_user, app),
        "canDelete": can_manage_app(current_user, app),
        **({"comments": comments} if comments is not None else {}),
    }

    if include_screenshots:
        screenshot_srcs = []
        screenshot_srcs_raw = getattr(app, "screenshot_srcs", None)
        if callable(screenshot_srcs_raw):
            screenshot_srcs = screenshot_srcs_raw()
        if not isinstance(screenshot_srcs, list):
            screenshot_srcs = []
        payload["screenshotUrls"] = screenshot_srcs
        payload["coverScreenshotIndex"] = 0

    return payload


__all__ = [
    "apply_cover_index",
    "can_manage_app",
    "can_manage_comment",
    "default_contact",
    "sanitize_screenshot_urls",
    "sanitize_tags",
    "serialize_app",
    "serialize_comment",
    "serialize_user",
]
