"""테이블 조회 및 업데이트 관련 뷰."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, List, Tuple

from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from ..activity_logging import (
    merge_activity_metadata,
    set_activity_new_state,
    set_activity_previous_state,
    set_activity_summary,
)
from ..db import execute, run_query
from .constants import DEFAULT_TABLE
from .utils import (
    build_date_range_filters,
    build_line_filters,
    ensure_date_bounds,
    find_column,
    list_table_columns,
    normalize_date_only,
    normalize_line_id,
    parse_json_body,
    resolve_table_schema,
    sanitize_identifier,
)

logger = logging.getLogger(__name__)

RECENT_HOURS_MIN = 0
RECENT_HOURS_DAY_STEP = 24
RECENT_HOURS_DAY_MODE_MIN_DAYS = 2
RECENT_HOURS_DAY_MODE_MAX_DAYS = 7
RECENT_HOURS_DAY_MODE_THRESHOLD = 24
RECENT_HOURS_MAX = RECENT_HOURS_DAY_MODE_MAX_DAYS * RECENT_HOURS_DAY_STEP
RECENT_HOURS_DEFAULT_START = 8
RECENT_HOURS_DEFAULT_END = 0
RECENT_FUTURE_TOLERANCE_MINUTES = 5


def _snap_recent_hours(value: int) -> int:
    clamped = max(RECENT_HOURS_MIN, min(value, RECENT_HOURS_MAX))
    if clamped <= RECENT_HOURS_DAY_MODE_THRESHOLD:
        return clamped

    days = (clamped + RECENT_HOURS_DAY_STEP - 1) // RECENT_HOURS_DAY_STEP
    bounded_days = max(
        RECENT_HOURS_DAY_MODE_MIN_DAYS,
        min(days, RECENT_HOURS_DAY_MODE_MAX_DAYS),
    )
    return bounded_days * RECENT_HOURS_DAY_STEP


def _clamp_recent_hours(value: Any, fallback: int) -> int:
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        numeric = fallback
    return _snap_recent_hours(numeric)


def _resolve_recent_hours_range(params) -> Tuple[int, int]:
    start = _clamp_recent_hours(params.get("recentHoursStart"), RECENT_HOURS_DEFAULT_START)
    end = _clamp_recent_hours(params.get("recentHoursEnd"), RECENT_HOURS_DEFAULT_END)
    if start < end:
        start = end
    return start, end


class TablesView(APIView):
    """임의 테이블을 조회하여 리스트 형태로 반환."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        params = request.GET

        from_param = normalize_date_only(params.get("from"))
        to_param = normalize_date_only(params.get("to"))
        normalized_line_id = normalize_line_id(params.get("lineId"))
        recent_hours_start, recent_hours_end = _resolve_recent_hours_range(params)

        if from_param and to_param:
            from_param, to_param = ensure_date_bounds(from_param, to_param)

        try:
            schema = resolve_table_schema(
                params.get("table"),
                default_table=DEFAULT_TABLE,
                require_timestamp=True,
            )
            table_name = schema.name
            column_names = schema.columns
            base_ts_col = schema.timestamp_column

            line_filter_result = build_line_filters(column_names, normalized_line_id)
            where_parts = list(line_filter_result["filters"])
            query_params = list(line_filter_result["params"])

            now_utc = datetime.utcnow()
            recent_start_dt = now_utc - timedelta(hours=recent_hours_start)
            recent_end_dt = now_utc - timedelta(hours=recent_hours_end)
            recent_end_dt += timedelta(minutes=RECENT_FUTURE_TOLERANCE_MINUTES)

            where_parts.append(f"{base_ts_col} BETWEEN %s AND %s")
            query_params.append(recent_start_dt.strftime("%Y-%m-%d %H:%M:%S"))
            query_params.append(recent_end_dt.strftime("%Y-%m-%d %H:%M:%S"))

            date_conditions, date_params = build_date_range_filters(base_ts_col, from_param, to_param)
            where_parts.extend(date_conditions)
            query_params.extend(date_params)

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
                "cutoff": (
                    "{col} BETWEEN NOW() - INTERVAL '{start} hours' AND NOW() - INTERVAL '{end} hours'"
                ).format(col=base_ts_col, start=recent_hours_start, end=recent_hours_end),
                "from": from_param or None,
                "to": to_param or None,
                "rowCount": len(rows),
                "columns": column_names,
                "rows": rows,
            }
            return JsonResponse(response_payload)
        except (ValueError, LookupError) as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except Exception as exc:  # pragma: no cover - 방어적 로깅
            error_code = getattr(exc, "code", None) or getattr(exc, "pgcode", None)
            if error_code in {"ER_NO_SUCH_TABLE", "42P01"}:
                return JsonResponse({"error": f'Table "{table_name}" was not found'}, status=404)
            logger.exception("Failed to load table data")
            return JsonResponse({"error": "Failed to load table data"}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class TableUpdateView(APIView):
    """임의 테이블의 일부분을 PATCH로 갱신."""

    ALLOWED_UPDATE_COLUMNS = {"comment", "needtosend", "instant_inform", "status"}

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

            set_activity_summary(
                request, f"Update {table_name} record #{record_id}"
            )
            merge_activity_metadata(
                request,
                resource=table_name,
                entryId=record_id,
            )

            previous_rows = run_query(
                """
                SELECT *
                FROM {table}
                WHERE {id_column} = %s
                LIMIT 1
                """.format(table=table_name, id_column=id_column),
                [record_id],
            )
            set_activity_previous_state(
                request,
                previous_rows[0] if previous_rows else None,
            )

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

            updated_rows = run_query(
                """
                SELECT *
                FROM {table}
                WHERE {id_column} = %s
                LIMIT 1
                """.format(table=table_name, id_column=id_column),
                [record_id],
            )
            if updated_rows:
                set_activity_new_state(request, updated_rows[0])

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
            return TableUpdateView._coerce_smallint_flag(value)
        if key == "instant_inform":
            return TableUpdateView._coerce_smallint_flag(value)
        if key == "status":
            return "" if value is None else str(value)
        return value

    @staticmethod
    def _coerce_smallint_flag(value: Any) -> int:
        """다양한 입력을 tinyint 스타일(0~127) 정수로 변환."""

        TINY_MIN, TINY_MAX = 0, 127

        def clamp(numeric: int) -> int:
            return max(TINY_MIN, min(TINY_MAX, int(numeric)))

        if isinstance(value, bool):
            return 1 if value else 0
        if value is None:
            return 0
        if isinstance(value, (int, float)):
            return clamp(value)
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "t", "y", "yes"}:
                return 1
            if normalized in {"0", "false", "f", "n", "no", ""}:
                return 0
            try:
                parsed = int(float(normalized))
                return clamp(parsed)
            except (TypeError, ValueError):
                return 0
        try:
            coerced = int(value)
            return clamp(coerced)
        except (TypeError, ValueError):
            return 0


__all__ = ["TableUpdateView", "TablesView"]
