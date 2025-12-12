from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .emails.department import reclassify_emails_for_sender_history_change
from .models import SenderSdwtHistory, ensure_user_profile


@receiver(post_save, sender=get_user_model())
def create_profile(sender, instance, created, **kwargs):
    if created:
        ensure_user_profile(instance)


@receiver(post_save, sender=SenderSdwtHistory)
def reclassify_emails_on_sender_history_change(sender, instance, created, **kwargs):
    """
    SenderSdwtHistory가 추가/수정될 때 이메일을 최신 소속(user_sdwt_prod)으로 재분류한다.
    raw=True (loaddata 등) 상태에서는 수행하지 않는다.
    """

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
