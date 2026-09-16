# =============================================================================
# 모듈 설명: Line Dashboard·Drone HTTP endpoint 책임 모듈입니다.
# =============================================================================

from __future__ import annotations

import logging
from typing import Any, Callable

from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from api.account import services as account_services
from api.common.services.activity_logging import (
    merge_activity_metadata,
    set_activity_new_state,
    set_activity_previous_state,
    set_activity_summary,
)
from api.common.services.request_helpers import (
    ensure_airflow_token,
    extract_first_error_message,
    parse_json_body,
    parse_json_body_or_error_when_present,
)

from .. import selectors, services
from ..services.jira.templates.jira_template_registry import TEMPLATE_SOURCES as JIRA_TEMPLATE_SOURCES
from ..services.mail.templates.mail_template_registry import MAIL_TEMPLATE_SOURCES
from ..services.messenger.templates.messenger_template_registry import EXCEL_TABLE_TEMPLATE_SENDERS
from ..serializers import (
    DroneEarlyInformCreateSerializer,
    DroneEarlyInformUpdateFieldsSerializer,
    DroneNotificationTargetMappingCreateSerializer,
    DroneNotificationTargetMappingDeleteSerializer,
    DroneNotificationTargetMappingUpdateSerializer,
    DroneRequestValidationError,
    DroneSopTargetAdminCreateSerializer,
    DroneSopTargetAdminDeleteSerializer,
    DroneSopTargetAdminUpdateSerializer,
    normalize_line_id,
    normalize_target_text,
    normalize_updated_by,
    parse_limit_param,
    parse_optional_bool_field,
    parse_optional_comment,
    parse_optional_text_field,
    parse_external_knox_id_list,
    parse_positive_int,
    parse_required_channel,
    parse_user_id_list,
    serialize_early_inform_entry,
    serialize_drone_sop_target_configuration,
)
from ..services.table_schema import DEFAULT_TABLE as TABLE_DEFAULT_TABLE, sanitize_identifier

logger = logging.getLogger(__name__)

TEMPLATE_OPTION_LABELS = {
    "common": "기본",
    "H1": "H1",
    "auto_sp": "Auto S/P",
}
DEFAULT_NOTIFICATION_TEMPLATE_KEY = "common"
LINE_DASHBOARD_SCOPE = "line-dashboard"
from ._shared import (
    DroneAirflowTriggerView,
    DroneAuthenticatedView,
    _ensure_airflow_authenticated,
    _ensure_authenticated,
    _ensure_line_dashboard_admin,
    _internal_server_error_response,
    _json_error,
    _merge_latest_delivery_updates,
    _parse_json_body_or_error,
    _record_activity_state_and_respond,
    _record_drone_sop_pipeline_activity,
    _respond_pipeline_trigger_result,
    _respond_pop3_ingest_result,
    _respond_precheck_has_candidates,
    _serialize_template_options,
    _validate_notification_template_key,
    _validation_error_response,
)

class DroneNotificationTargetView(DroneAuthenticatedView):
    """라인별 Drone SOP 알림 target 조회/생성 엔드포인트입니다."""

    @staticmethod
    def _serialize_target(target: Any, *, fallback_line_id: str) -> dict[str, object]:
        """DroneSopTarget row를 API 응답 형태로 변환합니다."""

        configuration = serialize_drone_sop_target_configuration(target)
        return {
            "lineId": getattr(target, "line_id", None) or fallback_line_id,
            "targetUserSdwtProd": getattr(target, "target_user_sdwt_prod", None) or "",
            "source": getattr(target, "source", None) or "custom",
            "isConfigured": True,
            "jiraKey": configuration["jiraKey"],
            "jiraEnabled": configuration["jiraEnabled"],
            "messengerEnabled": configuration["messengerEnabled"],
            "mailEnabled": configuration["mailEnabled"],
        }

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """라인별 알림 target 목록을 반환합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: target 목록

        부작용:
        - 없음(읽기 전용)

        오류:
        - 400: lineId 누락
        - 401: 미인증

        예시 요청:
        - 예시 요청: GET /api/v1/line-dashboard/notification-targets?lineId=L1

        snake/camel 호환:
        - 요청 쿼리는 lineId(camelCase)만 지원합니다.
        """

        auth_response = self._authorize_user(request)
        if auth_response is not None:
            return auth_response

        line_id = normalize_line_id(request.GET.get("lineId"))
        if not line_id:
            return JsonResponse({"error": "lineId is required"}, status=400)

        targets = selectors.list_drone_sop_notification_targets_for_line(line_id=line_id)
        mapping_options = selectors.list_drone_sop_mapping_option_values_for_line(line_id=line_id)
        mapping_option_lines = selectors.list_drone_sop_mapping_option_lines()
        return JsonResponse(
            {
                "lineId": line_id,
                "targets": targets,
                "targetUserSdwtProds": [row["targetUserSdwtProd"] for row in targets],
                "mappingOptions": mapping_options,
                "mappingOptionLines": mapping_option_lines,
            }
        )

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """라인별 알림 target을 생성합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: 생성/조회된 target

        부작용:
        - DroneSopTarget target row 생성 또는 재활성화

        오류:
        - 400: 입력 오류
        - 401: 미인증
        - 403: 권한 없음

        예시 요청:
        - 예시 요청: POST /api/v1/line-dashboard/notification-targets
          요청 바디 예시: {"lineId":"L1","targetUserSdwtProd":"L1_NIGHT_SHIFT"}

        snake/camel 호환:
        - 요청 본문은 lineId/targetUserSdwtProd(camelCase)만 지원합니다.
        """

        auth_response = self._authorize_user(request)
        if auth_response is not None:
            return auth_response
        if not selectors.user_can_manage_drone_sop_recipients(user=request.user):
            return JsonResponse({"error": "forbidden"}, status=403)

        payload, error_response = _parse_json_body_or_error(request)
        if error_response is not None:
            return error_response

        line_id = normalize_line_id(payload.get("lineId"))
        if not line_id:
            return JsonResponse({"error": "lineId is required"}, status=400)
        target_user_sdwt_prod = normalize_target_text(payload.get("targetUserSdwtProd"))
        if not target_user_sdwt_prod:
            return JsonResponse({"error": "targetUserSdwtProd is required"}, status=400)
        existing_targets = selectors.list_drone_sop_notification_targets_for_line(line_id=line_id)
        if any(
            str(row.get("targetUserSdwtProd") or "").casefold() == target_user_sdwt_prod.casefold()
            for row in existing_targets
        ):
            return JsonResponse({"error": "notification target already exists"}, status=409)

        try:
            target, updated = services.ensure_drone_sop_notification_target(
                line_id=line_id,
                target_user_sdwt_prod=target_user_sdwt_prod,
                actor=request.user,
            )
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)

        return JsonResponse(
            {
                "lineId": line_id,
                "target": self._serialize_target(target, fallback_line_id=line_id),
                "updated": updated,
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class DroneSopTargetAdminView(DroneAuthenticatedView):
    """Line Dashboard admin 전용 DroneSopTarget 관리 엔드포인트입니다."""

    @staticmethod
    def _authorize_admin(request: HttpRequest) -> JsonResponse | None:
        """Line Dashboard admin 역할을 확인합니다."""

        return _ensure_line_dashboard_admin(request)

    @staticmethod
    def _response_row(*, target_id: int) -> dict[str, object]:
        """변경된 target row를 admin 응답 형태로 조회합니다."""

        row = selectors.get_drone_sop_target_admin_row(target_id=target_id)
        if row is None:
            raise services.DroneSopTargetAdminNotFoundError("target not found")
        return row

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """DroneSopTarget 목록을 반환합니다.

        예시 요청:
        - GET /api/v1/line-dashboard/admin/drone-targets
        """

        auth_response = self._authorize_admin(request)
        if auth_response is not None:
            return auth_response

        targets = selectors.list_drone_sop_target_admin_rows()
        return JsonResponse({"targets": targets, "rowCount": len(targets)})

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """DroneSopTarget row를 생성합니다."""

        auth_response = self._authorize_admin(request)
        if auth_response is not None:
            return auth_response
        payload, error_response = _parse_json_body_or_error(request)
        if error_response is not None:
            return error_response

        serializer = DroneSopTargetAdminCreateSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse(
                {"error": extract_first_error_message(serializer.errors)},
                status=400,
            )
        validated = serializer.validated_data

        try:
            target = services.create_drone_sop_target_admin_row(
                line_id=validated["lineId"],
                target_user_sdwt_prod=validated["targetUserSdwtProd"],
            )
            row = self._response_row(target_id=target.id)
        except services.DroneSopTargetAdminDuplicateError as exc:
            return JsonResponse({"error": str(exc)}, status=409)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)

        set_activity_summary(request, "Create drone_sop_target admin row")
        set_activity_new_state(request, row)
        return JsonResponse({"target": row, "created": True}, status=201)

    def patch(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """DroneSopTarget row를 수정합니다."""

        auth_response = self._authorize_admin(request)
        if auth_response is not None:
            return auth_response
        payload, error_response = _parse_json_body_or_error(request)
        if error_response is not None:
            return error_response

        serializer = DroneSopTargetAdminUpdateSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse(
                {"error": extract_first_error_message(serializer.errors)},
                status=400,
            )
        validated = serializer.validated_data
        target_id = validated["id"]

        try:
            previous_row = selectors.get_drone_sop_target_admin_row(target_id=target_id)
            target = services.update_drone_sop_target_admin_row(
                target_id=target_id,
                line_id=validated["lineId"],
                target_user_sdwt_prod=validated["targetUserSdwtProd"],
            )
            row = self._response_row(target_id=target.id)
        except services.DroneSopTargetAdminDuplicateError as exc:
            return JsonResponse({"error": str(exc)}, status=409)
        except services.DroneSopTargetAdminNotFoundError as exc:
            return JsonResponse({"error": str(exc)}, status=404)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)

        set_activity_summary(request, "Update drone_sop_target admin row")
        set_activity_previous_state(request, previous_row or {})
        set_activity_new_state(request, row)
        return JsonResponse({"target": row, "updated": True})

    def delete(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """DroneSopTarget row를 삭제합니다."""

        auth_response = self._authorize_admin(request)
        if auth_response is not None:
            return auth_response
        payload, error_response = _parse_json_body_or_error(request)
        if error_response is not None:
            return error_response

        serializer = DroneSopTargetAdminDeleteSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse(
                {"error": extract_first_error_message(serializer.errors)},
                status=400,
            )
        target_id = serializer.validated_data["id"]

        try:
            previous_row = selectors.get_drone_sop_target_admin_row(target_id=target_id)
            services.delete_drone_sop_target_admin_row(target_id=target_id)
        except services.DroneSopTargetAdminNotFoundError as exc:
            return JsonResponse({"error": str(exc)}, status=404)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)

        set_activity_summary(request, "Delete drone_sop_target admin row")
        set_activity_previous_state(request, previous_row or {})
        set_activity_new_state(request, {"deleted": True})
        return JsonResponse({"deleted": True, "target": previous_row})


@method_decorator(csrf_exempt, name="dispatch")
class DroneNotificationTargetMappingView(DroneAuthenticatedView):
    """라인별 Drone SOP 알림 target 지정 조합 생성/수정/삭제 엔드포인트입니다."""

    @staticmethod
    def _find_response_target(*, line_id: str, target_user_sdwt_prod: str) -> dict[str, object]:
        """갱신 후 target 목록에서 응답 대상 target을 찾습니다."""

        targets = selectors.list_drone_sop_notification_targets_for_line(line_id=line_id)
        normalized_target = target_user_sdwt_prod.casefold()
        for target in targets:
            if str(target.get("targetUserSdwtProd") or "").casefold() == normalized_target:
                return target
        return {
            "lineId": line_id,
            "targetUserSdwtProd": target_user_sdwt_prod,
            "source": "custom",
            "isConfigured": True,
            "jiraKey": None,
            "jiraEnabled": True,
            "messengerEnabled": True,
            "mailEnabled": True,
            "mappings": [],
        }

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """알림 target에 sdwt_prod/user_sdwt_prod 지정 조합을 추가합니다.

        예시 요청:
        - POST /api/v1/line-dashboard/notification-target-mappings
          {"lineId":"L1","targetUserSdwtProd":"TARGET_A","sdwtProd":"SDWT_A","userSdwtProd":"USR_A"}
        """

        auth_response = self._authorize_user(request)
        if auth_response is not None:
            return auth_response
        if not selectors.user_can_manage_drone_sop_recipients(user=request.user):
            return JsonResponse({"error": "forbidden"}, status=403)

        payload, error_response = _parse_json_body_or_error(request)
        if error_response is not None:
            return error_response

        serializer = DroneNotificationTargetMappingCreateSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse(
                {"error": extract_first_error_message(serializer.errors)},
                status=400,
            )
        line_id = serializer.validated_data["normalized_line_id"]
        target_user_sdwt_prod = serializer.validated_data[
            "normalized_target_user_sdwt_prod"
        ]
        sdwt_prod = serializer.validated_data["normalized_sdwt_prod"]
        user_sdwt_prod = serializer.validated_data["normalized_user_sdwt_prod"]
        raw_needtosend_without_comment = serializer.validated_data[
            "normalized_needtosend_without_comment"
        ]

        try:
            mapping = services.create_drone_sop_target_mapping(
                line_id=line_id,
                target_user_sdwt_prod=target_user_sdwt_prod,
                sdwt_prod=sdwt_prod,
                user_sdwt_prod=user_sdwt_prod,
                needtosend_without_comment=raw_needtosend_without_comment,
                actor=request.user,
            )
        except services.DroneSopTargetMappingDuplicateError as exc:
            return JsonResponse({"error": str(exc)}, status=409)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)

        target = self._find_response_target(
            line_id=line_id,
            target_user_sdwt_prod=target_user_sdwt_prod,
        )
        return JsonResponse(
            {
                "lineId": line_id,
                "target": target,
                "mapping": {
                    "sdwtProd": mapping.sdwt_prod or "",
                    "userSdwtProd": mapping.user_sdwt_prod or "",
                    "needtosendWithoutComment": bool(mapping.needtosend_without_comment),
                },
            }
        )

    def patch(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """지정 조합의 Comment 생략 자동 예약 정책을 갱신합니다.

        예시 요청:
        - PATCH /api/v1/line-dashboard/notification-target-mappings
          {"lineId":"L1","targetUserSdwtProd":"TARGET_A","sdwtProd":"A","userSdwtProd":"EARSAUTO","needtosendWithoutComment":true}
        """

        auth_response = self._authorize_user(request)
        if auth_response is not None:
            return auth_response
        if not selectors.user_can_manage_drone_sop_recipients(user=request.user):
            return JsonResponse({"error": "forbidden"}, status=403)

        payload, error_response = _parse_json_body_or_error(request)
        if error_response is not None:
            return error_response

        serializer = DroneNotificationTargetMappingUpdateSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse(
                {"error": extract_first_error_message(serializer.errors)},
                status=400,
            )
        line_id = serializer.validated_data["normalized_line_id"]
        target_user_sdwt_prod = serializer.validated_data[
            "normalized_target_user_sdwt_prod"
        ]
        sdwt_prod = serializer.validated_data["normalized_sdwt_prod"]
        user_sdwt_prod = serializer.validated_data["normalized_user_sdwt_prod"]
        needtosend_without_comment = serializer.validated_data[
            "normalized_needtosend_without_comment"
        ]

        try:
            mapping = services.update_drone_sop_target_mapping_reservation_policy(
                line_id=line_id,
                target_user_sdwt_prod=target_user_sdwt_prod,
                sdwt_prod=sdwt_prod,
                user_sdwt_prod=user_sdwt_prod,
                needtosend_without_comment=needtosend_without_comment,
            )
        except services.DroneSopTargetMappingNotFoundError as exc:
            return JsonResponse({"error": str(exc)}, status=404)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)

        target = self._find_response_target(
            line_id=line_id,
            target_user_sdwt_prod=target_user_sdwt_prod,
        )
        return JsonResponse(
            {
                "lineId": line_id,
                "target": target,
                "mapping": {
                    "sdwtProd": mapping.sdwt_prod or "",
                    "userSdwtProd": mapping.user_sdwt_prod or "",
                    "needtosendWithoutComment": bool(mapping.needtosend_without_comment),
                },
            }
        )

    def delete(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """알림 target에 연결된 sdwt_prod/user_sdwt_prod 지정 조합을 삭제합니다.

        예시 요청:
        - DELETE /api/v1/line-dashboard/notification-target-mappings
          {"lineId":"L1","targetUserSdwtProd":"TARGET_A","sdwtProd":"SDWT_A","userSdwtProd":"USR_A"}
        """

        auth_response = self._authorize_user(request)
        if auth_response is not None:
            return auth_response
        if not selectors.user_can_manage_drone_sop_recipients(user=request.user):
            return JsonResponse({"error": "forbidden"}, status=403)

        payload, error_response = _parse_json_body_or_error(request)
        if error_response is not None:
            return error_response

        serializer = DroneNotificationTargetMappingDeleteSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse(
                {"error": extract_first_error_message(serializer.errors)},
                status=400,
            )
        line_id = serializer.validated_data["normalized_line_id"]
        target_user_sdwt_prod = serializer.validated_data[
            "normalized_target_user_sdwt_prod"
        ]
        sdwt_prod = serializer.validated_data["normalized_sdwt_prod"]
        user_sdwt_prod = serializer.validated_data["normalized_user_sdwt_prod"]

        try:
            services.delete_drone_sop_target_mapping(
                line_id=line_id,
                target_user_sdwt_prod=target_user_sdwt_prod,
                sdwt_prod=sdwt_prod,
                user_sdwt_prod=user_sdwt_prod,
            )
        except services.DroneSopTargetMappingNotFoundError as exc:
            return JsonResponse({"error": str(exc)}, status=404)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)

        target = self._find_response_target(
            line_id=line_id,
            target_user_sdwt_prod=target_user_sdwt_prod,
        )
        return JsonResponse(
            {
                "lineId": line_id,
                "target": target,
                "deleted": {
                    "sdwtProd": sdwt_prod,
                    "userSdwtProd": user_sdwt_prod,
                },
            }
        )
