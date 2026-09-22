from . import *  # noqa: F403


class AssistantChatServiceSourceFilteringTests(TestCase):
    """LLM 응답/출처 필터링 동작을 검증합니다."""

    def test_generate_llm_payload_sets_temperature_zero_when_background_knowledge_exists(self) -> None:
        """배경지식이 있으면 temperature가 0으로 설정되는지 확인합니다."""
        service = AssistantChatService(
            config=AssistantChatConfig(
                use_dummy=False,
                temperature=0.7,
            )
        )

        payload_with_context = service._generate_llm_payload("질문입니다", ["context"], email_ids=["E1"])
        self.assertEqual(payload_with_context.get("temperature"), 0.0)
        messages = payload_with_context.get("messages")
        self.assertEqual([entry.get("role") for entry in messages], ["system", "system", "system", "user"])
        constraints = messages[2].get("content", "")
        self.assertIn("segments가 비면 비어 있지 않은 통합 답변", constraints)
        self.assertIn('segments가 1개 이상이면', constraints)
        self.assertIn('빈 문자열("")', constraints)

        payload_without_context = service._generate_llm_payload("질문입니다", [], email_ids=["E1"])
        self.assertEqual(payload_without_context.get("temperature"), 0.7)

    def test_generate_reply_builds_segments_and_filters_sources(self) -> None:
        """segments 기반 출처 필터링이 올바른지 확인합니다."""
        service = AssistantChatService(
            config=AssistantChatConfig(use_dummy=False)
        )

        contexts = ["[emailId: E1]\ncontext 1", "[emailId: E2]\ncontext 2"]
        sources = [
            {"doc_id": "E1", "title": "메일 1", "snippet": "내용 1"},
            {"doc_id": "E2", "title": "메일 2", "snippet": "내용 2"},
        ]

        with patch.object(service, "_retrieve_documents", return_value=(contexts, {"hits": {}}, sources)):
            with patch(
                "api.assistant.services.chat.stream_llm_reply",
                return_value=json.dumps(
                    {
                        "answer": "통합 답변입니다",
                        "segments": [
                            {"answer": "메일 2 기반 답변", "usedEmailIds": ["E2"]},
                            {"answer": "메일 1+2 기반 답변", "usedEmailIds": ["E1", "E2", "E3"]},
                        ],
                    },
                    ensure_ascii=False,
                ),
            ):
                result = service.generate_reply_stream(
                    "질문입니다",
                    cancellation=ExternalCallCancellation(),
                )

        self.assertEqual(result.reply, "통합 답변입니다")
        self.assertEqual(len(result.segments), 2)
        self.assertEqual(result.segments[0]["reply"], "메일 2 기반 답변")
        self.assertEqual([entry["doc_id"] for entry in result.segments[0]["sources"]], ["E2"])
        self.assertEqual(result.segments[1]["reply"], "메일 1+2 기반 답변")
        self.assertEqual([entry["doc_id"] for entry in result.segments[1]["sources"]], ["E1", "E2"])
        self.assertEqual([entry["doc_id"] for entry in result.sources], ["E1", "E2"])

    def test_generate_reply_uses_segments_when_top_level_answer_is_unusable(self) -> None:
        """OpenWebUI의 최상위 answer를 쓸 수 없어도 유효한 segments를 처리합니다."""

        service = AssistantChatService(config=AssistantChatConfig(use_dummy=False))
        contexts = ["[emailId: E1]\n메일 배경지식"]
        sources = [{"doc_id": "E1", "title": "메일 1", "snippet": "메일 배경지식"}]
        raw_replies = (
            '{"answer":"","segments":[{"answer":"메일 기반 답변","usedEmailIds":["E1"]}]}',
            '{"answer":null,"segments":[{"answer":"메일 기반 답변","usedEmailIds":["E1"]}]}',
            '{"answer":[],"segments":[{"answer":"메일 기반 답변","usedEmailIds":["E1"]}]}',
            '{"segments":[{"answer":"메일 기반 답변","usedEmailIds":["E1"]}]}',
        )

        for raw_reply in raw_replies:
            with self.subTest(raw_reply=raw_reply), patch.object(
                service,
                "_retrieve_documents",
                return_value=(contexts, {"hits": {}}, sources),
            ), patch(
                "api.assistant.services.chat.stream_llm_reply",
                return_value=raw_reply,
            ):
                result = service.generate_reply_stream(
                    "질문입니다",
                    cancellation=ExternalCallCancellation(),
                )

            self.assertEqual(result.reply, "")
            self.assertEqual(result.segments[0]["reply"], "메일 기반 답변")
            self.assertEqual([source["doc_id"] for source in result.sources], ["E1"])

    def test_generate_reply_rejects_empty_answer_without_segments(self) -> None:
        """출처 segment와 통합 answer가 모두 빈 응답은 거부합니다."""

        service = AssistantChatService(config=AssistantChatConfig(use_dummy=False))
        with patch.object(
            service,
            "_retrieve_documents",
            return_value=(
                ["[emailId: E1]\n메일 내용"],
                {"hits": {}},
                [{"doc_id": "E1", "title": "메일 제목"}],
            ),
        ), patch(
            "api.assistant.services.chat.stream_llm_reply",
            return_value='{"answer":"","segments":[]}',
        ):
            with self.assertRaisesMessage(ValueError, "answer가 비어 있습니다"):
                service.generate_reply_stream(
                    "질문입니다",
                    cancellation=ExternalCallCancellation(),
                )

    def test_generate_reply_rejects_non_string_answer_without_segments(self) -> None:
        """출처 segment가 없으면 통합 answer는 문자열이어야 합니다."""

        service = AssistantChatService(config=AssistantChatConfig(use_dummy=False))
        with patch.object(
            service,
            "_retrieve_documents",
            return_value=(
                ["[emailId: E1]\n메일 내용"],
                {"hits": {}},
                [{"doc_id": "E1", "title": "메일 제목"}],
            ),
        ), patch(
            "api.assistant.services.chat.stream_llm_reply",
            return_value='{"answer":[],"segments":[]}',
        ):
            with self.assertRaisesMessage(ValueError, "answer 형식이 올바르지 않습니다"):
                service.generate_reply_stream(
                    "질문입니다",
                    cancellation=ExternalCallCancellation(),
                )

    @override_settings(
        OPENWEBUI_URL="http://openwebui/v1/chat/completions",
        OPENWEBUI_MODEL="openwebui-email-model",
        OPENWEBUI_API_TOKEN="email-token",
        OPENWEBUI_COMMON_HEADERS='{"X-Provider":"OpenWebUI"}',
        OPENWEBUI_TIMEOUT_SECONDS=77,
        ASSISTANT_LLM_URL="http://legacy-assistant/v1/chat/completions",
        ASSISTANT_LLM_MODEL="legacy-assistant-model",
    )
    def test_generate_reply_uses_openwebui_connection_after_rag_search(self) -> None:
        """Email RAG 답변 생성이 기존 Assistant 연결 대신 OpenWebUI 설정을 사용하는지 확인합니다."""

        service = AssistantChatService(config=AssistantChatConfig(use_dummy=False))
        contexts = ["[emailId: E1]\n메일 배경지식"]
        sources = [{"doc_id": "E1", "title": "메일 1", "snippet": "메일 배경지식"}]
        raw_reply = '{"answer":"통합 답변","segments":[{"answer":"메일 기반 답변","usedEmailIds":["E1"]}]}'

        with patch.object(
            service,
            "_retrieve_documents",
            return_value=(contexts, {"hits": {}}, sources),
        ), patch(
            "api.assistant.services.llm.stream_openai_chat_completion",
            return_value=iter([raw_reply]),
        ) as stream_mock:
            result = service.generate_reply_stream(
                "질문입니다",
                user_header_id="knox-user",
                cancellation=ExternalCallCancellation(),
            )

        request = stream_mock.call_args.kwargs
        self.assertEqual(request["url"], "http://openwebui/v1/chat/completions")
        self.assertEqual(request["payload"]["model"], "openwebui-email-model")
        self.assertEqual(request["headers"]["Authorization"], "Bearer email-token")
        self.assertEqual(request["headers"]["X-Provider"], "OpenWebUI")
        self.assertEqual(request["headers"]["User-Id"], "knox-user")
        self.assertEqual(request["timeout_seconds"], 77)
        self.assertEqual(result.segments[0]["reply"], "메일 기반 답변")
        self.assertEqual([source["doc_id"] for source in result.sources], ["E1"])

    def test_generate_reply_rejects_unparseable_reply(self) -> None:
        """파싱 불가 응답을 일반 답변으로 대신 사용하지 않습니다."""
        service = AssistantChatService(
            config=AssistantChatConfig(use_dummy=False)
        )

        sources = [{"doc_id": "E1", "title": "메일 1", "snippet": "내용 1"}]

        with patch.object(service, "_retrieve_documents", return_value=(["context"], {"hits": {}}, sources)):
            with patch(
                "api.assistant.services.chat.stream_llm_reply",
                return_value="그냥 텍스트 응답",
            ):
                with self.assertRaisesMessage(ValueError, "JSON 형식이 아닙니다"):
                    service.generate_reply_stream(
                        "질문입니다",
                        cancellation=ExternalCallCancellation(),
                    )

    def test_generate_reply_treats_empty_segments_as_no_sources(self) -> None:
        """segments가 비어 있으면 일반 업무 사실 대신 근거 없음으로 응답합니다."""
        service = AssistantChatService(
            config=AssistantChatConfig(use_dummy=False)
        )

        sources = [{"doc_id": "E1", "title": "메일 1", "snippet": "내용 1"}]

        with patch.object(service, "_retrieve_documents", return_value=(["context"], {"hits": {}}, sources)):
            with patch(
                "api.assistant.services.chat.stream_llm_reply",
                return_value='{"answer":"OK","segments":[]}',
            ):
                result = service.generate_reply_stream(
                    "질문입니다",
                    cancellation=ExternalCallCancellation(),
                )

        self.assertEqual(result.reply, "배경지식에서 관련 내용을 찾지 못했습니다.")
        self.assertEqual(result.sources, [])
        self.assertEqual(result.segments, [])

    def test_generate_reply_rejects_legacy_used_email_ids_format(self) -> None:
        """segments가 없는 과거 응답 포맷을 현재 계약으로 추정하지 않습니다."""
        service = AssistantChatService(
            config=AssistantChatConfig(use_dummy=False)
        )

        sources = [
            {"doc_id": "E1", "title": "메일 1", "snippet": "내용 1"},
            {"doc_id": "E2", "title": "메일 2", "snippet": "내용 2"},
        ]

        with patch.object(service, "_retrieve_documents", return_value=(["context"], {"hits": {}}, sources)):
            with patch(
                "api.assistant.services.chat.stream_llm_reply",
                return_value='{"answer":"OK","usedEmailIds":["E2","E3"]}',
            ):
                with self.assertRaisesMessage(ValueError, "segments가 배열이 아닙니다"):
                    service.generate_reply_stream(
                        "질문입니다",
                        cancellation=ExternalCallCancellation(),
                    )
