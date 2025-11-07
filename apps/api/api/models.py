from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class UserProfile(models.Model):
    class Roles(models.TextChoices):
        ADMIN = "admin", "Admin"
        MANAGER = "manager", "Manager"
        VIEWER = "viewer", "Viewer"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=32, choices=Roles.choices, default=Roles.VIEWER)

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return f"{self.user.get_username()} ({self.get_role_display()})"


class ActivityLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=255)
    path = models.CharField(max_length=512)
    method = models.CharField(max_length=10)
    status_code = models.PositiveIntegerField(default=200)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:  # pragma: no cover - debugging helper
        username = self.user.get_username() if self.user else "anonymous"
        return f"{self.method} {self.path} by {username} -> {self.status_code}"


def ensure_user_profile(user=None) -> UserProfile:
    if user is None:
        raise ValueError("user is required to ensure a profile exists")
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


class DroneSOPV3(models.Model):
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
    metro_steps = models.CharField(max_length=100, null=True, blank=True)
    metro_end_step = models.CharField(max_length=50, null=True, blank=True)
    status = models.CharField(max_length=50, null=True, blank=True)
    knoxid = models.CharField(max_length=50, null=True, blank=True)
    comment = models.TextField(null=True, blank=True)
    user_sdwt_prod = models.CharField(max_length=50, null=True, blank=True)
    defect_url = models.TextField(null=True, blank=True)
    send_jira = models.BooleanField(default=False)
    needtosend = models.BooleanField(default=True)
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
        ]

    def __str__(self) -> str:  # pragma: no cover - helpful for admin/debugging
        return f"SOP {self.line_id or '-'} {self.main_step or '-'}"


class DroneEarlyInformV3(models.Model):
    line_id = models.CharField(max_length=50)
    main_step = models.CharField(max_length=50)
    custom_end_step = models.CharField(max_length=50, null=True, blank=True)

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


class LineSDWT(models.Model):
    line_id = models.CharField(max_length=50, null=True, blank=True)
    user_sdwt_prod = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        db_table = "line_sdwt"

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return f"{self.line_id or 'Unknown'} -> {self.user_sdwt_prod or 'N/A'}"
