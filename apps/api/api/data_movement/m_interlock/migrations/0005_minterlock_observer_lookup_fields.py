from django.contrib.postgres.operations import (
    AddIndexConcurrently,
    RemoveIndexConcurrently,
)
from django.db import migrations, models


class Migration(migrations.Migration):
    """Observer 대용량 조회용 정규화 필드와 keyset 인덱스를 추가합니다."""

    atomic = False

    dependencies = [
        ("m_interlock", "0004_minterlock_interlock_no_unique"),
    ]

    operations = [
        migrations.AddField(
            model_name="minterlock",
            name="prod_eqp_id_lookup",
            field=models.CharField(blank=True, max_length=40, null=True),
        ),
        migrations.AddField(
            model_name="minterlock",
            name="interlock_kind_lookup",
            field=models.CharField(blank=True, max_length=30, null=True),
        ),
        migrations.AddField(
            model_name="minterlock",
            name="prod_progs_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        AddIndexConcurrently(
            model_name="minterlock",
            index=models.Index(
                fields=[
                    "prod_eqp_id_lookup",
                    "interlock_kind_lookup",
                    "-prod_progs_at",
                    "-id",
                ],
                name="idx_m_intlk_obs_page",
            ),
        ),
        RemoveIndexConcurrently(
            model_name="minterlock",
            name="idx_m_intlk_prd_kind_ptm",
        ),
    ]
