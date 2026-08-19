from . import *  # noqa: F403


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

    def test_openwebui_title_is_saved_for_default_conversation(self) -> None:
        """저장된 첫 질문과 답변으로 생성한 제목이 대화방에 반영되는지 확인합니다."""

        self.client.force_login(self.owner)
        conversation_id = self._create_conversation(name="새 대화")
        conversation = AssistantConversation.objects.get(id=conversation_id)
        _append_assistant_messages(
            conversation=conversation,
            messages=[
                {
                    "client_id": "user-title",
                    "role": "user",
                    "content": "EQP DOWN이 반복되는 원인은?",
                    "context_key": "assistant:openwebui:portal",
                },
                {
                    "client_id": "assistant-title",
                    "role": "assistant",
                    "content": "인터락 반복 발생이 주요 원인입니다.",
                    "context_key": "assistant:openwebui:portal",
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
        _append_assistant_messages(
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
        _append_assistant_messages(
            conversation=conversation,
            messages=[
                {
                    "client_id": f"user-{index}",
                    "role": "user",
                    "content": f"질문 {index}",
                    "context_key": "assistant:openwebui:portal",
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
        _append_assistant_messages(
            conversation=conversation,
            messages=[
                {
                    "client_id": "user-after-reset",
                    "role": "user",
                    "content": "초기화 후 질문",
                    "context_key": "assistant:openwebui:portal",
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
        _append_assistant_messages(
            conversation=conversation,
            messages=[
                {
                    "client_id": f"summary-{index}",
                    "role": "user" if index % 2 == 0 else "assistant",
                    "content": f"대화 {index}",
                    "context_key": "assistant:openwebui:portal",
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
                data=json.dumps({"contextKey": "profile:portal-default"}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["updated"])
        self.assertEqual(response.json()["coveredMessageCount"], 15)
        summary = AssistantConversationSummary.objects.get(
            conversation=conversation,
            context_key="shared",
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

    def test_summary_refresh_keeps_profile_partitions_separate(self) -> None:
        """rolling summary는 Portal·Observer·Email partition을 서로 섞지 않습니다."""

        self.client.force_login(self.owner)
        conversation_id = self._create_conversation()
        conversation = AssistantConversation.objects.get(id=conversation_id)
        messages = []
        for index in range(25):
            messages.extend(
                [
                    {
                        "client_id": f"general-{index}",
                        "role": "user",
                        "content": f"일반 대화 {index}",
                        "context_key": "assistant:openwebui:portal",
                    },
                    {
                        "client_id": f"observer-{index}",
                        "role": "assistant",
                        "content": f"Observer 분석 {index}",
                        "context_key": "observer:scope-a",
                    },
                    {
                        "client_id": f"email-{index}",
                        "role": "user",
                        "content": f"메일 대화 {index}",
                        "context_key": "assistant",
                    },
                ]
            )
        _append_assistant_messages(
            conversation=conversation,
            messages=messages,
        )

        with patch(
            "api.assistant.services.conversations.request_openwebui_conversation_summary",
            return_value="Portal 공용 대화 요약",
        ) as mocked_summary:
            response = self.client.post(
                f"/api/v1/assistant/conversations/{conversation_id}/refresh-summary",
                data=json.dumps({"contextKey": "profile:portal-default"}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200, response.content)
        summarized_contents = [
            message["content"]
            for message in mocked_summary.call_args.kwargs["messages"]
        ]
        self.assertTrue(summarized_contents)
        self.assertTrue(
            all("Observer 분석" not in content and "메일 대화" not in content for content in summarized_contents)
        )

        with patch(
            "api.assistant.services.conversations.request_openwebui_conversation_summary",
            return_value="Observer 전용 요약",
        ):
            observer_response = self.client.post(
                f"/api/v1/assistant/conversations/{conversation_id}/refresh-summary",
                data=json.dumps({"contextKey": "profile:observer-analysis"}),
                content_type="application/json",
            )

        self.assertEqual(observer_response.status_code, 200, observer_response.content)
        self.assertTrue(observer_response.json()["updated"])
        summaries = AssistantConversationSummary.objects.filter(
            conversation=conversation,
        )
        self.assertEqual(summaries.count(), 2)
        self.assertEqual(
            summaries.get(context_key="shared").summary,
            "Portal 공용 대화 요약",
        )
        self.assertEqual(
            summaries.get(context_key="scope:observer").summary,
            "Observer 전용 요약",
        )

    def test_conversation_metadata_archive_and_message_search(self) -> None:
        """이름·고정·보관 갱신과 메시지 본문 검색을 함께 지원합니다."""

        self.client.force_login(self.owner)
        conversation_id = self._create_conversation(name="초기 이름")
        conversation = AssistantConversation.objects.get(id=conversation_id)
        _append_assistant_messages(
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
