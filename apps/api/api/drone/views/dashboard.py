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

class LineHistoryView(APIView):
    """라인 대시보드 차트용 시간 단위 합계/분해 집계 제공."""

    DEFAULT_RANGE_DAYS = 14

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """라인 대시보드 히스토리 집계를 반환합니다.

        요청 예시:
            예시 요청: GET /api/v1/line-dashboard/history?lineId=L1&rangeDays=14

        반환:
            예시 응답: 200 {"table": "...", "from": "...", "to": "...", "totals": [...], "breakdowns": {...}}

        부작용:
            없음. 읽기 전용 조회입니다.

        오류:
            400: 파라미터 검증 오류
            500: 서버 오류

        snake_case/camelCase 호환:
            query 파라미터는 lineId/rangeDays 등 camelCase만 지원합니다.
        """
        # -----------------------------------------------------------------------------
        # 1) 집계 payload 구성
        # -----------------------------------------------------------------------------
        try:
            payload = selectors.get_line_history_payload(
                table_param=request.GET.get("table"),
                line_id_param=request.GET.get("lineId"),
                from_param=request.GET.get("from"),
                to_param=request.GET.get("to"),
                range_days_param=request.GET.get("rangeDays"),
                default_range_days=self.DEFAULT_RANGE_DAYS,
            )
            return JsonResponse(payload)
        except (ValueError, LookupError) as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except Exception:  # 방어적 로깅 (pragma: no cover)
            return _internal_server_error_response(
                log_message="Failed to load history data",
                error_message="Failed to load history data",
            )


class LineIdListView(APIView):
    """사이드바 필터용 line_id 고유값 목록 반환."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """line_id 고유값 목록을 반환합니다.

        요청 예시:
            예시 요청: GET /api/v1/line-dashboard/line-ids

        반환:
            예시 응답: 200 {"lineIds": ["L1", "L2"]}

        부작용:
            없음. 읽기 전용 조회입니다.

        오류:
            500: 서버 오류

        snake_case/camelCase 호환:
            입력 파라미터는 없습니다.
        """
        # -----------------------------------------------------------------------------
        # 1) 목록 조회
        # -----------------------------------------------------------------------------
        try:
            return JsonResponse({"lineIds": selectors.list_distinct_line_ids()})
        except Exception:  # 방어적 로깅 (pragma: no cover)
            return _internal_server_error_response(
                log_message="Failed to load distinct line ids",
                error_message="Failed to load line options",
            )


class LineDashboardLineSdwtOptionsView(APIView):
    """TIP status 화면용 line/user_sdwt_prod 옵션을 반환합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """Drone target과 station_master 기준 선택 옵션을 반환합니다.

        요청 예시:
            예시 요청: GET /api/v1/line-dashboard/line-sdwt-options

        반환:
            예시 응답: 200 {"lines": [{"lineId": "L1", "userSdwtProds": ["S1"]}]}

        부작용:
            없음. 읽기 전용 조회입니다.

        오류:
            500: 서버 오류

        snake_case/camelCase 호환:
            입력 파라미터는 없습니다.
        """
        # -----------------------------------------------------------------------------
        # 1) Drone target 기준 line/user_sdwt_prod 옵션 조회
        # -----------------------------------------------------------------------------
        try:
            return JsonResponse(selectors.get_tip_status_line_sdwt_options_payload())
        except Exception:  # 방어적 로깅 (pragma: no cover)
            return _internal_server_error_response(
                log_message="Failed to load line SDWT options",
                error_message="Failed to load line SDWT options",
            )


class DroneTablesView(APIView):
    """라인 대시보드 테이블 조회 엔드포인트입니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """테이블 목록 조회 결과를 반환합니다.

        요청 예시:
            예시 요청: GET /api/v1/line-dashboard/tables?table=drone_sop&lineId=L1

        반환:
            예시 응답: 200 {"table":"drone_sop","rowCount":1,"rows":[...]}

        부작용:
            없음. 읽기 전용 조회입니다.

        오류:
            404: 테이블 없음
            400: 입력 오류(컬럼/날짜 등)
            500: 내부 오류
        """

        try:
            payload = services.get_table_list_payload(params=request.GET)
            return JsonResponse(payload)
        except services.TableNotFoundError as exc:
            return JsonResponse({"error": str(exc)}, status=404)
        except (ValueError, LookupError) as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except Exception:  # 방어적 로깅 (pragma: no cover)
            return _internal_server_error_response(
                log_message="Failed to load drone tables data",
                error_message="Failed to load table data",
            )


@method_decorator(csrf_exempt, name="dispatch")
class DroneTableUpdateView(APIView):
    """라인 대시보드 테이블 단건 수정 엔드포인트입니다."""

    def patch(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """테이블 레코드를 부분 업데이트합니다.

        요청 예시:
            예시 요청: PATCH /api/v1/line-dashboard/tables/update
            예시 바디: {"table":"drone_sop","id":123,"updates":{"needtosend":1}}

        반환:
            예시 응답: 200 {"success": true}

        부작용:
            대상 테이블 레코드가 업데이트됩니다.

        오류:
            400: 입력 오류/JSON 파싱 실패
            404: 테이블/레코드 없음
            500: 내부 오류
        """

        payload = parse_json_body(request)
        if not isinstance(payload, dict):
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        table_name = sanitize_identifier(payload.get("table"), TABLE_DEFAULT_TABLE)
        if not table_name:
            return JsonResponse({"error": "Invalid table name"}, status=400)

        record_id = payload.get("id")
        if record_id in (None, ""):
            return JsonResponse({"error": "Record id is required"}, status=400)

        set_activity_summary(request, f"Update {table_name} record #{record_id}")
        merge_activity_metadata(request, resource=table_name, entryId=record_id)

        try:
            result = services.update_table_record(payload=payload)
        except services.TableNotFoundError as exc:
            return JsonResponse({"error": str(exc)}, status=404)
        except services.TableRecordNotFoundError as exc:
            return JsonResponse({"error": str(exc)}, status=404)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except Exception:  # 방어적 로깅 (pragma: no cover)
            return _internal_server_error_response(
                log_message="Failed to update drone table record",
                error_message="Failed to update record",
            )

        if result.previous_row is not None:
            set_activity_previous_state(request, result.previous_row)
        if result.updated_row is not None:
            set_activity_new_state(request, result.updated_row)

        updated = _merge_latest_delivery_updates(
            sop_id=record_id,
            updated_fields=result.updated_row or {},
        )
        return JsonResponse({"success": True, "updated": updated})
