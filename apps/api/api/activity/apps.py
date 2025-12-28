# =============================================================================
# 모듈: Activity 앱 설정
# 주요 클래스: ActivityConfig
# 주요 가정: Django 앱 라벨은 api.activity로 유지합니다.
# =============================================================================
from __future__ import annotations

from django.apps import AppConfig


class ActivityConfig(AppConfig):
    """Activity(활동 로그) 도메인 앱 설정입니다."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "api.activity"
