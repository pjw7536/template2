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
def _serialize_template_options(template_sources: dict[str, object]) -> list[dict[str, str]]:
    """registry key 목록을 template select 옵션으로 변환합니다."""

    return [
        {
            "key": key,
            "label": TEMPLATE_OPTION_LABELS.get(key, key),
        }
        for key in template_sources
    ]


def _validate_notification_template_key(
    *,
    field_name: str,
    template_key: str | None,
    template_sources: dict[str, object],
) -> str:
    """채널별 template key가 registry에 존재하는지 검증합니다."""

    resolved_key = template_key or DEFAULT_NOTIFICATION_TEMPLATE_KEY
    if resolved_key not in template_sources:
        raise DroneRequestValidationError(f"{field_name} is not supported")
    return resolved_key


def _ensure_authenticated(request: HttpRequest) -> JsonResponse | None:
    """인증 여부를 확인하고 실패 시 JsonResponse를 반환합니다.

    인자:
        요청: Django HttpRequest 객체.

    반환:
        인증 실패 시 JsonResponse, 성공 시 None.

    부작용:
        없음. 순수 검사입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 사용자 인증 확인
    # -----------------------------------------------------------------------------
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return JsonResponse({"error": "로그인이 필요합니다."}, status=401)
    return None


def _ensure_line_dashboard_admin(request: HttpRequest) -> JsonResponse | None:
    """Line Dashboard admin 역할을 확인하고 실패 시 JsonResponse를 반환합니다."""

    auth_response = _ensure_authenticated(request)
    if auth_response is not None:
        return auth_response
    if not account_services.has_scope_role(
        user=request.user,
        scope_key=LINE_DASHBOARD_SCOPE,
        request=request,
    ):
        return JsonResponse({"error": "forbidden"}, status=403)
    return None


def _json_error(message: str, status: int = 400) -> JsonResponse:
    """에러 응답(JsonResponse)을 구성합니다.

    인자:
        message: 에러 메시지.
        status: HTTP 상태 코드.

    반환:
        JsonResponse 객체.

    부작용:
        없음. 순수 응답 생성입니다.
    """

    return JsonResponse({"error": message}, status=status)


def _validation_error_response(exc: DroneRequestValidationError) -> JsonResponse:
    """요청 검증 예외를 JsonResponse로 변환합니다."""

    return JsonResponse({"error": str(exc)}, status=exc.status_code)


def _parse_json_body_or_error(request: HttpRequest) -> tuple[dict[str, Any], JsonResponse | None]:
    """JSON 바디를 파싱하고 실패 시 에러 응답을 반환합니다.

    인자:
        request: Django HttpRequest 객체.

    반환:
        (payload, error_response) 형태의 튜플.
        - 성공 시: (payload, None)
        - 실패 시: ({}, JsonResponse)

    부작용:
        없음. 순수 파싱입니다.
    """

    payload = parse_json_body(request)
    if not isinstance(payload, dict):
        return {}, _json_error("Invalid JSON body", status=400)
    return payload, None


def _resolve_knox_id(request: HttpRequest) -> str | None:
    """요청 사용자에서 knox_id를 추출합니다.

    인자:
        request: Django HttpRequest 객체.

    반환:
        knox_id 문자열 또는 None.

    부작용:
        없음. 순수 추출입니다.
    """

    user = getattr(request, "user", None)
    if user and getattr(user, "is_authenticated", False):
        return getattr(user, "knox_id", None)
    return None


def _ensure_airflow_authenticated(request: HttpRequest) -> JsonResponse | None:
    """Airflow Bearer 토큰 인증을 수행합니다.

    인자:
        request: Django HttpRequest 객체.

    반환:
        인증 실패 시 JsonResponse, 성공 시 None.

    부작용:
        없음. 인증 검사만 수행합니다.
    """

    return ensure_airflow_token(request, require_bearer=True)


def _record_drone_sop_pipeline_activity(
    request: HttpRequest,
    *,
    summary: str,
    pipeline: str,
    limit: int | None = None,
) -> None:
    """Drone SOP 파이프라인 액티비티 로그 메타데이터를 기록합니다."""

    set_activity_summary(request, summary)
    metadata: dict[str, Any] = {
        "resource": "drone_sop",
        "pipeline": pipeline,
    }
    if limit is not None:
        metadata["limit"] = limit
    merge_activity_metadata(request, **metadata)


def _internal_server_error_response(
    *,
    log_message: str,
    error_message: str,
) -> JsonResponse:
    """공통 500 응답을 생성하고 예외 로그를 기록합니다."""

    logger.exception(log_message)
    return JsonResponse({"error": error_message}, status=500)


def _record_activity_state_and_respond(
    request: HttpRequest,
    *,
    activity_state: dict[str, Any],
    response_payload: dict[str, Any],
    status: int = 200,
) -> JsonResponse:
    """액티비티 상태를 기록하고 JSON 응답을 반환합니다."""

    set_activity_new_state(request, activity_state)
    return JsonResponse(response_payload, status=status)


def _merge_latest_delivery_updates(*, sop_id: int, updated_fields: dict[str, Any]) -> dict[str, Any]:
    """단건 액션 응답에 최신 delivery 메타를 병합합니다."""

    delivery_updates = services.get_table_record_delivery_update_payload(record_id=sop_id)
    return {**updated_fields, **delivery_updates}


def _respond_precheck_has_candidates(
    request: HttpRequest,
    *,
    has_candidates: bool,
) -> JsonResponse:
    """사전 확인(precheck) 응답을 구성합니다."""

    response_payload: dict[str, Any] = {"hasCandidates": has_candidates}
    activity_state: dict[str, Any] = {"has_candidates": has_candidates}

    return _record_activity_state_and_respond(
        request,
        activity_state=activity_state,
        response_payload=response_payload,
    )


def _respond_pop3_ingest_result(request: HttpRequest, *, result: Any) -> JsonResponse:
    """POP3 수집 트리거 응답을 구성합니다."""

    return _record_activity_state_and_respond(
        request,
        activity_state={
            "matched": result.matched_mails,
            "upserted": result.upserted_rows,
            "deleted": result.deleted_mails,
            "pruned": result.pruned_rows,
            "skipped": result.skipped,
            "skip_reason": result.skip_reason,
        },
        response_payload={
            "matched": result.matched_mails,
            "upserted": result.upserted_rows,
            "deleted": result.deleted_mails,
            "pruned": result.pruned_rows,
            "skipped": result.skipped,
            "skipReason": result.skip_reason,
        },
    )


def _respond_pipeline_trigger_result(
    request: HttpRequest,
    *,
    result: Any,
) -> JsonResponse:
    """통합 Drone SOP 파이프라인 트리거 응답을 구성합니다."""

    response_payload: dict[str, Any] = {
        "candidates": result.candidates,
        "jiraCreated": result.jira_created,
        "jiraUpdated": result.jira_updated_rows,
        "messengerSent": result.messenger_sent,
        "mailSent": result.mail_sent,
        "skipped": result.skipped,
        "skipReason": result.skip_reason,
    }
    activity_state: dict[str, Any] = {
        "candidates": result.candidates,
        "jira_created": result.jira_created,
        "jira_updated_rows": result.jira_updated_rows,
        "messenger_sent": result.messenger_sent,
        "mail_sent": result.mail_sent,
        "skipped": result.skipped,
        "skip_reason": result.skip_reason,
    }
    return _record_activity_state_and_respond(
        request,
        activity_state=activity_state,
        response_payload=response_payload,
    )


class DroneAirflowTriggerView(APIView):
    """Airflow Bearer 토큰 인증이 필요한 트리거 뷰 베이스 클래스."""

    permission_classes: tuple = ()

    @staticmethod
    def _authorize_airflow(request: HttpRequest) -> JsonResponse | None:
        """Airflow 토큰 인증을 확인합니다."""

        return _ensure_airflow_authenticated(request)

    def _execute_airflow_pipeline(
        self,
        request: HttpRequest,
        *,
        summary: str,
        pipeline: str,
        on_success: Callable[[], JsonResponse],
        log_message: str,
        error_message: str,
        limit: int | None = None,
        authorize: bool = True,
    ) -> JsonResponse:
        """Airflow 트리거 공통 실행 흐름(인증/로그/예외)을 처리합니다."""

        if authorize:
            auth_response = self._authorize_airflow(request)
            if auth_response is not None:
                return auth_response

        _record_drone_sop_pipeline_activity(
            request,
            summary=summary,
            pipeline=pipeline,
            limit=limit,
        )

        try:
            return on_success()
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except Exception:  # 방어적 로깅 (pragma: no cover)
            return _internal_server_error_response(
                log_message=log_message,
                error_message=error_message,
            )


class DroneAuthenticatedView(APIView):
    """로그인 사용자 인증이 필요한 뷰 베이스 클래스."""

    @staticmethod
    def _authorize_user(request: HttpRequest) -> JsonResponse | None:
        """사용자 인증을 확인합니다."""

        return _ensure_authenticated(request)

    @staticmethod
    def _execute_user_action(
        *,
        on_success: Callable[[], JsonResponse],
        log_message: str,
        error_message: str,
    ) -> JsonResponse:
        """사용자 액션 공통 실행 흐름(ValueError/예외)을 처리합니다."""

        try:
            return on_success()
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except Exception:  # 방어적 로깅 (pragma: no cover)
            return _internal_server_error_response(
                log_message=log_message,
                error_message=error_message,
            )

__all__ = [
    "DroneAirflowTriggerView",
    "DroneAuthenticatedView",
    "_ensure_airflow_authenticated",
    "_ensure_authenticated",
    "_ensure_line_dashboard_admin",
    "_internal_server_error_response",
    "_json_error",
    "_merge_latest_delivery_updates",
    "_parse_json_body_or_error",
    "_record_activity_state_and_respond",
    "_record_drone_sop_pipeline_activity",
    "_resolve_knox_id",
    "_respond_pipeline_trigger_result",
    "_respond_pop3_ingest_result",
    "_respond_precheck_has_candidates",
    "_serialize_template_options",
    "_validate_notification_template_key",
    "_validation_error_response",
]
