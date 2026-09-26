"""새 Portal DB에서 EPID 식별자와 마지막 로그인 프로필을 사용합니다."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("account", "0007_separate_affiliation_access")]
    operations = [
        migrations.AlterField(model_name="user", name="avatarid", field=models.CharField(max_length=50, unique=True)),
        migrations.AddField(model_name="user", name="identity_profile", field=models.JSONField(blank=True, default=dict)),
    ]
