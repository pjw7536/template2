from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from api.account.models import UserSdwtProdAccess
from api.assistant import services as assistant_services
from api.assistant.services import AssistantChatConfig, AssistantChatService
from api.rag import services as rag_services


class AssistantRagIndexViewsTests(TestCase):
    def setUp(self) -> None:
        User = get_user_model()
        self.user = User.objects.create_user(
            sabun="S90000",
            password="test-password",
            email="s90000@example.com",
        )
        self.user.user_sdwt_prod = "group-a"
        self.user.knox_id = "knox-90000"
        self.user.save(update_fields=["user_sdwt_prod", "knox_id"])

        UserSdwtProdAccess.objects.create(user=self.user, user_sdwt_prod="group-b", can_manage=False)

    def test_rag_index_list_returns_accessible_user_sdwt_prods(self) -> None:
        self.client.force_login(self.user)

        response = self.client.get("/api/v1/assistant/rag-indexes")
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertEqual(payload.get("currentUserSdwtProd"), "group-a")
        self.assertEqual(
            set(payload.get("permissionGroups", [])),
            {"group-a", "group-b", "knox-90000", rag_services.RAG_PUBLIC_GROUP},
        )
        self.assertEqual(payload.get("ragIndexes"), rag_services.get_rag_index_candidates())
        self.assertEqual(payload.get("defaultRagIndex"), rag_services.resolve_rag_index_name(None))
        self.assertEqual(
            payload.get("emailRagIndex"),
            rag_services.resolve_rag_index_name(rag_services.RAG_INDEX_EMAILS),
        )

    def test_chat_accepts_accessible_user_sdwt_prod_override(self) -> None:
        self.client.force_login(self.user)

        with patch("api.assistant.views.assistant_chat_service.generate_reply") as mocked_generate:
            mocked_generate.return_value = SimpleNamespace(
                reply="OK",
                contexts=[],
                sources=[],
                is_dummy=True,
            )
            default_index = rag_services.resolve_rag_index_name(None)

            response = self.client.post(
                "/api/v1/assistant/chat",
                data=json.dumps(
                    {
                        "prompt": "hello",
                        "permission_groups": ["group-b"],
                        "rag_index_name": default_index,
                    }
                ),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mocked_generate.call_count, 1)
        kwargs = mocked_generate.call_args.kwargs
        self.assertEqual(kwargs.get("permission_groups"), ["group-b"])
        self.assertEqual(kwargs.get("rag_index_names"), [default_index])

    def test_chat_rejects_inaccessible_user_sdwt_prod_override(self) -> None:
        self.client.force_login(self.user)

        response = self.client.post(
            "/api/v1/assistant/chat",
            data=json.dumps({"prompt": "hello", "permission_groups": ["group-x"]}),
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
        superuser.knox_id = "knox-super"
        superuser.save(update_fields=["user_sdwt_prod", "knox_id"])

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
        permission_groups = payload.get("permissionGroups")
        self.assertEqual(permission_groups, sorted(permission_groups))
        self.assertEqual(
            set(permission_groups),
            {
                "group-a",
                "group-b",
                "group-c",
                "group-d",
                "group-admin",
                "knox-super",
                rag_services.RAG_PUBLIC_GROUP,
            },
        )

    def test_chat_accepts_user_sdwt_prod_override_for_superuser(self) -> None:
        User = get_user_model()
        superuser = User.objects.create_superuser(
            sabun="S90001",
            password="test-password",
            email="s90001@example.com",
        )
        superuser.user_sdwt_prod = "group-admin"
        superuser.knox_id = "knox-super"
        superuser.save(update_fields=["user_sdwt_prod", "knox_id"])

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
            default_index = rag_services.resolve_rag_index_name(None)

            response = self.client.post(
                "/api/v1/assistant/chat",
                data=json.dumps(
                    {
                        "prompt": "hello",
                        "permission_groups": ["group-c"],
                        "rag_index_name": [default_index],
                    }
                ),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        kwargs = mocked_generate.call_args.kwargs
        self.assertEqual(kwargs.get("permission_groups"), ["group-c"])
        self.assertEqual(kwargs.get("rag_index_names"), [default_index])


class AssistantChatServiceSourceFilteringTests(TestCase):
    def test_generate_llm_payload_sets_temperature_zero_when_background_knowledge_exists(self) -> None:
        service = AssistantChatService(
            config=AssistantChatConfig(
                use_dummy=False,
                llm_url="http://example.com",
                llm_credential="token",
                temperature=0.7,
            )
        )

        payload_with_context = service._generate_llm_payload("질문입니다", ["context"], email_ids=["E1"])
        self.assertEqual(payload_with_context.get("temperature"), 0.0)
        messages = payload_with_context.get("messages")
        self.assertEqual([entry.get("role") for entry in messages], ["system", "system", "system", "user"])

        payload_without_context = service._generate_llm_payload("질문입니다", [], email_ids=["E1"])
        self.assertEqual(payload_without_context.get("temperature"), 0.7)

    def test_generate_reply_builds_segments_and_filters_sources(self) -> None:
        service = AssistantChatService(
            config=AssistantChatConfig(
                use_dummy=False,
                llm_url="http://example.com",
                llm_credential="token",
            )
        )

        contexts = ["[emailId: E1]\ncontext 1", "[emailId: E2]\ncontext 2"]
        sources = [
            {"doc_id": "E1", "title": "메일 1", "snippet": "내용 1"},
            {"doc_id": "E2", "title": "메일 2", "snippet": "내용 2"},
        ]

        with patch.object(service, "_retrieve_documents", return_value=(contexts, {"hits": {}}, sources)):
            with patch.object(
                service,
                "_call_llm",
                return_value=(
                    json.dumps(
                        {
                            "answer": "통합 답변입니다",
                            "segments": [
                                {"answer": "메일 2 기반 답변", "usedEmailIds": ["E2"]},
                                {"answer": "메일 1+2 기반 답변", "usedEmailIds": ["E1", "E2", "E3"]},
                            ],
                        },
                        ensure_ascii=False,
                    ),
                    {"choices": []},
                ),
            ):
                result = service.generate_reply("질문입니다")

        self.assertEqual(result.reply, "통합 답변입니다")
        self.assertEqual(len(result.segments), 2)
        self.assertEqual(result.segments[0]["reply"], "메일 2 기반 답변")
        self.assertEqual([entry["doc_id"] for entry in result.segments[0]["sources"]], ["E2"])
        self.assertEqual(result.segments[1]["reply"], "메일 1+2 기반 답변")
        self.assertEqual([entry["doc_id"] for entry in result.segments[1]["sources"]], ["E1", "E2"])
        self.assertEqual([entry["doc_id"] for entry in result.sources], ["E1", "E2"])

    def test_generate_reply_hides_sources_on_unparseable_reply(self) -> None:
        service = AssistantChatService(
            config=AssistantChatConfig(
                use_dummy=False,
                llm_url="http://example.com",
                llm_credential="token",
            )
        )

        sources = [{"doc_id": "E1", "title": "메일 1", "snippet": "내용 1"}]

        with patch.object(service, "_retrieve_documents", return_value=(["context"], {"hits": {}}, sources)):
            with patch.object(service, "_call_llm", return_value=("그냥 텍스트 응답", {"choices": []})):
                result = service.generate_reply("질문입니다")

        self.assertEqual(result.reply, "그냥 텍스트 응답")
        self.assertEqual(result.sources, [])
        self.assertEqual(result.segments, [])

    def test_generate_reply_treats_empty_segments_as_no_sources(self) -> None:
        service = AssistantChatService(
            config=AssistantChatConfig(
                use_dummy=False,
                llm_url="http://example.com",
                llm_credential="token",
            )
        )

        sources = [{"doc_id": "E1", "title": "메일 1", "snippet": "내용 1"}]

        with patch.object(service, "_retrieve_documents", return_value=(["context"], {"hits": {}}, sources)):
            with patch.object(service, "_call_llm", return_value=('{"answer":"OK","segments":[]}', {"choices": []})):
                result = service.generate_reply("질문입니다")

        self.assertEqual(result.reply, "OK")
        self.assertEqual(result.sources, [])
        self.assertEqual(result.segments, [])

    def test_generate_reply_supports_legacy_used_email_ids_format(self) -> None:
        service = AssistantChatService(
            config=AssistantChatConfig(
                use_dummy=False,
                llm_url="http://example.com",
                llm_credential="token",
            )
        )

        sources = [
            {"doc_id": "E1", "title": "메일 1", "snippet": "내용 1"},
            {"doc_id": "E2", "title": "메일 2", "snippet": "내용 2"},
        ]

        with patch.object(service, "_retrieve_documents", return_value=(["context"], {"hits": {}}, sources)):
            with patch.object(
                service,
                "_call_llm",
                return_value=('{"answer":"OK","usedEmailIds":["E2","E3"]}', {"choices": []}),
            ):
                result = service.generate_reply("질문입니다")

        self.assertEqual(result.reply, "OK")
        self.assertEqual(len(result.segments), 1)
        self.assertEqual(result.segments[0]["reply"], "OK")
        self.assertEqual([entry["doc_id"] for entry in result.segments[0]["sources"]], ["E2"])
        self.assertEqual([entry["doc_id"] for entry in result.sources], ["E2"])


class AssistantNormalizationTests(TestCase):
    def test_normalize_room_id_defaults_to_default(self) -> None:
        self.assertEqual(assistant_services.normalize_room_id(None), "default")
        self.assertEqual(assistant_services.normalize_room_id(""), "default")

    def test_normalize_room_id_sanitizes(self) -> None:
        self.assertEqual(assistant_services.normalize_room_id(" room$% "), "room--")

    def test_normalize_sources_dedupes(self) -> None:
        sources = [
            {"doc_id": "DOC1", "title": "T1", "snippet": "S1"},
            {"docId": "DOC1", "title": "T1b", "snippet": "S1b"},
            {"doc_id": "DOC2", "title": "T2", "snippet": "S2"},
        ]
        normalized = assistant_services.normalize_sources(sources)
        self.assertEqual(len(normalized), 2)
        self.assertEqual({item["docId"] for item in normalized}, {"DOC1", "DOC2"})
