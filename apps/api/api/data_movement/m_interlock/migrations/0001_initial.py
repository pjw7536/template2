"""m_interlock 원천 및 적재 이력 테이블을 생성합니다."""

from __future__ import annotations

import django.db.models.functions.datetime
from django.db import migrations, models

import api.data_movement.common.models


class Migration(migrations.Migration):
    """m_interlock 앱의 초기 schema를 생성합니다."""

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="MInterlock",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("line_id", models.CharField(blank=True, max_length=10, null=True)),
                ("interlock_no", models.CharField(blank=True, max_length=100, null=True)),
                ("item_value", models.CharField(blank=True, max_length=200, null=True)),
                ("interlock_type", models.CharField(blank=True, max_length=30, null=True)),
                ("interlock_comment", models.CharField(blank=True, max_length=2000, null=True)),
                ("ppid", models.CharField(blank=True, max_length=255, null=True)),
                ("usl", api.data_movement.common.models.UnboundedNumericField(blank=True, null=True)),
                ("spec_target", api.data_movement.common.models.UnboundedNumericField(blank=True, null=True)),
                ("lsl", api.data_movement.common.models.UnboundedNumericField(blank=True, null=True)),
                ("ucl", api.data_movement.common.models.UnboundedNumericField(blank=True, null=True)),
                ("cl", api.data_movement.common.models.UnboundedNumericField(blank=True, null=True)),
                ("lcl", api.data_movement.common.models.UnboundedNumericField(blank=True, null=True)),
                ("batch_id", models.CharField(blank=True, max_length=50, null=True)),
                ("metro_item", models.CharField(blank=True, max_length=128, null=True)),
                ("interlock_desc", models.CharField(blank=True, max_length=200, null=True)),
                ("area_name", models.CharField(blank=True, max_length=12, null=True)),
                ("process_id", models.CharField(blank=True, max_length=16, null=True)),
                ("interlock_kind", models.CharField(blank=True, max_length=30, null=True)),
                ("lot_id", models.CharField(blank=True, max_length=40, null=True)),
                ("prod_step_seq", models.CharField(blank=True, max_length=20, null=True)),
                ("prod_progs_time", models.CharField(blank=True, max_length=18, null=True)),
                ("prod_eqp_type", models.CharField(blank=True, max_length=40, null=True)),
                ("prod_bay_name", models.CharField(blank=True, max_length=10, null=True)),
                ("prod_chamber_id", models.CharField(blank=True, max_length=50, null=True)),
                ("metro_step_seq", models.CharField(blank=True, max_length=16, null=True)),
                ("metro_progs_time", models.CharField(blank=True, max_length=18, null=True)),
                ("intlk_occur_week", models.CharField(blank=True, max_length=8, null=True)),
                ("intlk_occur_year_m", models.CharField(blank=True, max_length=8, null=True)),
                ("metro_eqp_id", models.CharField(blank=True, max_length=40, null=True)),
                ("prod_eqp_id", models.CharField(blank=True, max_length=40, null=True)),
                ("last_update_date", models.DateTimeField(blank=True, null=True)),
                ("wafer_id", models.CharField(blank=True, max_length=45, null=True)),
                ("eqp_process_phase", models.CharField(blank=True, max_length=50, null=True)),
                ("eqp_detail_comment", models.CharField(blank=True, max_length=255, null=True)),
                ("engr_comment", models.CharField(blank=True, max_length=500, null=True)),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True,
                        db_default=django.db.models.functions.datetime.Now(),
                    ),
                ),
            ],
            options={"db_table": "m_interlock"},
        ),
        migrations.CreateModel(
            name="MInterlockLoadJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("file_name", models.TextField()),
                ("file_path", models.TextField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("running", "Running"),
                            ("success", "Success"),
                            ("failed", "Failed"),
                            ("dry_run", "Dry run"),
                        ],
                        default="running",
                        max_length=16,
                    ),
                ),
                ("row_count", models.PositiveIntegerField(blank=True, null=True)),
                ("error_message", models.TextField(blank=True, null=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True,
                        db_default=django.db.models.functions.datetime.Now(),
                    ),
                ),
            ],
            options={
                "db_table": "m_interlock_load_job",
                "indexes": [
                    models.Index(fields=["status"], name="idx_m_intlk_job_sts"),
                    models.Index(fields=["created_at"], name="idx_m_intlk_job_crt"),
                ],
            },
        ),
    ]
