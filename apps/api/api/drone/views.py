"""Drone 조기 알림 설정 및 라인 대시보드 집계 엔드포인트.

Early inform 설정은 DroneEarlyInform ORM 모델을 통해 처리하고,
라인 대시보드 집계/옵션 조회는 selectors에서 raw SQL로 처리합니다.

# 엔드포인트 요약
- GET    /api/v1/line-dashboard/early-inform?lineId=L1
- POST   /api/v1/line-dashboard/early-inform { lineId, mainStep, customEndStep? }
- PATCH  /api/v1/line-dashboard/early-inform { id, lineId?, mainStep?, customEndStep? }
- DELETE /api/v1/line-dashboard/early-inform?id=123

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
import os
from typing import Any, Optional

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from api.common.constants import MAX_FIELD_LENGTH
from api.common.utils import parse_json_body

from api.common.activity_logging import (
    merge_activity_metadata,
    set_activity_new_state,
    set_activity_previous_state,
    set_activity_summary,
)

from . import selectors, services
from .serializers import serialize_early_inform_entry

logger = logging.getLogger(__name__)


def _ensure_authenticated(request: HttpRequest) -> JsonResponse | None:
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return JsonResponse({"error": "로그인이 필요합니다."}, status=401)
    return None


def _extract_bearer_token(request: HttpRequest) -> str | None:
    auth_header = request.META.get("HTTP_AUTHORIZATION", "")
    if not isinstance(auth_header, str) or not auth_header:
        return None
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


def _ensure_airflow_token(request: HttpRequest) -> JsonResponse | None:
    expected = (
        getattr(settings, "AIRFLOW_TRIGGER_TOKEN", "") or os.getenv("AIRFLOW_TRIGGER_TOKEN") or ""
    ).strip()
    if not expected:
        return JsonResponse({"error": "AIRFLOW_TRIGGER_TOKEN not configured"}, status=500)

    provided = _extract_bearer_token(request)
    if provided != expected:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    return None


@method_decorator(csrf_exempt, name="dispatch")
class DroneEarlyInformView(APIView):
    """drone_early_inform 테이블에 대한 CRUD.

    - GET: lineId로 행 목록 조회(최신 정렬 기준: main_step ASC, id ASC)
    - POST: 신규 행 추가(중복 main_step 방지 가정)
    - PATCH: 부분 업데이트(id 필수)
    - DELETE: 행 삭제(id 쿼리 파라미터)
    """

    # 한 곳에서만 테이블명을 관리해 실수 방지
    TABLE_NAME = "drone_early_inform"

    # --------------------------------------------------------------------- #
    # READ
    # --------------------------------------------------------------------- #
    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """lineId로 행 목록을 가져옵니다."""
        auth_response = _ensure_authenticated(request)
        if auth_response is not None:
            return auth_response

        line_id = self._sanitize_line_id(request.GET.get("lineId"))
        if not line_id:
            return JsonResponse({"error": "lineId is required"}, status=400)

        try:
            normalized_rows = [
                serialize_early_inform_entry(entry)
                for entry in selectors.list_early_inform_entries(line_id=line_id)
            ]
            user_sdwt_values = selectors.list_user_sdwt_prod_values_for_line(line_id=line_id)
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
        auth_response = _ensure_authenticated(request)
        if auth_response is not None:
            return auth_response

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

        user = getattr(request, "user", None)
        knox_id = None
        if user and getattr(user, "is_authenticated", False):
            knox_id = getattr(user, "knox_id", None)
        updated_by = self._sanitize_updated_by(knox_id or "system")

        try:
            entry = services.create_early_inform_entry(
                line_id=line_id,
                main_step=main_step,
                custom_end_step=custom_end_step,
                updated_by=updated_by,
            )
            entry_payload = serialize_early_inform_entry(entry)

            # 액티비티 로그(요약 + 신규 상태 + 메타데이터)
            set_activity_summary(request, "Create drone_early_inform entry")
            set_activity_new_state(request, entry_payload)
            merge_activity_metadata(
                request,
                resource=self.TABLE_NAME,
                entryId=entry_payload["id"],
            )
            return JsonResponse({"entry": entry_payload}, status=201)

        except services.DroneEarlyInformDuplicateError as exc:
            return JsonResponse({"error": str(exc)}, status=409)
        except Exception:  # pragma: no cover - 방어적 로깅
            logger.exception("Failed to create drone_early_inform row")
            return JsonResponse({"error": "Failed to create entry"}, status=500)

    # --------------------------------------------------------------------- #
    # UPDATE (partial)
    # --------------------------------------------------------------------- #
    def patch(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """id로 지정된 행을 부분 업데이트합니다."""
        auth_response = _ensure_authenticated(request)
        if auth_response is not None:
            return auth_response

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

        updates: dict[str, Any] = {}
        user = getattr(request, "user", None)
        knox_id = None
        if user and getattr(user, "is_authenticated", False):
            knox_id = getattr(user, "knox_id", None)
        updated_by = self._sanitize_updated_by(knox_id or "system")

        if "lineId" in payload:
            line_id = self._sanitize_line_id(payload.get("lineId"))
            if not line_id:
                return JsonResponse({"error": "lineId is required"}, status=400)
            updates["line_id"] = line_id

        if "mainStep" in payload:
            main_step = self._sanitize_main_step(payload.get("mainStep"))
            if not main_step:
                return JsonResponse({"error": "mainStep is required"}, status=400)
            updates["main_step"] = main_step

        if "customEndStep" in payload:
            try:
                normalized = self._normalize_custom_end_step(payload.get("customEndStep"))
            except ValueError as exc:
                return JsonResponse({"error": str(exc)}, status=400)
            updates["custom_end_step"] = normalized

        if not updates:
            return JsonResponse({"error": "No valid fields to update"}, status=400)

        try:
            result = services.update_early_inform_entry(
                entry_id=entry_id,
                updates=updates,
                updated_by=updated_by,
            )
            set_activity_previous_state(request, serialize_early_inform_entry(result.previous_entry))
            entry_payload = serialize_early_inform_entry(result.entry)
            set_activity_new_state(request, entry_payload)
            return JsonResponse({"entry": entry_payload})

        except services.DroneEarlyInformNotFoundError as exc:
            return JsonResponse({"error": str(exc)}, status=404)
        except services.DroneEarlyInformDuplicateError as exc:
            return JsonResponse({"error": str(exc)}, status=409)
        except Exception:  # pragma: no cover - 방어적 로깅
            logger.exception("Failed to update drone_early_inform row")
            return JsonResponse({"error": "Failed to update entry"}, status=500)

    # --------------------------------------------------------------------- #
    # DELETE
    # --------------------------------------------------------------------- #
    def delete(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """id로 지정된 행을 삭제합니다."""
        auth_response = _ensure_authenticated(request)
        if auth_response is not None:
            return auth_response

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

        try:
            deleted_entry = services.delete_early_inform_entry(entry_id=entry_id)
            set_activity_previous_state(request, serialize_early_inform_entry(deleted_entry))

            # 삭제 성공도 신규 상태로 간단히 표기
            set_activity_new_state(request, {"deleted": True})
            return JsonResponse({"success": True})

        except services.DroneEarlyInformNotFoundError as exc:
            return JsonResponse({"error": str(exc)}, status=404)
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


class LineHistoryView(APIView):
    """라인 대시보드 차트용 시간 단위 합계/분해 집계 제공."""

    DEFAULT_RANGE_DAYS = 14

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        try:
            payload = selectors.get_line_history_payload(
                table_param=request.GET.get("table"),
                line_id_param=request.GET.get("lineId"),
                from_param=request.GET.get("from"),
                to_param=request.GET.get("to"),
                range_days_param=request.GET.get("rangeDays"),
                default_range_days=self.DEFAULT_RANGE_DAYS,
            )
            return JsonResponse(payload)
        except (ValueError, LookupError) as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except Exception:  # pragma: no cover - 방어적 로깅
            logger.exception("Failed to load history data")
            return JsonResponse({"error": "Failed to load history data"}, status=500)


class LineIdListView(APIView):
    """사이드바 필터용 line_id 고유값 목록 반환."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        try:
            return JsonResponse({"lineIds": selectors.list_distinct_line_ids()})
        except Exception:  # pragma: no cover - 방어적 로깅
            logger.exception("Failed to load distinct line ids")
            return JsonResponse({"error": "Failed to load line options"}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class DroneSopInstantInformView(APIView):
    """Line dashboard에서 호출하는 Drone SOP 단건 즉시인폼(=Jira 강제 생성)."""

    permission_classes: tuple = ()

    def post(self, request: HttpRequest, sop_id: int, *args: object, **kwargs: object) -> JsonResponse:
        auth_response = _ensure_authenticated(request)
        if auth_response is not None:
            return auth_response

        payload = parse_json_body(request) or {}
        raw_comment = payload.get("comment")
        if raw_comment is not None and not isinstance(raw_comment, str):
            return JsonResponse({"error": "comment must be a string"}, status=400)
        comment = raw_comment.strip() if isinstance(raw_comment, str) else None

        set_activity_summary(request, f"Instant inform drone_sop #{sop_id}")
        merge_activity_metadata(request, resource="drone_sop", action="instant_inform", sop_id=sop_id)
        if comment is not None:
            merge_activity_metadata(request, comment_length=len(comment))

        try:
            result = services.run_drone_sop_jira_instant_inform(sop_id=sop_id, comment=comment)
            set_activity_new_state(
                request,
                {
                    "created": result.created,
                    "already_informed": result.already_informed,
                    "jira_key": result.jira_key,
                    "skipped": result.skipped,
                    "skip_reason": result.skip_reason,
                },
            )

            status = 200
            if result.skipped and result.skip_reason == "already_running":
                status = 409
            payload = {
                "created": result.created,
                "alreadyInformed": result.already_informed,
                "jiraKey": result.jira_key,
                "updated": result.updated_fields,
                "skipped": result.skipped,
                "skipReason": result.skip_reason,
            }
            if status != 200:
                payload["error"] = "Jira pipeline is already running"

            return JsonResponse(payload, status=status)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except RuntimeError as exc:
            logger.exception("Drone SOP instant inform failed")
            return JsonResponse({"error": str(exc) or "Jira create failed"}, status=502)
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Drone SOP instant inform failed")
            return JsonResponse({"error": "Drone SOP instant inform failed"}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class DroneSopPop3IngestTriggerView(APIView):
    """외부 Airflow에서 호출하는 Drone SOP POP3 수집 트리거."""

    permission_classes: tuple = ()

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        auth_response = _ensure_airflow_token(request)
        if auth_response is not None:
            return auth_response

        set_activity_summary(request, "Trigger drone_sop POP3 ingest")
        merge_activity_metadata(request, resource="drone_sop", pipeline="pop3_ingest")

        try:
            result = services.run_drone_sop_pop3_ingest_from_env()
            set_activity_new_state(
                request,
                {
                    "matched": result.matched_mails,
                    "upserted": result.upserted_rows,
                    "deleted": result.deleted_mails,
                    "pruned": result.pruned_rows,
                    "skipped": result.skipped,
                    "skip_reason": result.skip_reason,
                },
            )
            return JsonResponse(
                {
                    "matched": result.matched_mails,
                    "upserted": result.upserted_rows,
                    "deleted": result.deleted_mails,
                    "pruned": result.pruned_rows,
                    "skipped": result.skipped,
                    "skipReason": result.skip_reason,
                }
            )
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Failed to trigger drone SOP POP3 ingest")
            return JsonResponse({"error": "Drone SOP POP3 ingest failed"}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class DroneSopJiraTriggerView(APIView):
    """외부 Airflow에서 호출하는 Drone SOP Jira 생성 트리거."""

    permission_classes: tuple = ()

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        auth_response = _ensure_airflow_token(request)
        if auth_response is not None:
            return auth_response

        payload = parse_json_body(request) or {}
        raw_limit = payload.get("limit")
        if raw_limit is None:
            raw_limit = request.GET.get("limit")
        limit = None
        if raw_limit is not None:
            try:
                limit = int(raw_limit)
            except (TypeError, ValueError):
                return JsonResponse({"error": "limit must be an integer"}, status=400)
            if limit <= 0:
                limit = None

        set_activity_summary(request, "Trigger drone_sop Jira create")
        merge_activity_metadata(request, resource="drone_sop", pipeline="jira_create", limit=limit)

        try:
            result = services.run_drone_sop_jira_create_from_env(limit=limit)
            set_activity_new_state(
                request,
                {
                    "candidates": result.candidates,
                    "created": result.created,
                    "updated_rows": result.updated_rows,
                    "skipped": result.skipped,
                    "skip_reason": result.skip_reason,
                },
            )
            return JsonResponse(
                {
                    "candidates": result.candidates,
                    "created": result.created,
                    "updated": result.updated_rows,
                    "skipped": result.skipped,
                    "skipReason": result.skip_reason,
                }
            )
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Failed to trigger drone SOP Jira create")
            return JsonResponse({"error": "Drone SOP Jira create failed"}, status=500)


__all__ = [
    "DroneEarlyInformView",
    "DroneSopInstantInformView",
    "DroneSopJiraTriggerView",
    "DroneSopPop3IngestTriggerView",
    "LineHistoryView",
    "LineIdListView",
]
