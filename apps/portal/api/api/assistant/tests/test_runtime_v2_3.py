from . import *  # noqa: F403


class AssistantRuntimeV2Part3Tests(TestCase):
    """Assistant Runtime v2 권한·실행 계약을 검증합니다."""

    def setUp(self) -> None:
        """모든 Account scope를 통과하는 테스트 사용자와 대화방을 준비합니다."""

        _allow_test_scope_access(self)
        User = get_user_model()
        self.user = User.objects.create_user(
            sabun="S98000",
            password="test-password",
        )
        self.user.knox_id = "knox-98000"
        self.user.save(update_fields=["knox_id"])
        _set_current_affiliation(self.user, user_sdwt_prod="group-a")
        self.client.force_login(self.user)
        self.conversation = AssistantConversation.objects.create(
            user=self.user,
            title="새 대화",
            title_source="default",
        )

    def _generation(self, *, partition: str, profile_key: str) -> AssistantGeneration:
        """memory partition이 고정된 완료 Run을 생성합니다."""

        now = timezone.now()
        return AssistantGeneration.objects.create(
            user=self.user,
            conversation=self.conversation,
            client_request_id=f"request-{profile_key}",
            context_key=f"profile:{profile_key}",
            status=AssistantGeneration.Status.COMPLETED,
            provider="test",
            profile_key=profile_key,
            profile_version=2,
            memory_partition=partition,
            access_requirements=assistant_services.access_requirements_for_scopes(()),
            expires_at=now + timedelta(minutes=1),
            finished_at=now,
        )

    def test_runtime_memory_starts_after_partition_summary_cursor(self) -> None:
        """summary에 포함된 partition 메시지는 최근 history에서 다시 보내지 않습니다."""

        generation = self._generation(
            partition="shared",
            profile_key="portal-default",
        )
        parent = None
        for index in range(3):
            parent = AssistantMessage.objects.create(
                conversation=self.conversation,
                client_id=f"summary-overlap-{index}",
                role=AssistantMessage.Roles.USER,
                content=f"메시지 {index}",
                context_key="assistant:openwebui:portal",
                parent=parent,
                generation=generation,
                access_requirements=assistant_services.access_requirements_for_scopes(
                    ("assistant",)
                ),
            )
        self.conversation.current_message = parent
        self.conversation.save(update_fields=["current_message"])
        AssistantConversationSummary.objects.create(
            conversation=self.conversation,
            context_key="shared",
            memory_partition="shared",
            summary="첫 두 메시지 요약",
            message_count=2,
            access_requirements=assistant_services.access_requirements_for_scopes(
                ("assistant",)
            ),
        )

        memory = assistant_services.build_assistant_runtime_memory(
            user=self.user,
            conversation=self.conversation,
            profile=assistant_services.get_assistant_profile(
                profile_key="portal-default"
            ),
        )

        self.assertEqual(memory.summary, "첫 두 메시지 요약")
        self.assertEqual(
            [entry["content"] for entry in memory.history],
            ["메시지 2"],
        )

    def test_locked_summary_batch_does_not_advance_cursor(self) -> None:
        """연속 batch 중 하나라도 잠기면 summary cursor를 건너뛰지 않습니다."""

        parent = None
        for index in range(22):
            requirements = (
                {
                    "version": 1,
                    "accountScopes": ["assistant"],
                    "dataClaims": {"ragPermissionGroups": ["revoked-group"]},
                }
                if index == 3
                else assistant_services.access_requirements_for_scopes(("assistant",))
            )
            parent = AssistantMessage.objects.create(
                conversation=self.conversation,
                client_id=f"locked-summary-{index}",
                role=(
                    AssistantMessage.Roles.USER
                    if index % 2 == 0
                    else AssistantMessage.Roles.ASSISTANT
                ),
                content=f"요약 대상 {index}",
                context_key="assistant:openwebui:portal",
                parent=parent,
                access_requirements=requirements,
            )
        self.conversation.current_message = parent
        self.conversation.save(update_fields=["current_message"])

        result = assistant_services.refresh_authorized_assistant_conversation_summary(
            user=self.user,
            request=RequestFactory().post("/"),
            conversation=self.conversation,
            context_key="profile:portal-default",
        )

        self.assertFalse(result["updated"])
        self.assertEqual(result["coveredMessageCount"], 0)
        self.assertFalse(
            AssistantConversationSummary.objects.filter(
                conversation=self.conversation,
                context_key="shared",
            ).exists()
        )

    def test_locked_title_and_body_are_not_search_or_pagination_oracles(self) -> None:
        """잠긴 제목·본문 검색은 대화 존재 여부나 page 위치를 드러내지 않습니다."""

        locked = AssistantConversation.objects.create(
            user=self.user,
            title="극비 검색 키워드",
            title_source="auto",
            title_access_requirements={
                "version": 1,
                "accountScopes": ["assistant", "emails"],
                "dataClaims": {"ragPermissionGroups": ["revoked-group"]},
            },
        )
        locked_message = AssistantMessage.objects.create(
            conversation=locked,
            client_id="locked-search-message",
            role=AssistantMessage.Roles.USER,
            content="극비 검색 키워드 본문",
            context_key="assistant",
            access_requirements=locked.title_access_requirements,
        )
        locked.current_message = locked_message
        locked.save(update_fields=["current_message"])

        response = self.client.get(
            "/api/v1/assistant/conversations",
            {"search": "극비 검색 키워드", "limit": 1},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], [])
        self.assertFalse(response.json()["hasMore"])

    def test_retry_cannot_reference_run_from_another_conversation(self) -> None:
        """retryRunId는 요청 conversation 안의 Run만 참조할 수 있습니다."""

        other = AssistantConversation.objects.create(
            user=self.user,
            title="다른 대화",
            title_source="default",
        )
        now = timezone.now()
        foreign_run = AssistantGeneration.objects.create(
            user=self.user,
            conversation=other,
            client_request_id="foreign-retry-run",
            context_key="assistant:openwebui:portal",
            status=AssistantGeneration.Status.FAILED,
            provider="openwebui",
            profile_key="portal-default",
            profile_version=2,
            memory_partition="shared",
            access_requirements=assistant_services.access_requirements_for_scopes(
                ("assistant",)
            ),
            expires_at=now,
            finished_at=now,
        )
        AssistantMessage.objects.create(
            conversation=other,
            client_id="foreign-retry-user",
            role=AssistantMessage.Roles.USER,
            content="다른 대화 질문",
            context_key="assistant:openwebui:portal",
            generation=foreign_run,
            access_requirements=foreign_run.access_requirements,
        )
        payload = {
            "action": "retry",
            "conversationId": str(self.conversation.id),
            "clientRequestId": "cross-conversation-retry",
            "profileKey": "portal-default",
            "message": {"clientId": "new-retry-user", "content": "재시도"},
            "retryRunId": str(foreign_run.id),
            "toolInputs": {},
        }

        response = self.client.post(
            "/api/v1/assistant/turns/stream",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"], "target_not_found")

    def test_expired_run_result_is_fenced_before_message_persistence(self) -> None:
        """lease가 만료된 Provider 결과는 답변이나 branch head를 저장하지 않습니다."""

        from api.assistant.services.turn_persistence import (
            AssistantRunFencedError,
            commit_assistant_turn_result,
        )

        generation = AssistantGeneration.objects.create(
            user=self.user,
            conversation=self.conversation,
            client_request_id="expired-run",
            context_key="assistant:openwebui:portal",
            status=AssistantGeneration.Status.STREAMING,
            provider="openwebui",
            profile_key="portal-default",
            profile_version=2,
            memory_partition="shared",
            access_requirements=assistant_services.access_requirements_for_scopes(
                ("assistant",)
            ),
            expires_at=timezone.now() - timedelta(seconds=1),
            started_at=timezone.now() - timedelta(minutes=1),
        )
        user_message = AssistantMessage.objects.create(
            conversation=self.conversation,
            client_id="expired-user",
            role=AssistantMessage.Roles.USER,
            content="이미 만료된 질문",
            context_key="assistant:openwebui:portal",
            generation=generation,
            access_requirements=generation.access_requirements,
        )
        self.conversation.current_message = user_message
        self.conversation.save(update_fields=["current_message"])
        result = assistant_services.AssistantRuntimeResult(
            content="늦게 도착한 답변",
            blocks=[
                {
                    "type": "text",
                    "content": "늦게 도착한 답변",
                    "sourceIds": [],
                }
            ],
            access_requirements=generation.access_requirements,
        )

        with self.assertRaises(AssistantRunFencedError):
            commit_assistant_turn_result(
                generation_id=generation.id,
                input_message_id=user_message.id,
                input_message_client_id=user_message.client_id,
                assistant_client_id="expired-assistant",
                context_key="assistant:openwebui:portal",
                result=result,
            )

        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.current_message_id, user_message.id)
        self.assertFalse(
            AssistantMessage.objects.filter(
                conversation=self.conversation,
                client_id="expired-assistant",
            ).exists()
        )

    def test_turn_failure_never_exposes_upstream_error_detail(self) -> None:
        """Provider 예외 본문과 식별자는 run.failed로 전달하지 않습니다."""

        payload = {
            "action": "send",
            "conversationId": str(self.conversation.id),
            "clientRequestId": "safe-error-run",
            "profileKey": "portal-default",
            "appContextKey": "assistant:openwebui:portal",
            "message": {"clientId": "safe-error-user", "content": "질문"},
            "toolInputs": {},
        }
        with patch.object(
            assistant_services.assistant_turn_service.runtime,
            "execute",
            side_effect=RuntimeError("internal-host secret-token mailbox-77"),
        ):
            response = self.client.post(
                "/api/v1/assistant/turns/stream",
                data=json.dumps(payload),
                content_type="application/json",
            )
            body = b"".join(response.streaming_content).decode("utf-8")

        self.assertIn("event: run.failed", body)
        self.assertNotIn("secret-token", body)
        self.assertNotIn("mailbox-77", body)
