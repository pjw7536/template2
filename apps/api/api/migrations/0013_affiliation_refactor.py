from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0012_create_appstore_models"),
    ]

    operations = [
        migrations.RenameField(
            model_name="user",
            old_name="sdwt",
            new_name="user_sdwt_prod",
        ),
        migrations.CreateModel(
            name="UserSdwtProdAccess",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("user_sdwt_prod", models.CharField(max_length=64)),
                ("can_manage", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "granted_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.SET_NULL,
                        related_name="sdwt_prod_grants",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=models.CASCADE,
                        related_name="sdwt_prod_access",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "user_sdwt_prod_access",
                "unique_together": {("user", "user_sdwt_prod")},
                "indexes": [
                    models.Index(fields=["user"], name="user_sdwt_access_user"),
                    models.Index(fields=["user_sdwt_prod"], name="user_sdwt_access_prod"),
                ],
            },
        ),
        migrations.CreateModel(
            name="UserSdwtProdChange",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("department", models.CharField(blank=True, max_length=128, null=True)),
                ("line", models.CharField(blank=True, max_length=64, null=True)),
                ("from_user_sdwt_prod", models.CharField(blank=True, max_length=64, null=True)),
                ("to_user_sdwt_prod", models.CharField(max_length=64)),
                ("effective_from", models.DateTimeField()),
                ("applied", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.SET_NULL,
                        related_name="sdwt_prod_changes_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=models.CASCADE,
                        related_name="sdwt_prod_changes",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "user_sdwt_prod_change",
                "ordering": ["-effective_from", "-id"],
                "indexes": [
                    models.Index(fields=["user", "effective_from"], name="user_sdwt_change_user_effective"),
                    models.Index(fields=["applied"], name="user_sdwt_change_applied"),
                ],
            },
        ),
        migrations.CreateModel(
            name="AffiliationHierarchy",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("department", models.CharField(max_length=128)),
                ("line", models.CharField(max_length=64)),
                ("user_sdwt_prod", models.CharField(max_length=64)),
            ],
            options={
                "db_table": "affiliation_hierarchy",
                "unique_together": {("department", "line", "user_sdwt_prod")},
                "indexes": [
                    models.Index(fields=["department"], name="aff_hier_department"),
                    models.Index(fields=["line"], name="aff_hier_line"),
                    models.Index(fields=["user_sdwt_prod"], name="aff_hier_user_sdwt_prod"),
                ],
            },
        ),
        migrations.CreateModel(
            name="SenderSdwtHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sender_id", models.CharField(db_index=True, max_length=50)),
                ("effective_from", models.DateTimeField()),
                ("department", models.CharField(blank=True, max_length=50, null=True)),
                ("line", models.CharField(blank=True, max_length=64, null=True)),
                ("user_sdwt_prod", models.CharField(blank=True, max_length=64, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.CharField(default="", max_length=50)),
            ],
            options={
                "db_table": "sender_sdwt_history",
                "unique_together": {("sender_id", "effective_from")},
                "indexes": [
                    models.Index(fields=["sender_id", "effective_from"], name="sender_sdwt_effective"),
                    models.Index(fields=["user_sdwt_prod"], name="sender_sdwt_user_sdwt"),
                ],
            },
        ),
        migrations.AddField(
            model_name="email",
            name="user_sdwt_prod",
            field=models.CharField(blank=True, db_index=True, max_length=64, null=True),
        ),
        migrations.RemoveField(
            model_name="email",
            name="department_code",
        ),
        migrations.DeleteModel(
            name="UserDepartmentHistory",
        ),
    ]
