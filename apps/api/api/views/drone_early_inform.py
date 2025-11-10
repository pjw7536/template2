"""드론 조기 알림(Drone Early Inform) 설정 CRUD 뷰.

이 모듈은 drone_early_inform_v3 테이블을 직접 SQL로 조회/수정합니다.
요청 → 파라미터 정규화/검증 → DB쿼리 → 액티비티 로깅(이전/신규 상태) → JSON 응답
순서로 동작합니다.

# 엔드포인트 요약
- GET    /.../drone-early-inform?lineId=L1
- POST   /.../drone-early-inform { lineId, mainStep, customEndStep? }
- PATCH  /.../drone-early-inform { id, lineId?, mainStep?, customEndStep? }
- DELETE /.../drone-early-inform?id=123

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
from typing import Any, Dict, List, Optional

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
from .constants import MAX_FIELD_LENGTH
from .utils import parse_json_body

logger = logging.getLogger(__name__)


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
                SELECT id, line_id, main_step, custom_end_step
                FROM {table}
                WHERE line_id = %s
                ORDER BY main_step ASC, id ASC
                """.format(table=self.TABLE_NAME),
                [line_id],
            )
            # DB 레코드를 API 응답 형태로 정규화
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
            error_code = getattr(exc, "code", None) or getattr(exc, "pgcode", None)
            if error_code in {"ER_DUP_ENTRY", "23505"}:
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

        # 동적 UPDATE 컬럼 구성
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

            set_activity_new_state(request, entry)
            return JsonResponse({"entry": entry})

        except Exception as exc:  # pragma: no cover - 방어적 로깅
            error_code = getattr(exc, "code", None) or getattr(exc, "pgcode", None)
            if error_code in {"ER_DUP_ENTRY", "23505"}:
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
    def _map_row(row: Optional[Dict[str, Any]], fallback_line_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """DB 행(dict)을 API 응답 형식으로 매핑.

        - id: int로 강제
        - lineId: str 또는 None (fallback_line_id로 보완)
        - mainStep: str (값이 숫자일 수도 있어 안전 문자열화)
        - customEndStep: str 또는 None
        """
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
            "mainStep": (
                main_step if isinstance(main_step, str)
                else str(main_step) if main_step is not None
                else ""
            ),
            "customEndStep": custom_end_step if isinstance(custom_end_step, str) else None,
        }


__all__ = ["DroneEarlyInformView"]
