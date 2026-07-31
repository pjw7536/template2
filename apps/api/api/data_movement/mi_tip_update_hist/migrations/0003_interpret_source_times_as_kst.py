from django.db import migrations


class Migration(migrations.Migration):
    """기존 TIP 원천 시간을 KST 벽시계 기준 UTC instant로 보정합니다."""

    dependencies = [
        ("mi_tip_update_hist", "0002_lookup_index"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                UPDATE mi_tip_update_hist
                SET
                    rule_pkg_update_date = rule_pkg_update_date - INTERVAL '9 hours',
                    gpm_update_date = gpm_update_date - INTERVAL '9 hours',
                    last_update_date = last_update_date - INTERVAL '9 hours'
            """,
            reverse_sql="""
                UPDATE mi_tip_update_hist
                SET
                    rule_pkg_update_date = rule_pkg_update_date + INTERVAL '9 hours',
                    gpm_update_date = gpm_update_date + INTERVAL '9 hours',
                    last_update_date = last_update_date + INTERVAL '9 hours'
            """,
        ),
    ]
