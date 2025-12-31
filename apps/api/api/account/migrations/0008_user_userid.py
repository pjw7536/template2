from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0007_usersdwtprodchange_rejection_reason"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="userid",
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
    ]
