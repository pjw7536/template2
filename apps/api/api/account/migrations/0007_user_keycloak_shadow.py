from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("account", "0006_account_authorization_system")]

    operations = [
        migrations.AddField(
            model_name="user",
            name="affiliation_snapshot",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="user",
            name="keycloak_client_roles",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="user",
            name="keycloak_group_id",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="user",
            name="keycloak_groups",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="user",
            name="keycloak_realm_roles",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="user",
            name="keycloak_subject",
            field=models.CharField(blank=True, max_length=255, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="user",
            name="keycloak_synced_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
