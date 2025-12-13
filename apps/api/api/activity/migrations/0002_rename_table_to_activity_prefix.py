from __future__ import annotations

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0014_split_models_by_feature"),
        ("activity", "0001_initial"),
    ]

    operations = [
        migrations.AlterModelTable(
            name="ActivityLog",
            table="activity_log",
        ),
    ]

