# =============================================================================
# 모듈 설명: AppStore 서비스/엔드포인트 테스트를 제공합니다.
# - 주요 대상: 스크린샷 처리, 댓글/좋아요, 생성/조회/수정/삭제 흐름
# - 불변 조건: URL 네임(appstore-*)이 등록되어 있어야 합니다.
# =============================================================================
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from threading import Barrier
from urllib.parse import parse_qs, urlparse
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import close_old_connections
from django.test import SimpleTestCase, TestCase, TransactionTestCase
from django.urls import reverse

from api.account import services as account_services
from api.appstore.selectors import (
    get_app_list,
    get_appstore_assistant_catalog,
    get_seeded_apps,
)
from api.appstore.serializers import default_contact
from api.appstore.services import (
    AppOrderConflictError,
    build_app_order_version,
    create_app,
    create_comment,
    reorder_apps,
    seed_appstore_dummy_data,
    update_app,
)


def _allow_test_scope_access(test_case: TestCase) -> None:
    """도메인 endpoint 테스트에서 공통 portal/app 권한 경계를 격리합니다."""

    patcher = patch(
        "api.account.services.get_access_payload",
        return_value={"allowed": True},
    )
    patcher.start()
    test_case.addCleanup(patcher.stop)


class AppstoreScreenshotTests(TestCase):
    """appstore 스크린샷 저장/응답 동작을 검증합니다."""

    def setUp(self) -> None:
        """보호된 AppStore endpoint를 호출할 인증 사용자를 준비합니다."""

        _allow_test_scope_access(self)
        User = get_user_model()
        self.viewer = User.objects.create_user(
            sabun="S00000",
            password="test-password",
            knox_id="knox-00000",
        )
        self.client.force_login(self.viewer)

    def test_create_app_stores_data_url_as_base64(self) -> None:
        """data URL이 base64 필드로 저장되는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자/입력 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S12345",
            password="test-password",
            knox_id="knox-12345",
        )
        screenshot_url = "data:image/png;base64,AAA="

        # -----------------------------------------------------------------------------
        # 2) 앱 생성
        # -----------------------------------------------------------------------------
        app = create_app(
            owner=user,
            name="Test App",
            category="Tools",
            description="",
            url="https://example.com",
            screenshot_url=screenshot_url,
            contact_name="홍길동",
            contact_knoxid="hong",
        )

        # -----------------------------------------------------------------------------
        # 3) 저장 결과 검증
        # -----------------------------------------------------------------------------
        app.refresh_from_db()
        self.assertEqual(app.screenshot_url, "")
        self.assertEqual(app.screenshot_base64, "AAA=")
        self.assertEqual(app.screenshot_mime_type, "image/png")
        self.assertEqual(app.screenshot_gallery, [])

    def test_create_app_keeps_external_screenshot_url(self) -> None:
        """외부 URL이 screenshot_url로 유지되는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자/입력 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S88888",
            password="test-password",
            knox_id="knox-88888",
        )
        screenshot_url = "https://example.com/screenshot.png"

        # -----------------------------------------------------------------------------
        # 2) 앱 생성
        # -----------------------------------------------------------------------------
        app = create_app(
            owner=user,
            name="Test App",
            category="Tools",
            description="",
            url="https://example.com",
            screenshot_url=screenshot_url,
            contact_name="홍길동",
            contact_knoxid="hong",
        )

        # -----------------------------------------------------------------------------
        # 3) 저장 결과 검증
        # -----------------------------------------------------------------------------
        app.refresh_from_db()
        self.assertEqual(app.screenshot_url, screenshot_url)
        self.assertEqual(app.screenshot_base64, "")
        self.assertEqual(app.screenshot_mime_type, "")
        self.assertEqual(app.screenshot_gallery, [])

    def test_create_app_stores_gallery_items(self) -> None:
        """갤러리 스크린샷이 올바르게 저장되는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자/입력 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S77777",
            password="test-password",
            knox_id="knox-77777",
        )

        cover = "data:image/png;base64,COVER="
        extra_url = "https://example.com/extra.png"
        extra_data = "data:image/png;base64,EXTRA="

        # -----------------------------------------------------------------------------
        # 2) 앱 생성
        # -----------------------------------------------------------------------------
        app = create_app(
            owner=user,
            name="Test App",
            category="Tools",
            description="",
            url="https://example.com",
            screenshot_urls=[cover, extra_url, extra_data],
            screenshot_url="",
            contact_name="홍길동",
            contact_knoxid="hong",
        )

        # -----------------------------------------------------------------------------
        # 3) 저장 결과 검증
        # -----------------------------------------------------------------------------
        app.refresh_from_db()
        self.assertEqual(app.screenshot_url, "")
        self.assertEqual(app.screenshot_base64, "COVER=")
        self.assertEqual(app.screenshot_mime_type, "image/png")
        self.assertEqual(
            app.screenshot_gallery,
            [
                {"url": extra_url, "base64": "", "mime_type": ""},
                {"url": "", "base64": "EXTRA=", "mime_type": "image/png"},
            ],
        )

    def test_update_app_allows_clearing_screenshot(self) -> None:
        """스크린샷 초기화(빈 값)가 허용되는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자/기존 앱 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S99999",
            password="test-password",
            knox_id="knox-99999",
        )
        app = create_app(
            owner=user,
            name="Test App",
            category="Tools",
            description="",
            url="https://example.com",
            screenshot_url="data:image/png;base64,BBB=",
            contact_name="홍길동",
            contact_knoxid="hong",
        )

        # -----------------------------------------------------------------------------
        # 2) 스크린샷 초기화 업데이트
        # -----------------------------------------------------------------------------
        updated = update_app(app=app, updates={"screenshot_url": ""})

        # -----------------------------------------------------------------------------
        # 3) 저장 결과 검증
        # -----------------------------------------------------------------------------
        updated.refresh_from_db()
        self.assertEqual(updated.screenshot_url, "")
        self.assertEqual(updated.screenshot_base64, "")
        self.assertEqual(updated.screenshot_mime_type, "")
        self.assertEqual(updated.screenshot_gallery, [])

    def test_update_app_preserves_cover_fields_when_database_save_fails(self) -> None:
        """커버 필드 저장 실패 시 기존 DB 값을 보존해야 합니다."""

        User = get_user_model()
        user = User.objects.create_user(
            sabun="S99998",
            password="test-password",
            knox_id="knox-99998",
        )
        app = create_app(
            owner=user,
            name="Rollback App",
            category="Tools",
            description="",
            url="https://example.com",
            screenshot_url="https://example.com/old.png",
            contact_name="홍길동",
            contact_knoxid="hong",
        )

        with patch.object(app, "save", side_effect=RuntimeError("save failed")):
            with self.assertRaises(RuntimeError):
                update_app(
                    app=app,
                    updates={
                        "screenshot_urls": [
                            "data:image/png;base64,QUJD",
                            "https://example.com/gallery.png",
                        ]
                    },
                )

        app.refresh_from_db()
        self.assertEqual(app.screenshot_url, "https://example.com/old.png")
        self.assertEqual(app.screenshot_base64, "")
        self.assertEqual(app.screenshot_gallery, [])

    def test_detail_payload_includes_screenshot_url(self) -> None:
        """상세 응답에 screenshotUrl/Urls와 manualUrl이 포함되는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자/앱 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S54321",
            password="test-password",
            knox_id="knox-54321",
        )
        screenshot_url = "data:image/png;base64,CCC="
        manual_url = "https://example.com/manual"
        app = create_app(
            owner=user,
            name="Test App",
            category="Tools",
            description="",
            url="https://example.com",
            manual_url=manual_url,
            screenshot_url=screenshot_url,
            contact_name="홍길동",
            contact_knoxid="hong",
        )

        # -----------------------------------------------------------------------------
        # 2) 상세 조회 요청
        # -----------------------------------------------------------------------------
        response = self.client.get(reverse("appstore-app-detail", kwargs={"app_id": app.pk}))
        self.assertEqual(response.status_code, 200)

        # -----------------------------------------------------------------------------
        # 3) 응답 페이로드 검증
        # -----------------------------------------------------------------------------
        payload = response.json()
        self.assertEqual(payload["app"]["screenshotUrl"], screenshot_url)
        self.assertEqual(payload["app"]["screenshotUrls"], [screenshot_url])
        self.assertEqual(payload["app"]["coverScreenshotIndex"], 0)
        self.assertEqual(payload["app"]["manualUrl"], manual_url)

    def test_list_payload_uses_cover_endpoint_for_base64(self) -> None:
        """목록 응답은 base64 커버를 엔드포인트 URL로 제공합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자/앱 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S22222",
            password="test-password",
            knox_id="knox-22222",
        )
        screenshot_url = "data:image/png;base64,QUJD"
        app = create_app(
            owner=user,
            name="Test App",
            category="Tools",
            description="",
            url="https://example.com",
            screenshot_url=screenshot_url,
            contact_name="홍길동",
            contact_knoxid="hong",
        )

        # -----------------------------------------------------------------------------
        # 2) 목록 조회
        # -----------------------------------------------------------------------------
        response = self.client.get(reverse("appstore-apps"))
        self.assertEqual(response.status_code, 200)

        # -----------------------------------------------------------------------------
        # 3) 응답 페이로드 검증
        # -----------------------------------------------------------------------------
        payload = response.json()
        results = payload.get("results", [])
        self.assertEqual(len(results), 1)
        cover_path = reverse("appstore-app-cover", kwargs={"app_id": app.pk})
        cover_url = results[0].get("screenshotUrl", "")
        self.assertTrue(isinstance(cover_url, str))
        parsed_cover_url = urlparse(cover_url)
        self.assertEqual(parsed_cover_url.path, cover_path)
        self.assertTrue(parse_qs(parsed_cover_url.query).get("v"))
        self.assertNotIn("data:image", cover_url)

    def test_cover_endpoint_returns_decoded_image(self) -> None:
        """커버 엔드포인트가 base64 스크린샷을 바이너리로 반환합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자/앱 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S33333",
            password="test-password",
            knox_id="knox-33333",
        )
        screenshot_url = "data:image/png;base64,QUJD"
        app = create_app(
            owner=user,
            name="Test App",
            category="Tools",
            description="",
            url="https://example.com",
            screenshot_url=screenshot_url,
            contact_name="홍길동",
            contact_knoxid="hong",
        )

        # -----------------------------------------------------------------------------
        # 2) 커버 조회
        # -----------------------------------------------------------------------------
        response = self.client.get(reverse("appstore-app-cover", kwargs={"app_id": app.pk}))

        # -----------------------------------------------------------------------------
        # 3) 응답 검증
        # -----------------------------------------------------------------------------
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertIn("max-age", response["Cache-Control"])
        self.assertTrue(response["ETag"])
        self.assertEqual(response.content, b"ABC")

        # -----------------------------------------------------------------------------
        # 4) 캐시 검증 요청
        # -----------------------------------------------------------------------------
        cached_response = self.client.get(
            reverse("appstore-app-cover", kwargs={"app_id": app.pk}),
            HTTP_IF_NONE_MATCH=response["ETag"],
        )
        self.assertEqual(cached_response.status_code, 304)
        self.assertEqual(cached_response["ETag"], response["ETag"])


class AppstoreContactDefaultTests(TestCase):
    """appstore 연락처 기본값 계산을 검증합니다."""

    def test_default_contact_uses_full_name_when_username_missing(self) -> None:
        """username이 없을 때 이름(first/last)을 사용해야 합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S11111",
            password="test-password",
            knox_id="knox-11111",
        )
        user.first_name = "John"
        user.last_name = "Doe"
        user.save(update_fields=["first_name", "last_name"])

        # -----------------------------------------------------------------------------
        # 2) 기본값 계산
        # -----------------------------------------------------------------------------
        contact_name, contact_knoxid = default_contact(user)

        # -----------------------------------------------------------------------------
        # 3) 결과 검증
        # -----------------------------------------------------------------------------
        self.assertEqual(contact_name, "John Doe")
        self.assertEqual(contact_knoxid, "knox-11111")

    def test_default_contact_uses_email_when_name_missing(self) -> None:
        """username/이름이 없으면 email을 사용해야 합니다."""
        # -----------------------------------------------------------------------------
        # 1) 사용자 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S11112",
            password="test-password",
            knox_id="knox-11112",
        )
        user.email = "user@example.com"
        user.save(update_fields=["email"])

        # -----------------------------------------------------------------------------
        # 2) 기본값 계산
        # -----------------------------------------------------------------------------
        contact_name, contact_knoxid = default_contact(user)

        # -----------------------------------------------------------------------------
        # 3) 결과 검증
        # -----------------------------------------------------------------------------
        self.assertEqual(contact_name, "user@example.com")
        self.assertEqual(contact_knoxid, "knox-11112")


class AppstoreCommentReplyLikeTests(TestCase):
    """appstore 댓글 대댓글/좋아요 동작을 검증합니다."""

    def setUp(self) -> None:
        """댓글/좋아요 테스트용 사용자와 앱을 준비합니다."""
        _allow_test_scope_access(self)
        User = get_user_model()
        self.user = User.objects.create_user(
            sabun="S22222",
            password="test-password",
            knox_id="knox-22222",
        )
        self.client.force_login(self.user)
        self.app = create_app(
            owner=self.user,
            name="Test App",
            category="Tools",
            description="",
            url="https://example.com",
            screenshot_url="",
            contact_name="홍길동",
            contact_knoxid="hong",
        )

    def test_create_reply_comment_sets_parent_comment_id(self) -> None:
        """대댓글 생성 시 parentCommentId가 설정되는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 부모 댓글 생성
        # -----------------------------------------------------------------------------
        parent = create_comment(app=self.app, user=self.user, content="부모 댓글")
        url = reverse("appstore-app-comments", kwargs={"app_id": self.app.pk})

        # -----------------------------------------------------------------------------
        # 2) 대댓글 생성 요청
        # -----------------------------------------------------------------------------
        response = self.client.post(
            url,
            data='{"content":"대댓글","parentCommentId":%d}' % parent.pk,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)

        # -----------------------------------------------------------------------------
        # 3) 응답 페이로드 검증
        # -----------------------------------------------------------------------------
        payload = response.json()
        self.assertEqual(payload["comment"]["parentCommentId"], parent.pk)

        # -----------------------------------------------------------------------------
        # 4) 상세 조회에서 댓글 포함 여부 확인
        # -----------------------------------------------------------------------------
        detail_response = self.client.get(reverse("appstore-app-detail", kwargs={"app_id": self.app.pk}))
        self.assertEqual(detail_response.status_code, 200)
        detail_payload = detail_response.json()
        comment_ids = {comment["id"] for comment in detail_payload["app"]["comments"]}
        self.assertIn(parent.pk, comment_ids)
        self.assertIn(payload["comment"]["id"], comment_ids)

    def test_toggle_comment_like_updates_like_count_and_liked(self) -> None:
        """댓글 좋아요 토글이 상태/카운트를 갱신하는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 댓글 생성 및 좋아요 URL 준비
        # -----------------------------------------------------------------------------
        comment = create_comment(app=self.app, user=self.user, content="좋아요 테스트")
        like_url = reverse(
            "appstore-app-comment-like",
            kwargs={"app_id": self.app.pk, "comment_id": comment.pk},
        )

        # -----------------------------------------------------------------------------
        # 2) 첫 번째 토글 결과 검증
        # -----------------------------------------------------------------------------
        first = self.client.post(like_url)
        self.assertEqual(first.status_code, 200)
        first_payload = first.json()
        self.assertTrue(first_payload["liked"])
        self.assertEqual(first_payload["likeCount"], 1)

        # -----------------------------------------------------------------------------
        # 3) 상세 조회에서 반영 여부 확인
        # -----------------------------------------------------------------------------
        detail_response = self.client.get(reverse("appstore-app-detail", kwargs={"app_id": self.app.pk}))
        self.assertEqual(detail_response.status_code, 200)
        detail_payload = detail_response.json()
        liked_comment = next(
            item for item in detail_payload["app"]["comments"] if item["id"] == comment.pk
        )
        self.assertTrue(liked_comment["liked"])
        self.assertEqual(liked_comment["likeCount"], 1)

        # -----------------------------------------------------------------------------
        # 4) 두 번째 토글 결과 검증
        # -----------------------------------------------------------------------------
        second = self.client.post(like_url)
        self.assertEqual(second.status_code, 200)
        second_payload = second.json()
        self.assertFalse(second_payload["liked"])
        self.assertEqual(second_payload["likeCount"], 0)


class AppstoreDisplayOrderTests(TestCase):
    """Appstore 앱 노출 순서 서비스 규칙을 검증합니다."""

    def setUp(self) -> None:
        """순서 테스트용 사용자와 앱 세 개를 준비합니다."""

        User = get_user_model()
        self.user = User.objects.create_user(
            sabun="S30000",
            password="test-password",
            knox_id="knox-30000",
        )
        self.apps = [
            create_app(
                owner=self.user,
                name=f"Order App {index}",
                category="Tools",
                description="",
                url=f"https://example.com/order-{index}",
                screenshot_url="",
                contact_name="홍길동",
                contact_knoxid="hong",
            )
            for index in range(3)
        ]

    def test_create_app_appends_to_display_order(self) -> None:
        """신규 앱이 기존 앱의 마지막 순서에 추가되는지 검증합니다."""

        self.assertEqual(
            [app.display_order for app in self.apps],
            [1, 2, 3],
        )
        self.assertEqual(
            list(get_app_list().values_list("id", flat=True)),
            [app.pk for app in self.apps],
        )

    def test_assistant_catalog_applies_filter_and_excludes_contact_data(self) -> None:
        """Assistant 카탈로그는 화면 필터를 적용하고 연락처·이미지를 노출하지 않습니다."""

        self.apps[0].name = "분석 도구"
        self.apps[0].description = "라인 데이터를 분석합니다."
        self.apps[0].contact_knoxid = "private-knox"
        self.apps[0].save(update_fields=["name", "description", "contact_knoxid", "updated_at"])

        payload = get_appstore_assistant_catalog(query="분석", category="Tools")

        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["apps"][0]["name"], "분석 도구")
        self.assertNotIn("contactKnoxid", payload["apps"][0])
        self.assertNotIn("screenshot", payload["apps"][0])

    def test_reorder_apps_replaces_full_order(self) -> None:
        """전체 앱 ID 순서가 연속된 노출 순서로 저장되는지 검증합니다."""

        current_ids = [app.pk for app in self.apps]
        requested_ids = list(reversed(current_ids))

        saved_ids, order_version = reorder_apps(
            app_ids=requested_ids,
            expected_order_version=build_app_order_version(current_ids),
        )

        self.assertEqual(saved_ids, requested_ids)
        self.assertEqual(order_version, build_app_order_version(requested_ids))
        self.assertEqual(
            list(get_app_list().values_list("id", flat=True)),
            requested_ids,
        )
        self.assertEqual(
            list(get_app_list().values_list("display_order", flat=True)),
            [1, 2, 3],
        )

    def test_reorder_apps_rejects_stale_version(self) -> None:
        """다른 관리자가 먼저 저장한 순서를 이전 버전으로 덮어쓰지 못해야 합니다."""

        current_ids = [app.pk for app in self.apps]
        stale_version = build_app_order_version(current_ids)
        reorder_apps(
            app_ids=list(reversed(current_ids)),
            expected_order_version=stale_version,
        )

        with self.assertRaises(AppOrderConflictError):
            reorder_apps(
                app_ids=current_ids,
                expected_order_version=stale_version,
            )

    def test_reorder_apps_rejects_changed_app_set(self) -> None:
        """일부 앱이 누락된 전체 순서 요청을 거부해야 합니다."""

        current_ids = [app.pk for app in self.apps]
        with self.assertRaises(AppOrderConflictError):
            reorder_apps(
                app_ids=current_ids[:-1],
                expected_order_version=build_app_order_version(current_ids),
            )

    def test_update_app_does_not_restore_stale_display_order(self) -> None:
        """일반 앱 수정이 먼저 저장된 노출 순서를 덮어쓰지 않아야 합니다."""

        current_ids = [app.pk for app in self.apps]
        stale_app = self.apps[0]
        requested_ids = list(reversed(current_ids))
        reorder_apps(
            app_ids=requested_ids,
            expected_order_version=build_app_order_version(current_ids),
        )

        update_app(app=stale_app, updates={"name": "Updated App"})

        self.assertEqual(
            list(get_app_list().values_list("id", flat=True)),
            requested_ids,
        )


class AppstoreDisplayOrderConcurrencyTests(TransactionTestCase):
    """Appstore 앱 생성 순번의 transaction 동시성을 검증합니다."""

    def setUp(self) -> None:
        """동시 생성 요청이 공유할 사용자 레코드를 준비합니다."""

        User = get_user_model()
        self.user = User.objects.create_user(
            sabun="S30001",
            password="test-password",
            knox_id="knox-30001",
        )

    def test_concurrent_create_app_assigns_distinct_display_orders(self) -> None:
        """동시에 생성된 앱 두 개에도 서로 다른 연속 순번을 배정해야 합니다."""

        start_barrier = Barrier(2)

        def create_ordered_app(index: int) -> int:
            """독립 DB connection에서 시작 시점을 맞춰 테스트 앱을 생성합니다."""

            close_old_connections()
            try:
                user = get_user_model().objects.get(pk=self.user.pk)
                start_barrier.wait()
                app = create_app(
                    owner=user,
                    name=f"Concurrent App {index}",
                    category="Tools",
                    description="",
                    url=f"https://example.com/concurrent-{index}",
                    screenshot_url="",
                    contact_name="홍길동",
                    contact_knoxid="hong",
                )
                return app.display_order
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            display_orders = list(executor.map(create_ordered_app, range(2)))

        self.assertEqual(sorted(display_orders), [1, 2])


class AppstoreDummyDataTests(TestCase):
    """Appstore 개발용 seed 데이터의 재실행 안전성을 검증합니다."""

    def setUp(self) -> None:
        """seed 소유자와 삭제되면 안 되는 일반 앱을 준비합니다."""

        User = get_user_model()
        self.owner = User.objects.create_user(
            sabun="S30002",
            password="test-password",
            username="Dummy Owner",
            knox_id="dummy-owner",
        )
        self.regular_app = create_app(
            owner=self.owner,
            name="Regular App",
            category="Tools",
            description="",
            url="https://example.com/regular",
            screenshot_url="",
            contact_name="홍길동",
            contact_knoxid="hong",
        )

    def test_seed_is_repeatable_and_reset_deletes_only_matching_prefix(self) -> None:
        """재실행은 기존 seed를 갱신하고 reset은 같은 marker만 재생성해야 합니다."""

        first = seed_appstore_dummy_data(prefix="dev", owner=self.owner, reset=True)
        second = seed_appstore_dummy_data(prefix="DEV", owner=self.owner)
        reset_result = seed_appstore_dummy_data(prefix="DEV", owner=self.owner, reset=True)

        self.assertEqual(first, {"deleted": 0, "created": 8, "updated": 0, "total": 8})
        self.assertEqual(second, {"deleted": 0, "created": 0, "updated": 8, "total": 8})
        self.assertEqual(reset_result, {"deleted": 8, "created": 8, "updated": 0, "total": 8})
        self.assertEqual(get_seeded_apps(name_prefix="[DEV] ").count(), 8)
        self.assertEqual(
            list(get_seeded_apps(name_prefix="[DEV] ").values_list("display_order", flat=True)),
            list(range(2, 10)),
        )
        self.assertTrue(get_app_list().filter(pk=self.regular_app.pk).exists())


class AppstoreDummyDataCommandTests(SimpleTestCase):
    """Appstore seed management command의 dev 환경 가드를 검증합니다."""

    def test_command_rejects_non_development_environment(self) -> None:
        """development 환경이 아니면 Appstore seed 실행을 거부합니다."""

        with patch.dict("os.environ", {"ENVIRONMENT": "production"}, clear=True):
            with self.assertRaises(CommandError):
                call_command("seed_appstore_dummy_data", stdout=StringIO())

    @patch(
        "api.appstore.management.commands.seed_appstore_dummy_data.seed_appstore_dummy_data"
    )
    @patch(
        "api.appstore.management.commands.seed_appstore_dummy_data.ensure_dev_dummy_superuser"
    )
    def test_command_uses_dev_dummy_owner(
        self,
        ensure_dummy: Mock,
        seed_data: Mock,
    ) -> None:
        """development 환경에서는 dev dummy 사용자를 seed 소유자로 전달합니다."""

        owner = object()
        ensure_dummy.return_value = owner
        seed_data.return_value = {"deleted": 0, "created": 8, "updated": 0, "total": 8}

        with patch.dict("os.environ", {"ENVIRONMENT": "development"}, clear=True):
            call_command(
                "seed_appstore_dummy_data",
                reset=True,
                prefix="demo",
                stdout=StringIO(),
            )

        ensure_dummy.assert_called_once_with()
        seed_data.assert_called_once_with(prefix="DEMO", owner=owner, reset=True)


class AppstoreEndpointTests(TestCase):
    """AppStore 엔드포인트 기본 흐름 테스트."""

    def setUp(self) -> None:
        """엔드포인트 테스트용 사용자와 기본 앱을 생성합니다."""
        _allow_test_scope_access(self)
        User = get_user_model()
        self.user = User.objects.create_user(
            sabun="S33333",
            password="test-password",
            email="s33333@example.com",
            knox_id="knox-33333",
        )
        self.client.force_login(self.user)
        self.app = create_app(
            owner=self.user,
            name="Test App",
            category="Tools",
            description="",
            url="https://example.com",
            screenshot_url="",
            contact_name="홍길동",
            contact_knoxid="hong",
        )

    def test_appstore_apps_list_and_create(self) -> None:
        """앱 목록 조회 및 생성 API가 정상 동작하는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 목록 조회
        # -----------------------------------------------------------------------------
        list_response = self.client.get(reverse("appstore-apps"))
        self.assertEqual(list_response.status_code, 200)
        list_payload = list_response.json()
        self.assertTrue(list_payload["orderVersion"])
        self.assertFalse(list_payload["permissions"]["canReorder"])
        self.assertEqual(list_payload["results"][0]["displayOrder"], 1)

        # -----------------------------------------------------------------------------
        # 2) 앱 생성
        # -----------------------------------------------------------------------------
        create_response = self.client.post(
            reverse("appstore-apps"),
            data=(
                '{"name":"New App","category":"Tools","description":"desc","url":"https://new.app",'
                '"contactName":"User","contactKnoxid":"user1"}'
            ),
            content_type="application/json",
        )
        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.json()["app"]["displayOrder"], 2)

    def test_appstore_endpoints_reject_removed_snake_case_aliases(self) -> None:
        """AppStore JSON body는 제거된 snake_case 별칭을 거절해야 합니다."""

        create_response = self.client.post(
            reverse("appstore-apps"),
            data={
                "name": "Legacy",
                "category": "Tools",
                "url": "https://legacy.example",
                "manual_url": "https://legacy.example/manual",
            },
            content_type="application/json",
        )
        update_response = self.client.patch(
            reverse("appstore-app-detail", kwargs={"app_id": self.app.pk}),
            data={"screenshot_url": "https://legacy.example/cover.png"},
            content_type="application/json",
        )
        with patch(
            "api.appstore.views.order.resolve_appstore_admin",
            return_value=True,
        ):
            order_response = self.client.put(
                reverse("appstore-app-order"),
                data={
                    "app_ids": [self.app.pk],
                    "order_version": build_app_order_version([self.app.pk]),
                },
                content_type="application/json",
            )
        comment_response = self.client.post(
            reverse("appstore-app-comments", kwargs={"app_id": self.app.pk}),
            data={"content": "legacy", "parent_comment_id": 1},
            content_type="application/json",
        )

        for response, expected_fields in (
            (create_response, ["manual_url"]),
            (update_response, ["screenshot_url"]),
            (order_response, ["app_ids", "order_version"]),
            (comment_response, ["parent_comment_id"]),
        ):
            with self.subTest(expected_fields=expected_fields):
                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    response.json()["fieldErrors"]["unexpectedFields"],
                    expected_fields,
                )

    def test_appstore_list_resolves_admin_role_once_per_request(self) -> None:
        """앱 개수와 관계없이 AppStore admin 판정은 요청당 한 번만 수행해야 합니다."""

        for index in range(3):
            create_app(
                owner=self.user,
                name=f"Query Test App {index}",
                category="Tools",
                description="",
                url=f"https://example.com/query-{index}",
                screenshot_url="",
                contact_name="홍길동",
                contact_knoxid="hong",
            )

        with patch(
            "api.appstore.services.permissions.account_services.has_scope_role",
            return_value=False,
        ) as role_check:
            response = self.client.get(reverse("appstore-apps"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 4)
        role_check.assert_called_once()
        self.assertEqual(role_check.call_args.kwargs["user"], self.user)
        self.assertEqual(role_check.call_args.kwargs["scope_key"], "appstore")
        self.assertEqual(role_check.call_args.kwargs["required_role"], "admin")
        self.assertIsNotNone(role_check.call_args.kwargs["request"])

    def test_appstore_detail_reuses_admin_role_for_nested_comments(self) -> None:
        """상세 댓글 수와 관계없이 같은 AppStore admin 판정 결과를 재사용해야 합니다."""

        for index in range(3):
            create_comment(
                app=self.app,
                user=self.user,
                content=f"Query Test Comment {index}",
            )

        with patch(
            "api.appstore.services.permissions.account_services.has_scope_role",
            return_value=False,
        ) as role_check:
            response = self.client.get(
                reverse("appstore-app-detail", kwargs={"app_id": self.app.pk})
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["app"]
        self.assertEqual(len(payload["comments"]), 3)
        self.assertTrue(payload["canEdit"])
        self.assertTrue(all(comment["canEdit"] for comment in payload["comments"]))
        role_check.assert_called_once()
        self.assertEqual(role_check.call_args.kwargs["user"], self.user)
        self.assertEqual(role_check.call_args.kwargs["scope_key"], "appstore")
        self.assertIsNotNone(role_check.call_args.kwargs["request"])

    def test_appstore_admin_can_reorder_apps(self) -> None:
        """Appstore admin이 전체 앱 노출 순서를 저장할 수 있는지 검증합니다."""

        second_app = create_app(
            owner=self.user,
            name="Second App",
            category="Tools",
            description="",
            url="https://example.com/second",
            screenshot_url="",
            contact_name="홍길동",
            contact_knoxid="hong",
        )
        with patch(
            "api.appstore.services.permissions.account_services.has_scope_role",
            return_value=True,
        ) as role_check:
            list_response = self.client.get(reverse("appstore-apps"))
            list_payload = list_response.json()
            requested_ids = [second_app.pk, self.app.pk]
            response = self.client.put(
                reverse("appstore-app-order"),
                data={
                    "appIds": requested_ids,
                    "orderVersion": list_payload["orderVersion"],
                },
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["appIds"], requested_ids)
        self.assertEqual(role_check.call_count, 2)
        self.assertTrue(
            all(call.kwargs["required_role"] == "admin" for call in role_check.call_args_list)
        )
        self.assertEqual(
            list(get_app_list().values_list("id", flat=True)),
            requested_ids,
        )

    def test_appstore_non_admin_cannot_reorder_apps(self) -> None:
        """일반 사용자의 앱 노출 순서 변경을 거부하는지 검증합니다."""

        with patch(
            "api.appstore.services.permissions.account_services.has_scope_role",
            return_value=False,
        ) as role_check:
            response = self.client.put(
                reverse("appstore-app-order"),
                data={
                    "appIds": [self.app.pk],
                    "orderVersion": build_app_order_version([self.app.pk]),
                },
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 403)
        role_check.assert_called_once()
        self.assertEqual(role_check.call_args.kwargs["required_role"], "admin")

    def test_appstore_anonymous_user_cannot_reorder_apps(self) -> None:
        """비로그인 사용자의 앱 노출 순서 변경을 인증 단계에서 거부합니다."""

        self.client.logout()
        response = self.client.put(
            reverse("appstore-app-order"),
            data={
                "appIds": [self.app.pk],
                "orderVersion": build_app_order_version([self.app.pk]),
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)

    def test_appstore_order_endpoint_rejects_duplicate_ids(self) -> None:
        """순서 요청에 중복 앱 ID가 있으면 400을 반환하는지 검증합니다."""

        with patch("api.appstore.views.order.resolve_appstore_admin", return_value=True):
            response = self.client.put(
                reverse("appstore-app-order"),
                data={
                    "appIds": [self.app.pk, self.app.pk],
                    "orderVersion": build_app_order_version([self.app.pk]),
                },
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 400)

    def test_appstore_order_endpoint_returns_conflict_for_stale_version(self) -> None:
        """이전 순서 버전으로 저장하면 409를 반환하는지 검증합니다."""

        with patch("api.appstore.views.order.resolve_appstore_admin", return_value=True):
            response = self.client.put(
                reverse("appstore-app-order"),
                data={
                    "appIds": [self.app.pk],
                    "orderVersion": "stale-version",
                },
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 409)

    def test_appstore_create_returns_canonical_serializer_error(self) -> None:
        """앱 생성 검증 실패 시 canonical 오류 계약을 반환하는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 필수 name 누락 요청
        # -----------------------------------------------------------------------------
        response = self.client.post(
            reverse("appstore-apps"),
            data='{"name":"   ","category":"Tools","url":"https://new.app"}',
            content_type="application/json",
        )

        # -----------------------------------------------------------------------------
        # 2) canonical 오류 응답 검증
        # -----------------------------------------------------------------------------
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["code"], "invalid_request")
        self.assertEqual(payload["message"], "name is required")
        self.assertIn("name", payload["fieldErrors"])

    def test_appstore_detail_update_delete_and_view_like(self) -> None:
        """상세 조회/수정/삭제 및 좋아요/조회수 API를 검증합니다."""
        # -----------------------------------------------------------------------------
        # 1) 상세 조회
        # -----------------------------------------------------------------------------
        detail = self.client.get(reverse("appstore-app-detail", kwargs={"app_id": self.app.pk}))
        self.assertEqual(detail.status_code, 200)

        # -----------------------------------------------------------------------------
        # 2) 상세 수정
        # -----------------------------------------------------------------------------
        update_response = self.client.patch(
            reverse("appstore-app-detail", kwargs={"app_id": self.app.pk}),
            data='{"description":"updated"}',
            content_type="application/json",
        )
        self.assertEqual(update_response.status_code, 200)

        # -----------------------------------------------------------------------------
        # 3) 좋아요/조회수 증가
        # -----------------------------------------------------------------------------
        like_response = self.client.post(reverse("appstore-app-like", kwargs={"app_id": self.app.pk}))
        self.assertEqual(like_response.status_code, 200)

        view_response = self.client.post(reverse("appstore-app-view", kwargs={"app_id": self.app.pk}))
        self.assertEqual(view_response.status_code, 200)

        # -----------------------------------------------------------------------------
        # 4) 삭제
        # -----------------------------------------------------------------------------
        delete_response = self.client.delete(reverse("appstore-app-detail", kwargs={"app_id": self.app.pk}))
        self.assertEqual(delete_response.status_code, 200)

    def test_appstore_admin_can_manage_appstore_content(self) -> None:
        """AppStore admin이 타인 콘텐츠를 편집할 수 있는지 검증합니다."""
        # -----------------------------------------------------------------------------
        # 1) AppStore 관리자 사용자 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()
        app_admin = User.objects.create_user(
            sabun="S44444",
            password="test-password",
            email="s44444@example.com",
            knox_id="knox-44444",
        )
        actor = User.objects.create_superuser(
            sabun="S44445",
            password="test-password",
            knox_id="knox-44445",
        )
        account_services.decide_user_access(
            actor=actor,
            user_id=app_admin.id,
            scope_key="portal",
            action="grant",
            reason="AppStore 관리자 테스트 Portal 권한 부여",
            role="user",
        )
        account_services.decide_user_access(
            actor=actor,
            user_id=app_admin.id,
            scope_key="appstore",
            action="grant",
            reason="AppStore 관리자 테스트 앱 권한 부여",
            role="admin",
        )
        self.client.force_login(app_admin)

        # -----------------------------------------------------------------------------
        # 2) 타인 앱 편집 권한 노출 확인
        # -----------------------------------------------------------------------------
        detail_response = self.client.get(reverse("appstore-app-detail", kwargs={"app_id": self.app.pk}))
        self.assertEqual(detail_response.status_code, 200)
        detail_payload = detail_response.json()
        self.assertTrue(detail_payload["app"]["canEdit"])
        self.assertTrue(detail_payload["app"]["canDelete"])

        # -----------------------------------------------------------------------------
        # 3) 타인 앱 수정 허용 확인
        # -----------------------------------------------------------------------------
        update_response = self.client.patch(
            reverse("appstore-app-detail", kwargs={"app_id": self.app.pk}),
            data='{"description":"app admin updated"}',
            content_type="application/json",
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.json()["app"]["description"], "app admin updated")

        # -----------------------------------------------------------------------------
        # 4) 타인 댓글 수정 허용 확인
        # -----------------------------------------------------------------------------
        comment = create_comment(app=self.app, user=self.user, content="owner comment")
        comment_response = self.client.patch(
            reverse(
                "appstore-app-comment-detail",
                kwargs={"app_id": self.app.pk, "comment_id": comment.pk},
            ),
            data='{"content":"app admin comment update"}',
            content_type="application/json",
        )
        self.assertEqual(comment_response.status_code, 200)
        self.assertEqual(comment_response.json()["comment"]["content"], "app admin comment update")

    def test_appstore_comments_endpoints(self) -> None:
        """댓글 목록/생성/수정/삭제/좋아요 API를 검증합니다."""
        # -----------------------------------------------------------------------------
        # 1) 댓글 목록 조회
        # -----------------------------------------------------------------------------
        list_response = self.client.get(reverse("appstore-app-comments", kwargs={"app_id": self.app.pk}))
        self.assertEqual(list_response.status_code, 200)

        # -----------------------------------------------------------------------------
        # 2) 댓글 생성
        # -----------------------------------------------------------------------------
        create_response = self.client.post(
            reverse("appstore-app-comments", kwargs={"app_id": self.app.pk}),
            data='{"content":"comment"}',
            content_type="application/json",
        )
        self.assertEqual(create_response.status_code, 201)
        comment_id = create_response.json()["comment"]["id"]

        # -----------------------------------------------------------------------------
        # 3) 댓글 수정
        # -----------------------------------------------------------------------------
        update_response = self.client.patch(
            reverse(
                "appstore-app-comment-detail",
                kwargs={"app_id": self.app.pk, "comment_id": comment_id},
            ),
            data='{"content":"updated"}',
            content_type="application/json",
        )
        self.assertEqual(update_response.status_code, 200)

        # -----------------------------------------------------------------------------
        # 4) 댓글 좋아요
        # -----------------------------------------------------------------------------
        like_response = self.client.post(
            reverse(
                "appstore-app-comment-like",
                kwargs={"app_id": self.app.pk, "comment_id": comment_id},
            )
        )
        self.assertEqual(like_response.status_code, 200)

        # -----------------------------------------------------------------------------
        # 5) 댓글 삭제
        # -----------------------------------------------------------------------------
        delete_response = self.client.delete(
            reverse(
                "appstore-app-comment-detail",
                kwargs={"app_id": self.app.pk, "comment_id": comment_id},
            )
        )
        self.assertEqual(delete_response.status_code, 200)
