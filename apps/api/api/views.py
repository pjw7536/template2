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

# -------------------------------------------------------------------
# 상수/정규식
# -------------------------------------------------------------------
SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9_]+$")  # 안전한 식별자(테이블/컬럼) 검증
DATE_ONLY_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")  # YYYY-MM-DD 형식 검증
DATE_COLUMN_CANDIDATES = ["created_at", "updated_at", "timestamp", "ts", "date"]  # 베이스 타임스탬프 후보
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


# ===================================================================
# 헬스 체크
# ===================================================================
class HealthView(View):
    """헬스 프로브 엔드포인트.
    - 서버/애플리케이션이 살아있는지 간단한 상태 정보 반환
    """

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        return JsonResponse(
            {
                "status": "ok",
                "application": "template2-api",
            }
        )


# ===================================================================
# 인증/프론트 리다이렉트/현 사용자
# ===================================================================
class AuthConfigurationView(View):
    """프론트엔드가 사용할 인증 관련 설정값 제공.
    - devLoginEnabled: 개발용 더미 로그인 허용 여부
    - loginUrl / frontendRedirect / sessionMaxAgeSeconds 등 프론트에서 필요
    """

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        provider_configured = bool(getattr(settings, "OIDC_PROVIDER_CONFIGURED", False))
        # OIDC 공급자가 설정되어 있지 않은 경우에만 개발용 로그인 허용
        dev_login_enabled = bool(getattr(settings, "OIDC_DEV_LOGIN_ENABLED", False) and not provider_configured)
        session_max_age = getattr(settings, "SESSION_COOKIE_AGE", None)
        try:
            session_max_age = int(session_max_age) if session_max_age is not None else None
        except (TypeError, ValueError):
            session_max_age = None
        return JsonResponse(
            {
                "devLoginEnabled": dev_login_enabled,
                "loginUrl": settings.LOGIN_URL,
                "frontendRedirect": settings.FRONTEND_BASE_URL,
                "sessionMaxAgeSeconds": session_max_age,
            }
        )


class FrontendRedirectView(View):
    """프론트엔드 베이스 URL로 안전하게 리다이렉트.
    - ?next=/path 전달 시 베이스 뒤에 붙여 리다이렉트
    - next가 없거나 비정상이면 베이스로 이동
    """

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
    """현재 로그인한 사용자 정보 조회.
    - 인증 안 되었으면 401
    - 권한 요약(스태프/슈퍼유저/역할/특정 퍼미션) 포함
    """

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
    """로그아웃 처리.
    - 세션 정리 및 세션 쿠키 삭제
    """

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
    """개발용 더미 로그인 엔드포인트(POST).
    - settings.DEBUG가 True이고 실제 OIDC 클라이언트 설정이 없을 때만 동작
    - body.email/name/role로 사용자 생성/로그인 (없는 경우 기본값 사용)
    """

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

        # 사용자 생성 또는 가져오기
        user, created = User.objects.get_or_create(
            email=email,
            defaults={"username": username, "first_name": name},
        )
        if created:
            user.set_unusable_password()
            user.save()
        else:
            # 이름이 바뀐 경우 업데이트
            if user.first_name != name:
                user.first_name = name
                user.last_name = ""
                user.save(update_fields=["first_name", "last_name"])

        # 프로필 보장 및 역할 반영
        profile = ensure_user_profile(user)
        if role in dict(profile.Roles.choices):
            profile.role = role
            profile.save(update_fields=["role"])

        # 세션 로그인
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")

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


# ===================================================================
# 액티비티 로그 조회
# ===================================================================
class ActivityLogView(View):
    """최근 액티비티 로그 조회.
    - 인증/퍼미션 체크
    - limit 쿼리 파라미터(최대 200)
    """

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


# ===================================================================
# 공용 유틸 함수
# ===================================================================
def sanitize_identifier(value: Any, fallback: Optional[str] = None) -> Optional[str]:
    """테이블/컬럼명 등 식별자를 안전하게 정규식으로 검증.
    - 안전하지 않으면 fallback 반환
    """
    if not isinstance(value, str):
        return fallback
    candidate = value.strip()
    return candidate if SAFE_IDENTIFIER.match(candidate) else fallback


def normalize_date_only(value: Any) -> Optional[str]:
    """YYYY-MM-DD 형식을 만족하면 그대로, 아니면 None."""
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    return candidate if DATE_ONLY_REGEX.match(candidate) else None


def find_column(column_names: Iterable[str], target: str) -> Optional[str]:
    """컬럼 이름 목록에서 대소문자 무시하고 정확 매칭."""
    target_lower = target.lower()
    for name in column_names:
        if isinstance(name, str) and name.lower() == target_lower:
            return name
    return None


def pick_base_timestamp_column(column_names: Sequence[str]) -> Optional[str]:
    """통계/필터의 기준이 되는 타임스탬프 컬럼 선택.
    - DATE_COLUMN_CANDIDATES 순서대로 첫 매칭 반환
    """
    for candidate in DATE_COLUMN_CANDIDATES:
        found = find_column(column_names, candidate)
        if found:
            return found
    return None


def _get_user_sdwt_prod_values(line_id: str) -> List[str]:
    """line_sdwt 테이블에서 line_id에 해당하는 user_sdwt_prod 목록 조회."""
    rows = run_query(
        """
        SELECT DISTINCT user_sdwt_prod
        FROM {table}
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


def _list_table_columns(table_name: str) -> List[str]:
    """현재 스키마에서 주어진 테이블의 컬럼 목록 조회.
    - information_schema.columns 사용
    - DB별 키 케이스를 고려해 column_name/COLUMN_NAME/Field 키 시도
    """
    rows = run_query(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND LOWER(table_name) = %s
        ORDER BY ordinal_position
        """,
        [table_name.lower()],
    )
    column_names: List[str] = []
    for row in rows:
        value: Optional[str] = None
        for key in ("column_name", "COLUMN_NAME", "Field"):
            raw = row.get(key)
            if isinstance(raw, str) and raw.strip():
                value = raw.strip()
                break
        if value:
            column_names.append(value)
    return column_names


def build_line_filters(column_names: Sequence[str], line_id: Optional[str]) -> Dict[str, Any]:
    """lineId 필터 SQL 조각 생성.
    - 1순위: user_sdwt_prod IN (...)
    - 2순위: line_id = ?
    - 둘 다 불가하면 빈 필터 반환
    """
    filters: List[str] = []
    params: List[Any] = []

    if not line_id:
        return {"filters": filters, "params": params}

    usdwt_col = find_column(column_names, "user_sdwt_prod")
    if usdwt_col:
        values = _get_user_sdwt_prod_values(line_id)
        if values:
            placeholders = ", ".join(["%s"] * len(values))
            filters.append(f"{usdwt_col} IN ({placeholders})")
            params.extend(values)
            return {"filters": filters, "params": params}

    line_col = find_column(column_names, "line_id")
    if line_col:
        filters.append(f"{line_col} = %s")
        params.append(line_id)

    return {"filters": filters, "params": params}


def _to_int(value: Any) -> int:
    """정수 변환 유틸(실패 시 0)."""
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return 0


def _parse_json_body(request: HttpRequest) -> Optional[Dict[str, Any]]:
    """요청 바디(JSON) 파싱 유틸.
    - 디코딩/파싱 실패 또는 dict 아님 → None
    """
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


# ===================================================================
# 테이블 조회 API (/tables) - Next.js API 대체
# ===================================================================
class TablesView(View):
    """테이블 데이터 조회(리스트).
    - table/from/to/lineId 파라미터 처리
    - 기준 타임스탬프 컬럼 확인 후 필터 및 정렬 적용
    - 최근 27시간 컷오프 조건 기본 포함
    """

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        params = request.GET

        table_name = sanitize_identifier(params.get("table"), DEFAULT_TABLE)
        if not table_name:
            return JsonResponse({"error": "Invalid table name"}, status=400)

        from_param = normalize_date_only(params.get("from"))
        to_param = normalize_date_only(params.get("to"))
        line_id_param = params.get("lineId")
        normalized_line_id = line_id_param.strip() if isinstance(line_id_param, str) and line_id_param.strip() else None

        # from/to 역전 방지
        if from_param and to_param:
            from_time = datetime.fromisoformat(f"{from_param}T00:00:00")
            to_time = datetime.fromisoformat(f"{to_param}T23:59:59")
            if from_time > to_time:
                from_param, to_param = to_param, from_param

        try:
            column_names = _list_table_columns(table_name)
            if not column_names:
                return JsonResponse({"error": f'Table "{table_name}" has no columns'}, status=400)

            base_ts_col = pick_base_timestamp_column(column_names)
            if not base_ts_col:
                expected = ", ".join(DATE_COLUMN_CANDIDATES)
                return JsonResponse(
                    {"error": f'No timestamp-like column found in "{table_name}". Expected one of: {expected}.'},
                    status=400,
                )

            # lineId 필터 구성
            line_filter_result = build_line_filters(column_names, normalized_line_id)
            where_parts = list(line_filter_result["filters"])
            query_params = list(line_filter_result["params"])

            # 기본 컷오프(최근 27시간)
            where_parts.append(
                f"{base_ts_col} >= (NOW() - INTERVAL '27 hours')"
            )

            # 추가 날짜 필터(from/to)
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


# ===================================================================
# 부분 업데이트 API (/tables/update)
# ===================================================================
@method_decorator(csrf_exempt, name="dispatch")
class TableUpdateView(View):
    """임의 테이블에 대한 부분 업데이트 처리(PATCH).
    - 현재 허용 컬럼: comment, needtosend
    - id 단일 레코드 기준 업데이트
    """

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

        # 허용된 컬럼만 필터링(값 None 제외)
        filtered = [(key, value) for key, value in updates.items() if key in self.ALLOWED_UPDATE_COLUMNS and value is not None]
        if not filtered:
            return JsonResponse({"error": "No valid updates provided"}, status=400)

        try:
            column_names = _list_table_columns(table_name)

            id_column = find_column(column_names, "id")
            if not id_column:
                return JsonResponse({"error": f'Table "{table_name}" does not expose an id column'}, status=400)

            assignments: List[str] = []
            params: List[Any] = []

            # 실제 존재하는 컬럼만 업데이트 구문 생성
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
        """컬럼별 업데이트 값 정규화.
        - comment: 문자열(없으면 빈 문자열)
        - needtosend: bool로 강제 변환
        """
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


# ===================================================================
# 라인 히스토리(차트용 집계) API
# ===================================================================
class LineHistoryView(View):
    """대시보드 차트용 일별 합계/분해(차원별) 집계 제공.
    - /history?table=...&from=...&to=...&rangeDays=...&lineId=...
    """

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

        # 조회 기간(from/to) 해석
        from_value, to_value = self._resolve_date_range(from_param, to_param, range_days)

        try:
            column_names = _list_table_columns(table_name)
            if not column_names:
                return JsonResponse({"error": f'Table "{table_name}" has no columns'}, status=400)

            timestamp_column = pick_base_timestamp_column(column_names)
            if not timestamp_column:
                return JsonResponse({"error": f'No timestamp-like column found in "{table_name}".'}, status=400)

            send_jira_column = find_column(column_names, "send_jira")
            # 차원 컬럼 존재 여부 매핑
            dimension_columns = {
                candidate: resolved
                for candidate in DIMENSION_CANDIDATES
                if (resolved := find_column(column_names, candidate))
            }

            # WHERE 절/파라미터 구성 (라인 + 기간)
            line_filter_result = build_line_filters(column_names, normalized_line_id)
            where_clause, query_params = self._build_where_clause(
                timestamp_column,
                line_filter_result["filters"],
                line_filter_result["params"],
                from_value,
                to_value,
            )

            # 일자별 합계
            totals_rows = run_query(
                self._build_totals_query(table_name, timestamp_column, send_jira_column, where_clause),
                query_params,
            )
            totals = [self._normalize_daily_row(row) for row in totals_rows]

            # 차원별 분해 결과
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

    # ----------------- 내부 헬퍼 -----------------
    def _resolve_date_range(
        self, from_param: Optional[str], to_param: Optional[str], range_param: Optional[str]
    ) -> tuple[Optional[str], Optional[str]]:
        """from/to/rangeDays 조합을 최종 from/to(YYYY-MM-DD)로 정리.
        - rangeDays가 주어지고 from이 없으면 to 기준 N일 전으로 산정
        - from > to 인 경우 스왑
        """
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
        """라인 및 날짜 범위를 WHERE 절과 파라미터로 구성."""
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
        """일자별 총 건수(+ send_jira 카운트) 집계 SQL 생성."""
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
        """일자×카테고리(차원값)별 건수(+ send_jira 카운트) 집계 SQL 생성."""
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
        """합계 행 스키마 정규화(date/rowCount/sendJiraCount)."""
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
        """분해(차원별) 행 스키마 정규화(date/category/rowCount/sendJiraCount)."""
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


# ===================================================================
# 라인 ID 목록 API
# ===================================================================
class LineIdListView(View):
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
            line_ids = [row["line_id"].strip() for row in rows if isinstance(row.get("line_id"), str) and row.get("line_id").strip()]
            return JsonResponse({"lineIds": line_ids})
        except Exception:  # pragma: no cover - 방어적 로깅
            logger.exception("Failed to load distinct line ids")
            return JsonResponse({"error": "Failed to load line options"}, status=500)


# ===================================================================
# drone_early_inform_v3 CRUD
# ===================================================================
@method_decorator(csrf_exempt, name="dispatch")
class DroneEarlyInformView(View):
    """drone_early_inform_v3 테이블에 대한 CRUD.
    - GET: lineId 기준 목록 조회
    - POST: 신규 레코드 생성
    - PATCH: 특정 id 필드 업데이트(main_step/custom_end_step)
    - DELETE: 특정 id 삭제
    """

    TABLE_NAME = "drone_early_inform_v3"

    # ----------------- READ -----------------
    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """lineId로 설정 목록 조회."""
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
            # 각 행을 프론트 친화 형태로 매핑
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

    # ----------------- CREATE -----------------
    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """신규 엔트리 생성(lineId/mainStep/customEndStep)."""
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
            logger.exception("Failed to insert drone_early_inform row")
            return JsonResponse({"error": "Failed to create entry"}, status=500)

    # ----------------- UPDATE -----------------
    def patch(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """기존 엔트리 일부 업데이트(id 필수)."""
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

            # 갱신된 행을 재조회하여 반환(프론트 일관성)
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

    # ----------------- DELETE -----------------
    def delete(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """id로 엔트리 삭제."""
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

    # ----------------- 입력값 정규화/검증 -----------------
    @staticmethod
    def _sanitize_line_id(value: Any) -> Optional[str]:
        """lineId 문자열 정리(공백 제거, 길이 제한)."""
        if not isinstance(value, str):
            return None
        trimmed = value.strip()
        return trimmed if trimmed and len(trimmed) <= MAX_FIELD_LENGTH else None

    @staticmethod
    def _sanitize_main_step(value: Any) -> Optional[str]:
        """mainStep 문자열 정리(빈 문자열/None 허용하지 않음)."""
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
        """customEndStep 문자열 정리(빈값→None, 길이 50 제한)."""
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
        """DB 행을 API 응답 스키마로 변환."""
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
