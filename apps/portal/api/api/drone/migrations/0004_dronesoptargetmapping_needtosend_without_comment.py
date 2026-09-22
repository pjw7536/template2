# Django 5.2.14가 2026-07-14에 생성

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("drone", "0003_dronesop_lookup_index"),
    ]

    operations = [
        migrations.AddField(
            model_name="dronesoptargetmapping",
            name="needtosend_without_comment",
            field=models.BooleanField(default=False),
        ),
    ]
