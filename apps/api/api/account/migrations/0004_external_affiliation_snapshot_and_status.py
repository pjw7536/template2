from __future__ import annotations

from django.db import migrations, models


def backfill_user_sdwt_prod_change_status(apps, schema_editor) -> None:
    Change = apps.get_model("account", "UserSdwtProdChange")
    Change.objects.filter(approved=True).update(status="APPROVED")
    Change.objects.filter(approved=False).update(status="PENDING")


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0003_affiliation_line_user_sdwt_unique"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="requires_affiliation_reconfirm",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="user",
            name="affiliation_confirmed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="usersdwtprodchange",
            name="status",
            field=models.CharField(
                choices=[
                    ("PENDING", "Pending"),
                    ("APPROVED", "Approved"),
                    ("REJECTED", "Rejected"),
                ],
                default="PENDING",
                max_length=16,
            ),
        ),
        migrations.CreateModel(
            name="ExternalAffiliationSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("knox_id", models.CharField(max_length=150, unique=True)),
                ("predicted_user_sdwt_prod", models.CharField(max_length=64)),
                ("source_updated_at", models.DateTimeField()),
                ("last_seen_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "account_external_affiliation_snapshot",
            },
        ),
        migrations.AddIndex(
            model_name="externalaffiliationsnapshot",
            index=models.Index(
                fields=["predicted_user_sdwt_prod"],
                name="idx_account_external_affiliation_snapshot_user_sdwt_prod",
            ),
        ),
        migrations.AddIndex(
            model_name="externalaffiliationsnapshot",
            index=models.Index(
                fields=["source_updated_at"],
                name="idx_account_external_affiliation_snapshot_source_updated_at",
            ),
        ),
        migrations.RunPython(
            backfill_user_sdwt_prod_change_status,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
