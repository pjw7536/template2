from __future__ import annotations

from django.db import migrations


UNASSIGNED = "UNASSIGNED"
LEGACY_UNCLASSIFIED = "rp-unclassified"


def normalize_unassigned_mailbox(apps, schema_editor) -> None:
    Email = apps.get_model("emails", "Email")
    Email.objects.filter(user_sdwt_prod__isnull=True).update(user_sdwt_prod=UNASSIGNED)
    Email.objects.filter(user_sdwt_prod__exact="").update(user_sdwt_prod=UNASSIGNED)
    Email.objects.filter(user_sdwt_prod=LEGACY_UNCLASSIFIED).update(user_sdwt_prod=UNASSIGNED)


class Migration(migrations.Migration):
    dependencies = [
        ("emails", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(normalize_unassigned_mailbox, migrations.RunPython.noop),
    ]

