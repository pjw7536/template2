from __future__ import annotations

from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ("drone", "0005_drone_sop_sop_key"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="dronesop",
            index=models.Index(
                fields=["id"],
                name="drone_sop_jira_pending",
                condition=Q(send_jira=0, needtosend=1, status="COMPLETE"),
            ),
        ),
    ]
