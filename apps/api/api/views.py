from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence

import os

from django.conf import settings
from django.contrib.auth import get_user_model, login, logout
from django.http import HttpRequest, HttpResponseRedirect, JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from .db import execute, run_query
from .models import ActivityLog, ensure_user_profile

logger = logging.getLogger(__name__)

SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9_]+$")
DATE_ONLY_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATE_COLUMN_CANDIDATES = ["created_at", "updated_at", "timestamp", "ts", "date"]
DEFAULT_TABLE = "drone_sop_v3"
LINE_SDWT_TABLE_NAME = "line_sdwt"
DIMENSION_CANDIDATES = [
    "sdwt",
    "user_sdwt",
    "eqp_id",
    "main_step",
    "sample_type",
    "line_id",
]
MAX_FIELD_LENGTH = 50


class HealthView(View):
    """Simple health probe returning application metadata."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        return JsonResponse(
            {
                "status": "ok",
                "application": "template2-api",
            }
        )


class AuthConfigurationView(View):
    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        return JsonResponse(
            {
                "devLoginEnabled": settings.DEBUG and not settings.OIDC_RP_CLIENT_ID,
                "loginUrl": settings.LOGIN_URL,
                "frontendRedirect": settings.FRONTEND_BASE_URL,
            }
        )


class FrontendRedirectView(View):
    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> HttpResponseRedirect:
        base = settings.FRONTEND_BASE_URL.rstrip("/") if settings.FRONTEND_BASE_URL else "http://localhost:3000"
        if not base:
            base = "http://localhost:3000"
        next_path = request.GET.get("next")
        if isinstance(next_path, str) and next_path.strip():
            normalized = next_path.strip().lstrip("/")
            if normalized:
                return HttpResponseRedirect(f"{base}/{normalized}")
        return HttpResponseRedirect(base)


class CurrentUserView(View):
    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)
        user = request.user
        profile = getattr(user, "profile", None)
        role = profile.role if profile else "viewer"
        permissions = {
            "is_staff": user.is_staff,
            "is_superuser": user.is_superuser,
            "role": role,
            "canViewActivity": user.has_perm("api.view_activitylog"),
        }

        return JsonResponse(
            {
                "id": user.pk,
                "username": user.get_username(),
                "name": user.get_full_name() or user.get_username(),
                "email": user.email,
                "permissions": permissions,
            }
        )


class LogoutView(View):
    @method_decorator(csrf_exempt)
    def dispatch(self, *args: object, **kwargs: object):
        return super().dispatch(*args, **kwargs)

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        if request.user.is_authenticated:
            logout(request)
        response = JsonResponse({"status": "ok"})
        response.delete_cookie(settings.SESSION_COOKIE_NAME)
        return response


class DevelopmentLoginView(View):
    http_method_names = ["post"]

    @method_decorator(csrf_exempt)
    def dispatch(self, *args: object, **kwargs: object):
        return super().dispatch(*args, **kwargs)

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        if not settings.DEBUG or settings.OIDC_RP_CLIENT_ID:
            return JsonResponse({"error": "Development login disabled"}, status=404)

        data = _parse_json_body(request) or {}
        email = data.get("email") or os.environ.get("AUTH_DUMMY_EMAIL", "demo@example.com")
        if not isinstance(email, str) or "@" not in email:
            email = "demo@example.com"
        name = data.get("name") or os.environ.get("AUTH_DUMMY_NAME", "Demo User")
        if not isinstance(name, str) or not name.strip():
            name = "Demo User"
        role = data.get("role") or "viewer"

        User = get_user_model()
        username = email.split("@")[0] if isinstance(email, str) and "@" in email else (email or "dev-user")

        user, created = User.objects.get_or_create(
            email=email,
            defaults={"username": username, "first_name": name},
        )
        if created:
            user.set_unusable_password()
            user.save()
        else:
            if user.first_name != name:
                user.first_name = name
                user.last_name = ""
                user.save(update_fields=["first_name", "last_name"])

        profile = ensure_user_profile(user)
        if role in dict(profile.Roles.choices):
            profile.role = role
            profile.save(update_fields=["role"])

        login(request, user)

        return JsonResponse(
            {
                "status": "ok",
                "user": {
                    "id": user.pk,
                    "username": user.get_username(),
                    "name": user.get_full_name() or name,
                    "email": user.email,
                    "role": profile.role,
                },
            }
        )


class ActivityLogView(View):
    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)
        if not request.user.has_perm("api.view_activitylog"):
            return JsonResponse({"error": "Forbidden"}, status=403)

        limit = _to_int(request.GET.get("limit")) or 50
        limit = max(1, min(limit, 200))

        logs = (
            ActivityLog.objects.select_related("user", "user__profile")
            .order_by("-created_at")
            [:limit]
        )

        payload = []
        for entry in logs:
            payload.append(
                {
                    "id": entry.id,
                    "user": entry.user.get_username() if entry.user else None,
                    "role": getattr(getattr(entry.user, "profile", None), "role", None) if entry.user else None,
                    "action": entry.action,
                    "path": entry.path,
                    "method": entry.method,
                    "status": entry.status_code,
                    "metadata": entry.metadata,
                    "timestamp": entry.created_at.isoformat(),
                }
            )

        return JsonResponse({"results": payload})


def sanitize_identifier(value: Any, fallback: Optional[str] = None) -> Optional[str]:
    if not isinstance(value, str):
        return fallback
    candidate = value.strip()
    return candidate if SAFE_IDENTIFIER.match(candidate) else fallback


def normalize_date_only(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    return candidate if DATE_ONLY_REGEX.match(candidate) else None


def find_column(column_names: Iterable[str], target: str) -> Optional[str]:
    target_lower = target.lower()
    for name in column_names:
        if isinstance(name, str) and name.lower() == target_lower:
            return name
    return None


def pick_base_timestamp_column(column_names: Sequence[str]) -> Optional[str]:
    for candidate in DATE_COLUMN_CANDIDATES:
        found = find_column(column_names, candidate)
        if found:
            return found
    return None


def _get_user_sdwt_prod_values(line_id: str) -> List[str]:
    rows = run_query(
        """
        SELECT DISTINCT user_sdwt_prod
        FROM `{table}`
        WHERE line_id = %s
          AND user_sdwt_prod IS NOT NULL
          AND user_sdwt_prod <> ''
        """.format(table=LINE_SDWT_TABLE_NAME),
        [line_id],
    )
    values: List[str] = []
    for row in rows:
        raw = row.get("user_sdwt_prod")
        if isinstance(raw, str):
            trimmed = raw.strip()
            if trimmed:
                values.append(trimmed)
    return values


def build_line_filters(column_names: Sequence[str], line_id: Optional[str]) -> Dict[str, Any]:
    filters: List[str] = []
    params: List[Any] = []

    if not line_id:
        return {"filters": filters, "params": params}

    usdwt_col = find_column(column_names, "user_sdwt_prod")
    if usdwt_col:
        values = _get_user_sdwt_prod_values(line_id)
        if values:
            placeholders = ", ".join(["%s"] * len(values))
            filters.append(f"`{usdwt_col}` IN ({placeholders})")
            params.extend(values)
            return {"filters": filters, "params": params}

    line_col = find_column(column_names, "line_id")
    if line_col:
        filters.append(f"`{line_col}` = %s")
        params.append(line_id)

    return {"filters": filters, "params": params}


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return 0


def _parse_json_body(request: HttpRequest) -> Optional[Dict[str, Any]]:
    try:
        body = request.body.decode("utf-8")
    except UnicodeDecodeError:
        return None
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return data


class TablesView(View):
    """Expose table data queries handled previously by the Next.js API routes."""

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
            column_rows = run_query(f"SHOW COLUMNS FROM `{table_name}`")
            column_names = [row.get("Field") for row in column_rows if isinstance(row.get("Field"), str)]

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
                f"`{base_ts_col}` >= (CONVERT_TZ(UTC_TIMESTAMP(), 'UTC', '+09:00') - INTERVAL 36 HOUR)"
            )

            if from_param:
                where_parts.append(f"`{base_ts_col}` >= %s")
                query_params.append(f"{from_param} 00:00:00")

            if to_param:
                where_parts.append(f"`{base_ts_col}` <= %s")
                query_params.append(f"{to_param} 23:59:59")

            where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
            order_clause = f"ORDER BY `{base_ts_col}` DESC, `id` DESC"

            rows = run_query(
                """
                SELECT *
                FROM `{table}`
                {where_clause}
                {order_clause}
                """.format(table=table_name, where_clause=where_clause, order_clause=order_clause),
                query_params,
            )

            response_payload = {
                "table": table_name,
                "cutoff": "`{}` >= CONVERT_TZ(UTC_TIMESTAMP(),'UTC','+09:00') - INTERVAL 36 HOUR".format(base_ts_col),
                "from": from_param or None,
                "to": to_param or None,
                "rowCount": len(rows),
                "columns": column_names,
                "rows": rows,
            }
            return JsonResponse(response_payload)
        except Exception as exc:  # pragma: no cover - defensive logging
            if getattr(exc, "code", None) == "ER_NO_SUCH_TABLE":
                return JsonResponse({"error": f'Table "{table_name}" was not found'}, status=404)
            logger.exception("Failed to load table data")
            return JsonResponse({"error": "Failed to load table data"}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class TableUpdateView(View):
    """Handle partial updates to arbitrary tables."""

    ALLOWED_UPDATE_COLUMNS = {"comment", "needtosend"}

    def patch(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        payload = _parse_json_body(request)
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
            column_rows = run_query(f"SHOW COLUMNS FROM `{table_name}`")
            column_names = [row.get("Field") for row in column_rows if isinstance(row.get("Field"), str)]

            id_column = find_column(column_names, "id")
            if not id_column:
                return JsonResponse({"error": f'Table "{table_name}" does not expose an id column'}, status=400)

            assignments: List[str] = []
            params: List[Any] = []

            for key, value in filtered:
                column_name = find_column(column_names, key)
                if not column_name:
                    continue
                assignments.append(f"`{column_name}` = %s")
                params.append(self._normalize_update_value(key, value))

            if not assignments:
                return JsonResponse({"error": "No matching columns to update"}, status=400)

            params.append(record_id)
            sql = (
                """
                UPDATE `{table}`
                SET {assignments}
                WHERE `{id_column}` = %s
                LIMIT 1
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
        except Exception as exc:  # pragma: no cover - defensive logging
            if getattr(exc, "code", None) == "ER_NO_SUCH_TABLE":
                return JsonResponse({"error": f'Table "{table_name}" was not found'}, status=404)
            logger.exception("Failed to update table record")
            return JsonResponse({"error": "Failed to update record"}, status=500)

    @staticmethod
    def _normalize_update_value(key: str, value: Any) -> Any:
        if key == "comment":
            return "" if value is None else str(value)
        if key == "needtosend":
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                numeric = 0
            return 0 if numeric == 0 else 1
        return value


class LineHistoryView(View):
    """Aggregate historical counts for the dashboard charts."""

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
            column_rows = run_query(f"SHOW COLUMNS FROM `{table_name}`")
            column_names = [row.get("Field") for row in column_rows if isinstance(row.get("Field"), str)]

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
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Failed to load history data")
            return JsonResponse({"error": "Failed to load history data"}, status=500)

    def _resolve_date_range(
        self, from_param: Optional[str], to_param: Optional[str], range_param: Optional[str]
    ) -> tuple[Optional[str], Optional[str]]:
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
            conditions.append(f"`{timestamp_column}` >= %s")
            params.append(f"{from_value} 00:00:00")

        if to_value:
            conditions.append(f"`{timestamp_column}` <= %s")
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
        totals_select = [f"DATE(`{timestamp_column}`) AS day", "COUNT(*) AS row_count"]
        if send_jira_column:
            totals_select.append(
                "SUM(CASE WHEN `{col}` IS NOT NULL AND `{col}` <> 0 THEN 1 ELSE 0 END) AS send_jira_count".format(
                    col=send_jira_column
                )
            )
        else:
            totals_select.append("0 AS send_jira_count")

        return (
            """
            SELECT {select_clause}
            FROM `{table}`
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
            f"DATE(`{timestamp_column}`) AS day",
            f"COALESCE(CAST(`{dimension_column}` AS CHAR), 'Unspecified') AS category",
            "COUNT(*) AS row_count",
        ]

        if send_jira_column:
            select_parts.append(
                "SUM(CASE WHEN `{col}` IS NOT NULL AND `{col}` <> 0 THEN 1 ELSE 0 END) AS send_jira_count".format(
                    col=send_jira_column
                )
            )
        else:
            select_parts.append("0 AS send_jira_count")

        return (
            """
            SELECT {select_clause}
            FROM `{table}`
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
        date_str = str(date_value).strip() if isinstance(date_value, str) else None
        if not date_str and isinstance(date_value, datetime):
            date_str = date_value.date().isoformat()
        return {
            "date": date_str,
            "rowCount": _to_int(row.get("row_count", 0)),
            "sendJiraCount": _to_int(row.get("send_jira_count", 0)),
        }

    @staticmethod
    def _normalize_breakdown_row(row: Dict[str, Any]) -> Dict[str, Any]:
        date_value = row.get("day") or row.get("date")
        date_str = str(date_value).strip() if isinstance(date_value, str) else None
        if not date_str and isinstance(date_value, datetime):
            date_str = date_value.date().isoformat()
        category = row.get("category") or row.get("dimension") or "Unspecified"
        if not isinstance(category, str) or not category.strip():
            category = "Unspecified"
        return {
            "date": date_str,
            "category": category.strip() if isinstance(category, str) else str(category),
            "rowCount": _to_int(row.get("row_count", 0)),
            "sendJiraCount": _to_int(row.get("send_jira_count", 0)),
        }


class LineIdListView(View):
    """Return the list of available line identifiers for the sidebar filter."""

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
            line_ids = [row["line_id"].strip() for row in rows if isinstance(row.get("line_id"), str) and row.get("line_id").strip()]
            return JsonResponse({"lineIds": line_ids})
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Failed to load distinct line ids")
            return JsonResponse({"error": "Failed to load line options"}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class DroneEarlyInformView(View):
    """CRUD operations for the drone_early_inform_v3 table."""

    TABLE_NAME = "drone_early_inform_v3"

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        line_id = self._sanitize_line_id(request.GET.get("lineId"))
        if not line_id:
            return JsonResponse({"error": "lineId is required"}, status=400)

        try:
            rows = run_query(
                """
                SELECT id, line_id, main_step, custom_end_step
                FROM `{table}`
                WHERE line_id = %s
                ORDER BY main_step ASC, id ASC
                """.format(table=self.TABLE_NAME),
                [line_id],
            )
            normalized = [self._map_row(row, line_id) for row in rows]
            normalized_rows = [row for row in normalized if row is not None]
            return JsonResponse({
                "lineId": line_id,
                "rowCount": len(normalized_rows),
                "rows": normalized_rows,
            })
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Failed to load drone_early_inform rows")
            return JsonResponse({"error": "Failed to load settings"}, status=500)

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        line_id = self._sanitize_line_id(payload.get("lineId"))
        main_step = self._sanitize_main_step(payload.get("mainStep"))
        if not line_id:
            return JsonResponse({"error": "lineId is required"}, status=400)
        if not main_step:
            return JsonResponse({"error": "mainStep is required"}, status=400)

        try:
            custom_end_step = self._normalize_custom_end_step(payload.get("customEndStep"))
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)

        try:
            params = [line_id, main_step, custom_end_step]
            affected, last_row_id = execute(
                """
                INSERT INTO `{table}` (line_id, main_step, custom_end_step)
                VALUES (%s, %s, %s)
                """.format(table=self.TABLE_NAME),
                params,
            )
            entry = {
                "id": int(last_row_id or 0),
                "lineId": line_id,
                "mainStep": main_step,
                "customEndStep": custom_end_step,
            }
            return JsonResponse({"entry": entry}, status=201)
        except Exception as exc:  # pragma: no cover - defensive logging
            if getattr(exc, "code", None) == "ER_DUP_ENTRY":
                return JsonResponse({"error": "An entry for this main step already exists"}, status=409)
            logger.exception("Failed to insert drone_early_inform row")
            return JsonResponse({"error": "Failed to create entry"}, status=500)

    def patch(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        raw_id = payload.get("id")
        try:
            entry_id = int(raw_id)
        except (TypeError, ValueError):
            return JsonResponse({"error": "A valid id is required"}, status=400)
        if entry_id <= 0:
            return JsonResponse({"error": "A valid id is required"}, status=400)

        assignments: List[str] = []
        params: List[Any] = []

        if "mainStep" in payload:
            main_step = self._sanitize_main_step(payload.get("mainStep"))
            if not main_step:
                return JsonResponse({"error": "mainStep is required"}, status=400)
            assignments.append("`main_step` = %s")
            params.append(main_step)

        if "customEndStep" in payload:
            try:
                normalized = self._normalize_custom_end_step(payload.get("customEndStep"))
            except ValueError as exc:
                return JsonResponse({"error": str(exc)}, status=400)
            assignments.append("`custom_end_step` = %s")
            params.append(normalized)

        if not assignments:
            return JsonResponse({"error": "No valid fields to update"}, status=400)

        params.append(entry_id)
        try:
            affected, _ = execute(
                """
                UPDATE `{table}`
                SET {assignments}
                WHERE id = %s
                LIMIT 1
                """.format(table=self.TABLE_NAME, assignments=", ".join(assignments)),
                params,
            )
            if affected == 0:
                return JsonResponse({"error": "Entry not found"}, status=404)

            rows = run_query(
                """
                SELECT id, line_id, main_step, custom_end_step
                FROM `{table}`
                WHERE id = %s
                LIMIT 1
                """.format(table=self.TABLE_NAME),
                [entry_id],
            )
            entry = self._map_row(rows[0] if rows else None)
            if not entry:
                return JsonResponse({"error": "Entry not found"}, status=404)
            return JsonResponse({"entry": entry})
        except Exception as exc:  # pragma: no cover - defensive logging
            if getattr(exc, "code", None) == "ER_DUP_ENTRY":
                return JsonResponse({"error": "An entry for this main step already exists"}, status=409)
            logger.exception("Failed to update drone_early_inform row")
            return JsonResponse({"error": "Failed to update entry"}, status=500)

    def delete(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        raw_id = request.GET.get("id")
        try:
            entry_id = int(raw_id)
        except (TypeError, ValueError):
            return JsonResponse({"error": "A valid id is required"}, status=400)
        if entry_id <= 0:
            return JsonResponse({"error": "A valid id is required"}, status=400)

        try:
            affected, _ = execute(
                """
                DELETE FROM `{table}`
                WHERE id = %s
                LIMIT 1
                """.format(table=self.TABLE_NAME),
                [entry_id],
            )
            if affected == 0:
                return JsonResponse({"error": "Entry not found"}, status=404)
            return JsonResponse({"success": True})
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Failed to delete drone_early_inform row")
            return JsonResponse({"error": "Failed to delete entry"}, status=500)

    @staticmethod
    def _sanitize_line_id(value: Any) -> Optional[str]:
        if not isinstance(value, str):
            return None
        trimmed = value.strip()
        return trimmed if trimmed and len(trimmed) <= MAX_FIELD_LENGTH else None

    @staticmethod
    def _sanitize_main_step(value: Any) -> Optional[str]:
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
    def _map_row(row: Optional[Dict[str, Any]], fallback_line_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if not row:
            return None
        entry_id = row.get("id")
        if entry_id is None:
            return None
        line_id = row.get("line_id") or fallback_line_id
        main_step = row.get("main_step")
        custom_end_step = row.get("custom_end_step")
        return {
            "id": int(entry_id),
            "lineId": line_id if isinstance(line_id, str) else None,
            "mainStep": main_step if isinstance(main_step, str) else str(main_step) if main_step is not None else "",
            "customEndStep": custom_end_step if isinstance(custom_end_step, str) else None,
        }
