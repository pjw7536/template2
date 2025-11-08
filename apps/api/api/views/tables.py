"""테이블 조회 및 업데이트 관련 뷰."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, List

from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from ..db import execute, run_query
from .constants import DATE_COLUMN_CANDIDATES, DEFAULT_TABLE
from .utils import (
    build_line_filters,
    find_column,
    list_table_columns,
    normalize_date_only,
    parse_json_body,
    pick_base_timestamp_column,
    sanitize_identifier,
)

logger = logging.getLogger(__name__)


class TablesView(APIView):
    """임의 테이블을 조회하여 리스트 형태로 반환."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        params = request.GET

        table_name = sanitize_identifier(params.get("table"), DEFAULT_TABLE)
        if not table_name:
            return JsonResponse({"error": "Invalid table name"}, status=400)

        from_param = normalize_date_only(params.get("from"))
        to_param = normalize_date_only(params.get("to"))
        line_id_param = params.get("lineId")
        normalized_line_id = line_id_param.strip() if isinstance(line_id_param, str) and line_id_param.strip() else None

        if from_param and to_param:
            from_time = datetime.fromisoformat(f"{from_param}T00:00:00")
            to_time = datetime.fromisoformat(f"{to_param}T23:59:59")
            if from_time > to_time:
                from_param, to_param = to_param, from_param

        try:
            column_names = list_table_columns(table_name)
            if not column_names:
                return JsonResponse({"error": f'Table "{table_name}" has no columns'}, status=400)

            base_ts_col = pick_base_timestamp_column(column_names)
            if not base_ts_col:
                expected = ", ".join(DATE_COLUMN_CANDIDATES)
                return JsonResponse(
                    {"error": f'No timestamp-like column found in "{table_name}". Expected one of: {expected}.'},
                    status=400,
                )

            line_filter_result = build_line_filters(column_names, normalized_line_id)
            where_parts = list(line_filter_result["filters"])
            query_params = list(line_filter_result["params"])

            where_parts.append(
                f"{base_ts_col} >= (NOW() - INTERVAL '27 hours')"
            )

            if from_param:
                where_parts.append(f"{base_ts_col} >= %s")
                query_params.append(f"{from_param} 00:00:00")

            if to_param:
                where_parts.append(f"{base_ts_col} <= %s")
                query_params.append(f"{to_param} 23:59:59")

            where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
            order_clause = f"ORDER BY {base_ts_col} DESC, id DESC"

            rows = run_query(
                """
                SELECT *
                FROM {table}
                {where_clause}
                {order_clause}
                """.format(table=table_name, where_clause=where_clause, order_clause=order_clause),
                query_params,
            )

            response_payload = {
                "table": table_name,
                "cutoff": "{} >= NOW() - INTERVAL '27 hours'".format(base_ts_col),
                "from": from_param or None,
                "to": to_param or None,
                "rowCount": len(rows),
                "columns": column_names,
                "rows": rows,
            }
            return JsonResponse(response_payload)
        except Exception as exc:  # pragma: no cover - 방어적 로깅
            error_code = getattr(exc, "code", None) or getattr(exc, "pgcode", None)
            if error_code in {"ER_NO_SUCH_TABLE", "42P01"}:
                return JsonResponse({"error": f'Table "{table_name}" was not found'}, status=404)
            logger.exception("Failed to load table data")
            return JsonResponse({"error": "Failed to load table data"}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class TableUpdateView(APIView):
    """임의 테이블의 일부분을 PATCH로 갱신."""

    ALLOWED_UPDATE_COLUMNS = {"comment", "needtosend"}

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

        updates = payload.get("updates")
        if not isinstance(updates, dict):
            return JsonResponse({"error": "Updates must be an object"}, status=400)

        filtered = [(key, value) for key, value in updates.items() if key in self.ALLOWED_UPDATE_COLUMNS and value is not None]
        if not filtered:
            return JsonResponse({"error": "No valid updates provided"}, status=400)

        try:
            column_names = list_table_columns(table_name)

            id_column = find_column(column_names, "id")
            if not id_column:
                return JsonResponse({"error": f'Table "{table_name}" does not expose an id column'}, status=400)

            assignments: List[str] = []
            params: List[Any] = []

            for key, value in filtered:
                column_name = find_column(column_names, key)
                if not column_name:
                    continue
                assignments.append(f"{column_name} = %s")
                params.append(self._normalize_update_value(key, value))

            if not assignments:
                return JsonResponse({"error": "No matching columns to update"}, status=400)

            params.append(record_id)
            sql = (
                """
                UPDATE {table}
                SET {assignments}
                WHERE {id_column} = %s
                """.format(
                    table=table_name,
                    assignments=", ".join(assignments),
                    id_column=id_column,
                )
            )

            affected, _ = execute(sql, params)
            if affected == 0:
                return JsonResponse({"error": "Record not found"}, status=404)

            return JsonResponse({"success": True})
        except Exception as exc:  # pragma: no cover - 방어적 로깅
            error_code = getattr(exc, "code", None) or getattr(exc, "pgcode", None)
            if error_code in {"ER_NO_SUCH_TABLE", "42P01"}:
                return JsonResponse({"error": f'Table "{table_name}" was not found'}, status=404)
            logger.exception("Failed to update table record")
            return JsonResponse({"error": "Failed to update record"}, status=500)

    @staticmethod
    def _normalize_update_value(key: str, value: Any) -> Any:
        """컬럼별 업데이트 값 정규화."""

        if key == "comment":
            return "" if value is None else str(value)
        if key == "needtosend":
            return TableUpdateView._coerce_boolean(value)
        return value

    @staticmethod
    def _coerce_boolean(value: Any) -> bool:
        """다양한 입력을 0/1 불리언으로 안전 변환."""

        if isinstance(value, bool):
            return value
        if value is None:
            return False
        if isinstance(value, (int, float)):
            return int(value) == 1
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "t", "y", "yes"}:
                return True
            if normalized in {"0", "false", "f", "n", "no", ""}:
                return False
        try:
            coerced = int(value)
            return coerced == 1
        except (TypeError, ValueError):
            return False


__all__ = ["TableUpdateView", "TablesView"]
