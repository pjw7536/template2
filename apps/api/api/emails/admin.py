from __future__ import annotations

from django import forms
from django.contrib import admin
from django.contrib import messages
from django.contrib.admin.helpers import ActionForm

from api.account.selectors import get_current_user_sdwt_prod_change, get_user_by_knox_id
from api.common.affiliations import UNASSIGNED_USER_SDWT_PROD
from api.emails.models import Email
from api.emails.services import move_emails_to_user_sdwt_prod, move_sender_emails_after


class EmailActionForm(ActionForm):
    to_user_sdwt_prod = forms.CharField(
        required=False,
        label="이동 대상 user_sdwt_prod",
        help_text="선택한 메일을 지정한 메일함(user_sdwt_prod)으로 이동합니다.",
    )


@admin.register(Email)
class EmailAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "received_at",
        "user_sdwt_prod",
        "classification_source",
        "rag_index_status",
        "sender_id",
        "sender",
        "recipient",
        "cc",
        "subject",
    )
    list_filter = ("user_sdwt_prod", "classification_source", "rag_index_status")
    search_fields = ("subject", "sender", "participants_search", "message_id", "rag_doc_id", "sender_id")
    date_hierarchy = "received_at"
    ordering = ("-received_at", "-id")

    fieldsets = (
        (None, {"fields": ("message_id", "received_at", "subject", "sender", "sender_id", "recipient", "cc")}),
        ("Mailbox", {"fields": ("user_sdwt_prod", "classification_source", "rag_index_status", "rag_doc_id")}),
        ("Content", {"classes": ("collapse",), "fields": ("body_text",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    readonly_fields = ("message_id", "received_at", "rag_doc_id", "created_at", "updated_at")

    action_form = EmailActionForm
    actions = ("move_selected_emails_to_mailbox", "move_emails_after_sender_affiliation_change")

    @admin.action(
        description="선택한 메일을 지정한 user_sdwt_prod로 이동 (RAG 재색인, 누락=요청했지만 DB에 없는 ID)"
    )
    def move_selected_emails_to_mailbox(self, request, queryset):  # type: ignore[override]
        target = (request.POST.get("to_user_sdwt_prod") or "").strip()
        if not target:
            self.message_user(request, "이동 대상 user_sdwt_prod를 입력해주세요.", level=messages.ERROR)
            return None

        email_ids = list(queryset.values_list("id", flat=True))
        try:
            result = move_emails_to_user_sdwt_prod(email_ids=email_ids, to_user_sdwt_prod=target)
        except ValueError as exc:
            self.message_user(request, str(exc), level=messages.ERROR)
            return None

        self.message_user(
            request,
            f"이동된 메일: {result['moved']}개 → {target}. "
            f"RAG 큐 적재={result['ragRegistered']}, 실패={result['ragFailed']}, "
            f"누락={result.get('ragMissing', 0)} (요청했지만 DB에 없는 ID).",
            level=messages.SUCCESS,
        )
        return None

    @admin.action(
        description=(
            "발신자 소속 변경 시각 이후 메일을 현재 user_sdwt_prod로 이동 "
            "(RAG 재색인, 누락=요청했지만 DB에 없는 ID)"
        )
    )
    def move_emails_after_sender_affiliation_change(self, request, queryset):  # type: ignore[override]
        sender_ids = sorted(
            {str(value).strip() for value in queryset.values_list("sender_id", flat=True) if str(value).strip()}
        )
        if not sender_ids:
            self.message_user(request, "선택된 메일에 sender_id가 없습니다.", level=messages.ERROR)
            return None

        total_moved = 0
        total_rag_registered = 0
        total_rag_failed = 0
        total_rag_missing = 0
        failures: list[str] = []

        for sender_id in sender_ids:
            user = get_user_by_knox_id(knox_id=sender_id)
            if user is None:
                failures.append(f"{sender_id}: 사용자 없음")
                continue

            target_user_sdwt_prod = (getattr(user, "user_sdwt_prod", None) or "").strip()
            if not target_user_sdwt_prod or target_user_sdwt_prod == UNASSIGNED_USER_SDWT_PROD:
                failures.append(f"{sender_id}: user_sdwt_prod 없음/UNASSIGNED")
                continue

            change = get_current_user_sdwt_prod_change(user=user)
            if change is None:
                failures.append(f"{sender_id}: 소속 변경 이력(UserSdwtProdChange) 없음")
                continue

            try:
                result = move_sender_emails_after(
                    sender_id=sender_id,
                    received_at_gte=change.effective_from,
                    to_user_sdwt_prod=target_user_sdwt_prod,
                )
            except Exception as exc:
                failures.append(f"{sender_id}: {exc}")
                continue

            total_moved += result.get("moved", 0)
            total_rag_registered += result.get("ragRegistered", 0)
            total_rag_failed += result.get("ragFailed", 0)
            total_rag_missing += result.get("ragMissing", 0)

        level = messages.SUCCESS if not failures else messages.WARNING
        details = ""
        if failures:
            details = " | ".join(failures[:5])
            if len(failures) > 5:
                details = f"{details} | (+{len(failures) - 5} more)"

        self.message_user(
            request,
            f"이동된 메일: {total_moved}개. RAG 큐 적재={total_rag_registered}, "
            f"실패={total_rag_failed}, 누락={total_rag_missing} (요청했지만 DB에 없는 ID)."
            + (f" 실패: {details}" if details else ""),
            level=level,
        )
        return None
