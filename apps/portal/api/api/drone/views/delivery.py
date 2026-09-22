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

class DroneSopInstantInformView(DroneAuthenticatedView):
    """라인 대시보드에서 호출하는 Drone SOP 단건 즉시인폼 체크 요청."""

    permission_classes: tuple = ()

    @staticmethod
    def _resolve_status(result: services.DroneSopInstantInformResult) -> str:
        """즉시 인폼 결과를 상태 문자열로 변환합니다."""

        if result.already_informed:
            return "already_informed"
        if result.queued:
            return "queued"
        return "not_queueable"

    def post(self, request: HttpRequest, sop_id: int, *args: object, **kwargs: object) -> JsonResponse:
        """Drone SOP 단건 즉시인폼 체크 요청을 처리합니다.

        요청 예시:
            예시 요청: POST /api/v1/line-dashboard/sop/123/instant-inform
            예시 바디: {"comment":"추가 코멘트"}

        반환:
            예시 응답: 200 {"status": "queued", "queued": true, "alreadyInformed": false, "updated": {...}}

        부작용:
            즉시인폼 체크는 배치 실행 시 설정된 채널 알림 전송으로 이어집니다.

        오류:
            400: 입력 검증 오류
            401: 비인증
            500: 서버 오류

        snake_case/camelCase 호환:
            요청 본문은 comment만 사용하며 camelCase만 지원합니다.
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        auth_response = self._authorize_user(request)
        if auth_response is not None:
            return auth_response

        # -----------------------------------------------------------------------------
        # 2) JSON 파싱 및 comment 검증
        # -----------------------------------------------------------------------------
        payload, payload_error = parse_json_body_or_error_when_present(request)
        if payload_error is not None:
            return payload_error
        try:
            comment = parse_optional_comment(payload)
        except DroneRequestValidationError as exc:
            return _validation_error_response(exc)

        # -----------------------------------------------------------------------------
        # 3) 액티비티 로그 기록
        # -----------------------------------------------------------------------------
        set_activity_summary(request, f"Instant inform drone_sop #{sop_id}")
        merge_activity_metadata(request, resource="drone_sop", action="instant_inform", sop_id=sop_id)
        if comment is not None:
            merge_activity_metadata(request, comment_length=len(comment))

        # -----------------------------------------------------------------------------
        # 4) 서비스 호출 및 응답 구성
        # -----------------------------------------------------------------------------
        def _run() -> JsonResponse:
            result = services.enqueue_drone_sop_jira_instant_inform(sop_id=sop_id, comment=comment)
            status = self._resolve_status(result)

            set_activity_new_state(
                request,
                {
                    "status": status,
                    "already_informed": result.already_informed,
                    "queued": result.queued,
                    "not_queueable": getattr(result, "not_queueable", False),
                    "block_reason": getattr(result, "block_reason", None),
                    "jira_key": result.jira_key,
                },
            )

            payload = {
                "status": status,
                "alreadyInformed": result.already_informed,
                "queued": result.queued,
                "notQueueable": getattr(result, "not_queueable", False),
                "blockReason": getattr(result, "block_reason", None),
                "jiraKey": result.jira_key,
                "updated": _merge_latest_delivery_updates(
                    sop_id=sop_id,
                    updated_fields=result.updated_fields,
                ),
            }
            return JsonResponse(payload, status=200)

        return self._execute_user_action(
            on_success=_run,
            log_message="Drone SOP instant inform failed",
            error_message="Drone SOP instant inform failed",
        )


@method_decorator(csrf_exempt, name="dispatch")
class DroneSopRetryChannelView(DroneAuthenticatedView):
    """라인 대시보드에서 호출하는 Drone SOP 단건 채널 재시도 요청."""

    permission_classes: tuple = ()

    @staticmethod
    def _resolve_status(result: services.DroneSopRetryChannelResult) -> str:
        """채널 재시도 결과를 상태 문자열로 변환합니다."""

        if result.queued:
            return "queued"
        if result.already_sent:
            return "already_sent"
        if getattr(result, "already_disabled", False):
            return "disabled"
        return "already_pending"

    def post(self, request: HttpRequest, sop_id: int, *args: object, **kwargs: object) -> JsonResponse:
        """Drone SOP 단건 채널 재시도 요청을 처리합니다.

        요청 예시:
            예시 요청: POST /api/v1/line-dashboard/sop/123/retry-channel
            예시 바디: {"channel":"jira"}

        반환:
            예시 응답: 200 {"status":"queued","channel":"jira","updated":{...}}

        부작용:
            실패 delivery 채널이면 해당 채널을 pending으로 되돌립니다.

        오류:
            400: 입력 검증 오류
            401: 비인증
            500: 서버 오류

        snake_case/camelCase 호환:
            요청 본문은 channel만 사용하며 camelCase만 지원합니다.
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        auth_response = self._authorize_user(request)
        if auth_response is not None:
            return auth_response

        # -----------------------------------------------------------------------------
        # 2) JSON 파싱 및 channel 검증
        # -----------------------------------------------------------------------------
        payload, payload_error = _parse_json_body_or_error(request)
        if payload_error is not None:
            return payload_error
        try:
            channel = parse_required_channel(payload)
        except DroneRequestValidationError as exc:
            return _validation_error_response(exc)

        # -----------------------------------------------------------------------------
        # 3) 액티비티 로그 기록
        # -----------------------------------------------------------------------------
        set_activity_summary(request, f"Retry drone_sop #{sop_id} channel={channel}")
        merge_activity_metadata(request, resource="drone_sop", action="retry_channel", sop_id=sop_id, channel=channel)

        # -----------------------------------------------------------------------------
        # 4) 서비스 호출 및 응답 구성
        # -----------------------------------------------------------------------------
        def _run() -> JsonResponse:
            result = services.retry_drone_sop_channel(sop_id=sop_id, channel=channel)
            status = self._resolve_status(result)

            set_activity_new_state(
                request,
                {
                    "status": status,
                    "channel": result.channel,
                    "queued": result.queued,
                    "already_pending": result.already_pending,
                    "already_sent": result.already_sent,
                    "already_disabled": getattr(result, "already_disabled", False),
                },
            )

            response_payload = {
                "status": status,
                "channel": result.channel,
                "queued": result.queued,
                "alreadyPending": result.already_pending,
                "alreadySent": result.already_sent,
                "alreadyDisabled": getattr(result, "already_disabled", False),
                "updated": _merge_latest_delivery_updates(
                    sop_id=sop_id,
                    updated_fields=result.updated_fields,
                ),
            }
            return JsonResponse(response_payload, status=200)

        return self._execute_user_action(
            on_success=_run,
            log_message="Drone SOP retry-channel failed",
            error_message="Drone SOP retry-channel failed",
        )
