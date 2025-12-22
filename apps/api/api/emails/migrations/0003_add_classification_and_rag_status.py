from __future__ import annotations

from django.db import migrations, models
from django.db.models import Q


def backfill_email_classification(apps, schema_editor) -> None:
    Email = apps.get_model("emails", "Email")

    unassigned_query = (
        Q(user_sdwt_prod__isnull=True)
        | Q(user_sdwt_prod__exact="")
        | Q(user_sdwt_prod="UNASSIGNED")
        | Q(user_sdwt_prod="rp-unclassified")
    )

    Email.objects.filter(unassigned_query).update(
        classification_source="UNASSIGNED",
        rag_index_status="SKIPPED",
    )
    Email.objects.exclude(unassigned_query).update(
        classification_source="CONFIRMED_USER",
    )
    Email.objects.exclude(unassigned_query).filter(
        Q(rag_doc_id__isnull=True) | Q(rag_doc_id="")
    ).update(rag_index_status="PENDING")
    Email.objects.exclude(unassigned_query).exclude(
        Q(rag_doc_id__isnull=True) | Q(rag_doc_id="")
    ).update(rag_index_status="INDEXED")


class Migration(migrations.Migration):
    dependencies = [
        ("emails", "0002_email_cc_participants_search"),
    ]

    operations = [
        migrations.AddField(
            model_name="email",
            name="classification_source",
            field=models.CharField(
                choices=[
                    ("CONFIRMED_USER", "Confirmed User"),
                    ("PREDICTED_EXTERNAL", "Predicted External"),
                    ("UNASSIGNED", "Unassigned"),
                ],
                default="UNASSIGNED",
                max_length=24,
            ),
        ),
        migrations.AddField(
            model_name="email",
            name="rag_index_status",
            field=models.CharField(
                choices=[("PENDING", "Pending"), ("INDEXED", "Indexed"), ("SKIPPED", "Skipped")],
                default="SKIPPED",
                max_length=16,
            ),
        ),
        migrations.RunPython(
            backfill_email_classification,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
