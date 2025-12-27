from __future__ import annotations

import os

from django.apps import AppConfig
from django.db import IntegrityError, OperationalError, ProgrammingError, connection


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

        self._ensure_default_superuser()

    def _ensure_default_superuser(self) -> None:
        from django.contrib.auth import get_user_model

        def env_or_default(key: str, default: str) -> str:
            value = os.environ.get(key)
            if value is None:
                return default
            value = value.strip()
            return value or default

        UserModel = get_user_model()
        try:
            table_names = connection.introspection.table_names()
        except (OperationalError, ProgrammingError):
            return

        if UserModel._meta.db_table not in table_names:
            return

        sabun = env_or_default("DJANGO_SUPERUSER_SABUN", "00000000")
        if UserModel.objects.filter(sabun=sabun).exists():
            return

        try:
            UserModel.objects.create_superuser(
                sabun=sabun,
                password=env_or_default("DJANGO_SUPERUSER_PASSWORD", "dkssud123!"),
                username=env_or_default("DJANGO_SUPERUSER_USERNAME", "admin"),
                email=env_or_default("DJANGO_SUPERUSER_EMAIL", "etch_mail_collector@samsung.com"),
            )
        except IntegrityError:
            return
