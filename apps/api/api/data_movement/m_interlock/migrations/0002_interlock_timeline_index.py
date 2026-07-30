from django.db import migrations, models
from django.db.models.functions import Trim, Upper


class Migration(migrations.Migration):
    """Observer interlock 이력 조회용 복합 표현식 인덱스를 추가합니다."""

    dependencies = [
        ("m_interlock", "0001_initial"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="minterlock",
            index=models.Index(
                Upper(Trim("prod_eqp_id")),
                Upper(Trim("interlock_kind")),
                "prod_progs_time",
                name="idx_m_intlk_prd_kind_ptm",
            ),
        ),
    ]
