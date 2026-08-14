# =============================================================================
# 모듈 설명: voc 엔드포인트 테스트를 제공합니다.
# - 주요 클래스: VocEndpointTests
# - 불변 조건: URL 네임(voc-*)이 등록되어 있어야 합니다.
# =============================================================================

from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

import api.voc.selectors as voc_selectors
import api.voc.services as voc_services
from api.voc.models import VocPost
from api.voc.serializers import (
    VocPostCreateInputSerializer,
    VocPostUpdateInputSerializer,
    VocReplyCreateInputSerializer,
)


def _allow_test_scope_access(test_case: TestCase) -> None:
    """도메인 endpoint 테스트에서 공통 portal/app 권한 경계를 격리합니다."""

    patcher = patch(
        "api.account.services.get_access_payload",
        return_value={"allowed": True},
    )
    patcher.start()
    test_case.addCleanup(patcher.stop)


class VocEndpointTests(TestCase):
    def setUp(self) -> None:
        _allow_test_scope_access(self)
        User = get_user_model()
        self.user = User.objects.create_user(
            sabun="S80000",
            password="test-password",
            knox_id="knox-80000",
            username="정진우",
        )
        self.client.force_login(self.user)

    def test_voc_posts_list_returns_results(self) -> None:
        VocPost.objects.create(title="Hello", content="World", author=self.user, status="접수")
        response = self.client.get(reverse("voc-posts"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(set(payload), {"results"})
        self.assertEqual(payload["results"][0]["app"], "기타")
        self.assertEqual(payload["results"][0]["author"]["name"], "정진우(knox-80000)")

    def test_voc_author_display_uses_only_username_and_knox_id(self) -> None:
        User = get_user_model()
        fallback_user = User.objects.create_user(
            sabun="S80001",
            password="test-password",
            knox_id="knox-80001",
            username="",
            first_name="진우",
            last_name="정",
            email="jinwoo@example.com",
        )
        VocPost.objects.create(title="Fallback", content="Body", author=fallback_user, status="접수")

        response = self.client.get(reverse("voc-posts"))

        self.assertEqual(response.status_code, 200)
        results = response.json()["results"]
        fallback_post = next(post for post in results if post["title"] == "Fallback")
        self.assertEqual(fallback_post["author"]["name"], "knox-80001")

    def test_voc_posts_create_update_delete_and_reply(self) -> None:
        # -----------------------------------------------------------------------------
        # 1) 게시글 생성
        # -----------------------------------------------------------------------------
        create_response = self.client.post(
            reverse("voc-posts"),
            data='{"title":"Title","content":"Body","status":"접수","app":"기타"}',
            content_type="application/json",
        )
        self.assertEqual(create_response.status_code, 201)
        create_payload = create_response.json()
        self.assertEqual(set(create_payload), {"post"})
        post_id = create_payload["post"]["id"]

        # -----------------------------------------------------------------------------
        # 2) 게시글 수정
        # -----------------------------------------------------------------------------
        update_response = self.client.patch(
            reverse("voc-post-detail", kwargs={"post_id": post_id}),
            data='{"status":"진행중","title":"Updated"}',
            content_type="application/json",
        )
        self.assertEqual(update_response.status_code, 200)
        update_payload = update_response.json()
        self.assertEqual(set(update_payload), {"post"})
        self.assertEqual(update_payload["post"]["status"], "진행중")

        # -----------------------------------------------------------------------------
        # 3) 답변 추가
        # -----------------------------------------------------------------------------
        reply_response = self.client.post(
            reverse("voc-post-reply", kwargs={"post_id": post_id}),
            data='{"content":"Reply"}',
            content_type="application/json",
        )
        self.assertEqual(reply_response.status_code, 201)
        self.assertEqual(set(reply_response.json()), {"post", "reply"})

        # -----------------------------------------------------------------------------
        # 4) 게시글 삭제
        # -----------------------------------------------------------------------------
        delete_response = self.client.delete(reverse("voc-post-detail", kwargs={"post_id": post_id}))
        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(delete_response.json(), {"success": True})

    def test_voc_posts_create_requires_app(self) -> None:
        response = self.client.post(
            reverse("voc-posts"),
            data='{"title":"Title","content":"Body","status":"접수"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_voc_admin_can_update_another_users_post(self) -> None:
        """VOC admin 역할은 다른 사용자의 게시글을 관리할 수 있어야 합니다."""

        User = get_user_model()
        admin_user = User.objects.create_user(
            sabun="S80002",
            password="test-password",
            knox_id="knox-80002",
        )
        admin_user.keycloak_subject = "voc-admin-subject"
        admin_user.keycloak_client_roles = {
            "portal": ["portal-user", "voc-admin"],
        }
        admin_user.save(update_fields=["keycloak_subject", "keycloak_client_roles"])
        post = VocPost.objects.create(
            title="다른 사용자 글",
            content="내용",
            author=self.user,
            status="접수",
        )

        self.client.force_login(admin_user)
        response = self.client.patch(
            reverse("voc-post-detail", kwargs={"post_id": post.id}),
            data='{"status":"진행중"}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["post"]["status"], "진행중")


class VocSerializerTests(SimpleTestCase):
    """VOC 입력 serializer의 canonical validation을 검증합니다."""

    def test_create_serializer_applies_default_status(self) -> None:
        serializer = VocPostCreateInputSerializer(
            data={"title": "제목", "content": "내용", "app": "기타"}
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["status"], "접수")

    def test_input_serializers_reject_unknown_fields(self) -> None:
        """정상 필드와 함께 전달된 legacy 필드도 모두 거절해야 합니다."""

        serializers_with_legacy_field = [
            VocPostCreateInputSerializer(
                data={
                    "title": "제목",
                    "content": "내용",
                    "app": "기타",
                    "created_at": "legacy",
                }
            ),
            VocPostUpdateInputSerializer(
                data={"status": "완료", "created_at": "legacy"}
            ),
            VocReplyCreateInputSerializer(
                data={"content": "답변", "post_id": 1}
            ),
        ]

        for serializer in serializers_with_legacy_field:
            with self.subTest(serializer=serializer.__class__.__name__):
                self.assertFalse(serializer.is_valid())
                self.assertIn("unexpectedFields", serializer.errors)


class VocServiceSelectorTests(TestCase):
    """VOC service와 selector의 역할 경계를 검증합니다."""

    def setUp(self) -> None:
        User = get_user_model()
        self.user = User.objects.create_user(
            sabun="S80100",
            password="test-password",
            knox_id="knox-80100",
        )

    def test_create_and_update_service_persist_validated_values(self) -> None:
        post = voc_services.create_post(
            author=self.user,
            title="처음",
            content="내용",
            status="접수",
            app="기타",
        )

        updated = voc_services.update_post(post=post, updates={"status": "완료"})

        updated.refresh_from_db()
        self.assertEqual(updated.status, "완료")

    def test_post_list_selector_orders_newest_first(self) -> None:
        first = VocPost.objects.create(title="먼저", content="내용", author=self.user)
        second = VocPost.objects.create(title="나중", content="내용", author=self.user)

        self.assertEqual(list(voc_selectors.get_post_list()), [second, first])
