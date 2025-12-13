"""드론 조기 알림(Drone Early Inform) 설정 CRUD 뷰.

이 모듈은 drone_early_inform_v3 테이블을 직접 SQL로 조회/수정합니다.
요청 → 파라미터 정규화/검증 → DB쿼리 → 액티비티 로깅(이전/신규 상태) → JSON 응답
순서로 동작합니다.

# 엔드포인트 요약
- GET    /api/v1/drone/early-inform?lineId=L1
- POST   /api/v1/drone/early-inform { lineId, mainStep, customEndStep? }
- PATCH  /api/v1/drone/early-inform { id, lineId?, mainStep?, customEndStep? }
- DELETE /api/v1/drone/early-inform?id=123

# 응답(예시)
GET:
{
  "lineId": "L1",
  "rowCount": 2,
  "rows": [
    { "id": 1, "lineId": "L1", "mainStep": "ETCH", "customEndStep": "ETCH-9" },
    { "id": 2, "lineId": "L1", "mainStep": "PR",   "customEndStep": null }
  ]
}

POST/PATCH:
{ "entry": { "id": 3, "lineId": "L1", "mainStep": "CMP", "customEndStep": null } }

DELETE:
{ "success": true }

# 유의사항
- CSRF 예외(@csrf_exempt)를 적용했으므로, 외부 호출 노출 시 토큰/인증 등 별도 방어가 필수입니다.
- 값 길이 제한은 MAX_FIELD_LENGTH(예: 50) 기준으로 검증합니다.
- 중복키(ER_DUP_ENTRY/MySQL, 23505/PostgreSQL)는 409 Conflict로 응답합니다.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence

from django.http import HttpRequest, JsonResponse
from django.db import IntegrityError
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from api.common.constants import DEFAULT_TABLE, DIMENSION_CANDIDATES, LINE_SDWT_TABLE_NAME, MAX_FIELD_LENGTH
from api.common.utils import (
    _get_user_sdwt_prod_values,
    build_date_range_filters,
    build_line_filters,
    ensure_date_bounds,
    find_column,
    normalize_date_only,
    normalize_line_id,
    parse_json_body,
    resolve_table_schema,
    to_int,
)

from api.common.activity_logging import (
    merge_activity_metadata,
    set_activity_new_state,
    set_activity_previous_state,
    set_activity_summary,
)
from api.common.db import execute, run_query

logger = logging.getLogger(__name__)


def _is_duplicate_error(exc: Exception) -> bool:
    """DB 중복 에러 여부를 광범위하게 판별."""

    error_code = getattr(exc, "code", None) or getattr(exc, "pgcode", None)
    if error_code:
        code_str = str(error_code)
        if code_str in {"ER_DUP_ENTRY", "23505", "1062"}:
            return True

    if isinstance(exc, IntegrityError):
        message = str(exc).lower()
        if any(key in message for key in ("duplicate", "unique", "uniq", "already exists")):
            return True

    # 일반 Exception의 문자열 메시지에서만 duplicate 힌트가 있는 경우
    message = str(exc).lower()
    return any(key in message for key in ("duplicate", "unique", "uniq", "already exists"))


@method_decorator(csrf_exempt, name="dispatch")
class DroneEarlyInformView(APIView):
    """drone_early_inform_v3 테이블에 대한 CRUD.

    - GET: lineId로 행 목록 조회(최신 정렬 기준: main_step ASC, id ASC)
    - POST: 신규 행 추가(중복 main_step 방지 가정)
    - PATCH: 부분 업데이트(id 필수)
    - DELETE: 행 삭제(id 쿼리 파라미터)
    """

    # 한 곳에서만 테이블명을 관리해 실수 방지
    TABLE_NAME = "drone_early_inform_v3"

    # --------------------------------------------------------------------- #
    # READ
    # --------------------------------------------------------------------- #
    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """lineId로 행 목록을 가져옵니다."""
        line_id = self._sanitize_line_id(request.GET.get("lineId"))
        if not line_id:
            return JsonResponse({"error": "lineId is required"}, status=400)

        try:
            rows = run_query(
                """
                SELECT id, line_id, main_step, custom_end_step, updated_by, updated_at
                FROM {table}
                WHERE line_id = %s
                ORDER BY main_step ASC, id ASC
                """.format(table=self.TABLE_NAME),
                [line_id],
            )
            # DB 레코드를 API 응답 형태로 정규화
            normalized = [self._map_row(row, line_id) for row in rows]
            normalized_rows = [row for row in normalized if row is not None]
            user_sdwt_values = _get_user_sdwt_prod_values(line_id)
            return JsonResponse({
                "lineId": line_id,
                "rowCount": len(normalized_rows),
                "rows": normalized_rows,
                "userSdwt": user_sdwt_values,
            })
        except Exception:  # pragma: no cover - 방어적 로깅
            logger.exception("Failed to load drone_early_inform rows")
            return JsonResponse({"error": "Failed to load settings"}, status=500)

    # --------------------------------------------------------------------- #
    # CREATE
    # --------------------------------------------------------------------- #
    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """신규 행을 생성합니다."""
        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        # 필수 필드 검증
        line_id = self._sanitize_line_id(payload.get("lineId"))
        main_step = self._sanitize_main_step(payload.get("mainStep"))
        if not line_id:
            return JsonResponse({"error": "lineId is required"}, status=400)
        if not main_step:
            return JsonResponse({"error": "mainStep is required"}, status=400)

        # 선택 필드 정규화(빈 문자열 → None / 길이 제한 검사)
        try:
            custom_end_step = self._normalize_custom_end_step(payload.get("customEndStep"))
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)

        updated_by = self._resolve_updated_by(request)

        try:
            params = [line_id, main_step, custom_end_step, updated_by]
            affected, last_row_id = execute(
                """
                INSERT INTO {table} (line_id, main_step, custom_end_step, updated_by, updated_at)
                VALUES (%s, %s, %s, %s, NOW())
                RETURNING id
                """.format(table=self.TABLE_NAME),
                params,
            )
            rows = run_query(
                """
                SELECT id, line_id, main_step, custom_end_step, updated_by, updated_at
                FROM {table}
                WHERE id = %s
                LIMIT 1
                """.format(table=self.TABLE_NAME),
                [last_row_id],
            )
            entry = self._map_row(rows[0] if rows else None, line_id)
            if not entry:
                return JsonResponse({"error": "Failed to create entry"}, status=500)

            # 액티비티 로그(요약 + 신규 상태 + 메타데이터)
            set_activity_summary(request, "Create drone_early_inform entry")
            set_activity_new_state(request, entry)
            merge_activity_metadata(
                request,
                resource=self.TABLE_NAME,
                entryId=entry["id"],
            )
            return JsonResponse({"entry": entry}, status=201)

        except Exception as exc:  # pragma: no cover - 방어적 로깅
            # MySQL/PG의 유니크 제약 위반 코드 매핑
            if _is_duplicate_error(exc):
                return JsonResponse({"error": "An entry for this main step already exists"}, status=409)
            logger.exception("Failed to create drone_early_inform row")
            return JsonResponse({"error": "Failed to create entry"}, status=500)

    # --------------------------------------------------------------------- #
    # UPDATE (partial)
    # --------------------------------------------------------------------- #
    def patch(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """id로 지정된 행을 부분 업데이트합니다."""
        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        # id 정수 검증
        entry_id = payload.get("id")
        if not isinstance(entry_id, int):
            try:
                entry_id = int(entry_id)
            except (TypeError, ValueError):
                return JsonResponse({"error": "A valid id is required"}, status=400)
        if entry_id <= 0:
            return JsonResponse({"error": "A valid id is required"}, status=400)

        # 액티비티 로그(요약/리소스 메타)
        set_activity_summary(request, f"Update drone_early_inform entry #{entry_id}")
        merge_activity_metadata(request, resource=self.TABLE_NAME, entryId=entry_id)

        # 이전 상태 로드 → 액티비티에 보관
        previous_rows = run_query(
            """
            SELECT id, line_id, main_step, custom_end_step, updated_by, updated_at
            FROM {table}
            WHERE id = %s
            LIMIT 1
            """.format(table=self.TABLE_NAME),
            [entry_id],
        )
        set_activity_previous_state(
            request,
            self._map_row(previous_rows[0] if previous_rows else None),
        )

        # 동적 UPDATE 컬럼 구성
        assignments: List[str] = []
        params: List[Any] = []

        updated_by = self._resolve_updated_by(request)

        if "lineId" in payload:
            line_id = self._sanitize_line_id(payload.get("lineId"))
            if not line_id:
                return JsonResponse({"error": "lineId is required"}, status=400)
            assignments.append("line_id = %s")
            params.append(line_id)

        if "mainStep" in payload:
            main_step = self._sanitize_main_step(payload.get("mainStep"))
            if not main_step:
                return JsonResponse({"error": "mainStep is required"}, status=400)
            assignments.append("main_step = %s")
            params.append(main_step)

        if "customEndStep" in payload:
            try:
                normalized = self._normalize_custom_end_step(payload.get("customEndStep"))
            except ValueError as exc:
                return JsonResponse({"error": str(exc)}, status=400)
            assignments.append("custom_end_step = %s")
            params.append(normalized)

        if not assignments:
            return JsonResponse({"error": "No valid fields to update"}, status=400)

        # 항상 업데이트 메타 컬럼 갱신
        assignments.append("updated_by = %s")
        params.append(updated_by)
        assignments.append("updated_at = NOW()")

        # WHERE id = %s
        params.append(entry_id)
        try:
            affected, _ = execute(
                """
                UPDATE {table}
                SET {assignments}
                WHERE id = %s
                """.format(table=self.TABLE_NAME, assignments=", ".join(assignments)),
                params,
            )
            if affected == 0:
                return JsonResponse({"error": "Entry not found"}, status=404)

            # 변경 후 행 다시 조회 → 응답/로그에 사용
            rows = run_query(
                """
                SELECT id, line_id, main_step, custom_end_step, updated_by, updated_at
                FROM {table}
                WHERE id = %s
                LIMIT 1
                """.format(table=self.TABLE_NAME),
                [entry_id],
            )
            entry = self._map_row(rows[0] if rows else None)
            if not entry:
                return JsonResponse({"error": "Entry not found"}, status=404)

            set_activity_new_state(request, entry)
            return JsonResponse({"entry": entry})

        except Exception as exc:  # pragma: no cover - 방어적 로깅
            if _is_duplicate_error(exc):
                return JsonResponse({"error": "An entry for this main step already exists"}, status=409)
            logger.exception("Failed to update drone_early_inform row")
            return JsonResponse({"error": "Failed to update entry"}, status=500)

    # --------------------------------------------------------------------- #
    # DELETE
    # --------------------------------------------------------------------- #
    def delete(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """id로 지정된 행을 삭제합니다."""
        raw_id = request.GET.get("id")
        try:
            entry_id = int(raw_id)
        except (TypeError, ValueError):
            return JsonResponse({"error": "A valid id is required"}, status=400)
        if entry_id <= 0:
            return JsonResponse({"error": "A valid id is required"}, status=400)

        # 액티비티 로그 요약/메타 + 이전 상태 보관
        set_activity_summary(request, f"Delete drone_early_inform entry #{entry_id}")
        merge_activity_metadata(request, resource=self.TABLE_NAME, entryId=entry_id)

        previous_rows = run_query(
            """
            SELECT id, line_id, main_step, custom_end_step
            FROM {table}
            WHERE id = %s
            LIMIT 1
            """.format(table=self.TABLE_NAME),
            [entry_id],
        )
        set_activity_previous_state(
            request,
            self._map_row(previous_rows[0] if previous_rows else None),
        )

        try:
            affected, _ = execute(
                """
                DELETE FROM {table}
                WHERE id = %s
                """.format(table=self.TABLE_NAME),
                [entry_id],
            )
            if affected == 0:
                return JsonResponse({"error": "Entry not found"}, status=404)

            # 삭제 성공도 신규 상태로 간단히 표기
            set_activity_new_state(request, {"deleted": True})
            return JsonResponse({"success": True})

        except Exception:  # pragma: no cover - 방어적 로깅
            logger.exception("Failed to delete drone_early_inform row")
            return JsonResponse({"error": "Failed to delete entry"}, status=500)

    # --------------------------------------------------------------------- #
    # 밸리데이션/정규화/매퍼 유틸
    # --------------------------------------------------------------------- #
    @staticmethod
    def _sanitize_line_id(value: Any) -> Optional[str]:
        """lineId: 문자열 & 공백 제거 & 길이 제한."""
        if not isinstance(value, str):
            return None
        trimmed = value.strip()
        return trimmed if trimmed and len(trimmed) <= MAX_FIELD_LENGTH else None

    @staticmethod
    def _sanitize_main_step(value: Any) -> Optional[str]:
        """mainStep: None/빈값 불가, 문자열화 후 공백 제거 & 길이 제한."""
        if isinstance(value, str):
            trimmed = value.strip()
        elif value is None:
            trimmed = ""
        else:
            trimmed = str(value).strip()
        if not trimmed:
            return None
        return trimmed if len(trimmed) <= MAX_FIELD_LENGTH else None

    @staticmethod
    def _normalize_custom_end_step(value: Any) -> Optional[str]:
        """customEndStep: 빈 문자열은 None 처리, 길이 제한 초과 시 ValueError."""
        if value is None:
            return None
        if isinstance(value, str):
            trimmed = value.strip()
        else:
            trimmed = str(value).strip()
        if not trimmed:
            return None
        if len(trimmed) > MAX_FIELD_LENGTH:
            raise ValueError("customEndStep must be 50 characters or fewer")
        return trimmed

    @staticmethod
    def _sanitize_updated_by(value: Any) -> Optional[str]:
        """updated_by: 문자열 공백 제거 & 길이 제한."""
        if not isinstance(value, str):
            return None
        trimmed = value.strip()
        return trimmed if trimmed and len(trimmed) <= MAX_FIELD_LENGTH else None

    @staticmethod
    def _extract_username(raw_username: str) -> str:
        """이메일인 경우 @ 앞 로컬 파트만 추출."""
        if "@" in raw_username:
            local_part = raw_username.split("@", 1)[0]
            return local_part or raw_username
        return raw_username

    def _resolve_updated_by(self, request: HttpRequest) -> Optional[str]:
        """요청 사용자 정보를 updated_by 문자열로 정리."""
        user = getattr(request, "user", None)
        raw_username = None
        if user and getattr(user, "is_authenticated", False):
            raw_username = (
                getattr(user, "get_username", lambda: None)() or getattr(user, "email", None) or None
            )
        if not raw_username:
            raw_username = "system"
        username = self._extract_username(str(raw_username))
        return self._sanitize_updated_by(username)

    @staticmethod
    def _map_row(row: Optional[Dict[str, Any]], fallback_line_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """DB 행(dict)을 API 응답 형식으로 매핑.

        - id: int로 강제
        - lineId: str 또는 None (fallback_line_id로 보완)
        - mainStep: str (값이 숫자일 수도 있어 안전 문자열화)
        - customEndStep: str 또는 None
        - updatedBy: str 또는 None
        - updatedAt: ISO 문자열 또는 None
        """
        if not row:
            return None
        entry_id = row.get("id")
        if entry_id is None:
            return None

        line_id = row.get("line_id") or fallback_line_id
        main_step = row.get("main_step")
        custom_end_step = row.get("custom_end_step")
        updated_by = row.get("updated_by")
        updated_at = row.get("updated_at")

        return {
            "id": int(entry_id),
            "lineId": line_id if isinstance(line_id, str) else None,
            "mainStep": (
                main_step if isinstance(main_step, str)
                else str(main_step) if main_step is not None
                else ""
            ),
            "customEndStep": custom_end_step if isinstance(custom_end_step, str) else None,
            "updatedBy": updated_by if isinstance(updated_by, str) else None,
            "updatedAt": (
                updated_at.isoformat()
                if hasattr(updated_at, "isoformat")
                else str(updated_at)
                if updated_at is not None
                else None
            ),
        }


def _normalize_bucket_value(value: Any) -> Optional[str]:
    """
    날짜/시간 버킷 값을 ISO-like 문자열로 정규화합니다.

    - 문자열: 공백을 T로 치환해 Date 파서 친화적으로 정규화
    - datetime/date: 시/분/초를 0으로 맞춰 문자열 변환
    - 실패 시 원본 문자열을 그대로 반환
    """

    if value is None:
        return None

    if isinstance(value, datetime):
        return value.replace(minute=0, second=0, microsecond=0).isoformat()

    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time()).isoformat()

    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None

        candidate = cleaned
        if " " in candidate and "T" not in candidate:
            candidate = candidate.replace(" ", "T")

        try:
            parsed = datetime.fromisoformat(candidate)
            return parsed.replace(minute=0, second=0, microsecond=0).isoformat()
        except ValueError:
            return cleaned

    return None


class LineHistoryView(APIView):
    """라인 대시보드 차트용 시간 단위 합계/분해 집계 제공."""

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
                    self._build_breakdown_query(
                        table_name,
                        timestamp_column,
                        column_name,
                        send_jira_column,
                        where_clause,
                    ),
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
        self,
        from_param: Optional[str],
        to_param: Optional[str],
        range_param: Optional[str],
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
        bucket_expr = f"DATE_TRUNC('hour', {timestamp_column})"
        totals_select = [f"{bucket_expr} AS bucket", "COUNT(*) AS row_count"]
        if send_jira_column:
            totals_select.append(
                "SUM(CASE WHEN {col} > 0 THEN 1 ELSE 0 END) AS send_jira_count".format(col=send_jira_column)
            )
        else:
            totals_select.append("0 AS send_jira_count")

        return (
            """
            SELECT {select_clause}
            FROM {table}
            {where_clause}
            GROUP BY bucket
            ORDER BY bucket ASC
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
        bucket_expr = f"DATE_TRUNC('hour', {timestamp_column})"
        select_parts = [
            f"{bucket_expr} AS bucket",
            f"COALESCE(CAST({dimension_column} AS TEXT), 'Unspecified') AS category",
            "COUNT(*) AS row_count",
        ]

        if send_jira_column:
            select_parts.append(
                "SUM(CASE WHEN {col} > 0 THEN 1 ELSE 0 END) AS send_jira_count".format(col=send_jira_column)
            )
        else:
            select_parts.append("0 AS send_jira_count")

        return (
            """
            SELECT {select_clause}
            FROM {table}
            {where_clause}
            GROUP BY bucket, category
            ORDER BY bucket ASC, category ASC
            """.format(
                select_clause=", ".join(select_parts),
                table=table_name,
                where_clause=where_clause,
            )
        )

    @staticmethod
    def _normalize_daily_row(row: Dict[str, Any]) -> Dict[str, Any]:
        date_str = _normalize_bucket_value(row.get("bucket") or row.get("day") or row.get("date"))

        return {
            "date": date_str,
            "rowCount": to_int(row.get("row_count", 0)),
            "sendJiraCount": to_int(row.get("send_jira_count", 0)),
        }

    @staticmethod
    def _normalize_breakdown_row(row: Dict[str, Any]) -> Dict[str, Any]:
        date_str = _normalize_bucket_value(row.get("bucket") or row.get("day") or row.get("date"))

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


__all__ = [
    "DroneEarlyInformView",
    "LineHistoryView",
    "LineIdListView",
]
