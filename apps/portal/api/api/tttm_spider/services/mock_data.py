"""TTTM Spider 개발용 mock 데이터 생성 서비스 v3입니다.

실제스러운 이름, 다중 recipe, 다수 웨이퍼 데이터를 생성합니다.
eqp=ELXX30x, chamber=PM1..PM6, recipe=RCP_A(process)/RCP_ISD(isd), 웨이퍼 다수.
lotwf 인덱스(전 챔버) + score_data(전 챔버·양 recipe) + raw/decomp(PM1 풀).

실행: ``python -m api.tttm_spider.services.mock_data``
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(os.environ.get("TTTM_SPIDER_ROOT", "/data/tttm_spider"))
DATA = ROOT / "data"
RESULT = ROOT / "result" / "score_data"
DECOMP = ROOT / "result" / "decomp_data"
LOTWF_INDEX = ROOT / "lotwf_index.parquet"

LINE = "L1"
EQPS_COMP = ["ELXX301", "ELXX302"]
EQP_GOLDEN = "ELXX303"
CHAMBERS = ["PM1", "PM2", "PM3", "PM4", "PM5", "PM6"]
FULL_CHAMBERS = ["PM1"]                     # raw + decomp 풀데이터
RECIPES = ["RCP_A", "RCP_ISD"]              # process / isd
RECIPE_FACTOR = {"RCP_A": 1.0, "RCP_ISD": 0.45}   # ISD는 이상 약하게
CTYPE = "process"
LOTS = ["LOTA", "LOTB"]
WAFERS = list(range(1, 14))                 # 13매 → 다수 웨이퍼 헷지
STEPS = ["STEP1", "STEP2", "STEP3"]
STEP_BUMP = {"STEP1": 1.0, "STEP2": 0.6, "STEP3": 1.3}
PARAMS = [
    ("RF_FWD_PWR", 500.0, 1.1), ("RF_REF_PWR", 5.0, 1.4), ("CHAMBER_PRESS", 30.0, 2.0),
    ("GAS_FLOW_AR", 85.0, 6.0), ("GAS_FLOW_O2", 40.0, 3.0), ("ESC_VOLT", 100.0, 12.0),
    ("HELIUM_LEAK", 0.5, 1.0),
]
CYCLES = {
    "ELXX301": {"cur": ("2026-07-22", "13"), "prev": ("2026-07-15", "10")},
    "ELXX302": {"cur": ("2026-07-21", "09"), "prev": ("2026-07-14", "08")},
    "ELXX303": {"cur": ("2026-07-23", "15")},
}
rng = np.random.default_rng(17)


# ── lotwf 인덱스 (전 eqp·챔버·주기·recipe·웨이퍼) ────────────────────────────
rows = []
for eqp, cyc in CYCLES.items():
    for chamber in CHAMBERS:
        for _cname, (date, hh) in cyc.items():
            for ri, recipe in enumerate(RECIPES):
                for li, lot in enumerate(LOTS):
                    for wf in WAFERS:
                        mm = (ri * len(LOTS) * len(WAFERS) + li * len(WAFERS) + (wf - 1)) % 60
                        rows.append({
                            "line": LINE, "eqp": eqp, "chamber": chamber, "date": date,
                            "lot_id": lot, "slot_no": f"{wf:02d}", "recipe_id": recipe,
                            "tkin_time": f"{date} {hh}:{mm:02d}:00", "is_golden": eqp == EQP_GOLDEN,
                        })
LOTWF_INDEX.parent.mkdir(parents=True, exist_ok=True)
pd.DataFrame(rows).to_parquet(LOTWF_INDEX, engine="pyarrow", index=False)


# ── RAW trace (PM1 노드) ─────────────────────────────────────────────────────
RAW_LOTS = [("LOTA", "03"), ("LOTA", "04"), ("LOTB", "03")]


def _waveform(level, noise_amp, n=120):
    t = np.linspace(0, 6, n)
    v = np.where(t < 0.8, level * np.clip(t / 0.8, 0, 1), level + 4.0 * np.sin(t * 1.3))
    return t, v + rng.normal(0, noise_amp, n)


def write_raw(eqp, chamber, date, current):
    for name, lvl, jit in PARAMS:
        base = DATA / LINE / eqp / chamber / date / "trace" / f"type={CTYPE}" / "ppid=-" / "recipe_id=RCP_A" / f"trace_param_name={name}"
        base.mkdir(parents=True, exist_ok=True)
        rows_ = []
        for lot, wf in RAW_LOTS:
            for step in STEPS:
                noise = 0.01 * lvl * (jit if current else 1.0)
                shift = (lvl * 0.02 * jit) if current else 0.0
                t, v = _waveform(lvl + shift, max(noise, 0.05))
                for ti, vi in zip(t, v):
                    rows_.append({"ch_step": step, "Time": round(float(ti), 4), "value": round(float(vi), 4),
                                  "lot_id": lot, "slot_no": wf, "recipe_id": "RCP_A"})
        pd.DataFrame(rows_).to_parquet(base / f"{lot}_{wf}.parquet", engine="pyarrow", index=False)


# ── score_data + decomp ──────────────────────────────────────────────────────
def sdir(ref, comp, dt):
    return (RESULT / f"ref_line={ref['line']}" / f"ref_eqp={ref['eqp']}" / f"ref_ch={ref['chamber']}" / f"ref_dt={ref['date']}"
            / f"comp_line={comp['line']}" / f"comp_eqp={comp['eqp']}" / f"comp_ch={comp['chamber']}" / f"comp_dt={comp['date']}"
            / f"type={CTYPE}" / f"data_type={dt}")


def write_trace(ref, comp):
    rows_ = []
    for recipe in RECIPES:
        rf = RECIPE_FACTOR[recipe]
        for step in STEPS:
            bump = STEP_BUMP[step]
            for name, lvl, jit in PARAMS:
                dl = jit * 8.0 * bump * rf
                rows_.append({"item_name": name, "step": step, "delta_level": round(dl, 4), "delta_shape": 0.0,
                              "delta_jitter": round(1.0 + (jit - 1.0) * rf, 4), "alarm_pct": round(min(100.0, dl * 0.4), 1),
                              "trace_recipe_id": recipe, "trace_ppid": "-"})
    d = sdir(ref, comp, "trace"); d.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows_).to_parquet(d / "scores.parquet", engine="pyarrow", index=False)


def write_oes(ref, comp):
    species_wl = {"F": 685.0, "CL": 725.0, "BR": 826.0, "O": 777.0, "N": 337.0, "H": 305.0,
                  "CARBON": 251.0, "SI": 288.0, "AL": 396.0, "CU": 324.0, "W": 407.0, "Y": 371.0, "TI": 454.0, "AR": 750.0}
    sev = {"F": 3.2, "O": 2.4, "CL": 1.6, "SI": 1.0, "AR": 0.3}
    rows_ = []
    for step in STEPS:
        bump = {"STEP1": 1.0, "STEP2": 0.5, "STEP3": 1.2}[step]
        n_flag = sum(1 for k in species_wl if sev.get(k, 0.1) * bump >= 1.0)
        for key, wl in species_wl.items():
            dv = round(sev.get(key, 0.1) * bump, 4)
            for off in (-0.4, 0.0, 0.4):
                rows_.append({"step": step, "wavelength": round(wl + off, 4), "delta_spectrum": dv,
                              "flagged_wl": float(n_flag), "direction": "up", "oes_recipe_id": "RCP_A", "oes_ppid": "P1"})
    d = sdir(ref, comp, "oes"); d.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows_).to_parquet(d / "scores.parquet", engine="pyarrow", index=False)


def ddir(ref, comp, param, step):
    return (DECOMP / f"ref_line={ref['line']}" / f"ref_eqp={ref['eqp']}" / f"ref_ch={ref['chamber']}" / f"ref_dt={ref['date']}"
            / f"comp_line={comp['line']}" / f"comp_eqp={comp['eqp']}" / f"comp_ch={comp['chamber']}" / f"comp_dt={comp['date']}"
            / f"type={CTYPE}" / f"param={param}" / f"ch_step={step}")


def write_decomp(ref, comp):
    ph = list(range(100))
    for name, lvl, jit in PARAMS:
        for step in STEPS:
            q50 = np.array([np.sin(p / 99 * np.pi) for p in ph]); mad = np.full(100, 0.05)
            srows = [pd.DataFrame({"ref_dt": ref["date"], "comp_dt": comp["date"], "phase": ph,
                                   "value": q50 + rng.normal(0, 0.02, 100), "group": f"ref_{lot}_{wf}", "lot_id": lot, "slot_no": wf})
                     for lot, wf in RAW_LOTS[:2]]
            srows.append(pd.DataFrame({"ref_dt": ref["date"], "comp_dt": comp["date"], "phase": ph,
                                       "value": q50 + (0.12 * jit / 6.0) * np.sin(np.array(ph) / 99 * np.pi * 3) + rng.normal(0, 0.02, 100),
                                       "group": "comp_LOTB_03", "lot_id": "LOTB", "slot_no": "03"}))
            for g, v in [("tube_q50", q50), ("tube_usl", q50 + 3 * mad), ("tube_lsl", q50 - 3 * mad)]:
                srows.append(pd.DataFrame({"ref_dt": ref["date"], "comp_dt": comp["date"], "phase": ph, "value": v, "group": g, "lot_id": "", "slot_no": "-1"}))
            d = ddir(ref, comp, name, step); d.mkdir(parents=True, exist_ok=True)
            pd.concat(srows, ignore_index=True).to_parquet(d / "shape.parquet", engine="pyarrow", index=False)
            jrows = []
            for grp, fac in [("ref", 1.0), ("comp", jit)]:
                for lot, wf in RAW_LOTS:
                    jrows.append({"ref_dt": ref["date"], "comp_dt": comp["date"], "root_lot_id": lot, "lot_id": lot, "slot_no": wf,
                                  "jitter_rms": round(float(0.01 * lvl * fac + rng.normal(0, 0.002 * lvl)), 6),
                                  "level": round(float(lvl + (lvl * 0.02 * jit if grp == "comp" else 0) + rng.normal(0, 0.01 * lvl)), 4), "group": grp})
            pd.DataFrame(jrows).to_parquet(d / "jitter.parquet", engine="pyarrow", index=False)


for eqp in EQPS_COMP:
    cur, prev = CYCLES[eqp]["cur"][0], CYCLES[eqp]["prev"][0]
    gold = CYCLES[EQP_GOLDEN]["cur"][0]
    for chamber in CHAMBERS:
        comp = {"line": LINE, "eqp": eqp, "chamber": chamber, "date": cur}
        for ref in ({"line": LINE, "eqp": eqp, "chamber": chamber, "date": prev},
                    {"line": LINE, "eqp": EQP_GOLDEN, "chamber": chamber, "date": gold}):
            write_trace(ref, comp)
            write_oes(ref, comp)
            if chamber in FULL_CHAMBERS:
                write_decomp(ref, comp)

for chamber in FULL_CHAMBERS:
    for eqp in EQPS_COMP:
        write_raw(eqp, chamber, CYCLES[eqp]["cur"][0], True)
        write_raw(eqp, chamber, CYCLES[eqp]["prev"][0], False)
    write_raw(EQP_GOLDEN, chamber, CYCLES[EQP_GOLDEN]["cur"][0], False)

print(f"lotwf_index rows={len(rows)} (eqps={list(CYCLES)}, chambers={CHAMBERS}, recipes={RECIPES}, wafers={len(WAFERS)})")
print(f"score_data: all chambers × 2 refs · raw/decomp: {FULL_CHAMBERS}")
