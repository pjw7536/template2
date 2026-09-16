from . import *  # noqa: F403


class AssistantRunBackfillTests(TestCase):
    """legacy provenance backfill의 해제·잠금·재실행 안정성을 검증합니다."""

    def setUp(self) -> None:
        """backfill 대상 사용자와 대화방을 준비합니다."""

        User = get_user_model()
        self.user = User.objects.create_user(
            sabun="S99000",
            password="test-password",
        )
        self.conversation = AssistantConversation.objects.create(
            user=self.user,
            title="Legacy 대화",
            title_source="legacy_unknown",
        )
        self.unresolved = {
            "version": 1,
            "accountScopes": ["legacy-unresolved"],
            "dataClaims": {},
        }

    def test_backfill_replaces_sentinel_and_keeps_unresolved_terminal(self) -> None:
        """분류 가능한 row만 잠금을 해제하고 unresolved row는 재실행해도 그대로 둡니다."""

        email_message = AssistantMessage.objects.create(
            conversation=self.conversation,
            client_id="legacy-email",
            role=AssistantMessage.Roles.USER,
            content="메일 질문",
            context_key="assistant",
            access_requirements=self.unresolved,
            user_sdwt_prod="group-a",
        )
        unknown_message = AssistantMessage.objects.create(
            conversation=self.conversation,
            client_id="legacy-unknown",
            role=AssistantMessage.Roles.USER,
            content="출처 불명 질문",
            context_key="unknown-context",
            access_requirements=self.unresolved,
        )

        first_output = StringIO()
        call_command(
            "backfill_assistant_run_access",
            batch_size=10,
            stdout=first_output,
        )
        email_message.refresh_from_db()
        unknown_message.refresh_from_db()
        email_run = email_message.generation
        unknown_run = unknown_message.generation

        self.assertEqual(email_run.profile_key, "email-rag")
        self.assertNotIn(
            "legacy-unresolved",
            email_run.access_requirements["accountScopes"],
        )
        self.assertEqual(unknown_run.profile_key, "legacy-unresolved")
        self.assertIn(
            "legacy-unresolved",
            unknown_run.access_requirements["accountScopes"],
        )

        second_output = StringIO()
        call_command(
            "backfill_assistant_run_access",
            batch_size=10,
            stdout=second_output,
        )
        unknown_run.refresh_from_db()
        second_report = json.loads(second_output.getvalue().strip().splitlines()[-1])

        self.assertEqual(second_report["processed"], 0)
        self.assertEqual(unknown_run.profile_key, "legacy-unresolved")
        self.assertIn(
            "legacy-unresolved",
            unknown_run.access_requirements["accountScopes"],
        )
