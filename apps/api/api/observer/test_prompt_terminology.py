"""Observer 분석 prompt의 영문 업무 용어 계약을 검증합니다."""

from django.test import SimpleTestCase

from api.observer.services.analysis import ANALYSIS_SYSTEM_PROMPT


class ObserverTerminologyPromptTests(SimpleTestCase):
    """Observer 분석 prompt가 공통 canonical guide를 포함하는지 확인합니다."""

    def test_analysis_prompt_includes_terminology_guide(self) -> None:
        """canonical 영문 용어와 금지 음역 표기를 함께 전달합니다."""

        for expected in (
            "[영문 업무 용어 보존 규칙]",
            "- interlock",
            "- wafer lot",
            "인터록, 인터락",
            "웨이퍼 로트",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, ANALYSIS_SYSTEM_PROMPT)
