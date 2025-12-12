from __future__ import annotations

import logging
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from api.common.affiliations import get_affiliation_option
from api.common.utils import parse_json_body
from api.emails.reclassify import reclassify_emails_for_user_sdwt_change
from api.models import AffiliationHierarchy, LineSDWT, UserSdwtProdAccess, UserSdwtProdChange

User = get_user_model()
KST = ZoneInfo("Asia/Seoul")
TIMEZONE_NAME = "Asia/Seoul"
logger = logging.getLogger(__name__)


def _parse_effective_from(value: Optional[str]):
    """Parse the input datetime string and return a UTC-aware datetime."""
    if not value:
        return None
    parsed = parse_datetime(str(value))
    if not parsed:
        return None
    if timezone.is_naive(parsed):
        parsed = parsed.replace(tzinfo=KST)
    return parsed.astimezone(timezone.utc)


def _ensure_self_access(user) -> UserSdwtProdAccess | None:
    """
    Ensure the user has an access row for their own user_sdwt_prod.
    Grants manage permission by default so each group has at least one manager.
    """
    if not user.user_sdwt_prod:
        return None
    access, _ = UserSdwtProdAccess.objects.get_or_create(
        user=user,
        user_sdwt_prod=user.user_sdwt_prod,
        defaults={"can_manage": True, "granted_by": None},
    )
    if not access.can_manage:
        access.can_manage = True
        access.save(update_fields=["can_manage"])
    return access


def _apply_pending_change_if_due(user) -> None:
    """Pending-change flow removed; kept as a no-op for compatibility."""
    return


def _serialize_access(access: UserSdwtProdAccess, source: str) -> Dict[str, object]:
    return {
        "userSdwtProd": access.user_sdwt_prod,
        "canManage": access.can_manage,
        "source": source,
        "grantedBy": access.granted_by_id,
        "grantedAt": access.created_at.isoformat(),
    }


def _serialize_member(access: UserSdwtProdAccess) -> Dict[str, object]:
    user = access.user
    return {
        "userId": user.id,
        "username": user.get_username(),
        "name": (user.first_name or "") + (user.last_name or ""),
        "userSdwtProd": access.user_sdwt_prod,
        "canManage": access.can_manage,
        "grantedBy": access.granted_by_id,
        "grantedAt": access.created_at.isoformat(),
    }


def _current_access_list(user) -> List[Dict[str, object]]:
    rows = list(UserSdwtProdAccess.objects.filter(user=user).order_by("user_sdwt_prod", "id"))
    access_map = {row.user_sdwt_prod: row for row in rows}

    # Ensure base membership exists.
    base_access = _ensure_self_access(user)
    if base_access:
        access_map.setdefault(base_access.user_sdwt_prod, base_access)

    result: List[Dict[str, object]] = []
    for prod, entry in sorted(access_map.items()):
        source = "self" if prod == user.user_sdwt_prod else "grant"
        result.append(_serialize_access(entry, source))
    return result


@method_decorator(csrf_exempt, name="dispatch")
class AccountAffiliationView(APIView):
    """현재 사용자의 user_sdwt_prod 소속 관리 (실제 변경 시점 입력)."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        _ensure_self_access(user)

        access_list = _current_access_list(user)
        manageable = [entry["userSdwtProd"] for entry in access_list if entry["canManage"]]
        options = list(
            AffiliationHierarchy.objects.all()
            .order_by("department", "line", "user_sdwt_prod")
            .values("department", "line", "user_sdwt_prod")
        )

        return JsonResponse(
            {
                "currentUserSdwtProd": user.user_sdwt_prod,
                "currentDepartment": user.department,
                "currentLine": user.line,
                "timezone": TIMEZONE_NAME,
                "accessibleUserSdwtProds": access_list,
                "manageableUserSdwtProds": manageable,
                "affiliationOptions": options,
            }
        )

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        _ensure_self_access(user)

        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        department = (payload.get("department") or "").strip()
        line = (payload.get("line") or "").strip()
        new_value = (payload.get("user_sdwt_prod") or payload.get("userSdwtProd") or "").strip()
        if not new_value:
            return JsonResponse({"error": "user_sdwt_prod is required"}, status=400)

        option = get_affiliation_option(department, line, new_value)
        if option is None:
            return JsonResponse({"error": "Invalid department/line/user_sdwt_prod combination"}, status=400)

        # 이동하려는 소속에 대한 관리자 승인 필요 (superuser는 예외)
        if not user.is_superuser:
            has_manage_permission = UserSdwtProdAccess.objects.filter(
                user=user, user_sdwt_prod=new_value, can_manage=True
            ).exists()
            if not has_manage_permission:
                return JsonResponse({"error": "forbidden"}, status=403)

        effective_from_raw = payload.get("effective_from") or payload.get("effectiveFrom")
        effective_from = _parse_effective_from(effective_from_raw)
        if effective_from_raw and effective_from is None:
            return JsonResponse({"error": "Invalid effective_from"}, status=400)
        if not effective_from:
            effective_from = timezone.now()

        UserSdwtProdChange.objects.create(
            user=user,
            department=option.department,
            line=option.line,
            from_user_sdwt_prod=user.user_sdwt_prod,
            to_user_sdwt_prod=new_value,
            effective_from=effective_from,
            applied=True,
            created_by=user,
        )

        previous_user_sdwt = user.user_sdwt_prod
        user.user_sdwt_prod = new_value
        user.department = option.department
        user.line = option.line
        user.save(update_fields=["user_sdwt_prod", "department", "line"])

        _ensure_self_access(user)

        # 이전 소속 관리 권한 회수
        if previous_user_sdwt and previous_user_sdwt != new_value:
            UserSdwtProdAccess.objects.filter(
                user=user, user_sdwt_prod=previous_user_sdwt, can_manage=True
            ).update(can_manage=False)

        # 메일/RAG 재분류 (시점 기준)
        try:
            reclassify_emails_for_user_sdwt_change(user, effective_from)
        except Exception:
            logger.exception("Failed to reclassify emails for user %s", user.username)

        return self.get(request, *args, **kwargs)


@method_decorator(csrf_exempt, name="dispatch")
class AccountGrantView(APIView):
    """user_sdwt_prod 그룹 접근 권한 부여/회수."""

    def _require_manage_permission(self, user, user_sdwt_prod: str) -> Optional[JsonResponse]:
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)
        if user.is_superuser or user.is_staff:
            return None
        has_permission = UserSdwtProdAccess.objects.filter(
            user=user, user_sdwt_prod=user_sdwt_prod, can_manage=True
        ).exists()
        if has_permission:
            return None
        return JsonResponse({"error": "forbidden"}, status=403)

    def _resolve_target_user(self, payload: Dict[str, object]) -> Optional[User]:
        target_id = payload.get("userId") or payload.get("user_id")
        target_username = payload.get("username")
        user_qs = User.objects.all()
        target: Optional[User] = None
        if target_id:
            try:
                target = user_qs.get(id=int(target_id))
            except (User.DoesNotExist, ValueError, TypeError):
                target = None
        if not target and target_username:
            try:
                target = user_qs.get(username=str(target_username))
            except User.DoesNotExist:
                target = None
        return target

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)
        _ensure_self_access(user)
        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        target_group = (payload.get("user_sdwt_prod") or payload.get("userSdwtProd") or "").strip()
        if not target_group:
            return JsonResponse({"error": "user_sdwt_prod is required"}, status=400)

        permission_error = self._require_manage_permission(user, target_group)
        if permission_error:
            return permission_error

        target_user = self._resolve_target_user(payload)
        if not target_user:
            return JsonResponse({"error": "Target user not found"}, status=404)

        action = (payload.get("action") or "grant").lower()
        can_manage = bool(payload.get("canManage") or payload.get("can_manage"))

        if action == "revoke":
            access = UserSdwtProdAccess.objects.filter(user=target_user, user_sdwt_prod=target_group).first()
            if not access:
                return JsonResponse({"status": "ok", "deleted": 0})

            if access.can_manage:
                remaining_managers = UserSdwtProdAccess.objects.filter(
                    user_sdwt_prod=target_group,
                    can_manage=True,
                ).exclude(user=target_user)
                if not remaining_managers.exists():
                    return JsonResponse({"error": "Cannot remove the last manager for this group"}, status=400)

            access.delete()
            return JsonResponse({"status": "ok", "deleted": 1})

        access, created = UserSdwtProdAccess.objects.get_or_create(
            user=target_user,
            user_sdwt_prod=target_group,
            defaults={"can_manage": can_manage, "granted_by": user},
        )
        if not created and (access.can_manage != can_manage or access.granted_by_id != user.id):
            access.can_manage = can_manage
            access.granted_by = user
            access.save(update_fields=["can_manage", "granted_by"])

        return JsonResponse(_serialize_member(access))


@method_decorator(csrf_exempt, name="dispatch")
class AccountGrantListView(APIView):
    """요청 사용자가 관리할 수 있는 user_sdwt_prod 그룹 멤버 목록 조회."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        _ensure_self_access(user)

        manageable_rows = UserSdwtProdAccess.objects.filter(user=user, can_manage=True).values_list(
            "user_sdwt_prod", flat=True
        )
        manageable_set = set(manageable_rows)
        if user.user_sdwt_prod:
            manageable_set.add(user.user_sdwt_prod)

        groups: List[Dict[str, object]] = []
        if not manageable_set:
            return JsonResponse({"groups": groups})

        members = (
            UserSdwtProdAccess.objects.filter(user_sdwt_prod__in=manageable_set)
            .select_related("user")
            .order_by("user_sdwt_prod", "user_id")
        )

        members_by_group: Dict[str, List[Dict[str, object]]] = {prod: [] for prod in manageable_set}
        for access in members:
            members_by_group.setdefault(access.user_sdwt_prod, []).append(_serialize_member(access))

        for prod in sorted(manageable_set):
            groups.append({"userSdwtProd": prod, "members": members_by_group.get(prod, [])})

        return JsonResponse({"groups": groups})


@method_decorator(csrf_exempt, name="dispatch")
class LineSdwtOptionsView(APIView):
    """사용자가 선택할 수 있는 line/user_sdwt_prod 조합을 DB 값으로 한정해 제공."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        rows = (
            LineSDWT.objects.filter(line_id__isnull=False, line_id__gt="")
            .exclude(user_sdwt_prod__isnull=True)
            .exclude(user_sdwt_prod__exact="")
            .order_by("line_id", "user_sdwt_prod")
            .values("line_id", "user_sdwt_prod")
        )

        grouped: Dict[str, List[str]] = {}
        for row in rows:
            line = row["line_id"]
            usdwt = row["user_sdwt_prod"]
            grouped.setdefault(line, []).append(usdwt)

        lines = [
            {"lineId": line_id, "userSdwtProds": sorted(list(set(user_sdwt_list)))}  # dedupe per line
            for line_id, user_sdwt_list in grouped.items()
        ]
        all_user_sdwt = sorted({usdwt for user_sdwt_list in grouped.values() for usdwt in user_sdwt_list})

        return JsonResponse({"lines": lines, "userSdwtProds": all_user_sdwt})
