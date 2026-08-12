# Django 5.2.14 기준으로 2026-08-12에 작성

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("drone", "0004_dronesoptargetmapping_needtosend_without_comment"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                UPDATE drone_sop
                   SET eqp_id_lookup = UPPER(NULLIF(TRIM(eqp_id), ''))
                 WHERE eqp_id_lookup IS DISTINCT FROM UPPER(NULLIF(TRIM(eqp_id), ''))
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
