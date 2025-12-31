# =============================================================================
# 모듈 설명: 공용 유틸리티/정규화 함수 모음을 제공합니다.
# - 주요 대상: 식별자/날짜 정규화, 테이블 메타 조회, 리다이렉트 처리
# - 불변 조건: SAFE_IDENTIFIER 규칙을 통과한 값만 DB 조회에 사용합니다.
# =============================================================================

"""여러 뷰에서 공용으로 사용하는 유틸리티 함수 모음.

- 주요 대상: 식별자/날짜 정규화, 테이블 메타 조회, 필터 조합, 안전한 리다이렉트
- 주요 엔드포인트/클래스: TableSchema(테이블 스키마 요약 데이터)
- 가정/불변 조건: 테이블/컬럼 식별자는 SAFE_IDENTIFIER 규칙을 통과해야 함
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.utils.http import url_has_allowed_host_and_scheme

from api.common import selectors as common_selectors
from .constants import (
    DATE_COLUMN_CANDIDATES,
    DATE_ONLY_REGEX,
    DEFAULT_TABLE,
    LINE_SDWT_TABLE_NAME,
    SAFE_IDENTIFIER,
)


# ---------------------------------------------------------------------------
# 문자열/날짜 정규화
# ---------------------------------------------------------------------------
def sanitize_identifier(value: Any, fallback: Optional[str] = None) -> Optional[str]:
    """식별자 문자열을 안전한 정규식으로 검증합니다.

    입력:
    - value: 검증 대상 값(문자열 기대)
    - fallback: 검증 실패 시 반환할 기본값

    반환:
    - Optional[str]: 검증된 식별자 또는 fallback

    부작용:
    - 없음

    오류:
    - 없음
    """

    if not isinstance(value, str):
        return fallback
    candidate = value.strip()
    return candidate if SAFE_IDENTIFIER.match(candidate) else fallback


def normalize_date_only(value: Any) -> Optional[str]:
    """YYYY-MM-DD 형식 문자열만 허용합니다.

    입력:
    - value: 날짜 후보 값

    반환:
    - Optional[str]: 유효한 날짜 문자열 또는 None

    부작용:
    - 없음

    오류:
    - 없음
    """

    if not isinstance(value, str):
        return None
    candidate = value.strip()
    return candidate if DATE_ONLY_REGEX.match(candidate) else None


def normalize_line_id(value: Any) -> Optional[str]:
    """lineId 쿼리 파라미터를 정규화합니다.

    입력:
    - value: lineId 후보 값

    반환:
    - Optional[str]: 공백 제거 후 값 또는 None

    부작용:
    - 없음

    오류:
    - 없음
    """

    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed or None


def normalize_text(value: Any) -> str:
    """텍스트 필드를 트림하고 비문자열은 빈 문자열로 처리합니다.

    입력:
    - value: 텍스트 후보 값

    반환:
    - str: 정규화된 문자열

    부작용:
    - 없음

    오류:
    - 없음
    """

    if not isinstance(value, str):
        return ""
    return value.strip()


def ensure_date_bounds(from_value: Optional[str], to_value: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """from/to 날짜 범위가 뒤집힌 경우 순서를 교정합니다.

    입력:
    - from_value: 시작 날짜(YYYY-MM-DD)
    - to_value: 종료 날짜(YYYY-MM-DD)

    반환:
    - Tuple[Optional[str], Optional[str]]: 교정된 (from, to)

    부작용:
    - 없음

    오류:
    - 없음(파싱 실패 시 원본을 그대로 반환)
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 확인 및 파싱 시도
    # -----------------------------------------------------------------------------
    if from_value and to_value:
        try:
            from_time = datetime.fromisoformat(f"{from_value}T00:00:00")
            to_time = datetime.fromisoformat(f"{to_value}T00:00:00")
        except ValueError:
            return from_value, to_value
        # -----------------------------------------------------------------------------
        # 2) 범위 역전 여부 교정
        # -----------------------------------------------------------------------------
        if from_time > to_time:
            return to_value, from_value
    # -----------------------------------------------------------------------------
    # 3) 최종 반환
    # -----------------------------------------------------------------------------
    return from_value, to_value


def build_date_range_filters(
    timestamp_column: str, from_value: Optional[str], to_value: Optional[str]
) -> Tuple[List[str], List[str]]:
    """타임스탬프 컬럼 기준의 WHERE 조건과 파라미터를 생성합니다.

    입력:
    - timestamp_column: 기준 컬럼명
    - from_value: 시작 날짜(YYYY-MM-DD)
    - to_value: 종료 날짜(YYYY-MM-DD)

    반환:
    - Tuple[List[str], List[str]]: 조건 문자열 목록과 파라미터 목록

    부작용:
    - 없음

    오류:
    - 없음

    참고:
    - from → YYYY-MM-DD 00:00:00 이상
    - to   → YYYY-MM-DD 23:59:59 이하
    """

    # -----------------------------------------------------------------------------
    # 1) 기본 컨테이너 준비
    # -----------------------------------------------------------------------------
    conditions: List[str] = []
    params: List[str] = []

    # -----------------------------------------------------------------------------
    # 2) from 조건 구성
    # -----------------------------------------------------------------------------
    if from_value:
        conditions.append(f"{timestamp_column} >= %s")
        params.append(f"{from_value} 00:00:00")

    # -----------------------------------------------------------------------------
    # 3) to 조건 구성
    # -----------------------------------------------------------------------------
    if to_value:
        conditions.append(f"{timestamp_column} <= %s")
        params.append(f"{to_value} 23:59:59")

    # -----------------------------------------------------------------------------
    # 4) 결과 반환
    # -----------------------------------------------------------------------------
    return conditions, params


@dataclass(frozen=True)
class TableSchema:
    """테이블 스키마 정보를 묶어 전달하는 데이터 클래스.

    - name: 테이블 이름
    - columns: 컬럼 목록
    - timestamp_column: 기준 타임스탬프 컬럼(선택)
    """

    name: str
    columns: List[str]
    timestamp_column: Optional[str] = None


def resolve_table_schema(
    table_param: Any, *, default_table: Optional[str] = DEFAULT_TABLE, require_timestamp: bool = False
) -> TableSchema:
    """테이블 이름을 검증하고 컬럼/타임스탬프 컬럼 정보를 반환합니다.

    입력:
    - table_param: 테이블명 후보 값
    - default_table: 기본 테이블명
    - require_timestamp: 타임스탬프 컬럼 필수 여부

    반환:
    - TableSchema: 테이블/컬럼/타임스탬프 컬럼 정보

    부작용:
    - 없음(메타 조회는 읽기 전용)

    오류:
    - ValueError: 테이블명이 비어있거나 안전하지 않음
    - LookupError: 컬럼 없음 또는 타임스탬프 후보 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 테이블명 정규화 및 검증
    # -----------------------------------------------------------------------------
    table_name = sanitize_identifier(table_param, default_table)
    if not table_name:
        raise ValueError("Invalid table name")

    # -----------------------------------------------------------------------------
    # 2) 컬럼 목록 조회
    # -----------------------------------------------------------------------------
    columns = common_selectors.list_table_columns(table_name)
    if not columns:
        raise LookupError(f'Table "{table_name}" has no columns')

    # -----------------------------------------------------------------------------
    # 3) 타임스탬프 컬럼 선택(옵션)
    # -----------------------------------------------------------------------------
    timestamp_column = None
    if require_timestamp:
        timestamp_column = pick_base_timestamp_column(columns)
        if not timestamp_column:
            expected = ", ".join(DATE_COLUMN_CANDIDATES)
            raise LookupError(f'No timestamp-like column found in "{table_name}". Expected one of: {expected}.')

    # -----------------------------------------------------------------------------
    # 4) 결과 반환
    # -----------------------------------------------------------------------------
    return TableSchema(name=table_name, columns=columns, timestamp_column=timestamp_column)


def to_int(value: Any) -> int:
    """값을 정수로 변환하고 실패 시 0을 반환합니다.

    입력:
    - value: 정수 변환 대상 값

    반환:
    - int: 변환된 정수 또는 0

    부작용:
    - 없음

    오류:
    - 없음(변환 실패는 0으로 처리)
    """

    # -----------------------------------------------------------------------------
    # 1) 1차 정수 변환 시도
    # -----------------------------------------------------------------------------
    try:
        return int(value)
    except (TypeError, ValueError):
        # -----------------------------------------------------------------------------
        # 2) 부동소수점 경유 변환 시도
        # -----------------------------------------------------------------------------
        try:
            return int(float(value))
        except (TypeError, ValueError):
            # -----------------------------------------------------------------------------
            # 3) 실패 시 기본값 반환
            # -----------------------------------------------------------------------------
            return 0


def parse_json_body(request: HttpRequest) -> Optional[Dict[str, Any]]:
    """요청 바디(JSON)를 파싱해 딕셔너리로 반환합니다.

    입력:
    - 요청: Django HttpRequest

    반환:
    - Optional[Dict[str, Any]]: 파싱 성공 시 dict, 실패 시 None

    부작용:
    - 없음

    오류:
    - 없음(디코딩/파싱 실패는 None으로 처리)
    """

    # -----------------------------------------------------------------------------
    # 1) 바이트 문자열 디코딩
    # -----------------------------------------------------------------------------
    try:
        body = request.body.decode("utf-8")
    except UnicodeDecodeError:
        return None
    # -----------------------------------------------------------------------------
    # 2) JSON 파싱
    # -----------------------------------------------------------------------------
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return None
    # -----------------------------------------------------------------------------
    # 3) 객체 타입 검증 및 반환
    # -----------------------------------------------------------------------------
    return data if isinstance(data, dict) else None


def extract_bearer_token(request: HttpRequest) -> str:
    """Authorization 헤더에서 토큰 문자열을 추출합니다.

    입력:
    - 요청: Django HttpRequest

    반환:
    - str: 추출된 토큰 문자열(없으면 빈 문자열)

    부작용:
    - 없음

    오류:
    - 없음

    참고:
    - "Bearer <token>" 형식과 raw 토큰을 모두 지원합니다.
    """

    # -----------------------------------------------------------------------------
    # 1) Authorization 헤더 확보
    # -----------------------------------------------------------------------------
    auth_header = request.headers.get("Authorization") or request.META.get("HTTP_AUTHORIZATION") or ""
    if not isinstance(auth_header, str):
        return ""

    # -----------------------------------------------------------------------------
    # 2) Bearer 프리픽스 처리
    # -----------------------------------------------------------------------------
    normalized = auth_header.strip()
    if normalized.lower().startswith("bearer "):
        return normalized[7:].strip()
    return normalized


def ensure_airflow_token(request: HttpRequest, *, require_bearer: bool = False) -> JsonResponse | None:
    """AIRFLOW_TRIGGER_TOKEN을 검증하고 실패 시 JsonResponse를 반환합니다.

    입력:
    - 요청: Django HttpRequest
    - require_bearer: Authorization 헤더의 Bearer 형식 강제 여부

    반환:
    - JsonResponse | None: 오류 시 JsonResponse, 정상 시 None

    부작용:
    - 없음

    오류:
    - 500: 서버 설정에 토큰이 없을 때
    - 401: 제공된 토큰이 기대값과 다를 때
    """

    # -----------------------------------------------------------------------------
    # 1) 기대 토큰 준비
    # -----------------------------------------------------------------------------
    expected = (
        getattr(settings, "AIRFLOW_TRIGGER_TOKEN", "") or os.getenv("AIRFLOW_TRIGGER_TOKEN") or ""
    ).strip()
    if not expected:
        return JsonResponse({"error": "AIRFLOW_TRIGGER_TOKEN not configured"}, status=500)

    # -----------------------------------------------------------------------------
    # 2) 제공된 토큰 추출
    # -----------------------------------------------------------------------------
    if require_bearer:
        auth_header = request.headers.get("Authorization") or request.META.get("HTTP_AUTHORIZATION") or ""
        if isinstance(auth_header, str) and auth_header.strip().lower().startswith("bearer "):
            provided = auth_header.strip()[7:].strip()
        else:
            provided = ""
    else:
        provided = extract_bearer_token(request)
    # -----------------------------------------------------------------------------
    # 3) 비교 및 결과 반환
    # -----------------------------------------------------------------------------
    if provided != expected:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    return None


# ---------------------------------------------------------------------------
# DB 메타 정보/필터링 로직
# ---------------------------------------------------------------------------
def find_column(column_names: Iterable[str], target: str) -> Optional[str]:
    """컬럼 목록에서 대소문자 무시 일치 항목을 찾습니다.

    입력:
    - column_names: 컬럼명 목록
    - target: 찾을 컬럼명

    반환:
    - Optional[str]: 일치하는 컬럼명 또는 None

    부작용:
    - 없음

    오류:
    - 없음
    """

    target_lower = target.lower()
    for name in column_names:
        if isinstance(name, str) and name.lower() == target_lower:
            return name
    return None


def pick_base_timestamp_column(column_names: Sequence[str]) -> Optional[str]:
    """통계/필터의 기준이 되는 타임스탬프 컬럼을 선택합니다.

    입력:
    - column_names: 컬럼명 목록

    반환:
    - Optional[str]: 기준 타임스탬프 컬럼명 또는 None

    부작용:
    - 없음

    오류:
    - 없음
    """

    for candidate in DATE_COLUMN_CANDIDATES:
        found = find_column(column_names, candidate)
        if found:
            return found
    return None


def build_line_filters(column_names: Sequence[str], line_id: Optional[str]) -> Dict[str, Any]:
    """lineId 기반 필터 SQL 조각을 생성합니다.

    입력:
    - column_names: 테이블 컬럼 목록
    - line_id: lineId 값

    반환:
    - Dict[str, Any]: {"filters": [...], "params": [...]} (필터/파라미터 조각)

    부작용:
    - 없음

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 기본 컨테이너 준비
    # -----------------------------------------------------------------------------
    filters: List[str] = []
    params: List[Any] = []

    # -----------------------------------------------------------------------------
    # 2) line_id 미제공 처리
    # -----------------------------------------------------------------------------
    if not line_id:
        return {"filters": filters, "params": params}

    # -----------------------------------------------------------------------------
    # 3) user_sdwt_prod 경유 필터 구성
    # -----------------------------------------------------------------------------
    usdwt_col = find_column(column_names, "user_sdwt_prod")
    if usdwt_col:
        filters.append(
            "{col} IN ("
            "SELECT user_sdwt_prod FROM {table} "
            "WHERE line = %s "
            "AND user_sdwt_prod IS NOT NULL "
            "AND user_sdwt_prod <> ''"
            ")".format(col=usdwt_col, table=LINE_SDWT_TABLE_NAME)
        )
        params.append(line_id)
        return {"filters": filters, "params": params}

    # -----------------------------------------------------------------------------
    # 4) line_id 직접 컬럼 필터 구성
    # -----------------------------------------------------------------------------
    line_col = find_column(column_names, "line_id")
    if line_col:
        filters.append(f"{line_col} = %s")
        params.append(line_id)

    # -----------------------------------------------------------------------------
    # 5) 결과 반환
    # -----------------------------------------------------------------------------
    return {"filters": filters, "params": params}


# ---------------------------------------------------------------------------
# URL 헬퍼
# ---------------------------------------------------------------------------
def resolve_frontend_target(
    next_value: Optional[str], *, request: Optional[HttpRequest] = None
) -> str:
    """프론트엔드 베이스 URL과 next 값을 조합해 안전한 리다이렉트를 생성합니다.

    입력:
    - next_value: next 파라미터 값
    - 요청: Django HttpRequest(선택)

    반환:
    - str: 안전한 리다이렉트 URL

    부작용:
    - 없음

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 기본 베이스 URL 결정
    # -----------------------------------------------------------------------------
    base = str(getattr(settings, "FRONTEND_BASE_URL", "") or "").strip()
    if not base and request is not None:
        base = request.build_absolute_uri("/").rstrip("/")
    if not base:
        base = "http://localhost"

    # -----------------------------------------------------------------------------
    # 2) 허용 호스트 집합 계산
    # -----------------------------------------------------------------------------
    base = base.rstrip("/")
    parsed_base = urlparse(base if "://" in base else f"http://{base.lstrip('/')}")
    allowed_hosts = {parsed_base.netloc} if parsed_base.netloc else set()

    # -----------------------------------------------------------------------------
    # 3) next 값 검증 및 조합
    # -----------------------------------------------------------------------------
    if next_value:
        candidate = str(next_value).strip()
        if candidate:
            if url_has_allowed_host_and_scheme(
                candidate, allowed_hosts=allowed_hosts, require_https=False
            ):
                return candidate
            if candidate.startswith("/"):
                trimmed = candidate.lstrip("/")
                return f"{base}/{trimmed}" if trimmed else base
            if "://" not in candidate:
                trimmed = candidate.lstrip("/")
                return f"{base}/{trimmed}" if trimmed else base

    # -----------------------------------------------------------------------------
    # 4) 기본 베이스 반환
    # -----------------------------------------------------------------------------
    return base


__all__ = [
    "build_line_filters",
    "find_column",
    "normalize_date_only",
    "resolve_table_schema",
    "TableSchema",
    "parse_json_body",
    "pick_base_timestamp_column",
    "resolve_frontend_target",
    "sanitize_identifier",
    "to_int",
]
