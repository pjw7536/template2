from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0002_add_drone_sop_v3_indexes"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="linesdwt",
            index=models.Index(
                fields=["line_id", "user_sdwt_prod"],
                name="line_sdwt_line_user_sdwt",
            ),
        ),
    ]
