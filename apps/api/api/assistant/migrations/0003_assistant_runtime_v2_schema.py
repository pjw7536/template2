import api.assistant.models
from django.db import migrations, models


def lock_legacy_provenance(apps, schema_editor):
    """분류 전 legacy 파생 데이터를 version 불명 상태로 잠급니다."""

    del schema_editor
    unresolved = {
        "version": 1,
        "accountScopes": ["legacy-unresolved"],
        "dataClaims": {},
    }
    apps.get_model("assistant", "AssistantConversation").objects.update(
        title_access_requirements=unresolved
    )
    apps.get_model("assistant", "AssistantConversationSummary").objects.update(
        access_requirements=unresolved
    )
    apps.get_model("assistant", "AssistantGeneration").objects.update(
        access_requirements=unresolved
    )
    apps.get_model("assistant", "AssistantMessage").objects.update(
        access_requirements=unresolved
    )


class Migration(migrations.Migration):
    """Assistant Runtime v2의 nullable provenance와 권한 필드를 추가합니다."""

    dependencies = [("assistant", "0002_reset_portal_assistant_summary_cache")]

    operations = [
        migrations.AddField(
            model_name="assistantconversation",
            name="title_access_requirements",
            field=models.JSONField(default=api.assistant.models.default_assistant_access_requirements),
        ),
        migrations.AddField(
            model_name="assistantconversation",
            name="title_source",
            field=models.CharField(default="legacy_unknown", max_length=32),
        ),
        migrations.AddField(
            model_name="assistantconversationsummary",
            name="access_requirements",
            field=models.JSONField(default=api.assistant.models.default_assistant_access_requirements),
        ),
        migrations.AddField(
            model_name="assistantconversationsummary",
            name="memory_partition",
            field=models.CharField(blank=True, max_length=128, null=True),
        ),
        migrations.AddField(
            model_name="assistantgeneration",
            name="access_requirements",
            field=models.JSONField(default=api.assistant.models.default_assistant_access_requirements),
        ),
        migrations.AddField(
            model_name="assistantgeneration",
            name="execution_metadata",
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name="assistantgeneration",
            name="memory_partition",
            field=models.CharField(blank=True, default="", max_length=128),
        ),
        migrations.AddField(
            model_name="assistantgeneration",
            name="profile_key",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="assistantgeneration",
            name="profile_version",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="assistantgeneration",
            name="request_hash",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="assistantgeneration",
            name="tool_inputs",
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name="assistantgeneration",
            name="tool_keys",
            field=models.JSONField(default=list),
        ),
        migrations.AddField(
            model_name="assistantmessage",
            name="access_requirements",
            field=models.JSONField(default=api.assistant.models.default_assistant_access_requirements),
        ),
        migrations.AddField(
            model_name="assistantmessage",
            name="blocks",
            field=models.JSONField(default=list),
        ),
        migrations.RunPython(lock_legacy_provenance, migrations.RunPython.noop),
    ]
