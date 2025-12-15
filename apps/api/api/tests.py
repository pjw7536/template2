from __future__ import annotations

import json
from unittest.mock import Mock, patch

from django.test import RequestFactory, SimpleTestCase

from api.auth.oidc import _extract_user_info_from_claims
from api.assistant.services import AssistantChatConfig, AssistantChatService, AssistantConfigError
from api.assistant.views import AssistantChatView, _normalize_sources
from api.rag.services import search_rag


class OidcClaimExtractionTests(SimpleTestCase):
    """OIDC 클레임에서 사용자 정보 추출 로직을 검증합니다."""

    def test_extract_user_info_maps_loginid_to_knox_id(self) -> None:
        claims = {
            "loginid": "knox-user",
            "sabun": "12345",
            "username": "홍길동",
            "deptname": "Engineering",
            "mail": "user@example.com",
        }

        info = _extract_user_info_from_claims(claims)
        self.assertEqual(info["knox_id"], "knox-user")
        self.assertEqual(info["sabun"], "12345")
        self.assertEqual(info["deptname"], "Engineering")
        self.assertEqual(info["mail"], "user@example.com")

    def test_extract_user_info_prefers_givenname_surname(self) -> None:
        claims = {
            "loginid": "knox-user",
            "sabun": "12345",
            "givenname": "John",
            "surname": "Doe",
            "deptname": "Engineering",
            "mail": "user@example.com",
        }

        info = _extract_user_info_from_claims(claims)
        self.assertEqual(info["first_name"], "John")
        self.assertEqual(info["last_name"], "Doe")


class AssistantSourceNormalizationTests(SimpleTestCase):
    def test_normalize_sources_deduplicates_doc_ids_preserving_first_hit(self) -> None:
        raw_sources = [
            {"doc_id": "email-1", "title": "첫번째"},
            {"doc_id": "email-1", "title": "두번째"},
            {"docId": "email-2", "title": "세번째"},
            {"doc_id": " email-2 ", "title": "네번째"},
            {"doc_id": "email-3"},
            {"doc_id": ""},
            {"doc_id": None},
            "not-a-dict",
        ]

        normalized = _normalize_sources(raw_sources)

        self.assertEqual([entry["docId"] for entry in normalized], ["email-1", "email-2", "email-3"])
        self.assertEqual(normalized[0]["title"], "첫번째")
        self.assertEqual(normalized[1]["title"], "세번째")


class RagSearchServiceTests(SimpleTestCase):
    def test_search_rag_posts_expected_payload(self) -> None:
        response = Mock()
        response.raise_for_status = Mock()
        response.json.return_value = {"hits": {"hits": []}}

        with patch("api.rag.services.RAG_SEARCH_URL", "http://rag/search"), patch(
            "api.rag.services.RAG_HEADERS", {"Content-Type": "application/json"}
        ), patch("api.rag.services.RAG_PERMISSION_GROUPS", ["group-a"]), patch(
            "api.rag.services.RAG_INDEX_NAME", "idx-default"
        ), patch(
            "api.rag.services.requests.post", return_value=response
        ) as post:
            result = search_rag("hello", num_result_doc=3, timeout=12)

        self.assertEqual(result, {"hits": {"hits": []}})

        args, kwargs = post.call_args
        self.assertEqual(args[0], "http://rag/search")
        self.assertEqual(kwargs["headers"], {"Content-Type": "application/json"})
        self.assertEqual(
            kwargs["json"],
            {
                "index_name": "rp-idx-default",
                "permission_groups": ["group-a"],
                "query_text": "hello",
                "num_result_doc": 3,
            },
        )
        self.assertEqual(kwargs["timeout"], 12)


class AssistantRagIntegrationTests(SimpleTestCase):
    def test_generate_reply_uses_rag_services_search(self) -> None:
        rag_response = {
            "hits": {
                "hits": [
                    {
                        "_id": "doc-1",
                        "_source": {
                            "doc_id": "email-1",
                            "title": "첫번째",
                            "merge_title_content": "컨텍스트1",
                        },
                    },
                    {
                        "_id": "doc-2",
                        "_source": {
                            "doc_id": "email-2",
                            "title": "두번째",
                            "merge_title_content": "컨텍스트2",
                        },
                    },
                ]
            }
        }

        config = AssistantChatConfig(use_dummy=True, dummy_use_rag=True, rag_index_name="idx-user", rag_num_docs=5)

        with patch("api.rag.services.RAG_SEARCH_URL", "http://rag/search"), patch(
            "api.rag.services.search_rag", return_value=rag_response
        ) as search_mock:
            service = AssistantChatService(config=config)
            result = service.generate_reply("hello")

        search_mock.assert_called_once_with("hello", index_name="idx-user", num_result_doc=5, timeout=30)
        self.assertTrue(result.is_dummy)
        self.assertEqual(result.contexts, ["컨텍스트1", "컨텍스트2"])
        self.assertEqual([source["doc_id"] for source in result.sources], ["email-1", "email-2"])
        self.assertEqual(result.rag_response, rag_response)


class AssistantChatViewTests(SimpleTestCase):
    def setUp(self) -> None:
        self.factory = RequestFactory()

    def test_chat_view_returns_response_without_rag_url_attribute_error(self) -> None:
        class DummyUser:
            is_authenticated = True
            email = "dummy.user@example.com"
            user_sdwt_prod = ""

            def get_username(self) -> str:
                return "dummy"

        request = self.factory.post(
            "/api/v1/assistant/chat",
            data=json.dumps({"prompt": "hello"}),
            content_type="application/json",
        )
        request.user = DummyUser()

        with patch(
            "api.assistant.views.assistant_chat_service.generate_reply",
            return_value=Mock(reply="안녕", contexts=[], sources=[], is_dummy=True),
        ):
            response = AssistantChatView().post(request)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode("utf-8"))
        self.assertEqual(payload["reply"], "안녕")
        self.assertIn("meta", payload)

    def test_chat_view_returns_503_when_assistant_config_error(self) -> None:
        class DummyUser:
            is_authenticated = True
            email = "dummy.user@example.com"
            user_sdwt_prod = ""

            def get_username(self) -> str:
                return "dummy"

        request = self.factory.post(
            "/api/v1/assistant/chat",
            data=json.dumps({"prompt": "hello"}),
            content_type="application/json",
        )
        request.user = DummyUser()

        with patch(
            "api.assistant.views.assistant_chat_service.generate_reply",
            side_effect=AssistantConfigError("missing config"),
        ):
            response = AssistantChatView().post(request)

        self.assertEqual(response.status_code, 503)
