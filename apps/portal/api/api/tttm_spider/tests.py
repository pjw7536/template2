# =============================================================================
# 모듈: TTTM Spider 서비스/뷰 테스트
# 주요 대상: combo/options, dashboard/data(trace), 자가비교=100, 결과 없음 404
# 주요 가정: 결과 데이터는 임시 Parquet 파일로 생성한다(파이프라인 미실행, DB 미사용).
# =============================================================================
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import pandas as pd
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from .views import (
    TttmSpiderComboOptionsView,
    TttmSpiderDashboardDataView,
)

_USER = SimpleNamespace(is_authenticated=True)


def _load(response) -> dict:
    if hasattr(response, "render") and not getattr(response, "is_rendered", True):
        response.render()
    return json.loads(response.content.decode("utf-8"))


def _write_trace_parquet(result_root: Path, ref: dict, comp: dict) -> None:
    path = (
        result_root / "score_data"
        / f"ref_line={ref['line']}" / f"ref_eqp={ref['eqp']}" / f"ref_ch={ref['chamber']}" / f"ref_dt={ref['date']}"
        / f"comp_line={comp['line']}" / f"comp_eqp={comp['eqp']}" / f"comp_ch={comp['chamber']}" / f"comp_dt={comp['date']}"
        / f"type={comp['type']}" / "data_type=trace"
    )
    path.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame([
        {"item_name": "S_A", "step": "S1", "delta_level": 0.0, "delta_shape": 0.0,
         "delta_jitter": 1.0, "alarm_pct": 0.0, "trace_recipe_id": "R1"},
        {"item_name": "S_B", "step": "S1", "delta_level": 10.0, "delta_shape": 0.0,
         "delta_jitter": 0.0, "alarm_pct": 0.0, "trace_recipe_id": "R1"},
    ])
    df.to_parquet(path / "scores.parquet", engine="pyarrow", index=False)


class TttmSpiderComboTest(SimpleTestCase):
    def test_combo_options_line(self):
        with TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "data"
            (data_root / "L1" / "EQ1").mkdir(parents=True)
            (data_root / "L2").mkdir(parents=True)
            with override_settings(TTTM_SPIDER_DATA_ROOT=str(data_root)):
                req = APIRequestFactory().get("/combo/options", {"level": "line"})
                force_authenticate(req, user=_USER)
                resp = TttmSpiderComboOptionsView.as_view()(req)
                self.assertEqual(resp.status_code, 200)
                self.assertEqual(_load(resp)["items"], ["L1", "L2"])


class TttmSpiderDashboardTest(SimpleTestCase):
    REF = {"line": "RL", "eqp": "RE", "chamber": "RC", "date": "2026-07-01"}
    COMP = {"line": "CL", "eqp": "CE", "chamber": "CC", "date": "2026-07-02", "type": "ag"}

    def _post(self, result_root, ref, comp):
        payload = {"comp": comp, "ref": ref, "dataType": "trace", "stage": "P3"}
        req = APIRequestFactory().post("/dashboard/data", payload, format="json")
        force_authenticate(req, user=_USER)
        with override_settings(TTTM_SPIDER_RESULT_ROOT=str(result_root)):
            return TttmSpiderDashboardDataView.as_view()(req)

    def test_trace_bundle_matches_handcomputed(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_trace_parquet(root, self.REF, self.COMP)
            resp = self._post(root, self.REF, self.COMP)
            self.assertEqual(resp.status_code, 200)
            chamber = _load(resp)["bundle"]["chambers"][0]
            # 두 센서는 맵에 없어 ETC. 6개 top 중 ETC leaf만 3.9 → 전체 RMS=√(3.9²/6)=1.6 → 98.4
            self.assertEqual(chamber["score"], 98.4)
            self.assertEqual(chamber["grade"], "정상")
            self.assertEqual(chamber["radar_leaf"]["ETC"], 96.1)
            self.assertEqual(len(chamber["sensors"]), 2)
            self.assertGreater(chamber["sensors"][0]["deviation"], chamber["sensors"][1]["deviation"])
            self.assertIn("by_stage", chamber)
            self.assertIn("P2", chamber["by_stage"])

    def test_self_comparison_forces_100(self):
        # REF == COMP (같은 챔버/날짜) → 전부 100점
        ref = {"line": "X", "eqp": "Y", "chamber": "Z", "date": "2026-07-01"}
        comp = {**ref, "type": "ag"}
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_trace_parquet(root, ref, comp)
            resp = self._post(root, ref, comp)
            self.assertEqual(resp.status_code, 200)
            chamber = _load(resp)["bundle"]["chambers"][0]
            self.assertEqual(chamber["score"], 100.0)
            self.assertEqual(chamber["grade"], "정상")
            self.assertTrue(chamber.get("self_compare"))
            self.assertTrue(all(v == 100.0 for v in chamber["radar"].values()))

    def test_missing_parquet_returns_404(self):
        with TemporaryDirectory() as tmp:
            resp = self._post(Path(tmp), self.REF, self.COMP)
            self.assertEqual(resp.status_code, 404)
