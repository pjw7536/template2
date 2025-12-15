from __future__ import annotations

from django import forms
from django.contrib import admin
from django.contrib import messages
from django.contrib.admin.widgets import AdminSplitDateTime
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import BaseUserCreationForm, SetUnusablePasswordMixin, UserChangeForm, UsernameField
from django.utils import timezone

from api.account.selectors import get_current_user_sdwt_prod_change
from api.account.models import (
    Affiliation,
    User,
    UserProfile,
    UserSdwtProdAccess,
    UserSdwtProdChange,
)
from api.common.affiliations import UNASSIGNED_USER_SDWT_PROD
from api.emails.services import claim_unassigned_emails_for_user


class AccountUserCreationForm(SetUnusablePasswordMixin, BaseUserCreationForm):
    usable_password = SetUnusablePasswordMixin.create_usable_password_field()

    class Meta(BaseUserCreationForm.Meta):
        model = User
        fields = ("sabun",)
        field_classes = {"sabun": UsernameField}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].required = False
        self.fields["password2"].required = False


class AccountUserChangeForm(UserChangeForm):
    user_sdwt_prod_effective_from = forms.SplitDateTimeField(
        required=False,
        label="user_sdwt_prod 변경 시각",
        help_text="현재 user_sdwt_prod가 적용되는 기준 시각(effective_from)입니다. "
        "이 값을 변경하면 Emails에서 소속 변경 이후 메일 이동 시 이 시각이 사용됩니다.",
        widget=AdminSplitDateTime(),
    )

    class Meta(UserChangeForm.Meta):
        model = User
        fields = "__all__"
        field_classes = {"sabun": UsernameField}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not getattr(self.instance, "pk", None):
            return

        change = get_current_user_sdwt_prod_change(user=self.instance)
        if change is None:
            return

        self.fields["user_sdwt_prod_effective_from"].initial = change.effective_from


@admin.register(User)
class AccountUserAdmin(DjangoUserAdmin):
    form = AccountUserChangeForm
    add_form = AccountUserCreationForm
    actions = ("claim_unassigned_emails",)
    ordering = ("sabun",)
    list_display = (
        "sabun",
        "knox_id",
        "mail",
        "deptname",
        "line",
        "user_sdwt_prod",
        "is_staff",
        "is_superuser",
        "is_active",
    )
    list_filter = ("is_staff", "is_superuser", "is_active", "line")
    search_fields = ("sabun", "knox_id", "mail", "firstname", "lastname", "deptname", "line", "user_sdwt_prod")

    fieldsets = (
        (None, {"fields": ("sabun", "password")}),
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
        ("Identity", {"fields": ("knox_id", "mail")}),
        ("Names", {"fields": ("firstname", "lastname", "username_en", "givenname", "surname")}),
        (
            "Organization",
            {
                "fields": (
                    "deptname",
                    "deptid",
                    "department",
                    "line",
                    "user_sdwt_prod",
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
                    "sabun",
                    "usable_password",
                    "password1",
                    "password2",
                    "is_staff",
                    "is_superuser",
                ),
            },
        ),
    )

    @admin.action(description="UNASSIGNED(미분류) 메일을 사용자 현재 메일함으로 가져오기 (RAG 베스트에포트)")
    def claim_unassigned_emails(self, request, queryset):  # type: ignore[override]
        total_moved = 0
        total_rag_registered = 0
        total_rag_failed = 0
        failures: list[str] = []

        for user in queryset.iterator():
            try:
                result = claim_unassigned_emails_for_user(user=user)
            except Exception as exc:
                failures.append(f"{getattr(user, 'sabun', user)}: {exc}")
                continue

            total_moved += result.get("moved", 0)
            total_rag_registered += result.get("ragRegistered", 0)
            total_rag_failed += result.get("ragFailed", 0)

        if failures:
            details = " | ".join(failures[:5])
            if len(failures) > 5:
                details = f"{details} | (+{len(failures) - 5} more)"
            self.message_user(
                request,
                f"가져온 메일: {total_moved}개. RAG 등록 성공={total_rag_registered}, 실패={total_rag_failed}. "
                f"실패: {details}",
                level=messages.WARNING,
            )
            return None

        self.message_user(
            request,
            f"가져온 메일: {total_moved}개. RAG 등록 성공={total_rag_registered}, 실패={total_rag_failed}.",
            level=messages.SUCCESS,
        )
        return None

    def save_model(self, request, obj, form, change):  # type: ignore[override]
        super().save_model(request, obj, form, change)

        effective_from = form.cleaned_data.get("user_sdwt_prod_effective_from")
        if effective_from is None:
            return

        if timezone.is_naive(effective_from):
            effective_from = timezone.make_aware(effective_from, timezone.get_current_timezone())

        current_user_sdwt_prod = (getattr(obj, "user_sdwt_prod", None) or "").strip()
        if not current_user_sdwt_prod or current_user_sdwt_prod == UNASSIGNED_USER_SDWT_PROD:
            return

        change_row = get_current_user_sdwt_prod_change(user=obj)
        if change_row is None:
            self.message_user(
                request,
                "현재 user_sdwt_prod에 대한 UserSdwtProdChange 기록이 없어 변경 시각을 저장할 수 없습니다. "
                "먼저 소속 변경을 적용(승인)하거나 UserSdwtProdChange에서 레코드를 생성해주세요.",
                level=messages.WARNING,
            )
            return

        if change_row.effective_from != effective_from:
            change_row.effective_from = effective_from
            change_row.save(update_fields=["effective_from"])
            self.message_user(
                request,
                f"user_sdwt_prod 변경 시각을 {effective_from.isoformat()}로 업데이트했습니다.",
                level=messages.SUCCESS,
            )


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role")
    list_filter = ("role",)
    search_fields = ("user__sabun", "user__knox_id", "user__mail")
    autocomplete_fields = ("user",)


@admin.register(Affiliation)
class AffiliationAdmin(admin.ModelAdmin):
    list_display = ("department", "line", "user_sdwt_prod")
    search_fields = ("department", "line", "user_sdwt_prod")
    list_filter = ("line",)
    ordering = ("department", "line", "user_sdwt_prod")


@admin.register(UserSdwtProdAccess)
class UserSdwtProdAccessAdmin(admin.ModelAdmin):
    list_display = ("user", "user_sdwt_prod", "can_manage", "granted_by", "created_at")
    list_filter = ("can_manage", "user_sdwt_prod")
    search_fields = (
        "user__sabun",
        "user__knox_id",
        "user__mail",
        "user_sdwt_prod",
        "granted_by__sabun",
        "granted_by__knox_id",
    )
    autocomplete_fields = ("user", "granted_by")
    ordering = ("-created_at", "-id")


@admin.register(UserSdwtProdChange)
class UserSdwtProdChangeAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "from_user_sdwt_prod",
        "to_user_sdwt_prod",
        "effective_from",
        "approved",
        "applied",
        "approved_by",
        "approved_at",
    )
    list_filter = ("approved", "applied", "to_user_sdwt_prod")
    search_fields = (
        "user__sabun",
        "user__knox_id",
        "from_user_sdwt_prod",
        "to_user_sdwt_prod",
    )
    autocomplete_fields = ("user", "approved_by", "created_by")
    date_hierarchy = "effective_from"
    ordering = ("-effective_from", "-id")
