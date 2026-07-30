"""m_interlock Django 앱 설정입니다."""

from __future__ import annotations

from django.apps import AppConfig


class MInterlockConfig(AppConfig):
    """m_interlock data movement 앱 설정 클래스입니다."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "api.data_movement.m_interlock"
