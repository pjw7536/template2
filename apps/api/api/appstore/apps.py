# =============================================================================
# 모듈 설명: appstore 앱 설정을 정의합니다.
# - 주요 클래스: AppstoreConfig
# - 불변 조건: Django 앱 라벨은 api.appstore로 유지합니다.
# =============================================================================
from __future__ import annotations

from django.apps import AppConfig


class AppstoreConfig(AppConfig):
    """AppStore 도메인 앱 설정입니다."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "api.appstore"
