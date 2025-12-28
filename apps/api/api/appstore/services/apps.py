from __future__ import annotations

from typing import Any, Dict

from ..selectors import get_app_by_id
from ..models import AppStoreApp
from .screenshots import (
    _normalize_screenshot_gallery,
    _normalize_screenshot_input,
    _split_cover_and_gallery,
)


def create_app(
    *,
    owner,
    name: str,
    category: str,
    description: str,
    url: str,
    badge: str,
    tags: list[str],
    screenshot_urls: list[str] | None = None,
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
        screenshot_urls: Screenshot list (cover first). Each item may be an external URL or data URL (base64).
        screenshot_url: Screenshot external URL or data URL (base64).
        contact_name: Contact person name.
        contact_knoxid: Contact knoxid.

    Returns:
        Created AppStoreApp (reloaded with comment_count).

    Side effects:
        Inserts a new AppStoreApp row.
    """

    cover_input, gallery_inputs = _split_cover_and_gallery(screenshot_urls or [])
    if not cover_input:
        cover_input = (screenshot_url or "").strip()

    normalized_url, screenshot_base64, screenshot_mime_type = _normalize_screenshot_input(cover_input)
    screenshot_gallery = _normalize_screenshot_gallery(gallery_inputs)
    app = AppStoreApp.objects.create(
        name=name,
        category=category,
        description=description,
        url=url,
        screenshot_url=normalized_url,
        screenshot_base64=screenshot_base64,
        screenshot_mime_type=screenshot_mime_type,
        screenshot_gallery=screenshot_gallery,
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
    screenshot_urls_input: list[str] | None = None
    if "screenshot_url" in updates:
        screenshot_input = str(updates.pop("screenshot_url") or "")
    if "screenshot_urls" in updates:
        raw = updates.pop("screenshot_urls")
        screenshot_urls_input = raw if isinstance(raw, list) else []

    for field, value in updates.items():
        setattr(app, field, value)

    if screenshot_urls_input is not None:
        cover_input, gallery_inputs = _split_cover_and_gallery(screenshot_urls_input)
        normalized_url, screenshot_base64, screenshot_mime_type = _normalize_screenshot_input(cover_input)
        app.screenshot_url = normalized_url
        app.screenshot_base64 = screenshot_base64
        app.screenshot_mime_type = screenshot_mime_type
        app.screenshot_gallery = _normalize_screenshot_gallery(gallery_inputs)
    elif screenshot_input is not None:
        normalized_url, screenshot_base64, screenshot_mime_type = _normalize_screenshot_input(screenshot_input)
        app.screenshot_url = normalized_url
        app.screenshot_base64 = screenshot_base64
        app.screenshot_mime_type = screenshot_mime_type
        if not (normalized_url or screenshot_base64):
            app.screenshot_gallery = []

    app.save()
    return get_app_by_id(app_id=app.pk) or app


def delete_app(*, app: AppStoreApp) -> None:
    """AppStore 앱을 삭제합니다.

    Delete an AppStore app.

    Side effects:
        Deletes the AppStoreApp row.
    """

    app.delete()
