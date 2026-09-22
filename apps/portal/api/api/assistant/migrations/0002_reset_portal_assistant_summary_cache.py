"""Portal Assistant 기억 통합 전 rolling summary cache를 초기화합니다."""

from django.db import migrations


LEGACY_SUMMARY_CONTEXT_KEYS = (
    "assistant",
    "chatwidget:shared",
)


def reset_portal_assistant_summary_cache(apps, _schema_editor):
    """통합 후 위치 기준이 달라진 기존 summary row만 삭제합니다.

    원본 대화와 메시지는 유지하며, 삭제된 요약은 이후 summary 갱신 요청에서
    통합된 메시지 집합을 기준으로 다시 생성됩니다.
    """

    AssistantConversationSummary = apps.get_model(
        "assistant",
        "AssistantConversationSummary",
    )
    AssistantConversationSummary.objects.filter(
        context_key__in=LEGACY_SUMMARY_CONTEXT_KEYS,
    ).delete()


class Migration(migrations.Migration):
    """Portal Assistant 공용 기억 전환을 위한 data migration입니다."""

    dependencies = [
        ("assistant", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            reset_portal_assistant_summary_cache,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
