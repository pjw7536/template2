"""PM Comparison trace score와 원본 frame 처리입니다."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from api.pm_comparison import selectors

from .contracts import DATE_COLUMN, SCORE_COLUMNS, SCORE_FRAME_COLUMNS, TRACE_COLUMNS
from .payloads import (
    _camelize_mapping,
    _compat_row_limit,
    _line_chart_payload,
    _trace_chart_x_frame,
    _trace_series_columns,
)

def _date_key(value: Any) -> str:
    """PM 날짜 값을 비교 가능한 YYYY-MM-DD 문자열로 정규화합니다."""

    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert("UTC").tz_localize(None)
    return timestamp.date().isoformat()


def _ref_date_values(value: Any) -> list[Any]:
    """score ref_dates 값을 원본 날짜 후보 목록으로 펼칩니다."""

    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        if not text or text.lower() in {"nan", "none", "null"}:
            return []
        if text.startswith("[") and text.endswith("]"):
            try:
                return _ref_date_values(ast.literal_eval(text))
            except (SyntaxError, ValueError):
                return [text]
        return [text]
    if isinstance(value, (list, tuple, set, np.ndarray, pd.Series)):
        values: list[Any] = []
        for item in value:
            values.extend(_ref_date_values(item))
        return values
    try:
        if pd.isna(value):
            return []
    except (TypeError, ValueError):
        pass
    return [value]


def _selected_pm_date(selection: dict[str, object]) -> str:
    """요청에서 현재 PM 날짜를 추출합니다."""

    return _date_key(selection["pmTimestamp"])


def _safe_date_key(value: Any) -> str | None:
    """날짜로 해석 가능한 값을 YYYY-MM-DD로 정리합니다."""

    if value in (None, ""):
        return None
    try:
        return _date_key(value)
    except (TypeError, ValueError):
        text = str(value).strip()
        if len(text) >= 10 and text[4] == "-" and text[7] == "-":
            return text[:10]
        if len(text) >= 8 and text[:8].isdigit():
            return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return None


def _plain_dir_value(part: str) -> str:
    """plain 경로 segment에서 key=value와 일반 값을 모두 지원합니다."""

    if "=" in part:
        return part.split("=", 1)[1]
    return part


def _plain_oes_filename_values(path: Path) -> dict[str, str]:
    """DASHBOARD_SPEC OES 파일명에서 metadata를 추출합니다."""

    fields = path.stem.split("#")
    if len(fields) < 11:
        return {}
    values = {
        "line_id": fields[0],
        "process_id": fields[1],
        "step_seq": fields[2],
        "rcp_step": fields[3],
        "ppid": fields[4],
        "recipe_id": fields[5],
        "eqp_id": fields[6],
        "chamber_id": fields[7],
        "fdc_bin": fields[7],
        "bin_id": fields[7],
        "lot_id": fields[8],
        "slot_no": fields[9],
        "slot_id": fields[9],
        "wafer_end_time": fields[10],
    }
    return {key: value for key, value in values.items() if value not in (None, "")}


def _plain_oes_path_values(path: Path) -> dict[str, str]:
    """plain OES 경로와 파일명에서 누락 metadata를 추출합니다."""

    try:
        raw_root = selectors.ensure_dataset_root(selectors.RAW_DIR_NAME).resolve()
        parts = path.resolve().relative_to(raw_root).parts
    except (FileNotFoundError, NotADirectoryError, OSError, ValueError):
        return {}
    if "oes" not in parts:
        return {}
    source_index = parts.index("oes")
    if source_index < 4:
        return {}

    values = {
        "line_id": parts[0],
        "eqp_id": parts[1],
        "fdc_bin": parts[2],
        "chamber_id": parts[2],
        "bin_id": parts[2],
        "dt": parts[3],
        "data_source": "oes",
    }
    pm_date = _safe_date_key(parts[3])
    if pm_date:
        values[DATE_COLUMN] = pm_date
    if len(parts) > source_index + 1:
        values["type"] = _plain_dir_value(parts[source_index + 1])
    if len(parts) > source_index + 2:
        values["step_seq"] = _plain_dir_value(parts[source_index + 2])
    if len(parts) > source_index + 3:
        values["ppid"] = _plain_dir_value(parts[source_index + 3])
    if len(parts) > source_index + 4:
        values["recipe_id"] = _plain_dir_value(parts[source_index + 4])
    if len(parts) > source_index + 5:
        values["lot_id"] = _plain_dir_value(parts[source_index + 5])
    if len(parts) > source_index + 6:
        slot_value = _plain_dir_value(parts[source_index + 6])
        values["slot_no"] = slot_value
        values["slot_id"] = slot_value

    filename_values = _plain_oes_filename_values(path)
    values.update(filename_values)
    if DATE_COLUMN not in values:
        wafer_date = _safe_date_key(filename_values.get("wafer_end_time"))
        if wafer_date:
            values[DATE_COLUMN] = wafer_date
    return values


def _fill_metadata_column(frame: pd.DataFrame, key: str, value: str) -> None:
    """frame 컬럼이 없거나 비어 있을 때 metadata 값을 채웁니다."""

    if value in (None, ""):
        return
    if key not in frame.columns:
        frame[key] = value
        return
    missing = frame[key].isna()
    try:
        missing = missing | (frame[key].astype(str) == "")
    except (TypeError, ValueError):
        pass
    if missing.any():
        frame.loc[missing, key] = value


def _apply_partitions(frame: pd.DataFrame, path: Path) -> pd.DataFrame:
    """파일 경로 partition 값을 누락 컬럼에 보강합니다."""

    partitions = {
        **selectors.parse_partition_values(path),
        **_plain_oes_path_values(path),
    }
    for key, value in partitions.items():
        _fill_metadata_column(frame, key, value)
    return frame


def _read_frames(
    files: Iterable[Path],
    *,
    columns: list[str] | None,
    filters: list[tuple[str, str, Any]] | None = None,
    warnings: list[str],
) -> tuple[list[pd.DataFrame], int]:
    """후보 파일을 DataFrame 목록으로 읽습니다."""

    frames: list[pd.DataFrame] = []
    file_count = 0
    for path in files:
        file_count += 1
        try:
            frame = selectors.read_parquet(path, columns, filters=filters)
            frames.append(_apply_partitions(frame, path))
        except Exception as exc:
            warnings.append(f"읽기 실패: {path.name} ({exc})")
    return frames, file_count


def _normalize_score_frame(frame: pd.DataFrame, selection: dict[str, object], data_type: str) -> pd.DataFrame:
    """result frame을 표준 컬럼과 요청 조건으로 정리합니다."""

    if frame.empty:
        return pd.DataFrame(columns=SCORE_FRAME_COLUMNS)
    for column in SCORE_COLUMNS:
        if column not in frame.columns:
            frame[column] = None
    frame = frame.copy()
    frame["line_id"] = frame["line_id"].fillna(selection.get("lineId"))
    frame["eqp_id"] = frame["eqp_id"].fillna(selection.get("eqpId"))
    chamber_id = str(selection.get("chamberId") or selection.get("fdcBin") or "")
    frame["chamber_id"] = frame["chamber_id"].fillna(chamber_id)
    frame["type"] = frame["type"].fillna(selection.get("type"))
    frame["data_type"] = frame["data_type"].fillna(data_type)
    mask = (
        (frame["line_id"].astype(str) == str(selection.get("lineId")))
        & (frame["eqp_id"].astype(str) == str(selection.get("eqpId")))
        & (frame["type"].astype(str) == str(selection.get("type")))
        & (frame["data_type"].astype(str) == data_type)
    )
    if chamber_id:
        mask = mask & (frame["chamber_id"].astype(str) == chamber_id)
    frame = frame[mask].copy()
    if DATE_COLUMN not in frame.columns or "score" not in frame.columns:
        return frame.iloc[0:0].copy()
    frame["pm_date"] = frame[DATE_COLUMN].map(_date_key)
    frame["score"] = pd.to_numeric(frame["score"], errors="coerce")
    return frame[frame["score"].notna()].copy()


def _read_score(selection: dict[str, object], data_type: str, warnings: list[str]) -> tuple[pd.DataFrame, int]:
    """result를 읽어 표준 frame으로 반환합니다."""

    files = selectors.iter_score_files(selection, data_type=data_type)
    frames, file_count = _read_frames(files, columns=SCORE_COLUMNS, warnings=warnings)
    if not frames:
        return pd.DataFrame(columns=SCORE_FRAME_COLUMNS), file_count
    frame = _normalize_score_frame(pd.concat(frames, ignore_index=True), selection, data_type)
    return frame, file_count


def _cycle_map(score_frame: pd.DataFrame, current_pm_date: str) -> dict[str, int]:
    """현재 PM 날짜 기준 상대 cycle index를 계산합니다."""

    dates = {
        date
        for date in score_frame.get("pm_date", pd.Series(dtype=str)).dropna().unique().tolist()
        if str(date) <= current_pm_date
    }
    if "ref_dates" in score_frame.columns and "pm_date" in score_frame.columns:
        current_rows = score_frame[score_frame["pm_date"] == current_pm_date]
        for value in current_rows["ref_dates"].tolist():
            for ref_value in _ref_date_values(value):
                try:
                    ref_date = _date_key(ref_value)
                except (TypeError, ValueError):
                    continue
                if ref_date <= current_pm_date:
                    dates.add(ref_date)
    if current_pm_date not in dates:
        dates.add(current_pm_date)
    dates = sorted(dates)
    previous_dates = [date for date in dates if date < current_pm_date]
    mapping = {current_pm_date: 0}
    for offset, date in enumerate(reversed(previous_dates), start=1):
        mapping[date] = -offset
    return mapping


def _score_ref_raw_dt_values(
    score_frame: pd.DataFrame,
    current_pm_date: str,
    selected_ref_dates: set[str],
) -> list[str]:
    """선택된 score ref_dates의 원본 raw dt 후보를 반환합니다."""

    if not selected_ref_dates or "ref_dates" not in score_frame.columns or "pm_date" not in score_frame.columns:
        return []
    values: list[str] = []
    current_rows = score_frame[score_frame["pm_date"] == current_pm_date]
    for value in current_rows["ref_dates"].tolist():
        for ref_value in _ref_date_values(value):
            try:
                ref_date = _date_key(ref_value)
            except (TypeError, ValueError):
                continue
            if ref_date in selected_ref_dates:
                values.append(str(ref_value).strip())
    return [value for value in dict.fromkeys(values) if value]


def _requested_ref_dates(selection: dict[str, object]) -> set[str] | None:
    """요청된 ref PM 날짜 목록을 정규화합니다."""

    if "refPmDates" not in selection:
        return None
    dates: set[str] = set()
    for value in selection.get("refPmDates") or []:
        try:
            dates.add(_date_key(value))
        except (TypeError, ValueError):
            continue
    return dates


def _selected_ref_dates(selection: dict[str, object], cycle_map: dict[str, int]) -> set[str]:
    """선택된 ref PM 날짜를 cycle map 기준으로 확정합니다."""

    available = {date for date, cycle_index in cycle_map.items() if cycle_index < 0}
    requested = _requested_ref_dates(selection)
    if requested is None:
        return available
    return available.intersection(requested)


def _selection_with_raw_dt_values(
    selection: dict[str, object],
    current_pm_date: str,
    selected_ref_dates: set[str],
    ref_dt_values: Iterable[object] | None = None,
) -> dict[str, object]:
    """raw 파일 탐색이 선택된 PM cycle 날짜로 좁혀지도록 dt 후보를 보강합니다."""

    dt_values: list[str] = []
    for value in selection.get("dtValues") or []:
        dt_values.extend(selectors.date_partition_candidates(value))
    for value in ref_dt_values or []:
        dt_values.extend(selectors.date_partition_candidates(value))
    for value in [current_pm_date, *sorted(selected_ref_dates)]:
        dt_values.extend(selectors.date_partition_candidates(value))
    if not dt_values:
        dt_values.extend(selectors.date_partition_candidates(selection.get("pmTimestamp")))
    return {
        **selection,
        "dtValues": list(dict.fromkeys(dt_values)),
    }


def _ref_cycle_rows(cycle_map: dict[str, int], selected_ref_dates: set[str]) -> list[dict[str, Any]]:
    """화면 checkbox에 표시할 ref cycle 목록을 생성합니다."""

    rows = [
        {
            "pm_date": date,
            "cycle_index": cycle_index,
            "phase": "ref",
            "selected": date in selected_ref_dates,
        }
        for date, cycle_index in cycle_map.items()
        if cycle_index < 0
    ]
    rows.sort(key=lambda row: int(row["cycle_index"]), reverse=True)
    return [_camelize_mapping(row) for row in rows]


def _filter_selected_cycles(frame: pd.DataFrame, selected_ref_dates: set[str]) -> pd.DataFrame:
    """comp와 선택된 ref cycle만 남깁니다."""

    if frame.empty or "cycle_index" not in frame.columns or "pm_date" not in frame.columns:
        return frame
    return frame[(frame["cycle_index"] == 0) | (frame["pm_date"].isin(selected_ref_dates))].copy()


def _add_cycle_columns(frame: pd.DataFrame, cycle_map: dict[str, int]) -> pd.DataFrame:
    """frame에 cycle_index와 ref/comp phase를 추가합니다."""

    if frame.empty:
        frame = frame.copy()
        frame["cycle_index"] = []
        frame["phase"] = []
        return frame
    frame = frame.copy()
    if "pm_date" not in frame.columns:
        frame["pm_date"] = frame[DATE_COLUMN].map(_date_key)
    frame["cycle_index"] = frame["pm_date"].map(cycle_map)
    frame = frame[frame["cycle_index"].notna()].copy()
    frame["cycle_index"] = frame["cycle_index"].astype(int)
    frame["phase"] = frame["cycle_index"].map(lambda value: "comp" if value == 0 else "ref")
    return frame


def _score_trend_rows(
    score_frame: pd.DataFrame,
    cycle_map: dict[str, int],
    selected_ref_dates: set[str],
) -> list[dict[str, Any]]:
    """PM cycle별 score scatter row를 생성합니다."""

    frame = _filter_selected_cycles(_add_cycle_columns(score_frame, cycle_map), selected_ref_dates)
    if frame.empty:
        return []
    frame = frame.sort_values(["cycle_index", "score", "item_name", "step", "wavelength"])
    columns = ["pm_date", "cycle_index", "phase", "item_name", "step", "wavelength", "score"]
    return [_camelize_mapping(row) for row in frame[columns].to_dict(orient="records")]


def _cycle_summary(
    score_frame: pd.DataFrame,
    cycle_map: dict[str, int],
    selected_ref_dates: set[str],
) -> list[dict[str, Any]]:
    """cycle별 포함 데이터 수와 worst score를 요약합니다."""

    frame = _filter_selected_cycles(_add_cycle_columns(score_frame, cycle_map), selected_ref_dates)
    if frame.empty:
        return []
    grouped = (
        frame.groupby(["pm_date", "cycle_index", "phase"], dropna=False)["score"]
        .agg(item_count="count", worst_score="min", avg_score="mean")
        .reset_index()
        .sort_values("cycle_index")
    )
    return [_camelize_mapping(row) for row in grouped.to_dict(orient="records")]


def _trace_rank_rows(score_frame: pd.DataFrame, current_pm_date: str) -> list[dict[str, Any]]:
    """trace score row를 rank row로 변환합니다."""

    if score_frame.empty or "pm_date" not in score_frame.columns:
        return []
    current = score_frame[score_frame["pm_date"] == current_pm_date].copy()
    current = current.sort_values(["score", "item_name"])
    rows = []
    for row in current.to_dict(orient="records"):
        rows.append(
            {
                "trace_sensor": row.get("item_name"),
                "item_name": row.get("item_name"),
                "step": row.get("step"),
                "score": row.get("score"),
                "delta_shape": row.get("delta_shape"),
                "delta_jitter": row.get("delta_jitter"),
                "delta_level": row.get("delta_level"),
                "flag": row.get("flag"),
                "alarm_pct": row.get("alarm_pct"),
                "pm_date": row.get("pm_date"),
                "cycle_index": 0,
                "phase": "comp",
            }
        )
    return [_camelize_mapping(row) for row in rows]


def _oes_rank_rows(score_frame: pd.DataFrame, current_pm_date: str) -> list[dict[str, Any]]:
    """OES score row를 rank row로 변환합니다."""

    if score_frame.empty or "pm_date" not in score_frame.columns:
        return []
    current = score_frame[score_frame["pm_date"] == current_pm_date].copy()
    current = current.sort_values(["score", "step", "wavelength", "item_name"])
    rows = []
    for row in current.to_dict(orient="records"):
        rows.append(
            {
                "item_name": row.get("item_name"),
                "step": row.get("step"),
                "wavelength": row.get("wavelength"),
                "score": row.get("score"),
                "delta_spectrum": row.get("delta_spectrum"),
                "direction": row.get("direction"),
                "flagged_wl": row.get("flagged_wl"),
                "pm_date": row.get("pm_date"),
                "cycle_index": 0,
                "phase": "comp",
            }
        )
    return [_camelize_mapping(row) for row in rows]


def _raw_cycle_frame(frame: pd.DataFrame, cycle_map: dict[str, int]) -> pd.DataFrame:
    """raw frame에 날짜 기반 cycle 정보를 추가합니다."""

    if frame.empty or DATE_COLUMN not in frame.columns:
        return frame.iloc[0:0].copy()
    frame = frame.copy()
    frame["pm_date"] = frame[DATE_COLUMN].map(_date_key)
    return _add_cycle_columns(frame, cycle_map)


def _prepare_trace(selection: dict[str, object], current_pm_date: str, warnings: list[str]) -> dict[str, Any]:
    """result 기반 trace rank와 data 기반 상세 trend를 준비합니다."""

    score_frame, score_file_count = _read_score(selection, "trace", warnings)
    cycle_map = _cycle_map(score_frame, current_pm_date)
    selected_ref_dates = _selected_ref_dates(selection, cycle_map)
    rank_rows = _trace_rank_rows(score_frame, current_pm_date)
    selected_sensors = [str(value) for value in selection.get("traceParamNames", []) if value]
    if not selected_sensors:
        selected_sensors = [row["traceSensor"] for row in rank_rows[:1] if row.get("traceSensor")]

    trend_rows: list[dict[str, Any]] = []
    shape_rows: list[dict[str, Any]] = []
    jitter_rows: list[dict[str, Any]] = []
    line_chart: dict[str, Any] = {"series": [], "xDomain": [None, None], "yDomain": [None, None]}
    raw_file_count = 0
    row_count = 0
    if selection.get("includeDetails", True) and selection.get("includeTraceDetails", True):
        ref_dt_values = _score_ref_raw_dt_values(score_frame, current_pm_date, selected_ref_dates)
        raw_selection = _selection_with_raw_dt_values(
            selection,
            current_pm_date,
            selected_ref_dates,
            ref_dt_values=ref_dt_values,
        )
        files = selectors.iter_raw_files(
            raw_selection,
            data_source=str(selection.get("traceDataSource") or "trace"),
            trace_param_names=selected_sensors,
        )
        frames, raw_file_count = _read_frames(files, columns=TRACE_COLUMNS, warnings=warnings)
        if frames:
            frame = pd.concat(frames, ignore_index=True)
            if "trace_param_name" not in frame.columns and "name" in frame.columns:
                frame["trace_param_name"] = frame["name"]
            x_col = "time" if "time" in frame.columns else ("step_time" if "step_time" in frame.columns else None)
            if x_col and {"value", DATE_COLUMN, "trace_param_name"}.issubset(frame.columns):
                frame = _filter_selected_cycles(_raw_cycle_frame(frame, cycle_map), selected_ref_dates)
                if x_col == "time":
                    frame["time"] = pd.to_datetime(frame["time"], errors="coerce", utc=True)
                    frame = frame[frame["time"].notna()]
                frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
                frame = frame[frame["value"].notna()].copy()
                if selected_sensors:
                    frame = frame[frame["trace_param_name"].astype(str).isin(selected_sensors)]
                frame = frame.sort_values(["cycle_index", x_col])
                row_count = int(len(frame))
                chart_frame, chart_x_col = _trace_chart_x_frame(frame)
                line_chart = _line_chart_payload(
                    chart_frame,
                    x_column=chart_x_col,
                    y_column="value",
                    selection=selection,
                    series_columns=_trace_series_columns(chart_frame),
                    label_columns=["phase", "lot_id", "slot_no", "wafer_id"],
                )
                columns = [
                    "time",
                    "step_time",
                    "period",
                    "phase",
                    "cycle_index",
                    "pm_date",
                    "trace_param_name",
                    "value",
                    "root_lot_id",
                    "lot_id",
                    "wafer_id",
                    "ch_step",
                    "group",
                    "slot_no",
                ]
                visible_columns = [column for column in columns if column in frame.columns]
                compat_frame = frame.head(_compat_row_limit(selection))
                trend_rows = [_camelize_mapping(row) for row in compat_frame[visible_columns].to_dict(orient="records")]
            else:
                warnings.append("trace data에 날짜/time/value/trace_param_name 컬럼이 없어 상세 plot을 건너뜁니다.")

        # decomp_data에서 shape/jitter 상세 데이터를 읽습니다.
        _SHAPE_COLS = [DATE_COLUMN, "ref_dates", "phase", "value", "group", "lot_id", "slot_no"]
        _JITTER_COLS = [DATE_COLUMN, "ref_dates", "lot_id", "slot_no", "jitter_rms", "level", "group"]
        shape_files = selectors.iter_decomp_files(selection, comp_dt=current_pm_date, param_names=selected_sensors, file_name="shape.parquet")
        jitter_files = selectors.iter_decomp_files(selection, comp_dt=current_pm_date, param_names=selected_sensors, file_name="jitter.parquet")
        shape_frames, _ = _read_frames(shape_files, columns=_SHAPE_COLS, warnings=warnings)
        jitter_frames, _ = _read_frames(jitter_files, columns=_JITTER_COLS, warnings=warnings)
        if shape_frames:
            sf = pd.concat(shape_frames, ignore_index=True)
            if {DATE_COLUMN, "phase", "value"}.issubset(sf.columns):
                sf = sf.rename(columns={"value": "shape", "phase": "norm_phase"})
                sf = _filter_selected_cycles(_raw_cycle_frame(sf, cycle_map), selected_ref_dates)
                sf["shape"] = pd.to_numeric(sf["shape"], errors="coerce")
                sf["norm_phase"] = pd.to_numeric(sf.get("norm_phase", pd.Series(dtype=float)), errors="coerce")
                sf = sf[sf["shape"].notna() & sf["norm_phase"].notna()].copy()
                _vis = [c for c in ["norm_phase", "shape", "ch_step", "lot_id", "slot_no", "group",
                                    "cycle_index", "phase", "pm_date"]
                        if c in sf.columns]
                shape_rows = [_camelize_mapping(r) for r in sf[_vis].to_dict(orient="records")]
        if jitter_frames:
            jf = pd.concat(jitter_frames, ignore_index=True)
            if {DATE_COLUMN, "jitter_rms", "group"}.issubset(jf.columns):
                jf = _filter_selected_cycles(_raw_cycle_frame(jf, cycle_map), selected_ref_dates)
                jf["jitter_rms"] = pd.to_numeric(jf["jitter_rms"], errors="coerce")
                jf = jf[jf["jitter_rms"].notna()].copy()
                _jvis = [c for c in ["lot_id", "slot_no", "jitter_rms", "level", "group", "ch_step",
                                     "cycle_index", "phase", "pm_date"]
                         if c in jf.columns]
                jitter_rows = [_camelize_mapping(r) for r in jf[_jvis].to_dict(orient="records")]

    return {
        "fileCount": raw_file_count,
        "scoreFileCount": score_file_count,
        "rowCount": row_count,
        "worstSensor": rank_rows[0] if rank_rows else None,
        "summaryRows": rank_rows,
        "trendRows": trend_rows,
        "lineChart": line_chart,
        "shapeRows": shape_rows,
        "jitterRows": jitter_rows,
        "scoreTrendRows": _score_trend_rows(score_frame, cycle_map, selected_ref_dates),
        "cycleSummary": _cycle_summary(score_frame, cycle_map, selected_ref_dates),
        "refCycles": _ref_cycle_rows(cycle_map, selected_ref_dates),
    }
