from __future__ import annotations

import gzip
import logging
import os
from datetime import datetime, time
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.core.paginator import EmptyPage, Paginator
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.exceptions import NotFound
from rest_framework.views import APIView

from api.common.utils import parse_json_body

from .permissions import (
    email_is_unassigned,
    extract_bearer_token,
    resolve_access_control,
    user_can_access_email,
    user_can_view_unassigned,
)
from .selectors import (
    contains_unassigned_emails,
    count_unassigned_emails_for_sender_id,
    get_email_by_id,
    get_filtered_emails,
    list_mailbox_members,
    list_privileged_email_mailboxes,
    user_can_bulk_delete_emails,
)
from api.common.affiliations import UNASSIGNED_USER_SDWT_PROD

from .services import (
    bulk_delete_emails,
    claim_unassigned_emails_for_user,
    delete_single_email,
    process_email_outbox_batch,
    run_pop3_ingest_from_env,
)

logger = logging.getLogger(__name__)

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def _ensure_airflow_token(request: HttpRequest) -> JsonResponse | None:
    expected = (
        getattr(settings, "AIRFLOW_TRIGGER_TOKEN", "") or os.getenv("AIRFLOW_TRIGGER_TOKEN") or ""
    ).strip()
    if not expected:
        return JsonResponse({"error": "AIRFLOW_TRIGGER_TOKEN not configured"}, status=500)

    provided = extract_bearer_token(request)
    if provided != expected:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    return None


def _parse_int(value: Any, default: int) -> int:
    """입력 값을 정수로 파싱하고 실패/0 이하일 때 기본값을 반환합니다."""

    try:
        parsed = int(value)
        if parsed <= 0:
            return default
        return parsed
    except (TypeError, ValueError):
        return default


def _parse_datetime(value: str):
    """날짜/일시 문자열을 timezone-aware datetime(UTC)으로 파싱합니다."""

    if not value:
        return None
    dt = parse_datetime(value)
    if dt:
        return dt
    date_only = parse_date(value)
    if date_only:
        return datetime.combine(date_only, time.min, tzinfo=timezone.utc)
    return None


def _build_email_filters(request: HttpRequest) -> Dict[str, Any]:
    """이메일 목록 필터 값을 일관되게 정규화합니다.

    - 쿼리 파라미터 파싱 로직을 한곳으로 모아 중복을 줄입니다.
    - view 내부 가독성을 높이고, 향후 필터 추가 시 변경 지점을 최소화합니다.
    """

    return {
        "mailbox_user_sdwt_prod": _parse_mailbox_user_sdwt_prod(request),
        "search": (request.GET.get("q") or "").strip(),
        "sender": (request.GET.get("sender") or "").strip(),
        "recipient": (request.GET.get("recipient") or "").strip(),
        "date_from": _parse_datetime(request.GET.get("date_from")),
        "date_to": _parse_datetime(request.GET.get("date_to")),
        "page": _parse_int(request.GET.get("page"), 1),
        "page_size": min(_parse_int(request.GET.get("page_size"), DEFAULT_PAGE_SIZE), MAX_PAGE_SIZE),
    }


def _check_email_access(
    *,
    request: HttpRequest,
    email: Any,
    is_privileged: bool,
    accessible: Optional[set[str]],
) -> Optional[JsonResponse]:
    """공통 이메일 접근 검증을 수행하고, 문제 시 JsonResponse를 반환합니다.

    - 세부 view에서 동일한 권한 체크를 반복하지 않도록 캡슐화했습니다.
    - 반환값이 None이면 접근 가능하다는 의미입니다.
    """

    if email is None:
        return JsonResponse({"error": "Email not found"}, status=404)

    if email_is_unassigned(email) and not user_can_view_unassigned(request.user):
        return JsonResponse({"error": "forbidden"}, status=403)

    if not is_privileged:
        if not accessible or not user_can_access_email(request.user, email, accessible):
            return JsonResponse({"error": "forbidden"}, status=403)

    return None


def _serialize_email(email: Any) -> Dict[str, Any]:
    """Email 인스턴스를 목록 응답용 dict로 직렬화합니다."""

    snippet = (email.body_text or "").strip()
    if len(snippet) > 180:
        snippet = snippet[:177] + "..."
    return {
        "id": email.id,
        "messageId": email.message_id,
        "receivedAt": email.received_at.isoformat(),
        "subject": email.subject,
        "sender": email.sender,
        "senderId": email.sender_id,
        "recipient": email.recipient,
        "cc": email.cc,
        "userSdwtProd": email.user_sdwt_prod,
        "snippet": snippet,
        "ragDocId": email.rag_doc_id,
    }


def _serialize_detail(email: Any) -> Dict[str, Any]:
    """Email 인스턴스를 상세 응답용 dict로 직렬화합니다."""

    return {
        **_serialize_email(email),
        "bodyText": email.body_text,
        "createdAt": email.created_at.isoformat(),
        "updatedAt": email.updated_at.isoformat(),
    }


def _parse_mailbox_user_sdwt_prod(request: HttpRequest) -> str:
    """요청 쿼리에서 mailbox(user_sdwt_prod) 값을 추출/정규화합니다."""

    raw = request.GET.get("user_sdwt_prod") or request.GET.get("userSdwtProd") or ""
    return raw.strip() if isinstance(raw, str) else ""


@method_decorator(csrf_exempt, name="dispatch")
class EmailListView(APIView):
    """메일 리스트 조회."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        is_authenticated, is_privileged, accessible = resolve_access_control(request)
        if not is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        if not is_privileged and not accessible:
            return JsonResponse({"error": "forbidden"}, status=403)

        filters = _build_email_filters(request)
        mailbox_user_sdwt_prod = filters["mailbox_user_sdwt_prod"]
        can_view_unassigned = user_can_view_unassigned(request.user)
        if mailbox_user_sdwt_prod == UNASSIGNED_USER_SDWT_PROD and not can_view_unassigned:
            return JsonResponse({"error": "forbidden"}, status=403)
        if mailbox_user_sdwt_prod and not is_privileged:
            if mailbox_user_sdwt_prod not in accessible:
                return JsonResponse({"error": "forbidden"}, status=403)

        qs = get_filtered_emails(
            accessible_user_sdwt_prods=accessible,
            is_privileged=is_privileged,
            can_view_unassigned=can_view_unassigned,
            mailbox_user_sdwt_prod=mailbox_user_sdwt_prod,
            search=filters["search"],
            sender=filters["sender"],
            recipient=filters["recipient"],
            date_from=filters["date_from"],
            date_to=filters["date_to"],
        )

        page = filters["page"]
        page_size = filters["page_size"]

        paginator = Paginator(qs, page_size)
        try:
            page_obj = paginator.page(page)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages or 1)

        results = [_serialize_email(email) for email in page_obj.object_list]

        return JsonResponse(
            {
                "results": results,
                "page": page_obj.number,
                "pageSize": page_size,
                "total": paginator.count,
                "totalPages": paginator.num_pages,
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class EmailMailboxListView(APIView):
    """현재 사용자가 접근 가능한 메일함(user_sdwt_prod) 목록을 반환합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        is_authenticated, is_privileged, accessible = resolve_access_control(request)
        if not is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        if is_privileged:
            results = list_privileged_email_mailboxes()
            if not user_can_view_unassigned(request.user):
                results = [
                    mailbox
                    for mailbox in results
                    if mailbox not in {UNASSIGNED_USER_SDWT_PROD, "rp-unclassified"}
                ]
            return JsonResponse({"results": results})

        if not accessible:
            return JsonResponse({"error": "forbidden"}, status=403)

        return JsonResponse({"results": sorted(accessible)})


@method_decorator(csrf_exempt, name="dispatch")
class EmailMailboxMembersView(APIView):
    """메일함(user_sdwt_prod)에 접근 가능한 멤버 목록을 반환합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        is_authenticated, is_privileged, accessible = resolve_access_control(request)
        if not is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        if not is_privileged and not accessible:
            return JsonResponse({"error": "forbidden"}, status=403)

        mailbox_user_sdwt_prod = _parse_mailbox_user_sdwt_prod(request)
        if not mailbox_user_sdwt_prod:
            return JsonResponse({"error": "user_sdwt_prod is required"}, status=400)

        can_view_unassigned = user_can_view_unassigned(request.user)
        if mailbox_user_sdwt_prod == UNASSIGNED_USER_SDWT_PROD and not can_view_unassigned:
            return JsonResponse({"error": "forbidden"}, status=403)

        if not is_privileged and mailbox_user_sdwt_prod not in accessible:
            return JsonResponse({"error": "forbidden"}, status=403)

        members = list_mailbox_members(mailbox_user_sdwt_prod=mailbox_user_sdwt_prod)
        return JsonResponse({"userSdwtProd": mailbox_user_sdwt_prod, "members": members})


@method_decorator(csrf_exempt, name="dispatch")
class EmailUnassignedSummaryView(APIView):
    """현재 사용자(sender_id=knox_id)의 UNASSIGNED 메일 개수를 반환합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        sender_id = getattr(user, "knox_id", None) or ""
        count = count_unassigned_emails_for_sender_id(sender_id=sender_id)
        return JsonResponse({"mailbox": UNASSIGNED_USER_SDWT_PROD, "count": count})


@method_decorator(csrf_exempt, name="dispatch")
class EmailUnassignedClaimView(APIView):
    """현재 사용자(sender_id=knox_id)의 UNASSIGNED 메일을 현재 user_sdwt_prod로 귀속(옮김)합니다."""

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        try:
            payload = claim_unassigned_emails_for_user(user=user)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Failed to claim UNASSIGNED emails for user_id=%s", getattr(user, "id", None))
            return JsonResponse({"error": "Failed to claim emails"}, status=500)

        return JsonResponse(payload)


@method_decorator(csrf_exempt, name="dispatch")
class EmailDetailView(APIView):
    """단일 메일 상세 조회 (텍스트)."""

    def get(self, request: HttpRequest, email_id: int, *args: object, **kwargs: object) -> JsonResponse:
        is_authenticated, is_privileged, accessible = resolve_access_control(request)
        if not is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)
        email = get_email_by_id(email_id=email_id)
        access_error = _check_email_access(
            request=request,
            email=email,
            is_privileged=is_privileged,
            accessible=accessible,
        )
        if access_error:
            return access_error

        return JsonResponse(_serialize_detail(email))

    def delete(self, request: HttpRequest, email_id: int, *args: object, **kwargs: object) -> JsonResponse:
        is_authenticated, is_privileged, accessible = resolve_access_control(request)
        if not is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)
        email = get_email_by_id(email_id=email_id)
        access_error = _check_email_access(
            request=request,
            email=email,
            is_privileged=is_privileged,
            accessible=accessible,
        )
        if access_error:
            return access_error
        try:
            delete_single_email(email_id)
            return JsonResponse({"status": "ok"})
        except NotFound as exc:
            return JsonResponse({"error": str(exc)}, status=404)
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Failed to delete email id=%s", email_id)
            return JsonResponse({"error": "Failed to delete email"}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class EmailHtmlView(APIView):
    """gzip 저장된 HTML 본문 복원."""

    def get(self, request: HttpRequest, email_id: int, *args: object, **kwargs: object) -> HttpResponse:
        is_authenticated, is_privileged, accessible = resolve_access_control(request)
        if not is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)
        email = get_email_by_id(email_id=email_id)
        access_error = _check_email_access(
            request=request,
            email=email,
            is_privileged=is_privileged,
            accessible=accessible,
        )
        if access_error:
            return access_error

        if not email.body_html_gzip:
            return HttpResponse("", status=204)

        try:
            html = gzip.decompress(email.body_html_gzip).decode("utf-8")
        except Exception:  # pragma: no cover - defensive decode
            logger.exception("Failed to decompress email HTML (id=%s)", email_id)
            return JsonResponse({"error": "Failed to decode HTML body"}, status=500)

        return HttpResponse(html, content_type="text/html; charset=utf-8")


@method_decorator(csrf_exempt, name="dispatch")
class EmailBulkDeleteView(APIView):
    """여러 메일 삭제 (모두 성공 시 반영)."""

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        is_authenticated, is_privileged, accessible = resolve_access_control(request)
        if not is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)
        if not is_privileged and not accessible:
            return JsonResponse({"error": "forbidden"}, status=403)

        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        email_ids = payload.get("email_ids") or payload.get("emailIds")
        if not isinstance(email_ids, list) or not email_ids:
            return JsonResponse({"error": "email_ids must be a non-empty list"}, status=400)

        normalized_ids: List[int] = []
        for raw in email_ids:
            try:
                normalized_ids.append(int(raw))
            except (TypeError, ValueError):
                return JsonResponse({"error": "email_ids must contain numeric values"}, status=400)

        if not is_privileged:
            if not user_can_bulk_delete_emails(
                email_ids=normalized_ids,
                accessible_user_sdwt_prods=accessible,
            ):
                return JsonResponse({"error": "forbidden"}, status=403)
        else:
            if not user_can_view_unassigned(request.user) and contains_unassigned_emails(
                email_ids=normalized_ids
            ):
                return JsonResponse({"error": "forbidden"}, status=403)

        try:
            deleted_count = bulk_delete_emails(normalized_ids)
            return JsonResponse({"deleted": deleted_count})
        except NotFound as exc:
            return JsonResponse({"error": str(exc)}, status=404)
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Failed to bulk delete emails")
            return JsonResponse({"error": "Failed to delete emails"}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class EmailIngestTriggerView(APIView):
    """POP3 메일 수집을 백엔드에서 실행하도록 트리거."""

    permission_classes: tuple = ()

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        expected_token = getattr(settings, "AIRFLOW_TRIGGER_TOKEN", "") or ""
        provided_token = extract_bearer_token(request)

        if expected_token:
            if provided_token != expected_token and not request.user.is_authenticated:
                return JsonResponse({"error": "Unauthorized"}, status=401)
        elif not request.user.is_authenticated:
            return JsonResponse({"error": "로그인이 필요합니다."}, status=401)

        try:
            result = run_pop3_ingest_from_env() or {}
            return JsonResponse({"deleted": result.get("deleted", 0), "reindexed": result.get("reindexed", 0)})
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except Exception:
            logger.exception("Failed to trigger POP3 ingest")
            return JsonResponse({"error": "POP3 ingest failed"}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class EmailOutboxProcessTriggerView(APIView):
    """Process pending email outbox items (RAG operations)."""

    permission_classes: tuple = ()

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        auth_response = _ensure_airflow_token(request)
        if auth_response is not None:
            return auth_response

        payload = parse_json_body(request) or {}
        raw_limit = payload.get("limit")
        if raw_limit is None:
            raw_limit = request.GET.get("limit")

        limit = None
        if raw_limit is not None:
            try:
                limit = int(raw_limit)
            except (TypeError, ValueError):
                return JsonResponse({"error": "limit must be an integer"}, status=400)
            if limit <= 0:
                limit = None

        try:
            if limit is None:
                result = process_email_outbox_batch()
            else:
                result = process_email_outbox_batch(limit=limit)
            return JsonResponse(result)
        except Exception:
            logger.exception("Failed to process email outbox")
            return JsonResponse({"error": "Email outbox processing failed"}, status=500)
