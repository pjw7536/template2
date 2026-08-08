# =============================================================================
# 모듈 설명: AppStore 앱 생성/수정/삭제 및 노출 순서 서비스 로직을 제공합니다.
# - 주요 함수: create_app, reorder_apps, update_app, delete_app
# - 불변 조건: 스크린샷 입력은 URL/data URL이며 노출 순서는 전체 앱 ID 집합을 기준으로 변경합니다.
# =============================================================================
from __future__ import annotations

import hashlib
from typing import Any, Dict, Sequence

from django.db import connection, transaction

from ..models import AppStoreApp
from ..selectors import (
    get_app_by_id,
    get_apps_for_display_order_update,
    get_next_app_display_order,
)
from .screenshots import (
    normalize_screenshot_gallery,
    normalize_screenshot_input,
    split_cover_and_gallery,
)


# Appstore 순서에 영향을 주는 transaction만 직렬화하는 PostgreSQL advisory lock 키입니다.
APP_ORDER_LOCK_ID = 0x41505053544F5245


class AppOrderConflictError(Exception):
    """클라이언트와 서버의 앱 목록 또는 순서가 다를 때 발생합니다."""


def _acquire_app_order_lock() -> None:
    """현재 transaction이 끝날 때까지 Appstore 순서 변경 잠금을 획득합니다.

    반환:
        없음.

    부작용:
        PostgreSQL transaction advisory lock을 획득합니다.

    오류:
        transaction 밖에서 호출하거나 DB 잠금 획득에 실패하면 예외가 발생할 수 있습니다.
    """

    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [APP_ORDER_LOCK_ID])


def build_app_order_version(app_ids: Sequence[int]) -> str:
    """사용자에게 보이는 앱 ID 순서의 불투명 버전을 생성합니다.

    인자:
        app_ids: 현재 노출 순서대로 나열한 앱 PK 목록.

    반환:
        동시 편집 충돌 확인에 사용할 SHA-256 문자열.

    부작용:
        없음.

    오류:
        없음.
    """

    raw_order = ",".join(str(app_id) for app_id in app_ids)
    return hashlib.sha256(raw_order.encode("utf-8")).hexdigest()


def create_app(
    *,
    owner: Any,
    name: str,
    category: str,
    description: str,
    url: str,
    manual_url: str | None = None,
    screenshot_urls: list[str] | None = None,
    screenshot_url: str,
    contact_name: str,
    contact_knoxid: str,
) -> AppStoreApp:
    """AppStore 앱을 생성합니다.

    인자:
        owner: 앱 소유자(Django user).
        name: 앱 이름.
        category: 앱 카테고리.
        description: 앱 설명.
        url: 앱 URL.
        manual_url: 메뉴얼 URL(없으면 None).
        screenshot_urls: 스크린샷 목록(대표가 첫 번째). URL 또는 data URL.
        screenshot_url: 스크린샷 URL 또는 data URL.
        contact_name: 담당자 이름.
        contact_knoxid: 담당자 knox id.

    반환:
        생성된 AppStoreApp 인스턴스(댓글 수 포함 재조회 시도).

    부작용:
        AppStoreApp 레코드를 생성합니다.

    오류:
        ORM 저장 과정에서 예외가 발생할 수 있습니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 스크린샷 입력 분리/정규화
    # -----------------------------------------------------------------------------
    cover_input, gallery_inputs = split_cover_and_gallery(screenshot_urls or [])
    if not cover_input:
        cover_input = (screenshot_url or "").strip()

    normalized_url, screenshot_base64, screenshot_mime_type = normalize_screenshot_input(cover_input)
    screenshot_gallery = normalize_screenshot_gallery(gallery_inputs)

    # -----------------------------------------------------------------------------
    # 2) 앱 레코드 생성
    # -----------------------------------------------------------------------------
    with transaction.atomic():
        _acquire_app_order_lock()
        app = AppStoreApp.objects.create(
            name=name,
            category=category,
            description=description,
            url=url,
            screenshot_url=normalized_url,
            screenshot_base64=screenshot_base64,
            screenshot_mime_type=screenshot_mime_type,
            screenshot_gallery=screenshot_gallery,
            contact_name=contact_name,
            contact_knoxid=contact_knoxid,
            owner=owner,
            manual_url=manual_url,
            display_order=get_next_app_display_order(),
        )

    # -----------------------------------------------------------------------------
    # 3) 댓글 수 포함 재조회(없으면 생성된 객체 반환)
    # -----------------------------------------------------------------------------
    return get_app_by_id(app_id=app.pk) or app


def reorder_apps(
    *,
    app_ids: Sequence[int],
    expected_order_version: str,
) -> tuple[list[int], str]:
    """전체 Appstore 앱의 노출 순서를 원자적으로 교체합니다.

    인자:
        app_ids: 저장할 전체 앱 PK 목록.
        expected_order_version: 편집 시작 시점의 노출 순서 버전.

    반환:
        저장된 앱 PK 목록과 새 노출 순서 버전.

    부작용:
        모든 AppStoreApp 레코드의 display_order를 연속된 값으로 갱신합니다.

    오류:
        앱 집합이나 순서 버전이 현재 상태와 다르면 AppOrderConflictError를 발생시킵니다.
    """

    requested_ids = [int(app_id) for app_id in app_ids]

    with transaction.atomic():
        _acquire_app_order_lock()
        # -----------------------------------------------------------------------------
        # 1) 모든 현재 앱을 동일한 PK 순서로 잠가 동시 순서 저장을 직렬화
        # -----------------------------------------------------------------------------
        locked_apps = list(get_apps_for_display_order_update())
        apps_by_id = {app.pk: app for app in locked_apps}
        current_ids = [
            app.pk
            for app in sorted(
                locked_apps,
                key=lambda item: (item.display_order, item.pk),
            )
        ]

        # -----------------------------------------------------------------------------
        # 2) 편집 이후 앱 추가/삭제 또는 다른 관리자의 선행 저장 감지
        # -----------------------------------------------------------------------------
        current_version = build_app_order_version(current_ids)
        if current_version != expected_order_version:
            raise AppOrderConflictError("App order changed")
        if len(requested_ids) != len(current_ids) or set(requested_ids) != set(current_ids):
            raise AppOrderConflictError("App list changed")

        # -----------------------------------------------------------------------------
        # 3) 요청 순서대로 연속 순번을 부여하고 한 번에 저장
        # -----------------------------------------------------------------------------
        ordered_apps = [apps_by_id[app_id] for app_id in requested_ids]
        for display_order, app in enumerate(ordered_apps, start=1):
            app.display_order = display_order
        if ordered_apps:
            AppStoreApp.objects.bulk_update(ordered_apps, ["display_order"])

    return requested_ids, build_app_order_version(requested_ids)


def update_app(*, app: AppStoreApp, updates: Dict[str, Any]) -> AppStoreApp:
    """AppStore 앱 정보를 업데이트합니다.

    인자:
        app: 대상 AppStoreApp 인스턴스.
        updates: 업데이트할 필드 dict.

    반환:
        업데이트된 AppStoreApp 인스턴스(댓글 수 포함 재조회 시도).

    부작용:
        AppStoreApp 레코드를 업데이트합니다.

    오류:
        ORM 저장 과정에서 예외가 발생할 수 있습니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 스크린샷 입력 분리
    # -----------------------------------------------------------------------------
    screenshot_input: str | None = None
    screenshot_urls_input: list[str] | None = None
    if "screenshot_url" in updates:
        screenshot_input = str(updates.pop("screenshot_url") or "")
    if "screenshot_urls" in updates:
        raw = updates.pop("screenshot_urls")
        screenshot_urls_input = raw if isinstance(raw, list) else []

    # -----------------------------------------------------------------------------
    # 2) 일반 필드 반영
    # -----------------------------------------------------------------------------
    fields_to_update = set(updates)
    for field, value in updates.items():
        setattr(app, field, value)

    # -----------------------------------------------------------------------------
    # 3) 스크린샷 필드 반영
    # -----------------------------------------------------------------------------
    if screenshot_urls_input is not None:
        cover_input, gallery_inputs = split_cover_and_gallery(screenshot_urls_input)
        normalized_url, screenshot_base64, screenshot_mime_type = normalize_screenshot_input(cover_input)
        app.screenshot_url = normalized_url
        app.screenshot_base64 = screenshot_base64
        app.screenshot_mime_type = screenshot_mime_type
        app.screenshot_gallery = normalize_screenshot_gallery(gallery_inputs)
        fields_to_update.update(
            {
                "screenshot_url",
                "screenshot_base64",
                "screenshot_mime_type",
                "screenshot_gallery",
            }
        )
    elif screenshot_input is not None:
        normalized_url, screenshot_base64, screenshot_mime_type = normalize_screenshot_input(screenshot_input)
        app.screenshot_url = normalized_url
        app.screenshot_base64 = screenshot_base64
        app.screenshot_mime_type = screenshot_mime_type
        fields_to_update.update(
            {
                "screenshot_url",
                "screenshot_base64",
                "screenshot_mime_type",
            }
        )
        if not (normalized_url or screenshot_base64):
            app.screenshot_gallery = []
            fields_to_update.add("screenshot_gallery")

    # -----------------------------------------------------------------------------
    # 4) 저장 및 재조회
    # -----------------------------------------------------------------------------
    fields_to_update.add("updated_at")
    app.save(update_fields=sorted(fields_to_update))
    return get_app_by_id(app_id=app.pk) or app


def delete_app(*, app: AppStoreApp) -> None:
    """AppStore 앱을 삭제합니다.

    인자:
        app: 대상 AppStoreApp 인스턴스.

    반환:
        없음.

    부작용:
        AppStoreApp 레코드를 삭제합니다.

    오류:
        ORM 삭제 과정에서 예외가 발생할 수 있습니다.
    """

    with transaction.atomic():
        _acquire_app_order_lock()
        app.delete()
