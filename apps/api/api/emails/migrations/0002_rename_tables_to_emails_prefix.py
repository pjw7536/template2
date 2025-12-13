from __future__ import annotations

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0014_split_models_by_feature"),
        ("emails", "0001_initial"),
    ]

    operations = [
        migrations.AlterModelTable(
            name="Email",
            table="emails_inbox",
        ),
        migrations.AlterModelTable(
            name="SenderSdwtHistory",
            table="emails_sender_sdwt_history",
        ),
    ]

