from __future__ import annotations

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    department = models.CharField(max_length=128, null=True, blank=True)
    line = models.CharField(max_length=64, null=True, blank=True)
    sdwt = models.CharField(max_length=64, null=True, blank=True)

    class Meta:
        db_table = "api_user"

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return self.get_username()


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
    metro_steps = models.CharField(max_length=1000, null=True, blank=True)
    metro_end_step = models.CharField(max_length=50, null=True, blank=True)
    status = models.CharField(max_length=50, null=True, blank=True)
    knoxid = models.CharField(max_length=50, null=True, blank=True)
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
            models.Index(fields=["knoxid"], name="drone_sop_v3_knoxid"),
        ]

    def __str__(self) -> str:  # pragma: no cover - helpful for admin/debugging
        return f"SOP {self.line_id or '-'} {self.main_step or '-'}"


class DroneEarlyInformV3(models.Model):
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


class LineSDWT(models.Model):
    line_id = models.CharField(max_length=50, null=True, blank=True)
    user_sdwt_prod = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        db_table = "line_sdwt"
        indexes = [
            models.Index(fields=["line_id", "user_sdwt_prod"], name="line_sdwt_line_user_sdwt"),
        ]

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return f"{self.line_id or 'Unknown'} -> {self.user_sdwt_prod or 'N/A'}"


class VocPost(models.Model):
    class Status(models.TextChoices):
        RECEIVED = "접수", "접수"
        IN_PROGRESS = "진행중", "진행중"
        DONE = "완료", "완료"
        REJECTED = "반려", "반려"

    title = models.CharField(max_length=255)
    content = models.TextField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.RECEIVED)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="voc_posts",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "voc_post"
        ordering = ["-created_at"]

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return f"[{self.status}] {self.title}"


class VocReply(models.Model):
    post = models.ForeignKey(VocPost, on_delete=models.CASCADE, related_name="replies")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="voc_replies",
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "voc_reply"
        ordering = ["created_at"]

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return f"Reply to {self.post_id}"


class UserDepartmentHistory(models.Model):
    """발신자 부서 이력 (수동 입력 가능)."""

    employee_id = models.CharField(max_length=50, db_index=True)  # Email.sender_id 와 동일 키
    department_code = models.CharField(max_length=50)
    effective_from = models.DateTimeField()  # 이 시점부터 department_code 적용

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=50)

    class Meta:
        db_table = "user_department_history"
        indexes = [
            models.Index(fields=["employee_id", "effective_from"]),
        ]

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return f"{self.employee_id} -> {self.department_code} ({self.effective_from.isoformat()})"


class Email(models.Model):
    """수신 메일 저장 모델 (RAG doc 연동)."""

    message_id = models.CharField(max_length=255, unique=True)
    received_at = models.DateTimeField()
    subject = models.TextField()
    sender = models.TextField()
    sender_id = models.CharField(max_length=50, db_index=True)  # 사번/계정 ID 등 식별자
    recipient = models.TextField()

    # 메일 수신 시점의 부서 스냅샷
    department_code = models.CharField(max_length=50, db_index=True)

    body_text = models.TextField(blank=True)  # RAG 검색/스니펫용 텍스트
    body_html_gzip = models.BinaryField(null=True, blank=True)  # UI 렌더용 gzip HTML

    rag_doc_id = models.CharField(max_length=255, null=True, blank=True, unique=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "email"

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return f"{self.subject[:40]} ({self.sender} -> {self.recipient}) [{self.department_code}]"


class AppStoreApp(models.Model):
    """내부 Appstore 앱 메타데이터."""

    name = models.CharField(max_length=255)
    category = models.CharField(max_length=100)
    description = models.TextField(blank=True, default="")
    url = models.TextField()
    tags = models.JSONField(default=list, blank=True)
    badge = models.CharField(max_length=64, blank=True, default="")
    contact_name = models.CharField(max_length=255, blank=True, default="")
    contact_knoxid = models.CharField(max_length=255, blank=True, default="")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appstore_apps",
    )
    view_count = models.PositiveIntegerField(default=0)
    like_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "appstore_app"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["category"], name="appstore_app_category_idx"),
            models.Index(fields=["name"], name="appstore_app_name_idx"),
        ]

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return self.name


class AppStoreLike(models.Model):
    """앱 좋아요(토글) 기록."""

    app = models.ForeignKey(
        AppStoreApp,
        on_delete=models.CASCADE,
        related_name="likes",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="appstore_likes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "appstore_like"
        unique_together = ("app", "user")
        indexes = [
            models.Index(fields=["user"], name="appstore_like_user_idx"),
            models.Index(fields=["app"], name="appstore_like_app_idx"),
        ]

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return f"{self.user_id} -> {self.app_id}"


class AppStoreComment(models.Model):
    """앱 댓글."""

    app = models.ForeignKey(
        AppStoreApp,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appstore_comments",
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "appstore_comment"
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(fields=["app"], name="appstore_comment_app_idx"),
            models.Index(fields=["app", "created_at"], name="appstore_comment_created_idx"),
        ]

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return f"Comment {self.pk} on app {self.app_id}"
