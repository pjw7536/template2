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

class DroneSopPop3IngestTriggerView(DroneAirflowTriggerView):
    """외부 Airflow에서 호출하는 Drone SOP POP3 수집 트리거."""

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """POP3 수집 트리거를 실행합니다.

        요청 예시:
            예시 요청: POST /api/v1/line-dashboard/sop/ingest/pop3/trigger
            헤더 예시: Authorization: Bearer <token>

        반환:
            예시 응답: 200 {"matched": 1, "upserted": 1, "deleted": 0, "pruned": 0, "skipped": false}

        부작용:
            POP3 수집 및 DB upsert가 발생합니다.

        오류:
            401: 토큰 인증 실패
            400: 입력 검증 오류
            500: 서버 오류

        snake_case/camelCase 호환:
            입력 파라미터는 없습니다.
        """
        return self._execute_airflow_pipeline(
            request,
            summary="Trigger drone_sop POP3 ingest",
            pipeline="pop3_ingest",
            on_success=lambda: _respond_pop3_ingest_result(
                request,
                result=services.run_drone_sop_pop3_ingest_from_settings(),
            ),
            log_message="Failed to trigger drone SOP POP3 ingest",
            error_message="Drone SOP POP3 ingest failed",
        )


@method_decorator(csrf_exempt, name="dispatch")
class DroneSopPipelinePrecheckView(DroneAirflowTriggerView):
    """외부 Airflow에서 호출하는 통합 Drone SOP 파이프라인 precheck 트리거."""

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """통합 파이프라인 전송 대상 존재 여부를 반환합니다.

        요청 예시:
            예시 요청: POST /api/v1/line-dashboard/sop/precheck
            헤더 예시: Authorization: Bearer <token>

        반환:
            예시 응답: 200 {"hasCandidates": true}

        부작용:
            없음. 읽기 전용 조회입니다.

        오류:
            401: 토큰 인증 실패
            500: 서버 오류

        snake_case/camelCase 호환:
            입력 파라미터는 없습니다.
        """
        return self._execute_airflow_pipeline(
            request,
            summary="Precheck drone_sop pipeline candidates",
            pipeline="pipeline_precheck",
            on_success=lambda: _respond_precheck_has_candidates(
                request,
                has_candidates=services.has_drone_sop_pipeline_candidates(),
            ),
            log_message="Failed to precheck drone SOP pipeline candidates",
            error_message="Drone SOP pipeline precheck failed",
        )


@method_decorator(csrf_exempt, name="dispatch")
class DroneSopPipelineTriggerView(DroneAirflowTriggerView):
    """외부 Airflow에서 호출하는 통합 Drone SOP 파이프라인 실행 트리거."""

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """통합 Drone SOP 파이프라인 실행을 처리합니다.

        요청 예시:
            예시 요청: POST /api/v1/line-dashboard/sop/trigger
            헤더 예시: Authorization: Bearer <token>
            예시 바디: {"limit":100}

        반환:
            예시 응답: 200 {"candidates": 10, "jiraCreated": 9, "messengerSent": 9, "mailSent": 9}

        부작용:
            Jira/메신저/메일 전송 및 drone_sop 업데이트가 발생합니다.

        오류:
            401: 토큰 인증 실패
            400: limit 검증 오류
            500: 서버 오류

        snake_case/camelCase 호환:
            요청 본문은 limit만 사용하며 camelCase만 지원합니다.
        """
        # -----------------------------------------------------------------------------
        # 1) Airflow 토큰 검증
        # -----------------------------------------------------------------------------
        auth_response = self._authorize_airflow(request)
        if auth_response is not None:
            return auth_response

        # -----------------------------------------------------------------------------
        # 2) limit 파라미터 파싱
        # -----------------------------------------------------------------------------
        payload, payload_error = parse_json_body_or_error_when_present(request)
        if payload_error is not None:
            return payload_error
        try:
            limit = parse_limit_param(body_value=payload.get("limit"), query_value=request.GET.get("limit"))
        except DroneRequestValidationError as exc:
            return _validation_error_response(exc)

        return self._execute_airflow_pipeline(
            request,
            summary="Trigger drone_sop pipeline create",
            pipeline="pipeline_create",
            limit=limit,
            authorize=False,
            on_success=lambda: _respond_pipeline_trigger_result(
                request,
                result=services.run_drone_sop_pipeline_from_settings(limit=limit),
            ),
            log_message="Failed to trigger drone SOP pipeline create",
            error_message="Drone SOP pipeline create failed",
        )
