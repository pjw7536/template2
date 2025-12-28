# =============================================================================
# 모듈 설명: emails 도메인 앱 설정을 정의합니다.
# - 주요 클래스: EmailsConfig
# - 불변 조건: 앱 이름은 "api.emails", 기본 PK는 BigAutoField입니다.
# =============================================================================

from __future__ import annotations

from django.apps import AppConfig


class EmailsConfig(AppConfig):
    """Emails 도메인 앱 설정."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "api.emails"
