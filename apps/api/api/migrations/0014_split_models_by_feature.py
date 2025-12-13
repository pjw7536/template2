from __future__ import annotations

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0013_affiliation_refactor"),
        ("account", "0001_initial"),
        ("activity", "0001_initial"),
        ("appstore", "0001_initial"),
        ("drone", "0001_initial"),
        ("emails", "0001_initial"),
        ("voc", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name="ActivityLog"),
                migrations.DeleteModel(name="AffiliationHierarchy"),
                migrations.DeleteModel(name="AppStoreApp"),
                migrations.DeleteModel(name="AppStoreComment"),
                migrations.DeleteModel(name="AppStoreLike"),
                migrations.DeleteModel(name="DroneEarlyInformV3"),
                migrations.DeleteModel(name="DroneSOPV3"),
                migrations.DeleteModel(name="Email"),
                migrations.DeleteModel(name="LineSDWT"),
                migrations.DeleteModel(name="SenderSdwtHistory"),
                migrations.DeleteModel(name="UserProfile"),
                migrations.DeleteModel(name="UserSdwtProdAccess"),
                migrations.DeleteModel(name="UserSdwtProdChange"),
                migrations.DeleteModel(name="VocPost"),
                migrations.DeleteModel(name="VocReply"),
            ],
            database_operations=[],
        ),
    ]

