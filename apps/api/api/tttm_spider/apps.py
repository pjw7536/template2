# =============================================================================
# 모듈: TTTM Spider 앱 설정
# 주요 클래스: TttmSpiderConfig
# 주요 가정: 앱 라벨은 api.tttm_spider를 사용합니다.
# =============================================================================
from __future__ import annotations

from django.apps import AppConfig


class TttmSpiderConfig(AppConfig):
    """TTTM Spider 도메인 앱 설정입니다."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "api.tttm_spider"
