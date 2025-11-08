"""드론 조기 알림 설정 CRUD 뷰."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from ..db import execute, run_query
from .constants import MAX_FIELD_LENGTH
from .utils import parse_json_body

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class DroneEarlyInformView(APIView):
    """drone_early_inform_v3 테이블에 대한 CRUD."""

    TABLE_NAME = "drone_early_inform_v3"

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        line_id = self._sanitize_line_id(request.GET.get("lineId"))
        if not line_id:
            return JsonResponse({"error": "lineId is required"}, status=400)

        try:
            rows = run_query(
                """
                SELECT id, line_id, main_step, custom_end_step
                FROM {table}
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
        except Exception:  # pragma: no cover - 방어적 로깅
            logger.exception("Failed to load drone_early_inform rows")
            return JsonResponse({"error": "Failed to load settings"}, status=500)

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        payload = parse_json_body(request)
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
                INSERT INTO {table} (line_id, main_step, custom_end_step)
                VALUES (%s, %s, %s)
                RETURNING id
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
        except Exception as exc:  # pragma: no cover - 방어적 로깅
            error_code = getattr(exc, "code", None) or getattr(exc, "pgcode", None)
            if error_code in {"ER_DUP_ENTRY", "23505"}:
                return JsonResponse({"error": "An entry for this main step already exists"}, status=409)
            logger.exception("Failed to create drone_early_inform row")
            return JsonResponse({"error": "Failed to create entry"}, status=500)

    def patch(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        entry_id = payload.get("id")
        if not isinstance(entry_id, int):
            try:
                entry_id = int(entry_id)
            except (TypeError, ValueError):
                return JsonResponse({"error": "A valid id is required"}, status=400)
        if entry_id <= 0:
            return JsonResponse({"error": "A valid id is required"}, status=400)

        assignments: List[str] = []
        params: List[Any] = []

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

            rows = run_query(
                """
                SELECT id, line_id, main_step, custom_end_step
                FROM {table}
                WHERE id = %s
                LIMIT 1
                """.format(table=self.TABLE_NAME),
                [entry_id],
            )
            entry = self._map_row(rows[0] if rows else None)
            if not entry:
                return JsonResponse({"error": "Entry not found"}, status=404)
            return JsonResponse({"entry": entry})
        except Exception as exc:  # pragma: no cover - 방어적 로깅
            error_code = getattr(exc, "code", None) or getattr(exc, "pgcode", None)
            if error_code in {"ER_DUP_ENTRY", "23505"}:
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
                DELETE FROM {table}
                WHERE id = %s
                """.format(table=self.TABLE_NAME),
                [entry_id],
            )
            if affected == 0:
                return JsonResponse({"error": "Entry not found"}, status=404)
            return JsonResponse({"success": True})
        except Exception:  # pragma: no cover - 방어적 로깅
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


__all__ = ["DroneEarlyInformView"]
