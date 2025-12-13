from __future__ import annotations

from django.apps import AppConfig


class ApiConfig(AppConfig):
    """Django 프로젝트의 api 패키지(AppConfig) 설정입니다."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "api"
