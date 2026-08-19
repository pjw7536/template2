from . import *  # noqa: F403


class AssistantRuntimeV2Part1Tests(TestCase):
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

    def test_profile_reads_only_allowed_memory_partitions(self) -> None:
        """일반 대화는 공용 기억만 읽고 전용 Profile은 현재 앱 범위만 추가합니다."""

        parent = None
        for partition, profile_key, content in (
            ("shared", "portal-default", "공용 기억"),
            ("scope:emails", "email-rag", "메일 기억"),
            ("scope:observer", "observer-analysis", "Observer 기억"),
        ):
            parent = AssistantMessage.objects.create(
                conversation=self.conversation,
                client_id=f"message-{profile_key}",
                role=AssistantMessage.Roles.USER,
                content=content,
                context_key=f"profile:{profile_key}",
                parent=parent,
                generation=self._generation(
                    partition=partition,
                    profile_key=profile_key,
                ),
            )
        parent = AssistantMessage.objects.create(
            conversation=self.conversation,
            client_id="message-without-run",
            role=AssistantMessage.Roles.USER,
            content="contextKey만 있는 미분류 기억",
            context_key="assistant:openwebui:portal",
            parent=parent,
            access_requirements=assistant_services.access_requirements_for_scopes(()),
        )
        self.conversation.current_message = parent
        self.conversation.save(update_fields=["current_message"])

        locked = AssistantMessage.objects.create(
            conversation=self.conversation,
            client_id="message-locked-observer",
            role=AssistantMessage.Roles.USER,
            content="권한이 회수된 Observer 기억",
            context_key="profile:observer-analysis",
            parent=parent,
            generation=self._generation(
                partition="scope:observer",
                profile_key="locked-observer",
            ),
            access_requirements={
                "version": 1,
                "accountScopes": ["assistant", "observer"],
                "dataClaims": {"ragPermissionGroups": ["revoked-group"]},
            },
        )
        self.conversation.current_message = locked
        self.conversation.save(update_fields=["current_message"])

        portal = assistant_services.build_assistant_runtime_memory(
            user=self.user,
            conversation=self.conversation,
            profile=assistant_services.get_assistant_profile(
                profile_key="portal-default"
            ),
        )
        email = assistant_services.build_assistant_runtime_memory(
            user=self.user,
            conversation=self.conversation,
            profile=assistant_services.get_assistant_profile(profile_key="email-rag"),
        )
        observer = assistant_services.build_assistant_runtime_memory(
            user=self.user,
            conversation=self.conversation,
            profile=assistant_services.get_assistant_profile(
                profile_key="observer-analysis"
            ),
        )

        self.assertEqual(
            [item["content"] for item in portal.history],
            ["공용 기억"],
        )
        self.assertEqual(
            [item["content"] for item in email.history],
            ["공용 기억", "메일 기억"],
        )
        self.assertEqual(
            [item["content"] for item in observer.history],
            ["공용 기억", "Observer 기억"],
        )
        self.assertEqual(
            assistant_services.get_assistant_profile(
                profile_key="appstore-context"
            ).read_partitions,
            ("shared", "scope:appstore"),
        )
        self.assertEqual(
            assistant_services.get_assistant_profile(
                profile_key="line-dashboard-context"
            ).read_partitions,
            ("shared", "scope:line-dashboard"),
        )
        self.assertEqual(
            {
                profile_key: assistant_services.get_assistant_profile(
                    profile_key=profile_key
                ).version
                for profile_key in (
                    "appstore-context",
                    "line-dashboard-context",
                    "observer-analysis",
                )
            },
            {
                "appstore-context": 2,
                "line-dashboard-context": 2,
                "observer-analysis": 2,
            },
        )

    def test_portal_profile_uses_only_explicit_current_app_context(self) -> None:
        """일반 Profile은 전달된 현재 앱 설명만 사용하고 Portal context는 배경지식을 비웁니다."""

        runtime = assistant_services.AssistantRuntime()
        profile = assistant_services.get_assistant_profile(
            profile_key="portal-default"
        )
        with patch(
            "api.assistant.services.runtime.stream_openwebui_chat",
            side_effect=[["현재 앱 답변"], ["일반 답변"]],
        ) as provider:
            runtime.execute(
                profile=profile,
                prompt="현재 앱 질문",
                history=[],
                conversation_summary="",
                tool_inputs={},
                user_header_id=self.user.sabun,
                context_key="assistant:openwebui:voc",
                cancellation=ExternalCallCancellation(),
            )
            runtime.execute(
                profile=profile,
                prompt="일반 질문",
                history=[],
                conversation_summary="",
                tool_inputs={},
                user_header_id=self.user.sabun,
                context_key="assistant:openwebui:portal",
                cancellation=ExternalCallCancellation(),
            )

        self.assertEqual(
            provider.call_args_list[0].kwargs["context_key"],
            "assistant:openwebui:voc",
        )
        self.assertEqual(
            provider.call_args_list[1].kwargs["context_key"],
            "assistant:openwebui:portal",
        )

    def test_appstore_and_line_dashboard_runtime_use_server_snapshots(self) -> None:
        """전용 Tool은 브라우저 원본 없이 서버 selector snapshot만 Provider에 전달합니다."""

        runtime = assistant_services.AssistantRuntime()
        appstore_snapshot = {
            "count": 1,
            "truncated": False,
            "apps": [{"id": 7, "name": "분석 앱"}],
        }
        line_snapshot = {
            "totalCount": 3,
            "from": "2026-08-01",
            "to": "2026-08-02",
            "statusCounts": [{"status": "RUN", "count": 3}],
        }
        with patch(
            "api.assistant.services.runtime.appstore_selectors.get_appstore_assistant_catalog",
            return_value=appstore_snapshot,
        ) as appstore_selector, patch(
            "api.assistant.services.runtime.drone_selectors.get_line_dashboard_assistant_snapshot",
            return_value=line_snapshot,
        ) as line_selector, patch(
            "api.assistant.services.runtime.stream_openwebui_chat",
            side_effect=[["Appstore 답변"], ["ESOP 답변"]],
        ) as provider:
            appstore_result = runtime.execute(
                profile=assistant_services.get_assistant_profile(
                    profile_key="appstore-context"
                ),
                prompt="분석 앱을 알려줘",
                history=[],
                conversation_summary="",
                tool_inputs={
                    "appstore.catalog": {
                        "query": "분석",
                        "category": "Tools",
                        "selectedAppId": None,
                    }
                },
                user_header_id="knox-98000",
                context_key="appstore:v1",
                cancellation=ExternalCallCancellation(),
            )
            line_result = runtime.execute(
                profile=assistant_services.get_assistant_profile(
                    profile_key="line-dashboard-context"
                ),
                prompt="현재 상태를 알려줘",
                history=[],
                conversation_summary="",
                tool_inputs={
                    "line-dashboard.snapshot": {
                        "view": "status",
                        "lineId": "L1",
                        "from": "2026-08-01",
                        "to": "2026-08-02",
                        "lineFilterMode": "target_user_sdwt_prod",
                        "recentHoursStart": 8,
                        "recentHoursEnd": 0,
                    }
                },
                user_header_id="knox-98000",
                context_key="line-dashboard:v1",
                cancellation=ExternalCallCancellation(),
            )

        appstore_selector.assert_called_once_with(
            query="분석",
            category="Tools",
            selected_app_id=None,
        )
        line_selector.assert_called_once_with(
            line_id="L1",
            view="status",
            from_value="2026-08-01",
            to_value="2026-08-02",
            line_filter_mode="target_user_sdwt_prod",
            recent_hours_start=8,
            recent_hours_end=0,
        )
        self.assertEqual(appstore_result.tool_keys, ["appstore.catalog"])
        self.assertEqual(line_result.tool_keys, ["line-dashboard.snapshot"])
        self.assertEqual(
            appstore_result.access_requirements["accountScopes"],
            ["appstore", "assistant"],
        )
        self.assertEqual(
            line_result.access_requirements["accountScopes"],
            ["assistant", "line-dashboard"],
        )
        self.assertIn("분석 앱", provider.call_args_list[0].kwargs["system_message"])
        self.assertIn('"status":"RUN"', provider.call_args_list[1].kwargs["system_message"])

    def test_line_dashboard_tool_input_preserves_current_table_filters(self) -> None:
        """ESOP Tool 입력은 현재 표의 line·최근 시간 필터를 검증해 보존합니다."""

        normalized = assistant_services.AssistantTurnService()._normalize_tool_inputs(
            user=self.user,
            profile=assistant_services.get_assistant_profile(
                profile_key="line-dashboard-context"
            ),
            tool_inputs={
                "line-dashboard.snapshot": {
                    "view": "status",
                    "lineId": " L1 ",
                    "from": "2026-08-15",
                    "to": "2026-08-15",
                    "lineFilterMode": "target_user_sdwt_prod",
                    "recentHoursStart": 8,
                    "recentHoursEnd": 0,
                }
            },
        )

        self.assertEqual(
            normalized["line-dashboard.snapshot"],
            {
                "view": "status",
                "lineId": "L1",
                "from": "2026-08-15",
                "to": "2026-08-15",
                "lineFilterMode": "target_user_sdwt_prod",
                "recentHoursStart": 8,
                "recentHoursEnd": 0,
            },
        )
        with self.assertRaises(assistant_services.AssistantTurnError):
            assistant_services.AssistantTurnService()._normalize_tool_inputs(
                user=self.user,
                profile=assistant_services.get_assistant_profile(
                    profile_key="line-dashboard-context"
                ),
                tool_inputs={
                    "line-dashboard.snapshot": {
                        "view": "status",
                        "lineId": "L1",
                        "from": "2026-08-15",
                        "to": "2026-08-15",
                    }
                },
            )

    def test_email_turn_revalidates_mailbox_and_selected_email_scope(self) -> None:
        """Email 현재 화면 scope는 서버 selector 결과로 바꾸고 불일치 범위는 거부합니다."""

        payload = {
            "action": "send",
            "conversationId": str(self.conversation.id),
            "clientRequestId": "email-scope-turn-request",
            "profileKey": "email-rag",
            "profileVersion": 2,
            "appContextKey": "assistant",
            "message": {"clientId": "email-scope-user-message", "content": "이 메일을 요약해줘"},
            "toolInputs": {
                "rag.search": {
                    "permissionGroups": ["group-a"],
                    "ragIndexes": ["rp-emails"],
                    "mailbox": "group-a",
                    "emailId": "17",
                }
            },
        }
        with patch(
            "api.assistant.services.turns.email_selectors.resolve_assistant_email_scope",
            return_value=None,
        ), patch.object(
            assistant_services.assistant_turn_service.runtime,
            "execute",
        ) as execute:
            response = self.client.post(
                "/api/v1/assistant/turns/stream",
                data=json.dumps(payload),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 403)
        execute.assert_not_called()

    def test_email_turn_returns_verified_scope_result(self) -> None:
        """검증된 Email scope가 실제 실행 입력과 응답에 반영됩니다."""

        runtime_result = assistant_services.AssistantRuntimeResult(
            content="선택 메일 요약",
            blocks=[{"type": "text", "content": "선택 메일 요약", "sourceIds": ["rag-17"]}],
            sources=[{"doc_id": "rag-17", "title": "메일 제목"}],
            tool_keys=["rag.search"],
            access_requirements=assistant_services.access_requirements_for_scopes(
                ("assistant", "emails")
            ),
        )
        payload = {
            "action": "send",
            "conversationId": str(self.conversation.id),
            "clientRequestId": "email-scope-success-request",
            "profileKey": "email-rag",
            "profileVersion": 2,
            "appContextKey": "assistant",
            "message": {"clientId": "email-scope-success-user", "content": "이 메일을 요약해줘"},
            "toolInputs": {
                "rag.search": {
                    "permissionGroups": ["group-a"],
                    "ragIndexes": ["rp-emails"],
                    "mailbox": "group-a",
                    "emailId": "17",
                }
            },
        }
        with patch(
            "api.assistant.services.turns.email_selectors.resolve_assistant_email_scope",
            return_value={"mailbox": "group-a", "emailId": "rag-17"},
        ), patch.object(
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
        self.assertEqual(
            execute.call_args.kwargs["tool_inputs"]["rag.search"]["emailId"],
            "rag-17",
        )
        self.assertIn("선택 메일 요약", body)
        self.assertNotIn("permissionGroups", body)

    def test_appstore_turn_stores_scoped_profile_and_normalized_tool_input(self) -> None:
        """Appstore Turn은 전용 partition과 앱 권한 provenance를 저장합니다."""

        runtime_result = assistant_services.AssistantRuntimeResult(
            content="분석 앱 안내",
            blocks=[{"type": "text", "content": "분석 앱 안내", "sourceIds": []}],
            tool_keys=["appstore.catalog"],
            access_requirements=assistant_services.access_requirements_for_scopes(
                ("assistant", "appstore")
            ),
        )
        payload = {
            "action": "send",
            "conversationId": str(self.conversation.id),
            "clientRequestId": "appstore-turn-request",
            "profileKey": "appstore-context",
            "profileVersion": 2,
            "appContextKey": "appstore:v1",
            "message": {"clientId": "appstore-user-message", "content": "분석 앱을 알려줘"},
            "toolInputs": {
                "appstore.catalog": {
                    "query": "  분석  ",
                    "category": "Tools",
                    "selectedAppId": "7",
                }
            },
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
            self.assertEqual(response.status_code, 200)
            body = b"".join(response.streaming_content).decode("utf-8")

        self.assertIn("event: run.completed", body)
        stored_run = AssistantGeneration.objects.get(
            user=self.user,
            client_request_id="appstore-turn-request",
        )
        self.assertEqual(stored_run.profile_key, "appstore-context")
        self.assertEqual(stored_run.memory_partition, "scope:appstore")
        self.assertEqual(
            stored_run.access_requirements["accountScopes"],
            ["appstore", "assistant"],
        )
        self.assertEqual(
            execute.call_args.kwargs["tool_inputs"],
            {
                "appstore.catalog": {
                    "query": "분석",
                    "category": "Tools",
                    "selectedAppId": 7,
                }
            },
        )
