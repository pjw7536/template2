# =============================================================================
# 모듈: 어시스턴트 기능 테스트
# 주요 대상: RAG 인덱스 조회, 채팅 권한 검증, 응답/정규화 처리
# 주요 가정: 외부 호출은 mock으로 대체합니다.
# =============================================================================
from __future__ import annotations

import csv
import json
from datetime import timedelta
from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.utils import timezone

import api.account.services as account_services
from api.assistant import services as assistant_services
from api.assistant.models import (
    AssistantContextSnapshot,
    AssistantConversation,
    AssistantConversationSummary,
    AssistantGeneration,
    AssistantMessage,
    AssistantMessageFeedback,
)
from api.assistant.serializers import (
    AssistantChatRequestSerializer,
    AssistantMessageBatchSerializer,
)
from api.assistant.services import (
    AssistantChatConfig,
    AssistantChatService,
    AssistantConfigError,
    AssistantOpenWebUIConfig,
    build_openwebui_messages,
    normalize_openwebui_conversation_title,
    request_openwebui_chat,
    request_openwebui_conversation_title,
    stream_openwebui_chat,
)
from api.assistant.views import AssistantChatView
import api.rag.services as rag_services


def _set_current_affiliation(user, *, user_sdwt_prod: str) -> None:
    """테스트 사용자의 현재 앱 소속을 설정합니다."""

    account_services.set_current_affiliation_for_user(
        user=user,
        department="Dept",
        line="Line",
        user_sdwt_prod=user_sdwt_prod,
    )


def _allow_test_scope_access(test_case: TestCase) -> None:
    """도메인 endpoint 테스트에서 공통 portal/app 권한 경계를 격리합니다."""

    for target in (
        "api.account.services.get_access_payload",
        "api.account.services.data_scope.get_access_payload",
    ):
        patcher = patch(target, return_value={"allowed": True})
        patcher.start()
        test_case.addCleanup(patcher.stop)


class AssistantRagIndexViewsTests(TestCase):
    """RAG 인덱스/권한 그룹 API 동작을 검증합니다."""

    def setUp(self) -> None:
        """테스트용 사용자/권한 데이터를 준비합니다."""
        _allow_test_scope_access(self)
        User = get_user_model()
        self.user = User.objects.create_user(
            sabun="S90000",
            password="test-password",
            email="s90000@example.com",
        )
        self.user.knox_id = "knox-90000"
        self.user.save(update_fields=["knox_id"])
        _set_current_affiliation(self.user, user_sdwt_prod="group-a")

        manager = User.objects.create_user(sabun="S90010", password="test-password")
        _set_current_affiliation(manager, user_sdwt_prod="group-b")
        account_services.ensure_self_access(manager, role="manager")
        _, status_code = account_services.grant_or_revoke_access(
            grantor=manager,
            target_group="group-b",
            target_user=self.user,
            action="grant",
            role="member",
            reason="테스트 권한 변경",
        )
        self.assertEqual(status_code, 200)
        authority = User.objects.create_superuser(
            sabun="S90012",
            password="test-password",
        )
        affiliation = account_services.ensure_affiliation_option(
            department="Dept",
            line="Line",
            user_sdwt_prod="group-b",
        )
        payload, data_scope_status = account_services.update_user_scope_affiliation_data(
            actor=authority,
            user_id=self.user.id,
            scope_key="assistant",
            data_scope_mode="default",
            affiliation_ids=[affiliation.id],
            reason="Assistant 테스트 추가 범위",
        )
        self.assertEqual(data_scope_status, 200, payload)

    def test_rag_index_list_returns_accessible_user_sdwt_prods(self) -> None:
        """접근 가능한 user_sdwt_prod가 응답에 포함되는지 확인합니다."""
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
        """접근 가능한 permission_groups override가 허용되는지 확인합니다."""
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
        """접근 불가능한 permission_groups override는 거부되는지 확인합니다."""
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
        """슈퍼유저는 모든 user_sdwt_prod가 노출되는지 확인합니다."""
        User = get_user_model()
        superuser = User.objects.create_superuser(
            sabun="S90001",
            password="test-password",
            email="s90001@example.com",
        )
        superuser.knox_id = "knox-super"
        superuser.save(update_fields=["knox_id"])
        _set_current_affiliation(superuser, user_sdwt_prod="group-admin")

        other_user = User.objects.create_user(
            sabun="S90002",
            password="test-password",
            email="s90002@example.com",
        )
        _set_current_affiliation(other_user, user_sdwt_prod="group-c")
        manager = User.objects.create_user(sabun="S90011", password="test-password")
        _set_current_affiliation(manager, user_sdwt_prod="group-d")
        account_services.ensure_self_access(manager, role="manager")
        _, status_code = account_services.grant_or_revoke_access(
            grantor=manager,
            target_group="group-d",
            target_user=other_user,
            action="grant",
            role="member",
            reason="테스트 권한 변경",
        )
        self.assertEqual(status_code, 200)

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
        """슈퍼유저는 permission_groups override가 허용되는지 확인합니다."""
        User = get_user_model()
        superuser = User.objects.create_superuser(
            sabun="S90001",
            password="test-password",
            email="s90001@example.com",
        )
        superuser.knox_id = "knox-super"
        superuser.save(update_fields=["knox_id"])
        _set_current_affiliation(superuser, user_sdwt_prod="group-admin")

        other_user = User.objects.create_user(
            sabun="S90002",
            password="test-password",
            email="s90002@example.com",
        )
        _set_current_affiliation(other_user, user_sdwt_prod="group-c")

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
    """LLM 응답/출처 필터링 동작을 검증합니다."""

    def test_generate_llm_payload_sets_temperature_zero_when_background_knowledge_exists(self) -> None:
        """배경지식이 있으면 temperature가 0으로 설정되는지 확인합니다."""
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
        """segments 기반 출처 필터링이 올바른지 확인합니다."""
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
        """파싱 불가 응답일 때 출처가 숨겨지는지 확인합니다."""
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
        """segments가 비어 있으면 출처가 비워지는지 확인합니다."""
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
        """레거시 usedEmailIds 포맷을 처리하는지 확인합니다."""
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


class AssistantRagIntegrationTests(SimpleTestCase):
    """Assistant와 RAG 연동 경로를 검증합니다."""

    def test_generate_reply_uses_rag_services_search(self) -> None:
        """generate_reply가 RAG 검색을 호출하는지 확인합니다."""
        # -------------------------------------------------------------------------
        # 1) RAG 응답 더미 준비
        # -------------------------------------------------------------------------
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

        # -------------------------------------------------------------------------
        # 2) Assistant 설정 구성
        # -------------------------------------------------------------------------
        config = AssistantChatConfig(
            use_dummy=True,
            dummy_use_rag=True,
            rag_index_names=["idx-user"],
            rag_num_docs=5,
        )

        # -------------------------------------------------------------------------
        # 3) RAG 검색 patch 및 호출
        # -------------------------------------------------------------------------
        with patch("api.rag.services.RAG_SEARCH_URL", "http://rag/search"), patch(
            "api.rag.services.search_rag", return_value=rag_response
        ) as search_mock:
            service = AssistantChatService(config=config)
            result = service.generate_reply("hello")

        # -------------------------------------------------------------------------
        # 4) 호출 파라미터/응답 검증
        # -------------------------------------------------------------------------
        search_mock.assert_called_once_with("hello", index_name=["idx-user"], num_result_doc=5, timeout=30)
        self.assertTrue(result.is_dummy)
        self.assertEqual(
            result.contexts,
            [
                "[emailId: email-1 | title: 첫번째]\n컨텍스트1",
                "[emailId: email-2 | title: 두번째]\n컨텍스트2",
            ],
        )

    def test_generate_reply_passes_permission_group_override(self) -> None:
        """permission_groups 오버라이드가 전달되는지 확인합니다."""
        # -------------------------------------------------------------------------
        # 1) RAG 응답/설정 준비
        # -------------------------------------------------------------------------
        rag_response = {"hits": {"hits": []}}
        config = AssistantChatConfig(
            use_dummy=True,
            dummy_use_rag=True,
            rag_index_names=["idx-default"],
            rag_num_docs=5,
        )

        # -------------------------------------------------------------------------
        # 2) RAG 검색 patch 및 호출
        # -------------------------------------------------------------------------
        with patch("api.rag.services.RAG_SEARCH_URL", "http://rag/search"), patch(
            "api.rag.services.search_rag", return_value=rag_response
        ) as search_mock:
            service = AssistantChatService(config=config)
            result = service.generate_reply("hello", permission_groups=["group-a"])

        # -------------------------------------------------------------------------
        # 3) 호출 파라미터/응답 검증
        # -------------------------------------------------------------------------
        search_mock.assert_called_once_with(
            "hello",
            index_name=["idx-default"],
            num_result_doc=5,
            timeout=30,
            permission_groups=["group-a"],
        )
        self.assertEqual(result.sources, [])
        self.assertEqual(result.rag_response, rag_response)


class AssistantChatViewTests(TestCase):
    """AssistantChatView API 응답을 검증합니다."""

    def setUp(self) -> None:
        """테스트용 사용자/요청 팩토리를 준비합니다."""
        _allow_test_scope_access(self)
        self.factory = RequestFactory()
        User = get_user_model()
        self.user = User.objects.create_user(
            sabun="S77777",
            password="test-password",
            email="dummy.user@example.com",
        )
        self.user.knox_id = "knox-77777"
        self.user.save(update_fields=["knox_id"])
        _set_current_affiliation(self.user, user_sdwt_prod="group-a")

    def test_chat_view_returns_response_without_rag_url_attribute_error(self) -> None:
        """정상 요청 시 응답 페이로드가 생성되는지 확인합니다."""
        # -------------------------------------------------------------------------
        # 1) 요청 객체 구성
        # -------------------------------------------------------------------------
        request = self.factory.post(
            "/api/v1/assistant/chat",
            data=json.dumps({"prompt": "hello"}),
            content_type="application/json",
        )
        request.user = self.user

        # -------------------------------------------------------------------------
        # 2) 서비스 응답 patch 및 호출
        # -------------------------------------------------------------------------
        with patch(
            "api.assistant.views.assistant_chat_service.generate_reply",
            return_value=Mock(reply="안녕", contexts=[], sources=[], is_dummy=True),
        ):
            response = AssistantChatView().post(request)

        # -------------------------------------------------------------------------
        # 3) 응답 검증
        # -------------------------------------------------------------------------
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode("utf-8"))
        self.assertEqual(payload["reply"], "안녕")
        self.assertIn("meta", payload)

    def test_chat_view_returns_string_error_for_serializer_validation_failure(self) -> None:
        """serializer 검증 실패 시 문자열 error 계약을 유지하는지 확인합니다."""
        # -------------------------------------------------------------------------
        # 1) 빈 prompt 요청 구성
        # -------------------------------------------------------------------------
        request = self.factory.post(
            "/api/v1/assistant/chat",
            data=json.dumps({"prompt": "   "}),
            content_type="application/json",
        )
        request.user = self.user

        # -------------------------------------------------------------------------
        # 2) 뷰 호출 및 응답 검증
        # -------------------------------------------------------------------------
        response = AssistantChatView().post(request)
        self.assertEqual(response.status_code, 400)

        payload = json.loads(response.content.decode("utf-8"))
        self.assertEqual(payload["error"], "prompt is required")

    def test_chat_view_returns_503_when_assistant_config_error(self) -> None:
        """설정 오류 발생 시 503을 반환하는지 확인합니다."""
        # -------------------------------------------------------------------------
        # 1) 요청 객체 구성
        # -------------------------------------------------------------------------
        request = self.factory.post(
            "/api/v1/assistant/chat",
            data=json.dumps({"prompt": "hello"}),
            content_type="application/json",
        )
        request.user = self.user

        # -------------------------------------------------------------------------
        # 2) 서비스 오류 patch 및 호출
        # -------------------------------------------------------------------------
        with patch(
            "api.assistant.views.assistant_chat_service.generate_reply",
            side_effect=AssistantConfigError("missing config"),
        ):
            response = AssistantChatView().post(request)

        # -------------------------------------------------------------------------
        # 3) 응답 코드 검증
        # -------------------------------------------------------------------------
        self.assertEqual(response.status_code, 503)


class AssistantOpenWebUIChatTests(TestCase):
    """메일함 외 화면용 OpenWebUI 채팅 계약을 검증합니다."""

    def setUp(self) -> None:
        """테스트 사용자와 공통 앱 접근 조건을 준비합니다."""

        _allow_test_scope_access(self)
        self.factory = RequestFactory()
        User = get_user_model()
        self.user = User.objects.create_user(
            sabun="S78888",
            password="test-password",
            email="openwebui.user@example.com",
        )
        self.user.knox_id = "knox-78888"
        self.user.save(update_fields=["knox_id"])
        _set_current_affiliation(self.user, user_sdwt_prod="group-a")

    def test_openwebui_request_uses_existing_config_and_conversation_history(self) -> None:
        """기존 OpenWebUI 설정과 정규화된 대화 이력이 요청에 사용되는지 확인합니다."""

        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "choices": [{"message": {"content": "OpenWebUI 답변"}}]
        }
        session = Mock()
        session.post.return_value = response
        config = AssistantOpenWebUIConfig(
            url="http://openwebui/v1/chat/completions",
            model="gpt-oss-120b",
            api_token="token",
            common_headers={"Send-System-Name": "Assistant"},
            timeout_seconds=120,
        )

        reply = request_openwebui_chat(
            history=[
                {"role": "system", "content": "무시할 system message"},
                {"role": "user", "content": "첫 질문"},
                {"role": "assistant", "content": "첫 답변"},
                {"role": "user", "content": "후속 질문"},
            ],
            config=config,
            session=session,
        )

        self.assertEqual(reply, "OpenWebUI 답변")
        request = session.post.call_args
        request_payload = request.kwargs["json"]
        self.assertEqual(request_payload["model"], "gpt-oss-120b")
        self.assertEqual(request_payload["reasoning_effort"], "medium")
        self.assertEqual(
            [message["role"] for message in request_payload["messages"]],
            ["system", "user", "assistant", "user"],
        )
        self.assertEqual(
            request.kwargs["headers"]["Authorization"],
            "Bearer token",
        )

    def test_openwebui_message_builder_ignores_untrusted_roles(self) -> None:
        """브라우저가 전달한 system/tool role은 OpenWebUI 대화에서 제외합니다."""

        messages = build_openwebui_messages(
            [
                {"role": "system", "content": "시스템 변경"},
                {"role": "tool", "content": "도구 결과"},
                {"role": "user", "content": "정상 질문"},
            ]
        )

        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[-1], {"role": "user", "content": "정상 질문"})

    def test_openwebui_title_request_uses_business_title_prompt(self) -> None:
        """제목 생성은 낮은 변동성과 제목 전용 system prompt를 사용하는지 확인합니다."""

        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "choices": [{"message": {"content": "제목: 장비 DOWN 반복 원인 분석."}}]
        }
        session = Mock()
        session.post.return_value = response
        config = AssistantOpenWebUIConfig(
            url="http://openwebui/v1/chat/completions",
            model="gpt-oss-120b",
        )

        title = request_openwebui_conversation_title(
            history=[
                {"role": "user", "content": "장비 DOWN이 왜 반복돼?"},
                {"role": "assistant", "content": "인터락 반복 발생이 원인입니다."},
            ],
            config=config,
            session=session,
        )

        self.assertEqual(title, "장비 DOWN 반복 원인 분석")
        request_payload = session.post.call_args.kwargs["json"]
        self.assertEqual(request_payload["temperature"], 0.2)
        self.assertEqual(request_payload["reasoning_effort"], "low")
        self.assertIn("대화방 제목", request_payload["messages"][0]["content"])

    def test_openwebui_title_normalizer_removes_wrappers_and_limits_length(self) -> None:
        """모델이 붙인 접두어와 장식을 제거하고 40자 제한을 적용합니다."""

        normalized = normalize_openwebui_conversation_title(
            '**제목:** “EQP DOWN 및 IDLE 반복 발생 원인과 인터락 조치 방안 상세 분석 보고서 초안. 🚨”'
        )

        self.assertFalse(normalized.startswith("제목"))
        self.assertNotIn("“", normalized)
        self.assertNotIn("🚨", normalized)
        self.assertLessEqual(len(normalized), 40)

    def test_openwebui_view_returns_normalized_chat_payload(self) -> None:
        """OpenWebUI endpoint가 기존 ChatWidget 호환 응답을 반환하는지 확인합니다."""

        self.client.force_login(self.user)

        with patch(
            "api.assistant.views.request_openwebui_chat",
            return_value="일반 OpenWebUI 답변",
        ) as mocked_request:
            response = self.client.post(
                "/api/v1/assistant/openwebui-chat",
                data=json.dumps(
                    {
                        "prompt": "후속 질문",
                        "roomId": "room-1",
                        "history": [{"role": "user", "content": "후속 질문"}],
                    }
                ),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["reply"], "일반 OpenWebUI 답변")
        self.assertEqual(payload["sources"], [])
        self.assertEqual(payload["segments"], [])
        self.assertEqual(payload["meta"]["provider"], "openwebui")
        history = mocked_request.call_args.kwargs["history"]
        self.assertEqual(history[-1], {"role": "user", "content": "후속 질문"})

    def test_openwebui_stream_closes_upstream_connection(self) -> None:
        """OpenWebUI SSE 조각을 순서대로 반환하고 연결을 닫는지 확인합니다."""

        response = Mock()
        response.raise_for_status.return_value = None
        response.iter_lines.return_value = iter(
            [
                'data: {"choices":[{"delta":{"content":"첫 "}}]}',
                'data: {"choices":[{"delta":{"content":"답변"}}]}',
                "data: [DONE]",
            ]
        )
        session = Mock()
        session.post.return_value = response
        config = AssistantOpenWebUIConfig(
            url="http://openwebui/v1/chat/completions",
            model="gpt-oss-120b",
        )

        chunks = list(
            stream_openwebui_chat(
                history=[{"role": "user", "content": "질문"}],
                config=config,
                session=session,
            )
        )

        self.assertEqual(chunks, ["첫 ", "답변"])
        self.assertTrue(session.post.call_args.kwargs["json"]["stream"])
        self.assertTrue(session.post.call_args.kwargs["stream"])
        response.iter_lines.assert_called_once_with(
            chunk_size=1,
            decode_unicode=True,
        )
        response.close.assert_called_once_with()

    def test_openwebui_stream_rejects_eof_without_done_event(self) -> None:
        """일부 delta 뒤 완료 신호 없이 끊긴 upstream 응답을 실패로 처리합니다."""

        response = Mock()
        response.raise_for_status.return_value = None
        response.iter_lines.return_value = iter(
            ['data: {"choices":[{"delta":{"content":"일부 답변"}}]}']
        )
        session = Mock()
        session.post.return_value = response

        with self.assertRaisesRegex(assistant_services.AssistantRequestError, "완료 신호"):
            list(
                stream_openwebui_chat(
                    history=[{"role": "user", "content": "질문"}],
                    config=AssistantOpenWebUIConfig(
                        url="http://openwebui/v1/chat/completions",
                        model="gpt-oss-120b",
                    ),
                    session=session,
                )
            )

        response.close.assert_called_once_with()

    def test_openwebui_stream_view_emits_meta_delta_and_done_events(self) -> None:
        """브라우저 endpoint가 정해진 SSE event 순서와 buffering header를 반환합니다."""

        self.client.force_login(self.user)
        with patch(
            "api.assistant.views.stream_openwebui_chat",
            return_value=iter(["첫 ", "답변"]),
        ):
            response = self.client.post(
                "/api/v1/assistant/openwebui-chat/stream",
                data=json.dumps(
                    {
                        "prompt": "질문",
                        "roomId": "room-stream",
                        "history": [{"role": "user", "content": "질문"}],
                    }
                ),
                content_type="application/json",
            )
            body = b"".join(response.streaming_content).decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Accel-Buffering"], "no")
        self.assertIn("event: meta", body)
        self.assertIn('data: {"content":"첫 "}', body)
        self.assertIn('data: {"reply":"첫 답변"', body)
        self.assertLess(body.index("event: meta"), body.index("event: delta"))
        self.assertLess(body.index("event: delta"), body.index("event: done"))

    def test_openwebui_view_injects_owned_conversation_summary(self) -> None:
        """UUID 대화방의 저장 요약이 같은 소유자의 OpenWebUI 요청에만 전달됩니다."""

        self.client.force_login(self.user)
        conversation = AssistantConversation.objects.create(
            user=self.user,
            title="요약 테스트",
        )
        AssistantConversationSummary.objects.create(
            conversation=conversation,
            context_key="assistant:openwebui",
            summary="DOWN 반복 원인은 인터락입니다.",
            message_count=12,
        )
        with patch(
            "api.assistant.views.request_openwebui_chat",
            return_value="요약 기반 답변",
        ) as mocked_request:
            response = self.client.post(
                "/api/v1/assistant/openwebui-chat",
                data=json.dumps(
                    {
                        "prompt": "그 원인은?",
                        "roomId": str(conversation.id),
                        "contextKey": "assistant:openwebui",
                        "history": [{"role": "user", "content": "그 원인은?"}],
                    }
                ),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            mocked_request.call_args.kwargs["conversation_summary"],
            "DOWN 반복 원인은 인터락입니다.",
        )


class AssistantConversationPersistenceTests(TestCase):
    """사용자별 대화방과 메시지 영구 저장 API를 검증합니다."""

    def setUp(self) -> None:
        """소유권 검증에 사용할 두 사용자를 준비합니다."""

        _allow_test_scope_access(self)
        User = get_user_model()
        self.owner = User.objects.create_user(
            sabun="S71001",
            password="test-password",
        )
        self.other = User.objects.create_user(
            sabun="S71002",
            password="test-password",
        )
        self.owner.knox_id = "knox-71001"
        self.owner.save(update_fields=["knox_id"])
        self.other.knox_id = "knox-71002"
        self.other.save(update_fields=["knox_id"])

    def _create_conversation(self, *, name: str = "장비 문의") -> str:
        """현재 로그인 사용자의 대화방을 API로 만들고 UUID를 반환합니다."""

        response = self.client.post(
            "/api/v1/assistant/conversations",
            data=json.dumps({"name": name}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()["id"]

    def test_conversation_messages_are_persisted_idempotently(self) -> None:
        """메시지 저장 재시도가 중복 row를 만들지 않고 다시 조회되는지 확인합니다."""

        self.client.force_login(self.owner)
        conversation_id = self._create_conversation()
        request_payload = {
            "messages": [
                {
                    "clientId": "user-1",
                    "role": "user",
                    "content": "첫 질문",
                    "contextKey": "assistant:openwebui",
                },
                {
                    "clientId": "assistant-1",
                    "role": "assistant",
                    "content": "첫 답변",
                    "contextKey": "assistant:openwebui",
                    "sources": [],
                },
            ]
        }

        for _ in range(2):
            response = self.client.post(
                f"/api/v1/assistant/conversations/{conversation_id}/messages",
                data=json.dumps(request_payload),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 201, response.content)

        self.assertEqual(AssistantMessage.objects.count(), 2)
        response = self.client.get(
            f"/api/v1/assistant/conversations/{conversation_id}/messages"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [message["content"] for message in response.json()["results"]],
            ["첫 질문", "첫 답변"],
        )

    def test_other_user_cannot_read_append_or_delete_conversation(self) -> None:
        """다른 사용자는 UUID를 알아도 대화방에 접근할 수 없는지 확인합니다."""

        self.client.force_login(self.owner)
        conversation_id = self._create_conversation()
        self.client.force_login(self.other)

        list_response = self.client.get("/api/v1/assistant/conversations")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()["results"], [])

        messages_url = (
            f"/api/v1/assistant/conversations/{conversation_id}/messages"
        )
        self.assertEqual(self.client.get(messages_url).status_code, 404)
        self.assertEqual(
            self.client.post(
                messages_url,
                data=json.dumps(
                    {
                        "messages": [
                            {
                                "clientId": "other-user",
                                "role": "user",
                                "content": "침범 시도",
                            }
                        ]
                    }
                ),
                content_type="application/json",
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.delete(
                f"/api/v1/assistant/conversations/{conversation_id}"
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                f"/api/v1/assistant/conversations/{conversation_id}/generate-title"
            ).status_code,
            404,
        )
        self.assertTrue(AssistantConversation.objects.filter(id=conversation_id).exists())

    def test_openwebui_title_is_saved_for_default_conversation(self) -> None:
        """저장된 첫 질문과 답변으로 생성한 제목이 대화방에 반영되는지 확인합니다."""

        self.client.force_login(self.owner)
        conversation_id = self._create_conversation(name="새 대화")
        conversation = AssistantConversation.objects.get(id=conversation_id)
        assistant_services.append_assistant_messages(
            conversation=conversation,
            messages=[
                {
                    "client_id": "user-title",
                    "role": "user",
                    "content": "EQP DOWN이 반복되는 원인은?",
                    "context_key": "assistant:openwebui",
                },
                {
                    "client_id": "assistant-title",
                    "role": "assistant",
                    "content": "인터락 반복 발생이 주요 원인입니다.",
                    "context_key": "assistant:openwebui",
                },
            ],
        )

        with patch(
            "api.assistant.services.conversations.request_openwebui_conversation_title",
            return_value="EQP DOWN 반복 원인 분석",
        ) as mocked_title_request:
            response = self.client.post(
                f"/api/v1/assistant/conversations/{conversation_id}/generate-title"
            )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["name"], "EQP DOWN 반복 원인 분석")
        conversation.refresh_from_db()
        self.assertEqual(conversation.title, "EQP DOWN 반복 원인 분석")
        history = mocked_title_request.call_args.kwargs["history"]
        self.assertEqual([entry["role"] for entry in history], ["user", "assistant"])

    def test_title_generation_requires_saved_question_and_answer(self) -> None:
        """질문이나 답변이 부족하면 OpenWebUI를 호출하지 않고 409를 반환합니다."""

        self.client.force_login(self.owner)
        conversation_id = self._create_conversation(name="새 대화")

        with patch(
            "api.assistant.services.conversations.request_openwebui_conversation_title"
        ) as mocked_title_request:
            response = self.client.post(
                f"/api/v1/assistant/conversations/{conversation_id}/generate-title"
            )

        self.assertEqual(response.status_code, 409)
        mocked_title_request.assert_not_called()

    def test_title_generation_does_not_recreate_deleted_conversation(self) -> None:
        """OpenWebUI 응답 대기 중 삭제된 방을 제목 저장이 다시 만들지 않습니다."""

        self.client.force_login(self.owner)
        conversation_id = self._create_conversation(name="새 대화")
        conversation = AssistantConversation.objects.get(id=conversation_id)
        assistant_services.append_assistant_messages(
            conversation=conversation,
            messages=[
                {
                    "client_id": "user-race",
                    "role": "user",
                    "content": "DOWN 원인은?",
                },
                {
                    "client_id": "assistant-race",
                    "role": "assistant",
                    "content": "인터락입니다.",
                },
            ],
        )

        def delete_conversation_while_generating(**kwargs: object) -> str:
            AssistantConversation.objects.filter(id=conversation_id).delete()
            return "EQP DOWN 원인 분석"

        with patch(
            "api.assistant.services.conversations.request_openwebui_conversation_title",
            side_effect=delete_conversation_while_generating,
        ):
            response = self.client.post(
                f"/api/v1/assistant/conversations/{conversation_id}/generate-title"
            )

        self.assertEqual(response.status_code, 409)
        self.assertFalse(AssistantConversation.objects.filter(id=conversation_id).exists())

    def test_message_list_returns_latest_twenty_and_delete_cascades(self) -> None:
        """기본 조회 상한과 대화방 삭제의 message cascade를 검증합니다."""

        self.client.force_login(self.owner)
        conversation_id = self._create_conversation()
        conversation = AssistantConversation.objects.get(id=conversation_id)
        assistant_services.append_assistant_messages(
            conversation=conversation,
            messages=[
                {
                    "client_id": f"user-{index}",
                    "role": "user",
                    "content": f"질문 {index}",
                    "context_key": "assistant:openwebui",
                }
                for index in range(25)
            ],
        )

        response = self.client.get(
            f"/api/v1/assistant/conversations/{conversation_id}/messages"
        )
        self.assertEqual(response.status_code, 200)
        results = response.json()["results"]
        self.assertEqual(len(results), 20)
        self.assertEqual(results[0]["content"], "질문 5")
        self.assertEqual(results[-1]["content"], "질문 24")
        self.assertTrue(response.json()["hasMore"])

        older_response = self.client.get(
            f"/api/v1/assistant/conversations/{conversation_id}/messages",
            {"before": response.json()["nextCursor"]},
        )
        self.assertEqual(older_response.status_code, 200)
        self.assertEqual(
            [message["content"] for message in older_response.json()["results"]],
            [f"질문 {index}" for index in range(5)],
        )
        self.assertFalse(older_response.json()["hasMore"])

        response = self.client.delete(
            f"/api/v1/assistant/conversations/{conversation_id}/messages"
        )
        self.assertEqual(response.status_code, 204)
        self.assertTrue(AssistantConversation.objects.filter(id=conversation_id).exists())
        self.assertEqual(AssistantMessage.objects.count(), 0)
        assistant_services.append_assistant_messages(
            conversation=conversation,
            messages=[
                {
                    "client_id": "user-after-reset",
                    "role": "user",
                    "content": "초기화 후 질문",
                    "context_key": "assistant:openwebui",
                }
            ],
        )

        response = self.client.delete(
            f"/api/v1/assistant/conversations/{conversation_id}"
        )
        self.assertEqual(response.status_code, 204)
        self.assertFalse(AssistantConversation.objects.filter(id=conversation_id).exists())
        self.assertEqual(AssistantMessage.objects.count(), 0)

    def test_conversation_list_supports_search_and_cursor_pagination(self) -> None:
        """검색 조건을 유지한 signed cursor로 다음 대화방 page를 조회합니다."""

        self.client.force_login(self.owner)
        first_id = self._create_conversation(name="EQP DOWN 분석 A")
        second_id = self._create_conversation(name="EQP DOWN 분석 B")
        self._create_conversation(name="TIP 상태 분석")

        first_response = self.client.get(
            "/api/v1/assistant/conversations",
            {"search": "DOWN", "limit": 1},
        )
        self.assertEqual(first_response.status_code, 200)
        self.assertTrue(first_response.json()["hasMore"])
        self.assertEqual(len(first_response.json()["results"]), 1)

        second_response = self.client.get(
            "/api/v1/assistant/conversations",
            {
                "search": "DOWN",
                "limit": 1,
                "cursor": first_response.json()["nextCursor"],
            },
        )
        self.assertEqual(second_response.status_code, 200)
        self.assertFalse(second_response.json()["hasMore"])
        returned_ids = {
            first_response.json()["results"][0]["id"],
            second_response.json()["results"][0]["id"],
        }
        self.assertEqual(returned_ids, {first_id, second_id})

        mismatched_response = self.client.get(
            "/api/v1/assistant/conversations",
            {
                "search": "TIP",
                "cursor": first_response.json()["nextCursor"],
            },
        )
        self.assertEqual(mismatched_response.status_code, 400)

    def test_conversation_list_keeps_pinned_rooms_first_across_pages(self) -> None:
        """오래된 고정 대화방도 첫 page에서 누락되지 않고 중복 없이 조회됩니다."""

        self.client.force_login(self.owner)
        pinned_id = self._create_conversation(name="오래된 고정 대화")
        pin_response = self.client.patch(
            f"/api/v1/assistant/conversations/{pinned_id}",
            data=json.dumps({"pinned": True}),
            content_type="application/json",
        )
        self.assertEqual(pin_response.status_code, 200, pin_response.content)
        recent_ids = {
            self._create_conversation(name="최근 대화 A"),
            self._create_conversation(name="최근 대화 B"),
        }

        returned_ids: list[str] = []
        cursor = None
        while True:
            query = {"limit": 1}
            if cursor:
                query["cursor"] = cursor
            response = self.client.get(
                "/api/v1/assistant/conversations",
                query,
            )
            self.assertEqual(response.status_code, 200, response.content)
            returned_ids.extend(item["id"] for item in response.json()["results"])
            if not response.json()["hasMore"]:
                break
            cursor = response.json()["nextCursor"]

        self.assertEqual(returned_ids[0], pinned_id)
        self.assertEqual(set(returned_ids), {pinned_id, *recent_ids})
        self.assertEqual(len(returned_ids), 3)

    def test_summary_refresh_rolls_up_old_messages_and_clear_resets_memory(self) -> None:
        """오래된 메시지만 요약하고 메시지 초기화 시 장기 기억도 제거합니다."""

        self.client.force_login(self.owner)
        conversation_id = self._create_conversation()
        conversation = AssistantConversation.objects.get(id=conversation_id)
        assistant_services.append_assistant_messages(
            conversation=conversation,
            messages=[
                {
                    "client_id": f"summary-{index}",
                    "role": "user" if index % 2 == 0 else "assistant",
                    "content": f"대화 {index}",
                    "context_key": "assistant:openwebui",
                }
                for index in range(25)
            ],
        )

        with patch(
            "api.assistant.services.conversations.request_openwebui_conversation_summary",
            return_value="DOWN 원인과 조치가 합의되었습니다.",
        ) as mocked_summary:
            response = self.client.post(
                f"/api/v1/assistant/conversations/{conversation_id}/refresh-summary",
                data=json.dumps({"contextKey": "assistant:openwebui"}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["updated"])
        self.assertEqual(response.json()["coveredMessageCount"], 15)
        summary = AssistantConversationSummary.objects.get(
            conversation=conversation,
            context_key="assistant:openwebui",
        )
        self.assertEqual(summary.message_count, 15)
        self.assertEqual(summary.summary, "DOWN 원인과 조치가 합의되었습니다.")
        self.assertEqual(len(mocked_summary.call_args.kwargs["messages"]), 15)

        clear_response = self.client.delete(
            f"/api/v1/assistant/conversations/{conversation_id}/messages"
        )
        self.assertEqual(clear_response.status_code, 204)
        self.assertFalse(
            AssistantConversationSummary.objects.filter(
                conversation=conversation,
            ).exists()
        )

    def test_summary_refresh_does_not_mix_message_contexts(self) -> None:
        """rolling summary는 요청 contextKey와 다른 화면의 메시지를 포함하지 않습니다."""

        self.client.force_login(self.owner)
        conversation_id = self._create_conversation()
        conversation = AssistantConversation.objects.get(id=conversation_id)
        messages = []
        for index in range(24):
            messages.extend(
                [
                    {
                        "client_id": f"general-{index}",
                        "role": "user",
                        "content": f"일반 대화 {index}",
                        "context_key": "assistant:openwebui",
                    },
                    {
                        "client_id": f"observer-{index}",
                        "role": "assistant",
                        "content": f"Observer 분석 {index}",
                        "context_key": "observer:scope-a",
                    },
                ]
            )
        assistant_services.append_assistant_messages(
            conversation=conversation,
            messages=messages,
        )

        with patch(
            "api.assistant.services.conversations.request_openwebui_conversation_summary",
            return_value="일반 대화 요약",
        ) as mocked_summary:
            response = self.client.post(
                f"/api/v1/assistant/conversations/{conversation_id}/refresh-summary",
                data=json.dumps({"contextKey": "assistant:openwebui"}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200, response.content)
        summarized_contents = [
            message["content"]
            for message in mocked_summary.call_args.kwargs["messages"]
        ]
        self.assertTrue(all(content.startswith("일반 대화") for content in summarized_contents))

        with patch(
            "api.assistant.services.conversations.request_openwebui_conversation_summary",
            return_value="Observer 대화 요약",
        ):
            observer_response = self.client.post(
                f"/api/v1/assistant/conversations/{conversation_id}/refresh-summary",
                data=json.dumps({"contextKey": "observer:scope-a"}),
                content_type="application/json",
            )

        self.assertEqual(observer_response.status_code, 200, observer_response.content)
        summaries = AssistantConversationSummary.objects.filter(
            conversation=conversation,
        )
        self.assertEqual(summaries.count(), 2)
        self.assertEqual(
            summaries.get(context_key="assistant:openwebui").summary,
            "일반 대화 요약",
        )
        self.assertEqual(
            summaries.get(context_key="observer:scope-a").summary,
            "Observer 대화 요약",
        )

    def test_generation_lease_blocks_other_tabs_until_finalized(self) -> None:
        """사용자 단위 generation lease가 다중 탭의 중복 생성을 차단합니다."""

        self.client.force_login(self.owner)
        first_conversation_id = self._create_conversation(name="첫 대화")
        second_conversation_id = self._create_conversation(name="두 번째 대화")
        first_response = self.client.post(
            "/api/v1/assistant/generations",
            data=json.dumps(
                {
                    "conversationId": first_conversation_id,
                    "clientRequestId": "request-first",
                    "contextKey": "assistant:openwebui",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(first_response.status_code, 201, first_response.content)

        blocked_response = self.client.post(
            "/api/v1/assistant/generations",
            data=json.dumps(
                {
                    "conversationId": second_conversation_id,
                    "clientRequestId": "request-second",
                    "contextKey": "assistant:openwebui",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(blocked_response.status_code, 409)
        self.assertEqual(
            blocked_response.json()["generation"]["conversationId"],
            first_conversation_id,
        )

        generation_id = first_response.json()["id"]
        finalize_response = self.client.patch(
            f"/api/v1/assistant/generations/{generation_id}",
            data=json.dumps({"status": "completed"}),
            content_type="application/json",
        )
        self.assertEqual(finalize_response.status_code, 200)
        self.assertEqual(finalize_response.json()["status"], "completed")
        self.assertEqual(AssistantGeneration.objects.count(), 1)

    def test_expired_generation_is_not_active_or_reusable(self) -> None:
        """만료된 generation은 활성 조회에서 숨기고 같은 요청 ID 재사용을 거절합니다."""

        self.client.force_login(self.owner)
        conversation_id = self._create_conversation()
        conversation = AssistantConversation.objects.get(id=conversation_id)
        AssistantGeneration.objects.create(
            user=self.owner,
            conversation=conversation,
            client_request_id="expired-request",
            context_key="assistant:openwebui",
            status=AssistantGeneration.Status.STREAMING,
            expires_at=timezone.now() - timedelta(seconds=1),
        )

        active_response = self.client.get("/api/v1/assistant/generations")
        self.assertEqual(active_response.status_code, 200)
        self.assertIsNone(active_response.json()["generation"])

        reused_response = self.client.post(
            "/api/v1/assistant/generations",
            data=json.dumps(
                {
                    "conversationId": conversation_id,
                    "clientRequestId": "expired-request",
                    "contextKey": "assistant:openwebui",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(reused_response.status_code, 409)
        self.assertIn("새 요청 ID", reused_response.json()["error"])

    def test_generation_request_id_cannot_change_its_contract(self) -> None:
        """활성 generation도 같은 요청 ID로 대화방이나 문맥을 바꿀 수 없습니다."""

        self.client.force_login(self.owner)
        first_conversation_id = self._create_conversation(name="첫 대화")
        second_conversation_id = self._create_conversation(name="두 번째 대화")
        first_response = self.client.post(
            "/api/v1/assistant/generations",
            data=json.dumps(
                {
                    "conversationId": first_conversation_id,
                    "clientRequestId": "same-request",
                    "contextKey": "assistant:openwebui",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(first_response.status_code, 201)

        mismatched_response = self.client.post(
            "/api/v1/assistant/generations",
            data=json.dumps(
                {
                    "conversationId": second_conversation_id,
                    "clientRequestId": "same-request",
                    "contextKey": "observer:scope-a",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(mismatched_response.status_code, 409)
        self.assertIn("다른 생성 조건", mismatched_response.json()["error"])

    def test_assistant_message_save_completes_generation_in_same_request(self) -> None:
        """Assistant 답변 저장 성공 시 별도 finalize 요청 없이 lease를 종료합니다."""

        self.client.force_login(self.owner)
        first_conversation_id = self._create_conversation(name="첫 대화")
        second_conversation_id = self._create_conversation(name="두 번째 대화")
        generation_response = self.client.post(
            "/api/v1/assistant/generations",
            data=json.dumps(
                {
                    "conversationId": first_conversation_id,
                    "clientRequestId": "atomic-completion-first",
                    "contextKey": "assistant:openwebui",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(generation_response.status_code, 201, generation_response.content)
        generation_id = generation_response.json()["id"]

        message_response = self.client.post(
            f"/api/v1/assistant/conversations/{first_conversation_id}/messages",
            data=json.dumps(
                {
                    "messages": [
                        {
                            "clientId": "atomic-assistant-answer",
                            "role": "assistant",
                            "content": "저장이 완료되었습니다.",
                            "contextKey": "assistant:openwebui",
                            "generationId": generation_id,
                        }
                    ]
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(message_response.status_code, 201, message_response.content)
        generation = AssistantGeneration.objects.get(id=generation_id)
        self.assertEqual(generation.status, AssistantGeneration.Status.COMPLETED)
        self.assertIsNotNone(generation.finished_at)

        next_generation_response = self.client.post(
            "/api/v1/assistant/generations",
            data=json.dumps(
                {
                    "conversationId": second_conversation_id,
                    "clientRequestId": "atomic-completion-second",
                    "contextKey": "assistant:openwebui",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(
            next_generation_response.status_code,
            201,
            next_generation_response.content,
        )

    def test_message_edit_creates_new_current_branch_without_deleting_original(self) -> None:
        """질문 수정 시 원본 분기를 보존하고 새 분기만 조회합니다."""

        self.client.force_login(self.owner)
        conversation_id = self._create_conversation()
        messages_url = f"/api/v1/assistant/conversations/{conversation_id}/messages"
        original_response = self.client.post(
            messages_url,
            data=json.dumps(
                {
                    "messages": [
                        {"clientId": "user-original", "role": "user", "content": "원본 질문"},
                        {
                            "clientId": "assistant-original",
                            "role": "assistant",
                            "content": "원본 답변",
                            "parentId": "user-original",
                        },
                    ]
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(original_response.status_code, 201, original_response.content)
        conversation = AssistantConversation.objects.get(id=conversation_id)
        AssistantConversationSummary.objects.create(
            conversation=conversation,
            context_key="assistant:openwebui",
            summary="원본 분기 요약",
            message_count=2,
        )

        branch_response = self.client.post(
            messages_url,
            data=json.dumps(
                {
                    "messages": [
                        {
                            "clientId": "user-edited",
                            "role": "user",
                            "content": "수정 질문",
                            "parentId": None,
                            "revisionOfId": "user-original",
                        },
                        {
                            "clientId": "assistant-edited",
                            "role": "assistant",
                            "content": "수정 답변",
                            "parentId": "user-edited",
                        },
                    ]
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(branch_response.status_code, 201, branch_response.content)

        list_response = self.client.get(messages_url)
        self.assertEqual(
            [message["content"] for message in list_response.json()["results"]],
            ["수정 질문", "수정 답변"],
        )
        self.assertEqual(AssistantMessage.objects.count(), 4)
        edited = AssistantMessage.objects.get(client_id="user-edited")
        self.assertEqual(edited.revision_of.client_id, "user-original")
        self.assertFalse(
            AssistantConversationSummary.objects.filter(
                conversation=conversation,
            ).exists()
        )

        summary = AssistantConversationSummary.objects.create(
            conversation=conversation,
            context_key="assistant:openwebui",
            summary="수정 분기 요약",
            message_count=2,
        )
        replay_response = self.client.post(
            messages_url,
            data=json.dumps(
                {
                    "messages": [
                        {
                            "clientId": "user-edited",
                            "role": "user",
                            "content": "수정 질문",
                            "parentId": None,
                            "revisionOfId": "user-original",
                        },
                        {
                            "clientId": "assistant-edited",
                            "role": "assistant",
                            "content": "수정 답변",
                            "parentId": "user-edited",
                        },
                    ]
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(replay_response.status_code, 201, replay_response.content)
        summary.refresh_from_db()
        self.assertEqual(summary.summary, "수정 분기 요약")

    def test_conversation_metadata_archive_and_message_search(self) -> None:
        """이름·고정·보관 갱신과 메시지 본문 검색을 함께 지원합니다."""

        self.client.force_login(self.owner)
        conversation_id = self._create_conversation(name="초기 이름")
        conversation = AssistantConversation.objects.get(id=conversation_id)
        assistant_services.append_assistant_messages(
            conversation=conversation,
            messages=[
                {
                    "client_id": "search-user",
                    "role": "user",
                    "content": "LOCAL 반복 원인을 찾아줘",
                }
            ],
        )
        search_response = self.client.get(
            "/api/v1/assistant/conversations",
            {"search": "LOCAL 반복"},
        )
        self.assertEqual(search_response.status_code, 200)
        self.assertEqual(search_response.json()["results"][0]["id"], conversation_id)

        patch_response = self.client.patch(
            f"/api/v1/assistant/conversations/{conversation_id}",
            data=json.dumps(
                {"name": "LOCAL 반복 원인", "pinned": True, "archived": True}
            ),
            content_type="application/json",
        )
        self.assertEqual(patch_response.status_code, 200, patch_response.content)
        self.assertTrue(patch_response.json()["pinned"])
        self.assertTrue(patch_response.json()["archived"])
        active_response = self.client.get("/api/v1/assistant/conversations")
        self.assertEqual(active_response.json()["results"], [])
        archived_response = self.client.get(
            "/api/v1/assistant/conversations",
            {"archived": "true"},
        )
        self.assertEqual(archived_response.json()["results"][0]["id"], conversation_id)

    def test_observer_snapshot_feedback_and_exports_are_persisted(self) -> None:
        """분석 근거 snapshot·평가·현재 분기 내보내기를 검증합니다."""

        self.client.force_login(self.owner)
        conversation_id = self._create_conversation(name="=Observer 분석")
        messages_url = f"/api/v1/assistant/conversations/{conversation_id}/messages"
        response = self.client.post(
            messages_url,
            data=json.dumps(
                {
                    "messages": [
                        {"clientId": "observer-user", "role": "user", "content": "종합 분석"},
                        {
                            "clientId": "observer-answer",
                            "role": "assistant",
                            "content": "=HYPERLINK(\"https://invalid.test\") DOWN 반복 원인은 인터락입니다.",
                            "parentId": "observer-user",
                            "contextKey": "observer:scope-a",
                            "contextSnapshot": {
                                "kind": "observer",
                                "scope": {"eqpId": "EQP-01"},
                                "coverage": {"eqpTargetCount": 12},
                                "evidence": [
                                    {"target": "DOWN", "evidenceIds": ["log-1", "log-2"]}
                                ],
                            },
                        },
                    ]
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(AssistantContextSnapshot.objects.count(), 1)
        self.assertEqual(
            response.json()["results"][1]["contextSnapshot"]["scope"]["eqpId"],
            "EQP-01",
        )

        feedback_url = (
            f"/api/v1/assistant/conversations/{conversation_id}/messages/"
            "observer-answer/feedback"
        )
        feedback_response = self.client.put(
            feedback_url,
            data=json.dumps({"rating": "up"}),
            content_type="application/json",
        )
        self.assertEqual(feedback_response.status_code, 200)
        self.assertEqual(AssistantMessageFeedback.objects.count(), 1)

        markdown_response = self.client.get(
            f"/api/v1/assistant/conversations/{conversation_id}/export",
            {"exportFormat": "markdown"},
        )
        self.assertEqual(markdown_response.status_code, 200, markdown_response.content)
        self.assertIn("DOWN 반복 원인", markdown_response.content.decode("utf-8"))
        csv_response = self.client.get(
            f"/api/v1/assistant/conversations/{conversation_id}/export",
            {"exportFormat": "csv"},
        )
        self.assertEqual(csv_response.status_code, 200)
        self.assertTrue(csv_response.content.startswith(b"\xef\xbb\xbf"))
        csv_rows = list(
            csv.reader(StringIO(csv_response.content.decode("utf-8-sig")))
        )
        self.assertEqual(csv_rows[0][1], "'=Observer 분석")
        self.assertTrue(csv_rows[3][2].startswith("'=HYPERLINK"))

        delete_feedback_response = self.client.delete(feedback_url)
        self.assertEqual(delete_feedback_response.status_code, 204)
        self.assertEqual(AssistantMessageFeedback.objects.count(), 0)


class AssistantNormalizationTests(TestCase):
    """정규화 유틸 동작을 검증합니다."""

    def test_normalize_room_id_defaults_to_default(self) -> None:
        """room_id가 비면 기본값으로 대체되는지 확인합니다."""
        self.assertEqual(assistant_services.normalize_room_id(None), "default")
        self.assertEqual(assistant_services.normalize_room_id(""), "default")

    def test_assistant_request_size_limits_reject_oversized_payloads(self) -> None:
        """채팅과 메시지 저장 요청의 권장 상한을 초과하면 검증에서 거부합니다."""

        chat_serializer = AssistantChatRequestSerializer(
            data={"prompt": "가" * 10_001}
        )
        self.assertFalse(chat_serializer.is_valid())
        self.assertIn("prompt", chat_serializer.errors)

        oversized_history = AssistantChatRequestSerializer(
            data={
                "prompt": "질문",
                "history": [
                    {"role": "user", "content": f"이전 질문 {index}"}
                    for index in range(21)
                ],
            }
        )
        self.assertFalse(oversized_history.is_valid())
        self.assertIn("history", oversized_history.errors)

        oversized_history_content = AssistantChatRequestSerializer(
            data={
                "prompt": "질문",
                "history": [{"role": "assistant", "content": "가" * 10_001}],
            }
        )
        self.assertFalse(oversized_history_content.is_valid())
        self.assertIn("history", oversized_history_content.errors)

        base_message = {
            "clientId": "limit-message",
            "role": "assistant",
            "content": "정상 답변",
        }
        oversized_batch = AssistantMessageBatchSerializer(
            data={
                "messages": [
                    {**base_message, "clientId": f"limit-message-{index}"}
                    for index in range(21)
                ]
            }
        )
        self.assertFalse(oversized_batch.is_valid())

        oversized_content = AssistantMessageBatchSerializer(
            data={"messages": [{**base_message, "content": "가" * 10_001}]}
        )
        self.assertFalse(oversized_content.is_valid())

        too_many_sources = AssistantMessageBatchSerializer(
            data={"messages": [{**base_message, "sources": [{}] * 51}]}
        )
        self.assertFalse(too_many_sources.is_valid())

        oversized_sources = AssistantMessageBatchSerializer(
            data={
                "messages": [
                    {**base_message, "sources": [{"snippet": "가" * 20_000}]}
                ]
            }
        )
        self.assertFalse(oversized_sources.is_valid())

        oversized_snapshot = AssistantMessageBatchSerializer(
            data={
                "messages": [
                    {
                        **base_message,
                        "contextSnapshot": {"evidence": ["가" * 40_000]},
                    }
                ]
            }
        )
        self.assertFalse(oversized_snapshot.is_valid())

    def test_normalize_room_id_sanitizes(self) -> None:
        """room_id가 허용 문자로 정규화되는지 확인합니다."""
        self.assertEqual(assistant_services.normalize_room_id(" room$% "), "room--")

    def test_normalize_history_keeps_latest(self) -> None:
        """normalize_history가 최신 N개를 유지하는지 확인합니다."""
        history = [
            {"role": "user", "content": "첫번째"},
            {"role": "assistant", "content": "두번째"},
            {"role": "user", "content": "세번째"},
        ]

        normalized = assistant_services.normalize_history(history, limit=2)

        self.assertEqual(len(normalized), 2)
        self.assertEqual([entry["content"] for entry in normalized], ["두번째", "세번째"])

    def test_normalize_sources_dedupes(self) -> None:
        """normalize_sources가 doc_id 기준으로 중복 제거하는지 확인합니다."""
        sources = [
            {"doc_id": "DOC1", "title": "T1", "snippet": "S1"},
            {"docId": "DOC1", "title": "T1b", "snippet": "S1b"},
            {"doc_id": "DOC2", "title": "T2", "snippet": "S2"},
        ]
        normalized = assistant_services.normalize_sources(sources)
        self.assertEqual(len(normalized), 2)
        self.assertEqual({item["docId"] for item in normalized}, {"DOC1", "DOC2"})
