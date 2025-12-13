from __future__ import annotations

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("api", "0013_affiliation_refactor"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name="AppStoreApp",
                    fields=[
                        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                        ("name", models.CharField(max_length=255)),
                        ("category", models.CharField(max_length=100)),
                        ("description", models.TextField(blank=True, default="")),
                        ("url", models.TextField()),
                        ("tags", models.JSONField(blank=True, default=list)),
                        ("badge", models.CharField(blank=True, default="", max_length=64)),
                        ("contact_name", models.CharField(blank=True, default="", max_length=255)),
                        ("contact_knoxid", models.CharField(blank=True, default="", max_length=255)),
                        ("view_count", models.PositiveIntegerField(default=0)),
                        ("like_count", models.PositiveIntegerField(default=0)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                        (
                            "owner",
                            models.ForeignKey(
                                blank=True,
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name="appstore_apps",
                                to=settings.AUTH_USER_MODEL,
                            ),
                        ),
                    ],
                    options={
                        "db_table": "appstore_app",
                        "ordering": ["-created_at", "-id"],
                        "indexes": [
                            models.Index(fields=["category"], name="appstore_app_category_idx"),
                            models.Index(fields=["name"], name="appstore_app_name_idx"),
                        ],
                    },
                ),
                migrations.CreateModel(
                    name="AppStoreLike",
                    fields=[
                        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        (
                            "app",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="likes",
                                to="appstore.appstoreapp",
                            ),
                        ),
                        (
                            "user",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="appstore_likes",
                                to=settings.AUTH_USER_MODEL,
                            ),
                        ),
                    ],
                    options={
                        "db_table": "appstore_like",
                        "unique_together": {("app", "user")},
                        "indexes": [
                            models.Index(fields=["user"], name="appstore_like_user_idx"),
                            models.Index(fields=["app"], name="appstore_like_app_idx"),
                        ],
                    },
                ),
                migrations.CreateModel(
                    name="AppStoreComment",
                    fields=[
                        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                        ("content", models.TextField()),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                        (
                            "app",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="comments",
                                to="appstore.appstoreapp",
                            ),
                        ),
                        (
                            "user",
                            models.ForeignKey(
                                blank=True,
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name="appstore_comments",
                                to=settings.AUTH_USER_MODEL,
                            ),
                        ),
                    ],
                    options={
                        "db_table": "appstore_comment",
                        "ordering": ["created_at", "id"],
                        "indexes": [
                            models.Index(fields=["app"], name="appstore_comment_app_idx"),
                            models.Index(fields=["app", "created_at"], name="appstore_comment_created_idx"),
                        ],
                    },
                ),
            ],
            database_operations=[],
        ),
    ]

