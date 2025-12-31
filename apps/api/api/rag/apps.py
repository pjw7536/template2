# =============================================================================
# 모듈 설명: rag 앱 설정을 제공합니다.
# - 주요 클래스: RagConfig
# - 불변 조건: 앱 이름은 api.rag 입니다.
# =============================================================================

"""rag 앱 설정 모듈."""
from __future__ import annotations

from django.apps import AppConfig


class RagConfig(AppConfig):
    """rag 도메인 앱 설정 클래스입니다."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "api.rag"
