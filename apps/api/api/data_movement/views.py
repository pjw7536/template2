"""data_movement Airflow 트리거 API입니다."""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, is_dataclass
from typing import Any

from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from api.common.services import api_error_response, ensure_airflow_token, parse_json_body_or_error_when_present
from api.data_movement.common.registry import get_data_movement_loader
from api.data_movement.ct_process_comment.services import summarize_pending_ct_process_comments

logger = logging.getLogger(__name__)

_ALLOWED_TRIGGER_FIELDS = frozenset({"limit", "dryRun"})


def _parse_optional_positive_int(*, body_value: Any, query_value: Any, field_name: str) -> int | None:
    """body/query 값을 양의 정수 옵션으로 변환합니다."""

    raw_value = query_value if query_value not in (None, "") else body_value
    if raw_value in (None, ""):
        return None
    try:
        parsed = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name}은 1 이상의 정수여야 합니다.") from exc
    if parsed < 1:
        raise ValueError(f"{field_name}은 1 이상의 정수여야 합니다.")
    return parsed


def _parse_optional_bool(*, body_value: Any, query_value: Any, field_name: str) -> bool:
    """body/query 값을 boolean 옵션으로 변환합니다."""

    raw_value = query_value if query_value not in (None, "") else body_value
    if raw_value in (None, ""):
        return False
    if isinstance(raw_value, bool):
        return raw_value
    normalized = str(raw_value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{field_name}은 boolean 값이어야 합니다.")


def _serialize_outcome(outcome: Any) -> dict[str, Any]:
    """loader outcome을 JSON 응답용 dict로 변환합니다."""

    raw = asdict(outcome) if is_dataclass(outcome) else dict(outcome)
    return {_to_camel_case(key): value for key, value in raw.items() if value is not None}


def _to_camel_case(value: str) -> str:
    """snake_case 내부 필드명을 API camelCase 필드명으로 변환합니다."""

    return re.sub(r"_([a-z])", lambda match: match.group(1).upper(), value)


def _validate_trigger_fields(*, payload: dict[str, Any], request: HttpRequest) -> JsonResponse | None:
    """trigger body/query가 canonical 필드만 포함하는지 검증합니다."""

    unknown_fields = sorted((set(payload) | set(request.GET)) - _ALLOWED_TRIGGER_FIELDS)
    if not unknown_fields:
        return None
    return api_error_response(
        code="invalid_request",
        message="지원하지 않는 요청 필드가 있습니다.",
        status=400,
        field_errors={field: ["지원하지 않는 필드입니다."] for field in unknown_fields},
    )


def _serialize_summary(*, table_name: str, summary: Any) -> dict[str, Any]:
    """loader summary를 JSON 응답용 dict로 변환합니다."""

    outcomes = [_serialize_outcome(outcome) for outcome in summary.outcomes]
    payload = {
        "tableName": table_name,
        "processedCount": summary.processed_count,
        "successCount": summary.success_count,
        "failureCount": summary.failure_count,
        "outcomes": outcomes,
    }
    if hasattr(summary, "skipped_count"):
        payload["skippedCount"] = summary.skipped_count
    if hasattr(summary, "dry_run_count"):
        payload["dryRunCount"] = summary.dry_run_count
    if hasattr(summary, "exhausted_count"):
        payload["exhaustedCount"] = summary.exhausted_count
    return payload


@method_decorator(csrf_exempt, name="dispatch")
class DataMovementLoadTriggerView(APIView):
    """Airflow에서 data_movement 파일 적재를 트리거합니다."""

    permission_classes: tuple = ()

    def post(self, request: HttpRequest, table_name: str, *args: object, **kwargs: object) -> JsonResponse:
        """테이블별 data_movement loader를 실행합니다."""

        auth_response = ensure_airflow_token(request, require_bearer=True)
        if auth_response is not None:
            return auth_response

        loader = get_data_movement_loader(table_name)
        if loader is None:
            return api_error_response(
                code="not_found",
                message=f"지원하지 않는 data_movement 테이블입니다: {table_name}",
                status=404,
            )

        payload, payload_error = parse_json_body_or_error_when_present(request)
        if payload_error is not None:
            return payload_error
        validation_error = _validate_trigger_fields(payload=payload, request=request)
        if validation_error is not None:
            return validation_error

        try:
            limit = _parse_optional_positive_int(
                body_value=payload.get("limit"),
                query_value=request.GET.get("limit"),
                field_name="limit",
            )
            dry_run = _parse_optional_bool(
                body_value=payload.get("dryRun"),
                query_value=request.GET.get("dryRun"),
                field_name="dryRun",
            )
            summary = loader(dry_run=dry_run, limit=limit)
        except ValueError as exc:
            return api_error_response(code="invalid_request", message=str(exc), status=400)
        except Exception:
            logger.exception("Failed to trigger data_movement load: %s", table_name)
            return api_error_response(
                code="internal_error",
                message="data_movement 파일 적재에 실패했습니다.",
                status=500,
            )

        response_payload = _serialize_summary(table_name=table_name, summary=summary)
        status_code = 500 if summary.failure_count else 200
        return JsonResponse(response_payload, status=status_code)


@method_decorator(csrf_exempt, name="dispatch")
class DataMovementCtProcessCommentSummaryTriggerView(APIView):
    """Airflow에서 ct_process_comment OpenWebUI 요약을 트리거합니다."""

    permission_classes: tuple = ()

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """ct_process_comment 요약 batch를 실행합니다."""

        auth_response = ensure_airflow_token(request, require_bearer=True)
        if auth_response is not None:
            return auth_response

        payload, payload_error = parse_json_body_or_error_when_present(request)
        if payload_error is not None:
            return payload_error
        validation_error = _validate_trigger_fields(payload=payload, request=request)
        if validation_error is not None:
            return validation_error

        try:
            limit = _parse_optional_positive_int(
                body_value=payload.get("limit"),
                query_value=request.GET.get("limit"),
                field_name="limit",
            )
            dry_run = _parse_optional_bool(
                body_value=payload.get("dryRun"),
                query_value=request.GET.get("dryRun"),
                field_name="dryRun",
            )
            summary = summarize_pending_ct_process_comments(dry_run=dry_run, limit=limit)
        except ValueError as exc:
            return api_error_response(code="invalid_request", message=str(exc), status=400)
        except Exception:
            logger.exception("Failed to trigger ct_process_comment summary")
            return api_error_response(
                code="internal_error",
                message="ct_process_comment 요약에 실패했습니다.",
                status=500,
            )

        response_payload = _serialize_summary(table_name="ct_process_comment", summary=summary)
        status_code = 500 if summary.all_failed else 200
        return JsonResponse(response_payload, status=status_code)
