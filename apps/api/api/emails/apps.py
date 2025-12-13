from __future__ import annotations

from django.apps import AppConfig


class EmailsConfig(AppConfig):
    """Emails 도메인 앱 설정 및 SenderSdwtHistory 변경 시 재분류 시그널을 등록합니다."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "api.emails"

    def ready(self) -> None:
        from django.db.models.signals import post_save

        from api.emails.models import SenderSdwtHistory
        from api.emails.services import reclassify_emails_for_sender_history_change

        def reclassify_emails_on_sender_history_change(sender, instance, created: bool, **kwargs) -> None:
            if kwargs.get("raw"):
                return

            try:
                reclassify_emails_for_sender_history_change(
                    sender_id=instance.sender_id,
                    effective_from=instance.effective_from,
                )
            except Exception:
                # 메일 재분류 실패 시에도 SenderSdwtHistory 저장은 유지하고 로그만 남긴다.
                import logging

                logger = logging.getLogger(__name__)
                logger.exception(
                    "Failed to reclassify emails for sender_id=%s, user_sdwt_prod=%s, effective_from=%s",
                    instance.sender_id,
                    instance.user_sdwt_prod,
                    instance.effective_from,
                )

        post_save.connect(
            reclassify_emails_on_sender_history_change,
            sender=SenderSdwtHistory,
            dispatch_uid="emails_reclassify_emails_on_sender_history_change",
        )
