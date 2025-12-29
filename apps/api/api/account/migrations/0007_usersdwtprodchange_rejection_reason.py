from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0006_shorten_external_affiliation_snapshot_indexes"),
    ]

    operations = [
        migrations.AddField(
            model_name="usersdwtprodchange",
            name="rejection_reason",
            field=models.TextField(blank=True, null=True),
        ),
    ]
