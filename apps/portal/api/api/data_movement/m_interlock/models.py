"""m_interlock 적재 대상 및 처리 이력 모델입니다."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from django.db import models
from django.db.models.functions import Now

from api.data_movement.common.models import UnboundedNumericField

SEOUL_TIMEZONE = ZoneInfo("Asia/Seoul")
PROD_PROGS_TIME_FORMATS = (
    "%Y%m%d %H%M%S",
    "%Y%m%d%H%M%S%f",
)


def normalize_interlock_lookup(value: object) -> str | None:
    """Observer 검색용 문자열을 공백 제거 후 대문자로 정규화합니다."""

    normalized = str(value or "").strip().upper()
    return normalized or None


def parse_prod_progs_at(value: object) -> datetime | None:
    """원천 진행 시각을 Asia/Seoul aware datetime으로 변환합니다."""

    raw_value = str(value or "").strip()
    for source_format in PROD_PROGS_TIME_FORMATS:
        try:
            parsed = datetime.strptime(raw_value, source_format)
        except ValueError:
            continue
        return parsed.replace(tzinfo=SEOUL_TIMEZONE)
    return None


class MInterlock(models.Model):
    """m_interlock 원천 데이터를 interlock_no 기준으로 저장합니다."""

    line_id = models.CharField(max_length=10, null=True, blank=True)
    interlock_no = models.CharField(max_length=100, null=True, blank=True)
    item_value = models.CharField(max_length=200, null=True, blank=True)
    interlock_type = models.CharField(max_length=30, null=True, blank=True)
    interlock_comment = models.CharField(max_length=2000, null=True, blank=True)
    ppid = models.CharField(max_length=255, null=True, blank=True)
    usl = UnboundedNumericField(null=True, blank=True)
    spec_target = UnboundedNumericField(null=True, blank=True)
    lsl = UnboundedNumericField(null=True, blank=True)
    ucl = UnboundedNumericField(null=True, blank=True)
    cl = UnboundedNumericField(null=True, blank=True)
    lcl = UnboundedNumericField(null=True, blank=True)
    batch_id = models.CharField(max_length=50, null=True, blank=True)
    metro_item = models.CharField(max_length=128, null=True, blank=True)
    interlock_desc = models.CharField(max_length=200, null=True, blank=True)
    area_name = models.CharField(max_length=12, null=True, blank=True)
    process_id = models.CharField(max_length=16, null=True, blank=True)
    interlock_kind = models.CharField(max_length=30, null=True, blank=True)
    lot_id = models.TextField(null=True, blank=True)
    prod_step_seq = models.CharField(max_length=20, null=True, blank=True)
    prod_progs_time = models.CharField(max_length=18, null=True, blank=True)
    prod_eqp_type = models.CharField(max_length=40, null=True, blank=True)
    prod_bay_name = models.CharField(max_length=10, null=True, blank=True)
    prod_chamber_id = models.CharField(max_length=50, null=True, blank=True)
    metro_step_seq = models.CharField(max_length=16, null=True, blank=True)
    metro_progs_time = models.CharField(max_length=18, null=True, blank=True)
    intlk_occur_week = models.CharField(max_length=8, null=True, blank=True)
    intlk_occur_year_m = models.CharField(max_length=8, null=True, blank=True)
    metro_eqp_id = models.CharField(max_length=40, null=True, blank=True)
    prod_eqp_id = models.CharField(max_length=40, null=True, blank=True)
    last_update_date = models.DateTimeField(null=True, blank=True)
    wafer_id = models.CharField(max_length=45, null=True, blank=True)
    eqp_process_phase = models.CharField(max_length=50, null=True, blank=True)
    eqp_detail_comment = models.CharField(max_length=255, null=True, blank=True)
    engr_comment = models.CharField(max_length=500, null=True, blank=True)
    prod_eqp_id_lookup = models.CharField(max_length=40, null=True, blank=True)
    interlock_kind_lookup = models.CharField(max_length=30, null=True, blank=True)
    prod_progs_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())

    class Meta:
        db_table = "m_interlock"
        constraints = [
            models.UniqueConstraint(
                fields=["interlock_no"],
                name="uniq_m_intlk_no",
            ),
        ]
        indexes = [
            models.Index(
                fields=[
                    "prod_eqp_id_lookup",
                    "interlock_kind_lookup",
                    "-prod_progs_at",
                    "-id",
                ],
                name="idx_m_intlk_obs_page",
            ),
        ]

    def sync_observer_fields(self) -> None:
        """원천 필드에서 Observer 검색용 파생 필드를 계산합니다."""

        self.prod_eqp_id_lookup = normalize_interlock_lookup(self.prod_eqp_id)
        self.interlock_kind_lookup = normalize_interlock_lookup(self.interlock_kind)
        self.prod_progs_at = parse_prod_progs_at(self.prod_progs_time)

    def save(self, *args, **kwargs) -> None:
        """ORM 저장에서도 Observer 파생 필드를 항상 함께 유지합니다."""

        self.sync_observer_fields()
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = set(update_fields) | {
                "prod_eqp_id_lookup",
                "interlock_kind_lookup",
                "prod_progs_at",
            }
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        """관리자/디버깅용 문자열 표현을 반환합니다."""

        return f"m_interlock {self.line_id or '-'} {self.interlock_no or '-'}"


class MInterlockLoadJob(models.Model):
    """m_interlock 파일 적재 처리 이력을 저장합니다."""

    class Status(models.TextChoices):
        """파일 적재 상태 값입니다."""

        RUNNING = "running", "Running"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        DRY_RUN = "dry_run", "Dry run"

    file_name = models.TextField()
    file_path = models.TextField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.RUNNING)
    row_count = models.PositiveIntegerField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())

    class Meta:
        db_table = "m_interlock_load_job"
        indexes = [
            models.Index(fields=["status"], name="idx_m_intlk_job_sts"),
            models.Index(fields=["created_at"], name="idx_m_intlk_job_crt"),
        ]

    def __str__(self) -> str:
        """관리자/디버깅용 문자열 표현을 반환합니다."""

        return f"{self.file_name} ({self.status})"
