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

class DroneNotificationRecipientView(DroneAuthenticatedView):
    """Drone SOP 채널별 수신인 조회/교체 엔드포인트입니다.

    커스텀 targetUserSdwtProd는 허용하지만 lineId는 기존 라인 안에서만 허용합니다.
    """

    @classmethod
    def _validate_line_id(cls, raw_value: Any) -> tuple[str, JsonResponse | None]:
        """lineId 필수 여부를 검증합니다."""

        line_id = normalize_line_id(raw_value)
        if not line_id:
            return "", JsonResponse({"error": "lineId is required"}, status=400)
        return line_id, None

    @classmethod
    def _validate_target(cls, raw_value: Any) -> tuple[str, JsonResponse | None]:
        """targetUserSdwtProd 필수 여부를 검증합니다."""

        target_user_sdwt_prod = normalize_target_text(raw_value)
        if not target_user_sdwt_prod:
            return "", JsonResponse({"error": "targetUserSdwtProd is required"}, status=400)
        return target_user_sdwt_prod, None

    @staticmethod
    def _validate_channel(raw_value: Any) -> tuple[str, JsonResponse | None]:
        """채널 값을 mail/messenger 중 하나로 검증합니다."""

        try:
            channel = services.normalize_recipient_channel(raw_value)
        except ValueError as exc:
            return "", JsonResponse({"error": str(exc)}, status=400)
        return channel, None

    @staticmethod
    def _can_update_recipients(*, user: Any) -> bool:
        """수신인 설정 변경 권한을 확인합니다."""

        return selectors.user_can_manage_drone_sop_recipients(user=user)

    @staticmethod
    def _validate_target_line_context(*, line_id: str, target_user_sdwt_prod: str) -> JsonResponse | None:
        """target이 이미 다른 line에 소속되어 있으면 요청을 거부합니다."""

        target = selectors.get_drone_sop_channel_by_target_user_sdwt_prod(
            target_user_sdwt_prod=target_user_sdwt_prod
        )
        target_line_id = getattr(target, "line_id", "") if target else ""
        if target_line_id and target_line_id.casefold() != line_id.casefold():
            return JsonResponse({"error": "targetUserSdwtProd already belongs to another line"}, status=400)
        return None

    @staticmethod
    def _resolve_target_line_id(*, line_id: str, target_user_sdwt_prod: str) -> str:
        """기존 target이 있으면 저장된 line_id를 우선 사용합니다."""

        target = selectors.get_drone_sop_channel_by_target_user_sdwt_prod(
            target_user_sdwt_prod=target_user_sdwt_prod
        )
        target_line_id = getattr(target, "line_id", "") if target else ""
        return target_line_id or line_id

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """target/channel 수신인 목록을 반환합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: 수신인 목록

        부작용:
        - 없음(읽기 전용)

        오류:
        - 400: 입력 오류
        - 401: 미인증

        예시 요청:
        - 예시 요청: GET /api/v1/line-dashboard/notification-recipients?lineId=L1&targetUserSdwtProd=ETCH_A&channel=mail

        snake/camel 호환:
        - 요청 쿼리는 lineId/targetUserSdwtProd/channel(camelCase)만 지원합니다.
        """

        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        auth_response = self._authorize_user(request)
        if auth_response is not None:
            return auth_response

        # -----------------------------------------------------------------------------
        # 2) line/target/channel 검증
        # -----------------------------------------------------------------------------
        line_id, line_error = self._validate_line_id(request.GET.get("lineId"))
        if line_error is not None:
            return line_error
        target_user_sdwt_prod, target_error = self._validate_target(request.GET.get("targetUserSdwtProd"))
        if target_error is not None:
            return target_error
        channel, channel_error = self._validate_channel(request.GET.get("channel") or "mail")
        if channel_error is not None:
            return channel_error
        resolved_line_id = self._resolve_target_line_id(
            line_id=line_id,
            target_user_sdwt_prod=target_user_sdwt_prod,
        )

        # -----------------------------------------------------------------------------
        # 3) 수신인 조회 및 응답 반환
        # -----------------------------------------------------------------------------
        recipients = selectors.list_drone_sop_channel_recipients(
            line_id=resolved_line_id,
            target_user_sdwt_prod=target_user_sdwt_prod,
            channel=channel,
        )
        return JsonResponse(
            {
                "lineId": resolved_line_id,
                "targetUserSdwtProd": target_user_sdwt_prod,
                "channel": channel,
                "recipients": recipients,
            }
        )

    def put(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """target/channel 수신인 목록을 최종 userIds 스냅샷으로 교체합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: 갱신된 수신인 목록

        부작용:
        - 수신인 생성/삭제

        오류:
        - 400: 입력 오류
        - 401: 미인증
        - 403: 권한 없음

        예시 요청:
        - 예시 요청: PUT /api/v1/line-dashboard/notification-recipients
          요청 바디 예시:
          {"lineId":"L1","targetUserSdwtProd":"ETCH_A","channel":"mail","userIds":[1],"externalKnoxIds":["ext1"]}

        snake/camel 호환:
        - 요청 본문은 lineId/targetUserSdwtProd/channel/userIds/externalKnoxIds(camelCase)만 지원합니다.
        """

        # -----------------------------------------------------------------------------
        # 1) 인증 및 JSON 파싱
        # -----------------------------------------------------------------------------
        auth_response = self._authorize_user(request)
        if auth_response is not None:
            return auth_response
        payload, error_response = _parse_json_body_or_error(request)
        if error_response is not None:
            return error_response

        # -----------------------------------------------------------------------------
        # 2) line/target/channel/userIds 검증
        # -----------------------------------------------------------------------------
        line_id, line_error = self._validate_line_id(payload.get("lineId"))
        if line_error is not None:
            return line_error
        target_user_sdwt_prod, target_error = self._validate_target(payload.get("targetUserSdwtProd"))
        if target_error is not None:
            return target_error
        channel, channel_error = self._validate_channel(payload.get("channel") or "mail")
        if channel_error is not None:
            return channel_error
        target_line_error = self._validate_target_line_context(
            line_id=line_id,
            target_user_sdwt_prod=target_user_sdwt_prod,
        )
        if target_line_error is not None:
            return target_line_error
        try:
            user_ids = parse_user_id_list(payload.get("userIds"))
            external_knox_ids = parse_external_knox_id_list(payload.get("externalKnoxIds"))
        except DroneRequestValidationError as exc:
            return _validation_error_response(exc)

        if not self._can_update_recipients(user=request.user):
            return JsonResponse({"error": "forbidden"}, status=403)

        # -----------------------------------------------------------------------------
        # 3) 서비스 호출 및 응답 반환
        # -----------------------------------------------------------------------------
        try:
            result = services.replace_drone_sop_channel_recipients(
                line_id=line_id,
                target_user_sdwt_prod=target_user_sdwt_prod,
                channel=channel,
                user_ids=user_ids,
                external_knox_ids=external_knox_ids,
                actor=request.user,
            )
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        return JsonResponse(result)


@method_decorator(csrf_exempt, name="dispatch")
class DroneNotificationRecipientPermissionView(DroneAuthenticatedView):
    """Drone SOP 수신인 설정 권한 컨텍스트 조회 엔드포인트입니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """현재 사용자의 Drone SOP 수신인 설정 권한을 반환합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: 운영자 여부와 관리 가능한 User SDWT 목록

        부작용:
        - 없음

        오류:
        - 401: 미인증

        예시 요청:
        - 예시 요청: GET /api/v1/line-dashboard/notification-recipient-permissions

        snake/camel 호환:
        - 요청 바디 없음
        """

        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        auth_response = self._authorize_user(request)
        if auth_response is not None:
            return auth_response

        # -----------------------------------------------------------------------------
        # 2) Drone 앱 권한 컨텍스트 반환
        # -----------------------------------------------------------------------------
        return JsonResponse(selectors.get_drone_sop_permission_context(user=request.user))


class DroneMyNotificationRecipientTargetView(DroneAuthenticatedView):
    """현재 사용자가 수신인으로 등록된 target 목록 조회 엔드포인트입니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """현재 사용자의 수신 target 목록을 반환합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: 현재 사용자가 수신인인 target 목록

        부작용:
        - 없음

        오류:
        - 401: 미인증

        예시 요청:
        - 예시 요청: GET /api/v1/line-dashboard/my-notification-recipient-targets?lineId=L1

        snake/camel 호환:
        - 요청 쿼리는 lineId(camelCase)만 지원합니다.
        """

        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        auth_response = self._authorize_user(request)
        if auth_response is not None:
            return auth_response

        # -----------------------------------------------------------------------------
        # 2) 선택 라인 기준으로 본인 수신 target 조회
        # -----------------------------------------------------------------------------
        line_id = normalize_line_id(request.GET.get("lineId"))
        targets = selectors.list_drone_sop_recipient_targets_for_user(
            user=request.user,
            line_id=line_id,
        )
        return JsonResponse(
            {
                "lineId": line_id,
                "targets": targets,
            }
        )
