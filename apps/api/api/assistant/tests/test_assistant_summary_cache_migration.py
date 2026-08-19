from . import *  # noqa: F403


class AssistantSummaryCacheMigrationTests(TestCase):
    """Portal Assistant 기억 통합 data migration의 삭제 범위를 검증합니다."""

    def test_migration_resets_only_rebuildable_shared_summary_cache(self) -> None:
        """공유·Email 요약만 삭제하고 원본 메시지와 다른 문맥 요약은 보존합니다."""

        user = get_user_model().objects.create_user(
            sabun="S71000",
            password="test-password",
        )
        conversation = AssistantConversation.objects.create(
            user=user,
            title="요약 migration 테스트",
        )
        message = AssistantMessage.objects.create(
            conversation=conversation,
            client_id="migration-message",
            role="user",
            content="보존할 원본 메시지",
            context_key="assistant",
        )
        for context_key in (
            "assistant",
            "chatwidget:shared",
            "custom:isolated",
        ):
            AssistantConversationSummary.objects.create(
                conversation=conversation,
                context_key=context_key,
                summary=f"{context_key} 요약",
                message_count=1,
            )

        migration = import_module(
            "api.assistant.migrations.0002_reset_portal_assistant_summary_cache"
        )
        migration.reset_portal_assistant_summary_cache(django_apps, None)

        self.assertEqual(
            set(
                AssistantConversationSummary.objects.filter(
                    conversation=conversation,
                ).values_list("context_key", flat=True)
            ),
            {"custom:isolated"},
        )
        self.assertTrue(
            AssistantMessage.objects.filter(
                id=message.id,
                conversation=conversation,
                content="보존할 원본 메시지",
            ).exists()
        )
