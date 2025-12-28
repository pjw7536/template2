# =============================================================================
# 모듈: 드론 앱 설정
# 주요 클래스: DroneConfig
# 주요 가정: 앱 라벨은 api.drone을 사용합니다.
# =============================================================================
from __future__ import annotations

from django.apps import AppConfig


class DroneConfig(AppConfig):
    """Drone 도메인 앱 설정입니다."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "api.drone"
