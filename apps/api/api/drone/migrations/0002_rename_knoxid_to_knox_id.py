from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("drone", "0001_initial"),
    ]

    operations = [
        migrations.RenameField(
            model_name="dronesopv3",
            old_name="knoxid",
            new_name="knox_id",
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveIndex(
                    model_name="dronesopv3",
                    name="drone_sop_v3_knoxid",
                ),
                migrations.AddIndex(
                    model_name="dronesopv3",
                    index=models.Index(fields=["knox_id"], name="drone_sop_v3_knoxid"),
                ),
            ],
            database_operations=[],
        ),
    ]

