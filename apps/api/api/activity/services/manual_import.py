# =============================================================================
# 모듈 설명: 외부 앱 접속 통계의 수동 CSV/TSV 입력을 담당합니다.
# - 불변 조건: snake_case와 한국어 헤더는 파일 입력 별칭으로만 허용합니다.
# =============================================================================
from __future__ import annotations

import csv
from datetime import date
from io import StringIO
from typing import Any

from django.db import transaction
from django.utils import timezone

from ..models import ExternalAppAccessDailyStat
from ._shared import normalize_app_name, serialize_date

MANUAL_SOURCE_TYPE = ExternalAppAccessDailyStat.SOURCE_TYPE_MANUAL
MANUAL_PASTE_EXPECTED_COLUMNS = ["date", "appName", "accessCount", "uniqueUserCount", "memo"]
HEADER_ALIASES = {
    "date": "date",
    "stat_date": "date",
    "날짜": "date",
    "일자": "date",
    "app_id": "app_id",
    "appid": "app_id",
    "앱id": "app_id",
    "앱_id": "app_id",
    "앱아이디": "app_id",
    "app_name": "app_name",
    "appname": "app_name",
    "앱명": "app_name",
    "앱이름": "app_name",
    "access_count": "access_count",
    "accesscount": "access_count",
    "접속횟수": "access_count",
    "접속수": "access_count",
    "unique_user_count": "unique_user_count",
    "uniqueusercount": "unique_user_count",
    "접속사용자": "unique_user_count",
    "접속사용자수": "unique_user_count",
    "사용자수": "unique_user_count",
    "memo": "memo",
    "메모": "memo",
    "비고": "memo",
}
REQUIRED_MANUAL_COLUMNS = ["date", "app_name", "access_count", "unique_user_count"]
MANUAL_COLUMN_LABELS = {
    "date": "date",
    "app_name": "appName",
    "access_count": "accessCount",
    "unique_user_count": "uniqueUserCount",
}


def _normalize_header(value: Any) -> str:
    """붙여넣기 헤더 이름을 내부 컬럼명으로 정규화합니다."""

    if not isinstance(value, str):
        return ""
    key = value.strip().lstrip("\ufeff").lower().replace(" ", "").replace("-", "_")
    return HEADER_ALIASES.get(key, key)


def _detect_paste_delimiter(pasted_text: str) -> str:
    """붙여넣기 원문에서 TSV/CSV 구분자를 판별합니다."""

    first_line = next((line for line in pasted_text.splitlines() if line.strip()), "")
    return "\t" if "\t" in first_line else ","


def _read_paste_rows(pasted_text: str) -> tuple[list[str], list[list[str]]]:
    """붙여넣기 원문을 헤더와 데이터 행으로 분리합니다."""

    delimiter = _detect_paste_delimiter(pasted_text)
    reader = csv.reader(StringIO(pasted_text), delimiter=delimiter)
    rows = [[cell.strip() for cell in row] for row in reader if any(cell.strip() for cell in row)]
    if not rows:
        return [], []
    return rows[0], rows[1:]


def _parse_manual_date(value: str) -> tuple[date | None, str | None]:
    """수동 입력 날짜 값을 검증합니다."""

    if not value:
        return None, "date is required"
    try:
        return date.fromisoformat(value), None
    except ValueError:
        return None, "date must be YYYY-MM-DD"


def _parse_manual_count(value: str, *, field_name: str) -> tuple[int | None, str | None]:
    """수동 입력 숫자 값을 0 이상의 정수로 검증합니다."""

    if value == "":
        return None, f"{field_name} is required"
    try:
        parsed = int(value.replace(",", ""))
    except ValueError:
        return None, f"{field_name} must be a number"
    if parsed < 0:
        return None, f"{field_name} must be greater than or equal to 0"
    return parsed, None


def _build_manual_row(
    *,
    row_number: int,
    headers: list[str],
    cells: list[str],
) -> dict[str, Any]:
    """붙여넣기 데이터 한 행을 미리보기 row로 변환합니다."""

    values_by_header = {header: cells[index].strip() if index < len(cells) else "" for index, header in enumerate(headers)}
    errors: list[str] = []

    stat_date, date_error = _parse_manual_date(values_by_header.get("date", ""))
    if date_error:
        errors.append(date_error)

    app_name = normalize_app_name(values_by_header.get("app_name", ""))
    if not app_name:
        errors.append("appName is required")

    access_count, access_error = _parse_manual_count(values_by_header.get("access_count", ""), field_name="accessCount")
    if access_error:
        errors.append(access_error)

    unique_user_count, unique_error = _parse_manual_count(
        values_by_header.get("unique_user_count", ""),
        field_name="uniqueUserCount",
    )
    if unique_error:
        errors.append(unique_error)

    if access_count is not None and unique_user_count is not None and unique_user_count > access_count:
        errors.append("uniqueUserCount must be less than or equal to accessCount")

    return {
        "rowNumber": row_number,
        "values": {
            "date": serialize_date(stat_date),
            "appId": app_name,
            "appName": app_name,
            "accessCount": access_count if access_count is not None else values_by_header.get("access_count", ""),
            "uniqueUserCount": unique_user_count
            if unique_user_count is not None
            else values_by_header.get("unique_user_count", ""),
            "memo": values_by_header.get("memo", "").strip(),
        },
        "errors": errors,
    }


def build_manual_app_access_preview(*, pasted_text: str, source_name: str) -> dict[str, Any]:
    """수동 붙여넣기 원문을 검증 미리보기 payload로 변환합니다.

    입력:
    - pasted_text: 스프레드시트에서 복사한 TSV/CSV 원문
    - source_name: 입력 출처 이름

    반환:
    - dict[str, Any]: summary/rows/errors preview payload

    부작용:
    - 없음

    오류:
    - 없음(검증 실패는 payload errors로 반환)
    """

    raw_headers, raw_rows = _read_paste_rows(pasted_text)
    headers = [_normalize_header(header) for header in raw_headers]
    missing_columns = [
        MANUAL_COLUMN_LABELS.get(column, column)
        for column in REQUIRED_MANUAL_COLUMNS
        if column not in headers
    ]
    top_level_errors = [f"Missing required columns: {', '.join(missing_columns)}"] if missing_columns else []

    preview_rows: list[dict[str, Any]] = []
    if not top_level_errors:
        preview_rows = [
            _build_manual_row(row_number=index + 2, headers=headers, cells=row)
            for index, row in enumerate(raw_rows)
        ]

    error_rows = sum(1 for row in preview_rows if row["errors"])
    valid_rows = len(preview_rows) - error_rows
    if not preview_rows and not top_level_errors:
        top_level_errors.append("No data rows found")

    return {
        "sourceType": MANUAL_SOURCE_TYPE,
        "sourceName": source_name,
        "expectedColumns": MANUAL_PASTE_EXPECTED_COLUMNS,
        "summary": {
            "totalRows": len(preview_rows),
            "validRows": valid_rows,
            "errorRows": error_rows + (1 if top_level_errors else 0),
        },
        "errors": top_level_errors,
        "rows": preview_rows,
    }


def _has_preview_errors(preview: dict[str, Any]) -> bool:
    """미리보기 payload에 저장 차단 오류가 있는지 확인합니다."""

    if preview.get("errors"):
        return True
    return any(row.get("errors") for row in preview.get("rows", []))


def commit_manual_app_access_stats(
    *,
    pasted_text: str,
    source_name: str,
    user: Any,
) -> dict[str, Any]:
    """검증된 수동 외부 앱 접속 집계를 저장합니다.

    입력:
    - pasted_text: 스프레드시트에서 복사한 TSV/CSV 원문
    - source_name: 입력 출처 이름
    - user: 저장 요청 사용자

    반환:
    - dict[str, Any]: 반영 요약과 preview payload

    부작용:
    - ExternalAppAccessDailyStat rows를 생성하거나 갱신합니다.

    오류:
    - ValueError: preview 오류가 있어 저장할 수 없을 때
    """

    preview = build_manual_app_access_preview(pasted_text=pasted_text, source_name=source_name)
    if _has_preview_errors(preview):
        error = ValueError("Manual access stats contain invalid rows")
        error.preview = preview  # type: ignore[attr-defined]
        raise error

    created_count = 0
    updated_count = 0
    now = timezone.now()
    with transaction.atomic():
        for row in preview["rows"]:
            values = row["values"]
            stat, created = ExternalAppAccessDailyStat.objects.update_or_create(
                app_id=values["appId"],
                stat_date=date.fromisoformat(values["date"]),
                source_name=source_name,
                defaults={
                    "app_name": values["appName"],
                    "access_count": values["accessCount"],
                    "unique_user_count": values["uniqueUserCount"],
                    "source_type": MANUAL_SOURCE_TYPE,
                    "memo": values["memo"],
                    "raw_payload": {"rowNumber": row["rowNumber"], "source": "spreadsheet_paste"},
                    "updated_by": user,
                    "updated_at": now,
                },
            )
            if created:
                stat.created_by = user
                stat.created_at = now
                stat.save(update_fields=["created_by", "created_at"])
                created_count += 1
            else:
                updated_count += 1

    return {
        **preview,
        "commit": {
            "createdRows": created_count,
            "updatedRows": updated_count,
        },
    }
