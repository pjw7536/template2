from . import *  # noqa: F403


class AssistantRuntimeV2Part2Tests(TestCase):
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

    def test_turn_send_and_completed_replay_do_not_mutate_branch(self) -> None:
        """동일 완료 Turn replay가 저장 답변만 재생하고 branch/message 수를 유지합니다."""

        runtime_result = assistant_services.AssistantRuntimeResult(
            content="표준 답변",
            blocks=[{"type": "text", "content": "표준 답변", "sourceIds": []}],
            access_requirements=assistant_services.access_requirements_for_scopes(
                ("assistant",)
            ),
        )
        payload = {
            "action": "send",
            "conversationId": str(self.conversation.id),
            "clientRequestId": "turn-request-1",
            "profileKey": "portal-default",
            "appContextKey": "assistant:openwebui:portal",
            "message": {"clientId": "turn-user-1", "content": "표준 질문"},
            "toolInputs": {},
        }
        with patch.object(
            assistant_services.assistant_turn_service.runtime,
            "execute",
            return_value=runtime_result,
        ) as execute:
            response = self.client.post(
                "/api/v1/assistant/turns/stream",
                data=json.dumps(payload),
                content_type="application/json",
            )
            body = b"".join(response.streaming_content).decode("utf-8")
        self.assertEqual(response.status_code, 200)
        self.assertIn("event: run.started", body)
        self.assertIn("event: message.completed", body)
        self.assertIn("event: run.completed", body)
        execute.assert_called_once()
        self.assertEqual(
            execute.call_args.kwargs["context_key"],
            "assistant:openwebui:portal",
        )
        stored_run = AssistantGeneration.objects.get(
            user=self.user,
            client_request_id="turn-request-1",
        )
        self.assertEqual(stored_run.context_key, "assistant:openwebui:portal")
        before_head = AssistantConversation.objects.get(
            id=self.conversation.id
        ).current_message_id
        before_count = AssistantMessage.objects.filter(
            conversation=self.conversation
        ).count()

        replay = self.client.post(
            "/api/v1/assistant/turns/stream",
            data=json.dumps(payload),
            content_type="application/json",
        )
        replay_body = b"".join(replay.streaming_content).decode("utf-8")
        self.assertIn('"replay":true', replay_body)
        self.assertEqual(
            AssistantConversation.objects.get(id=self.conversation.id).current_message_id,
            before_head,
        )
        self.assertEqual(
            AssistantMessage.objects.filter(conversation=self.conversation).count(),
            before_count,
        )

    def test_disconnect_at_precommit_checkpoint_does_not_save_answer(self) -> None:
        """Provider 완료 뒤 저장 직전 연결이 끊기면 답변을 commit하지 않습니다."""

        runtime_result = assistant_services.AssistantRuntimeResult(
            content="저장되면 안 되는 답변",
            blocks=[
                {
                    "type": "text",
                    "content": "저장되면 안 되는 답변",
                    "sourceIds": [],
                }
            ],
            access_requirements=assistant_services.access_requirements_for_scopes(
                ("assistant",)
            ),
        )
        payload = {
            "action": "send",
            "conversationId": str(self.conversation.id),
            "clientRequestId": "turn-disconnect-precommit",
            "profileKey": "portal-default",
            "appContextKey": "assistant:openwebui:portal",
            "message": {
                "clientId": "turn-disconnect-user",
                "content": "저장 직전 중단",
            },
            "toolInputs": {},
        }
        with patch.object(
            assistant_services.assistant_turn_service.runtime,
            "execute",
            return_value=runtime_result,
        ):
            response = self.client.post(
                "/api/v1/assistant/turns/stream",
                data=json.dumps(payload),
                content_type="application/json",
            )
            event_stream = response._iterator
            self.assertIn(b"event: run.started", next(event_stream))
            self.assertIn(b"event: run.heartbeat", next(event_stream))
            event_stream.close()

        generation = AssistantGeneration.objects.get(
            user=self.user,
            client_request_id="turn-disconnect-precommit",
        )
        self.assertEqual(generation.status, AssistantGeneration.Status.STOPPED)
        self.assertFalse(
            AssistantMessage.objects.filter(
                conversation=self.conversation,
                role=AssistantMessage.Roles.ASSISTANT,
                content="저장되면 안 되는 답변",
            ).exists()
        )

    def test_locked_message_returns_chronology_only(self) -> None:
        """data claim이 회수된 메시지는 본문·block·source·snapshot을 반환하지 않습니다."""

        message = AssistantMessage.objects.create(
            conversation=self.conversation,
            client_id="locked-message",
            role=AssistantMessage.Roles.ASSISTANT,
            content="보호 본문",
            blocks=[{"type": "text", "content": "보호 block", "sourceIds": ["mail-1"]}],
            sources=[{"doc_id": "mail-1"}],
            access_requirements={
                "version": 1,
                "accountScopes": ["assistant", "emails"],
                "dataClaims": {"ragPermissionGroups": ["revoked-group"]},
            },
        )
        self.conversation.current_message = message
        self.conversation.save(update_fields=["current_message"])

        response = self.client.get(
            f"/api/v1/assistant/conversations/{self.conversation.id}/messages"
        )
        payload = response.json()["results"][0]
        self.assertEqual(payload["accessState"], "locked")
        for protected_key in ("content", "blocks", "sources", "contextSnapshot"):
            self.assertNotIn(protected_key, payload)

    def test_email_permission_groups_use_email_scope_only(self) -> None:
        """Assistant에서만 허용된 group은 Email RAG 입력과 재검증에서 거부합니다."""

        with patch(
            "api.assistant.selectors.get_accessible_email_user_sdwt_prods_for_user",
            return_value={"group-a"},
        ):
            with self.assertRaises(assistant_services.AssistantRequestError):
                assistant_services.resolve_permission_groups(["assistant-only"], self.user)
            decision = assistant_services.validate_access_requirements(
                user=self.user,
                requirements={
                    "version": 1,
                    "accountScopes": ["assistant", "emails"],
                    "dataClaims": {
                        "ragPermissionGroups": ["assistant-only"],
                    },
                },
            )

        self.assertFalse(decision.allowed)
        self.assertTrue(decision.data_claim_denied)

    def test_email_and_observer_provider_receive_recent_history(self) -> None:
        """Email/Observer Provider에 장기 요약과 요약 이후 최근 이력을 함께 전달합니다."""

        email_service = Mock()
        email_service.generate_reply_stream.return_value = SimpleNamespace(
            reply="메일 답변",
            segments=[],
            sources=[],
            retrieved_sources=[{"doc_id": "mail-1", "_mailbox": "group-a"}],
            contexts=[],
        )
        runtime = assistant_services.AssistantRuntime(
            email_chat_service=email_service,
        )
        email_result = runtime.execute(
            profile=assistant_services.get_assistant_profile(profile_key="email-rag"),
            prompt="방금 메일을 다시 설명해줘",
            history=[{"role": "assistant", "content": "방금 메일의 핵심"}],
            conversation_summary="이전 합의",
            tool_inputs={
                "rag.search": {
                    "permissionGroups": ["group-a"],
                    "mailboxes": ["group-a"],
                    "ragIndexes": ["idx-email"],
                }
            },
            user_header_id="knox-98000",
            context_key="assistant",
            cancellation=ExternalCallCancellation(),
        )
        email_context = email_service.generate_reply_stream.call_args.kwargs[
            "conversation_context"
        ]
        self.assertIn("이전 합의", email_context)
        self.assertIn("방금 메일의 핵심", email_context)
        self.assertEqual(
            email_result.access_requirements["dataClaims"]["mailboxes"],
            ["group-a"],
        )

        observer_payload = {
            "analysis": {
                "headline": "비교 결과",
                "summary": "직전 분석과 비교했습니다.",
                "findings": [],
                "limitations": [],
            },
            "meta": {"sourceCounts": {"eqp": 2}},
            "scope": {},
        }
        with patch(
            "api.assistant.services.runtime.analyze_observer_logs_stream",
            return_value=observer_payload,
        ) as analyze:
            observer_result = runtime.execute(
                profile=assistant_services.get_assistant_profile(
                    profile_key="observer-analysis"
                ),
                prompt="앞 분석과 비교해줘",
                history=[{"role": "assistant", "content": "직전 DOWN 분석"}],
                conversation_summary="장기 Observer 요약",
                tool_inputs={
                    "observer.analysis": {
                        "eqpId": "EQP-1",
                        "from": "2026-08-01T00:00:00+09:00",
                        "to": "2026-08-02T00:00:00+09:00",
                        "logTypes": ["eqp"],
                        "tipGroups": ["__ALL__"],
                    }
                },
                user_header_id="knox-98000",
                context_key="observer:test",
                cancellation=ExternalCallCancellation(),
            )
        observer_context = analyze.call_args.kwargs["conversation_summary"]
        self.assertIn("장기 Observer 요약", observer_context)
        self.assertIn("직전 DOWN 분석", observer_context)
        self.assertIn("직전 분석과 비교했습니다.", observer_result.content)
        self.assertEqual(observer_result.execution_metadata["evidenceCount"], 2)

    def test_observer_provider_returns_not_found_only_when_all_sources_are_empty(self) -> None:
        """Observer 조회 source가 모두 0건일 때만 근거 없음 응답을 반환합니다."""

        observer_payload = {
            "analysis": {
                "headline": "분석 결과",
                "summary": "조회 범위에 분석할 로그가 없습니다.",
                "findings": [],
                "limitations": [],
            },
            "meta": {"sourceCounts": {"eqp": 0, "tip": 0}},
            "scope": {},
        }
        with patch(
            "api.assistant.services.runtime.analyze_observer_logs_stream",
            return_value=observer_payload,
        ):
            result = assistant_services.AssistantRuntime().execute(
                profile=assistant_services.get_assistant_profile(
                    profile_key="observer-analysis"
                ),
                prompt="현재 범위를 분석해줘",
                history=[],
                conversation_summary="",
                tool_inputs={
                    "observer.analysis": {
                        "eqpId": "EQP-1",
                        "from": "2026-08-01T00:00:00+09:00",
                        "to": "2026-08-02T00:00:00+09:00",
                        "logTypes": ["eqp"],
                        "tipGroups": ["__ALL__"],
                    }
                },
                user_header_id="knox-98000",
                context_key="observer:test",
                cancellation=ExternalCallCancellation(),
            )

        self.assertEqual(result.content, "배경지식에서 관련 내용을 찾지 못했습니다.")
        self.assertEqual(result.execution_metadata["evidenceCount"], 0)

    def test_observer_provider_accepts_interlock_log_keys(self) -> None:
        """Observer Provider는 화면과 selector가 사용하는 Interlock 키를 허용합니다."""

        observer_payload = {
            "analysis": {
                "headline": "Interlock 분석",
                "summary": "SPC/FDC Interlock을 분석했습니다.",
                "findings": [],
                "limitations": [],
            },
            "meta": {
                "sourceCounts": {"spc-interlock": 1, "fdc-interlock": 1}
            },
            "scope": {},
        }
        with patch(
            "api.assistant.services.runtime.analyze_observer_logs_stream",
            return_value=observer_payload,
        ) as analyze:
            assistant_services.AssistantRuntime().execute(
                profile=assistant_services.get_assistant_profile(
                    profile_key="observer-analysis",
                    profile_version=2,
                ),
                prompt="Interlock을 분석해줘",
                history=[],
                conversation_summary="",
                tool_inputs={
                    "observer.analysis": {
                        "eqpId": "EQP-1",
                        "from": "2026-08-01T00:00:00+09:00",
                        "to": "2026-08-02T00:00:00+09:00",
                        "logTypes": ["spc-interlock", "fdc-interlock"],
                        "tipGroups": ["__ALL__"],
                    }
                },
                user_header_id="knox-98000",
                context_key="observer:test",
                cancellation=ExternalCallCancellation(),
            )

        self.assertEqual(
            analyze.call_args.kwargs["log_types"],
            ["spc-interlock", "fdc-interlock"],
        )
