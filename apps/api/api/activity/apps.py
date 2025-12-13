from __future__ import annotations

from django.apps import AppConfig


class ActivityConfig(AppConfig):
    """Activity(활동 로그) 도메인 앱 설정입니다."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "api.activity"
