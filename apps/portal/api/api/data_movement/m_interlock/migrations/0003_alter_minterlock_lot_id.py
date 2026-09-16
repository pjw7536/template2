from django.db import migrations, models


class Migration(migrations.Migration):
    """m_interlock lot_id를 길이 제한 없는 text로 확장합니다."""

    dependencies = [
        ("m_interlock", "0002_interlock_timeline_index"),
    ]

    operations = [
        migrations.AlterField(
            model_name="minterlock",
            name="lot_id",
            field=models.TextField(blank=True, null=True),
        ),
    ]
