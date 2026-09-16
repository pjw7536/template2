from django.db import migrations


class Migration(migrations.Migration):
    """기존 EQP 원천 시간을 KST 벽시계 기준 UTC instant로 보정합니다."""

    dependencies = [
        ("eqp_status_chg", "0002_lookup_index"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                UPDATE eqp_status_chg
                SET
                    chg_time = chg_time - INTERVAL '9 hours',
                    last_update_time = last_update_time - INTERVAL '9 hours'
            """,
            reverse_sql="""
                UPDATE eqp_status_chg
                SET
                    chg_time = chg_time + INTERVAL '9 hours',
                    last_update_time = last_update_time + INTERVAL '9 hours'
            """,
        ),
    ]
