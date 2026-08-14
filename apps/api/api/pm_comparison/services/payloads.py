"""PM Comparison chart 응답 직렬화 도우미입니다."""

from __future__ import annotations

import math
from bisect import bisect_right
from typing import Any

import pandas as pd

def _json_safe_value(value: Any) -> Any:
    """JSON 직렬화 가능한 값으로 정리합니다."""

    if value is None:
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        return _json_safe_value(value.item())
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def _snake_to_camel(value: str) -> str:
    """snake_case 문자열을 camelCase로 변환합니다."""

    parts = value.split("_")
    return parts[0] + "".join(part[:1].upper() + part[1:] for part in parts[1:])


def _camelize_mapping(row: dict[str, Any]) -> dict[str, Any]:
    """dict 키를 camelCase로 변환하고 값을 JSON 안전 형태로 바꿉니다."""

    return {_snake_to_camel(key): _json_safe_value(value) for key, value in row.items()}


def _selection_int(selection: dict[str, object], key: str, default: int, minimum: int, maximum: int) -> int:
    """요청 정수 옵션을 안전한 범위로 정규화합니다."""

    try:
        value = int(selection.get(key) or default)
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _selection_float(selection: dict[str, object], key: str) -> float | None:
    """요청 실수 옵션을 반환합니다."""

    try:
        value = selection.get(key)
        if value in (None, ""):
            return None
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def _compat_row_limit(selection: dict[str, object]) -> int:
    """기존 행 목록 호환 응답의 최대 행 수를 반환합니다."""

    return _selection_int(selection, "limit", 1200, 50, 5000)


def _chart_max_points(selection: dict[str, object]) -> int:
    """series 하나당 차트에 내려줄 최대 점 수를 반환합니다."""

    return _selection_int(selection, "maxPoints", 2400, 100, 20000)


def _apply_numeric_x_range(frame: pd.DataFrame, x_column: str, selection: dict[str, object]) -> pd.DataFrame:
    """요청 X 범위가 있으면 frame을 좁힙니다."""

    start = _selection_float(selection, "xStart")
    end = _selection_float(selection, "xEnd")
    if start is None and end is None:
        return frame
    ranged = frame
    if start is not None:
        ranged = ranged[ranged[x_column] >= start]
    if end is not None:
        ranged = ranged[ranged[x_column] <= end]
    return ranged.copy()


def _downsample_xy(points: list[tuple[float, float]], max_points: int) -> list[tuple[float, float]]:
    """최소/최대 bucket 방식으로 spike를 보존하며 점 수를 줄입니다."""

    clean_points = [(x, y) for x, y in points if math.isfinite(x) and math.isfinite(y)]
    clean_points.sort(key=lambda point: point[0])
    count = len(clean_points)
    if count <= max_points:
        return clean_points
    bucket_count = max(1, max_points // 2)
    bucket_size = max(1, math.ceil(count / bucket_count))
    sampled: list[tuple[float, float]] = []
    for start in range(0, count, bucket_size):
        bucket = clean_points[start : start + bucket_size]
        if not bucket:
            continue
        low = min(bucket, key=lambda point: point[1])
        high = max(bucket, key=lambda point: point[1])
        if low[0] <= high[0]:
            sampled.extend([low, high] if low != high else [low])
        else:
            sampled.extend([high, low] if low != high else [low])
    sampled.sort(key=lambda point: point[0])
    if len(sampled) > max_points:
        step = len(sampled) / max_points
        sampled = [sampled[int(index * step)] for index in range(max_points)]
    return sampled


def _line_chart_payload(
    frame: pd.DataFrame,
    *,
    x_column: str,
    y_column: str,
    selection: dict[str, object],
    series_columns: list[str],
    label_columns: list[str] | None = None,
) -> dict[str, Any]:
    """Canvas 라인 차트용 컬럼 기반 응답을 생성합니다."""

    empty = {
        "series": [],
        "xDomain": [None, None],
        "yDomain": [None, None],
        "sourcePointCount": 0,
        "pointCount": 0,
        "downsampled": False,
        "maxPoints": _chart_max_points(selection),
    }
    if frame.empty or x_column not in frame.columns or y_column not in frame.columns:
        return empty

    work = frame.copy()
    work[x_column] = pd.to_numeric(work[x_column], errors="coerce")
    work[y_column] = pd.to_numeric(work[y_column], errors="coerce")
    work = work[work[x_column].notna() & work[y_column].notna()].copy()
    if work.empty:
        return empty
    work = _apply_numeric_x_range(work, x_column, selection)
    if work.empty:
        return empty

    max_points = _chart_max_points(selection)
    if not series_columns:
        work["_series"] = "series"
        series_columns = ["_series"]
    labels = label_columns or series_columns
    series_payload: list[dict[str, Any]] = []
    source_count = 0
    point_count = 0
    x_values: list[float] = []
    y_values: list[float] = []
    groupby: str | list[str] = series_columns[0] if len(series_columns) == 1 else series_columns
    for group_key, group in work.groupby(groupby, dropna=False, sort=True):
        group_values = group_key if isinstance(group_key, tuple) else (group_key,)
        label_parts = [str(value) for value in group_values if value not in (None, "")]
        points = [
            (float(row[x_column]), float(row[y_column]))
            for row in group[[x_column, y_column]].to_dict(orient="records")
        ]
        source_count += len(points)
        sampled = _downsample_xy(points, max_points)
        if not sampled:
            continue
        xs = [round(point[0], 6) for point in sampled]
        ys = [_json_safe_value(round(point[1], 6)) for point in sampled]
        x_values.extend(xs)
        y_values.extend(float(value) for value in ys if value is not None)
        point_count += len(sampled)
        meta = {}
        for column, value in zip(series_columns, group_values):
            meta[_snake_to_camel(column)] = _json_safe_value(value)
        label = " · ".join(label_parts) if label_parts else "series"
        if labels:
            first_row = group.iloc[0].to_dict()
            label_values = [str(first_row.get(column)) for column in labels if first_row.get(column) not in (None, "")]
            if label_values:
                label = " · ".join(label_values)
        series_payload.append(
            {
                "key": "|".join(label_parts) or f"series-{len(series_payload) + 1}",
                "label": label,
                "x": xs,
                "y": ys,
                "meta": meta,
                "sourcePointCount": len(points),
                "pointCount": len(sampled),
                "downsampled": len(sampled) < len(points),
            }
        )

    if not series_payload:
        return empty
    return {
        "series": series_payload,
        "xDomain": [min(x_values), max(x_values)] if x_values else [None, None],
        "yDomain": [min(y_values), max(y_values)] if y_values else [None, None],
        "sourcePointCount": source_count,
        "pointCount": point_count,
        "downsampled": point_count < source_count,
        "maxPoints": max_points,
    }


def _trace_chart_x_frame(frame: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    """trace frame에 차트용 숫자 X 컬럼을 추가합니다."""

    work = frame.copy()
    if "step_time" in work.columns:
        work["chart_x"] = pd.to_numeric(work["step_time"], errors="coerce")
    elif "period" in work.columns:
        work["chart_x"] = pd.to_numeric(work["period"], errors="coerce")
    elif "time" in work.columns:
        time_values = pd.to_datetime(work["time"], errors="coerce", utc=True)
        if time_values.notna().any():
            origin = time_values.dropna().min()
            work["chart_x"] = (time_values - origin).dt.total_seconds()
        else:
            work["chart_x"] = None
    else:
        work["chart_x"] = work.groupby(["cycle_index", "phase"], dropna=False).cumcount()
    if work["chart_x"].isna().all():
        work["chart_x"] = work.groupby(["cycle_index", "phase"], dropna=False).cumcount()
    return work, "chart_x"


def _trace_series_columns(frame: pd.DataFrame) -> list[str]:
    """trace 라인 차트 series 그룹 기준 컬럼을 선택합니다."""

    candidates = ["phase", "cycle_index", "trace_param_name", "ch_step", "lot_id", "slot_no", "wafer_id"]
    return [column for column in candidates if column in frame.columns]


def _heatmap_bins(selection: dict[str, object]) -> tuple[int, int]:
    """OES 히트맵 해상도를 요청 옵션에서 얻습니다."""

    x_bins = _selection_int(selection, "heatmapXBins", 1200, 20, 1600)
    y_bins = _selection_int(selection, "heatmapYBins", 100, 10, 240)
    return x_bins, y_bins


def _bin_edges(min_value: float, max_value: float, bins: int) -> list[float]:
    """균등 bin edge를 생성합니다."""

    if not math.isfinite(min_value) or not math.isfinite(max_value):
        return []
    if min_value == max_value:
        return [min_value, max_value + 1]
    step = (max_value - min_value) / bins
    return [min_value + step * index for index in range(bins + 1)]


def _value_edges(values: list[float]) -> list[float]:
    """실제 측정값을 중심으로 하는 bin edge를 생성합니다."""

    if not values:
        return []
    if len(values) == 1:
        value = values[0]
        margin = max(abs(value) * 1e-9, 0.5)
        return [value - margin, value + margin]
    edges = [values[0] - (values[1] - values[0]) / 2]
    edges.extend((values[index] + values[index + 1]) / 2 for index in range(len(values) - 1))
    edges.append(values[-1] + (values[-1] - values[-2]) / 2)
    return edges


def _bin_centers(edges: list[float]) -> list[float]:
    """bin edge에서 center 값을 생성합니다."""

    return [round((edges[index] + edges[index + 1]) / 2, 6) for index in range(len(edges) - 1)]


def _nearest_value(values: list[float], target: float) -> float | None:
    """정렬된 실제 값 목록에서 target에 가장 가까운 값을 반환합니다."""

    if not values:
        return None
    right = bisect_right(values, target)
    if right <= 0:
        return values[0]
    if right >= len(values):
        return values[-1]
    left_value = values[right - 1]
    right_value = values[right]
    return left_value if abs(target - left_value) <= abs(right_value - target) else right_value


def _representative_values_for_edges(values: list[float], edges: list[float]) -> list[float]:
    """각 bin을 대표하는 실제 측정값을 반환합니다."""

    labels: list[float] = []
    cursor = 0
    last_index = len(edges) - 2
    for edge_index in range(max(0, len(edges) - 1)):
        start = edges[edge_index]
        end = edges[edge_index + 1]
        while cursor < len(values) and values[cursor] < start:
            cursor += 1
        next_cursor = cursor
        while next_cursor < len(values) and (
            values[next_cursor] < end or (edge_index == last_index and values[next_cursor] <= end)
        ):
            next_cursor += 1
        bucket = values[cursor:next_cursor]
        if bucket:
            labels.append(bucket[len(bucket) // 2])
        else:
            center = (start + end) / 2
            nearest = _nearest_value(values, center)
            labels.append(nearest if nearest is not None else center)
        cursor = max(cursor, next_cursor)
    return [round(value, 6) for value in labels]


def _bin_index(value: float, edges: list[float]) -> int | None:
    """값이 속한 bin index를 반환합니다."""

    if not edges or not math.isfinite(value):
        return None
    if value < edges[0] or value > edges[-1]:
        return None
    if value == edges[-1]:
        return len(edges) - 2
    return max(0, min(len(edges) - 2, bisect_right(edges, value) - 1))


def _flat_average_grid(
    frame: pd.DataFrame,
    *,
    x_edges: list[float],
    y_edges: list[float],
    value_column: str,
) -> list[float | None]:
    """평균값 1차원 matrix를 생성합니다."""

    width = max(0, len(x_edges) - 1)
    height = max(0, len(y_edges) - 1)
    sums = [0.0 for _ in range(width * height)]
    counts = [0 for _ in range(width * height)]
    for row in frame[["chart_x", "chart_y", value_column]].to_dict(orient="records"):
        x_index = _bin_index(float(row["chart_x"]), x_edges)
        y_index = _bin_index(float(row["chart_y"]), y_edges)
        value = row[value_column]
        if x_index is None or y_index is None or value is None or not math.isfinite(float(value)):
            continue
        offset = y_index * width + x_index
        sums[offset] += float(value)
        counts[offset] += 1
    return [round(sums[index] / counts[index], 6) if counts[index] else None for index in range(width * height)]


def _oes_heatmap_payload(frame: pd.DataFrame, selection: dict[str, object]) -> dict[str, Any]:
    """OES step frame에서 Canvas 히트맵 matrix를 생성합니다."""

    empty = {"width": 0, "height": 0, "wavelengths": [], "phases": [], "ref": [], "comp": [], "oob": []}
    if frame.empty or "wavelength" not in frame.columns or "value" not in frame.columns:
        return empty
    work = frame.copy()
    work["chart_x"] = pd.to_numeric(work["wavelength"], errors="coerce")
    if "traj_phase" in work.columns:
        work["chart_y"] = pd.to_numeric(work["traj_phase"], errors="coerce")
    else:
        work["chart_y"] = work.groupby(["phase", "cycle_index"], dropna=False).cumcount()
    work["value"] = pd.to_numeric(work["value"], errors="coerce")
    work = work[work["chart_x"].notna() & work["chart_y"].notna() & work["value"].notna()].copy()
    if work.empty:
        return empty
    x_bins, y_bins = _heatmap_bins(selection)
    x_values = sorted(float(value) for value in work["chart_x"].dropna().unique().tolist())
    if len(x_values) <= x_bins:
        x_edges = _value_edges(x_values)
        wavelength_labels = [round(value, 6) for value in x_values]
    else:
        x_edges = _bin_edges(float(work["chart_x"].min()), float(work["chart_x"].max()), x_bins)
        wavelength_labels = _representative_values_for_edges(x_values, x_edges)
    y_edges = _bin_edges(float(work["chart_y"].min()), float(work["chart_y"].max()), min(y_bins, max(1, int(work["chart_y"].nunique()) or y_bins)))
    if len(x_edges) < 2 or len(y_edges) < 2:
        return empty
    ref_frame = work[work.get("phase", pd.Series(dtype=str)).astype(str) == "ref"]
    comp_frame = work[work.get("phase", pd.Series(dtype=str)).astype(str) != "ref"]
    ref_values = _flat_average_grid(ref_frame, x_edges=x_edges, y_edges=y_edges, value_column="value")
    comp_values = _flat_average_grid(comp_frame, x_edges=x_edges, y_edges=y_edges, value_column="value")
    oob_values: list[float | None] = []
    for ref_value, comp_value in zip(ref_values, comp_values):
        oob_values.append(
            round(comp_value - ref_value, 6)
            if ref_value is not None and comp_value is not None
            else None
        )
    width = len(x_edges) - 1
    height = len(y_edges) - 1
    return {
        "width": width,
        "height": height,
        "wavelengths": wavelength_labels,
        "phases": _bin_centers(y_edges),
        "ref": ref_values,
        "comp": comp_values,
        "oob": oob_values,
        "sourcePointCount": int(len(work)),
    }


def _oes_spectrum_payload(frame: pd.DataFrame, selection: dict[str, object]) -> dict[str, Any]:
    """OES step frame에서 wavelength별 ref/comp median 차트를 생성합니다."""

    if frame.empty or "wavelength" not in frame.columns or "value" not in frame.columns:
        return {"series": [], "xDomain": [None, None], "yDomain": [None, None], "sourcePointCount": 0, "pointCount": 0}
    work = frame.copy()
    work["wavelength"] = pd.to_numeric(work["wavelength"], errors="coerce")
    work["value"] = pd.to_numeric(work["value"], errors="coerce")
    work = work[work["wavelength"].notna() & work["value"].notna()].copy()
    if work.empty:
        return {"series": [], "xDomain": [None, None], "yDomain": [None, None], "sourcePointCount": 0, "pointCount": 0}
    work["series_phase"] = work.get("phase", pd.Series(["comp"] * len(work))).astype(str).map(lambda value: "ref" if value == "ref" else "comp")
    grouped = work.groupby(["series_phase", "wavelength"], dropna=False)["value"].median().reset_index()
    return _line_chart_payload(
        grouped,
        x_column="wavelength",
        y_column="value",
        selection=selection,
        series_columns=["series_phase"],
        label_columns=["series_phase"],
    )
