from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from api.appstore.services import create_app, create_comment, update_app


class AppstoreScreenshotTests(TestCase):
    """appstore 스크린샷 저장/응답 동작을 검증합니다."""

    def test_create_app_stores_data_url_as_base64(self) -> None:
        User = get_user_model()
        user = User.objects.create_user(sabun="S12345", password="test-password")
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

    def test_create_app_keeps_external_screenshot_url(self) -> None:
        User = get_user_model()
        user = User.objects.create_user(sabun="S88888", password="test-password")
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

    def test_update_app_allows_clearing_screenshot(self) -> None:
        User = get_user_model()
        user = User.objects.create_user(sabun="S99999", password="test-password")
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

    def test_detail_payload_includes_screenshot_url(self) -> None:
        User = get_user_model()
        user = User.objects.create_user(sabun="S54321", password="test-password")
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


class AppstoreCommentReplyLikeTests(TestCase):
    """appstore 댓글 대댓글/좋아요 동작을 검증합니다."""

    def setUp(self) -> None:
        User = get_user_model()
        self.user = User.objects.create_user(sabun="S22222", password="test-password")
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
