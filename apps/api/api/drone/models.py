from __future__ import annotations

from django.db import models


class DroneSOPV3(models.Model):
    """Drone SOP v3 관련 데이터(알림/상태/지라 연동 등)를 저장하는 모델입니다."""

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
    send_jira = models.SmallIntegerField(default=0)
    instant_inform = models.SmallIntegerField(default=0)
    needtosend = models.SmallIntegerField(default=1)
    custom_end_step = models.CharField(max_length=50, null=True, blank=True)
    inform_step = models.CharField(max_length=50, null=True, blank=True)
    jira_key = models.CharField(max_length=50, null=True, blank=True)
    informed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "drone_sop_v3"
        constraints = [
            models.UniqueConstraint(
                fields=["line_id", "eqp_id", "chamber_ids", "lot_id", "main_step"],
                name="uniq_row",
            )
        ]
        indexes = [
            models.Index(fields=["send_jira", "needtosend"], name="send_jira_needtosend"),
            models.Index(fields=["sdwt_prod"], name="sdwt_prod"),
            models.Index(fields=["created_at", "id"], name="drone_sop_v3_created_at_id"),
            models.Index(fields=["user_sdwt_prod", "created_at", "id"], name="dsopv3_usr_sdwt_created_id"),
            models.Index(fields=["send_jira"], name="drone_sop_v3_send_jira"),
            models.Index(fields=["knox_id"], name="drone_sop_v3_knoxid"),
        ]

    def __str__(self) -> str:  # pragma: no cover - helpful for admin/debugging
        return f"SOP {self.line_id or '-'} {self.main_step or '-'}"


class DroneEarlyInformV3(models.Model):
    """Drone 조기 알림 설정(라인/스텝 기준)을 저장하는 모델입니다."""

    line_id = models.CharField(max_length=50)
    main_step = models.CharField(max_length=50)
    custom_end_step = models.CharField(max_length=50, null=True, blank=True)
    updated_by = models.CharField(max_length=50, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = "drone_early_inform_v3"
        constraints = [
            models.UniqueConstraint(
                fields=["line_id", "main_step"],
                name="uniq_line_mainstep",
            )
        ]

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return f"{self.line_id} - {self.main_step}"


__all__ = ["DroneEarlyInformV3", "DroneSOPV3"]
