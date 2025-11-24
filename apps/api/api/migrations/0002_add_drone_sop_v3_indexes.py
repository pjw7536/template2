from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0001_initial"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="dronesopv3",
            index=models.Index(
                fields=["created_at", "id"],
                name="drone_sop_v3_created_at_id",
            ),
        ),
        migrations.AddIndex(
            model_name="dronesopv3",
            index=models.Index(
                fields=["user_sdwt_prod", "created_at", "id"],
                name="dsopv3_usr_sdwt_created_id",
            ),
        ),
        migrations.AddIndex(
            model_name="dronesopv3",
            index=models.Index(
                fields=["send_jira"],
                name="drone_sop_v3_send_jira",
            ),
        ),
        migrations.AddIndex(
            model_name="dronesopv3",
            index=models.Index(
                fields=["knoxid"],
                name="drone_sop_v3_knoxid",
            ),
        ),
    ]
