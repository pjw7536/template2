# =============================================================================
# 모듈 설명: Email 모델 관리자 화면과 관리자 액션을 정의합니다.
# - 주요 클래스: EmailActionForm, EmailAdmin
# - 불변 조건: 메일 이동/재색인은 서비스 계층을 통해 처리합니다.
# =============================================================================

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
    """관리자 액션에서 user_sdwt_prod 입력을 제공하는 폼입니다."""

    to_user_sdwt_prod = forms.CharField(
        required=False,
        label="이동 대상 user_sdwt_prod",
        help_text="선택한 메일을 지정한 메일함(user_sdwt_prod)으로 이동합니다.",
    )


@admin.register(Email)
class EmailAdmin(admin.ModelAdmin):
    """Email 모델의 관리자 목록/검색/액션 구성을 정의합니다."""

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
    # 타입 검사 무시 지시어(mypy)
    def move_selected_emails_to_mailbox(self, request, queryset):  # type: ignore[override]  오버라이드 타입 검사 생략
        """선택한 메일을 지정한 메일함으로 이동하고 RAG 재색인을 요청합니다.

        입력:
            request: 관리자 요청 객체.
            queryset: 선택된 Email queryset.
        반환:
            None (관리자 액션 응답은 message_user로 전달).
        부작용:
            - Email.user_sdwt_prod 업데이트.
            - RAG 인덱싱 Outbox 적재.
        오류:
            - user_sdwt_prod 미입력 시 오류 메시지 반환.
            - 서비스 오류 시 오류 메시지 반환.
        """

        # -----------------------------------------------------------------------------
        # 1) 입력 검증
        # -----------------------------------------------------------------------------
        target = (request.POST.get("to_user_sdwt_prod") or "").strip()
        if not target:
            self.message_user(request, "이동 대상 user_sdwt_prod를 입력해주세요.", level=messages.ERROR)
            return None

        # -----------------------------------------------------------------------------
        # 2) 서비스 호출 및 결과 메시지 출력
        # -----------------------------------------------------------------------------
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
    # 타입 검사 무시 지시어(mypy)
    def move_emails_after_sender_affiliation_change(self, request, queryset):  # type: ignore[override]  오버라이드 타입 검사 생략
        """발신자 소속 변경 시각 이후 메일을 현재 소속 메일함으로 이동합니다.

        입력:
            request: 관리자 요청 객체.
            queryset: 선택된 Email queryset (sender_id를 추출).
        반환:
            None (관리자 액션 응답은 message_user로 전달).
        부작용:
            - Email.user_sdwt_prod 업데이트.
            - RAG 인덱싱 Outbox 적재.
        오류:
            - sender_id 누락/사용자 없음/소속 이력 없음 등은 경고로 기록.
            - 서비스 오류는 개별 실패 목록에 기록.
        """

        # -----------------------------------------------------------------------------
        # 1) sender_id 목록 수집 및 검증
        # -----------------------------------------------------------------------------
        sender_ids = sorted(
            {str(value).strip() for value in queryset.values_list("sender_id", flat=True) if str(value).strip()}
        )
        if not sender_ids:
            self.message_user(request, "선택된 메일에 sender_id가 없습니다.", level=messages.ERROR)
            return None

        # -----------------------------------------------------------------------------
        # 2) 결과 집계 준비
        # -----------------------------------------------------------------------------
        total_moved = 0
        total_rag_registered = 0
        total_rag_failed = 0
        total_rag_missing = 0
        failures: list[str] = []

        # -----------------------------------------------------------------------------
        # 3) 발신자별 이동 처리
        # -----------------------------------------------------------------------------
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

        # -----------------------------------------------------------------------------
        # 4) 결과 메시지 구성 및 반환
        # -----------------------------------------------------------------------------
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
