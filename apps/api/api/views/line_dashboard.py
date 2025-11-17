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
    find_column,
    list_table_columns,
    normalize_date_only,
    pick_base_timestamp_column,
    sanitize_identifier,
    to_int,
)

logger = logging.getLogger(__name__)


class LineHistoryView(APIView):
    """대시보드 차트용 일별 합계/분해 집계 제공."""

    DEFAULT_RANGE_DAYS = 14

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        params = request.GET

        table_name = sanitize_identifier(params.get("table"), DEFAULT_TABLE)
        if not table_name:
            return JsonResponse({"error": "Invalid table name"}, status=400)

        from_param = normalize_date_only(params.get("from"))
        to_param = normalize_date_only(params.get("to"))
        range_days = params.get("rangeDays")
        line_id_param = params.get("lineId")
        normalized_line_id = line_id_param.strip() if isinstance(line_id_param, str) and line_id_param.strip() else None

        from_value, to_value = self._resolve_date_range(from_param, to_param, range_days)

        try:
            column_names = list_table_columns(table_name)
            if not column_names:
                return JsonResponse({"error": f'Table "{table_name}" has no columns'}, status=400)

            timestamp_column = pick_base_timestamp_column(column_names)
            if not timestamp_column:
                return JsonResponse({"error": f'No timestamp-like column found in "{table_name}".'}, status=400)

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
            from_time = datetime.fromisoformat(f"{from_value}T00:00:00")
            to_time = datetime.fromisoformat(f"{to_value}T00:00:00")
            if from_time > to_time:
                from_value, to_value = to_value, from_value

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

        if from_value:
            conditions.append(f"{timestamp_column} >= %s")
            params.append(f"{from_value} 00:00:00")

        if to_value:
            conditions.append(f"{timestamp_column} <= %s")
            params.append(f"{to_value} 23:59:59")

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
                "SUM(CASE WHEN {col} IS TRUE THEN 1 ELSE 0 END) AS send_jira_count".format(
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
                "SUM(CASE WHEN {col} IS TRUE THEN 1 ELSE 0 END) AS send_jira_count".format(
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
        date_value = row.get("day") or row.get("date")
    
        date_str: Optional[str] = None
    
        # 1) 문자열인 경우: 그냥 strip
        if isinstance(date_value, str):
            date_str = date_value.strip() or None
    
        # 2) datetime인 경우: 날짜만 떼어서 YYYY-MM-DD
        elif isinstance(date_value, datetime):
            date_str = date_value.date().isoformat()
    
        # 3) date 인 경우: 그대로 isoformat()
        elif isinstance(date_value, date):
            date_str = date_value.isoformat()
    
        # (원한다면: else 에서 로그 찍을 수도 있음)
    
        return {
            "date": date_str,
            "rowCount": to_int(row.get("row_count", 0)),
            "sendJiraCount": to_int(row.get("send_jira_count", 0)),
        }
    
    @staticmethod
    def _normalize_breakdown_row(row: Dict[str, Any]) -> Dict[str, Any]:
        date_value = row.get("day") or row.get("date")
    
        date_str: Optional[str] = None
        if isinstance(date_value, str):
            date_str = date_value.strip() or None
        elif isinstance(date_value, datetime):
            date_str = date_value.date().isoformat()
        elif isinstance(date_value, date):
            date_str = date_value.isoformat()
    
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
