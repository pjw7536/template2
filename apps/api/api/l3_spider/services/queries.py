"""L3 Spider 구조·통계·요약·차트 조회를 처리합니다."""

from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Any

import pandas as pd

from api.l3_spider import selectors

from . import line_name_rules
from .analytics import (
    ANOMALY_STATUSES,
    _camelize_mapping,
    _dataframe_to_columnar,
    _empty_stats,
    _has_required_selection,
    _make_selection_cache_key,
    _normalize_display_status,
    _sample_chart_points,
)
from .cache import TTLCache
from .metadata import (
    _add_path_context,
    _apply_exclusion_filters,
    _apply_exclusion_filters_with_rules,
    _filter_files_by_line_names,
    _get_exclusion_rules,
    _matches_comma_separated_patterns,
    _matches_pattern,
    _parallel_read,
    _parse_filename_key,
    _read_chart_file,
    _read_daily_summary_file,
    _read_stats_file,
    _read_summary_frames,
)
from .state import (
    CHART_COLUMNS,
    L3SpiderServiceError,
    _daily_summary_cache,
    _stats_cache,
    _structure_cache,
)

def get_structure(selection: dict[str, object], *, user: Any | None = None) -> dict[str, object]:
    """파일명 스캔만으로 edsStepSeqs·edsStepPpids를 즉시 반환합니다 (parquet 읽기 없음).

    제외 필터의 경로 필드(line_id, process_id, eds_step, step_seq, ppid)를 적용합니다.
    eqpch·bin_name 기준 규칙은 parquet 데이터 없이 판단 불가하므로 자동으로 무시됩니다.
    """
    empty: dict[str, object] = {"edsStepSeqs": {}, "edsStepPpids": {}}
    if not _has_required_selection(selection):
        return empty

    rules = _get_exclusion_rules(user=user)
    rules_hash = str(hash(tuple(sorted(str(r) for r in rules))))
    cache_key = f"{rules_hash}:{_make_selection_cache_key(selection)}"
    cached = _structure_cache.get(cache_key)
    if cached is not None:
        return cached

    line_names = {str(v) for v in (selection.get("lineNames") or []) if v}

    # 파일명 스캔만으로 처리(parquet 읽기 없음). line_name은 (line_id, process_id, step_seq)로
    # 파일마다 결정되므로 스캔 중 바로 필터합니다.
    root = selectors.get_data_root()
    file_rows: list[dict[str, str]] = []
    try:
        for path in selectors.iter_data_files(selection):
            parsed = _parse_filename_key(path)
            if not parsed:
                # 계약상 daily_anomaly 파일명엔 step_seq가 항상 있음. structure는 파일명 스캔만
                # 하므로(parquet 미읽음) step_seq를 못 읽는 파일은 다룰 수 없어 제외.
                continue
            step_seq, ppid = parsed
            relative_parts = path.relative_to(root).parts
            if len(relative_parts) < 5:
                continue
            date, line_id, process_id, eds_step = relative_parts[:4]
            if line_names and line_name_rules.resolve_line_name(line_id, process_id, step_seq) not in line_names:
                continue
            file_rows.append({
                "date": date,
                "line_id": line_id,
                "process_id": process_id,
                "eds_step": eds_step,
                "step_seq": step_seq,
                "ppid": ppid,
            })
    except (FileNotFoundError, NotADirectoryError) as exc:
        raise L3SpiderServiceError(str(exc), status_code=404) from exc
    if not file_rows:
        _structure_cache.set(cache_key, empty)
        return empty
    df = pd.DataFrame(file_rows).drop_duplicates()
    # eqc·bin_name 컬럼이 없으므로 해당 필드가 있는 규칙은 자동으로 제외 대상 없음 처리됨
    df = _apply_exclusion_filters_with_rules(df, rules)

    eds_step_seqs: dict[str, set[str]] = {}
    eds_step_ppids: dict[str, set[str]] = {}

    if not df.empty and {"eds_step", "step_seq", "ppid"}.issubset(df.columns):
        for _, row in df[["eds_step", "step_seq", "ppid"]].drop_duplicates().iterrows():
            eds_step = str(row["eds_step"])
            step_seq = str(row["step_seq"])
            ppid_val = str(row["ppid"])
            eds_step_seqs.setdefault(eds_step, set()).add(step_seq)
            eds_step_ppids.setdefault(f"{eds_step}|||{step_seq}", set()).add(ppid_val)

    result: dict[str, object] = {
        "edsStepSeqs": {eds: sorted(steps) for eds, steps in sorted(eds_step_seqs.items())},
        "edsStepPpids": {key: sorted(ppids) for key, ppids in sorted(eds_step_ppids.items())},
    }
    _structure_cache.set(cache_key, result)
    return result


def get_stats(selection: dict[str, object], *, user: Any | None = None) -> dict[str, object]:
    """slim parquet 읽기로 stats + PPID별 last_tkin_time을 반환합니다."""
    empty: dict[str, object] = {"stats": _empty_stats(), "ppidLastTkinTime": {}}
    if not _has_required_selection(selection):
        return empty

    # rules hash를 포함한 cache key: 필터 변경 시 자동으로 다른 key가 사용됨
    rules = _get_exclusion_rules(user=user)
    rules_hash = str(hash(tuple(sorted(str(r) for r in rules))))
    cache_key = f"{rules_hash}:{_make_selection_cache_key(selection)}"
    cached = _stats_cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        files = list(selectors.iter_data_files(selection))
    except (FileNotFoundError, NotADirectoryError) as exc:
        raise L3SpiderServiceError(str(exc), status_code=404) from exc

    files = _filter_files_by_line_names(files, selection)
    frames = _parallel_read(files, _read_stats_file)
    if not frames:
        _stats_cache.set(cache_key, empty)
        return empty

    merged = pd.concat(frames, ignore_index=True)
    merged = _normalize_display_status(merged)
    # rules는 이미 읽었으므로 직접 적용 (DB 재조회 방지)
    merged = _apply_exclusion_filters_with_rules(merged, rules)

    if "display_status" not in merged.columns:
        _stats_cache.set(cache_key, empty)
        return empty

    status = merged["display_status"]
    anomaly_mask = status.isin(ANOMALY_STATUSES)
    high_risk_mask = status == "High Risk Chamber"

    stats = {
        "total": int(len(merged)),
        "normal": int((status == "Normal (Ref)").sum()),
        "warning": int((status == "Warning").sum()),
        "risk": int(high_risk_mask.sum()),
        "anomalySteps": int(merged.loc[anomaly_mask, "step_seq"].dropna().nunique())
            if "step_seq" in merged.columns else 0,
        "highRiskEqpchs": int(merged.loc[high_risk_mask, "eqc"].dropna().nunique())
            if "eqc" in merged.columns else 0,
    }

    ppid_last_tkin_time: dict[str, str] = {}
    if {"eds_step", "step_seq", "ppid", "tkin_time"}.issubset(merged.columns):
        try:
            tkin = merged[["eds_step", "step_seq", "ppid", "tkin_time"]].copy()
            tkin["tkin_time"] = pd.to_datetime(tkin["tkin_time"], errors="coerce")
            tkin = tkin.dropna(subset=["tkin_time"])
            if not tkin.empty:
                grouped = tkin.groupby(["eds_step", "step_seq", "ppid"], sort=False)["tkin_time"].max()
                for (eds, step, ppid), ts in grouped.items():
                    ppid_last_tkin_time[f"{eds}|||{step}|||{ppid}"] = ts.strftime("%Y-%m-%d %H:%M")
        except Exception as exc:
            print(f"[WARN] L3 Spider ppidLastTkinTime compute failed: {exc}")

    result = {"stats": stats, "ppidLastTkinTime": ppid_last_tkin_time}
    _stats_cache.set(cache_key, result)
    return result


def get_summary(selection: dict[str, object], *, user: Any | None = None) -> dict[str, object]:
    """선택 조건의 이상감지 요약 정보를 반환합니다."""
    empty = {"stats": _empty_stats(), "edsStepSeqs": {}, "edsStepPpids": {}, "stepPpids": {}, "ppidEqcs": {}, "ppidHighRiskEqcs": {}, "ppidBins": {}, "eqcBins": {}, "eqcAnomalyBins": {}, "eqcHighRiskBins": {}, "bins": [], "anomalies": []}
    if not _has_required_selection(selection):
        return empty

    frames = _read_summary_frames(selection)
    if not frames:
        return empty

    merged = pd.concat(frames, ignore_index=True)
    merged = _normalize_display_status(merged)
    merged = _apply_exclusion_filters(merged, user=user)
    if merged.empty:
        return empty
    if "display_status" not in merged.columns:
        return empty

    status = merged["display_status"]
    anomaly_mask = status.isin(ANOMALY_STATUSES)
    high_risk_mask = status == "High Risk Chamber"
    stats = {
        "total": int(len(merged)),
        "normal": int((status == "Normal (Ref)").sum()),
        "warning": int((status == "Warning").sum()),
        "risk": int(high_risk_mask.sum()),
        "anomalySteps": int(merged.loc[anomaly_mask, "step_seq"].dropna().nunique())
        if "step_seq" in merged.columns
        else 0,
        "highRiskEqpchs": int(merged.loc[high_risk_mask, "eqc"].dropna().nunique())
        if "eqc" in merged.columns
        else 0,
    }

    eds_step_seqs: dict[str, list[str]] = {}
    if {"eds_step", "step_seq"}.issubset(merged.columns):
        pairs = merged[["eds_step", "step_seq"]].drop_duplicates().sort_values(["eds_step", "step_seq"])
        eds_step_seqs = {
            str(eds): sorted(group["step_seq"].dropna().astype(str).tolist())
            for eds, group in pairs.groupby("eds_step", sort=True)
        }

    eds_step_ppids: dict[str, list[str]] = {}
    if {"eds_step", "step_seq", "ppid"}.issubset(merged.columns):
        pairs = merged[["eds_step", "step_seq", "ppid"]].drop_duplicates().sort_values(
            ["eds_step", "step_seq", "ppid"]
        )
        eds_step_ppids = {
            f"{str(eds)}|||{str(step)}": sorted(group["ppid"].dropna().astype(str).tolist())
            for (eds, step), group in pairs.groupby(["eds_step", "step_seq"], sort=True)
        }

    step_ppids: dict[str, list[str]] = {}
    if {"step_seq", "ppid"}.issubset(merged.columns):
        pairs = merged[["step_seq", "ppid"]].drop_duplicates().sort_values(["step_seq", "ppid"])
        step_ppids = {
            str(step): group["ppid"].dropna().astype(str).tolist()
            for step, group in pairs.groupby("step_seq", sort=True)
        }

    anomalies: list[dict[str, Any]] = []
    anomaly_columns = ["eds_step", "step_seq", "ppid", "eqc", "bin_name"]
    if all(column in merged.columns for column in anomaly_columns):
        anomalies = [
            _camelize_mapping(row)
            for row in (
                merged.loc[high_risk_mask, anomaly_columns]
                .drop_duplicates()
                .sort_values(anomaly_columns)
                .astype(str)
                .to_dict(orient="records")
            )
        ]

    ppid_eqcs: dict[str, list[str]] = {}
    if {"ppid", "eqc"}.issubset(merged.columns):
        pairs = merged[["ppid", "eqc"]].drop_duplicates().sort_values(["ppid", "eqc"])
        ppid_eqcs = {
            str(ppid): sorted(group["eqc"].dropna().astype(str).tolist())
            for ppid, group in pairs.groupby("ppid", sort=True)
        }

    ppid_high_risk_eqcs: dict[str, list[str]] = {}
    if {"ppid", "eqc", "display_status"}.issubset(merged.columns):
        high_risk_pairs = (
            merged.loc[high_risk_mask, ["ppid", "eqc"]]
            .drop_duplicates()
            .sort_values(["ppid", "eqc"])
        )
        ppid_high_risk_eqcs = {
            str(ppid): sorted(group["eqc"].dropna().astype(str).tolist())
            for ppid, group in high_risk_pairs.groupby("ppid", sort=True)
        }

    ppid_bins: dict[str, list[str]] = {}
    if {"ppid", "bin_name"}.issubset(merged.columns):
        pairs = merged[["ppid", "bin_name"]].drop_duplicates().sort_values(["ppid", "bin_name"])
        ppid_bins = {
            str(ppid): sorted(group["bin_name"].dropna().astype(str).tolist())
            for ppid, group in pairs.groupby("ppid", sort=True)
        }

    eqc_bins: dict[str, list[str]] = {}
    if {"eqc", "bin_name"}.issubset(merged.columns):
        pairs = merged[["eqc", "bin_name"]].drop_duplicates().sort_values(["eqc", "bin_name"])
        eqc_bins = {
            str(eqc): sorted(group["bin_name"].dropna().astype(str).tolist())
            for eqc, group in pairs.groupby("eqc", sort=True)
        }

    eqc_anomaly_bins: dict[str, list[str]] = {}
    if {"eqc", "bin_name", "display_status"}.issubset(merged.columns):
        anomaly_pairs = (
            merged.loc[merged["display_status"].isin(ANOMALY_STATUSES), ["eqc", "bin_name"]]
            .drop_duplicates()
            .sort_values(["eqc", "bin_name"])
        )
        eqc_anomaly_bins = {
            str(eqc): sorted(group["bin_name"].dropna().astype(str).tolist())
            for eqc, group in anomaly_pairs.groupby("eqc", sort=True)
        }

    eqc_high_risk_bins: dict[str, list[str]] = {}
    if {"eqc", "bin_name", "display_status"}.issubset(merged.columns):
        high_risk_bin_pairs = (
            merged.loc[high_risk_mask, ["eqc", "bin_name"]]
            .drop_duplicates()
            .sort_values(["eqc", "bin_name"])
        )
        eqc_high_risk_bins = {
            str(eqc): sorted(group["bin_name"].dropna().astype(str).tolist())
            for eqc, group in high_risk_bin_pairs.groupby("eqc", sort=True)
        }

    bins = (
        sorted(merged["bin_name"].dropna().astype(str).unique().tolist())
        if "bin_name" in merged.columns
        else []
    )
    return {
        "stats": stats,
        "edsStepSeqs": eds_step_seqs,
        "edsStepPpids": eds_step_ppids,
        "stepPpids": step_ppids,
        "ppidEqcs": ppid_eqcs,
        "ppidHighRiskEqcs": ppid_high_risk_eqcs,
        "ppidBins": ppid_bins,
        "eqcBins": eqc_bins,
        "eqcAnomalyBins": eqc_anomaly_bins,
        "eqcHighRiskBins": eqc_high_risk_bins,
        "bins": bins,
        "anomalies": anomalies,
    }


def _empty_daily_summary() -> dict[str, object]:
    return {
        "dates": [],
        "headline": {
            "groups": 0, "binNames": 0, "stepSeqs": 0, "lines": 0, "processes": 0,
            "edsSteps": 0, "ppids": 0, "lots": 0, "totalRows": 0,
            "anomalies": 0, "highRisk": 0, "warning": 0, "anomalyGroups": 0,
            "anomalyEqpchs": 0, "highRiskEqpchs": 0, "warningEqpchs": 0,
        },
        "matrix": {"lines": [], "processes": [], "edsSteps": [], "cells": []},
        "runStats": {"totalRows": 0, "combinations": 0, "byLine": [], "byLineName": []},
        "selectionTree": None,
    }


def _parse_json_list(value: object) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(x) for x in value]
    try:
        parsed = json.loads(value)
        return [str(x) for x in parsed] if isinstance(parsed, list) else []
    except Exception:
        return []


def _daily_file_df_from_index(index_rows: list[dict], date: str, root: Path) -> tuple[pd.DataFrame, list[Path]]:
    """file_index 행 → 파일별 집계 프레임(카운트 있는 파일) + 카운트 NULL 파일 경로 목록."""
    counted: list[dict] = []
    uncounted_paths: list[Path] = []
    for r in index_rows:
        if r.get("high_risk_cnt") is None:  # 구 데이터 → parquet 폴백 대상
            uncounted_paths.append(
                root / date / str(r.get("line_id")) / str(r.get("process_id"))
                / str(r.get("eds_step")) / Path(str(r.get("filepath"))).name
            )
            continue
        counted.append({
            "line_id": str(r.get("line_id") or ""),
            "process_id": str(r.get("process_id") or ""),
            "eds_step": str(r.get("eds_step") or ""),
            "step_seq": str(r.get("step_seq") or ""),
            "ppid": str(r.get("ppid") or ""),
            "hr": int(r.get("high_risk_cnt") or 0),
            "wn": int(r.get("warning_cnt") or 0),
            "row_cnt": int(r.get("row_cnt") or 0),
            "bins": _parse_json_list(r.get("bin_names")),
            "hr_eqcs": _parse_json_list(r.get("high_risk_eqcs")),
            # 분석 그룹용: 알고리즘이 처리한 전체 bin 수(이상 여부 무관).
            # 알고리즘 서버가 total_bin_cnt를 아직 안 주면 이상 bin 수(len(bins))로 폴백.
            "total_bins": (
                int(r["total_bin_cnt"])
                if r.get("total_bin_cnt") is not None
                else len(_parse_json_list(r.get("bin_names")))
            ),
        })
    return pd.DataFrame(counted), uncounted_paths


def _read_daily_summary_rows(paths: list[Path], rules: list[dict] | None) -> pd.DataFrame:
    """daily summary Parquet을 읽고 제외 필터를 적용한 행을 반환합니다."""

    if not paths:
        return pd.DataFrame()
    frames = _parallel_read(list(paths), _read_daily_summary_file)
    if not frames:
        return pd.DataFrame()
    merged = pd.concat(frames, ignore_index=True)
    merged = _normalize_display_status(merged)
    if rules:
        merged = _apply_exclusion_filters_with_rules(merged, rules)
    if merged.empty or "display_status" not in merged.columns:
        return pd.DataFrame()
    for col in ("line_id", "process_id", "eds_step", "step_seq", "ppid", "bin_name"):
        if col not in merged.columns:
            merged[col] = ""
        merged[col] = merged[col].fillna("").astype(str)
    if "eqc" not in merged.columns:
        merged["eqc"] = ""
    merged["eqc"] = merged["eqc"].fillna("").astype(str)
    return merged


def _daily_file_df_from_rows(merged: pd.DataFrame) -> pd.DataFrame:
    """필터 적용이 끝난 daily summary 행을 파일별 집계로 변환합니다."""

    if merged.empty:
        return pd.DataFrame()
    merged = merged.copy()
    status = merged["display_status"].astype(str)
    merged["_hr"] = (status == "High Risk Chamber").astype(int)
    merged["_wn"] = (status == "Warning").astype(int)
    records: list[dict] = []
    for (lid, pid, eds, sseq, ppid), group in merged.groupby(
        ["line_id", "process_id", "eds_step", "step_seq", "ppid"], sort=False
    ):
        hr_eqcs = sorted(
            e for e in group.loc[group["_hr"] == 1, "eqc"].unique().tolist() if e
        )
        all_bins = group["bin_name"].dropna().astype(str).unique().tolist()
        records.append({
            "line_id": lid, "process_id": pid, "eds_step": eds, "step_seq": sseq, "ppid": ppid,
            "hr": int(group["_hr"].sum()), "wn": int(group["_wn"].sum()), "row_cnt": int(len(group)),
            "bins": sorted(all_bins),
            "hr_eqcs": hr_eqcs,
            # parquet에는 정상 포함 전체 행이 있으므로 distinct bin 수 = 분석 그룹용 total_bins
            "total_bins": int(len(all_bins)),
        })
    return pd.DataFrame(records)


def _daily_file_df_from_parquet(paths: list[Path], rules: list[dict] | None) -> pd.DataFrame:
    """Parquet 파일을 읽어 제외 필터 적용 후 파일별 집계로 변환합니다."""

    return _daily_file_df_from_rows(_read_daily_summary_rows(paths, rules))


def _build_selection_tree(merged: pd.DataFrame) -> dict[str, object]:
    """필터 적용 후 High Risk leaf만 포함하는 Chart 선택 트리를 반환합니다."""

    required = {
        "line_id", "process_id", "eds_step", "step_seq", "ppid",
        "eqc", "bin_name", "display_status",
    }
    if merged.empty or not required.issubset(merged.columns):
        return {}

    high_risk = merged.loc[
        merged["display_status"] == "High Risk Chamber",
        list(required),
    ].drop_duplicates()
    if high_risk.empty:
        return {}

    tree: dict[str, dict] = {}
    for row in high_risk.itertuples(index=False):
        line_name = line_name_rules.resolve_line_name(
            row.line_id,
            row.process_id,
            row.step_seq,
        )
        bins = (
            tree.setdefault(str(line_name), {})
            .setdefault(str(row.process_id), {})
            .setdefault(str(row.eds_step), {})
            .setdefault(str(row.step_seq), {})
            .setdefault(str(row.ppid), {})
            .setdefault(str(row.eqc), set())
        )
        bins.add(str(row.bin_name))

    return {
        line_name: {
            process_id: {
                eds_step: {
                    step_seq: {
                        ppid: {
                            eqc: sorted(bin_names)
                            for eqc, bin_names in sorted(eqcs.items())
                        }
                        for ppid, eqcs in sorted(ppids.items())
                    }
                    for step_seq, ppids in sorted(steps.items())
                }
                for eds_step, steps in sorted(eds_steps.items())
            }
            for process_id, eds_steps in sorted(processes.items())
        }
        for line_name, processes in sorted(tree.items())
    }


def _aggregate_daily(file_df: pd.DataFrame, dates: list) -> dict:
    """파일별 집계 프레임 → 일별 요약(line_name 기준 매트릭스 + 헤드라인)."""
    if file_df.empty:
        return {**_empty_daily_summary(), "dates": sorted(dates)}
    for col in ("line_id", "process_id", "eds_step", "step_seq", "ppid"):
        if col not in file_df.columns:
            file_df[col] = ""
        file_df[col] = file_df[col].fillna("").astype(str)
    for col in ("hr", "wn", "row_cnt"):
        if col not in file_df.columns:
            file_df[col] = 0
        file_df[col] = file_df[col].fillna(0).astype(int)
    if "bins" not in file_df.columns:
        file_df["bins"] = [[] for _ in range(len(file_df))]
    if "hr_eqcs" not in file_df.columns:
        file_df["hr_eqcs"] = [[] for _ in range(len(file_df))]
    # 분석 그룹용 전체 bin 수. 없으면(구 인덱스/폴백) 이상 bin 수로 대체.
    if "total_bins" not in file_df.columns:
        file_df["total_bins"] = [len(b) if b else 0 for b in file_df["bins"]]
    file_df["total_bins"] = file_df["total_bins"].fillna(0).astype(int)

    name_map = {
        (lid, pid, sseq): line_name_rules.resolve_line_name(lid, pid, sseq)
        for lid, pid, sseq in file_df[["line_id", "process_id", "step_seq"]].drop_duplicates().itertuples(index=False)
    }
    file_df["line_name"] = [
        name_map[(lid, pid, sseq)]
        for lid, pid, sseq in zip(file_df["line_id"], file_df["process_id"], file_df["step_seq"])
    ]

    cells: list[dict] = []
    for (line_name, pid, eds), group in file_df.groupby(["line_name", "process_id", "eds_step"], sort=True):
        hr_c = int(group["hr"].sum())
        wn_c = int(group["wn"].sum())
        bins: set = set()
        for bin_list in group["bins"]:
            if bin_list:
                bins.update(bin_list)
        hr_step_seqs = {s for s in group.loc[group["hr"] > 0, "step_seq"] if s}
        cell_hr_eqcs: set = set()
        for eqc_list in group["hr_eqcs"]:
            if eqc_list:
                cell_hr_eqcs.update(eqc_list)
        cells.append({
            "line": line_name, "process": pid, "edsStep": eds,
            "highRisk": hr_c, "warning": wn_c, "total": hr_c + wn_c, "bins": len(bins),
            "hrStepSeqs": len(hr_step_seqs),  # High Risk 발생 step_seq 수
            "hrEqpchs": len(cell_hr_eqcs),    # High Risk 발생 EQPCH 수
        })

    # 이상 bin 조합(차트/이상 지표용) 및 이상 EQPCH 집계.
    # 주의: bins(=bin_names)는 알고리즘 서버가 '이상 bin만' 인덱싱하므로 이상 조합만 담긴다.
    anomaly_bin_groups: set = set()
    hr_eqc_set: set = set()
    for row in file_df.itertuples(index=False):
        for bin_name in (row.bins or []):
            anomaly_bin_groups.add((row.line_name, row.process_id, row.eds_step, row.step_seq, bin_name))
        for eqc in (row.hr_eqcs or []):
            hr_eqc_set.add(eqc)

    total_hr = int(file_df["hr"].sum())
    total_wn = int(file_df["wn"].sum())
    headline = {
        # 분석 그룹 = 알고리즘이 처리한 전체 (파일=line·process·eds·step_seq·ppid) × bin 수.
        # 이상 여부와 무관한 total_bins(=total_bin_cnt)의 합. 이상 조합만 세던 기존값과 다르다.
        "groups": int(file_df["total_bins"].sum()),
        "binNames": len({t[4] for t in anomaly_bin_groups}),
        "stepSeqs": int(file_df["step_seq"].nunique()),
        "lines": int(file_df["line_name"].nunique()),
        "processes": int(file_df["process_id"].nunique()),
        "edsSteps": int(file_df["eds_step"].nunique()),
        "ppids": int(file_df["ppid"].nunique()),
        "lots": 0,
        "totalRows": int(file_df["row_cnt"].sum()),
        "anomalies": total_hr + total_wn,
        "highRisk": total_hr,
        "warning": total_wn,
        "anomalyGroups": 0,
        "anomalyEqpchs": 0,
        "highRiskEqpchs": len(hr_eqc_set),  # 그날 High Risk 난 distinct EQPCH
        "warningEqpchs": 0,
    }
    matrix = {
        "lines": sorted(file_df["line_name"].unique().tolist()),
        "processes": sorted(file_df["process_id"].unique().tolist()),
        "edsSteps": sorted(file_df["eds_step"].unique().tolist()),
        "cells": cells,
    }
    return {"dates": sorted(dates), "headline": headline, "matrix": matrix}


def _build_line_name_run_stats(
    details: list[dict[str, object]],
    rules: list[dict],
) -> list[dict[str, object]]:
    """전체 실행 통계에서 line_name별 분석 step과 row 수를 집계합니다."""

    if not details:
        return []

    frame = pd.DataFrame(details)
    frame = _apply_exclusion_filters_with_rules(frame, rules)
    if frame.empty:
        return []
    frame["line_name"] = [
        line_name_rules.resolve_line_name(line_id, process_id, step_seq)
        for line_id, process_id, step_seq in frame[
            ["line_id", "process_id", "step_seq"]
        ].itertuples(index=False)
    ]

    result: list[dict[str, object]] = []
    for line_name, group in frame.groupby("line_name", sort=True):
        step_seqs = group["step_seq"].dropna().astype(str).str.strip()
        result.append({
            "lineName": str(line_name),
            "stepSeqCount": int(step_seqs[step_seqs != ""].nunique()),
            "rowCnt": int(group["row_cnt"].fillna(0).astype(int).sum()),
        })
    return result


def _include_analyzed_matrix_cells(
    matrix: dict[str, object],
    details: list[dict[str, object]],
    rules: list[dict],
) -> dict[str, object]:
    """실행 통계에만 있는 분석 조합을 이상 수치 0인 matrix cell로 보강합니다."""

    if not details:
        return matrix

    frame = _apply_exclusion_filters_with_rules(pd.DataFrame(details), rules)
    required_columns = {"line_id", "process_id", "eds_step", "step_seq"}
    if frame.empty or not required_columns.issubset(frame.columns):
        return matrix

    cells_by_key = {
        (
            str(cell.get("line") or ""),
            str(cell.get("process") or ""),
            str(cell.get("edsStep") or ""),
        ): dict(cell)
        for cell in matrix.get("cells", [])
    }

    for line_id, process_id, eds_step, step_seq in frame[
        ["line_id", "process_id", "eds_step", "step_seq"]
    ].drop_duplicates().itertuples(index=False):
        line_name = line_name_rules.resolve_line_name(line_id, process_id, step_seq)
        key = (str(line_name), str(process_id), str(eds_step))
        cells_by_key.setdefault(
            key,
            {
                "line": key[0],
                "process": key[1],
                "edsStep": key[2],
                "highRisk": 0,
                "warning": 0,
                "total": 0,
                "bins": 0,
                "hrStepSeqs": 0,
                "hrEqpchs": 0,
            },
        )

    cells = [cells_by_key[key] for key in sorted(cells_by_key)]
    return {
        **matrix,
        "lines": sorted({cell["line"] for cell in cells}),
        "processes": sorted({cell["process"] for cell in cells}),
        "edsSteps": sorted({cell["edsStep"] for cell in cells}),
        "cells": cells,
    }


def get_daily_summary(selection: dict[str, object], *, user: Any | None = None) -> dict[str, object]:
    """선택한 날짜 전체의 line_name×process×eds_step 기준 이상감지 요약을 반환합니다.

    Chart 조회와 달리 line/process/eds 선택과 무관하게 해당 날짜의 모든 그룹을 집계합니다.
    """
    dates = [str(d) for d in (selection.get("dates") or []) if d]
    if not dates:
        return _empty_daily_summary()

    # 완결성 게이트(방어): 완료되지 않은 날짜는 부분 데이터이므로 요약 대상에서 제외한다.
    # get_meta가 이미 미완료 날짜를 노출하지 않지만, 직접 API 호출로 우회하는 경우까지 막는다.
    completed_dates = selectors.query_completed_dates()
    if completed_dates is not None:
        dates = [d for d in dates if d in completed_dates]
        if not dates:
            return _empty_daily_summary()

    rules = _get_exclusion_rules(user=user)
    rules_hash = str(hash(tuple(sorted(str(r) for r in rules))))
    cache_key = f"{rules_hash}:{json.dumps(sorted(dates))}"
    cached = _daily_summary_cache.get(cache_key)
    if cached is not None:
        return cached

    # 제외필터가 있으면 행 단위 정확 필터가 필요 → 전량 parquet.
    # 없으면 file_index의 상태 카운트로 집계(초고속). 카운트 NULL(구 데이터) 파일만 parquet 폴백.
    file_frames: list[pd.DataFrame] = []
    selection_tree: dict[str, object] | None = None
    try:
        if rules:
            paths: list[Path] = []
            for date in dates:
                paths.extend(selectors.iter_date_files(date))
            filtered_rows = _read_daily_summary_rows(paths, rules)
            selection_tree = _build_selection_tree(filtered_rows)
            frame = _daily_file_df_from_rows(filtered_rows)
            if not frame.empty:
                file_frames.append(frame)
        else:
            index_rows_by_date = [(date, selectors.query_date_file_index(date)) for date in dates]
            all_rows = [r for _, rows in index_rows_by_date for r in rows]
            # 인덱스로 완전 집계하려면 카운트 + high_risk_eqcs(이상 EQPCH용) 컬럼이 모두 있어야 함
            index_full = bool(all_rows) and ("high_risk_eqcs" in all_rows[0])
            if index_full:
                root = selectors.get_data_root()
                uncounted_paths: list[Path] = []
                for date, rows in index_rows_by_date:
                    counted_df, uncounted = _daily_file_df_from_index(rows, date, root)
                    if not counted_df.empty:
                        file_frames.append(counted_df)
                    uncounted_paths.extend(uncounted)
                if uncounted_paths:  # 카운트 NULL 파일만 parquet 폴백
                    frame = _daily_file_df_from_parquet(uncounted_paths, None)
                    if not frame.empty:
                        file_frames.append(frame)
            else:
                # 인덱스가 카운트/eqc를 완전히 못 주면 전량 parquet(모든 지표 정확)
                paths = []
                for date in dates:
                    paths.extend(selectors.iter_date_files(date))
                frame = _daily_file_df_from_parquet(paths, None)
                if not frame.empty:
                    file_frames.append(frame)
    except (FileNotFoundError, NotADirectoryError) as exc:
        raise L3SpiderServiceError(str(exc), status_code=404) from exc

    file_df = pd.concat(file_frames, ignore_index=True) if file_frames else pd.DataFrame()
    result = _aggregate_daily(file_df, dates)
    result["selectionTree"] = selection_tree
    run_stats = selectors.query_run_stats(dates)
    run_stat_details = run_stats.pop("_details", [])
    result["matrix"] = _include_analyzed_matrix_cells(
        result["matrix"],
        run_stat_details,
        rules,
    )
    if not file_df.empty and "line_name" in file_df.columns:
        id_to_name = dict(zip(file_df["line_id"].astype(str), file_df["line_name"].astype(str)))
        for entry in run_stats["byLine"]:
            entry["lineName"] = id_to_name.get(str(entry["lineId"]), entry["lineId"])
    run_stats["byLineName"] = _build_line_name_run_stats(run_stat_details, rules)
    result["runStats"] = run_stats
    _daily_summary_cache.set(cache_key, result)
    return result


def get_data(selection: dict[str, object], *, user: Any | None = None) -> dict[str, object]:
    """선택 조건과 필터에 맞는 차트 행 데이터를 반환합니다."""
    _empty = {"cols": [], "colData": []}

    if not _has_required_selection(selection):
        return _empty

    selected_eqcs = set(selection.get("selectedEqcs") or [])
    selected_step_bins = set(selection.get("selectedStepBins") or [])
    selected_ppid_bins = set(selection.get("selectedPpidBins") or [])
    selected_steps = set(selection.get("selectedSteps") or [])
    checked_eds_steps = set(selection.get("checkedEdsSteps") or [])
    checked_ppids = set(selection.get("checkedPpids") or [])
    checked_bins = set(selection.get("checkedBins") or [])

    if not selected_eqcs and not selected_step_bins and not selected_ppid_bins and not selected_steps:
        return _empty

    # ── 파일 타겟팅 ──────────────────────────────────────────────────────────
    # eds_step + step_seq + ppid 가 단일 값이면 해당 파일만 정확히 읽음
    # (전체 디렉토리 읽기 대비 최대 10~20x 적은 I/O)
    try:
        if len(checked_eds_steps) == 1 and len(selected_steps) == 1 and len(checked_ppids) == 1:
            files = list(selectors.iter_filter_candidate_files(
                dates=selection.get("dates") or [],
                line_ids=selection.get("lineIds") or [],
                process_ids=selection.get("processIds") or [],
                eds_step=next(iter(checked_eds_steps)),
                step_seq=next(iter(selected_steps)),
                ppid=next(iter(checked_ppids)),
            ))
        else:
            files = list(selectors.iter_data_files(selection))
    except FileNotFoundError as exc:
        raise L3SpiderServiceError(str(exc), status_code=404) from exc
    except NotADirectoryError as exc:
        raise L3SpiderServiceError(str(exc), status_code=400) from exc

    files = _filter_files_by_line_names(files, selection)

    # ── 병렬 읽기 ────────────────────────────────────────────────────────────
    raw_frames = _parallel_read(files, functools.partial(_read_chart_file, columns=CHART_COLUMNS))

    frames = []
    for frame in raw_frames:
        if checked_eds_steps and "eds_step" in frame.columns:
            frame = frame[frame["eds_step"].isin(checked_eds_steps)]
        if checked_ppids and "ppid" in frame.columns:
            frame = frame[frame["ppid"].isin(checked_ppids)]
        if checked_bins and "bin_name" in frame.columns:
            frame = frame[frame["bin_name"].isin(checked_bins)]
        if selected_eqcs and "eqc" in frame.columns:
            frame = frame[frame["eqc"].isin(selected_eqcs)]
        if selected_steps and "step_seq" in frame.columns:
            frame = frame[frame["step_seq"].isin(selected_steps)]
        if selected_step_bins and {"step_seq", "bin_name"}.issubset(frame.columns):
            step_bin = frame["step_seq"].astype(str) + "|||" + frame["bin_name"].astype(str)
            frame = frame[step_bin.isin(selected_step_bins)]
        if selected_ppid_bins and {"step_seq", "ppid", "bin_name"}.issubset(frame.columns):
            ppid_bin = (
                frame["step_seq"].astype(str)
                + "|||"
                + frame["ppid"].astype(str)
                + "|||"
                + frame["bin_name"].astype(str)
            )
            frame = frame[ppid_bin.isin(selected_ppid_bins)]
        if not frame.empty:
            frames.append(frame)

    if not frames:
        return _empty

    merged = pd.concat(frames, ignore_index=True)
    merged = _normalize_display_status(merged)
    merged = _apply_exclusion_filters(merged, user=user)

    if merged.empty:
        return _empty

    if selected_eqcs:
        merged = _sample_chart_points(merged, ["step_seq", "bin_name"])
    elif checked_bins or selected_step_bins or selected_ppid_bins:
        merged = _sample_chart_points(merged, ["eqc"])

    if "comment" not in merged.columns:
        merged["comment"] = None

    for column in ["tkin_time", "tkout_time"]:
        if column in merged.columns:
            try:
                merged[column] = merged[column].dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                merged[column] = merged[column].astype(str)

    # ── 컬럼 기반 직렬화 (JSON 크기 ~60% 절감 + orjson 인코딩) ───────────────
    return _dataframe_to_columnar(merged)


_trend_cache = TTLCache(ttl=300.0)


def get_trend(*, user: Any | None = None) -> dict[str, object]:
    """날짜별·라인별 이상감지 건수 트렌드를 반환합니다.

    반환: {"points": [{"date": str, "lineName": str, "hr": int, "wn": int}, ...]}
    날짜 오름차순, 라인명 오름차순 정렬.
    """
    cached = _trend_cache.get("all")
    if cached is not None:
        return cached

    rows = selectors.query_trend_data()
    if not rows:
        result: dict[str, object] = {"points": []}
        _trend_cache.set("all", result)
        return result

    completed_dates = selectors.query_completed_dates()

    combos = {(r["line_id"], r["process_id"], r["step_seq"]) for r in rows}
    name_map = {
        (lid, pid, sseq): line_name_rules.resolve_line_name(lid, pid, sseq)
        for lid, pid, sseq in combos
    }

    agg: dict[tuple[str, str, str], dict[str, int]] = {}
    for r in rows:
        date = r["date"]
        if completed_dates is not None and date not in completed_dates:
            continue
        line_name = name_map.get((r["line_id"], r["process_id"], r["step_seq"]), r["line_id"])
        process_id = r["process_id"]
        key = (date, line_name, process_id)
        cur = agg.get(key, {"hr": 0, "wn": 0})
        cur["hr"] += r["hr"]
        cur["wn"] += r["wn"]
        agg[key] = cur

    points = [
        {"date": date, "lineName": line_name, "processId": process_id, "hr": v["hr"], "wn": v["wn"]}
        for (date, line_name, process_id), v in sorted(agg.items())
    ]
    result = {"points": points}
    _trend_cache.set("all", result)
    return result


def get_filter_candidates(selection: dict[str, object], *, user: Any | None = None) -> dict[str, object]:
    """PPID 선택 경로(date/line/process/eds_step/step_seq#ppid#*)에서 High Risk EQPCH·Bin 후보를 반환합니다."""
    dates = selection.get("dates") or []
    line_ids = selection.get("lineIds") or []
    process_ids = selection.get("processIds") or []
    eds_step = selection.get("edsStep", "")
    step_seq = selection.get("stepSeq", "")
    ppid = selection.get("ppid", "")

    if not all([dates, line_ids, process_ids, eds_step, step_seq, ppid]):
        return {"eqcHighRiskBins": {}}

    try:
        files = list(selectors.iter_filter_candidate_files(dates, line_ids, process_ids, eds_step, step_seq, ppid))
    except (FileNotFoundError, NotADirectoryError) as exc:
        raise L3SpiderServiceError(str(exc), status_code=404) from exc

    files = _filter_files_by_line_names(files, selection)

    def _read_candidate_file(path: Path) -> pd.DataFrame | None:
        try:
            frame = selectors.read_parquet_columns(path, ["eqc", "bin_name", "display_status"])
            frame = _normalize_display_status(frame)
            frame = _add_path_context(frame, path)
            return frame
        except Exception as exc:
            print(f"[WARN] L3 Spider filter-candidates read failed: {path}: {exc}")
            return None

    frames = _parallel_read(files, _read_candidate_file)
    if not frames:
        return {"eqcHighRiskBins": {}}

    merged = pd.concat(frames, ignore_index=True)
    merged = _apply_exclusion_filters(merged, user=user)

    eqc_high_risk_bins: dict[str, list[str]] = {}
    if {"eqc", "bin_name", "display_status"}.issubset(merged.columns):
        high_risk_mask = merged["display_status"] == "High Risk Chamber"
        pairs = (
            merged.loc[high_risk_mask, ["eqc", "bin_name"]]
            .drop_duplicates()
            .sort_values(["eqc", "bin_name"])
        )
        eqc_high_risk_bins = {
            str(eqc): sorted(group["bin_name"].dropna().astype(str).tolist())
            for eqc, group in pairs.groupby("eqc", sort=True)
        }

    return {"eqcHighRiskBins": eqc_high_risk_bins}
