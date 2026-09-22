# =============================================================================
# 모듈: TTTM Spider 읽기 전용 접근자
# 주요 함수: get_data_root, get_result_root, build_scores_parquet_path,
#            list_child_dirs, read_scores_parquet
# 주요 가정: result 는 알고리즘 서버가 미리 계산한 score_data parquet 이다.
#            이 앱은 파이프라인을 돌리지 않고 읽기만 한다 (SPEC §10/§11).
# 경로 스키마(원본 save_results_참고용.py / tttm_dashboard_api.py 와 동일):
#   {RESULT}/score_data/ref_line=/ref_eqp=/ref_ch=/ref_dt=/
#            comp_line=/comp_eqp=/comp_ch=/comp_dt=/type=/data_type=/scores.parquet
# =============================================================================
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
from django.conf import settings

_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9_.\-]+$")


class TttmSpiderPathError(ValueError):
    """경로 구성 요소가 안전하지 않을 때."""

    status_code = 400


def get_data_root() -> Path:
    """원본 데이터(콤보 조회용) 루트. /{...}/data 아래 line/eqp/chamber/date 트리."""
    return Path(settings.TTTM_SPIDER_DATA_ROOT).expanduser().resolve()


def get_result_root() -> Path:
    """결과 parquet 루트. /{...}/result 아래 score_data/... 트리."""
    return Path(settings.TTTM_SPIDER_RESULT_ROOT).expanduser().resolve()


def safe_segment(value: str, name: str) -> str:
    """경로 세그먼트 안전성 검사(../ 및 특수문자 차단)."""
    v = str(value or "").strip()
    if not v or ".." in v or not _SAFE_SEGMENT.match(v):
        raise TttmSpiderPathError(f"invalid path segment {name}={value!r}")
    return v


def normalize_comp_type(value: str) -> str:
    """원본 _normalize_comp_type: PW→process, NPW→ag."""
    v = (value or "").strip().lower()
    if v in {"pw", "process", "pw (process)"}:
        return "process"
    if v in {"npw", "ag", "npw (ag)"}:
        return "ag"
    raise TttmSpiderPathError("comp type must be one of: process, ag, PW (process), NPW (ag)")


def normalize_data_type(value: str) -> str:
    v = (value or "").strip().lower()
    if v in {"trace", "oes", "oes_decomp"}:
        return v
    raise TttmSpiderPathError("data_type must be trace, oes, or oes_decomp")


def date_seg(value: str) -> str:
    """원본 _date_for_result_path: 'YYYY-MM-DD ...' → 'YYYY-MM-DD'."""
    v = str(value or "").strip()
    if len(v) >= 10 and v[4] == "-" and v[7] == "-":
        return v[:10]
    return v.split()[0] if v.split() else v


def _safe_join(base: Path, *parts: str) -> Path:
    """base 하위로만 join 되도록 강제(경로 이탈 차단)."""
    base_resolved = base.resolve()
    target = base_resolved.joinpath(*parts).resolve()
    try:
        target.relative_to(base_resolved)
    except ValueError:
        raise TttmSpiderPathError("path escapes base")
    return target


def build_scores_parquet_path(ref: dict, comp: dict, data_type: str) -> Path:
    """
    원본 _build_scores_parquet_path 이식. ref/comp 는
    {line,eqp,chamber,date}(comp 는 추가로 type) 를 가진 dict.
    """
    comp_type = normalize_comp_type(comp.get("type", ""))
    dt = normalize_data_type(data_type)
    return _safe_join(
        get_result_root(),
        "score_data",
        f"ref_line={safe_segment(ref['line'], 'ref.line')}",
        f"ref_eqp={safe_segment(ref['eqp'], 'ref.eqp')}",
        f"ref_ch={safe_segment(ref['chamber'], 'ref.chamber')}",
        f"ref_dt={date_seg(ref['date'])}",
        f"comp_line={safe_segment(comp['line'], 'comp.line')}",
        f"comp_eqp={safe_segment(comp['eqp'], 'comp.eqp')}",
        f"comp_ch={safe_segment(comp['chamber'], 'comp.chamber')}",
        f"comp_dt={date_seg(comp['date'])}",
        f"type={comp_type}",
        f"data_type={dt}",
        "scores.parquet",
    )


def read_scores_parquet(path: Path) -> pd.DataFrame | None:
    """scores.parquet 을 읽어 pandas DataFrame 으로. 없으면 None."""
    if not path.exists():
        return None
    return pd.read_parquet(path, engine="pyarrow")


# ── 콤보(선택 캐스케이드) ────────────────────────────────────────────────────
def list_child_dirs(path: Path) -> list[str]:
    """디렉토리 하위의 (숨김 제외) 폴더명 목록. 없으면 빈 리스트."""
    if not path.exists() or not path.is_dir():
        return []
    return sorted(p.name for p in path.iterdir() if p.is_dir() and not p.name.startswith("."))


def get_lotwf_index_path() -> Path:
    """mock lotwf 인덱스 parquet 경로 ({ROOT}/lotwf_index.parquet)."""
    return get_data_root().parent / "lotwf_index.parquet"


def _read_lotwf_index() -> "pd.DataFrame | None":
    p = get_lotwf_index_path()
    if not p.exists():
        return None
    try:
        return pd.read_parquet(p, engine="pyarrow")
    except Exception:
        return None


def read_lotwf(eqp: str, chamber: str) -> list[dict]:
    """(eqp, chamber) 에서 진행된 lotwf 목록. tkin_time 내림차순(최근 먼저)."""
    df = _read_lotwf_index()
    if df is None:
        return []
    df = df[(df["eqp"].astype(str) == str(eqp)) & (df["chamber"].astype(str) == str(chamber))]
    if df.empty:
        return []
    df = df.sort_values("tkin_time", ascending=False)
    return [
        {k: (str(row[k]) if k not in ("is_golden",) else bool(row.get("is_golden", False)))
         for k in ("line", "eqp", "chamber", "date", "lot_id", "slot_no", "recipe_id", "tkin_time", "is_golden")
         if k in row}
        for _, row in df.iterrows()
    ]


def read_eqps() -> list[str]:
    """lotwf 인덱스의 전체 eqp 목록(자동완성용)."""
    df = _read_lotwf_index()
    if df is None:
        return []
    return sorted(str(e) for e in df["eqp"].unique())


def read_chambers_for_eqp(eqp: str) -> list[str]:
    """eqp 에 존재하는 chamber 목록(lotwf 인덱스 기준). eqp만 넣고 추가 시 사용."""
    df = _read_lotwf_index()
    if df is None:
        return []
    df = df[df["eqp"].astype(str) == str(eqp)]
    if df.empty:
        return []
    return sorted(str(c) for c in df["chamber"].unique())


def read_golden_lotwf(recipe_id: str | None = None) -> list[dict]:
    """골든 챔버(is_golden)로 진행된 lotwf. 타설비검증 REF 후보. 최근 먼저."""
    df = _read_lotwf_index()
    if df is None or "is_golden" not in df.columns:
        return []
    df = df[df["is_golden"].astype(bool)]
    if recipe_id:
        df = df[df["recipe_id"].astype(str) == str(recipe_id)]
    if df.empty:
        return []
    df = df.sort_values("tkin_time", ascending=False)
    return [
        {k: (str(row[k]) if k != "is_golden" else bool(row.get("is_golden", False)))
         for k in ("line", "eqp", "chamber", "date", "lot_id", "slot_no", "recipe_id", "tkin_time", "is_golden")
         if k in row}
        for _, row in df.iterrows()
    ]


def build_trace_glob(sel: dict, comp_type: str, param: str) -> str:
    """
    RAW trace parquet glob (드릴다운 원파형용).
    {DATA}/{line}/{eqp}/{chamber}/{date}/trace/type={type}/trace_param_name={param}/*.parquet
    (ppid/recipe/priority 중간 폴더가 있어도 되도록 재귀 glob 로 넓게 잡는다.)
    """
    base = _safe_join(
        get_data_root(),
        safe_segment(sel["line"], "line"),
        safe_segment(sel["eqp"], "eqp"),
        safe_segment(sel["chamber"], "chamber"),
        date_seg(sel["date"]),
        "trace",
        f"type={comp_type}",
    )
    return str(base / "**" / f"trace_param_name={safe_segment(param, 'param')}" / "**" / "*.parquet")


def read_trace_series(sel: dict, comp_type: str, param: str, step: str, side: str,
                      max_series: int = 60, max_points: int = 2000) -> list[dict]:
    """RAW trace 를 (lot_id, slot_no) 별 시계열 series 로. ch_step==step 만."""
    import glob as _glob

    files = sorted(_glob.glob(build_trace_glob(sel, comp_type, param), recursive=True))
    if not files:
        return []
    try:
        df = pd.concat([pd.read_parquet(f, engine="pyarrow") for f in files], ignore_index=True)
    except Exception:
        return []
    for col in ("ch_step", "Time", "value"):
        if col not in df.columns:
            return []
    df = df[df["ch_step"].astype(str) == str(step)].copy()
    if df.empty:
        return []
    df["Time"] = pd.to_numeric(df["Time"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["Time", "value"])
    for col in ("lot_id", "slot_no", "recipe_id"):
        if col not in df.columns:
            df[col] = ""

    series: list[dict] = []
    for (lot, slot, rcp), grp in df.groupby(["lot_id", "slot_no", "recipe_id"], sort=False):
        g = grp.sort_values("Time")
        pts = list(zip(g["Time"].tolist(), g["value"].tolist()))
        if len(pts) > max_points:
            stepn = len(pts) / max_points
            pts = [pts[int(i * stepn)] for i in range(max_points)]
        if len(pts) < 2:
            continue
        series.append({
            "side": side, "recipe_id": str(rcp), "lot_id": str(lot), "slot_no": str(slot),
            "points": [[float(t), float(v)] for t, v in pts], "n_points": len(pts),
        })
        if len(series) >= max_series:
            break
    return series


def build_decomp_dir(ref: dict, comp: dict, param: str, step: str) -> Path:
    """
    decomp_data 경로(save_results _decomp_dir 와 동일).
    {RESULT}/decomp_data/ref_line=/.../comp_dt=/type=/param=/ch_step=/
    """
    comp_type = normalize_comp_type(comp.get("type", ""))
    return _safe_join(
        get_result_root(), "decomp_data",
        f"ref_line={safe_segment(ref['line'], 'ref.line')}",
        f"ref_eqp={safe_segment(ref['eqp'], 'ref.eqp')}",
        f"ref_ch={safe_segment(ref['chamber'], 'ref.chamber')}",
        f"ref_dt={date_seg(ref['date'])}",
        f"comp_line={safe_segment(comp['line'], 'comp.line')}",
        f"comp_eqp={safe_segment(comp['eqp'], 'comp.eqp')}",
        f"comp_ch={safe_segment(comp['chamber'], 'comp.chamber')}",
        f"comp_dt={date_seg(comp['date'])}",
        f"type={comp_type}",
        f"param={safe_segment(param, 'param')}",
        f"ch_step={safe_segment(str(step), 'step')}",
    )


def read_decomp_shape(shape_path: Path) -> dict | None:
    """shape.parquet → {tube:{q50,usl,lsl}, ref_curves:[...], comp_curves:[...]}."""
    if not shape_path.exists():
        return None
    try:
        df = pd.read_parquet(shape_path, engine="pyarrow")
    except Exception:
        return None
    if not {"group", "phase", "value"}.issubset(df.columns):
        return None
    out = {"tube": {"q50": None, "usl": None, "lsl": None}, "ref_curves": [], "comp_curves": []}
    for gname, grp in df.groupby("group", sort=False):
        g = grp.sort_values("phase")
        vals = [float(v) for v in g["value"].tolist()]
        name = str(gname)
        if name == "tube_q50":
            out["tube"]["q50"] = vals
        elif name == "tube_usl":
            out["tube"]["usl"] = vals
        elif name == "tube_lsl":
            out["tube"]["lsl"] = vals
        elif name.startswith("ref_"):
            out["ref_curves"].append({"lot_id": str(g["lot_id"].iloc[0]) if "lot_id" in g else "",
                                      "slot_no": str(g["slot_no"].iloc[0]) if "slot_no" in g else "", "values": vals})
        elif name.startswith("comp_"):
            out["comp_curves"].append({"lot_id": str(g["lot_id"].iloc[0]) if "lot_id" in g else "",
                                       "slot_no": str(g["slot_no"].iloc[0]) if "slot_no" in g else "", "values": vals})
    return out


def read_decomp_jitter(jitter_path: Path) -> dict | None:
    """jitter.parquet → {ref:[{lot_id,slot_no,jitter_rms,level}], comp:[...]}."""
    if not jitter_path.exists():
        return None
    try:
        df = pd.read_parquet(jitter_path, engine="pyarrow")
    except Exception:
        return None
    if "group" not in df.columns:
        return None
    out = {"ref": [], "comp": []}
    for _, row in df.iterrows():
        entry = {
            "lot_id": str(row.get("lot_id", "")), "slot_no": str(row.get("slot_no", "")),
            "jitter_rms": float(row["jitter_rms"]) if pd.notna(row.get("jitter_rms")) else None,
            "level": float(row["level"]) if pd.notna(row.get("level")) else None,
        }
        grp = str(row.get("group", ""))
        if grp in out:
            out[grp].append(entry)
    return out


def combo_path(level: str, line: str | None, eqp: str | None, chamber: str | None) -> Path:
    """
    원본 _combo_path 이식. data/{line}/{eqp}/{chamber}/{date} 캐스케이드.
    """
    base = get_data_root()
    if level == "line":
        return _safe_join(base)
    if level == "eqp":
        return _safe_join(base, safe_segment(line, "line"))
    if level == "chamber":
        return _safe_join(base, safe_segment(line, "line"), safe_segment(eqp, "eqp"))
    if level == "date":
        return _safe_join(
            base, safe_segment(line, "line"), safe_segment(eqp, "eqp"),
            safe_segment(chamber, "chamber"),
        )
    raise TttmSpiderPathError("level must be one of: line, eqp, chamber, date")
