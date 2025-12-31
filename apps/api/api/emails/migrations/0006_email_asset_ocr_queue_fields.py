from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("emails", "0005_email_assets_and_html_object_key"),
    ]

    operations = [
        migrations.AddField(
            model_name="emailasset",
            name="ocr_lock_token",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name="emailasset",
            name="ocr_lock_expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="emailasset",
            name="ocr_worker_id",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name="emailasset",
            name="ocr_attempt_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="emailasset",
            name="ocr_attempted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="emailasset",
            name="ocr_completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="emailasset",
            name="ocr_error_code",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name="emailasset",
            name="ocr_error_message",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="emailasset",
            name="ocr_model",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name="emailasset",
            name="ocr_duration_ms",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="emailasset",
            name="ocr_status",
            field=models.CharField(
                choices=[
                    ("PENDING", "Pending"),
                    ("PROCESSING", "Processing"),
                    ("DONE", "Done"),
                    ("FAILED", "Failed"),
                ],
                default="PENDING",
                max_length=16,
            ),
        ),
        migrations.AddIndex(
            model_name="emailasset",
            index=models.Index(
                fields=["ocr_lock_expires_at"],
                name="idx_emails_email_asset_ocr_lock_expires_at",
            ),
        ),
    ]
