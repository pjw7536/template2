from django.db import migrations, models


def backfill_display_order(apps, schema_editor):
    """기존 최신순을 유지하도록 앱 노출 순서를 채웁니다."""

    AppStoreApp = apps.get_model("appstore", "AppStoreApp")
    ordered_apps = list(AppStoreApp.objects.order_by("-created_at", "-id").only("id"))
    for display_order, app in enumerate(ordered_apps, start=1):
        app.display_order = display_order
    if ordered_apps:
        AppStoreApp.objects.bulk_update(ordered_apps, ["display_order"])


class Migration(migrations.Migration):

    dependencies = [
        ("appstore", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="appstoreapp",
            name="display_order",
            field=models.PositiveIntegerField(null=True),
        ),
        migrations.RunPython(
            backfill_display_order,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="appstoreapp",
            name="display_order",
            field=models.PositiveIntegerField(),
        ),
        migrations.AlterModelOptions(
            name="appstoreapp",
            options={"ordering": ["display_order", "id"]},
        ),
        migrations.AddIndex(
            model_name="appstoreapp",
            index=models.Index(fields=["display_order"], name="idx_aps_app_dsp_ord"),
        ),
    ]
