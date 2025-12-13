from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("api", "0013_affiliation_refactor"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name="Email",
                    fields=[
                        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                        ("message_id", models.CharField(max_length=255, unique=True)),
                        ("received_at", models.DateTimeField()),
                        ("subject", models.TextField()),
                        ("sender", models.TextField()),
                        ("sender_id", models.CharField(db_index=True, max_length=50)),
                        ("recipient", models.TextField()),
                        ("user_sdwt_prod", models.CharField(blank=True, db_index=True, max_length=64, null=True)),
                        ("body_text", models.TextField(blank=True)),
                        ("body_html_gzip", models.BinaryField(blank=True, null=True)),
                        ("rag_doc_id", models.CharField(blank=True, max_length=255, null=True, unique=True)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                    ],
                    options={
                        "db_table": "email",
                    },
                ),
                migrations.CreateModel(
                    name="SenderSdwtHistory",
                    fields=[
                        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                        ("sender_id", models.CharField(db_index=True, max_length=50)),
                        ("effective_from", models.DateTimeField()),
                        ("department", models.CharField(blank=True, max_length=50, null=True)),
                        ("line", models.CharField(blank=True, max_length=64, null=True)),
                        ("user_sdwt_prod", models.CharField(blank=True, max_length=64, null=True)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("created_by", models.CharField(default="", max_length=50)),
                    ],
                    options={
                        "db_table": "sender_sdwt_history",
                        "unique_together": {("sender_id", "effective_from")},
                        "indexes": [
                            models.Index(fields=["sender_id", "effective_from"], name="sender_sdwt_effective"),
                            models.Index(fields=["user_sdwt_prod"], name="sender_sdwt_user_sdwt"),
                        ],
                    },
                ),
            ],
            database_operations=[],
        ),
    ]

