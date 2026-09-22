from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ct_process_comment", "0005_summary_batch_index"),
    ]

    operations = [
        migrations.AddField(
            model_name="ctprocesscomment",
            name="summary_last_error",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="ctprocesscomment",
            name="summary_last_error_code",
            field=models.CharField(blank=True, max_length=32, null=True),
        ),
        migrations.AddField(
            model_name="ctprocesscomment",
            name="summary_retry_count",
            field=models.PositiveSmallIntegerField(default=0),
        ),
    ]
