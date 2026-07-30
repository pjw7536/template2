# =============================================================================
# 모듈 설명: account 도메인의 Django Admin 설정을 제공합니다.
# - 주요 대상: 사용자/소속/권한/변경 요청 관리 화면
# - 불변 조건: 관리자 작업은 서비스 정책을 따라야 합니다.
# =============================================================================

"""계정 도메인 Django Admin 설정 모음.

- 주요 대상: 사용자/소속/권한/변경 요청 관리 화면
- 주요 엔드포인트/클래스: AccountUserAdmin, UserSdwtProdChangeAdmin 등
- 가정/불변 조건: 관리 화면에서의 변경은 서비스 정책을 준수해야 함
"""
from __future__ import annotations

from django import forms
from django.contrib import admin
from django.contrib import messages
from django.contrib.admin.helpers import ActionForm
from django.contrib.admin.widgets import AdminSplitDateTime
from django.contrib.auth.admin import GroupAdmin as DjangoGroupAdmin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import BaseUserCreationForm, SetUnusablePasswordMixin, UserChangeForm, UsernameField
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from api.account import services
from api.account.selectors import get_current_affiliation_values, get_current_user_sdwt_prod_change
from api.account.models import (
    AccessAuditLog,
    AccessPolicyRule,
    AccessScope,
    Affiliation,
    ExternalAffiliationSnapshot,
    User,
    UserAccess,
    UserCurrentAffiliation,
    UserScopeAffiliationGrant,
    UserSdwtProdAccess,
    UserSdwtProdChange,
)
from api.common.services import UNASSIGNED_USER_SDWT_PROD


_SENSITIVE_USER_PERMISSION_FIELDS = ("is_staff", "is_superuser", "groups", "user_permissions")


def _user_has_portal_admin_role(*, user_id: int | None) -> bool:
    """사용자의 유효한 Portal admin 역할 보유 여부를 반환합니다."""

    if not user_id:
        return False
    return services.can_manage_access(user=User.objects.filter(pk=user_id).first())


class SuperuserWriteAdminMixin:
    """민감한 접근 권한 모델의 Admin 쓰기를 superuser에게만 허용합니다."""

    def has_add_permission(self, request):
        """superuser에게만 생성 권한을 허용합니다."""

        return bool(getattr(request.user, "is_superuser", False)) and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        """superuser에게만 변경 권한을 허용합니다."""

        return bool(getattr(request.user, "is_superuser", False)) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        """superuser에게만 삭제 권한을 허용합니다."""

        return bool(getattr(request.user, "is_superuser", False)) and super().has_delete_permission(request, obj)


class ReadOnlyAdminMixin:
    """Portal API를 유일한 쓰기 경로로 유지할 모델을 읽기 전용으로 제공합니다."""

    actions = ()

    def has_add_permission(self, request):
        """Admin에서 직접 생성을 허용하지 않습니다."""

        return False

    def has_change_permission(self, request, obj=None):
        """Admin에서 직접 변경을 허용하지 않습니다."""

        return False

    def has_delete_permission(self, request, obj=None):
        """Admin에서 직접 삭제를 허용하지 않습니다."""

        return False


class AffiliationAdminForm(forms.ModelForm):
    """소속 생성 시 운영 사유를 함께 받는 Admin 폼입니다."""

    reason = forms.CharField(
        label="생성 사유",
        max_length=500,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="소속을 추가하는 업무 목적이나 동기화 근거를 입력하세요.",
    )

    class Meta:
        model = Affiliation
        fields = ("department", "line", "user_sdwt_prod")


class AffiliationActionForm(ActionForm):
    """소속 활성 상태 일괄 action의 운영 사유를 받습니다."""

    reason = forms.CharField(
        label="변경 사유",
        max_length=500,
        required=True,
        widget=forms.TextInput(
            attrs={"placeholder": "활성 상태 변경 사유를 입력하세요"}
        ),
    )


try:
    admin.site.unregister(Group)
except admin.sites.NotRegistered:
    pass


@admin.register(Group)
class AccountGroupAdmin(DjangoGroupAdmin):
    """Django Group의 권한 구성을 superuser만 관리하도록 제한합니다."""

    actions = ()

    def has_add_permission(self, request):
        """superuser에게만 그룹 생성 권한을 허용합니다."""

        return bool(getattr(request.user, "is_superuser", False)) and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        """superuser에게만 그룹 변경을 허용합니다."""

        return bool(getattr(request.user, "is_superuser", False)) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        """superuser에게만 그룹 삭제를 허용합니다."""

        return bool(getattr(request.user, "is_superuser", False)) and super().has_delete_permission(request, obj)


class AccountUserCreationForm(SetUnusablePasswordMixin, BaseUserCreationForm):
    """관리자 사용자 생성을 위한 커스텀 폼입니다."""

    usable_password = SetUnusablePasswordMixin.create_usable_password_field()

    class Meta(BaseUserCreationForm.Meta):
        model = User
        fields = ("knox_id",)
        field_classes = {"knox_id": UsernameField}

    def __init__(self, *args, **kwargs):
        """비밀번호 입력을 선택 사항으로 변경합니다.

        입력:
        - *args, **kwargs: Django 폼 초기화 인자

        반환:
        - 없음

        부작용:
        - password 필드의 required 속성을 변경

        오류:
        - 없음
        """
        super().__init__(*args, **kwargs)
        # -----------------------------------------------------------------------------
        # 1) 비밀번호 필드 필수 해제
        # -----------------------------------------------------------------------------
        self.fields["password1"].required = False
        self.fields["password2"].required = False

        # -----------------------------------------------------------------------------
        # 2) knox_id 필수 설정
        # -----------------------------------------------------------------------------
        self.fields["knox_id"].required = True

    def clean(self):
        """knox_id 기반 식별 값 중복을 확인합니다.

        입력:
        - 없음

        반환:
        - dict: 정제된 폼 데이터

        부작용:
        - knox_id 중복 시 에러 추가

        오류:
        - 없음
        """
        # -----------------------------------------------------------------------------
        # 1) 기본 검증 수행
        # -----------------------------------------------------------------------------
        cleaned_data = super().clean()

        # -----------------------------------------------------------------------------
        # 2) knox_id 확인
        # -----------------------------------------------------------------------------
        knox_id = cleaned_data.get("knox_id")
        if not knox_id:
            return cleaned_data

        # -----------------------------------------------------------------------------
        # 3) 사용자 식별 필드 중복 확인
        # -----------------------------------------------------------------------------
        username_field = User.USERNAME_FIELD
        if (
            User.objects.filter(**{username_field: knox_id})
            .exclude(pk=getattr(self.instance, "pk", None))
            .exists()
        ):
            self.add_error("knox_id", "이미 사용 중인 식별 값입니다.")
        return cleaned_data

    def save(self, commit=True):
        """knox_id를 사용자 식별 필드에 반영해 저장합니다.

        입력:
        - commit: 즉시 저장 여부

        반환:
        - User: 저장(또는 미저장)된 사용자 인스턴스

        부작용:
        - 사용자 식별 필드 값 설정

        오류:
        - 없음
        """
        # -----------------------------------------------------------------------------
        # 1) 기본 저장 준비
        # -----------------------------------------------------------------------------
        user = super().save(commit=False)

        # -----------------------------------------------------------------------------
        # 2) 사용자 식별 필드 동기화
        # -----------------------------------------------------------------------------
        knox_id = self.cleaned_data.get("knox_id")
        if knox_id:
            setattr(user, User.USERNAME_FIELD, knox_id)

        # -----------------------------------------------------------------------------
        # 3) 저장 및 M2M 처리
        # -----------------------------------------------------------------------------
        if commit:
            user.save()
            if hasattr(self, "save_m2m"):
                self.save_m2m()
        return user


class AccountUserChangeForm(UserChangeForm):
    """관리자 사용자 변경을 위한 커스텀 폼입니다."""

    user_sdwt_prod_effective_from = forms.SplitDateTimeField(
        required=False,
        label="user_sdwt_prod 변경 시각",
        help_text="현재 user_sdwt_prod가 적용되는 기준 시각(effective_from)입니다. "
        "이 값을 변경하면 Emails에서 소속 변경 이후 메일 이동 시 이 시각이 사용됩니다.",
        widget=AdminSplitDateTime(),
    )

    class Meta(UserChangeForm.Meta):
        model = User
        exclude = (User.USERNAME_FIELD,)
        field_classes = {"knox_id": UsernameField}

    def __init__(self, *args, **kwargs):
        """현재 user_sdwt_prod 변경 시각을 초기값으로 채웁니다.

        입력:
        - *args, **kwargs: Django 폼 초기화 인자

        반환:
        - 없음

        부작용:
        - user_sdwt_prod_effective_from 초기값 설정

        오류:
        - 없음
        """
        super().__init__(*args, **kwargs)
        # -----------------------------------------------------------------------------
        # 1) 신규 객체는 초기값 설정 없이 종료
        # -----------------------------------------------------------------------------
        if not getattr(self.instance, "pk", None):
            return

        # -----------------------------------------------------------------------------
        # 2) 현재 변경 이력 조회 및 초기값 설정
        # -----------------------------------------------------------------------------
        change = get_current_user_sdwt_prod_change(user=self.instance)
        if change is None:
            return

        self.fields["user_sdwt_prod_effective_from"].initial = change.effective_from


@admin.register(User)
class AccountUserAdmin(DjangoUserAdmin):
    """사용자(User) 관리 화면 설정입니다."""

    form = AccountUserChangeForm
    add_form = AccountUserCreationForm
    actions = ()
    ordering = ("knox_id",)
    list_display = (
        "knox_id",
        "email",
        "current_department",
        "current_line",
        "current_user_sdwt_prod",
        "current_requires_reconfirm",
        "is_staff",
        "is_superuser",
        "is_active",
    )
    list_filter = (
        "is_staff",
        "is_superuser",
        "is_active",
        "current_affiliation__affiliation__line",
        "current_affiliation__requires_reconfirm",
    )
    search_fields = (
        "knox_id",
        "email",
        "department",
        "username",
        "first_name",
        "last_name",
        "current_affiliation__affiliation__department",
        "current_affiliation__affiliation__line",
        "current_affiliation__affiliation__user_sdwt_prod",
    )
    readonly_fields = (
        "current_department",
        "current_line",
        "current_user_sdwt_prod",
        "current_requires_reconfirm",
        "current_affiliation_confirmed_at",
    )

    fieldsets = (
        (None, {"fields": ("knox_id", "password")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
        ("Identity", {"fields": ("email",)}),
        ("Names", {"fields": ("username", "first_name", "last_name", "username_en", "givenname", "surname")}),
        (
            "Organization",
            {
                "fields": (
                    "deptid",
                    "department",
                    "current_department",
                    "current_line",
                    "current_user_sdwt_prod",
                    "current_requires_reconfirm",
                    "current_affiliation_confirmed_at",
                    "user_sdwt_prod_effective_from",
                    "grd_name",
                    "grdname_en",
                    "busname",
                    "intcode",
                    "intname",
                    "origincomp",
                    "employeetype",
                )
            },
        ),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "knox_id",
                    "usable_password",
                    "password1",
                    "password2",
                    "is_staff",
                    "is_superuser",
                ),
            },
        ),
    )

    def get_readonly_fields(self, request, obj=None):
        """일반 staff가 인증·권한 관련 민감 필드를 변경하지 못하게 합니다."""

        readonly_fields = tuple(super().get_readonly_fields(request, obj))
        if getattr(request.user, "is_superuser", False):
            return readonly_fields
        return tuple(dict.fromkeys((*readonly_fields, *_SENSITIVE_USER_PERMISSION_FIELDS)))

    def has_change_permission(self, request, obj=None):
        """일반 staff가 superuser 또는 Portal admin 계정을 변경하지 못하게 합니다."""

        if (
            obj is not None
            and not getattr(request.user, "is_superuser", False)
            and _user_has_portal_admin_role(user_id=obj.pk)
        ):
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        """감사 대상 사용자 보존을 위해 물리 삭제를 허용하지 않습니다."""

        return False

    @admin.display(
        ordering="current_affiliation__affiliation__department",
        description="현재 department",
    )
    def current_department(self, obj):
        return get_current_affiliation_values(user=obj).get("department") or ""

    @admin.display(ordering="current_affiliation__affiliation__line", description="현재 line")
    def current_line(self, obj):
        return get_current_affiliation_values(user=obj).get("line") or ""

    @admin.display(
        ordering="current_affiliation__affiliation__user_sdwt_prod",
        description="현재 user_sdwt_prod",
    )
    def current_user_sdwt_prod(self, obj):
        return get_current_affiliation_values(user=obj).get("user_sdwt_prod") or ""

    @admin.display(
        boolean=True,
        ordering="current_affiliation__requires_reconfirm",
        description="재확인 필요",
    )
    def current_requires_reconfirm(self, obj):
        return bool(get_current_affiliation_values(user=obj).get("requires_reconfirm"))

    @admin.display(
        ordering="current_affiliation__confirmed_at",
        description="소속 확인 시각",
    )
    def current_affiliation_confirmed_at(self, obj):
        return get_current_affiliation_values(user=obj).get("confirmed_at")

    def save_model(self, request, obj, form, change):  # 타입 검사 생략: type: ignore[override]
        """관리자 저장 시 user_sdwt_prod 변경 시각을 동기화합니다.

        입력:
        - 요청: Django HttpRequest
        - obj: 저장 대상 User 객체
        - form: 변경 폼
        - change: 변경 여부 플래그

        반환:
        - 없음

        부작용:
        - UserSdwtProdChange.effective_from 갱신 가능
        - 관리자 메시지 출력

        오류:
        - 없음
        """
        # -----------------------------------------------------------------------------
        # 1) 기본 저장 처리
        # -----------------------------------------------------------------------------
        super().save_model(request, obj, form, change)

        # -----------------------------------------------------------------------------
        # 2) 변경 시각 값 확인
        # -----------------------------------------------------------------------------
        effective_from = form.cleaned_data.get("user_sdwt_prod_effective_from")
        if effective_from is None:
            return

        # -----------------------------------------------------------------------------
        # 3) 타임존 보정
        # -----------------------------------------------------------------------------
        if timezone.is_naive(effective_from):
            effective_from = timezone.make_aware(effective_from, timezone.get_current_timezone())

        # -----------------------------------------------------------------------------
        # 4) 현재 user_sdwt_prod 유효성 확인
        # -----------------------------------------------------------------------------
        current_user_sdwt_prod = (get_current_affiliation_values(user=obj).get("user_sdwt_prod") or "").strip()
        if (
            not current_user_sdwt_prod
            or current_user_sdwt_prod.casefold() == UNASSIGNED_USER_SDWT_PROD.casefold()
        ):
            return

        # -----------------------------------------------------------------------------
        # 5) 변경 이력 조회
        # -----------------------------------------------------------------------------
        change_row = get_current_user_sdwt_prod_change(user=obj)
        if change_row is None:
            self.message_user(
                request,
                "현재 user_sdwt_prod에 대한 UserSdwtProdChange 기록이 없어 변경 시각을 저장할 수 없습니다. "
                "먼저 소속 변경을 적용(승인)하거나 UserSdwtProdChange에서 레코드를 생성해주세요.",
                level=messages.WARNING,
            )
            return

        # -----------------------------------------------------------------------------
        # 6) 변경 시각 업데이트
        # -----------------------------------------------------------------------------
        if change_row.effective_from != effective_from:
            change_row.effective_from = effective_from
            change_row.save(update_fields=["effective_from"])
            self.message_user(
                request,
                f"user_sdwt_prod 변경 시각을 {effective_from.isoformat()}로 업데이트했습니다.",
                level=messages.SUCCESS,
            )

    def get_result_label(self, result):  # 타입 검사 생략: type: ignore[override]
        return result.knox_id or str(result.pk)


@admin.register(Affiliation)
class AffiliationAdmin(SuperuserWriteAdminMixin, admin.ModelAdmin):
    """소속 생성과 감사 가능한 활성 상태 action만 허용합니다."""

    actions = ("activate_affiliations", "deactivate_affiliations")
    action_form = AffiliationActionForm
    form = AffiliationAdminForm
    list_display = ("department", "line", "user_sdwt_prod", "is_active")
    search_fields = ("department", "line", "user_sdwt_prod")
    list_filter = ("line", "is_active")
    ordering = ("department", "line", "user_sdwt_prod")

    def get_readonly_fields(self, request, obj=None):
        """기존 소속의 식별 값과 활성 상태를 직접 수정하지 못하게 합니다."""

        if obj is not None:
            return tuple(field.name for field in self.model._meta.fields)
        return ("is_active", "created_at")

    def has_change_permission(self, request, obj=None):
        """목록 action은 허용하되 기존 소속의 개별 변경 화면은 읽기 전용으로 둡니다."""

        if obj is not None:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        """연결된 권한 기준점인 소속의 물리 삭제를 금지합니다."""

        return False

    def save_model(self, request, obj, form, change):
        """새 소속은 감사 가능한 생성 서비스로만 저장합니다."""

        if change:
            raise ValidationError("기존 소속은 활성/비활성 action으로만 변경할 수 있습니다.")
        services.create_affiliation(
            actor=request.user,
            affiliation=obj,
            reason=form.cleaned_data["reason"],
            source=services.AFFILIATION_AUDIT_SOURCE_DJANGO_ADMIN,
        )

    def delete_model(self, request, obj):
        """소속 물리 삭제 요청을 명시적으로 거부합니다."""

        raise PermissionDenied("소속은 삭제할 수 없습니다. 비활성화 action을 사용하세요.")

    def _set_affiliations_active(self, *, request, queryset, is_active):
        """선택 소속을 운영자 사유와 함께 한 transaction에서 변경합니다."""

        payload, status_code = services.set_affiliations_active(
            actor=request.user,
            affiliation_ids=list(
                queryset.order_by("id").values_list("id", flat=True)
            ),
            is_active=is_active,
            reason=request.POST.get("reason", ""),
        )
        if status_code != 200:
            self.message_user(
                request,
                f"상태를 변경하지 못했습니다: {payload.get('error', 'unknown_error')}",
                level=messages.ERROR,
            )
            return
        self.message_user(
            request,
            (
                f"상태 변경: {payload['updated']}건, "
                f"변경 없음: {payload['unchanged']}건"
            ),
            level=messages.SUCCESS,
        )

    @admin.action(description="선택한 소속 활성화")
    def activate_affiliations(self, request, queryset):
        """선택 소속을 감사 가능한 서비스 경로로 활성화합니다."""

        self._set_affiliations_active(
            request=request,
            queryset=queryset,
            is_active=True,
        )

    @admin.action(description="선택한 소속 비활성화")
    def deactivate_affiliations(self, request, queryset):
        """선택 소속을 감사 가능한 서비스 경로로 비활성화합니다."""

        self._set_affiliations_active(
            request=request,
            queryset=queryset,
            is_active=False,
        )


@admin.register(UserCurrentAffiliation)
class UserCurrentAffiliationAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    """현재 소속은 제품 서비스로만 변경하고 Admin에서는 읽기 전용으로 제공합니다."""

    list_display = (
        "user_knox_id",
        "department",
        "line",
        "user_sdwt_prod",
        "source",
        "requires_reconfirm",
        "confirmed_at",
    )
    list_filter = ("source", "requires_reconfirm", "affiliation__line")
    search_fields = (
        "user__knox_id",
        "user__email",
        "affiliation__department",
        "affiliation__line",
        "affiliation__user_sdwt_prod",
    )
    autocomplete_fields = ("user", "affiliation")
    ordering = ("user__knox_id",)

    @admin.display(ordering="user__knox_id", description="사용자 knox_id")
    def user_knox_id(self, obj):
        return getattr(obj.user, "knox_id", None) or ""

    @admin.display(ordering="affiliation__department", description="department")
    def department(self, obj):
        return getattr(obj.affiliation, "department", "") or ""

    @admin.display(ordering="affiliation__line", description="line")
    def line(self, obj):
        return getattr(obj.affiliation, "line", "") or ""

    @admin.display(ordering="affiliation__user_sdwt_prod", description="user_sdwt_prod")
    def user_sdwt_prod(self, obj):
        return getattr(obj.affiliation, "user_sdwt_prod", "") or ""


@admin.register(UserSdwtProdAccess)
class UserSdwtProdAccessAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    """소속 역할은 제품 API로만 변경하고 Admin에서는 읽기 전용으로 제공합니다."""

    list_display = ("user_knox_id", "affiliation_user_sdwt_prod", "role", "granted_by_knox_id", "created_at")
    list_filter = ("role", "affiliation__user_sdwt_prod")
    search_fields = (
        "user__knox_id",
        "user__email",
        "affiliation__department",
        "affiliation__line",
        "affiliation__user_sdwt_prod",
        "granted_by__knox_id",
        "granted_by__email",
    )
    autocomplete_fields = ("user", "affiliation", "granted_by")
    ordering = ("-created_at", "-id")

    @admin.display(ordering="user__knox_id", description="사용자 knox_id")
    def user_knox_id(self, obj):
        return getattr(obj.user, "knox_id", None) or ""

    @admin.display(ordering="affiliation__user_sdwt_prod", description="user_sdwt_prod")
    def affiliation_user_sdwt_prod(self, obj):
        return getattr(obj.affiliation, "user_sdwt_prod", "") or ""

    @admin.display(ordering="granted_by__knox_id", description="부여자 knox_id")
    def granted_by_knox_id(self, obj):
        granted_by = getattr(obj, "granted_by", None)
        return getattr(granted_by, "knox_id", None) or ""


def _serialize_admin_access_scope(obj):
    """Admin 감사 로그용 접근 scope snapshot을 반환합니다."""

    if obj is None:
        return {}
    return {
        "key": obj.key,
        "name": obj.name,
        "scopeType": obj.scope_type,
        "dataScopeType": obj.data_scope_type,
        "includeCurrentAffiliation": obj.include_current_affiliation,
        "isActive": obj.is_active,
        "requestable": obj.requestable,
    }


@admin.register(AccessScope)
class AccessScopeAdmin(SuperuserWriteAdminMixin, admin.ModelAdmin):
    """migration으로 생성한 접근 권한 대상의 운영 상태 관리 화면입니다."""

    list_display = (
        "key",
        "name",
        "scope_type",
        "data_scope_type",
        "include_current_affiliation",
        "is_active",
        "requestable",
        "created_at",
    )
    list_filter = (
        "scope_type",
        "data_scope_type",
        "include_current_affiliation",
        "is_active",
        "requestable",
    )
    search_fields = ("key", "name")
    ordering = ("key",)

    def has_add_permission(self, request):
        """scope 정의는 코드와 migration에서만 추가합니다."""

        return False

    def get_readonly_fields(self, request, obj=None):
        """모든 scope의 식별 키와 유형을 생성 이후 고정합니다."""

        return (
            "key",
            "scope_type",
            "data_scope_type",
            "include_current_affiliation",
        )

    def has_delete_permission(self, request, obj=None):
        """scope 이력과 사용자 권한 보존을 위해 물리 삭제를 거부합니다."""

        return False

    def save_model(self, request, obj, form, change):
        """scope 변경을 저장하고 같은 트랜잭션에서 감사 로그를 생성합니다."""

        with transaction.atomic():
            before_obj = AccessScope.objects.filter(pk=obj.pk).first() if change else None
            if before_obj is not None:
                if obj.key != before_obj.key:
                    raise ValidationError({"key": "scope key는 생성 후 변경할 수 없습니다."})
                if obj.scope_type != before_obj.scope_type:
                    raise ValidationError({"scope_type": "scope 유형은 생성 후 변경할 수 없습니다."})

            before = _serialize_admin_access_scope(before_obj)
            super().save_model(request, obj, form, change)
            after = _serialize_admin_access_scope(obj)
            if before == after:
                return
            services.create_access_audit_log(
                scope=obj,
                actor=request.user if getattr(request.user, "is_authenticated", False) else None,
                target_user=None,
                policy_rule=None,
                action=AccessAuditLog.Actions.SCOPE_UPDATE,
                before=before,
                after=after,
                reason=None,
            )

    def delete_model(self, request, obj):
        """개별 scope 물리 삭제를 항상 거부합니다."""

        raise PermissionDenied("scope는 삭제하지 않고 비활성화해야 합니다.")

    def delete_queryset(self, request, queryset):
        """일괄 작업에서도 scope 물리 삭제를 항상 거부합니다."""

        raise PermissionDenied("scope는 삭제하지 않고 비활성화해야 합니다.")


@admin.register(AccessPolicyRule)
class AccessPolicyRuleAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    """Portal 권한 관리 API에서 변경하는 scope 정책의 조회 화면입니다."""

    list_display = ("scope_key", "rule_type", "value", "is_active", "created_at")
    list_filter = ("scope__key", "rule_type", "is_active")
    search_fields = ("scope__key", "scope__name", "value")
    autocomplete_fields = ("scope",)
    ordering = ("scope__key", "rule_type", "value")

    @admin.display(ordering="scope__key", description="scope")
    def scope_key(self, obj):
        return getattr(obj.scope, "key", "") or ""


@admin.register(UserAccess)
class UserAccessAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    """Portal 권한 관리 API에서 변경하는 사용자 접근 상태의 조회 화면입니다."""

    list_display = (
        "scope_key",
        "user_knox_id",
        "department",
        "status",
        "role",
        "data_scope_mode",
        "requested_at",
        "decided_by_knox_id",
        "decided_at",
    )
    list_filter = ("scope__key", "status", "role", "data_scope_mode", "department")
    search_fields = (
        "scope__key",
        "scope__name",
        "user__knox_id",
        "user__email",
        "user__username",
        "department",
        "decided_by__knox_id",
    )
    autocomplete_fields = ("scope", "user", "decided_by")
    readonly_fields = ("requested_at", "updated_at")
    ordering = ("-requested_at", "-id")

    @admin.display(ordering="scope__key", description="scope")
    def scope_key(self, obj):
        return getattr(obj.scope, "key", "") or ""

    @admin.display(ordering="user__knox_id", description="사용자 knox_id")
    def user_knox_id(self, obj):
        return getattr(obj.user, "knox_id", None) or ""

    @admin.display(ordering="decided_by__knox_id", description="결정자 knox_id")
    def decided_by_knox_id(self, obj):
        decided_by = getattr(obj, "decided_by", None)
        return getattr(decided_by, "knox_id", None) or ""


@admin.register(UserScopeAffiliationGrant)
class UserScopeAffiliationGrantAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    """Portal 권한 관리 API에서 변경하는 앱별 소속 grant 조회 화면입니다."""

    list_display = (
        "scope",
        "user",
        "affiliation",
        "source",
        "is_active",
        "expires_at",
        "granted_by",
        "updated_at",
    )
    list_filter = ("scope__key", "source", "is_active")
    search_fields = (
        "scope__key",
        "user__knox_id",
        "affiliation__user_sdwt_prod",
        "granted_by__knox_id",
        "reason",
    )
    autocomplete_fields = ("scope", "user", "affiliation", "granted_by")
    ordering = ("scope__key", "user__knox_id", "affiliation__user_sdwt_prod")


@admin.register(AccessAuditLog)
class AccessAuditLogAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    """scope 접근 권한 감사 로그 조회 화면 설정입니다."""

    list_display = (
        "created_at",
        "scope_key",
        "action",
        "affiliation",
        "target_user_knox_id",
        "actor_knox_id",
        "policy_rule_label",
    )
    list_filter = ("scope__key", "affiliation__user_sdwt_prod", "action", "created_at")
    search_fields = (
        "scope__key",
        "actor__knox_id",
        "target_user__knox_id",
        "affiliation__user_sdwt_prod",
        "policy_rule__value",
        "reason",
    )
    readonly_fields = (
        "id",
        "scope",
        "actor",
        "target_user",
        "affiliation",
        "policy_rule",
        "action",
        "before",
        "after",
        "reason",
        "created_at",
    )
    ordering = ("-created_at", "-id")

    @admin.display(ordering="scope__key", description="scope")
    def scope_key(self, obj):
        return getattr(obj.scope, "key", "") or ""

    @admin.display(ordering="target_user__knox_id", description="대상 knox_id")
    def target_user_knox_id(self, obj):
        return getattr(obj.target_user, "knox_id", None) or ""

    @admin.display(ordering="actor__knox_id", description="작업자 knox_id")
    def actor_knox_id(self, obj):
        return getattr(obj.actor, "knox_id", None) or ""

    @admin.display(ordering="policy_rule__value", description="정책")
    def policy_rule_label(self, obj):
        policy_rule = getattr(obj, "policy_rule", None)
        if policy_rule is None:
            return ""
        return f"{policy_rule.rule_type}:{policy_rule.value}"


@admin.register(UserSdwtProdChange)
class UserSdwtProdChangeAdmin(admin.ModelAdmin):
    """소속 변경 요청은 읽기 전용으로 표시하고 승인 action만 허용합니다."""

    actions = ("approve_affiliation_changes",)
    list_display = (
        "user_knox_id",
        "from_user_sdwt_prod",
        "to_user_sdwt_prod",
        "effective_from",
        "status",
        "approved",
        "applied",
        "approved_by_knox_id",
        "approved_at",
    )
    list_filter = ("status", "approved", "applied", "to_user_sdwt_prod")
    search_fields = (
        "user__knox_id",
        "from_user_sdwt_prod",
        "to_user_sdwt_prod",
    )
    autocomplete_fields = ("user", "approved_by", "created_by")

    def has_add_permission(self, request):
        """Admin에서 소속 변경 요청 생성을 허용하지 않습니다."""

        return False

    def has_change_permission(self, request, obj=None):
        """목록 action 권한은 유지하되 개별 레코드 직접 변경은 금지합니다."""

        if obj is not None:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        """감사 대상인 소속 변경 요청 삭제를 허용하지 않습니다."""

        return False

    def get_readonly_fields(self, request, obj=None):
        """소속 변경 요청의 모든 필드를 읽기 전용으로 제공합니다."""

        return tuple(field.name for field in self.model._meta.fields)

    def save_model(self, request, obj, form, change):
        """직접 저장 대신 승인·반려 서비스를 사용하도록 강제합니다."""

        raise PermissionDenied("소속 변경 요청은 서비스 action으로만 처리할 수 있습니다.")

    def delete_model(self, request, obj):
        """소속 변경 요청의 물리 삭제를 명시적으로 거부합니다."""

        raise PermissionDenied("소속 변경 요청은 삭제할 수 없습니다.")

    @admin.display(ordering="user__knox_id", description="사용자 knox_id")
    def user_knox_id(self, obj):
        return getattr(obj.user, "knox_id", None) or ""

    @admin.display(ordering="approved_by__knox_id", description="승인자 knox_id")
    def approved_by_knox_id(self, obj):
        approved_by = getattr(obj, "approved_by", None)
        return getattr(approved_by, "knox_id", None) or ""

    @admin.action(description="선택한 소속 변경 요청 승인")
    def approve_affiliation_changes(self, request, queryset):  # 타입 검사 생략: type: ignore[override]
        """선택된 소속 변경 요청을 승인 처리합니다.

        입력:
        - 요청: Django HttpRequest
        - queryset: 선택된 변경 요청 QuerySet

        반환:
        - 없음

        부작용:
        - 서비스 승인 로직 호출
        - 관리자 메시지 출력

        오류:
        - 없음(실패 건은 메시지로 집계)
        """
        # -----------------------------------------------------------------------------
        # 1) 사용자 인증 확인
        # -----------------------------------------------------------------------------
        if not request.user or not request.user.is_authenticated:
            self.message_user(request, "승인 권한이 없습니다.", level=messages.ERROR)
            return None

        # -----------------------------------------------------------------------------
        # 2) 승인 처리 수행
        # -----------------------------------------------------------------------------
        approved_count = 0
        failed_count = 0
        failures: list[str] = []

        for change in queryset.iterator():
            payload, status_code = services.approve_affiliation_change(
                approver=request.user,
                change_id=change.id,
            )
            if status_code == 200:
                approved_count += 1
                continue

            failed_count += 1
            error_message = payload.get("error") if isinstance(payload, dict) else None
            failures.append(f"{change.id}: {error_message or 'unknown error'}")

        # -----------------------------------------------------------------------------
        # 3) 결과 메시지 출력
        # -----------------------------------------------------------------------------
        if failed_count:
            details = " | ".join(failures[:5])
            if len(failures) > 5:
                details = f"{details} | (+{len(failures) - 5} more)"
            self.message_user(
                request,
                f"승인 완료: {approved_count}건, 실패: {failed_count}건. 실패: {details}",
                level=messages.WARNING,
            )
            return None

        self.message_user(
            request,
            f"승인 완료: {approved_count}건.",
            level=messages.SUCCESS,
        )
        return None


@admin.register(ExternalAffiliationSnapshot)
class ExternalAffiliationSnapshotAdmin(admin.ModelAdmin):
    """ExternalAffiliationSnapshot 관리 화면 설정입니다."""

    list_display = (
        "knox_id",
        "username",
        "predicted_user_sdwt_prod",
        "source_updated_at",
        "last_seen_at",
    )
    search_fields = ("knox_id", "username", "predicted_user_sdwt_prod")
    ordering = ("-last_seen_at", "-id")
