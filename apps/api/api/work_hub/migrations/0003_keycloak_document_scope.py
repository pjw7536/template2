from django.db import migrations, models


def copy_affiliation_snapshot(apps, schema_editor):
    GristDocumentScope = apps.get_model("work_hub", "GristDocumentScope")
    for scope in GristDocumentScope.objects.select_related("affiliation").iterator():
        affiliation = scope.affiliation
        scope.keycloak_group_id = f"legacy-affiliation:{scope.affiliation_id}"
        scope.affiliation_snapshot = {
            "department": affiliation.department,
            "line": affiliation.line,
            "name": affiliation.user_sdwt_prod,
        }
        scope.save(update_fields=["keycloak_group_id", "affiliation_snapshot"])
class Migration(migrations.Migration):
    dependencies = [
        ("account", "0007_user_keycloak_shadow"),
        ("work_hub", "0002_webhook_queue"),
    ]

    operations = [
        migrations.AddField(
            model_name="gristdocumentscope",
            name="affiliation_snapshot",
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name="gristdocumentscope",
            name="keycloak_group_id",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="gristdocumentscope",
            name="keycloak_last_success_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(copy_affiliation_snapshot, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="gristdocumentscope",
            name="uniq_wrk_hub_doc_scp_aff",
        ),
        migrations.RemoveField(model_name="gristdocumentscope", name="affiliation"),
        migrations.AlterField(
            model_name="gristdocumentscope",
            name="keycloak_group_id",
            field=models.CharField(max_length=255, unique=True),
        ),
    ]
