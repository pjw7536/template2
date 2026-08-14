"""PM Comparison 조회 흐름을 조합하는 공개 서비스 구현입니다."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from api.pm_comparison import selectors

from .contracts import DATE_COLUMN, PmComparisonServiceError
from .oes_frames import _prepare_oes
from .payloads import _json_safe_value
from .trace_frames import _date_key, _prepare_trace, _selected_pm_date

def _empty_response(selection: dict[str, object], current_pm_date: str, warnings: list[str]) -> dict[str, Any]:
    """조회 결과가 없을 때도 동일한 응답 형태를 반환합니다."""

    return {
        "filters": _build_filter_response(selection),
        "window": {"pmTimestamp": current_pm_date, "pmDate": current_pm_date},
        "trace": {
            "fileCount": 0,
            "scoreFileCount": 0,
            "rowCount": 0,
            "worstSensor": None,
            "summaryRows": [],
            "trendRows": [],
            "lineChart": {"series": [], "xDomain": [None, None], "yDomain": [None, None]},
            "shapeRows": [],
            "jitterRows": [],
            "scoreTrendRows": [],
            "cycleSummary": [],
            "refCycles": [],
        },
        "oes": {
            "fileCount": 0,
            "scoreFileCount": 0,
            "rowCount": 0,
            "worstStep": None,
            "worstWavelength": None,
            "summaryRows": [],
            "stepRows": [],
            "detailRows": [],
            "trajectoryRows": [],
            "heatmap": {"width": 0, "height": 0, "wavelengths": [], "phases": [], "ref": [], "comp": [], "oob": []},
            "lineChart": {"series": [], "xDomain": [None, None], "yDomain": [None, None]},
            "spectrumChart": {"series": [], "xDomain": [None, None], "yDomain": [None, None]},
            "scoreTrendRows": [],
            "cycleSummary": [],
            "refCycles": [],
        },
        "warnings": warnings,
    }


def _build_filter_response(selection: dict[str, object]) -> dict[str, Any]:
    """요청 필터를 응답용으로 정리합니다."""

    keys = [
        "lineId",
        "eqpId",
        "chamberId",
        "fdcBin",
        "type",
        "ppid",
        "recipeId",
        "traceParamNames",
        "traceDataSource",
        "oesDataSource",
        "selectedStep",
        "selectedWavelength",
        "refPmDates",
        "limit",
        "maxPoints",
        "xStart",
        "xEnd",
        "heatmapXBins",
        "heatmapYBins",
    ]
    return {key: _json_safe_value(selection.get(key)) for key in keys}


@lru_cache(maxsize=4096)
def _score_file_dates(path_text: str, mtime_ns: int, size: int) -> tuple[str, ...]:
    """score 파일 하나에서 읽은 PM 날짜 목록을 캐시합니다."""

    frame = selectors.read_parquet(Path(path_text), [DATE_COLUMN])
    if DATE_COLUMN not in frame.columns:
        return tuple()
    return tuple(sorted({_date_key(value) for value in frame[DATE_COLUMN].dropna().unique().tolist()}))


def _collect_pm_dates(warnings: list[str], selection: dict[str, object] | None = None) -> list[str]:
    """result 전체에서 PM 날짜 목록을 수집합니다."""

    if not selection or not selection.get("lineId") or not selection.get("eqpId"):
        return []
    if selection.get("pmTimestamp"):
        try:
            return [_date_key(selection["pmTimestamp"])]
        except (TypeError, ValueError):
            return [str(selection["pmTimestamp"])]

    dates: set[str] = set()
    try:
        files = [
            *selectors.iter_score_files(selection or {}, data_type="trace"),
            *selectors.iter_score_files(selection or {}, data_type="oes"),
        ]
    except (FileNotFoundError, NotADirectoryError):
        return []
    for path in files:
        try:
            stat = path.stat()
            dates.update(_score_file_dates(str(path), stat.st_mtime_ns, stat.st_size))
        except Exception as exc:
            warnings.append(f"score 날짜 읽기 실패: {path.name} ({exc})")
            continue
    return sorted(dates)


def _has_time_part(value: str) -> bool:
    """raw dt 값에 시각 정보가 포함되어 있는지 확인합니다."""

    text = str(value)
    return (len(text) > 10 and text[10:11] in {" ", "T"}) or ":" in text


def _meta_pm_dates(
    selection: dict[str, object] | None,
    options: dict[str, list[str]],
    warnings: list[str],
) -> list[str]:
    """PM 시점 dropdown에 노출할 날짜 후보를 결정합니다."""

    raw_dt_values = options.get("dt", [])
    if selection and selection.get("fdcBin") and any(_has_time_part(value) for value in raw_dt_values):
        return raw_dt_values
    pm_dates = _collect_pm_dates(warnings, selection)
    return pm_dates or raw_dt_values


def get_meta(selection: dict[str, object] | None = None) -> dict[str, object]:
    """PM SPIDER 데이터 선택 메타데이터를 반환합니다."""

    warnings: list[str] = []
    try:
        options = selectors.collect_partition_options(selection)
    except FileNotFoundError as exc:
        raise PmComparisonServiceError(str(exc), status_code=404) from exc
    except NotADirectoryError as exc:
        raise PmComparisonServiceError(str(exc), status_code=400) from exc

    pm_dates = _meta_pm_dates(selection, options, warnings)

    return {
        "lineIds": options.get("line_id", []),
        "eqpIds": options.get("eqp_id", []),
        "fdcBins": options.get("fdc_bin", []),
        "dtValues": options.get("dt", []),
        "pmDates": pm_dates or options.get("dt", []),
        "types": options.get("type", []),
        "ppids": options.get("ppid", []),
        "recipeIds": options.get("recipe_id", []),
        "dataSources": options.get("data_source", []),
        "traceParamNames": options.get("trace_param_name", []),
        "warnings": warnings,
    }


def compare_pm_window(selection: dict[str, object]) -> dict[str, Any]:
    """PM 주기 기준 score rank와 raw 상세 데이터를 반환합니다."""

    warnings: list[str] = []
    current_pm_date = _selected_pm_date(selection)
    try:
        trace = _prepare_trace(selection, current_pm_date, warnings)
        oes = _prepare_oes(selection, current_pm_date, warnings)
    except FileNotFoundError as exc:
        raise PmComparisonServiceError(str(exc), status_code=404) from exc
    except NotADirectoryError as exc:
        raise PmComparisonServiceError(str(exc), status_code=400) from exc

    if not trace["summaryRows"] and not oes["summaryRows"]:
        return _empty_response(selection, current_pm_date, warnings)

    return {
        "filters": _build_filter_response(selection),
        "window": {"pmTimestamp": current_pm_date, "pmDate": current_pm_date},
        "trace": trace,
        "oes": oes,
        "warnings": warnings,
    }
