from __future__ import annotations

from django.db import migrations


def migrate_user_fields(apps, schema_editor) -> None:
    User = apps.get_model("account", "User")
    for user in User.objects.all().only(
        "id",
        "first_name",
        "last_name",
        "email",
        "department",
        "firstname",
        "lastname",
        "mail",
        "deptname",
    ):
        update_fields = []

        if not user.first_name and user.firstname:
            user.first_name = user.firstname
            update_fields.append("first_name")

        if not user.last_name and user.lastname:
            user.last_name = user.lastname
            update_fields.append("last_name")

        if not user.email and user.mail:
            user.email = user.mail
            update_fields.append("email")

        if not user.department and user.deptname:
            user.department = user.deptname
            update_fields.append("department")

        if update_fields:
            user.save(update_fields=update_fields)


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0004_external_affiliation_snapshot_and_status"),
    ]

    operations = [
        migrations.RunPython(migrate_user_fields, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="user",
            name="firstname",
        ),
        migrations.RemoveField(
            model_name="user",
            name="lastname",
        ),
        migrations.RemoveField(
            model_name="user",
            name="mail",
        ),
        migrations.RemoveField(
            model_name="user",
            name="deptname",
        ),
        migrations.RemoveField(
            model_name="user",
            name="x_ms_forwarded_client_ip",
        ),
    ]
