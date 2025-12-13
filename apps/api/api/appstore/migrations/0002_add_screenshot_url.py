from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("appstore", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="appstoreapp",
            name="screenshot_url",
            field=models.TextField(blank=True, default=""),
        ),
    ]

