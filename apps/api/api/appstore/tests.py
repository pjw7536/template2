from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from api.appstore.services import create_app, update_app


class AppstoreScreenshotTests(TestCase):
    """appstore 스크린샷 저장/응답 동작을 검증합니다."""

    def test_create_app_persists_screenshot_url(self) -> None:
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
        self.assertEqual(app.screenshot_url, screenshot_url)

    def test_update_app_allows_clearing_screenshot_url(self) -> None:
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

