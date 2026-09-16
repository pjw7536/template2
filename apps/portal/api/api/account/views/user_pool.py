"""Account 사용자 pool과 소속 선택 옵션 HTTP endpoint를 제공합니다."""

from __future__ import annotations

from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from .. import selectors, services
from ..serializers import UserPoolQuerySerializer


@method_decorator(csrf_exempt, name="dispatch")
class AccountUserPoolView(APIView):
    """수신인 선택 UI에서 사용할 활성 사용자 pool을 조회합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """canonical query를 검증하고 사용자·부서·소속 옵션을 반환합니다."""

        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        serializer = UserPoolQuerySerializer(data=request.GET)
        if not serializer.is_valid():
            return JsonResponse(serializer.errors, status=400)
        validated = serializer.validated_data
        department = validated["department"].strip()
        results = selectors.list_active_user_pool(
            search=validated["search"].strip(),
            department=department,
            user_sdwt_prod=validated["userSdwtProd"].strip(),
            contact_field=validated["contactField"],
            limit=validated["limit"],
            include_external_snapshots=validated["includeExternalSnapshots"],
        )
        departments = selectors.list_distinct_active_departments(
            include_external_snapshots=validated["includeExternalSnapshots"]
        )
        user_sdwt_prods = selectors.list_distinct_active_user_sdwt_prod_values(
            include_external_snapshots=validated["includeExternalSnapshots"],
            department=department,
        )
        return JsonResponse(
            {
                "results": results,
                "departments": departments,
                "userSdwtProds": user_sdwt_prods,
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class LineSdwtOptionsView(APIView):
    """DB에 존재하는 line과 userSdwtProd 선택 조합을 반환합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """인증 사용자가 선택할 수 있는 소속 조합을 반환합니다."""

        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)
        pairs = selectors.list_line_sdwt_pairs()
        return JsonResponse(services.get_line_sdwt_options_payload(pairs=pairs))
