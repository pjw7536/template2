from django.db import migrations, models


class Migration(migrations.Migration):
    """기존 interlock_no 중복을 정리하고 unique constraint를 추가합니다."""

    dependencies = [
        ("m_interlock", "0003_alter_minterlock_lot_id"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                DELETE FROM m_interlock AS target
                USING (
                    SELECT id
                    FROM (
                        SELECT
                            id,
                            ROW_NUMBER() OVER (
                                PARTITION BY interlock_no
                                ORDER BY
                                    last_update_date DESC NULLS LAST,
                                    id DESC
                            ) AS duplicate_order
                        FROM m_interlock
                        WHERE interlock_no IS NOT NULL
                    ) AS ranked
                    WHERE ranked.duplicate_order > 1
                ) AS duplicates
                WHERE target.id = duplicates.id
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.AddConstraint(
            model_name="minterlock",
            constraint=models.UniqueConstraint(
                fields=("interlock_no",),
                name="uniq_m_intlk_no",
            ),
        ),
    ]
