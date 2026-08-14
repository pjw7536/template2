"""PM Comparison OES score와 원본 frame 처리입니다."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from api.pm_comparison import selectors

from .contracts import DATE_COLUMN, OES_DETAIL_METADATA_COLUMNS, OES_ID_COLUMNS
from .payloads import (
    _bin_centers,
    _bin_edges,
    _camelize_mapping,
    _compat_row_limit,
    _heatmap_bins,
    _line_chart_payload,
    _oes_heatmap_payload,
    _oes_spectrum_payload,
    _representative_values_for_edges,
)
from .trace_frames import (
    _cycle_map,
    _cycle_summary,
    _filter_selected_cycles,
    _oes_rank_rows,
    _raw_cycle_frame,
    _read_frames,
    _read_score,
    _ref_cycle_rows,
    _score_ref_raw_dt_values,
    _score_trend_rows,
    _selected_ref_dates,
    _selection_with_raw_dt_values,
)

def _numeric_wavelength_columns(columns: Iterable[object]) -> list[object]:
    """wide OES schema에서 wavelength로 보이는 컬럼을 찾습니다."""

    wavelength_columns: list[object] = []
    id_names = {name.lower() for name in OES_ID_COLUMNS}
    for column in columns:
        name = str(column)
        if name.lower() in id_names:
            continue
        try:
            wavelength = float(name)
        except ValueError:
            continue
        if 100 <= wavelength <= 1200:
            wavelength_columns.append(column)
    return wavelength_columns


def _wavelength_column_pairs(columns: Iterable[object]) -> list[tuple[object, float]]:
    """wide OES wavelength 컬럼과 숫자 wavelength 값을 정렬해 반환합니다."""

    pairs: list[tuple[object, float]] = []
    for column in _numeric_wavelength_columns(columns):
        try:
            wavelength = float(str(column))
        except ValueError:
            continue
        pairs.append((column, wavelength))
    pairs.sort(key=lambda pair: pair[1])
    return pairs


def _nearest_wavelength_pair(
    wavelength_pairs: list[tuple[object, float]],
    selected_wavelength: str,
) -> list[tuple[object, float]]:
    """선택 wavelength에 가장 가까운 wide 컬럼을 반환합니다."""

    if not selected_wavelength:
        return []
    try:
        target = float(selected_wavelength)
    except (TypeError, ValueError):
        return []
    if not math.isfinite(target) or not wavelength_pairs:
        return []
    return [min(wavelength_pairs, key=lambda pair: abs(pair[1] - target))]


def _trajectory_only_oes_columns(
    files: list[Path],
    selection: dict[str, object],
    *,
    include_heatmap: bool,
    include_spectrum: bool,
    warnings: list[str],
) -> list[str] | None:
    """wavelength trajectory만 필요할 때 읽을 OES 컬럼을 좁힙니다."""

    selected_wl = str(selection.get("selectedWavelength") or "")
    if include_heatmap or include_spectrum or not selected_wl:
        return None
    for path in files:
        try:
            columns = selectors.parquet_columns(path)
        except Exception as exc:
            warnings.append(f"OES schema 읽기 실패: {path.name} ({exc})")
            continue
        wavelength_pairs = _wavelength_column_pairs(columns)
        selected_pairs = _nearest_wavelength_pair(wavelength_pairs, selected_wl)
        if not selected_pairs:
            continue
        available = set(columns)
        metadata_columns = [column for column in OES_DETAIL_METADATA_COLUMNS if column in available]
        selected_column = str(selected_pairs[0][0])
        return list(dict.fromkeys([*metadata_columns, selected_column]))
    return None


def _canonical_oes_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """OES raw 컬럼 alias를 상세 계산용 표준 컬럼으로 보강합니다."""

    work = frame.copy()
    if "rcp_step" not in work.columns and "step_seq" in work.columns:
        work["rcp_step"] = work["step_seq"]
    if "traj_phase" not in work.columns and "Time" in work.columns:
        work["traj_phase"] = work["Time"]
    return work


def _filter_oes_step_frame(frame: pd.DataFrame, selected_step: str) -> pd.DataFrame:
    """선택 step이 있으면 OES raw row를 먼저 줄입니다."""

    if not selected_step or "rcp_step" not in frame.columns:
        return frame
    return frame[frame["rcp_step"].astype(str) == selected_step].copy()


def _wide_oes_y_edges(work: pd.DataFrame, selection: dict[str, object]) -> list[float]:
    """wide OES heatmap y축 bin edge를 계산합니다."""

    _, y_bins = _heatmap_bins(selection)
    y_count = min(y_bins, max(1, int(work["chart_y"].nunique()) or y_bins))
    return _bin_edges(float(work["chart_y"].min()), float(work["chart_y"].max()), y_count)


def _wide_oes_representative_pairs(
    wavelength_pairs: list[tuple[object, float]],
    selection: dict[str, object],
) -> list[tuple[object, float]]:
    """heatmap x축 bin 수에 맞춰 대표 wavelength 컬럼을 선택합니다."""

    x_bins, _ = _heatmap_bins(selection)
    if len(wavelength_pairs) <= x_bins:
        return wavelength_pairs
    x_values = [value for _, value in wavelength_pairs]
    x_edges = _bin_edges(min(x_values), max(x_values), x_bins)
    labels = _representative_values_for_edges(x_values, x_edges)
    selected: list[tuple[object, float]] = []
    used_columns: set[object] = set()
    for label in labels:
        column, value = min(wavelength_pairs, key=lambda pair: abs(pair[1] - label))
        if column in used_columns:
            continue
        selected.append((column, value))
        used_columns.add(column)
    return selected or wavelength_pairs[:x_bins]


def _wide_oes_phase_grid(
    frame: pd.DataFrame,
    wavelength_pairs: list[tuple[object, float]],
    y_edges: list[float],
) -> list[float | None]:
    """wide OES row를 y축 bin별 wavelength 평균 matrix로 변환합니다."""

    width = len(wavelength_pairs)
    height = max(0, len(y_edges) - 1)
    if frame.empty or not width or not height:
        return [None for _ in range(width * height)]

    columns = [column for column, _ in wavelength_pairs]
    try:
        numeric_values = frame[columns].to_numpy(dtype=np.float32, copy=False)
    except (TypeError, ValueError):
        numeric_values = frame[columns].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=np.float32, copy=False)
    y_values = pd.to_numeric(frame["chart_y"], errors="coerce").to_numpy(dtype=np.float64, copy=False)
    values: list[float | None] = []
    for edge_index in range(height):
        start = y_edges[edge_index]
        end = y_edges[edge_index + 1]
        if edge_index == height - 1:
            mask = (y_values >= start) & (y_values <= end)
        else:
            mask = (y_values >= start) & (y_values < end)
        if not mask.any():
            values.extend([None for _ in range(width)])
            continue
        bucket = numeric_values[mask]
        finite = np.isfinite(bucket)
        counts = finite.sum(axis=0)
        sums = np.where(finite, bucket, 0.0).sum(axis=0, dtype=np.float64)
        means = np.divide(sums, counts, out=np.full(width, np.nan, dtype=np.float64), where=counts > 0)
        for value in means.tolist():
            if value is None or not math.isfinite(float(value)):
                values.append(None)
            else:
                values.append(round(float(value), 6))
    return values


def _wide_oes_heatmap_payload(
    frame: pd.DataFrame,
    wavelength_pairs: list[tuple[object, float]],
    selection: dict[str, object],
) -> dict[str, Any]:
    """wide OES step frame에서 melt 없이 heatmap matrix를 생성합니다."""

    empty = {"width": 0, "height": 0, "wavelengths": [], "phases": [], "ref": [], "comp": [], "oob": []}
    if frame.empty or not wavelength_pairs:
        return empty
    work = frame.copy()
    if "traj_phase" in work.columns:
        work["chart_y"] = pd.to_numeric(work["traj_phase"], errors="coerce")
    else:
        work["chart_y"] = work.groupby(["phase", "cycle_index"], dropna=False).cumcount()
    work = work[work["chart_y"].notna()].copy()
    if work.empty:
        return empty

    selected_pairs = _wide_oes_representative_pairs(wavelength_pairs, selection)
    y_edges = _wide_oes_y_edges(work, selection)
    if len(y_edges) < 2:
        return empty
    ref_frame = work[work.get("phase", pd.Series(dtype=str)).astype(str) == "ref"]
    comp_frame = work[work.get("phase", pd.Series(dtype=str)).astype(str) != "ref"]
    ref_values = _wide_oes_phase_grid(ref_frame, selected_pairs, y_edges)
    comp_values = _wide_oes_phase_grid(comp_frame, selected_pairs, y_edges)
    oob_values: list[float | None] = []
    for ref_value, comp_value in zip(ref_values, comp_values):
        oob_values.append(
            round(comp_value - ref_value, 6)
            if ref_value is not None and comp_value is not None
            else None
        )
    return {
        "width": len(selected_pairs),
        "height": len(y_edges) - 1,
        "wavelengths": [round(value, 6) for _, value in selected_pairs],
        "phases": _bin_centers(y_edges),
        "ref": ref_values,
        "comp": comp_values,
        "oob": oob_values,
        "sourcePointCount": int(len(work) * len(wavelength_pairs)),
    }


def _wide_oes_spectrum_payload(
    frame: pd.DataFrame,
    wavelength_pairs: list[tuple[object, float]],
    selection: dict[str, object],
) -> dict[str, Any]:
    """wide OES step frame에서 phase별 median spectrum 차트를 생성합니다."""

    empty = {"series": [], "xDomain": [None, None], "yDomain": [None, None], "sourcePointCount": 0, "pointCount": 0}
    if frame.empty or not wavelength_pairs:
        return empty

    rows: list[dict[str, Any]] = []
    columns = [column for column, _ in wavelength_pairs]
    for phase_value, phase_frame in [
        ("ref", frame[frame.get("phase", pd.Series(dtype=str)).astype(str) == "ref"]),
        ("comp", frame[frame.get("phase", pd.Series(dtype=str)).astype(str) != "ref"]),
    ]:
        if phase_frame.empty:
            continue
        numeric_values = phase_frame[columns].apply(pd.to_numeric, errors="coerce")
        medians = numeric_values.median(axis=0, skipna=True)
        for column, wavelength in wavelength_pairs:
            value = medians.get(column)
            if value is None or not math.isfinite(float(value)):
                continue
            rows.append({"series_phase": phase_value, "wavelength": wavelength, "value": float(value)})
    if not rows:
        return empty
    return _line_chart_payload(
        pd.DataFrame(rows),
        x_column="wavelength",
        y_column="value",
        selection=selection,
        series_columns=["series_phase"],
        label_columns=["series_phase"],
    )


def _wide_oes_long_frame(
    frame: pd.DataFrame,
    wavelength_pairs: list[tuple[object, float]],
    *,
    limit: int | None = None,
) -> pd.DataFrame:
    """wide OES frame 일부를 호환용 long row로 변환합니다."""

    if frame.empty or not wavelength_pairs:
        return pd.DataFrame()
    metadata_columns = [
        column
        for column in [
            "traj_phase",
            "phase",
            "cycle_index",
            "pm_date",
            "rcp_step",
            "lot_id",
            "slot_no",
            "slot_id",
            "group",
            "wafer_end_time",
        ]
        if column in frame.columns
    ]
    columns = [column for column, _ in wavelength_pairs]
    value_by_column = {column: wavelength for column, wavelength in wavelength_pairs}
    long_frame = frame[metadata_columns + columns].melt(
        id_vars=metadata_columns,
        value_vars=columns,
        var_name="wavelength",
        value_name="value",
    )
    long_frame["wavelength"] = long_frame["wavelength"].map(value_by_column)
    long_frame["value"] = pd.to_numeric(long_frame["value"], errors="coerce")
    long_frame = long_frame[long_frame["value"].notna()].copy()
    if limit is not None:
        long_frame = long_frame.head(limit)
    return long_frame


def _empty_wide_oes_detail_payload() -> dict[str, Any]:
    """wide OES 상세 계산이 비었을 때 동일한 응답 형태를 반환합니다."""

    return {
        "row_count": 0,
        "detail_rows": [],
        "heatmap": {"width": 0, "height": 0, "wavelengths": [], "phases": [], "ref": [], "comp": [], "oob": []},
        "line_chart": {"series": [], "xDomain": [None, None], "yDomain": [None, None]},
        "spectrum_chart": {"series": [], "xDomain": [None, None], "yDomain": [None, None]},
    }


def _wide_oes_detail_payload(
    frame: pd.DataFrame,
    selection: dict[str, object],
    *,
    cycle_map: dict[str, int],
    selected_ref_dates: set[str],
    selected_step: str,
    warnings: list[str],
) -> dict[str, Any] | None:
    """wide OES raw에서 큰 long frame 없이 상세 payload를 생성합니다."""

    wavelength_pairs = _wavelength_column_pairs(frame.columns)
    if not wavelength_pairs:
        return None
    work = _canonical_oes_columns(frame)
    work = _filter_oes_step_frame(work, selected_step)
    if work.empty:
        return _empty_wide_oes_detail_payload()
    if {DATE_COLUMN, "rcp_step"}.difference(work.columns):
        warnings.append("OES data에 날짜/rcp_step 컬럼이 없어 상세 plot을 건너뜁니다.")
        return _empty_wide_oes_detail_payload()

    work = _filter_selected_cycles(_raw_cycle_frame(work, cycle_map), selected_ref_dates)
    if work.empty:
        return _empty_wide_oes_detail_payload()

    selected_wl = str(selection.get("selectedWavelength") or "")
    include_heatmap = bool(selection.get("includeOesHeatmap", True))
    include_spectrum = bool(selection.get("includeOesSpectrum", True))
    source_point_count = int(len(work) * len(wavelength_pairs))
    heatmap = (
        _wide_oes_heatmap_payload(work, wavelength_pairs, selection)
        if include_heatmap
        else {"width": 0, "height": 0, "wavelengths": [], "phases": [], "ref": [], "comp": [], "oob": []}
    )
    spectrum_chart = (
        _wide_oes_spectrum_payload(work, wavelength_pairs, selection)
        if include_spectrum
        else {"series": [], "xDomain": [None, None], "yDomain": [None, None]}
    )

    line_chart = {"series": [], "xDomain": [None, None], "yDomain": [None, None]}
    line_frame = pd.DataFrame()
    selected_pairs = _nearest_wavelength_pair(wavelength_pairs, selected_wl)
    if selected_pairs:
        line_frame = _wide_oes_long_frame(work, selected_pairs)
        if "traj_phase" in line_frame.columns:
            line_frame["chart_x"] = pd.to_numeric(line_frame["traj_phase"], errors="coerce")
        else:
            line_frame["chart_x"] = line_frame.groupby(["phase", "cycle_index"], dropna=False).cumcount()
        line_chart = _line_chart_payload(
            line_frame,
            x_column="chart_x",
            y_column="value",
            selection=selection,
            series_columns=[
                column
                for column in ["phase", "cycle_index", "lot_id", "slot_no", "slot_id", "group"]
                if column in line_frame.columns
            ],
            label_columns=["phase", "lot_id", "slot_no", "slot_id", "group"],
        )

    compat_limit = _compat_row_limit(selection)
    if selected_pairs:
        detail_frame = line_frame.head(compat_limit)
        row_count = int(len(line_frame))
    else:
        rows_per_wavelength = max(1, len(work))
        sample_column_count = max(1, min(len(wavelength_pairs), math.ceil(compat_limit / rows_per_wavelength)))
        detail_frame = _wide_oes_long_frame(work, wavelength_pairs[:sample_column_count], limit=compat_limit)
        row_count = source_point_count

    columns = [
        "traj_phase",
        "phase",
        "cycle_index",
        "pm_date",
        "rcp_step",
        "wavelength",
        "value",
        "lot_id",
        "slot_no",
        "slot_id",
        "group",
        "wafer_end_time",
    ]
    visible_columns = [column for column in columns if column in detail_frame.columns]
    detail_rows = [_camelize_mapping(row) for row in detail_frame[visible_columns].to_dict(orient="records")]
    return {
        "row_count": row_count,
        "detail_rows": detail_rows,
        "heatmap": heatmap,
        "line_chart": line_chart,
        "spectrum_chart": spectrum_chart,
    }


def _normalize_oes(frame: pd.DataFrame, warnings: list[str]) -> pd.DataFrame:
    """OES wide/long schema를 step-wavelength-value long schema로 정규화합니다."""

    if {"wavelength", "value"}.issubset(frame.columns):
        long_frame = frame.copy()
    else:
        wavelength_columns = _numeric_wavelength_columns(frame.columns)
        if not wavelength_columns:
            warnings.append("OES data에서 wavelength 컬럼을 찾지 못했습니다.")
            return frame.iloc[0:0].copy()
        id_columns = [column for column in frame.columns if column not in wavelength_columns]
        long_frame = frame.melt(
            id_vars=id_columns,
            value_vars=wavelength_columns,
            var_name="wavelength",
            value_name="value",
        )

    if "rcp_step" not in long_frame.columns and "step_seq" in long_frame.columns:
        long_frame["rcp_step"] = long_frame["step_seq"]
    if "rcp_step" not in long_frame.columns:
        long_frame["rcp_step"] = "unknown"
    if "traj_phase" not in long_frame.columns and "Time" in long_frame.columns:
        long_frame["traj_phase"] = long_frame["Time"]
    long_frame["wavelength"] = pd.to_numeric(long_frame["wavelength"], errors="coerce")
    long_frame["value"] = pd.to_numeric(long_frame["value"], errors="coerce")
    return long_frame[long_frame["wavelength"].notna() & long_frame["value"].notna()].copy()


def _prepare_oes(selection: dict[str, object], current_pm_date: str, warnings: list[str]) -> dict[str, Any]:
    """result 기반 OES rank와 data 기반 spectrum 상세를 준비합니다."""

    score_frame, score_file_count = _read_score(selection, "oes", warnings)
    cycle_map = _cycle_map(score_frame, current_pm_date)
    selected_ref_dates = _selected_ref_dates(selection, cycle_map)
    rank_rows = _oes_rank_rows(score_frame, current_pm_date)
    selected_step = str(selection.get("selectedStep") or (rank_rows[0].get("step") if rank_rows else "") or "")

    detail_rows: list[dict[str, Any]] = []
    heatmap: dict[str, Any] = {"width": 0, "height": 0, "wavelengths": [], "phases": [], "ref": [], "comp": [], "oob": []}
    line_chart: dict[str, Any] = {"series": [], "xDomain": [None, None], "yDomain": [None, None]}
    spectrum_chart: dict[str, Any] = {"series": [], "xDomain": [None, None], "yDomain": [None, None]}
    raw_file_count = 0
    row_count = 0
    include_oes_heatmap = bool(selection.get("includeOesHeatmap", True))
    include_oes_spectrum = bool(selection.get("includeOesSpectrum", True))
    if selection.get("includeDetails", True) and selection.get("includeOesDetails", True):
        _oes_source = str(selection.get("oesDataSource") or "oes")
        ref_dt_values = _score_ref_raw_dt_values(score_frame, current_pm_date, selected_ref_dates)
        raw_selection = _selection_with_raw_dt_values(
            selection,
            current_pm_date,
            selected_ref_dates,
            ref_dt_values=ref_dt_values,
        )
        oes_step_filters = [("rcp_step", "==", selected_step)] if selected_step else None
        files = list(selectors.iter_raw_files(raw_selection, data_source=_oes_source, trace_param_names=[]))
        read_columns = _trajectory_only_oes_columns(
            files,
            selection,
            include_heatmap=include_oes_heatmap,
            include_spectrum=include_oes_spectrum,
            warnings=warnings,
        )
        frames, raw_file_count = _read_frames(files, columns=read_columns, filters=oes_step_filters, warnings=warnings)
        if not frames:
            files = list(selectors.iter_raw_files(raw_selection, data_source="oes_processed", trace_param_names=[]))
            read_columns = _trajectory_only_oes_columns(
                files,
                selection,
                include_heatmap=include_oes_heatmap,
                include_spectrum=include_oes_spectrum,
                warnings=warnings,
            )
            frames, raw_file_count = _read_frames(files, columns=read_columns, filters=oes_step_filters, warnings=warnings)
        if frames:
            raw_frame = pd.concat(frames, ignore_index=True)
            wide_payload = _wide_oes_detail_payload(
                raw_frame,
                selection,
                cycle_map=cycle_map,
                selected_ref_dates=selected_ref_dates,
                selected_step=selected_step,
                warnings=warnings,
            )
            if wide_payload is not None:
                row_count = wide_payload["row_count"]
                detail_rows = wide_payload["detail_rows"]
                heatmap = wide_payload["heatmap"]
                line_chart = wide_payload["line_chart"]
                spectrum_chart = wide_payload["spectrum_chart"]
            else:
                frame = _normalize_oes(raw_frame, warnings)
                if {DATE_COLUMN, "rcp_step", "wavelength", "value"}.issubset(frame.columns):
                    if "phase" in frame.columns:
                        frame = frame.rename(columns={"phase": "traj_phase"})
                    frame = _filter_selected_cycles(_raw_cycle_frame(frame, cycle_map), selected_ref_dates)
                    frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
                    if selected_step:
                        frame = frame[frame["rcp_step"].astype(str) == selected_step]
                    frame = frame[frame["value"].notna()].copy()
                    if "traj_phase" in frame.columns:
                        frame["traj_phase"] = pd.to_numeric(frame["traj_phase"], errors="coerce")
                        frame = frame[frame["traj_phase"].notna()]
                        frame = frame.sort_values(["cycle_index", "traj_phase"])
                    else:
                        frame = frame.sort_values(["cycle_index", "wavelength"])
                    step_frame = frame.copy()
                    if include_oes_heatmap:
                        heatmap = _oes_heatmap_payload(step_frame, selection)
                    if include_oes_spectrum:
                        spectrum_chart = _oes_spectrum_payload(step_frame, selection)
                    selected_wl = str(selection.get("selectedWavelength") or "")
                    if selected_wl:
                        try:
                            wl_val = float(selected_wl)
                            frame = step_frame[step_frame["wavelength"].round(1) == round(wl_val, 1)].copy()
                        except (ValueError, TypeError):
                            frame = step_frame.iloc[0:0].copy()
                    else:
                        frame = step_frame
                    if "traj_phase" in frame.columns:
                        frame["chart_x"] = pd.to_numeric(frame["traj_phase"], errors="coerce")
                    else:
                        frame["chart_x"] = frame.groupby(["phase", "cycle_index"], dropna=False).cumcount()
                    row_count = int(len(frame))
                    line_chart = _line_chart_payload(
                        frame,
                        x_column="chart_x",
                        y_column="value",
                        selection=selection,
                        series_columns=[
                            column
                            for column in ["phase", "cycle_index", "lot_id", "slot_no", "slot_id", "group"]
                            if column in frame.columns
                        ],
                        label_columns=["phase", "lot_id", "slot_no", "slot_id", "group"],
                    )
                    columns = [
                        "traj_phase",
                        "phase",
                        "cycle_index",
                        "pm_date",
                        "rcp_step",
                        "wavelength",
                        "value",
                        "lot_id",
                        "slot_no",
                        "slot_id",
                        "group",
                        "wafer_end_time",
                    ]
                    visible_columns = [column for column in columns if column in frame.columns]
                    compat_frame = frame.head(_compat_row_limit(selection))
                    detail_rows = [_camelize_mapping(row) for row in compat_frame[visible_columns].to_dict(orient="records")]
                else:
                    warnings.append("OES data에 날짜/rcp_step/wavelength/value 컬럼이 없어 상세 plot을 건너뜁니다.")

    step_rows = []
    if rank_rows:
        rank_frame = pd.DataFrame(rank_rows)
        if {"step", "score", "wavelength"}.issubset(rank_frame.columns):
            grouped = (
                rank_frame.groupby("step", dropna=False)
                .agg(wavelengthCount=("wavelength", "count"), minScore=("score", "min"), maxScore=("score", "max"))
                .reset_index()
                .sort_values(["minScore", "step"], ascending=[True, True])
            )
            step_rows = grouped.to_dict(orient="records")

    worst = rank_rows[0] if rank_rows else None
    return {
        "fileCount": raw_file_count,
        "scoreFileCount": score_file_count,
        "rowCount": row_count,
        "worstStep": worst.get("step") if worst else None,
        "worstWavelength": worst,
        "summaryRows": rank_rows,
        "stepRows": step_rows,
        "detailRows": detail_rows,
        "trajectoryRows": detail_rows,
        "heatmap": heatmap,
        "lineChart": line_chart,
        "spectrumChart": spectrum_chart,
        "scoreTrendRows": _score_trend_rows(score_frame, cycle_map, selected_ref_dates),
        "cycleSummary": _cycle_summary(score_frame, cycle_map, selected_ref_dates),
        "refCycles": _ref_cycle_rows(cycle_map, selected_ref_dates),
    }
