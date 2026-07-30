# =============================================================================
# 모듈: TTTM Spider 채점 서비스 단위 테스트
# 주요 대상: TRACE 채점, 자가비교 단락, OES 참조 카탈로그와 레이더
# 불변 조건: 채점 수식의 기준값은 도메인 검증값과 일치해야 합니다.
# =============================================================================
from __future__ import annotations

import math
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd
from django.test import SimpleTestCase, override_settings

from .services import catalog, scoring


class TttmSpiderScoringTest(SimpleTestCase):
    """TTTM Spider의 framework-agnostic 채점 수식을 검증합니다."""

    def test_sensor_power_score_matches_reference_values(self) -> None:
        """센서 축별 점수와 지배 축이 기준값을 유지해야 합니다."""

        score, dominant_axis = scoring.sensor_power_score(0, 0, 1.0)
        self.assertAlmostEqual(score, 0.6276458, places=4)
        self.assertEqual(dominant_axis, "jitter")

        score, dominant_axis = scoring.sensor_power_score(200, 0, 0)
        self.assertAlmostEqual(score, 55.0482, places=3)
        self.assertEqual(dominant_axis, "level")

    def test_rms_and_grade_boundaries_match_reference_values(self) -> None:
        """RMS 계산과 정상/주의/심각 경계가 기준값을 유지해야 합니다."""

        self.assertAlmostEqual(scoring.rms([3, 4]), 3.5355339, places=4)
        self.assertEqual(scoring.rms([]), 0.0)
        self.assertEqual(scoring.grade_from_severity(0.0), "정상")
        self.assertEqual(scoring.grade_from_severity(30.0), "주의")
        self.assertEqual(scoring.grade_from_severity(50.0), "심각")

    def test_trace_bundle_matches_reference_values(self) -> None:
        """두 센서의 TRACE 번들이 손계산 기준값과 일치해야 합니다."""

        frame = pd.DataFrame(
            [
                {"category": "ETC", "level": 0.0, "shape": 0.0, "jitter": 1.0},
                {"category": "ETC", "level": 10.0, "shape": 0.0, "jitter": 0.0},
            ],
            index=["s1@S1", "s2@S1"],
        )

        bundle = scoring.build_ttm_score_bundle(frame, "EQ-CH")

        self.assertEqual(bundle["score"], 98.4)
        self.assertEqual(bundle["grade"], "정상")
        self.assertEqual(bundle["radar_leaf"]["ETC"], 96.1)
        self.assertEqual(bundle["worst_category"], "ETC")
        self.assertEqual(len(bundle["sensors"]), 2)
        self.assertAlmostEqual(bundle["sensors"][0]["deviation"], 5.505, places=2)

    def test_self_comparison_forces_perfect_score(self) -> None:
        """동일한 REF와 COMP는 데이터 편차와 무관하게 100점이어야 합니다."""

        frame = pd.DataFrame(
            [{"category": "ETC", "level": 10.0, "shape": 5.0, "jitter": 3.0}],
            index=["s1@S1"],
        )
        bundle = scoring.build_ttm_score_bundle(frame, "EQ-CH", self_compare=True)
        reference = {"line": "L", "eqp": "E", "chamber": "C", "date": "D", "type": "ag"}

        self.assertEqual(bundle["score"], 100.0)
        self.assertEqual(bundle["grade"], "정상")
        self.assertEqual(bundle["sensors"][0]["deviation"], 0.0)
        self.assertTrue(scoring.is_self_comparison(reference, dict(reference)))
        self.assertFalse(
            scoring.is_self_comparison(reference, {**reference, "eqp": "OTHER"})
        )

    def test_oes_reference_catalog_and_radar(self) -> None:
        """read-only reference 경로의 OES 카탈로그가 레이더 분류에 사용되어야 합니다."""

        with TemporaryDirectory() as temporary_directory:
            reference_root = Path(temporary_directory)
            (reference_root / "oes_wavelength_catalog.txt").write_text(
                "\n".join(
                    [
                        "682.6,688.6,F,F",
                        "303.5,311.5,H,H/OH",
                        "748.4,752.4,AR,Ar",
                    ]
                ),
                encoding="utf-8",
            )
            with override_settings(TTTM_SPIDER_REFERENCE_ROOT=str(reference_root)):
                ranges = catalog.load_oes_wavelength_catalog()

        self.assertEqual(len(ranges), 3)
        self.assertEqual(scoring.categorize_wavelength(685.0, ranges), "F")
        self.assertEqual(scoring.categorize_wavelength(304.0, ranges), "H")
        self.assertEqual(scoring.categorize_wavelength(1000.0, ranges), "ETC")

        frame = pd.DataFrame(
            [
                {"step": "S1", "wavelength": 685.0, "delta_spectrum": 3.0},
                {"step": "S1", "wavelength": 304.0, "delta_spectrum": 0.0},
            ]
        )
        radar = scoring.build_oes_step_category_radar(frame, ranges)

        self.assertEqual(radar["step_category_radar"]["S1"]["F"], 50.0)
        self.assertEqual(radar["step_category_radar"]["S1"]["H"], 100.0)
        expected_score = round(100 - math.sqrt(2500 / 4), 1)
        self.assertEqual(radar["step_overall"]["S1"], expected_score)
