from __future__ import annotations

from django.db import migrations, models
from django.db.models import Count, Min


def _build_sop_key(*, line_id: str | None, eqp_id: str | None, chamber_ids: str | None, lot_id: str | None, main_step: str | None) -> str:
    def _normalize(value: str | None) -> str:
        if value is None:
            return ""
        return str(value).strip()

    return "|".join(
        [
            _normalize(line_id),
            _normalize(eqp_id),
            _normalize(chamber_ids),
            _normalize(lot_id),
            _normalize(main_step),
        ]
    )


def backfill_sop_key(apps, schema_editor) -> None:
    DroneSOP = apps.get_model("drone", "DroneSOP")

    rows = DroneSOP.objects.all().values(
        "id",
        "line_id",
        "eqp_id",
        "chamber_ids",
        "lot_id",
        "main_step",
    )
    for row in rows.iterator():
        sop_key = _build_sop_key(
            line_id=row.get("line_id"),
            eqp_id=row.get("eqp_id"),
            chamber_ids=row.get("chamber_ids"),
            lot_id=row.get("lot_id"),
            main_step=row.get("main_step"),
        )
        DroneSOP.objects.filter(id=row["id"]).update(sop_key=sop_key)

    duplicates = (
        DroneSOP.objects.values("sop_key")
        .annotate(count=Count("id"), keep_id=Min("id"))
        .filter(count__gt=1)
    )
    for entry in duplicates:
        sop_key = entry.get("sop_key")
        keep_id = entry.get("keep_id")
        if sop_key is None or keep_id is None:
            continue
        DroneSOP.objects.filter(sop_key=sop_key).exclude(id=keep_id).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("drone", "0004_drone_sop_jira_user_template"),
    ]

    operations = [
        migrations.AddField(
            model_name="dronesop",
            name="sop_key",
            field=models.CharField(blank=True, max_length=300, null=True),
        ),
        migrations.RunPython(backfill_sop_key, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="dronesop",
            name="sop_key",
            field=models.CharField(max_length=300, unique=True),
        ),
    ]
