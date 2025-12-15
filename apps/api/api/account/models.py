from __future__ import annotations

from django.contrib.auth.models import AbstractUser
from django.contrib.auth.base_user import BaseUserManager
from django.conf import settings
from django.db import models


class UserManager(BaseUserManager):
    """sabun 기반 사용자 생성을 제공하는 커스텀 User 매니저입니다."""

    use_in_migrations = True

    def _create_user(self, sabun: str, password: str | None, **extra_fields) -> "User":
        if not sabun:
            raise ValueError("sabun is required")
        user = self.model(sabun=str(sabun).strip(), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, sabun: str, password: str | None = None, **extra_fields) -> "User":
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(sabun, password, **extra_fields)

    def create_superuser(self, sabun: str, password: str | None = None, **extra_fields) -> "User":
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(sabun, password, **extra_fields)


class User(AbstractUser):
    """ADFS/OIDC 클레임을 저장하는 커스텀 사용자 모델입니다."""

    username = models.CharField(max_length=150, null=True, blank=True)
    sabun = models.CharField(max_length=50, unique=True)
    knox_id = models.CharField(max_length=150, null=True, blank=True, unique=True)
    firstname = models.CharField(max_length=150, null=True, blank=True)
    lastname = models.CharField(max_length=150, null=True, blank=True)
    username_en = models.CharField(max_length=150, null=True, blank=True)
    givenname = models.CharField(max_length=150, null=True, blank=True)
    surname = models.CharField(max_length=150, null=True, blank=True)
    mail = models.EmailField(null=True, blank=True)
    deptname = models.CharField(max_length=128, null=True, blank=True)
    deptid = models.CharField(max_length=50, null=True, blank=True)
    grd_name = models.CharField(max_length=150, null=True, blank=True)
    grdname_en = models.CharField(max_length=150, null=True, blank=True)
    busname = models.CharField(max_length=150, null=True, blank=True)
    intcode = models.CharField(max_length=64, null=True, blank=True)
    intname = models.CharField(max_length=150, null=True, blank=True)
    origincomp = models.CharField(max_length=150, null=True, blank=True)
    employeetype = models.CharField(max_length=150, null=True, blank=True)
    x_ms_forwarded_client_ip = models.CharField(max_length=45, null=True, blank=True)
    department = models.CharField(max_length=128, null=True, blank=True)
    line = models.CharField(max_length=64, null=True, blank=True)
    user_sdwt_prod = models.CharField(max_length=64, null=True, blank=True)

    class Meta:
        db_table = "account_user"

    objects = UserManager()

    USERNAME_FIELD = "sabun"
    REQUIRED_FIELDS: list[str] = []

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return self.get_username()


class UserProfile(models.Model):
    """사용자 역할(role) 등 추가 정보를 저장하는 프로필 모델입니다."""

    class Roles(models.TextChoices):
        ADMIN = "admin", "Admin"
        MANAGER = "manager", "Manager"
        VIEWER = "viewer", "Viewer"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=32, choices=Roles.choices, default=Roles.VIEWER)

    class Meta:
        db_table = "account_user_profile"

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return f"{self.user.get_username()} ({self.get_role_display()})"


class Affiliation(models.Model):
    """department/line/user_sdwt_prod 조합의 허용 목록(소속 hierarchy)을 저장하는 모델입니다."""

    department = models.CharField(max_length=128)
    line = models.CharField(max_length=64)
    user_sdwt_prod = models.CharField(max_length=64)

    class Meta:
        db_table = "account_affiliation"
        unique_together = ("department", "line", "user_sdwt_prod")
        indexes = [
            models.Index(fields=["department"], name="aff_hier_department"),
            models.Index(fields=["line"], name="aff_hier_line"),
            models.Index(fields=["user_sdwt_prod"], name="aff_hier_user_sdwt_prod"),
        ]

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return f"{self.department} / {self.line} / {self.user_sdwt_prod}"


class UserSdwtProdAccess(models.Model):
    """사용자의 user_sdwt_prod 접근/관리 권한을 저장하는 모델입니다."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sdwt_prod_access",
    )
    user_sdwt_prod = models.CharField(max_length=64)
    can_manage = models.BooleanField(default=False)
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sdwt_prod_grants",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "account_user_sdwt_prod_access"
        unique_together = ("user", "user_sdwt_prod")
        indexes = [
            models.Index(fields=["user"], name="user_sdwt_access_user"),
            models.Index(fields=["user_sdwt_prod"], name="user_sdwt_access_prod"),
        ]

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return f"{self.user_id} -> {self.user_sdwt_prod} ({'manager' if self.can_manage else 'member'})"


class UserSdwtProdChange(models.Model):
    """사용자 소속(user_sdwt_prod) 변경 요청/승인/적용 이력을 저장하는 모델입니다."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sdwt_prod_changes",
    )
    department = models.CharField(max_length=128, null=True, blank=True)
    line = models.CharField(max_length=64, null=True, blank=True)
    from_user_sdwt_prod = models.CharField(max_length=64, null=True, blank=True)
    to_user_sdwt_prod = models.CharField(max_length=64)
    effective_from = models.DateTimeField()
    applied = models.BooleanField(default=False)
    approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sdwt_prod_changes_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sdwt_prod_changes_created",
    )

    class Meta:
        db_table = "account_user_sdwt_prod_change"
        ordering = ["-effective_from", "-id"]
        indexes = [
            models.Index(fields=["user", "effective_from"], name="user_sdwt_change_eff"),
            models.Index(fields=["applied"], name="user_sdwt_change_applied"),
        ]

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return f"{self.user_id} {self.from_user_sdwt_prod or '-'} -> {self.to_user_sdwt_prod} at {self.effective_from}"


__all__ = [
    "Affiliation",
    "User",
    "UserProfile",
    "UserSdwtProdAccess",
    "UserSdwtProdChange",
]
