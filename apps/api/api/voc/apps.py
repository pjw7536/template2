# =============================================================================
# 모듈 설명: voc Django 앱 설정을 정의합니다.
# - 주요 클래스: VocConfig
# - 불변 조건: 앱 이름은 "api.voc" 입니다.
# =============================================================================

from __future__ import annotations

from django.apps import AppConfig


class VocConfig(AppConfig):
    """VOC 도메인 앱 설정입니다."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "api.voc"
