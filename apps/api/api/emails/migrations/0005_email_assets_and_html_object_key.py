from __future__ import annotations

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("emails", "0004_email_outbox"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="email",
            name="body_html_gzip",
        ),
        migrations.AddField(
            model_name="email",
            name="body_html_object_key",
            field=models.CharField(blank=True, max_length=512, null=True),
        ),
        migrations.CreateModel(
            name="EmailAsset",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sequence", models.PositiveIntegerField()),
                ("object_key", models.CharField(blank=True, max_length=512, null=True)),
                ("content_type", models.CharField(blank=True, max_length=128, null=True)),
                ("byte_size", models.PositiveIntegerField(blank=True, null=True)),
                (
                    "source",
                    models.CharField(
                        choices=[
                            ("CID", "CID"),
                            ("DATA_URL", "Data URL"),
                            ("EXTERNAL_URL", "External URL"),
                        ],
                        max_length=16,
                    ),
                ),
                ("original_url", models.TextField(blank=True, null=True)),
                (
                    "ocr_status",
                    models.CharField(
                        choices=[("PENDING", "Pending"), ("DONE", "Done"), ("FAILED", "Failed")],
                        default="PENDING",
                        max_length=16,
                    ),
                ),
                ("ocr_text", models.TextField(blank=True)),
                ("ocr_error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "email",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="assets",
                        to="emails.email",
                    ),
                ),
            ],
            options={
                "db_table": "emails_email_asset",
            },
        ),
        migrations.AddIndex(
            model_name="emailasset",
            index=models.Index(fields=["email"], name="idx_emails_email_asset_email"),
        ),
        migrations.AddIndex(
            model_name="emailasset",
            index=models.Index(fields=["ocr_status"], name="idx_emails_email_asset_ocr_status"),
        ),
        migrations.AddConstraint(
            model_name="emailasset",
            constraint=models.UniqueConstraint(
                fields=["email", "sequence"],
                name="uniq_emails_email_asset_email_sequence",
            ),
        ),
    ]
