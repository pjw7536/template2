from __future__ import annotations

from django.db import migrations, models


def _split_korean_name(display_name: str) -> tuple[str, str]:
    name = (display_name or "").strip()
    if not name:
        return "", ""
    if " " in name:
        parts = name.split()
        if len(parts) == 1:
            return parts[0], ""
        return parts[0], " ".join(parts[1:])
    if len(name) == 1:
        return name, ""
    return name[0], name[1:]


def populate_user_name_fields(apps, schema_editor) -> None:
    from django.db.models import F, Q

    User = apps.get_model("account", "User")

    User.objects.filter(Q(sabun__isnull=True) | Q(sabun="")).update(sabun=F("username"))

    User.objects.filter(adfs_username__isnull=False).exclude(adfs_username="").update(
        username=F("adfs_username")
    )

    users = (
        User.objects.filter(adfs_username__isnull=False)
        .exclude(adfs_username="")
        .filter(Q(firstname__isnull=True) | Q(firstname="") | Q(lastname__isnull=True) | Q(lastname=""))
        .only("id", "adfs_username", "firstname", "lastname")
    )
    for user in users:
        family_name, given_name = _split_korean_name(getattr(user, "adfs_username", "") or "")
        update_fields: list[str] = []
        if family_name and not (user.lastname or "").strip():
            user.lastname = family_name
            update_fields.append("lastname")
        if given_name and not (user.firstname or "").strip():
            user.firstname = given_name
            update_fields.append("firstname")
        if update_fields:
            user.save(update_fields=update_fields)


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0003_add_user_adfs_claim_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="username",
            field=models.CharField(blank=True, max_length=150, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="firstname",
            field=models.CharField(blank=True, max_length=150, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="lastname",
            field=models.CharField(blank=True, max_length=150, null=True),
        ),
        migrations.RunPython(populate_user_name_fields, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="user",
            name="sabun",
            field=models.CharField(max_length=50, unique=True),
        ),
        migrations.RemoveField(
            model_name="user",
            name="adfs_username",
        ),
    ]

