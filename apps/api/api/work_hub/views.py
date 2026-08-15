"""Work Hub launcher, Grist forward-auth, Webhook HTTP 경계를 제공합니다."""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlparse

from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect
from rest_framework import status
from rest_framework.views import APIView

from api.auth import services as auth_services

from .permissions import HasGristWebhookSecret
from .serializers import (
    GristWebhookPayloadSerializer,
    GristWebhookQuerySerializer,
    WorkHubContextSerializer,
)
from .services import (
    WebhookConflictError,
    WebhookMappingError,
    GristForwardAuthConfigurationError,
    GristForwardAuthRequestError,
    GristForwardAuthUserError,
    build_work_hub_context,
    has_grist_forward_auth_access,
    issue_grist_forward_auth_redirect,
    enqueue_grist_webhook,
    resolve_grist_forward_auth_user,
    validate_grist_login_next_path,
    validate_grist_login_return_url,
)


class WorkHubContextView(APIView):
    """현재 사용자의 Grist 실행 대상 소속을 반환합니다.

    요청 예시: GET /api/v1/work-hub/context
    요청 바디와 snake/camel 호환 입력은 없습니다.
    """

    def get(self, request: Any, *args: object, **kwargs: object) -> JsonResponse:
        """Portal·앱 접근 검사를 통과한 사용자의 launcher context를 반환합니다."""

        payload = build_work_hub_context(user=request.user)
        serializer = WorkHubContextSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        return JsonResponse(serializer.validated_data)


class GristForwardAuthLoginView(APIView):
    """Portal account 로그인 후 Grist forward-auth ticket을 발급합니다.

    요청 예시: GET /auth/grist/login?return_url=https://grist.example/auth/login&next=/o/work-hub
    요청 바디와 snake/camel 호환 입력은 없습니다.
    """

    permission_classes: list[type] = []

    def get(
        self,
        request: Any,
        *args: object,
        **kwargs: object,
    ) -> HttpResponse:
        """Portal 로그인·앱 접근을 검증하고 짧은 수명의 ticket으로 돌려보냅니다."""

        if not getattr(settings, "WORK_HUB_ENABLED", False):
            return HttpResponseForbidden("Work Hub가 비활성화되어 있습니다.")

        try:
            return_url = validate_grist_login_return_url(
                str(request.query_params.get("return_url") or "")
            )
            next_path = validate_grist_login_next_path(
                str(request.query_params.get("next") or "")
            )
        except GristForwardAuthRequestError:
            return HttpResponseBadRequest("유효하지 않은 Grist 로그인 요청입니다.")

        if not getattr(request.user, "is_authenticated", False):
            login_result = auth_services.auth_login(
                requested_target=request.build_absolute_uri(),
                request=request,
            )
            if login_result.bad_request_message:
                return HttpResponse(
                    "Portal 로그인을 시작할 수 없습니다.",
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            return redirect(login_result.authorize_url)

        if not has_grist_forward_auth_access(user=request.user, request=request):
            return HttpResponseForbidden("Work Hub 접근 권한이 없습니다.")

        try:
            return redirect(
                issue_grist_forward_auth_redirect(
                    user=request.user,
                    return_url=return_url,
                    next_path=next_path,
                )
            )
        except GristForwardAuthConfigurationError:
            return HttpResponse(
                "Grist forward-auth가 설정되지 않았습니다.",
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except GristForwardAuthUserError:
            return HttpResponseForbidden(
                "Grist 로그인에 필요한 Portal account 정보가 없습니다."
            )


class GristForwardAuthVerifyView(APIView):
    """내부 Nginx subrequest의 Portal account ticket을 검증합니다.

    요청 예시: GET /auth/grist/verify, X-Grist-Original-URI: /auth/login?ticket=...
    요청 바디와 snake/camel 호환 입력은 없습니다.
    """

    authentication_classes: list[type] = []
    permission_classes: list[type] = []

    def get(
        self,
        request: Any,
        *args: object,
        **kwargs: object,
    ) -> HttpResponse:
        """ticket의 현재 account·앱 권한을 확인하고 신뢰할 email header를 반환합니다."""

        original_uri = str(request.headers.get("X-Grist-Original-URI") or "")
        original_query = parse_qs(
            urlparse(original_uri).query,
            keep_blank_values=True,
        )
        ticket_values = original_query.get("ticket", [])
        next_values = original_query.get("next", [])
        ticket = ticket_values[0] if len(ticket_values) == 1 else ""
        next_path = next_values[0] if len(next_values) == 1 else ""

        if len(next_values) > 1:
            return HttpResponse(status=status.HTTP_401_UNAUTHORIZED)

        try:
            user = resolve_grist_forward_auth_user(
                ticket=ticket,
                next_path=next_path,
            )
        except GristForwardAuthConfigurationError:
            return HttpResponse(status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except (GristForwardAuthRequestError, GristForwardAuthUserError):
            return HttpResponse(status=status.HTTP_401_UNAUTHORIZED)

        if not has_grist_forward_auth_access(user=user, request=request):
            return HttpResponse(status=status.HTTP_403_FORBIDDEN)

        response = HttpResponse(status=status.HTTP_204_NO_CONTENT)
        response["X-Portal-User-Email"] = str(user.email).strip().casefold()
        response["Cache-Control"] = "no-store"
        return response


class GristWebhookView(APIView):
    """Grist WorkLog record Webhook을 수신합니다.

    요청 예시:
    POST /api/v1/work-hub/webhooks/grist?doc_id=abc&table_id=WorkLog
    [{"id": 3, "follow_up_required": true, "task": 0}]

    입력은 Grist column ID의 snake_case 계약만 지원합니다.
    """

    authentication_classes: list[type] = []
    permission_classes = [HasGristWebhookSecret]

    def post(self, request: Any, *args: object, **kwargs: object) -> JsonResponse:
        """Bearer secret과 입력을 검증한 뒤 Webhook 처리 작업을 적재합니다."""

        if not getattr(settings, "WORK_HUB_ENABLED", False):
            return JsonResponse(
                {"error": "work_hub_disabled"},
                status=status.HTTP_403_FORBIDDEN,
            )

        query_serializer = GristWebhookQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        payload_serializer = GristWebhookPayloadSerializer(data={"rows": request.data})
        payload_serializer.is_valid(raise_exception=True)
        try:
            result = enqueue_grist_webhook(
                doc_id=query_serializer.validated_data["doc_id"],
                table_id=query_serializer.validated_data["table_id"],
                rows=list(payload_serializer.validated_data["rows"]),
            )
        except WebhookConflictError as exc:
            return JsonResponse(
                {"error": "webhook_event_conflict", "detail": str(exc)},
                status=status.HTTP_409_CONFLICT,
            )
        except WebhookMappingError as exc:
            return JsonResponse(
                {"error": "webhook_mapping_not_found", "detail": str(exc)},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        return JsonResponse(result, status=status.HTTP_202_ACCEPTED)
