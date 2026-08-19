"""Airflow 외부 소속 스냅샷 동기화 HTTP endpoint를 제공합니다."""

from __future__ import annotations

from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from api.common.services import ensure_airflow_token, parse_json_body

from .. import services
from ..serializers import ExternalAffiliationSyncSerializer


@method_decorator(csrf_exempt, name="dispatch")
class AccountExternalAffiliationSyncView(APIView):
    """Airflow 토큰으로 인증한 외부 소속 스냅샷을 동기화합니다."""

    permission_classes: tuple = ()

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """canonical camelCase records를 검증해 동기화 서비스에 전달합니다."""

        auth_response = ensure_airflow_token(request, require_bearer=True)
        if auth_response is not None:
            return auth_response

        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        serializer = ExternalAffiliationSyncSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse(serializer.errors, status=400)

        records = serializer.validated_data.get("records") or []
        return JsonResponse(services.sync_external_affiliations(records=records))
