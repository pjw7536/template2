# =============================================================================
# 모듈 설명: assistant 앱 설정을 제공합니다.
# - 주요 클래스: AssistantConfig
# - 불변 조건: 앱 이름은 api.assistant 입니다.
# =============================================================================

"""assistant 앱 설정 모듈."""
from __future__ import annotations

from django.apps import AppConfig


class AssistantConfig(AppConfig):
    """assistant 도메인 앱 설정 클래스입니다."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "api.assistant"
