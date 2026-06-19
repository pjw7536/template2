"""
L3 Spider 가벼운 mock 데이터 생성 스크립트.
경로: data/l3_spider/daily_anomaly/2026-06-17/{line}/{process}/{eds_step}/{step_seq}#{ppid}#{index}
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent / "data" / "l3_spider" / "daily_anomaly"
DATE = "2026-06-17"

LINES = ["L1", "L2"]
PROCESSES = ["P001", "P002"]
EDS_STEPS = ["EDS_A", "EDS_B"]

PPIDS = ["PPID_AA", "PPID_BB", "PPID_CC"]
BINS = ["BIN_01", "BIN_02", "BIN_03"]
EQP_IDS = ["EQP_01", "EQP_02"]
STATUSES = ["Normal (Ref)", "Normal (Ref)", "Normal (Ref)", "Warning", "High Risk Chamber"]

ROWS_PER_FILE = 10

rng = np.random.default_rng(42)


def make_rows(line: str, process: str, eds_step: str) -> list[dict]:
    base_time = pd.Timestamp(f"{DATE} 08:00:00")
    rows = []
    for i in range(ROWS_PER_FILE):
        tkin = base_time + pd.Timedelta(hours=i)
        tkout = tkin + pd.Timedelta(minutes=30)
        eqp = rng.choice(EQP_IDS)
        step = f"S{rng.integers(1, 4)}"
        ppid = rng.choice(PPIDS)
        bin_name = rng.choice(BINS)
        eqc = f"{eqp}_CH{rng.integers(1, 4)}"
        bin_value = float(rng.uniform(0.5, 3.0))
        lsl, usl = 0.0, 4.0
        q1 = float(rng.uniform(0.8, 1.2))
        q3 = float(rng.uniform(2.0, 2.5))
        iqr = q3 - q1
        status = rng.choice(STATUSES)
        rows.append({
            "tkin_time": tkin,
            "tkout_time": tkout,
            "owning": line,
            "step_seq": step,
            "ppid": ppid,
            "root_lot_id": f"ROOT_{line}",
            "lot_id": f"LOT_{line}_{i:03d}",
            "wafer_id": f"W{i+1:02d}",
            "eqp_id": eqp,
            "chamber_id": eqc,
            "eqc": eqc,
            "bin_name": bin_name,
            "bin_value": bin_value,
            "prop_over_50": float(rng.uniform(0.0, 1.0)),
            "q1": q1,
            "q3": q3,
            "iqr": iqr,
            "lsl": lsl,
            "usl": usl,
            "seq_idx": i,
            "risk_score": float(rng.uniform(0.0, 1.0)),
            "display_status": status,
            "comment": "이상감지" if status != "Normal (Ref)" else None,
        })
    return rows


def main() -> None:
    count = 0
    for line in LINES:
        for process in PROCESSES:
            for eds_step in EDS_STEPS:
                dir_path = ROOT / DATE / line / process / eds_step
                dir_path.mkdir(parents=True, exist_ok=True)
                df = pd.DataFrame(make_rows(line, process, eds_step))
                for index, ((step_seq, ppid), group) in enumerate(df.groupby(["step_seq", "ppid"], sort=True)):
                    out_path = dir_path / f"{step_seq}#{ppid}#{index}"
                    group.to_parquet(out_path, engine="pyarrow", index=False)
                    count += 1
                    print(f"  생성: {out_path.relative_to(ROOT)}")
    print(f"\n완료: {count}개 파일, 원본 조합당 최대 {ROWS_PER_FILE}행")


if __name__ == "__main__":
    main()
