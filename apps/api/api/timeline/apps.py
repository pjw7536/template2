# =============================================================================
# 모듈 설명: timeline 앱 설정을 제공합니다.
# - 주요 클래스: TimelineConfig
# - 불변 조건: 앱 이름은 api.timeline 입니다.
# =============================================================================

"""timeline 앱 설정 모듈."""
from __future__ import annotations

from django.apps import AppConfig


class TimelineConfig(AppConfig):
    """timeline 도메인 앱 설정 클래스입니다."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "api.timeline"
