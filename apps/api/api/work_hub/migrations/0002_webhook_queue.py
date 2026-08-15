import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("work_hub", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="gristwebhookreceipt",
            name="available_at",
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AddField(
            model_name="gristwebhookreceipt",
            name="payload",
            field=models.JSONField(default=dict),
        ),
        migrations.AlterField(
            model_name="gristwebhookreceipt",
            name="status",
            field=models.CharField(
                choices=[
                    ("received", "Received"),
                    ("processing", "Processing"),
                    ("done", "Done"),
                    ("failed", "Failed"),
                    ("terminal", "Terminal"),
                ],
                default="received",
                max_length=16,
            ),
        ),
        migrations.AddIndex(
            model_name="gristwebhookreceipt",
            index=models.Index(
                fields=["status", "available_at"],
                name="idx_wrk_hub_hook_sts_avl",
            ),
        ),
    ]
