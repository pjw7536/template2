# =============================================================================
# 모듈: TTTM Spider 채점 코어 (framework-agnostic)
# 원본: tttm_dashboard_api.py 의 순수 채점 함수를 그대로 이식.
#   - sensor_power_score  = tttm_dashboard_api._sensor_power_score
#   - rms                 = tttm_dashboard_api._rms
#   - grade_from_severity = tttm_dashboard_api._grade_from_severity
#   - build_ttm_score_bundle   = tttm_dashboard_api._build_ttm_score_bundle
#   - build_trace_bundle_p2    = tttm_dashboard_api._build_trace_bundle_p2
#   - OES 레이더 빌더들         = tttm_dashboard_api._build_oes_step_category_radar 계열
# 주요 가정: Django/parquet 에 의존하지 않는다. 입력은 pandas DataFrame(pdf) 또는
#   OES row DataFrame 이며, 카테고리 계층은 catalog 모듈에서 주입한다.
#
# ⚠ 채점식은 도메인 검증 자산이라 임의 변경 금지 (SPEC §2 제약).
#   - Level=abs(양방향), Shape=max(0,·), Noise=max(0,·), 하드캡 100
#   - 계층 집계는 전부 순수 RMS. "조화평균 블렌드"는 폐기됨 → rms 로 고정.
#   - health = 100 - severity, ≤50 심각 / ≤70 주의 (하드코딩)
#
# 자가비교(REF==COMP) 가드: self_compare=True 이면 채점식을 타지 않고
#   챔버 health=100 / severity 0 으로 단락한다 (사용자 결정 2026-07-22).
# =============================================================================
from __future__ import annotations

import math
from typing import Any

from . import catalog

# ── own_score(=sensor_power_score) 상수: 원본과 동일 ────────────────────────
RAW_AXIS_CAP = 100.0                       # 원본 _RAW_AXIS_CAP
SENSOR_SCORE_AXIS_WEIGHTS = (1.0, 1.0, 1.3)  # 원본 _SENSOR_SCORE_AXIS_WEIGHTS
SENSOR_SCORE_POWER_P = 2.0                  # 원본 _SENSOR_SCORE_POWER_P

WARN_THRESHOLD_DEFAULT = 70.0
ALARM_THRESHOLD_DEFAULT = 50.0


# ════════════════════════════════════════════════════════════════════════════
#  기초 함수
# ════════════════════════════════════════════════════════════════════════════
def sensor_power_score(level: float, shape: float, jitter: float) -> tuple[float, str]:
    """
    원본 _sensor_power_score 그대로. 축 값의 가중 멱평균(POWER_P=2).
    level 은 abs()(양방향), shape/jitter 는 max(0,·). 각 축 min(100,·) 하드캡.
    """
    axes = [
        min(RAW_AXIS_CAP, abs(level)),
        min(RAW_AXIS_CAP, max(0.0, shape)),
        min(RAW_AXIS_CAP, max(0.0, jitter)),
    ]
    w = list(SENSOR_SCORE_AXIS_WEIGHTS)
    wsum = sum(w)
    w = [x / wsum for x in w]
    p = SENSOR_SCORE_POWER_P
    score = sum(wi * (ax ** p) for wi, ax in zip(w, axes)) ** (1.0 / p)
    dom_idx = axes.index(max(axes))
    dom = ["level", "shape", "jitter"][dom_idx]
    return float(score), dom


def rms(vals: list[float]) -> float:
    """원본 _rms 그대로. 빈 리스트는 0.0."""
    if not vals:
        return 0.0
    arr = [float(v) for v in vals]
    return (sum(v * v for v in arr) / len(arr)) ** 0.5


def blended_severity(vals: list[float]) -> float:
    """
    원본 _blended_severity 는 현재 그냥 rms(vals) 를 반환한다.
    "RMS + 조화평균 블렌드"는 수학적으로 산술평균과 항등이라 폐기된 이력이 있다.
    ⚠ 부활 금지 — 순수 RMS 로 고정한다 (SPEC §2.3).
    """
    return rms(vals)


def grade_from_severity(
    severity: float,
    warn_threshold: float = WARN_THRESHOLD_DEFAULT,
    alarm_threshold: float = ALARM_THRESHOLD_DEFAULT,
) -> str:
    """
    원본 _grade_from_severity 그대로.
    health = 100 - severity → health<=alarm(50) 심각 / <=warn(70) 주의 / 그외 정상.
    """
    health = 100.0 - severity
    if health <= alarm_threshold:
        return "심각"
    elif health <= warn_threshold:
        return "주의"
    return "정상"


def _clip100_health(severity: float) -> float:
    return round(max(0.0, min(100.0, 100.0 - severity)), 1)


# ════════════════════════════════════════════════════════════════════════════
#  자가비교 가드
# ════════════════════════════════════════════════════════════════════════════
def is_self_comparison(ref: dict, comp: dict) -> bool:
    """
    REF 와 COMP 선택이 동일 챔버·날짜면 자가비교. (line/eqp/chamber/date)
    원본 REF 선택엔 type 이 없으므로 type 은 비교에서 제외한다.
    """
    keys = ("line", "eqp", "chamber", "date")
    return all(str(ref.get(k, "")) == str(comp.get(k, "")) for k in keys)


def _self_compare_trace_bundle(pdf, chamber_name: str) -> dict:
    """자가비교: 모든 지표 100점(severity 0). 채점식을 타지 않는다."""
    sensors = []
    for idx, row in pdf.iterrows():
        sensors.append({
            "sensor": str(idx),
            "category": str(row.get("category", "ETC")),
            "deviation": 0.0,
            "dominant_axis": "level",
            "magnitude": 0.0,
            "shape": 0.0,
            "jitter": 0.0,
            "relationship": 0.0,
            "axis_deviation": 0.0,
            "score": 0.0,
            "grade": "정상",
            "trace": [],
        })
    radar_leaf = {cat: 100.0 for cat in catalog.LEAF_ORDER}
    radar_top = {cat: 100.0 for cat in catalog.TOP_ORDER}
    return {
        "name": chamber_name,
        "score": 100.0,
        "grade": "정상",
        "channels": {"chronic": 1.0, "acute": 1.0, "latent": 1.0},
        "radar": radar_top,
        "radar_leaf": radar_leaf,
        "worst_category": "",
        "worst_top3": [],
        "used_ppid": "",
        "used_recipe_id": "",
        "sensors": sensors,
        "self_compare": True,
    }


# ════════════════════════════════════════════════════════════════════════════
#  TRACE — TTTM Score (구 P3) 번들
# ════════════════════════════════════════════════════════════════════════════
def build_ttm_score_bundle(
    pdf,
    chamber_name: str,
    warn_threshold: float = WARN_THRESHOLD_DEFAULT,
    alarm_threshold: float = ALARM_THRESHOLD_DEFAULT,
    self_compare: bool = False,
) -> dict:
    """
    원본 _build_ttm_score_bundle 이식.
    own_score →(RMS) leaf severity →(RMS) top severity →(RMS) 전체 severity.
    각 계층은 round(...,1) 중간 반올림. 빈 카테고리도 0.0 으로 top RMS 분모에 포함.
    """
    if self_compare:
        return _self_compare_trace_bundle(pdf, chamber_name)

    sensors: list[dict[str, Any]] = []
    sensor_scores_by_cat: dict[str, list[float]] = {cat: [] for cat in catalog.LEAF_ORDER}

    for idx, row in pdf.iterrows():
        sid = str(idx)
        cat = str(row.get("category", "ETC"))
        level = float(row.get("level", 0.0) or 0.0)
        shape = float(row.get("shape", 0.0) or 0.0)
        jitter = float(row.get("jitter", 0.0) or 0.0)

        own_score, dom = sensor_power_score(level, shape, jitter)
        sensor_scores_by_cat.setdefault(cat, []).append(own_score)

        sensors.append({
            "sensor": sid,
            "category": cat,
            "deviation": round(own_score, 3),
            "dominant_axis": dom,
            "magnitude": round(level, 3),
            "shape": round(shape, 3),
            "jitter": round(jitter, 3),
            "relationship": 0.0,
            "axis_deviation": round(own_score, 3),
            "score": round(own_score, 3),
            "grade": grade_from_severity(own_score, warn_threshold, alarm_threshold),
            "trace": [],
        })

    sensors.sort(key=lambda x: -x["deviation"])

    combined_sev_leaf: dict[str, float] = {}
    for cat in catalog.LEAF_ORDER:
        vals = sensor_scores_by_cat.get(cat, [])
        combined_sev_leaf[cat] = round(blended_severity(vals), 1) if vals else 0.0

    combined_sev_top: dict[str, float] = {}
    for top in catalog.TOP_ORDER:
        children = catalog.CATEGORY_TREE.get(top)
        if children:
            vals = [combined_sev_leaf.get(c, 0.0) for c in children]
            combined_sev_top[top] = round(blended_severity(vals), 1) if vals else 0.0
        else:
            combined_sev_top[top] = combined_sev_leaf.get(top, 0.0)

    radar_leaf = {cat: _clip100_health(combined_sev_leaf[cat]) for cat in catalog.LEAF_ORDER}
    radar_top = {cat: _clip100_health(combined_sev_top[cat]) for cat in catalog.TOP_ORDER}

    top_sev_vals = list(combined_sev_top.values())
    final_severity = blended_severity(top_sev_vals) if top_sev_vals else 0.0
    health_score = _clip100_health(final_severity)

    grade = grade_from_severity(final_severity, warn_threshold, alarm_threshold)

    worst_rank = sorted(catalog.TOP_ORDER, key=lambda c: -combined_sev_top.get(c, 0.0))
    worst_category = worst_rank[0] if worst_rank else ""
    worst_top3 = worst_rank[:3]

    chronic_health = round(max(0.0, 1.0 - final_severity / 100.0), 3)
    acute_health = round(max(0.0, 1.0 - max(top_sev_vals) / 100.0), 3) if top_sev_vals else 1.0

    used_ppid, used_recipe_id = "", ""
    if len(pdf):
        for ppid_col, recipe_col in [("trace_ppid", "trace_recipe_id"), ("oes_ppid", "oes_recipe_id")]:
            if ppid_col in pdf.columns and recipe_col in pdf.columns:
                used_ppid = str(pdf[ppid_col].iloc[0])
                used_recipe_id = str(pdf[recipe_col].iloc[0])
                break

    return {
        "name": chamber_name,
        "score": health_score,
        "grade": grade,
        "channels": {"chronic": chronic_health, "acute": acute_health, "latent": 1.0},
        "radar": radar_top,
        "radar_leaf": radar_leaf,
        "worst_category": worst_category,
        "worst_top3": worst_top3,
        "used_ppid": used_ppid,
        "used_recipe_id": used_recipe_id,
        "sensors": sensors,
    }


# ════════════════════════════════════════════════════════════════════════════
#  TRACE — 웨이퍼 이상률 (구 P2, alarm_pct 기반) 번들
# ════════════════════════════════════════════════════════════════════════════
def build_trace_bundle_p2(
    pdf,
    chamber_name: str,
    warn_threshold: float = WARN_THRESHOLD_DEFAULT,
    alarm_threshold: float = ALARM_THRESHOLD_DEFAULT,
    self_compare: bool = False,
) -> dict:
    """
    원본 _build_trace_bundle_p2 이식. P2 는 축이 alarm_pct 하나뿐이라
    own_score = alarm_pct. 이후 leaf→top→전체 severity 는 순수 RMS(P3와 동일).
    """
    if self_compare:
        b = _self_compare_trace_bundle(pdf, chamber_name)
        for s in b["sensors"]:
            s["level"] = 0.0
        return b

    sensors: list[dict[str, Any]] = []
    sensor_scores_by_cat: dict[str, list[float]] = {cat: [] for cat in catalog.LEAF_ORDER}

    for idx, row in pdf.iterrows():
        alarm_pct = float(row.get("alarm_pct", 0.0) or 0.0)
        cat = str(row.get("category", "ETC"))
        own_score = max(0.0, alarm_pct)
        sensor_scores_by_cat.setdefault(cat, []).append(own_score)
        sensors.append({
            "sensor": str(idx),
            "category": cat,
            "level": alarm_pct,
            "shape": 0.0,
            "jitter": 0.0,
            "relationship": 0.0,
            "score": round(own_score, 3),
            "deviation": round(own_score, 3),
            "dominant_axis": "magnitude",
            "axis_deviation": round(own_score, 3),
            "grade": grade_from_severity(own_score, warn_threshold, alarm_threshold),
        })

    sensors.sort(key=lambda s: -s["deviation"])

    combined_sev_leaf: dict[str, float] = {}
    for cat in catalog.LEAF_ORDER:
        vals = sensor_scores_by_cat.get(cat, [])
        combined_sev_leaf[cat] = round(rms(vals), 1) if vals else 0.0

    combined_sev_top: dict[str, float] = {}
    for top in catalog.TOP_ORDER:
        children = catalog.CATEGORY_TREE.get(top)
        if children:
            vals = [combined_sev_leaf.get(c, 0.0) for c in children]
            combined_sev_top[top] = round(rms(vals), 1) if vals else 0.0
        else:
            combined_sev_top[top] = combined_sev_leaf.get(top, 0.0)

    radar_leaf = {cat: _clip100_health(combined_sev_leaf[cat]) for cat in catalog.LEAF_ORDER}
    radar = {cat: _clip100_health(combined_sev_top[cat]) for cat in catalog.TOP_ORDER}

    top_sev_vals = list(combined_sev_top.values())
    final_severity = rms(top_sev_vals) if top_sev_vals else 0.0
    score = _clip100_health(final_severity)
    grade = grade_from_severity(final_severity, warn_threshold, alarm_threshold)

    worst_rank = sorted(catalog.TOP_ORDER, key=lambda c: -combined_sev_top.get(c, 0.0))
    worst_category = worst_rank[0] if worst_rank else ""
    worst_top3 = worst_rank[:3]

    chronic_health = round(max(0.0, 1.0 - final_severity / 100.0), 3)
    acute_health = round(max(0.0, 1.0 - max(top_sev_vals) / 100.0), 3) if top_sev_vals else 1.0

    return {
        "name": chamber_name,
        "score": score,
        "grade": grade,
        "channels": {"chronic": chronic_health, "acute": acute_health, "latent": 1.0},
        "radar": radar,
        "radar_leaf": radar_leaf,
        "worst_category": worst_category,
        "worst_top3": worst_top3,
        "sensors": sensors,
    }


# ════════════════════════════════════════════════════════════════════════════
#  OES — 파장 카테고리 유틸 + STEP×화학종 RMS 레이더
# ════════════════════════════════════════════════════════════════════════════
def oes_category_order_and_labels(ranges: list) -> tuple[list[str], dict[str, str]]:
    """원본 _oes_category_order_and_labels: 카탈로그 등장 순서로 key 순서 + ETC 뒤에 붙임."""
    order: list[str] = []
    labels: dict[str, str] = {}
    for _low, _high, key, label in ranges:
        if key not in labels:
            order.append(key)
            labels[key] = label
    order.append("ETC")
    labels["ETC"] = "ETC"
    return order, labels


def categorize_wavelength(wl: float, ranges: list) -> str:
    """원본 _categorize_wavelength: 먼저 매칭되는 범위의 key, 없으면 ETC."""
    for low, high, key, _label in ranges:
        if low <= wl <= high:
            return key
    return "ETC"


def oes_wl_severity(dv: float) -> float:
    """
    원본 _wl_severity: delta_spectrum(0~5 정도) → 0~100 severity.
    severity = clip(max(0,dv)/3.0*50, 0, 100). (dv=3.0 이 alarm_th 기본값 → 정확히 50)
    """
    sev = max(0.0, dv) / 3.0 * 50.0
    if not math.isfinite(sev):
        sev = 0.0
    return min(100.0, sev)


def build_oes_step_category_radar(df, ranges: list, top_n_wavelengths: int = 8) -> dict[str, Any]:
    """
    원본 _build_oes_step_category_radar 이식 (OOB 경로).
    입력 df: 컬럼 step(str), wavelength(float), delta_spectrum(float).
    파장 severity →(RMS) 화학종 계열 →(RMS) STEP. TRACE 계층과 동일.
    """
    category_order, category_label = oes_category_order_and_labels(ranges)
    empty = {
        "steps": [], "step_category_radar": {}, "step_category_wavelengths": {},
        "step_overall": {}, "step_severity": {},
        "category_order": category_order, "category_label": category_label,
    }
    if not ranges or df is None or len(df) == 0:
        return empty

    steps_seen: list[str] = []
    step_cat_pairs: dict[str, dict[str, list[tuple[float, float]]]] = {}

    for row in df.itertuples(index=False):
        step = str(getattr(row, "step"))
        wl = getattr(row, "wavelength", None)
        dv = getattr(row, "delta_spectrum", None)
        if wl is None or dv is None or not math.isfinite(wl) or not math.isfinite(dv):
            continue
        if step not in step_cat_pairs:
            step_cat_pairs[step] = {}
            steps_seen.append(step)
        cat = categorize_wavelength(wl, ranges)
        step_cat_pairs[step].setdefault(cat, []).append((wl, dv))

    return _assemble_oes_radar(
        steps_seen, step_cat_pairs, category_order, category_label,
        top_n_wavelengths, severity_of=oes_wl_severity,
    )


def build_oes_decomp_step_category_radar(df, ranges: list, top_n_wavelengths: int = 8) -> dict[str, Any]:
    """
    원본 _build_oes_decomp_step_category_radar 이식 (Level/Shape/Jitter 경로).
    입력 df: 컬럼 step(str), wavelength(float), own_score(float, 이미 0~100 severity).
    own_score 를 severity 로 바로 사용 (delta_spectrum 변환 없음).
    """
    category_order, category_label = oes_category_order_and_labels(ranges)
    empty = {
        "steps": [], "step_category_radar": {}, "step_category_wavelengths": {},
        "step_overall": {}, "step_severity": {},
        "category_order": category_order, "category_label": category_label,
    }
    if not ranges or df is None or len(df) == 0:
        return empty

    steps_seen: list[str] = []
    step_cat_pairs: dict[str, dict[str, list[tuple[float, float]]]] = {}

    for row in df.itertuples(index=False):
        step = str(getattr(row, "step"))
        wl = getattr(row, "wavelength", None)
        sev = getattr(row, "own_score", None)
        if wl is None or sev is None or not math.isfinite(wl) or not math.isfinite(sev):
            continue
        if step not in step_cat_pairs:
            step_cat_pairs[step] = {}
            steps_seen.append(step)
        cat = categorize_wavelength(wl, ranges)
        step_cat_pairs[step].setdefault(cat, []).append((wl, sev))

    return _assemble_oes_radar(
        steps_seen, step_cat_pairs, category_order, category_label,
        top_n_wavelengths, severity_of=lambda s: s,
    )


def _assemble_oes_radar(steps_seen, step_cat_pairs, category_order, category_label,
                        top_n_wavelengths, severity_of) -> dict[str, Any]:
    """OOB/decomp 공통 조립부. severity_of 로 (wl,value)→severity 변환만 다르다."""
    step_category_radar: dict[str, dict[str, float]] = {}
    step_category_wavelengths: dict[str, dict[str, list[dict[str, float]]]] = {}
    step_overall: dict[str, float] = {}
    step_severity: dict[str, float] = {}

    for step in steps_seen:
        pair_map = step_cat_pairs.get(step, {})
        radar: dict[str, float] = {}
        cat_severities: list[float] = []
        wl_picks: dict[str, list[dict[str, float]]] = {}

        for cat in category_order:
            pairs = pair_map.get(cat, [])
            wl_severities = [severity_of(v) for _wl, v in pairs]
            cat_sev = rms(wl_severities) if wl_severities else 0.0
            radar[cat] = round(max(0.0, min(100.0, 100.0 - cat_sev)), 1)
            cat_severities.append(cat_sev)

            top_pairs = sorted(pairs, key=lambda p: p[1], reverse=True)[:top_n_wavelengths]
            wl_picks[cat] = [
                {"wavelength": round(wl, 2), "delta_spectrum": round(v, 4)}
                for wl, v in top_pairs
            ]

        step_sev = rms(cat_severities) if cat_severities else 0.0
        step_category_radar[step] = radar
        step_category_wavelengths[step] = wl_picks
        step_severity[step] = round(step_sev, 3)
        step_overall[step] = round(max(0.0, min(100.0, 100.0 - step_sev)), 1)

    return {
        "steps": steps_seen,
        "step_category_radar": step_category_radar,
        "step_category_wavelengths": step_category_wavelengths,
        "step_overall": step_overall,
        "step_severity": step_severity,
        "category_order": category_order,
        "category_label": category_label,
    }
