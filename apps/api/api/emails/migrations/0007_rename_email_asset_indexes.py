from __future__ import annotations

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("emails", "0006_email_asset_ocr_queue_fields"),
    ]

    operations = [
        migrations.RenameIndex(
            model_name="emailasset",
            old_name="idx_emails_email_asset_ocr_status",
            new_name="idx_emails_asset_ocr_status",
        ),
        migrations.RenameIndex(
            model_name="emailasset",
            old_name="idx_emails_email_asset_ocr_lock_expires_at",
            new_name="idx_emails_asset_ocr_lock",
        ),
    ]
