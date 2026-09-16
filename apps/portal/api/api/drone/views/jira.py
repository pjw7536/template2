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

class DroneNotificationTemplateOptionView(DroneAuthenticatedView):
    """채널별 알림 템플릿 옵션을 registry 기준으로 반환합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """알림 채널별 선택 가능한 템플릿 목록을 반환합니다."""

        auth_response = self._authorize_user(request)
        if auth_response is not None:
            return auth_response

        return JsonResponse(
            {
                "templates": {
                    "jira": _serialize_template_options(JIRA_TEMPLATE_SOURCES),
                    "messenger": _serialize_template_options(EXCEL_TABLE_TEMPLATE_SENDERS),
                    "mail": _serialize_template_options(MAIL_TEMPLATE_SOURCES),
                }
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class DroneJiraKeyView(DroneAuthenticatedView):
    """target_user_sdwt_prod 단위 Jira 템플릿/프로젝트 키 조회/갱신 엔드포인트입니다."""

    MAX_PROJECT_KEY_LENGTH = 64
    MAX_TEMPLATE_KEY_LENGTH = 50
    MAX_NEEDTOSEND_KEYWORD_LENGTH = 64

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """targetUserSdwtProd에 해당하는 Jira 키/템플릿 키를 조회합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: Jira 키/템플릿 키 정보

        부작용:
        - 없음(읽기 전용)

        오류:
        - 400: targetUserSdwtProd 누락 또는 legacy 별칭 입력
        - 401: 미인증
        - 404: targetUserSdwtProd 없음

        예시 요청:
        - 예시 요청: GET /api/v1/line-dashboard/jira-keys?targetUserSdwtProd=SDWT_A

        snake/camel 호환:
        - 요청 쿼리는 targetUserSdwtProd(camelCase)만 지원합니다.
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        auth_response = self._authorize_user(request)
        if auth_response is not None:
            return auth_response

        # -----------------------------------------------------------------------------
        # 2) targetUserSdwtProd 검증
        # -----------------------------------------------------------------------------
        if "userSdwtProd" in request.GET:
            return JsonResponse({"error": "userSdwtProd is not supported; use targetUserSdwtProd"}, status=400)
        target_user_sdwt_prod = normalize_target_text(
            request.GET.get("targetUserSdwtProd")
        )
        if not target_user_sdwt_prod:
            return JsonResponse({"error": "targetUserSdwtProd is required"}, status=400)

        # -----------------------------------------------------------------------------
        # 4) Jira 키 조회 및 응답 반환
        # -----------------------------------------------------------------------------
        entry = selectors.get_drone_sop_channel_by_target_user_sdwt_prod(
            target_user_sdwt_prod=target_user_sdwt_prod
        )
        configuration = serialize_drone_sop_target_configuration(entry)
        return JsonResponse(
            {
                "targetUserSdwtProd": target_user_sdwt_prod,
                "lineId": entry.line_id if entry else "",
                **configuration,
            }
        )

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """운영자가 targetUserSdwtProd에 대한 Jira 키/템플릿 키를 갱신합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: 갱신 결과

        부작용:
        - Jira 키/템플릿 키 갱신

        오류:
        - 400: 입력 오류
        - 401: 미인증
        - 403: 권한 없음
        - 404: targetUserSdwtProd 없음

        예시 요청:
        - 예시 요청: POST /api/v1/line-dashboard/jira-keys
          요청 바디 예시: {"targetUserSdwtProd":"SDWT_A","jiraKey":"ABC","jiraTemplateKey":"common"}

        snake/camel 호환:
        - 요청 본문은 targetUserSdwtProd/jiraKey/jiraTemplateKey(camelCase)만 지원합니다.
        """
        # -----------------------------------------------------------------------------
        # 1) 인증/권한 확인
        # -----------------------------------------------------------------------------
        auth_response = self._authorize_user(request)
        if auth_response is not None:
            return auth_response
        if not selectors.user_can_manage_drone_sop_recipients(user=request.user):
            return JsonResponse({"error": "forbidden"}, status=403)

        # -----------------------------------------------------------------------------
        # 2) JSON 바디 파싱
        # -----------------------------------------------------------------------------
        payload, error_response = _parse_json_body_or_error(request)
        if error_response is not None:
            return error_response

        # -----------------------------------------------------------------------------
        # 3) targetUserSdwtProd 추출 및 검증
        # -----------------------------------------------------------------------------
        if "userSdwtProd" in payload:
            return JsonResponse({"error": "userSdwtProd is not supported; use targetUserSdwtProd"}, status=400)
        if "templateKey" in payload:
            return JsonResponse({"error": "templateKey is not supported; use jiraTemplateKey"}, status=400)
        target_user_sdwt_prod = normalize_target_text(
            payload.get("targetUserSdwtProd")
        )
        if not target_user_sdwt_prod:
            return JsonResponse({"error": "targetUserSdwtProd is required"}, status=400)
        line_id = normalize_line_id(payload.get("lineId"))

        # -----------------------------------------------------------------------------
        # 4) Jira·메신저·메일 template key 추출 및 길이 검증
        # -----------------------------------------------------------------------------
        try:
            jira_key_provided, jira_key = parse_optional_text_field(
                payload,
                field_name="jiraKey",
                max_length=self.MAX_PROJECT_KEY_LENGTH,
            )
            jira_template_key_provided, jira_template_key = parse_optional_text_field(
                payload,
                field_name="jiraTemplateKey",
                max_length=self.MAX_TEMPLATE_KEY_LENGTH,
            )
            messenger_template_key_provided, messenger_template_key = parse_optional_text_field(
                payload,
                field_name="messengerTemplateKey",
                max_length=self.MAX_TEMPLATE_KEY_LENGTH,
            )
            mail_template_key_provided, mail_template_key = parse_optional_text_field(
                payload,
                field_name="mailTemplateKey",
                max_length=self.MAX_TEMPLATE_KEY_LENGTH,
            )
            jira_enabled_provided, jira_enabled = parse_optional_bool_field(
                payload,
                field_name="jiraEnabled",
            )
            messenger_enabled_provided, messenger_enabled = parse_optional_bool_field(
                payload,
                field_name="messengerEnabled",
            )
            messenger_force_new_chatroom_provided, messenger_force_new_chatroom = parse_optional_bool_field(
                payload,
                field_name="messengerForceNewChatroom",
            )
            mail_enabled_provided, mail_enabled = parse_optional_bool_field(
                payload,
                field_name="mailEnabled",
            )
            needtosend_comment_provided, needtosend_comment_last_at = parse_optional_text_field(
                payload,
                field_name="needtosendCommentLastAt",
                max_length=self.MAX_NEEDTOSEND_KEYWORD_LENGTH,
            )
            needtosend_enabled_provided, needtosend_enabled = parse_optional_bool_field(
                payload,
                field_name="needtosendEnabled",
            )
            needtosend_ignore_sample_type_provided, needtosend_ignore_sample_type = parse_optional_bool_field(
                payload,
                field_name="needtosendIgnoreSampleType",
            )
        except DroneRequestValidationError as exc:
            return _validation_error_response(exc)

        try:
            if jira_template_key_provided:
                jira_template_key = _validate_notification_template_key(
                    field_name="jiraTemplateKey",
                    template_key=jira_template_key,
                    template_sources=JIRA_TEMPLATE_SOURCES,
                )
            if messenger_template_key_provided:
                messenger_template_key = _validate_notification_template_key(
                    field_name="messengerTemplateKey",
                    template_key=messenger_template_key,
                    template_sources=EXCEL_TABLE_TEMPLATE_SENDERS,
                )
            if mail_template_key_provided:
                mail_template_key = _validate_notification_template_key(
                    field_name="mailTemplateKey",
                    template_key=mail_template_key,
                    template_sources=MAIL_TEMPLATE_SOURCES,
                )
        except DroneRequestValidationError as exc:
            return _validation_error_response(exc)

        if not (
            jira_key_provided
            or jira_template_key_provided
            or messenger_template_key_provided
            or mail_template_key_provided
            or jira_enabled_provided
            or messenger_enabled_provided
            or messenger_force_new_chatroom_provided
            or mail_enabled_provided
            or needtosend_comment_provided
            or needtosend_enabled_provided
            or needtosend_ignore_sample_type_provided
        ):
            return JsonResponse({"error": "at least one configuration field is required"}, status=400)

        # -----------------------------------------------------------------------------
        # 6) 서비스 호출 및 응답 반환
        # -----------------------------------------------------------------------------
        payload_kwargs: dict[str, object] = {"target_user_sdwt_prod": target_user_sdwt_prod}
        if line_id:
            payload_kwargs["line_id"] = line_id
            payload_kwargs["actor"] = request.user
        if jira_key_provided:
            payload_kwargs["jira_key"] = jira_key
        if jira_template_key_provided:
            payload_kwargs["jira_template_key"] = jira_template_key
        if messenger_template_key_provided:
            payload_kwargs["messenger_template_key"] = messenger_template_key
        if mail_template_key_provided:
            payload_kwargs["mail_template_key"] = mail_template_key
        if jira_enabled_provided:
            payload_kwargs["jira_enabled"] = jira_enabled
        if messenger_enabled_provided:
            payload_kwargs["messenger_enabled"] = messenger_enabled
        if messenger_force_new_chatroom_provided:
            payload_kwargs["force_new_chatroom"] = messenger_force_new_chatroom
        if mail_enabled_provided:
            payload_kwargs["mail_enabled"] = mail_enabled
        if needtosend_comment_provided:
            payload_kwargs["needtosend_comment_last_at"] = needtosend_comment_last_at
        if needtosend_enabled_provided:
            payload_kwargs["needtosend_enabled"] = needtosend_enabled
        if needtosend_ignore_sample_type_provided:
            payload_kwargs["needtosend_ignore_sample_type"] = needtosend_ignore_sample_type

        try:
            template, updated = services.upsert_drone_sop_user_sdwt_channel(**payload_kwargs)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        configuration = serialize_drone_sop_target_configuration(template)
        return JsonResponse(
            {
                "targetUserSdwtProd": target_user_sdwt_prod,
                "lineId": template.line_id or line_id,
                **configuration,
                "updated": updated,
            }
        )


class JiraUserSdwtProdListView(DroneAuthenticatedView):
    """채널 설정에 등록된 target_user_sdwt_prod 목록을 반환합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """채널 설정에 등록된 target_user_sdwt_prod 목록을 반환합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: {"userSdwtProds": ["..."]}

        부작용:
        - 없음(읽기 전용)

        오류:
        - 401: 미인증
        - 500: 서버 오류

        예시 요청:
        - 예시 요청: GET /api/v1/line-dashboard/jira-user-sdwt-prods

        snake/camel 호환:
        - 해당 없음(요청 바디 없음)
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        auth_response = self._authorize_user(request)
        if auth_response is not None:
            return auth_response

        # -----------------------------------------------------------------------------
        # 2) 목록 조회 및 응답 반환
        # -----------------------------------------------------------------------------
        try:
            target_user_sdwt_prods = selectors.list_drone_sop_jira_target_user_sdwt_prods()
            return JsonResponse({"userSdwtProds": target_user_sdwt_prods})
        except Exception:  # 방어적 로깅 (pragma: no cover)
            return _internal_server_error_response(
                log_message="Failed to load Jira user SDWT prods",
                error_message="Failed to load Jira user SDWT prods",
            )
