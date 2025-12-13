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

from api.common.utils import parse_json_body

from . import selectors, services

KST = ZoneInfo("Asia/Seoul")
TIMEZONE_NAME = "Asia/Seoul"


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


@method_decorator(csrf_exempt, name="dispatch")
class AccountAffiliationView(APIView):
    """현재 사용자의 user_sdwt_prod 소속 관리 (실제 변경 시점 입력)."""

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

        services.ensure_self_access(user, as_manager=False)

        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        department = (payload.get("department") or "").strip()
        line = (payload.get("line") or "").strip()
        new_value = (payload.get("user_sdwt_prod") or payload.get("userSdwtProd") or "").strip()
        if not new_value:
            return JsonResponse({"error": "user_sdwt_prod is required"}, status=400)

        option = selectors.get_affiliation_option(department, line, new_value)
        if option is None:
            return JsonResponse({"error": "Invalid department/line/user_sdwt_prod combination"}, status=400)

        effective_from_raw = payload.get("effective_from") or payload.get("effectiveFrom")
        effective_from = _parse_effective_from(effective_from_raw)
        if effective_from_raw and effective_from is None:
            return JsonResponse({"error": "Invalid effective_from"}, status=400)
        if not effective_from:
            effective_from = timezone.now()

        response_payload, status_code = services.request_affiliation_change(
            user=user,
            option=option,
            to_user_sdwt_prod=new_value,
            effective_from=effective_from,
            timezone_name=TIMEZONE_NAME,
        )
        return JsonResponse(response_payload, status=status_code)


@method_decorator(csrf_exempt, name="dispatch")
class AccountAffiliationApprovalView(APIView):
    """슈퍼유저/스태프가 소속 변경 요청을 승인한다."""

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)
        if not (user.is_superuser or user.is_staff):
            return JsonResponse({"error": "forbidden"}, status=403)

        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        change_raw = payload.get("changeId") or payload.get("id")
        try:
            change_id = int(change_raw)
        except (TypeError, ValueError):
            return JsonResponse({"error": "Invalid changeId"}, status=400)

        response_payload, status_code = services.approve_affiliation_change(
            approver=user,
            change_id=change_id,
        )
        return JsonResponse(response_payload, status=status_code)


@method_decorator(csrf_exempt, name="dispatch")
class AccountGrantView(APIView):
    """user_sdwt_prod 그룹 접근 권한 부여/회수."""

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        services.ensure_self_access(user, as_manager=False)
        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        target_group = (payload.get("user_sdwt_prod") or payload.get("userSdwtProd") or "").strip()
        if not target_group:
            return JsonResponse({"error": "user_sdwt_prod is required"}, status=400)

        target_user = services.resolve_target_user(
            target_id=payload.get("userId") or payload.get("user_id"),
            target_username=payload.get("username"),
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
