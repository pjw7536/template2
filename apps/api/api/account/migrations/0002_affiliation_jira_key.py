from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="affiliation",
            name="jira_key",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
    ]
