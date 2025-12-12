from __future__ import annotations

import gzip
import logging
from datetime import datetime, time
from typing import Any, Dict, List, Optional, Set

from django.conf import settings
from django.core.paginator import EmptyPage, Paginator
from django.db.models import Q
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.exceptions import NotFound
from rest_framework.views import APIView

from api.common.utils import parse_json_body

from .services import bulk_delete_emails, delete_single_email
from .pop3_ingest import run_pop3_ingest_from_env
from ..models import Email, UserSdwtProdAccess

logger = logging.getLogger(__name__)

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def _parse_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
        if parsed <= 0:
            return default
        return parsed
    except (TypeError, ValueError):
        return default


def _resolve_accessible_user_sdwt_prods(user) -> Set[str]:
    if not user or not user.is_authenticated:
        return set()

    values = set(
        UserSdwtProdAccess.objects.filter(user=user).values_list("user_sdwt_prod", flat=True)
    )
    if user.user_sdwt_prod:
        values.add(user.user_sdwt_prod)

    return {val for val in values if isinstance(val, str) and val.strip()}


def _user_can_access_email(user, email: Email, accessible: Optional[Set[str]]) -> bool:
    if user.is_superuser or user.is_staff:
        return True
    if accessible is None:
        return False
    return bool(email.user_sdwt_prod and email.user_sdwt_prod in accessible)


def _parse_datetime(value: str):
    if not value:
        return None
    dt = parse_datetime(value)
    if dt:
        return dt
    date_only = parse_date(value)
    if date_only:
        return datetime.combine(date_only, time.min, tzinfo=timezone.utc)
    return None


def _serialize_email(email: Email) -> Dict[str, Any]:
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
        "userSdwtProd": email.user_sdwt_prod,
        "snippet": snippet,
        "ragDocId": email.rag_doc_id,
    }


def _serialize_detail(email: Email) -> Dict[str, Any]:
    return {
        **_serialize_email(email),
        "bodyText": email.body_text,
        "createdAt": email.created_at.isoformat(),
        "updatedAt": email.updated_at.isoformat(),
    }


def _resolve_access_control(request: HttpRequest) -> tuple:
    """
    공통 권한 처리: 인증 여부, 접근 가능한 user_sdwt_prod 목록 반환.
    superuser/staff는 무제한 접근을 허용한다.
    """

    user = request.user
    if not user or not user.is_authenticated:
        return False, False, set()

    if user.is_superuser or user.is_staff:
        return True, True, set()

    accessible = _resolve_accessible_user_sdwt_prods(user)
    return True, bool(accessible), accessible


def _extract_bearer_token(request: HttpRequest) -> str:
    """Authorization 헤더에서 Bearer 토큰을 추출."""

    auth_header = request.headers.get("Authorization") or request.META.get("HTTP_AUTHORIZATION") or ""
    if not isinstance(auth_header, str):
        return ""

    normalized = auth_header.strip()
    if normalized.lower().startswith("bearer "):
        return normalized[7:].strip()
    return normalized


@method_decorator(csrf_exempt, name="dispatch")
class EmailListView(APIView):
    """메일 리스트 조회."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        is_authenticated, is_privileged, accessible = _resolve_access_control(request)
        if not is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        if not is_privileged and not accessible:
            return JsonResponse({"error": "forbidden"}, status=403)

        qs = Email.objects.order_by("-received_at", "-id")
        if not is_privileged:
            qs = qs.filter(user_sdwt_prod__in=accessible)

        search = (request.GET.get("q") or "").strip()
        sender = (request.GET.get("sender") or "").strip()
        recipient = (request.GET.get("recipient") or "").strip()
        date_from = _parse_datetime(request.GET.get("date_from"))
        date_to = _parse_datetime(request.GET.get("date_to"))

        if search:
            qs = qs.filter(
                Q(subject__icontains=search)
                | Q(body_text__icontains=search)
                | Q(sender__icontains=search)
            )
        if sender:
            qs = qs.filter(sender__icontains=sender)
        if recipient:
            qs = qs.filter(recipient__icontains=recipient)
        if date_from:
            qs = qs.filter(received_at__gte=date_from)
        if date_to:
            qs = qs.filter(received_at__lte=date_to)

        page = _parse_int(request.GET.get("page"), 1)
        page_size = min(_parse_int(request.GET.get("page_size"), DEFAULT_PAGE_SIZE), MAX_PAGE_SIZE)

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
class EmailDetailView(APIView):
    """단일 메일 상세 조회 (텍스트)."""

    def get(self, request: HttpRequest, email_id: int, *args: object, **kwargs: object) -> JsonResponse:
        is_authenticated, is_privileged, accessible = _resolve_access_control(request)
        if not is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)
        try:
            email = Email.objects.get(id=email_id)
        except Email.DoesNotExist:
            return JsonResponse({"error": "Email not found"}, status=404)

        if not is_privileged:
            if not accessible or not _user_can_access_email(request.user, email, accessible):
                return JsonResponse({"error": "forbidden"}, status=403)

        return JsonResponse(_serialize_detail(email))

    def delete(self, request: HttpRequest, email_id: int, *args: object, **kwargs: object) -> JsonResponse:
        is_authenticated, is_privileged, accessible = _resolve_access_control(request)
        if not is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)
        if not is_privileged:
            try:
                email = Email.objects.get(id=email_id)
            except Email.DoesNotExist:
                return JsonResponse({"error": "Email not found"}, status=404)
            if not accessible or not _user_can_access_email(request.user, email, accessible):
                return JsonResponse({"error": "forbidden"}, status=403)
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
        is_authenticated, is_privileged, accessible = _resolve_access_control(request)
        if not is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)
        try:
            email = Email.objects.get(id=email_id)
        except Email.DoesNotExist:
            return JsonResponse({"error": "Email not found"}, status=404)

        if not is_privileged:
            if not accessible or not _user_can_access_email(request.user, email, accessible):
                return JsonResponse({"error": "forbidden"}, status=403)

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
        is_authenticated, is_privileged, accessible = _resolve_access_control(request)
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
            owned_count = Email.objects.filter(id__in=normalized_ids, user_sdwt_prod__in=accessible).count()
            if owned_count != len(normalized_ids):
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
        expected_token = getattr(settings, "EMAIL_INGEST_TRIGGER_TOKEN", "") or ""
        provided_token = _extract_bearer_token(request)

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
