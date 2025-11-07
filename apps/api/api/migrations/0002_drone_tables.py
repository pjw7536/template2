from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="DroneSOPV3",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("line_id", models.CharField(blank=True, max_length=50, null=True)),
                ("sdwt_prod", models.CharField(blank=True, max_length=50, null=True)),
                ("sample_type", models.CharField(blank=True, max_length=50, null=True)),
                ("sample_group", models.CharField(blank=True, max_length=50, null=True)),
                ("eqp_id", models.CharField(blank=True, max_length=50, null=True)),
                ("chamber_ids", models.CharField(blank=True, max_length=50, null=True)),
                ("lot_id", models.CharField(blank=True, max_length=50, null=True)),
                ("proc_id", models.CharField(blank=True, max_length=50, null=True)),
                ("ppid", models.CharField(blank=True, max_length=50, null=True)),
                ("main_step", models.CharField(blank=True, max_length=50, null=True)),
                ("metro_current_step", models.CharField(blank=True, max_length=50, null=True)),
                ("metro_steps", models.CharField(blank=True, max_length=100, null=True)),
                ("metro_end_step", models.CharField(blank=True, max_length=50, null=True)),
                ("status", models.CharField(blank=True, max_length=50, null=True)),
                ("knoxid", models.CharField(blank=True, max_length=50, null=True)),
                ("comment", models.TextField(blank=True, null=True)),
                ("user_sdwt_prod", models.CharField(blank=True, max_length=50, null=True)),
                ("defect_url", models.TextField(blank=True, null=True)),
                ("send_jira", models.BooleanField(default=False)),
                ("needtosend", models.BooleanField(default=True)),
                ("custom_end_step", models.CharField(blank=True, max_length=50, null=True)),
                ("inform_step", models.CharField(blank=True, max_length=50, null=True)),
                ("jira_key", models.CharField(blank=True, max_length=50, null=True)),
                ("informed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "drone_sop_v3",
                "indexes": [
                    models.Index(fields=["send_jira", "needtosend"], name="send_jira_needtosend"),
                    models.Index(fields=["sdwt_prod"], name="sdwt_prod"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=["line_id", "eqp_id", "chamber_ids", "lot_id", "main_step"], name="uniq_row"),
                ],
            },
        ),
        migrations.CreateModel(
            name="DroneEarlyInformV3",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("line_id", models.CharField(max_length=50)),
                ("main_step", models.CharField(max_length=50)),
                ("custom_end_step", models.CharField(blank=True, max_length=50, null=True)),
            ],
            options={
                "db_table": "drone_early_inform_v3",
                "constraints": [
                    models.UniqueConstraint(fields=["line_id", "main_step"], name="uniq_line_mainstep"),
                ],
            },
        ),
        migrations.CreateModel(
            name="LineSDWT",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("line_id", models.CharField(blank=True, max_length=50, null=True)),
                ("user_sdwt_prod", models.CharField(blank=True, max_length=50, null=True)),
            ],
            options={
                "db_table": "line_sdwt",
            },
        ),
    ]
