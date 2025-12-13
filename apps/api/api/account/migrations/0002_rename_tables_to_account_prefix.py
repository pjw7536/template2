from __future__ import annotations

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0014_split_models_by_feature"),
        ("account", "0001_initial"),
    ]

    operations = [
        migrations.AlterModelTable(
            name="User",
            table="account_user",
        ),
        migrations.RunSQL(
            sql="ALTER TABLE api_user_groups RENAME TO account_user_groups;",
            reverse_sql="ALTER TABLE account_user_groups RENAME TO api_user_groups;",
        ),
        migrations.RunSQL(
            sql="ALTER TABLE api_user_user_permissions RENAME TO account_user_user_permissions;",
            reverse_sql="ALTER TABLE account_user_user_permissions RENAME TO api_user_user_permissions;",
        ),
        migrations.AlterModelTable(
            name="UserProfile",
            table="account_user_profile",
        ),
        migrations.AlterModelTable(
            name="AffiliationHierarchy",
            table="account_affiliation_hierarchy",
        ),
        migrations.AlterModelTable(
            name="UserSdwtProdAccess",
            table="account_user_sdwt_prod_access",
        ),
        migrations.AlterModelTable(
            name="UserSdwtProdChange",
            table="account_user_sdwt_prod_change",
        ),
        migrations.AlterModelTable(
            name="LineSDWT",
            table="account_line_sdwt",
        ),
    ]

