# =============================================================================
# Step 1 파리티 셀프테스트 (Django 무관). 실행:
#   cd apps/api && python3 -m api.tttm_spider._selftest_scoring
# 원본 tttm_dashboard_api.py 의 채점 수치를 손계산과 대조한다.
# =============================================================================
from __future__ import annotations

import math

import pandas as pd

from . import catalog, scoring

PASS = 0
FAIL = 0


def check(name, got, want, tol=1e-4):
    global PASS, FAIL
    ok = (abs(got - want) <= tol) if isinstance(want, (int, float)) and isinstance(got, (int, float)) else (got == want)
    print(f"  [{'OK ' if ok else 'XX '}] {name}: got={got!r} want={want!r}")
    if ok:
        PASS += 1
    else:
        FAIL += 1


print("== A. sensor_power_score ==")
s, dom = scoring.sensor_power_score(0, 0, 1.0)
check("self-jitter score", s, 0.6276458)
check("self-jitter dom", dom, "jitter")
s, dom = scoring.sensor_power_score(200, 0, 0)   # hardcap 100
check("hardcap level score", s, 55.0482, tol=1e-3)
check("hardcap level dom", dom, "level")

print("== B. rms / grade ==")
check("rms([3,4])", scoring.rms([3, 4]), 3.5355339)
check("rms([])", scoring.rms([]), 0.0)
check("grade sev0", scoring.grade_from_severity(0.0), "정상")
check("grade sev35", scoring.grade_from_severity(35.0), "주의")
check("grade sev30(health70)", scoring.grade_from_severity(30.0), "주의")
check("grade sev50(health50)", scoring.grade_from_severity(50.0), "심각")

print("== C. build_ttm_score_bundle (2 sensors, ETC) ==")
pdf = pd.DataFrame(
    [{"category": "ETC", "level": 0.0, "shape": 0.0, "jitter": 1.0},
     {"category": "ETC", "level": 10.0, "shape": 0.0, "jitter": 0.0}],
    index=["s1@S1", "s2@S1"],
)
# catalog 이 다축(mock)이라 ETC leaf(3.9)만 6개 top 중 하나 → 전체 RMS=√(3.9²/6)=1.6 → 98.4
b = scoring.build_ttm_score_bundle(pdf, "EQ-CH")
check("chamber health", b["score"], 98.4)
check("chamber grade", b["grade"], "정상")
check("radar_leaf ETC", b["radar_leaf"]["ETC"], 96.1)
check("radar_top ETC", b["radar"]["ETC"], 96.1)
check("worst_category", b["worst_category"], "ETC")
check("n sensors", len(b["sensors"]), 2)
check("sensors sorted (max dev first)", b["sensors"][0]["deviation"], 5.505, tol=1e-2)

print("== D. self-compare guard → all 100 ==")
b2 = scoring.build_ttm_score_bundle(pdf, "EQ-CH", self_compare=True)
check("self health", b2["score"], 100.0)
check("self grade", b2["grade"], "정상")
check("self radar_top ETC", b2["radar"]["ETC"], 100.0)
check("self sensor deviation", b2["sensors"][0]["deviation"], 0.0)
check("is_self_comparison same", scoring.is_self_comparison(
    {"line": "L", "eqp": "E", "chamber": "C", "date": "D", "type": "ag"},
    {"line": "L", "eqp": "E", "chamber": "C", "date": "D", "type": "ag"}), True)
check("is_self_comparison diff", scoring.is_self_comparison(
    {"line": "L", "eqp": "E", "chamber": "C", "date": "D", "type": "ag"},
    {"line": "L", "eqp": "E2", "chamber": "C", "date": "D", "type": "ag"}), False)

print("== E. OES catalog + categorize + wl_severity ==")
ranges = catalog.load_oes_wavelength_catalog()
check("n ranges", len(ranges), 31)
order, labels = scoring.oes_category_order_and_labels(ranges)
check("category_order len (14 species + ETC)", len(order), 15)
check("H label", labels.get("H"), "H/OH")
check("ETC last", order[-1], "ETC")
check("categorize 685→F", scoring.categorize_wavelength(685.0, ranges), "F")
check("categorize 304→H", scoring.categorize_wavelength(304.0, ranges), "H")
check("categorize 750→AR", scoring.categorize_wavelength(750.0, ranges), "AR")
check("categorize 1000→ETC", scoring.categorize_wavelength(1000.0, ranges), "ETC")
check("wl_severity(3.0)", scoring.oes_wl_severity(3.0), 50.0)
check("wl_severity(6.0) cap", scoring.oes_wl_severity(6.0), 100.0)

print("== F. OES step-category radar (OOB) ==")
odf = pd.DataFrame([
    {"step": "S1", "wavelength": 685.0, "delta_spectrum": 3.0},   # F, sev 50
    {"step": "S1", "wavelength": 304.0, "delta_spectrum": 0.0},   # H, sev 0
])
rad = scoring.build_oes_step_category_radar(odf, ranges)
check("oes radar F", rad["step_category_radar"]["S1"]["F"], 50.0)
check("oes radar H", rad["step_category_radar"]["S1"]["H"], 100.0)
# step severity = rms over ALL 15 categories (empty→0): only F=50 → sqrt(50²/15)
check("oes step_overall S1", rad["step_overall"]["S1"], round(100 - math.sqrt(2500 / 15), 1))

print(f"\n==== RESULT: {PASS} passed, {FAIL} failed ====")
if FAIL:
    raise SystemExit(1)
