from __future__ import annotations

from django.db import models
from django.db.models import Q
from django.db.models.functions import Now


def build_sop_key(
    *,
    line_id: str | None,
    eqp_id: str | None,
    chamber_ids: str | None,
    lot_id: str | None,
    main_step: str | None,
) -> str:
    def _normalize(value: str | None) -> str:
        if value is None:
            return ""
        return str(value).strip()

    return "|".join(
        [
            _normalize(line_id),
            _normalize(eqp_id),
            _normalize(chamber_ids),
            _normalize(lot_id),
            _normalize(main_step),
        ]
    )


class DroneSOP(models.Model):
    """Drone SOP 관련 데이터(알림/상태/지라 연동 등)를 저장하는 모델입니다."""

    sop_key = models.CharField(max_length=300, unique=True)
    line_id = models.CharField(max_length=50, null=True, blank=True)
    sdwt_prod = models.CharField(max_length=50, null=True, blank=True)
    sample_type = models.CharField(max_length=50, null=True, blank=True)
    sample_group = models.CharField(max_length=50, null=True, blank=True)
    eqp_id = models.CharField(max_length=50, null=True, blank=True)
    chamber_ids = models.CharField(max_length=50, null=True, blank=True)
    lot_id = models.CharField(max_length=50, null=True, blank=True)
    proc_id = models.CharField(max_length=50, null=True, blank=True)
    ppid = models.CharField(max_length=50, null=True, blank=True)
    main_step = models.CharField(max_length=50, null=True, blank=True)
    metro_current_step = models.CharField(max_length=50, null=True, blank=True)
    metro_steps = models.CharField(max_length=1000, null=True, blank=True)
    metro_end_step = models.CharField(max_length=50, null=True, blank=True)
    status = models.CharField(max_length=50, null=True, blank=True)
    knox_id = models.CharField(max_length=50, null=True, blank=True)
    comment = models.TextField(null=True, blank=True)
    user_sdwt_prod = models.CharField(max_length=50, null=True, blank=True)
    defect_url = models.TextField(null=True, blank=True)
    send_jira = models.SmallIntegerField(null=True, blank=True, default=0, db_default=0)
    instant_inform = models.SmallIntegerField(default=0)
    needtosend = models.SmallIntegerField(default=1)
    custom_end_step = models.CharField(max_length=50, null=True, blank=True)
    inform_step = models.CharField(max_length=50, null=True, blank=True)
    jira_key = models.CharField(max_length=50, null=True, blank=True)
    informed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())
    updated_at = models.DateTimeField(auto_now=True, db_default=Now())

    class Meta:
        db_table = "drone_sop"
        constraints = [
            models.UniqueConstraint(
                fields=["line_id", "eqp_id", "chamber_ids", "lot_id", "main_step"],
                name="uniq_row",
            )
        ]
        indexes = [
            models.Index(fields=["send_jira", "needtosend"], name="send_jira_needtosend"),
            models.Index(fields=["sdwt_prod"], name="sdwt_prod"),
            models.Index(fields=["created_at", "id"], name="drone_sop_created_at_id"),
            models.Index(fields=["user_sdwt_prod", "created_at", "id"], name="dsop_usr_sdwt_created_id"),
            models.Index(fields=["send_jira"], name="drone_sop_send_jira"),
            models.Index(fields=["knox_id"], name="drone_sop_knoxid"),
            models.Index(
                fields=["id"],
                name="drone_sop_jira_pending",
                condition=Q(send_jira=0, needtosend=1, status="COMPLETE"),
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover - helpful for admin/debugging
        return f"SOP {self.line_id or '-'} {self.main_step or '-'}"

    def save(self, *args: object, **kwargs: object) -> None:
        if not self.sop_key:
            self.sop_key = build_sop_key(
                line_id=self.line_id,
                eqp_id=self.eqp_id,
                chamber_ids=self.chamber_ids,
                lot_id=self.lot_id,
                main_step=self.main_step,
            )
        super().save(*args, **kwargs)


class DroneSopJiraTemplate(models.Model):
    """Drone SOP Jira 템플릿(line_id 매핑)을 저장하는 모델입니다."""

    line_id = models.CharField(max_length=50, unique=True)
    template_key = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())
    updated_at = models.DateTimeField(auto_now=True, db_default=Now())

    class Meta:
        db_table = "drone_sop_jira_template"
        indexes = [
            models.Index(fields=["line_id"], name="drone_jira_tpl_line"),
        ]

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return f"{self.line_id} -> {self.template_key}"


class DroneSopJiraUserTemplate(models.Model):
    """Drone SOP Jira 템플릿(user_sdwt_prod 매핑)을 저장하는 모델입니다."""

    user_sdwt_prod = models.CharField(max_length=50, unique=True)
    template_key = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())
    updated_at = models.DateTimeField(auto_now=True, db_default=Now())

    class Meta:
        db_table = "drone_sop_jira_user_template"
        indexes = [
            models.Index(fields=["user_sdwt_prod"], name="drone_jira_tpl_user"),
        ]

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return f"{self.user_sdwt_prod} -> {self.template_key}"


class DroneEarlyInform(models.Model):
    """Drone 조기 알림 설정(라인/스텝 기준)을 저장하는 모델입니다."""

    line_id = models.CharField(max_length=50)
    main_step = models.CharField(max_length=50)
    custom_end_step = models.CharField(max_length=50, null=True, blank=True)
    updated_by = models.CharField(max_length=50, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = "drone_early_inform"
        constraints = [
            models.UniqueConstraint(
                fields=["line_id", "main_step"],
                name="uniq_line_mainstep",
            )
        ]

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return f"{self.line_id} - {self.main_step}"


__all__ = [
    "DroneEarlyInform",
    "DroneSOP",
    "DroneSopJiraTemplate",
    "DroneSopJiraUserTemplate",
    "build_sop_key",
]
