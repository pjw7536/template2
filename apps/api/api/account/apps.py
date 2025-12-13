from __future__ import annotations

from django.apps import AppConfig


class AccountConfig(AppConfig):
    """Account 도메인 앱 설정 및 사용자 생성 시 프로필 생성 시그널을 등록합니다."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "api.account"

    def ready(self) -> None:
        from django.contrib.auth import get_user_model
        from django.db.models.signals import post_save

        from api.account.services import ensure_user_profile

        def create_profile(sender, instance, created: bool, **kwargs) -> None:
            if created:
                ensure_user_profile(instance)

        post_save.connect(
            create_profile,
            sender=get_user_model(),
            dispatch_uid="account_create_profile",
        )
