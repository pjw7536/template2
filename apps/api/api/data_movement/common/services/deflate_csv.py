"""deflate CSV 파일을 Polars DataFrame으로 읽는 공통 헬퍼입니다."""

from __future__ import annotations

import csv
import io
import zlib
from pathlib import Path
from typing import Any, Sequence

DATETIME_FORMATS = (
    "%Y-%m-%d %H:%M:%S%.f%#z",
    "%Y-%m-%dT%H:%M:%S%.f%#z",
    "%Y-%m-%d %H:%M:%S%.f",
    "%Y-%m-%dT%H:%M:%S%.f",
)


def _load_polars() -> Any:
    """Polars 의존성을 지연 로드하고 누락 시 명확한 오류를 발생시킵니다."""

    try:
        import polars as pl
    except ImportError as exc:  # pragma: no cover - 배포 의존성 누락 방어
        raise RuntimeError("polars 패키지가 필요합니다. apps/api/requirements.txt를 설치하세요.") from exc
    return pl


def _validate_column_count(*, raw: bytes, separator: str, expected_count: int) -> None:
    """헤더 없는 CSV의 각 non-empty row 컬럼 수가 계약과 같은지 검증합니다."""

    text = raw.decode("utf-8", errors="replace")
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=separator)
    for row_index, row in enumerate(reader, start=1):
        if not row or all(value == "" for value in row):
            continue
        if len(row) != expected_count:
            raise ValueError(
                f"CSV row {row_index} 컬럼 수가 올바르지 않습니다: "
                f"expected={expected_count}, actual={len(row)}"
            )


def read_deflate_csv_file(
    *,
    file_path: Path,
    columns: Sequence[str],
    datetime_columns: Sequence[str],
    float_columns: Sequence[str],
    separator: str = "\x03",
    strict_column_count: bool = False,
) -> Any:
    """deflate 압축 CSV를 읽고 테이블 spec 기준으로 타입을 변환합니다."""

    pl = _load_polars()

    with file_path.open("rb") as handle:
        raw = zlib.decompress(handle.read())

    if strict_column_count:
        _validate_column_count(raw=raw, separator=separator, expected_count=len(columns))

    frame = pl.read_csv(
        io.BytesIO(raw),
        separator=separator,
        has_header=False,
        new_columns=list(columns),
        encoding="utf8-lossy",
        null_values=["null", "NULL", ""],
        schema_overrides={column: pl.Utf8 for column in columns},
        ignore_errors=True,
        truncate_ragged_lines=True,
    )

    datetime_exprs = [
        pl.coalesce(
            [
                pl.col(column)
                .str.strip_chars()
                .str.strptime(pl.Datetime(time_zone="UTC"), date_format, strict=False)
                for date_format in DATETIME_FORMATS
            ]
        ).alias(column)
        for column in datetime_columns
    ]
    if datetime_exprs:
        frame = frame.with_columns(datetime_exprs)

    float_exprs = [
        pl.col(column).str.strip_chars().cast(pl.Float64, strict=False)
        for column in float_columns
    ]
    if float_exprs:
        frame = frame.with_columns(float_exprs)

    return frame
