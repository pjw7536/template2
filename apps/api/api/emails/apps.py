from __future__ import annotations

from django.apps import AppConfig


class EmailsConfig(AppConfig):
    """Emails 도메인 앱 설정."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "api.emails"
