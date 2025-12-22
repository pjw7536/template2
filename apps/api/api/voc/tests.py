from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from api.voc.models import VocPost


class VocEndpointTests(TestCase):
    def setUp(self) -> None:
        User = get_user_model()
        self.user = User.objects.create_user(sabun="S80000", password="test-password")
        self.client.force_login(self.user)

    def test_voc_posts_list_returns_results(self) -> None:
        VocPost.objects.create(title="Hello", content="World", author=self.user, status="접수")
        response = self.client.get(reverse("voc-posts"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 1)

    def test_voc_posts_create_update_delete_and_reply(self) -> None:
        create_response = self.client.post(
            reverse("voc-posts"),
            data='{"title":"Title","content":"Body","status":"접수"}',
            content_type="application/json",
        )
        self.assertEqual(create_response.status_code, 201)
        post_id = create_response.json()["post"]["id"]

        update_response = self.client.patch(
            reverse("voc-post-detail", kwargs={"post_id": post_id}),
            data='{"status":"진행중","title":"Updated"}',
            content_type="application/json",
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.json()["post"]["status"], "진행중")

        reply_response = self.client.post(
            reverse("voc-post-reply", kwargs={"post_id": post_id}),
            data='{"content":"Reply"}',
            content_type="application/json",
        )
        self.assertEqual(reply_response.status_code, 201)

        delete_response = self.client.delete(reverse("voc-post-detail", kwargs={"post_id": post_id}))
        self.assertEqual(delete_response.status_code, 200)
        self.assertTrue(delete_response.json()["success"])
