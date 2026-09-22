from django.db import migrations


DEVELOPER_PERMISSION_CODENAME = "view_developer_options"


def remove_developer_options_permission(apps, _schema_editor):
    """역할 기반 권한으로 대체된 legacy 개발자 permission을 제거합니다."""

    Permission = apps.get_model("auth", "Permission")
    Permission.objects.filter(
        content_type__app_label="l3_spider",
        codename=DEVELOPER_PERMISSION_CODENAME,
    ).delete()


def restore_developer_options_permission(apps, _schema_editor):
    """역방향 migration에서 legacy 개발자 permission을 복구합니다."""

    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")

    content_type = ContentType.objects.get(
        app_label="l3_spider",
        model="l3spiderlinenamerule",
    )
    Permission.objects.get_or_create(
        content_type=content_type,
        codename=DEVELOPER_PERMISSION_CODENAME,
        defaults={"name": "L3 Spider 개발자 옵션 조회"},
    )


class Migration(migrations.Migration):

    dependencies = [
        ("l3_spider", "0007_alter_l3spiderlinenamerule_options"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="l3spiderlinenamerule",
            options={"ordering": ["priority", "id"]},
        ),
        migrations.RunPython(
            remove_developer_options_permission,
            restore_developer_options_permission,
        ),
    ]
