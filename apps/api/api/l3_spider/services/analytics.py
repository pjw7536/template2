"""L3 Spider DataFrame 정규화와 응답 변환 계산을 제공합니다."""

from __future__ import annotations

import json
import math
from typing import Any

from django.conf import settings

import numpy as np
import pandas as pd

ANOMALY_STATUSES = {"Warning", "High Risk Chamber"}


def _snake_to_camel(value: str) -> str:
    """snake_case 컬럼명을 camelCase 응답 키로 변환합니다."""

    parts = value.split("_")
    return parts[0] + "".join(part[:1].upper() + part[1:] for part in parts[1:])


def _json_safe_value(value: Any) -> Any:
    """NaN과 무한대 및 NumPy scalar를 JSON 안전 값으로 변환합니다."""

    if value is None:
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return _json_safe_value(value.item())
    return value


def _camelize_mapping(row: dict[str, Any]) -> dict[str, Any]:
    """mapping의 키와 값을 API 응답 계약에 맞게 변환합니다."""

    return {_snake_to_camel(key): _json_safe_value(value) for key, value in row.items()}


def _normalize_display_status(frame: pd.DataFrame) -> pd.DataFrame:
    """legacy 상태 컬럼명과 Single Spike 값을 현재 계약으로 정규화합니다."""

    if "display status" in frame.columns and "display_status" not in frame.columns:
        frame = frame.rename(columns={"display status": "display_status"})
    if "display_status" in frame.columns:
        frame["display_status"] = frame["display_status"].replace({"Single Spike": "Warning"})
    return frame


def _empty_stats() -> dict[str, int]:
    """데이터가 없을 때 사용하는 통계 응답을 반환합니다."""

    return {
        "total": 0,
        "normal": 0,
        "warning": 0,
        "risk": 0,
        "anomalySteps": 0,
        "highRiskEqpchs": 0,
    }


def _has_required_selection(selection: dict[str, object]) -> bool:
    """데이터 조회에 필요한 계층 선택값이 모두 있는지 확인합니다."""

    return all(selection.get(key) for key in ("dates", "lineIds", "processIds", "edsSteps"))


def _make_selection_cache_key(selection: dict[str, object]) -> str:
    """선택 순서와 무관한 안정적인 캐시 키를 생성합니다."""

    return json.dumps(
        {
            "dates": sorted(selection.get("dates") or []),
            "lineIds": sorted(selection.get("lineIds") or []),
            "lineNames": sorted(selection.get("lineNames") or []),
            "processIds": sorted(selection.get("processIds") or []),
            "edsSteps": sorted(selection.get("edsSteps") or []),
        },
        sort_keys=True,
    )


def _sample_chart_points(frame: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    """이상값을 보존하면서 차트 패널별 최대 표시 점 수를 제한합니다."""

    max_points = getattr(settings, "L3_SPIDER_MAX_CHART_POINTS_PER_PANEL", 2000)
    if max_points <= 0 or frame.empty:
        return frame

    sampled: list[pd.DataFrame] = []
    available_group_columns = [column for column in group_columns if column in frame.columns]
    if not available_group_columns:
        return frame.head(max_points)

    for _, group in frame.groupby(available_group_columns, sort=False, dropna=False):
        if len(group) <= max_points:
            sampled.append(group)
            continue

        if "display_status" in group.columns:
            anomaly = group[group["display_status"].isin(ANOMALY_STATUSES)]
        else:
            anomaly = group.iloc[0:0]
        remaining_slots = max_points - len(anomaly)
        if remaining_slots <= 0:
            sampled.append(anomaly)
            continue

        others = group[~group.index.isin(anomaly.index)]
        sampled.append(
            pd.concat(
                [
                    anomaly,
                    others.sample(n=min(remaining_slots, len(others)), random_state=42),
                ]
            )
        )

    return pd.concat(sampled, ignore_index=True) if sampled else frame.iloc[0:0]


def _dataframe_to_columnar(merged: pd.DataFrame) -> dict[str, object]:
    """DataFrame을 중복 컬럼명을 제거한 columnar 응답으로 변환합니다."""

    float32_columns = merged.select_dtypes(include=["float32"]).columns
    if len(float32_columns):
        merged = merged.copy()
        merged[float32_columns] = merged[float32_columns].astype("float64")

    merged = merged.replace([np.inf, -np.inf], np.nan)
    columns = [_snake_to_camel(column) for column in merged.columns]
    column_data: list[list[object]] = []

    for column in merged.columns:
        series = merged[column]
        if pd.api.types.is_float_dtype(series):
            raw_values = series.tolist()
            column_data.append([None if value != value else value for value in raw_values])
        elif pd.api.types.is_integer_dtype(series):
            column_data.append(series.tolist())
        else:
            column_data.append([None if pd.isna(value) else value for value in series])

    return {"cols": columns, "colData": column_data}


__all__ = [
    "ANOMALY_STATUSES",
    "_camelize_mapping",
    "_dataframe_to_columnar",
    "_empty_stats",
    "_has_required_selection",
    "_json_safe_value",
    "_make_selection_cache_key",
    "_normalize_display_status",
    "_sample_chart_points",
    "_snake_to_camel",
]
