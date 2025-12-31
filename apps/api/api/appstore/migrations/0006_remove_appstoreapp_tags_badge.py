from __future__ import annotations

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("appstore", "0005_appstoreapp_screenshot_gallery"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="appstoreapp",
            name="badge",
        ),
        migrations.RemoveField(
            model_name="appstoreapp",
            name="tags",
        ),
    ]
