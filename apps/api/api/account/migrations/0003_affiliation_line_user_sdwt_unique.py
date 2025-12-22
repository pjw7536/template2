from __future__ import annotations

from django.db import migrations, models
from django.db.models import Count, Min


def dedupe_affiliation_line_sdwt(apps, schema_editor) -> None:
    Affiliation = apps.get_model("account", "Affiliation")

    duplicates = (
        Affiliation.objects.values("line", "user_sdwt_prod")
        .annotate(count=Count("id"), keep_id=Min("id"))
        .filter(count__gt=1)
    )
    for entry in duplicates:
        line = entry.get("line")
        user_sdwt_prod = entry.get("user_sdwt_prod")
        keep_id = entry.get("keep_id")
        if line is None or user_sdwt_prod is None or keep_id is None:
            continue
        Affiliation.objects.filter(line=line, user_sdwt_prod=user_sdwt_prod).exclude(id=keep_id).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0002_affiliation_jira_key"),
    ]

    operations = [
        migrations.RunPython(dedupe_affiliation_line_sdwt, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="affiliation",
            constraint=models.UniqueConstraint(
                fields=("line", "user_sdwt_prod"),
                name="uniq_aff_line_user_sdwt",
            ),
        ),
        migrations.AddIndex(
            model_name="affiliation",
            index=models.Index(fields=["line", "user_sdwt_prod"], name="aff_line_user_sdwt"),
        ),
    ]
