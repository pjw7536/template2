# =============================================================================
# 모듈 설명: account 앱 설정과 초기 시그널/기본 슈퍼유저 보정 로직을 제공합니다.
# - 주요 클래스: AccountConfig
# - 불변 조건: ready 단계에서는 시그널 등록만 수행합니다.
# =============================================================================

from __future__ import annotations

from django.apps import AppConfig


class AccountConfig(AppConfig):
    """Account 도메인 앱 설정과 기본 슈퍼유저 보정 시그널을 등록합니다."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "api.account"

    def ready(self) -> None:
        """Keycloak 전환 후 Django superuser 자동 생성을 수행하지 않습니다."""

        return None
