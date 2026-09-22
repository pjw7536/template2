# =============================================================================
# 모듈 설명: api Django 앱 설정을 정의합니다.
# - 주요 클래스: ApiConfig
# - 불변 조건: AppConfig 설정만 담당하며 런타임 로직을 포함하지 않습니다.
# =============================================================================

from __future__ import annotations

from django.apps import AppConfig


class ApiConfig(AppConfig):
    """Django 프로젝트의 api 패키지(AppConfig) 설정입니다."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "api"
