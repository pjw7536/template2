"""라인 대시보드 관련 뷰."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, date
from typing import Any, Dict, List, Optional, Sequence

from django.http import HttpRequest, JsonResponse
from rest_framework.views import APIView

from ..db import run_query
from .constants import (
    DEFAULT_TABLE,
    DIMENSION_CANDIDATES,
    LINE_SDWT_TABLE_NAME,
)
from .utils import (
    build_line_filters,
    build_date_range_filters,
    ensure_date_bounds,
    find_column,
    normalize_line_id,
    normalize_date_only,
    resolve_table_schema,
    to_int,
)

logger = logging.getLogger(__name__)


def _normalize_date_value(value: Any) -> Optional[str]:
    """날짜/문자/None 값을 YYYY-MM-DD 문자열 또는 None으로 정규화."""

    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return None


class LineHistoryView(APIView):
    """대시보드 차트용 일별 합계/분해 집계 제공."""

    DEFAULT_RANGE_DAYS = 14

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        params = request.GET

        from_param = normalize_date_only(params.get("from"))
        to_param = normalize_date_only(params.get("to"))
        range_days = params.get("rangeDays")
        normalized_line_id = normalize_line_id(params.get("lineId"))

        from_value, to_value = self._resolve_date_range(from_param, to_param, range_days)

        try:
            schema = resolve_table_schema(
                params.get("table"),
                default_table=DEFAULT_TABLE,
                require_timestamp=True,
            )
            table_name = schema.name
            column_names = schema.columns
            timestamp_column = schema.timestamp_column

            send_jira_column = find_column(column_names, "send_jira")
            dimension_columns = {
                candidate: resolved
                for candidate in DIMENSION_CANDIDATES
                if (resolved := find_column(column_names, candidate))
            }

            line_filter_result = build_line_filters(column_names, normalized_line_id)
            where_clause, query_params = self._build_where_clause(
                timestamp_column,
                line_filter_result["filters"],
                line_filter_result["params"],
                from_value,
                to_value,
            )

            totals_rows = run_query(
                self._build_totals_query(table_name, timestamp_column, send_jira_column, where_clause),
                query_params,
            )
            totals = [self._normalize_daily_row(row) for row in totals_rows]

            breakdowns: Dict[str, List[Dict[str, Any]]] = {}
            for dimension_key, column_name in dimension_columns.items():
                rows = run_query(
                    self._build_breakdown_query(table_name, timestamp_column, column_name, send_jira_column, where_clause),
                    query_params,
                )
                breakdowns[dimension_key] = [self._normalize_breakdown_row(row) for row in rows]

            return JsonResponse(
                {
                    "table": table_name,
                    "from": from_value,
                    "to": to_value,
                    "lineId": normalized_line_id,
                    "timestampColumn": timestamp_column,
                    "generatedAt": datetime.utcnow().isoformat() + "Z",
                    "totals": totals,
                    "breakdowns": breakdowns,
                }
            )
        except (ValueError, LookupError) as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except Exception:  # pragma: no cover - 방어적 로깅
            logger.exception("Failed to load history data")
            return JsonResponse({"error": "Failed to load history data"}, status=500)

    def _resolve_date_range(
        self, from_param: Optional[str], to_param: Optional[str], range_param: Optional[str]
    ) -> tuple[Optional[str], Optional[str]]:
        """from/to/rangeDays 조합을 최종 from/to(YYYY-MM-DD)로 정리."""

        from_value = from_param
        to_value = to_param

        parsed_range = None
        if isinstance(range_param, str) and range_param.isdigit():
            parsed_range = int(range_param)
        range_days = parsed_range if parsed_range and parsed_range > 0 else self.DEFAULT_RANGE_DAYS

        if not to_value:
            today = datetime.utcnow().date()
            to_value = today.isoformat()

        if not from_value and to_value:
            to_date = datetime.fromisoformat(f"{to_value}T00:00:00")
            from_date = to_date - timedelta(days=range_days - 1)
            from_value = from_date.date().isoformat()

        if from_value and to_value:
            from_value, to_value = ensure_date_bounds(from_value, to_value)

        return from_value, to_value

    def _build_where_clause(
        self,
        timestamp_column: str,
        line_filters: Sequence[str],
        line_params: Sequence[Any],
        from_value: Optional[str],
        to_value: Optional[str],
    ) -> tuple[str, List[Any]]:
        conditions = list(line_filters)
        params = list(line_params)

        date_conditions, date_params = build_date_range_filters(timestamp_column, from_value, to_value)
        conditions.extend(date_conditions)
        params.extend(date_params)

        clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        return clause, params

    def _build_totals_query(
        self,
        table_name: str,
        timestamp_column: str,
        send_jira_column: Optional[str],
        where_clause: str,
    ) -> str:
        totals_select = [f"DATE({timestamp_column}) AS day", "COUNT(*) AS row_count"]
        if send_jira_column:
            totals_select.append(
                "SUM(CASE WHEN {col} > 0 THEN 1 ELSE 0 END) AS send_jira_count".format(
                    col=send_jira_column
                )
            )
        else:
            totals_select.append("0 AS send_jira_count")

        return (
            """
            SELECT {select_clause}
            FROM {table}
            {where_clause}
            GROUP BY day
            ORDER BY day ASC
            """.format(
                select_clause=", ".join(totals_select),
                table=table_name,
                where_clause=where_clause,
            )
        )

    def _build_breakdown_query(
        self,
        table_name: str,
        timestamp_column: str,
        dimension_column: str,
        send_jira_column: Optional[str],
        where_clause: str,
    ) -> str:
        select_parts = [
            f"DATE({timestamp_column}) AS day",
            f"COALESCE(CAST({dimension_column} AS TEXT), 'Unspecified') AS category",
            "COUNT(*) AS row_count",
        ]

        if send_jira_column:
            select_parts.append(
                "SUM(CASE WHEN {col} > 0 THEN 1 ELSE 0 END) AS send_jira_count".format(
                    col=send_jira_column
                )
            )
        else:
            select_parts.append("0 AS send_jira_count")

        return (
            """
            SELECT {select_clause}
            FROM {table}
            {where_clause}
            GROUP BY day, category
            ORDER BY day ASC, category ASC
            """.format(
                select_clause=", ".join(select_parts),
                table=table_name,
                where_clause=where_clause,
            )
        )

    @staticmethod
    def _normalize_daily_row(row: Dict[str, Any]) -> Dict[str, Any]:
        date_str = _normalize_date_value(row.get("day") or row.get("date"))

        return {
            "date": date_str,
            "rowCount": to_int(row.get("row_count", 0)),
            "sendJiraCount": to_int(row.get("send_jira_count", 0)),
        }
    
    @staticmethod
    def _normalize_breakdown_row(row: Dict[str, Any]) -> Dict[str, Any]:
        date_str = _normalize_date_value(row.get("day") or row.get("date"))

        category = row.get("category") or row.get("dimension") or "Unspecified"
        if not isinstance(category, str) or not category.strip():
            category = "Unspecified"
    
        return {
            "date": date_str,
            "category": category.strip() if isinstance(category, str) else str(category),
            "rowCount": to_int(row.get("row_count", 0)),
            "sendJiraCount": to_int(row.get("send_jira_count", 0)),
        }
    
    

class LineIdListView(APIView):
    """사이드바 필터용 line_id 고유값 목록 반환."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        try:
            rows = run_query(
                """
                SELECT DISTINCT line_id
                FROM {table}
                WHERE line_id IS NOT NULL AND line_id <> ''
                ORDER BY line_id
                """.format(table=LINE_SDWT_TABLE_NAME)
            )
            line_ids = [
                row["line_id"].strip()
                for row in rows
                if isinstance(row.get("line_id"), str) and row.get("line_id").strip()
            ]
            return JsonResponse({"lineIds": line_ids})
        except Exception:  # pragma: no cover - 방어적 로깅
            logger.exception("Failed to load distinct line ids")
            return JsonResponse({"error": "Failed to load line options"}, status=500)


__all__ = ["LineHistoryView", "LineIdListView"]
