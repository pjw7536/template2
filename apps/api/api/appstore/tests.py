from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from api.appstore.services import create_app, create_comment, update_app


class AppstoreScreenshotTests(TestCase):
    """appstore 스크린샷 저장/응답 동작을 검증합니다."""

    def test_create_app_stores_data_url_as_base64(self) -> None:
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S12345",
            password="test-password",
            knox_id="knox-12345",
        )
        screenshot_url = "data:image/png;base64,AAA="

        app = create_app(
            owner=user,
            name="Test App",
            category="Tools",
            description="",
            url="https://example.com",
            badge="",
            tags=[],
            screenshot_url=screenshot_url,
            contact_name="홍길동",
            contact_knoxid="hong",
        )

        app.refresh_from_db()
        self.assertEqual(app.screenshot_url, "")
        self.assertEqual(app.screenshot_base64, "AAA=")
        self.assertEqual(app.screenshot_mime_type, "image/png")
        self.assertEqual(app.screenshot_gallery, [])

    def test_create_app_keeps_external_screenshot_url(self) -> None:
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S88888",
            password="test-password",
            knox_id="knox-88888",
        )
        screenshot_url = "https://example.com/screenshot.png"

        app = create_app(
            owner=user,
            name="Test App",
            category="Tools",
            description="",
            url="https://example.com",
            badge="",
            tags=[],
            screenshot_url=screenshot_url,
            contact_name="홍길동",
            contact_knoxid="hong",
        )

        app.refresh_from_db()
        self.assertEqual(app.screenshot_url, screenshot_url)
        self.assertEqual(app.screenshot_base64, "")
        self.assertEqual(app.screenshot_mime_type, "")
        self.assertEqual(app.screenshot_gallery, [])

    def test_create_app_stores_gallery_items(self) -> None:
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S77777",
            password="test-password",
            knox_id="knox-77777",
        )

        cover = "data:image/png;base64,COVER="
        extra_url = "https://example.com/extra.png"
        extra_data = "data:image/png;base64,EXTRA="

        app = create_app(
            owner=user,
            name="Test App",
            category="Tools",
            description="",
            url="https://example.com",
            badge="",
            tags=[],
            screenshot_urls=[cover, extra_url, extra_data],
            screenshot_url="",
            contact_name="홍길동",
            contact_knoxid="hong",
        )

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
            badge="",
            tags=[],
            screenshot_url="data:image/png;base64,BBB=",
            contact_name="홍길동",
            contact_knoxid="hong",
        )

        updated = update_app(app=app, updates={"screenshot_url": ""})
        updated.refresh_from_db()
        self.assertEqual(updated.screenshot_url, "")
        self.assertEqual(updated.screenshot_base64, "")
        self.assertEqual(updated.screenshot_mime_type, "")
        self.assertEqual(updated.screenshot_gallery, [])

    def test_detail_payload_includes_screenshot_url(self) -> None:
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S54321",
            password="test-password",
            knox_id="knox-54321",
        )
        screenshot_url = "data:image/png;base64,CCC="
        app = create_app(
            owner=user,
            name="Test App",
            category="Tools",
            description="",
            url="https://example.com",
            badge="",
            tags=[],
            screenshot_url=screenshot_url,
            contact_name="홍길동",
            contact_knoxid="hong",
        )

        response = self.client.get(reverse("appstore-app-detail", kwargs={"app_id": app.pk}))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["app"]["screenshotUrl"], screenshot_url)
        self.assertEqual(payload["app"]["screenshotUrls"], [screenshot_url])
        self.assertEqual(payload["app"]["coverScreenshotIndex"], 0)


class AppstoreCommentReplyLikeTests(TestCase):
    """appstore 댓글 대댓글/좋아요 동작을 검증합니다."""

    def setUp(self) -> None:
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
            badge="",
            tags=[],
            screenshot_url="",
            contact_name="홍길동",
            contact_knoxid="hong",
        )

    def test_create_reply_comment_sets_parent_comment_id(self) -> None:
        parent = create_comment(app=self.app, user=self.user, content="부모 댓글")
        url = reverse("appstore-app-comments", kwargs={"app_id": self.app.pk})
        response = self.client.post(
            url,
            data='{"content":"대댓글","parentCommentId":%d}' % parent.pk,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["comment"]["parentCommentId"], parent.pk)

        detail_response = self.client.get(reverse("appstore-app-detail", kwargs={"app_id": self.app.pk}))
        self.assertEqual(detail_response.status_code, 200)
        detail_payload = detail_response.json()
        comment_ids = {comment["id"] for comment in detail_payload["app"]["comments"]}
        self.assertIn(parent.pk, comment_ids)
        self.assertIn(payload["comment"]["id"], comment_ids)

    def test_toggle_comment_like_updates_like_count_and_liked(self) -> None:
        comment = create_comment(app=self.app, user=self.user, content="좋아요 테스트")
        like_url = reverse(
            "appstore-app-comment-like",
            kwargs={"app_id": self.app.pk, "comment_id": comment.pk},
        )

        first = self.client.post(like_url)
        self.assertEqual(first.status_code, 200)
        first_payload = first.json()
        self.assertTrue(first_payload["liked"])
        self.assertEqual(first_payload["likeCount"], 1)

        detail_response = self.client.get(reverse("appstore-app-detail", kwargs={"app_id": self.app.pk}))
        self.assertEqual(detail_response.status_code, 200)
        detail_payload = detail_response.json()
        liked_comment = next(
            item for item in detail_payload["app"]["comments"] if item["id"] == comment.pk
        )
        self.assertTrue(liked_comment["liked"])
        self.assertEqual(liked_comment["likeCount"], 1)

        second = self.client.post(like_url)
        self.assertEqual(second.status_code, 200)
        second_payload = second.json()
        self.assertFalse(second_payload["liked"])
        self.assertEqual(second_payload["likeCount"], 0)


class AppstoreEndpointTests(TestCase):
    def setUp(self) -> None:
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
            badge="",
            tags=[],
            screenshot_url="",
            contact_name="홍길동",
            contact_knoxid="hong",
        )

    def test_appstore_apps_list_and_create(self) -> None:
        list_response = self.client.get(reverse("appstore-apps"))
        self.assertEqual(list_response.status_code, 200)

        create_response = self.client.post(
            reverse("appstore-apps"),
            data=(
                '{"name":"New App","category":"Tools","description":"desc","url":"https://new.app",'
                '"tags":["tag1"],"contactName":"User","contactKnoxid":"user1"}'
            ),
            content_type="application/json",
        )
        self.assertEqual(create_response.status_code, 201)

    def test_appstore_detail_update_delete_and_view_like(self) -> None:
        detail = self.client.get(reverse("appstore-app-detail", kwargs={"app_id": self.app.pk}))
        self.assertEqual(detail.status_code, 200)

        update_response = self.client.patch(
            reverse("appstore-app-detail", kwargs={"app_id": self.app.pk}),
            data='{"description":"updated","badge":"New"}',
            content_type="application/json",
        )
        self.assertEqual(update_response.status_code, 200)

        like_response = self.client.post(reverse("appstore-app-like", kwargs={"app_id": self.app.pk}))
        self.assertEqual(like_response.status_code, 200)

        view_response = self.client.post(reverse("appstore-app-view", kwargs={"app_id": self.app.pk}))
        self.assertEqual(view_response.status_code, 200)

        delete_response = self.client.delete(reverse("appstore-app-detail", kwargs={"app_id": self.app.pk}))
        self.assertEqual(delete_response.status_code, 200)

    def test_appstore_comments_endpoints(self) -> None:
        list_response = self.client.get(reverse("appstore-app-comments", kwargs={"app_id": self.app.pk}))
        self.assertEqual(list_response.status_code, 200)

        create_response = self.client.post(
            reverse("appstore-app-comments", kwargs={"app_id": self.app.pk}),
            data='{"content":"comment"}',
            content_type="application/json",
        )
        self.assertEqual(create_response.status_code, 201)
        comment_id = create_response.json()["comment"]["id"]

        update_response = self.client.patch(
            reverse(
                "appstore-app-comment-detail",
                kwargs={"app_id": self.app.pk, "comment_id": comment_id},
            ),
            data='{"content":"updated"}',
            content_type="application/json",
        )
        self.assertEqual(update_response.status_code, 200)

        like_response = self.client.post(
            reverse(
                "appstore-app-comment-like",
                kwargs={"app_id": self.app.pk, "comment_id": comment_id},
            )
        )
        self.assertEqual(like_response.status_code, 200)

        delete_response = self.client.delete(
            reverse(
                "appstore-app-comment-detail",
                kwargs={"app_id": self.app.pk, "comment_id": comment_id},
            )
        )
        self.assertEqual(delete_response.status_code, 200)
