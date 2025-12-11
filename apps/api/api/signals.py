from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .emails.department import reclassify_emails_for_department_change
from .models import UserDepartmentHistory, ensure_user_profile


@receiver(post_save, sender=get_user_model())
def create_profile(sender, instance, created, **kwargs):
    if created:
        ensure_user_profile(instance)


@receiver(post_save, sender=UserDepartmentHistory)
def reclassify_emails_on_department_change(sender, instance, created, **kwargs):
    """
    부서 이동 이력이 새로 추가/수정될 때 이메일을 재분류한다.
    raw=True (loaddata 등) 상태에서는 수행하지 않는다.
    """

    if kwargs.get("raw"):
        return

    try:
        reclassify_emails_for_department_change(
            employee_id=instance.employee_id,
            department_code=instance.department_code,
            effective_from=instance.effective_from,
        )
    except Exception:
        # 메일 재분류 실패 시에도 UserDepartmentHistory 저장은 유지하고 로그만 남긴다.
        import logging

        logger = logging.getLogger(__name__)
        logger.exception(
            "Failed to reclassify emails for employee_id=%s, department_code=%s, effective_from=%s",
            instance.employee_id,
            instance.department_code,
            instance.effective_from,
        )
