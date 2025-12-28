"""테이블 조회 및 업데이트 관련 뷰."""
from __future__ import annotations

import logging

from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from api.common.constants import DEFAULT_TABLE
from api.common.utils import parse_json_body, sanitize_identifier
from api.common.activity_logging import (
    merge_activity_metadata,
    set_activity_new_state,
    set_activity_previous_state,
    set_activity_summary,
)

from .services import (
    TableNotFoundError,
    TableRecordNotFoundError,
    get_table_list_payload,
    update_table_record,
)

logger = logging.getLogger(__name__)


class TablesView(APIView):
    """임의 테이블을 조회하여 리스트 형태로 반환."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        try:
            payload = get_table_list_payload(params=request.GET)
            return JsonResponse(payload)
        except TableNotFoundError as exc:
            return JsonResponse({"error": str(exc)}, status=404)
        except (ValueError, LookupError) as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except Exception:  # pragma: no cover - 방어적 로깅
            logger.exception("Failed to load table data")
            return JsonResponse({"error": "Failed to load table data"}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class TableUpdateView(APIView):
    """임의 테이블의 일부분을 PATCH로 갱신."""

    def patch(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        table_name = sanitize_identifier(payload.get("table"), DEFAULT_TABLE)
        if not table_name:
            return JsonResponse({"error": "Invalid table name"}, status=400)

        record_id = payload.get("id")
        if record_id in (None, ""):
            return JsonResponse({"error": "Record id is required"}, status=400)

        set_activity_summary(request, f"Update {table_name} record #{record_id}")
        merge_activity_metadata(request, resource=table_name, entryId=record_id)

        try:
            result = update_table_record(payload=payload)
        except TableNotFoundError as exc:
            return JsonResponse({"error": str(exc)}, status=404)
        except TableRecordNotFoundError as exc:
            return JsonResponse({"error": str(exc)}, status=404)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except Exception:  # pragma: no cover - 방어적 로깅
            logger.exception("Failed to update table record")
            return JsonResponse({"error": "Failed to update record"}, status=500)

        if result.previous_row is not None:
            set_activity_previous_state(request, result.previous_row)
        if result.updated_row is not None:
            set_activity_new_state(request, result.updated_row)

        return JsonResponse({"success": True})


__all__ = ["TableUpdateView", "TablesView"]
