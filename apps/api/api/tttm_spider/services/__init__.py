# =============================================================================
# 모듈: TTTM Spider 서비스 (읽기 전용 번들 빌더)
# 원본: tttm_dashboard_api.py 의 _load_result_pdf / _filter_pdf_by_recipe /
#   _build_trace_meta / _build_oes_bundle / _build_oes_decomp_bundle /
#   _render_bundle 를 이식. 채점 수식은 ..scoring 에 있다.
# 주요 가정: scores.parquet 은 알고리즘 서버가 미리 계산해 둔다(파이프라인 미실행).
#   자가비교(REF==COMP)는 데이터타입 무관하게 health=100 으로 단락한다(사용자 결정).
# =============================================================================
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .. import catalog, scoring, selectors

WARN_THRESHOLD = 70.0
ALARM_THRESHOLD = 50.0


class TttmSpiderServiceError(Exception):
    """서비스 계층 에러(HTTP 상태코드 포함)."""

    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


# ════════════════════════════════════════════════════════════════════════════
#  콤보 옵션
# ════════════════════════════════════════════════════════════════════════════
def get_combo_options(level: str, line: str | None, eqp: str | None, chamber: str | None) -> dict[str, Any]:
    try:
        path = selectors.combo_path(level, line, eqp, chamber)
    except selectors.TttmSpiderPathError as exc:
        raise TttmSpiderServiceError(str(exc), status_code=400) from exc
    items = selectors.list_child_dirs(path)
    # date 는 최신 우선 정렬.
    if level == "date":
        items = sorted(items, reverse=True)
    return {"level": level, "path": str(path), "items": items}


def get_target_lotwf(eqp: str, chamber: str) -> dict[str, Any]:
    """(eqp, chamber)에서 진행된 lotwf 목록(lot/wf·recipe_id·tkin_time)."""
    items = selectors.read_lotwf(eqp, chamber)
    return {"eqp": eqp, "chamber": chamber, "items": items}


def get_golden_lotwf(recipe_id: str | None) -> dict[str, Any]:
    """타설비검증 REF 후보: 골든 챔버 lotwf(최근 먼저)."""
    return {"recipe_id": recipe_id or "", "items": selectors.read_golden_lotwf(recipe_id)}


def get_eqps() -> dict[str, Any]:
    """전체 eqp 목록(자동완성용)."""
    return {"items": selectors.read_eqps()}


def get_chambers_for_eqp(eqp: str) -> dict[str, Any]:
    """eqp 에 존재하는 chamber 목록(eqp만 입력하고 추가할 때 전체 챔버 조회용)."""
    return {"eqp": eqp, "items": selectors.read_chambers_for_eqp(eqp)}


def get_result_status(items: list[dict]) -> dict[str, Any]:
    """조합별 계산 결과(scores.parquet) 존재 여부. 순서 유지(프론트가 인덱스로 매핑)."""
    out = []
    for it in items or []:
        ref = it.get("ref") or {}
        comp = it.get("comp") or {}
        dt = it.get("dataType") or "trace"
        try:
            p = selectors.build_scores_parquet_path(ref, comp, dt)
            out.append({"exists": bool(p.exists())})
        except Exception:
            out.append({"exists": False})
    return {"items": out}


def get_type_options() -> dict[str, Any]:
    return {"items": [
        {"value": "process", "label": "PW (process)"},
        {"value": "ag", "label": "NPW (ag)"},
    ]}


def get_data_type_options() -> dict[str, Any]:
    return {"items": [
        {"value": "trace", "label": "TRACE"},
        {"value": "oes", "label": "OES"},
    ]}


# ════════════════════════════════════════════════════════════════════════════
#  TRACE 리더
# ════════════════════════════════════════════════════════════════════════════
def _load_result_pdf(scores_path: Path) -> pd.DataFrame:
    """
    원본 _load_result_pdf 이식. scores.parquet(trace) → item_name@step 인덱스,
    category(맵 조인) + level/shape/jitter(=delta_* rename) + alarm_pct.
    """
    raw = selectors.read_scores_parquet(scores_path)
    if raw is None:
        raise TttmSpiderServiceError(f"scores.parquet not found: {scores_path}", status_code=404)

    cat_map = catalog.load_sensor_category_map()

    rename = {"delta_level": "level", "delta_shape": "shape", "delta_jitter": "jitter"}
    keep = ["item_name", "step", "delta_level", "delta_shape", "delta_jitter"]
    optional = ["alarm_pct", "trace_ppid", "trace_recipe_id", "oes_ppid", "oes_recipe_id"]
    cols = [c for c in keep if c in raw.columns] + [c for c in optional if c in raw.columns]
    pdf = raw[cols].rename(columns=rename).copy()

    for axis in ("level", "shape", "jitter"):
        if axis not in pdf.columns:
            pdf[axis] = 0.0
    if "alarm_pct" not in pdf.columns:
        pdf["alarm_pct"] = 0.0

    pdf["category"] = pdf["item_name"].map(cat_map).fillna("ETC")
    pdf.index = pdf["item_name"].astype(str) + "@" + pdf["step"].astype(str)
    pdf = pdf.drop(columns=[c for c in ("item_name", "step") if c in pdf.columns])
    ordered = ["category"] + [c for c in pdf.columns if c != "category"]
    return pdf[ordered]


def _filter_pdf_by_recipe(pdf: pd.DataFrame, requested_recipe_id: str | None) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    원본 _filter_pdf_by_recipe 이식. UPSERT 저장으로 여러 recipe 행이 섞여 있을 수 있어
    반드시 하나의 recipe_id 로 좁힌다. (경로에 recipe_id 가 없어서 생기는 §7.1 대응)
    """
    info: dict[str, Any] = {"available_recipe_ids": [], "recipe_mixed_warning": False}
    if pdf.empty or "trace_recipe_id" not in pdf.columns:
        return pdf, info
    available = sorted({
        str(v) for v in pdf["trace_recipe_id"].dropna().unique()
        if str(v) not in ("", "nan", "None")
    })
    info["available_recipe_ids"] = available
    if len(available) <= 1:
        return pdf, info
    if requested_recipe_id and str(requested_recipe_id) in available:
        return pdf[pdf["trace_recipe_id"].astype(str) == str(requested_recipe_id)].copy(), info
    chosen = str(pdf["trace_recipe_id"].astype(str).value_counts().idxmax())
    info["recipe_mixed_warning"] = True
    return pdf[pdf["trace_recipe_id"].astype(str) == chosen].copy(), info


def _build_trace_meta(pdf: pd.DataFrame) -> dict[str, Any]:
    """원본 _build_trace_meta 이식. catalog 계층 메타."""
    sensor_category = {str(idx): str(row.get("category", "ETC")) for idx, row in pdf.iterrows()}
    return {
        "warn_threshold": WARN_THRESHOLD,
        "alarm_threshold": ALARM_THRESHOLD,
        "normal_median": 100.0,
        "n_points": 100,
        "n_fleet_units": 0,
        "n_fleet_repeats": 0,
        "reference_method": "precomputed_result_only",
        "catalog_is_stub": catalog.CATALOG_IS_STUB,
        "category_order": catalog.TOP_ORDER,
        "category_label": catalog.TOP_LABEL,
        "leaf_order": catalog.LEAF_ORDER,
        "leaf_label": catalog.LEAF_LABEL,
        "category_tree": catalog.CATEGORY_TREE,
        "leaf_to_parent": {
            leaf: catalog.leaf_parent(leaf) for leaf in catalog.LEAF_ORDER if catalog.leaf_parent(leaf) != leaf
        },
        "ref_radar": {cat: 100.0 for cat in catalog.TOP_ORDER},
        "ref_radar_leaf": {cat: 100.0 for cat in catalog.LEAF_ORDER},
        "sensor_units": {sid: "" for sid in sensor_category},
        "sensor_category": sensor_category,
        "relationship_pairs": {},
        "category_fleet_matrix": {},
    }


def _build_trace_bundle(ref: dict, comp: dict, stage: str, trace_recipe_id: str | None) -> tuple[dict, Path]:
    scores_path = selectors.build_scores_parquet_path(ref, comp, "trace")
    pdf = _load_result_pdf(scores_path)
    pdf, recipe_info = _filter_pdf_by_recipe(pdf, trace_recipe_id)

    chamber_name = f"{comp['eqp']}-{comp['chamber']}"
    requested_stage = (stage or "P3").upper()

    meta = _build_trace_meta(pdf)
    chamber_p3 = scoring.build_ttm_score_bundle(pdf, chamber_name, WARN_THRESHOLD, ALARM_THRESHOLD)
    chamber_p2 = scoring.build_trace_bundle_p2(pdf, chamber_name, WARN_THRESHOLD, ALARM_THRESHOLD)

    for b in (chamber_p3, chamber_p2):
        b["available_recipe_ids"] = recipe_info["available_recipe_ids"]
        b["recipe_mixed_warning"] = recipe_info["recipe_mixed_warning"]

    primary = dict(chamber_p2 if requested_stage == "P2" else chamber_p3)
    primary["by_stage"] = {"P2": chamber_p2, "P3": chamber_p3}
    bundle = {"meta": meta, "chambers": [primary], "ref_bands": {}}
    return bundle, scores_path


# ════════════════════════════════════════════════════════════════════════════
#  OES 리더
# ════════════════════════════════════════════════════════════════════════════
def _load_oes_score_rows(scores_path: Path) -> tuple[list[dict[str, Any]], pd.DataFrame]:
    """원본 _load_oes_score_rows(요약) + 레이더용 raw df 를 함께 반환."""
    raw = selectors.read_scores_parquet(scores_path)
    if raw is None:
        raise TttmSpiderServiceError(f"scores.parquet not found: {scores_path}", status_code=404)
    required = {"step", "delta_spectrum", "flagged_wl"}
    missing = required - set(raw.columns)
    if missing:
        raise TttmSpiderServiceError(
            f"OES scores.parquet missing columns: {sorted(missing)}", status_code=500)

    grp = (
        raw.groupby("step", as_index=False)
        .agg(delta_spectrum=("delta_spectrum", "median"), flagged_wl=("flagged_wl", "median"))
        .sort_values("flagged_wl", ascending=False)
    )
    rows = [
        {"step": str(r["step"]),
         "delta_spectrum": float(r["delta_spectrum"]) if pd.notna(r["delta_spectrum"]) else None,
         "flagged_wl": float(r["flagged_wl"]) if pd.notna(r["flagged_wl"]) else None}
        for _, r in grp.iterrows()
    ]
    return rows, raw


def _build_oes_bundle(ref: dict, comp: dict, stage: str) -> tuple[dict, Path]:
    scores_path = selectors.build_scores_parquet_path(ref, comp, "oes")
    rows, raw = _load_oes_score_rows(scores_path)
    ranges = catalog.load_oes_wavelength_catalog()

    step_radar = scoring.build_oes_step_category_radar(
        raw[["step", "wavelength", "delta_spectrum"]] if "wavelength" in raw.columns else pd.DataFrame(),
        ranges,
    )
    return _assemble_oes_bundle(comp, rows, step_radar, "oes_result_only"), scores_path


def _build_oes_decomp_bundle(ref: dict, comp: dict, stage: str) -> tuple[dict, Path]:
    scores_path = selectors.build_scores_parquet_path(ref, comp, "oes_decomp")
    raw = selectors.read_scores_parquet(scores_path)
    if raw is None:
        raise TttmSpiderServiceError(f"scores.parquet not found: {scores_path}", status_code=404)
    ranges = catalog.load_oes_wavelength_catalog()
    step_radar = scoring.build_oes_decomp_step_category_radar(
        raw[["step", "wavelength", "own_score"]] if {"step", "wavelength", "own_score"}.issubset(raw.columns) else pd.DataFrame(),
        ranges,
    )
    rows = [{"step": s, "delta_spectrum": step_radar["step_severity"].get(s, 0.0),
             "flagged_wl": step_radar["step_severity"].get(s, 0.0)}
            for s in step_radar["step_overall"].keys()]
    rows.sort(key=lambda r: r["delta_spectrum"], reverse=True)
    return _assemble_oes_bundle(comp, rows, step_radar, "oes_decomp_level_shape_jitter"), scores_path


def _assemble_oes_bundle(comp: dict, rows: list[dict], step_radar: dict, reference_method: str) -> dict:
    """OES(oob/decomp) 공통 번들 조립. 챔버 severity = RMS(step severity들)."""
    chamber_name = f"{comp['eqp']}-{comp['chamber']}"
    step_overall = step_radar["step_overall"]
    step_severity_map = step_radar["step_severity"]
    step_severities = list(step_severity_map.values())
    chamber_severity = scoring.rms(step_severities) if step_severities else 0.0
    health = round(max(0.0, min(100.0, 100.0 - chamber_severity)), 1)
    grade = scoring.grade_from_severity(chamber_severity, WARN_THRESHOLD, ALARM_THRESHOLD)
    worst_step = min(step_overall, key=lambda k: step_overall[k]) if step_overall else ""

    chamber = {
        "name": chamber_name,
        "score": health,
        "grade": grade,
        "channels": {"chronic": 1.0, "acute": 1.0, "latent": 1.0},
        "radar": step_overall,
        "radar_leaf": step_overall,
        "step_category_radar": step_radar["step_category_radar"],
        "step_category_wavelengths": step_radar["step_category_wavelengths"],
        "worst_category": worst_step,
        "worst_top3": [],
        "sensors": [],
        "oes_rows": rows,
        "by_stage": {
            "P2": {"score": health, "grade": grade, "gradable": bool(step_severities)},
            "P3": {"score": health, "grade": grade, "gradable": bool(step_severities)},
        },
    }
    meta = {
        "warn_threshold": WARN_THRESHOLD, "alarm_threshold": ALARM_THRESHOLD, "normal_median": "",
        "reference_method": reference_method,
        "category_order": step_radar["steps"],
        "category_label": {s: s for s in step_radar["steps"]},
        "leaf_order": step_radar["steps"],
        "leaf_label": {s: s for s in step_radar["steps"]},
        "oes_species_order": step_radar["category_order"],
        "oes_species_label": step_radar["category_label"],
        "category_tree": {}, "leaf_to_parent": {}, "ref_radar": {}, "ref_radar_leaf": {},
        "sensor_units": {}, "sensor_category": {}, "relationship_pairs": {}, "category_fleet_matrix": {},
    }
    return {"meta": meta, "chambers": [chamber], "ref_bands": {}}


# ════════════════════════════════════════════════════════════════════════════
#  자가비교 → 전부 100 단락
# ════════════════════════════════════════════════════════════════════════════
def _force_perfect(bundle: dict) -> dict:
    """자가비교: 채점 결과를 무시하고 모든 지표를 100(severity 0)으로 단락한다."""
    for chamber in bundle.get("chambers", []):
        chamber["score"] = 100.0
        chamber["grade"] = "정상"
        chamber["channels"] = {"chronic": 1.0, "acute": 1.0, "latent": 1.0}
        for key in ("radar", "radar_leaf"):
            if isinstance(chamber.get(key), dict):
                chamber[key] = {k: 100.0 for k in chamber[key]}
        if isinstance(chamber.get("step_category_radar"), dict):
            chamber["step_category_radar"] = {
                s: {k: 100.0 for k in cats} for s, cats in chamber["step_category_radar"].items()
            }
        for s in chamber.get("sensors", []):
            for f in ("deviation", "score", "axis_deviation", "level", "shape", "jitter"):
                if f in s:
                    s[f] = 0.0
            s["grade"] = "정상"
        for r in chamber.get("oes_rows", []):
            r["delta_spectrum"] = 0.0
            r["flagged_wl"] = 0.0
        for st in ("P2", "P3"):
            if st in chamber.get("by_stage", {}):
                chamber["by_stage"][st].update({"score": 100.0, "grade": "정상"})
        chamber["self_compare"] = True
    return bundle


# ════════════════════════════════════════════════════════════════════════════
#  오케스트레이터
# ════════════════════════════════════════════════════════════════════════════
def build_dashboard_bundle(
    *, ref: dict, comp: dict, data_type: str,
    stage: str | None = None, oes_method: str = "oob",
    trace_recipe_id: str | None = None,
) -> dict[str, Any]:
    """
    원본 _render_bundle 이식. data_type/oes_method 에 따라 번들 생성.
    자가비교면 _force_perfect 로 100 단락.
    """
    try:
        dt = selectors.normalize_data_type(data_type)
    except selectors.TttmSpiderPathError as exc:
        raise TttmSpiderServiceError(str(exc), status_code=400) from exc

    self_compare = scoring.is_self_comparison(ref, comp)

    if dt == "oes":
        if (oes_method or "oob").lower() == "decomp":
            bundle, _ = _build_oes_decomp_bundle(ref, comp, stage)
        else:
            bundle, _ = _build_oes_bundle(ref, comp, stage)
    else:
        bundle, _ = _build_trace_bundle(ref, comp, stage, trace_recipe_id)

    if self_compare:
        bundle = _force_perfect(bundle)
    return _sanitize(bundle)


def build_sensor_trace_response(*, ref: dict, comp: dict, data_type: str, sensor_key: str) -> dict[str, Any]:
    """
    원본 _build_sensor_trace_response(TRACE) 이식. 센서 원파형(REF/COMP) + decomp(shape/jitter).
    OES 원파형은 다음 단계에서.
    """
    try:
        dt = selectors.normalize_data_type(data_type)
        comp_type = selectors.normalize_comp_type(comp.get("type", ""))
    except selectors.TttmSpiderPathError as exc:
        raise TttmSpiderServiceError(str(exc), status_code=400) from exc

    comp_label = f"{comp['eqp']}-{comp['chamber']}"
    ref_label = f"{ref['eqp']}-{ref['chamber']}"

    if dt == "oes":
        return {"trace_kind": "oes", "sensor": sensor_key, "step": sensor_key, "series": [],
                "recipes": [], "decomp": None, "comp_label": comp_label, "ref_label": ref_label,
                "stats": {}, "message": "OES 원파형/Full Spectrum은 다음 단계에서 지원됩니다."}

    if "@" in sensor_key:
        param, step = sensor_key.split("@", 1)
    else:
        param, step = sensor_key, ""

    comp_series = selectors.read_trace_series(comp, comp_type, param, step, "comp")
    ref_series = selectors.read_trace_series(ref, comp_type, param, step, "ref")
    series = comp_series + ref_series
    recipes = sorted({s["recipe_id"] for s in series if s["recipe_id"]})

    decomp_dir = selectors.build_decomp_dir(ref, comp, param, step)
    shape = selectors.read_decomp_shape(decomp_dir / "shape.parquet")
    jitter = selectors.read_decomp_jitter(decomp_dir / "jitter.parquet")
    decomp = {"shape": shape, "jitter": jitter} if (shape or jitter) else None

    return _sanitize({
        "trace_kind": "trace", "sensor": param, "step": step,
        "series": series, "recipes": recipes, "decomp": decomp,
        "comp_label": comp_label, "ref_label": ref_label,
        "stats": {"series_total": len(series), "comp_files": len(comp_series), "ref_files": len(ref_series),
                  "message": "" if series else "선택한 sensor/step에 해당하는 trace 데이터가 없습니다."},
        "message": "" if series else "선택한 sensor/step에 해당하는 trace 데이터가 없습니다.",
    })


def _sanitize(obj):
    """NaN/Inf → None (브라우저 JSON.parse 보호). 원본 _sanitize_json_floats."""
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, (np.floating,)):
        v = float(obj)
        return v if math.isfinite(v) else None
    if isinstance(obj, (np.integer,)):
        return int(obj)
    return obj
