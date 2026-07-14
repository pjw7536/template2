# Django 5.2.14에서 2026-07-14 00:28에 생성했습니다.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("l3_spider", "0006_l3spiderlinenamerule"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="l3spiderlinenamerule",
            options={
                "ordering": ["priority", "id"],
                "permissions": [
                    ("view_developer_options", "L3 Spider 개발자 옵션 조회"),
                ],
            },
        ),
    ]
