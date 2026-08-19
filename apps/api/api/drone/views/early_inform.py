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
    _resolve_knox_id,
    _respond_pipeline_trigger_result,
    _respond_pop3_ingest_result,
    _respond_precheck_has_candidates,
    _serialize_template_options,
    _validate_notification_template_key,
    _validation_error_response,
)

class DroneEarlyInformView(DroneAuthenticatedView):
    """drone_early_inform 테이블 CRUD(생성/조회/수정/삭제) 엔드포인트입니다.

    - GET: lineId로 행 목록 조회(정렬: main_step ASC, id ASC)
    - POST: 신규 행 추가(중복 main_step 방지 가정)
    - PATCH: 부분 업데이트(id 필수)
    - DELETE: 행 삭제(id 쿼리 파라미터)
    """

    # 한 곳에서만 테이블명을 관리해 실수 방지
    TABLE_NAME = "drone_early_inform"

    # --------------------------------------------------------------------- #
    # 조회
    # --------------------------------------------------------------------- #
    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """lineId로 행 목록을 가져옵니다.

        요청 예시:
            예시 요청: GET /api/v1/line-dashboard/early-inform?lineId=L1

        반환:
            예시 응답: 200 {"lineId": "...", "rowCount": 1, "rows": [...], "userSdwt": [...]}

        부작용:
            없음. 읽기 전용 조회입니다.

        오류:
            400: lineId 누락/형식 오류
            401: 비인증
            500: 서버 오류

        snake_case/camelCase 호환:
            query 파라미터는 lineId만 지원합니다.
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        auth_response = self._authorize_user(request)
        if auth_response is not None:
            return auth_response

        # -----------------------------------------------------------------------------
        # 2) 파라미터 검증
        # -----------------------------------------------------------------------------
        line_id = normalize_line_id(request.GET.get("lineId"))
        if not line_id:
            return JsonResponse({"error": "lineId is required"}, status=400)

        # -----------------------------------------------------------------------------
        # 3) 조회 및 응답 반환
        # -----------------------------------------------------------------------------
        try:
            normalized_rows = [
                serialize_early_inform_entry(entry)
                for entry in selectors.list_early_inform_entries(line_id=line_id)
            ]
            user_sdwt_values = selectors.list_user_sdwt_prod_values_for_line(line_id=line_id)
            return JsonResponse(
                {
                    "lineId": line_id,
                    "rowCount": len(normalized_rows),
                    "rows": normalized_rows,
                    "userSdwt": user_sdwt_values,
                }
            )
        except Exception:  # 방어적 로깅 (pragma: no cover)
            return _internal_server_error_response(
                log_message="Failed to load drone_early_inform rows",
                error_message="Failed to load settings",
            )

    # --------------------------------------------------------------------- #
    # 생성
    # --------------------------------------------------------------------- #
    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """신규 행을 생성합니다.

        요청 예시:
            예시 요청: POST /api/v1/line-dashboard/early-inform
            예시 바디: {"lineId":"L1","mainStep":"STEP1","customEndStep":"STEP2"}

        반환:
            예시 응답: 201 {"entry": {...}}

        부작용:
            DroneEarlyInform 레코드가 생성됩니다.

        오류:
            400: JSON/필드 검증 오류
            401: 비인증
            409: 중복 키
            500: 서버 오류

        snake_case/camelCase 호환:
            요청 본문은 camelCase(lineId/mainStep/customEndStep)만 지원합니다.
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        auth_response = self._authorize_user(request)
        if auth_response is not None:
            return auth_response

        # -----------------------------------------------------------------------------
        # 2) JSON 파싱
        # -----------------------------------------------------------------------------
        payload, error_response = _parse_json_body_or_error(request)
        if error_response is not None:
            return error_response

        # -----------------------------------------------------------------------------
        # 3) 생성 입력 검증
        # -----------------------------------------------------------------------------
        serializer = DroneEarlyInformCreateSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse(
                {"error": extract_first_error_message(serializer.errors)},
                status=400,
            )
        line_id = serializer.validated_data["normalized_line_id"]
        main_step = serializer.validated_data["normalized_main_step"]
        custom_end_step = serializer.validated_data["normalized_custom_end_step"]

        # -----------------------------------------------------------------------------
        # 4) updated_by 계산
        # -----------------------------------------------------------------------------
        updated_by = self._resolve_updated_by(request)

        # -----------------------------------------------------------------------------
        # 5) 서비스 호출 및 액티비티 로그 기록
        # -----------------------------------------------------------------------------
        try:
            entry = services.create_early_inform_entry(
                line_id=line_id,
                main_step=main_step,
                custom_end_step=custom_end_step,
                updated_by=updated_by,
            )
            entry_payload = serialize_early_inform_entry(entry)

            set_activity_summary(request, "Create drone_early_inform entry")
            set_activity_new_state(request, entry_payload)
            merge_activity_metadata(
                request,
                resource=self.TABLE_NAME,
                entryId=entry_payload["id"],
            )
            return JsonResponse({"entry": entry_payload}, status=201)

        except services.DroneEarlyInformDuplicateError as exc:
            return JsonResponse({"error": str(exc)}, status=409)
        except Exception:  # 방어적 로깅 (pragma: no cover)
            return _internal_server_error_response(
                log_message="Failed to create drone_early_inform row",
                error_message="Failed to create entry",
            )

    # --------------------------------------------------------------------- #
    # 수정(부분)
    # --------------------------------------------------------------------- #
    def patch(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """id로 지정된 행을 부분 업데이트합니다.

        요청 예시:
            예시 요청: PATCH /api/v1/line-dashboard/early-inform
            예시 바디: {"id": 123, "customEndStep": "STEP2"}

        반환:
            예시 응답: 200 {"entry": {...}}

        부작용:
            DroneEarlyInform 레코드가 수정됩니다.

        오류:
            400: JSON/필드 검증 오류
            401: 비인증
            404: 대상 없음
            409: 중복 키
            500: 서버 오류

        snake_case/camelCase 호환:
            요청 본문은 camelCase(lineId/mainStep/customEndStep)만 지원합니다.
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        auth_response = self._authorize_user(request)
        if auth_response is not None:
            return auth_response

        # -----------------------------------------------------------------------------
        # 2) JSON 파싱
        # -----------------------------------------------------------------------------
        payload, error_response = _parse_json_body_or_error(request)
        if error_response is not None:
            return error_response

        # -----------------------------------------------------------------------------
        # 3) id 검증
        # -----------------------------------------------------------------------------
        try:
            entry_id = parse_positive_int(payload.get("id"))
        except DroneRequestValidationError as exc:
            return _validation_error_response(exc)

        # -----------------------------------------------------------------------------
        # 4) 액티비티 로그 및 업데이트 필드 수집
        # -----------------------------------------------------------------------------
        set_activity_summary(request, f"Update drone_early_inform entry #{entry_id}")
        merge_activity_metadata(request, resource=self.TABLE_NAME, entryId=entry_id)

        updated_by = self._resolve_updated_by(request)
        serializer = DroneEarlyInformUpdateFieldsSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse(
                {"error": extract_first_error_message(serializer.errors)},
                status=400,
            )
        updates = serializer.validated_data["normalized_updates"]

        # -----------------------------------------------------------------------------
        # 5) 서비스 호출 및 응답 구성
        # -----------------------------------------------------------------------------
        try:
            result = services.update_early_inform_entry(
                entry_id=entry_id,
                updates=updates,
                updated_by=updated_by,
            )
            set_activity_previous_state(request, serialize_early_inform_entry(result.previous_entry))
            entry_payload = serialize_early_inform_entry(result.entry)
            set_activity_new_state(request, entry_payload)
            return JsonResponse({"entry": entry_payload})

        except services.DroneEarlyInformNotFoundError as exc:
            return JsonResponse({"error": str(exc)}, status=404)
        except services.DroneEarlyInformDuplicateError as exc:
            return JsonResponse({"error": str(exc)}, status=409)
        except Exception:  # 방어적 로깅 (pragma: no cover)
            return _internal_server_error_response(
                log_message="Failed to update drone_early_inform row",
                error_message="Failed to update entry",
            )

    # --------------------------------------------------------------------- #
    # 삭제
    # --------------------------------------------------------------------- #
    def delete(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """id로 지정된 행을 삭제합니다.

        요청 예시:
            예시 요청: DELETE /api/v1/line-dashboard/early-inform?id=123

        반환:
            예시 응답: 200 {"success": true}

        부작용:
            DroneEarlyInform 레코드가 삭제됩니다.

        오류:
            400: id 검증 오류
            401: 비인증
            404: 대상 없음
            500: 서버 오류

        snake_case/camelCase 호환:
            query 파라미터는 id만 지원합니다.
        """
        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        auth_response = self._authorize_user(request)
        if auth_response is not None:
            return auth_response

        # -----------------------------------------------------------------------------
        # 2) id 검증
        # -----------------------------------------------------------------------------
        try:
            entry_id = parse_positive_int(request.GET.get("id"))
        except DroneRequestValidationError as exc:
            return _validation_error_response(exc)

        # -----------------------------------------------------------------------------
        # 3) 액티비티 로그 및 삭제 수행
        # -----------------------------------------------------------------------------
        set_activity_summary(request, f"Delete drone_early_inform entry #{entry_id}")
        merge_activity_metadata(request, resource=self.TABLE_NAME, entryId=entry_id)

        try:
            deleted_entry = services.delete_early_inform_entry(entry_id=entry_id)
            set_activity_previous_state(request, serialize_early_inform_entry(deleted_entry))

            set_activity_new_state(request, {"deleted": True})
            return JsonResponse({"success": True})

        except services.DroneEarlyInformNotFoundError as exc:
            return JsonResponse({"error": str(exc)}, status=404)
        except Exception:  # 방어적 로깅 (pragma: no cover)
            return _internal_server_error_response(
                log_message="Failed to delete drone_early_inform row",
                error_message="Failed to delete entry",
            )

    # --------------------------------------------------------------------- #
    # 검증/정규화 유틸
    # --------------------------------------------------------------------- #
    @classmethod
    def _resolve_updated_by(cls, request: HttpRequest) -> str | None:
        """요청 사용자 기반 updated_by 값을 정규화합니다."""

        knox_id = _resolve_knox_id(request)
        return normalize_updated_by(knox_id or "system")
