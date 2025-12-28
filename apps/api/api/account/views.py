from __future__ import annotations

from datetime import timezone as dt_timezone
from typing import Optional
from zoneinfo import ZoneInfo

from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from api.common.utils import normalize_text, parse_json_body

from . import selectors, services
from .serializers import (
    AffiliationApprovalSerializer,
    AffiliationReconfirmResponseSerializer,
    ExternalAffiliationSyncSerializer,
)

KST = ZoneInfo("Asia/Seoul")
TIMEZONE_NAME = "Asia/Seoul"
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def _parse_effective_from(value: Optional[str]):
    """입력 문자열을 파싱해 UTC timezone-aware datetime으로 변환합니다.

    Parse the input datetime string and return a UTC-aware datetime.
    """
    if not value:
        return None
    parsed = parse_datetime(str(value))
    if not parsed:
        return None
    if timezone.is_naive(parsed):
        parsed = parsed.replace(tzinfo=KST)
    return parsed.astimezone(dt_timezone.utc)


def _get_authenticated_user(request: HttpRequest):
    django_request = getattr(request, "_request", None)
    if django_request is not None:
        user = getattr(django_request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            return user
    user = getattr(request, "user", None)
    if user and getattr(user, "is_authenticated", False):
        return user
    return None


def _parse_int(value: object, default: int) -> int:
    """입력 값을 정수로 파싱하고 실패/0 이하일 때 기본값을 반환합니다."""

    try:
        parsed = int(value)
        if parsed <= 0:
            return default
        return parsed
    except (TypeError, ValueError):
        return default


@method_decorator(csrf_exempt, name="dispatch")
class AccountAffiliationView(APIView):
    """현재 사용자의 user_sdwt_prod 소속 변경을 신청합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        payload = services.get_affiliation_overview(user=user, timezone_name=TIMEZONE_NAME)
        return JsonResponse(payload)

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        department = normalize_text(payload.get("department"))
        line = normalize_text(payload.get("line"))
        new_value = normalize_text(payload.get("user_sdwt_prod"))
        if not new_value:
            new_value = normalize_text(payload.get("userSdwtProd"))
        if not new_value:
            return JsonResponse({"error": "user_sdwt_prod is required"}, status=400)

        option = selectors.get_affiliation_option(department, line, new_value)
        if option is None:
            return JsonResponse({"error": "Invalid department/line/user_sdwt_prod combination"}, status=400)

        effective_from_raw = payload.get("effective_from") or payload.get("effectiveFrom")
        effective_from = _parse_effective_from(effective_from_raw)
        if effective_from_raw and effective_from is None:
            return JsonResponse({"error": "Invalid effective_from"}, status=400)

        response_payload, status_code = services.request_affiliation_change(
            user=user,
            option=option,
            to_user_sdwt_prod=new_value,
            effective_from=effective_from,
            timezone_name=TIMEZONE_NAME,
        )
        return JsonResponse(response_payload, status=status_code)


@method_decorator(csrf_exempt, name="dispatch")
class AccountOverviewView(APIView):
    """계정 화면에서 필요한 데이터를 한번에 제공합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        payload = services.get_account_overview(user=user, timezone_name=TIMEZONE_NAME)
        return JsonResponse(payload)


@method_decorator(csrf_exempt, name="dispatch")
class AccountAffiliationApprovalView(APIView):
    """해당 소속 관리자(그룹 매니저)/슈퍼유저가 소속 변경 요청을 승인한다."""

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        if "changeId" not in payload and "id" in payload:
            payload = {**payload, "changeId": payload.get("id")}

        serializer = AffiliationApprovalSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse(serializer.errors, status=400)

        change_id = serializer.validated_data["changeId"]
        decision = (serializer.validated_data.get("decision") or "approve").lower()

        if decision == "reject":
            response_payload, status_code = services.reject_affiliation_change(
                approver=user,
                change_id=change_id,
            )
        else:
            response_payload, status_code = services.approve_affiliation_change(
                approver=user,
                change_id=change_id,
            )
        return JsonResponse(response_payload, status=status_code)


@method_decorator(csrf_exempt, name="dispatch")
class AccountAffiliationRequestListView(APIView):
    """소속 변경 요청 목록을 조회합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        status = (request.GET.get("status") or "pending").strip()
        search = (request.GET.get("q") or request.GET.get("search") or "").strip()
        user_sdwt_prod = (
            request.GET.get("user_sdwt_prod")
            or request.GET.get("userSdwtProd")
            or ""
        ).strip()
        page = _parse_int(request.GET.get("page"), 1)
        page_size = min(
            _parse_int(request.GET.get("page_size") or request.GET.get("pageSize"), DEFAULT_PAGE_SIZE),
            MAX_PAGE_SIZE,
        )

        payload, status_code = services.get_affiliation_change_requests(
            user=user,
            status=status if status and status.lower() != "all" else None,
            search=search or None,
            user_sdwt_prod=user_sdwt_prod or None,
            page=page,
            page_size=page_size,
        )
        return JsonResponse(payload, status=status_code)


@method_decorator(csrf_exempt, name="dispatch")
class AccountAffiliationReconfirmView(APIView):
    """외부 예측 소속 변경 시 사용자 재확인 여부를 조회/응답합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        payload = services.get_affiliation_reconfirm_status(user=user)
        return JsonResponse(payload)

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        serializer = AffiliationReconfirmResponseSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse(serializer.errors, status=400)

        validated = serializer.validated_data
        response_payload, status_code = services.submit_affiliation_reconfirm_response(
            user=user,
            accepted=validated["accepted"],
            department=validated.get("department"),
            line=validated.get("line"),
            user_sdwt_prod=validated.get("user_sdwt_prod"),
            timezone_name=TIMEZONE_NAME,
        )
        return JsonResponse(response_payload, status=status_code)


@method_decorator(csrf_exempt, name="dispatch")
class AccountExternalAffiliationSyncView(APIView):
    """외부 DB 예측 소속 스냅샷을 동기화합니다 (superuser 전용)."""

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)
        if not user.is_superuser:
            return JsonResponse({"error": "forbidden"}, status=403)

        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        serializer = ExternalAffiliationSyncSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse(serializer.errors, status=400)

        records = serializer.validated_data.get("records") or []
        result = services.sync_external_affiliations(records=records)
        return JsonResponse(result)


@method_decorator(csrf_exempt, name="dispatch")
class AccountAffiliationJiraKeyView(APIView):
    """Affiliation Jira project key를 조회/갱신합니다."""

    MAX_KEY_LENGTH = 64

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        line_id = (request.GET.get("lineId") or "").strip()
        if not line_id:
            return JsonResponse({"error": "lineId is required"}, status=400)

        if not selectors.affiliation_exists_for_line(line_id=line_id):
            return JsonResponse({"error": "lineId not found"}, status=404)

        jira_key = selectors.get_affiliation_jira_key_for_line(line_id=line_id)
        return JsonResponse({"lineId": line_id, "jiraKey": jira_key})

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        user = _get_authenticated_user(request)
        if not user:
            return JsonResponse({"error": "unauthorized"}, status=401)
        if not user.is_superuser:
            return JsonResponse({"error": "forbidden"}, status=403)

        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        line_id = (payload.get("lineId") or payload.get("line_id") or "").strip()
        if not line_id:
            return JsonResponse({"error": "lineId is required"}, status=400)

        jira_key_value = payload.get("jiraKey") if "jiraKey" in payload else payload.get("jira_key")
        jira_key = jira_key_value.strip() if isinstance(jira_key_value, str) else ""
        if jira_key and len(jira_key) > self.MAX_KEY_LENGTH:
            return JsonResponse(
                {"error": f"jiraKey must be {self.MAX_KEY_LENGTH} characters or fewer"},
                status=400,
            )

        updated = services.update_affiliation_jira_key(
            line_id=line_id,
            jira_key=jira_key or None,
        )
        if updated == 0:
            return JsonResponse({"error": "lineId not found"}, status=404)

        return JsonResponse({"lineId": line_id, "jiraKey": jira_key or None, "updated": updated})


@method_decorator(csrf_exempt, name="dispatch")
class AccountGrantView(APIView):
    """user_sdwt_prod 그룹 접근 권한 부여/회수."""

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        target_group = (payload.get("user_sdwt_prod") or payload.get("userSdwtProd") or "").strip()
        if not target_group:
            return JsonResponse({"error": "user_sdwt_prod is required"}, status=400)

        target_user = services.resolve_target_user(
            target_id=payload.get("userId") or payload.get("user_id"),
            target_knox_id=payload.get("knox_id"),
        )
        if not target_user:
            return JsonResponse({"error": "Target user not found"}, status=404)

        action = (payload.get("action") or "grant").lower()
        can_manage = bool(payload.get("canManage") or payload.get("can_manage"))

        response_payload, status_code = services.grant_or_revoke_access(
            grantor=user,
            target_group=target_group,
            target_user=target_user,
            action=action,
            can_manage=can_manage,
        )
        return JsonResponse(response_payload, status=status_code)


@method_decorator(csrf_exempt, name="dispatch")
class AccountGrantListView(APIView):
    """요청 사용자가 관리할 수 있는 user_sdwt_prod 그룹 멤버 목록 조회."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        payload = services.get_manageable_groups_with_members(user=user)
        return JsonResponse(payload)


@method_decorator(csrf_exempt, name="dispatch")
class LineSdwtOptionsView(APIView):
    """사용자가 선택할 수 있는 line/user_sdwt_prod 조합을 DB 값으로 한정해 제공."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        pairs = selectors.list_line_sdwt_pairs()
        payload = services.get_line_sdwt_options_payload(pairs=pairs)
        return JsonResponse(payload)
