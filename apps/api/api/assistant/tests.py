from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from api.account.models import UserSdwtProdAccess


class AssistantRagIndexViewsTests(TestCase):
    def setUp(self) -> None:
        User = get_user_model()
        self.user = User.objects.create_user(
            sabun="S90000",
            password="test-password",
            email="s90000@example.com",
        )
        self.user.user_sdwt_prod = "group-a"
        self.user.save(update_fields=["user_sdwt_prod"])

        UserSdwtProdAccess.objects.create(user=self.user, user_sdwt_prod="group-b", can_manage=False)

    def test_rag_index_list_returns_accessible_user_sdwt_prods(self) -> None:
        self.client.force_login(self.user)

        response = self.client.get("/api/v1/assistant/rag-indexes")
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertEqual(payload.get("currentUserSdwtProd"), "group-a")
        self.assertEqual(payload.get("results"), ["group-a", "group-b"])

    def test_chat_accepts_accessible_user_sdwt_prod_override(self) -> None:
        self.client.force_login(self.user)

        with patch("api.assistant.views.assistant_chat_service.generate_reply") as mocked_generate:
            mocked_generate.return_value = SimpleNamespace(
                reply="OK",
                contexts=[],
                sources=[],
                is_dummy=True,
            )

            response = self.client.post(
                "/api/v1/assistant/chat",
                data=json.dumps({"prompt": "hello", "userSdwtProd": "group-b"}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mocked_generate.call_count, 1)
        kwargs = mocked_generate.call_args.kwargs
        self.assertEqual(kwargs.get("rag_index_name"), "group-b")

    def test_chat_rejects_inaccessible_user_sdwt_prod_override(self) -> None:
        self.client.force_login(self.user)

        response = self.client.post(
            "/api/v1/assistant/chat",
            data=json.dumps({"prompt": "hello", "userSdwtProd": "group-x"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        payload = response.json()
        self.assertIn("error", payload)

    def test_rag_index_list_returns_all_known_user_sdwt_prods_for_superuser(self) -> None:
        User = get_user_model()
        superuser = User.objects.create_superuser(
            sabun="S90001",
            password="test-password",
            email="s90001@example.com",
        )
        superuser.user_sdwt_prod = "group-admin"
        superuser.save(update_fields=["user_sdwt_prod"])

        other_user = User.objects.create_user(
            sabun="S90002",
            password="test-password",
            email="s90002@example.com",
        )
        other_user.user_sdwt_prod = "group-c"
        other_user.save(update_fields=["user_sdwt_prod"])
        UserSdwtProdAccess.objects.create(user=other_user, user_sdwt_prod="group-d", can_manage=False)

        self.client.force_login(superuser)

        response = self.client.get("/api/v1/assistant/rag-indexes")
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertEqual(payload.get("currentUserSdwtProd"), "group-admin")
        results = payload.get("results")
        self.assertEqual(results, sorted(results))
        self.assertEqual(set(results), {"group-a", "group-b", "group-c", "group-d", "group-admin"})

    def test_chat_accepts_user_sdwt_prod_override_for_superuser(self) -> None:
        User = get_user_model()
        superuser = User.objects.create_superuser(
            sabun="S90001",
            password="test-password",
            email="s90001@example.com",
        )
        superuser.user_sdwt_prod = "group-admin"
        superuser.save(update_fields=["user_sdwt_prod"])

        other_user = User.objects.create_user(
            sabun="S90002",
            password="test-password",
            email="s90002@example.com",
        )
        other_user.user_sdwt_prod = "group-c"
        other_user.save(update_fields=["user_sdwt_prod"])

        self.client.force_login(superuser)

        with patch("api.assistant.views.assistant_chat_service.generate_reply") as mocked_generate:
            mocked_generate.return_value = SimpleNamespace(
                reply="OK",
                contexts=[],
                sources=[],
                is_dummy=True,
            )

            response = self.client.post(
                "/api/v1/assistant/chat",
                data=json.dumps({"prompt": "hello", "userSdwtProd": "group-c"}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        kwargs = mocked_generate.call_args.kwargs
        self.assertEqual(kwargs.get("rag_index_name"), "group-c")
