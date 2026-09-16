from django.db import migrations, models


class Migration(migrations.Migration):
    """새 Run과 메시지가 명시적인 context provenance 없이 저장되지 않게 합니다."""

    dependencies = [("assistant", "0003_assistant_runtime_v2_schema")]

    operations = [
        migrations.AlterField(
            model_name="assistantgeneration",
            name="context_key",
            field=models.CharField(max_length=512),
        ),
        migrations.AlterField(
            model_name="assistantmessage",
            name="context_key",
            field=models.CharField(max_length=512),
        ),
    ]
