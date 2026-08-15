# =============================================================================
# 모듈 설명: account 도메인 모델을 정의합니다.
# - 주요 대상: User, Affiliation, UserSdwtProdAccess, UserSdwtProdChange
# - 불변 조건: sabun은 사용자 고유키이며 각 모델은 db_table을 명시합니다.
# =============================================================================

"""계정/소속 도메인 모델 정의 모음.

- 주요 대상: User, Affiliation, UserSdwtProdAccess, UserSdwtProdChange
- 주요 엔드포인트/클래스: 각 모델 클래스
- 가정/불변 조건: sabun은 사용자 고유키이며 각 모델은 db_table을 명시함
"""
from __future__ import annotations

from typing import Any, Iterable

from django.contrib.auth.models import AbstractUser
from django.contrib.auth.base_user import BaseUserManager
from django.conf import settings
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower, Trim


ACCESS_SCOPE_PORTAL = "portal"
ACCESS_SCOPE_KEY_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
SYSTEM_APP_SCOPE_KEYS = (
    "access-stats",
    "appstore",
    "assistant",
    "emails",
    "l0-spider",
    "l1-spider",
    "l3-spider",
    "line-dashboard",
    "observer",
    "pm-spider",
    "teamstaff",
    "tttm-spider",
    "voc",
    "work-hub",
)
SYSTEM_ACCESS_SCOPE_KEYS = (ACCESS_SCOPE_PORTAL, *SYSTEM_APP_SCOPE_KEYS)
AFFILIATION_DATA_SCOPE_KEYS = (
    "assistant",
    "emails",
    "work-hub",
)


def _normalize_user_sdwt_prod(value: Any) -> str:
    """user_sdwt_prod 값을 공백 제거 기준으로 정규화합니다."""

    if not isinstance(value, str):
        return ""
    return value.strip()


def _normalize_user_sdwt_lookup_key(value: Any) -> str:
    """대소문자 비구분 비교용 user_sdwt_prod 키를 생성합니다."""

    normalized = _normalize_user_sdwt_prod(value)
    if not normalized:
        return ""
    return normalized.casefold()


def _same_user_sdwt_prod(left: Any, right: Any) -> bool:
    """두 user_sdwt_prod 값이 대소문자 비구분으로 같은지 확인합니다."""

    left_key = _normalize_user_sdwt_lookup_key(left)
    right_key = _normalize_user_sdwt_lookup_key(right)
    return bool(left_key and right_key and left_key == right_key)


def _build_user_sdwt_display_map(values: Iterable[Any]) -> dict[str, str]:
    """case-insensitive 비교용 lookup key와 표시값 매핑을 생성합니다."""

    display_map: dict[str, str] = {}
    for value in values:
        normalized = _normalize_user_sdwt_prod(value)
        lookup_key = _normalize_user_sdwt_lookup_key(normalized)
        if normalized and lookup_key and lookup_key not in display_map:
            display_map[lookup_key] = normalized
    return display_map


def _collapse_user_sdwt_prod_values(values: Iterable[Any]) -> set[str]:
    """user_sdwt_prod 값들을 대소문자 비구분으로 중복 제거합니다."""

    return set(_build_user_sdwt_display_map(values).values())


class UserManager(BaseUserManager):
    """sabun 기반 사용자 생성을 제공하는 커스텀 User 매니저입니다."""

    use_in_migrations = True

    def _create_user(self, sabun: str, password: str | None, **extra_fields) -> "User":
        """sabun 기반 사용자 생성 공통 로직을 수행합니다.

        입력:
        - sabun: 사용자 사번
        - password: 초기 비밀번호(없으면 unusable)
        - **extra_fields: 추가 필드 값

        반환:
        - User: 생성된 사용자 인스턴스

        부작용:
        - 사용자 레코드 생성(DB 쓰기)

        오류:
        - ValueError: sabun이 비어있을 때
        """
        # -----------------------------------------------------------------------------
        # 1) sabun 검증
        # -----------------------------------------------------------------------------
        if not sabun:
            raise ValueError("sabun is required")
        # -----------------------------------------------------------------------------
        # 2) 사용자 생성 및 저장
        # -----------------------------------------------------------------------------
        user = self.model(sabun=str(sabun).strip(), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, sabun: str, password: str | None = None, **extra_fields) -> "User":
        """일반 사용자 계정을 생성합니다.

        입력:
        - sabun: 사용자 사번
        - password: 초기 비밀번호(선택)
        - **extra_fields: 추가 필드 값

        반환:
        - User: 생성된 사용자 인스턴스

        부작용:
        - 사용자 레코드 생성(DB 쓰기)

        오류:
        - ValueError: sabun이 비어있을 때
        """
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(sabun, password, **extra_fields)

    def create_superuser(self, sabun: str, password: str | None = None, **extra_fields) -> "User":
        """슈퍼유저 계정을 생성합니다.

        입력:
        - sabun: 사용자 사번
        - password: 초기 비밀번호(선택)
        - **extra_fields: 추가 필드 값

        반환:
        - User: 생성된 슈퍼유저 인스턴스

        부작용:
        - 사용자 레코드 생성(DB 쓰기)

        오류:
        - ValueError: 필수 플래그가 올바르지 않을 때
        """
        # -----------------------------------------------------------------------------
        # 1) 기본 플래그 설정
        # -----------------------------------------------------------------------------
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        # -----------------------------------------------------------------------------
        # 2) 플래그 유효성 검증
        # -----------------------------------------------------------------------------
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        # -----------------------------------------------------------------------------
        # 3) 공통 생성 로직 호출
        # -----------------------------------------------------------------------------
        return self._create_user(sabun, password, **extra_fields)


class User(AbstractUser):
    """Keycloak 클레임을 로컬 세션에 연결하는 읽기 전용 shadow 사용자입니다."""

    username = models.CharField(max_length=150, null=True, blank=True)
    sabun = models.CharField(max_length=50, unique=True)
    knox_id = models.CharField(max_length=150, null=True, blank=True, unique=True)
    avatarid = models.CharField(max_length=50, null=True, blank=True)
    username_en = models.CharField(max_length=150, null=True, blank=True)
    givenname = models.CharField(max_length=150, null=True, blank=True)
    surname = models.CharField(max_length=150, null=True, blank=True)
    deptid = models.CharField(max_length=50, null=True, blank=True)
    department = models.CharField(max_length=128, null=True, blank=True)
    grd_name = models.CharField(max_length=150, null=True, blank=True)
    grdname_en = models.CharField(max_length=150, null=True, blank=True)
    busname = models.CharField(max_length=150, null=True, blank=True)
    intcode = models.CharField(max_length=64, null=True, blank=True)
    intname = models.CharField(max_length=150, null=True, blank=True)
    origincomp = models.CharField(max_length=150, null=True, blank=True)
    employeetype = models.CharField(max_length=150, null=True, blank=True)
    keycloak_subject = models.CharField(max_length=255, null=True, blank=True, unique=True)
    keycloak_group_id = models.CharField(max_length=255, blank=True, default="")
    keycloak_groups = models.JSONField(default=list, blank=True)
    keycloak_realm_roles = models.JSONField(default=list, blank=True)
    keycloak_client_roles = models.JSONField(default=dict, blank=True)
    affiliation_snapshot = models.JSONField(default=dict, blank=True)
    keycloak_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "account_user"

    objects = UserManager()

    USERNAME_FIELD = "sabun"
    REQUIRED_FIELDS: list[str] = []

    def __str__(self) -> str:  # 사람이 읽는 표현(커버리지 제외): pragma: no cover
        """사용자 표시용 문자열을 반환합니다."""
        return self.get_username()


class Affiliation(models.Model):
    """department/line/user_sdwt_prod 조합의 허용 목록(소속 hierarchy)을 저장하는 모델입니다."""

    department = models.CharField(max_length=128)
    line = models.CharField(max_length=64)
    user_sdwt_prod = models.CharField(max_length=64)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "account_affiliation"
        constraints = [
            models.UniqueConstraint(
                Lower(Trim("user_sdwt_prod")),
                name="uniq_acc_aff_usr_sdw_ci",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(user_sdwt_prod="")
                    & models.Q(
                        user_sdwt_prod=Trim(models.F("user_sdwt_prod")),
                    )
                ),
                name="chk_acc_aff_usr_sdw_trim",
            ),
        ]
        indexes = [
            models.Index(fields=["department"], name="idx_acc_aff_dep"),
            models.Index(fields=["line"], name="idx_acc_aff_ln"),
            models.Index(fields=["user_sdwt_prod"], name="idx_acc_aff_usr_sdw_prd"),
            models.Index(fields=["is_active"], name="idx_acc_aff_act"),
            models.Index(
                fields=["line", "user_sdwt_prod"],
                name="idx_acc_aff_ln_usr_sdw_prd",
            ),
        ]

    def __str__(self) -> str:  # 사람이 읽는 표현(커버리지 제외): pragma: no cover
        """소속 표시용 문자열을 반환합니다."""
        return f"{self.department} / {self.line} / {self.user_sdwt_prod}"


class UserCurrentAffiliation(models.Model):
    """앱에서 실제 권한 판단에 사용하는 사용자의 현재 소속을 저장하는 모델입니다."""

    class Sources(models.TextChoices):
        EXTERNAL_AUTO = "external_auto", "External Auto"
        USER_SELECTED = "user_selected", "User Selected"
        ADMIN_ASSIGNED = "admin_assigned", "Admin Assigned"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="current_affiliation",
    )
    affiliation = models.ForeignKey(
        Affiliation,
        on_delete=models.PROTECT,
        related_name="current_users",
    )
    source = models.CharField(
        max_length=32,
        choices=Sources.choices,
        default=Sources.USER_SELECTED,
    )
    requires_reconfirm = models.BooleanField(default=False)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "account_user_current_affiliation"
        indexes = [
            models.Index(fields=["affiliation"], name="idx_acc_usr_cur_aff_aff"),
            models.Index(fields=["requires_reconfirm"], name="idx_acc_usr_cur_aff_req"),
        ]

    def __str__(self) -> str:  # 사람이 읽는 표현(커버리지 제외): pragma: no cover
        """현재 소속 표시용 문자열을 반환합니다."""
        return f"{self.user_id} -> {self.affiliation.user_sdwt_prod}"


class UserSdwtProdAccess(models.Model):
    """사용자의 소속 옵션별 접근/관리 권한을 저장하는 모델입니다."""

    class Roles(models.TextChoices):
        VIEWER = "viewer", "Viewer"
        MEMBER = "member", "Member"
        MANAGER = "manager", "Manager"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sdwt_prod_access",
    )
    affiliation = models.ForeignKey(
        Affiliation,
        on_delete=models.CASCADE,
        related_name="user_accesses",
    )
    role = models.CharField(max_length=16, choices=Roles.choices, default=Roles.VIEWER)
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
        constraints = [
            models.UniqueConstraint(
                fields=["user", "affiliation"],
                name="uniq_acc_usr_sdw_prd_acs_aff",
            ),
            models.CheckConstraint(
                condition=models.Q(role__in=("viewer", "member", "manager")),
                name="chk_acc_usr_sdw_acs_role",
            ),
        ]
        indexes = [
            models.Index(fields=["user"], name="idx_acc_usr_sdw_prd_acs_usr"),
            models.Index(
                fields=["affiliation"],
                name="idx_acc_usr_sdw_prd_acs_aff",
            ),
        ]

    @property
    def user_sdwt_prod(self) -> str:
        """권한이 연결된 소속의 user_sdwt_prod 값을 반환합니다."""
        return self.affiliation.user_sdwt_prod if self.affiliation_id else ""

    def __str__(self) -> str:  # 사람이 읽는 표현(커버리지 제외): pragma: no cover
        """접근 권한 표시용 문자열을 반환합니다."""
        return f"{self.user_id} -> {self.user_sdwt_prod} ({self.role})"


class AccessRole(models.TextChoices):
    """모든 접근 scope에서 공통으로 사용할 역할을 정의합니다."""

    USER = "user", "User"
    ADMIN = "admin", "Admin"


class AccessSource(models.TextChoices):
    """최종 접근 판정의 결정 근거를 정의합니다."""

    SUPERUSER_BYPASS = "superuser_bypass", "Superuser Bypass"
    PORTAL_ACCESS_REQUIRED = "portal_access_required", "Portal Access Required"
    SCOPE_INACTIVE = "scope_inactive", "Scope Inactive"
    EXPLICIT_DENIED = "explicit_denied", "Explicit Denied"
    EXPLICIT_ALLOWED = "explicit_allowed", "Explicit Allowed"
    EXPLICIT_PENDING = "explicit_pending", "Explicit Pending"
    POLICY_DEPARTMENT = "policy_department", "Department Policy"
    NONE = "none", "None"
    SCOPE_NOT_FOUND = "scope_not_found", "Scope Not Found"


class AccessScope(models.Model):
    """포털/앱/기능 단위 접근 권한 대상을 정의합니다."""

    class ScopeTypes(models.TextChoices):
        PORTAL = "portal", "Portal"
        APP = "app", "App"
        FEATURE = "feature", "Feature"

    class DataScopeTypes(models.TextChoices):
        NONE = "none", "None"
        AFFILIATION = "affiliation", "Affiliation"

    key = models.CharField(
        max_length=64,
        unique=True,
        validators=[
            RegexValidator(
                regex=ACCESS_SCOPE_KEY_PATTERN,
                message="scope key는 소문자 영숫자와 하이픈만 사용할 수 있습니다.",
            )
        ],
    )
    name = models.CharField(max_length=128)
    scope_type = models.CharField(max_length=16, choices=ScopeTypes.choices, default=ScopeTypes.APP)
    data_scope_type = models.CharField(
        max_length=16,
        choices=DataScopeTypes.choices,
        default=DataScopeTypes.NONE,
    )
    include_current_affiliation = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    requestable = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "account_access_scope"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(scope_type__in=("portal", "app", "feature")),
                name="chk_acc_scp_typ_valid",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(key=ACCESS_SCOPE_PORTAL, scope_type="portal")
                    | (
                        ~models.Q(key=ACCESS_SCOPE_PORTAL)
                        & ~models.Q(scope_type="portal")
                    )
                ),
                name="chk_acc_scp_portal_key_type",
            ),
            models.CheckConstraint(
                condition=models.Q(key__regex=ACCESS_SCOPE_KEY_PATTERN),
                name="chk_acc_scp_key_fmt",
            ),
            models.CheckConstraint(
                condition=models.Q(data_scope_type__in=("none", "affiliation")),
                name="chk_acc_scp_dat_typ_valid",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(data_scope_type="affiliation")
                    | models.Q(include_current_affiliation=False)
                ),
                name="chk_acc_scp_cur_aff_scope",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(scope_type="portal")
                    | models.Q(data_scope_type="none", include_current_affiliation=False)
                ),
                name="chk_acc_scp_portal_no_data",
            ),
        ]
        indexes = [
            models.Index(fields=["scope_type"], name="idx_acc_acc_scp_typ"),
            models.Index(fields=["is_active"], name="idx_acc_acc_scp_act"),
        ]

    def __str__(self) -> str:  # 사람이 읽는 표현(커버리지 제외): pragma: no cover
        """접근 권한 대상 표시용 문자열을 반환합니다."""
        return self.key

class AccessPolicyRule(models.Model):
    """scope별 기본 접근 허용 규칙을 저장합니다."""

    class RuleTypes(models.TextChoices):
        DEPARTMENT = "department", "Department"

    scope = models.ForeignKey(AccessScope, on_delete=models.CASCADE, related_name="policy_rules")
    rule_type = models.CharField(max_length=32, choices=RuleTypes.choices)
    value = models.CharField(max_length=150, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "account_access_policy_rule"
        constraints = [
            models.UniqueConstraint(
                Lower(Trim("value")),
                "scope",
                "rule_type",
                name="uniq_acc_pol_scp_typ_val_ci",
            ),
            models.CheckConstraint(
                condition=models.Q(rule_type="department"),
                name="chk_acc_pol_rule_typ_dep",
            ),
        ]
        indexes = [
            models.Index(fields=["scope", "is_active"], name="idx_acc_pol_rule_scp_act"),
            models.Index(fields=["rule_type"], name="idx_acc_pol_rule_typ"),
        ]

    def __str__(self) -> str:  # 사람이 읽는 표현(커버리지 제외): pragma: no cover
        """접근 정책 규칙 표시용 문자열을 반환합니다."""
        return f"{self.scope.key}:{self.rule_type}:{self.value}"

    def clean(self) -> None:
        """부서 정책에 비교할 부서명이 있는지 검증합니다."""

        super().clean()
        value = (self.value or "").strip()
        if not value:
            raise ValidationError({"value": "정책 값은 비워둘 수 없습니다."})
        self.value = value


class UserAccess(models.Model):
    """사용자별 scope 접근 상태를 저장합니다."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ALLOWED = "allowed", "Allowed"
        DENIED = "denied", "Denied"

    class DataScopeModes(models.TextChoices):
        DEFAULT = "default", "Default"
        ALL = "all", "All"

    scope = models.ForeignKey(AccessScope, on_delete=models.CASCADE, related_name="user_accesses")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="access_grants",
    )
    department = models.CharField(max_length=128, null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    role = models.CharField(max_length=16, choices=AccessRole.choices, default=AccessRole.USER)
    data_scope_mode = models.CharField(
        max_length=16,
        choices=DataScopeModes.choices,
        default=DataScopeModes.DEFAULT,
    )
    reason = models.TextField(null=True, blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="access_decisions",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "account_user_access"
        constraints = [
            models.UniqueConstraint(
                fields=["scope", "user"],
                name="uniq_acc_usr_acc_scp_usr",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=("pending", "allowed", "denied")),
                name="chk_acc_usr_acc_sts_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(role__in=("user", "admin")),
                name="chk_acc_usr_acc_role_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(status="allowed") | models.Q(role="user"),
                name="chk_acc_usr_acc_role_state",
            ),
            models.CheckConstraint(
                condition=models.Q(data_scope_mode__in=("default", "all")),
                name="chk_acc_usr_acc_dat_mode",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(status="allowed")
                    | models.Q(data_scope_mode="default")
                ),
                name="chk_acc_usr_acc_dat_state",
            ),
        ]
        indexes = [
            models.Index(fields=["scope"], name="idx_acc_usr_acc_scp"),
            models.Index(fields=["status"], name="idx_acc_usr_acc_sts"),
            models.Index(fields=["department"], name="idx_acc_usr_acc_dep"),
        ]

    def __str__(self) -> str:  # 사람이 읽는 표현(커버리지 제외): pragma: no cover
        """사용자 접근 상태 표시용 문자열을 반환합니다."""
        return f"{self.scope_id}:{self.user_id} ({self.status})"


class UserScopeAffiliationGrant(models.Model):
    """사용자에게 앱 scope별 소속 데이터 범위를 명시적으로 부여합니다."""

    class Sources(models.TextChoices):
        MANUAL = "manual", "Manual"
        POLICY = "policy", "Policy"
        EXTERNAL = "external", "External"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="scope_affiliation_grants",
    )
    scope = models.ForeignKey(
        AccessScope,
        on_delete=models.PROTECT,
        related_name="affiliation_grants",
    )
    affiliation = models.ForeignKey(
        Affiliation,
        on_delete=models.PROTECT,
        related_name="scope_user_grants",
    )
    source = models.CharField(
        max_length=16,
        choices=Sources.choices,
        default=Sources.MANUAL,
    )
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    reason = models.TextField(null=True, blank=True)
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="scope_affiliation_grants_made",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "account_user_scope_aff_grant"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "scope", "affiliation"],
                name="uniq_acc_usr_scp_aff_grt",
            ),
            models.CheckConstraint(
                condition=models.Q(source__in=("manual", "policy", "external")),
                name="chk_acc_usr_scp_aff_src",
            ),
        ]
        indexes = [
            models.Index(
                fields=["user", "scope", "is_active"],
                name="idx_acc_usr_scp_aff_act",
            ),
            models.Index(
                fields=["scope", "affiliation", "is_active"],
                name="idx_acc_scp_aff_grt_act",
            ),
            models.Index(fields=["expires_at"], name="idx_acc_scp_aff_exp"),
        ]

    def __str__(self) -> str:  # 사람이 읽는 표현(커버리지 제외): pragma: no cover
        """앱별 소속 데이터 grant 표시 문자열을 반환합니다."""
        return f"{self.user_id}:{self.scope_id}:{self.affiliation_id}"


class AccessAuditLog(models.Model):
    """scope 접근 권한과 정책 변경 이력을 저장합니다."""

    class Actions(models.TextChoices):
        REQUEST = "request", "Request"
        APPROVE = "approve", "Approve"
        REJECT = "reject", "Reject"
        GRANT = "grant", "Grant"
        REVOKE = "revoke", "Revoke"
        RESET_TO_POLICY = "reset_to_policy", "Reset to policy"
        CHANGE_ROLE = "change_role", "Change role"
        POLICY_CREATE = "policy_create", "Policy create"
        POLICY_UPDATE = "policy_update", "Policy update"
        POLICY_DELETE = "policy_delete", "Policy delete"
        SCOPE_CREATE = "scope_create", "Scope create"
        SCOPE_UPDATE = "scope_update", "Scope update"
        SCOPE_DELETE = "scope_delete", "Scope delete"
        DATA_SCOPE_GRANT = "data_scope_grant", "Data scope grant"
        DATA_SCOPE_REVOKE = "data_scope_revoke", "Data scope revoke"
        DATA_SCOPE_CHANGE = "data_scope_change", "Data scope change"
        AFFILIATION_ROLE_GRANT = "affiliation_role_grant", "Affiliation role grant"
        AFFILIATION_ROLE_CHANGE = "affiliation_role_change", "Affiliation role change"
        AFFILIATION_ROLE_REVOKE = "affiliation_role_revoke", "Affiliation role revoke"
        AFFILIATION_CREATE = "affiliation_create", "Affiliation create"
        AFFILIATION_UPDATE = "affiliation_update", "Affiliation update"
        AFFILIATION_ACTIVATE = "affiliation_activate", "Affiliation activate"
        AFFILIATION_DEACTIVATE = "affiliation_deactivate", "Affiliation deactivate"

    scope = models.ForeignKey(
        AccessScope,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="audit_logs",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="access_audit_actions",
    )
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="access_audit_targets",
    )
    affiliation = models.ForeignKey(
        Affiliation,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="access_audit_logs",
    )
    policy_rule = models.ForeignKey(
        AccessPolicyRule,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=32, choices=Actions.choices)
    before = models.JSONField(default=dict, blank=True)
    after = models.JSONField(default=dict, blank=True)
    reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "account_access_audit_log"
        indexes = [
            models.Index(fields=["scope", "created_at"], name="idx_acc_aud_scp_ct"),
            models.Index(fields=["affiliation", "created_at"], name="idx_acc_aud_aff_ct"),
            models.Index(fields=["target_user", "created_at"], name="idx_acc_aud_tgt_ct"),
            models.Index(fields=["actor", "created_at"], name="idx_acc_aud_act_ct"),
            models.Index(fields=["action"], name="idx_acc_aud_action"),
        ]

    def __str__(self) -> str:  # 사람이 읽는 표현(커버리지 제외): pragma: no cover
        """감사 로그 표시용 문자열을 반환합니다."""
        return f"{self.action}:{self.scope_id}:{self.target_user_id}"


class UserSdwtProdChange(models.Model):
    """사용자 소속(user_sdwt_prod) 변경 요청/승인/적용 이력을 저장하는 모델입니다."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        SUPERSEDED = "SUPERSEDED", "Superseded"

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
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
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
    rejection_reason = models.TextField(null=True, blank=True)
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
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(status="PENDING"),
                name="uniq_acc_usr_sdw_chg_pend",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        status="APPROVED",
                        approved=True,
                        applied=True,
                        approved_at__isnull=False,
                        rejection_reason__isnull=True,
                    )
                    | models.Q(
                        status="PENDING",
                        approved=False,
                        applied=False,
                        approved_by__isnull=True,
                        approved_at__isnull=True,
                        rejection_reason__isnull=True,
                    )
                    | models.Q(
                        status="REJECTED",
                        approved=False,
                        applied=False,
                        approved_at__isnull=False,
                    )
                    | models.Q(
                        status="SUPERSEDED",
                        approved=False,
                        applied=False,
                        approved_by__isnull=True,
                        approved_at__isnull=True,
                    )
                ),
                name="chk_acc_usr_sdw_chg_state",
            ),
        ]
        indexes = [
            models.Index(
                fields=["user", "effective_from"],
                name="idx_acc_usr_sdw_prd_chg_364a4",
            ),
            models.Index(fields=["applied"], name="idx_acc_usr_sdw_prd_chg_app"),
        ]

    def __str__(self) -> str:  # 사람이 읽는 표현(커버리지 제외): pragma: no cover
        """소속 변경 표시용 문자열을 반환합니다."""
        return f"{self.user_id} {self.from_user_sdwt_prod or '-'} -> {self.to_user_sdwt_prod} at {self.effective_from}"


class ExternalAffiliationSnapshot(models.Model):
    """외부 DB에서 가져온 예측 소속(user_sdwt_prod) 스냅샷을 저장합니다."""

    knox_id = models.CharField(max_length=150, unique=True)
    username = models.CharField(max_length=150, null=True, blank=True)
    department = models.CharField(max_length=128, null=True, blank=True)
    predicted_user_sdwt_prod = models.CharField(max_length=64)
    source_updated_at = models.DateTimeField()
    last_seen_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "account_external_affiliation_snapshot"
        indexes = [
            models.Index(
                fields=["predicted_user_sdwt_prod"],
                name="idx_acc_ext_aff_snp_pred_54654",
            ),
            models.Index(
                fields=["source_updated_at"],
                name="idx_acc_ext_aff_snp_src_upd_at",
            ),
        ]

    def __str__(self) -> str:  # 사람이 읽는 표현(커버리지 제외): pragma: no cover
        """외부 소속 스냅샷 표시용 문자열을 반환합니다."""
        return f"{self.knox_id} -> {self.predicted_user_sdwt_prod}"


__all__ = [
    "AFFILIATION_DATA_SCOPE_KEYS",
    "Affiliation",
    "ExternalAffiliationSnapshot",
    "User",
    "UserCurrentAffiliation",
    "UserScopeAffiliationGrant",
    "UserSdwtProdAccess",
    "UserSdwtProdChange",
]
