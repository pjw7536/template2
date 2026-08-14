"""Assistant Runtime의 Observer 분석 기간 계약을 검증합니다."""

from datetime import date, timedelta
from unittest.mock import patch

from django.test import SimpleTestCase

from api.assistant import services as assistant_services
from api.common.services import ExternalCallCancellation
from api.observer.services import MAX_OBSERVER_QUERY_DAYS


class AssistantObserverAnalysisRangeTests(SimpleTestCase):
    """Observer 화면과 Assistant가 동일한 최대 조회 기간을 사용하는지 확인합니다."""

    def setUp(self) -> None:
        """외부 호출 없이 Runtime 기간 경계를 검증할 공통 입력을 준비합니다."""

        self.runtime = assistant_services.AssistantRuntime()
        self.profile = assistant_services.get_assistant_profile(
            profile_key="observer-analysis"
        )

    def execute(self, *, start_date: date, end_date: date) -> None:
        """지정한 날짜 범위로 Observer Runtime을 실행합니다."""

        self.runtime.execute(
            profile=self.profile,
            prompt="현재 범위를 분석해줘",
            history=[],
            conversation_summary="",
            tool_inputs={
                "observer.analysis": {
                    "eqpId": "EQP-1",
                    "from": start_date.isoformat(),
                    "to": end_date.isoformat(),
                    "logTypes": ["eqp"],
                    "tipGroups": ["__ALL__"],
                }
            },
            user_header_id="knox-98000",
            context_key="observer:test",
            cancellation=ExternalCallCancellation(),
        )

    def test_accepts_ranges_up_to_public_observer_limit(self) -> None:
        """기존 31일을 넘는 범위와 공개 최대 범위를 모두 허용합니다."""

        observer_payload = {
            "analysis": {
                "headline": "기간 분석",
                "summary": "선택한 기간을 분석했습니다.",
                "findings": [],
                "limitations": [],
            },
            "meta": {},
            "scope": {},
        }
        start_date = date(2026, 5, 1)
        end_dates = (
            start_date + timedelta(days=31),
            start_date + timedelta(days=MAX_OBSERVER_QUERY_DAYS - 1),
        )

        with patch(
            "api.assistant.services.runtime.analyze_observer_logs_stream",
            return_value=observer_payload,
        ) as analyze:
            for end_date in end_dates:
                with self.subTest(end_date=end_date):
                    self.execute(start_date=start_date, end_date=end_date)

        self.assertEqual(analyze.call_count, len(end_dates))

    def test_rejects_range_over_public_observer_limit(self) -> None:
        """공개 최대 범위를 하루 초과한 요청은 조회 전에 거부합니다."""

        start_date = date(2026, 5, 1)
        end_date = start_date + timedelta(days=MAX_OBSERVER_QUERY_DAYS)
        with patch(
            "api.assistant.services.runtime.analyze_observer_logs_stream"
        ) as analyze, self.assertRaisesMessage(
            ValueError,
            f"Observer 분석 조회 기간은 최대 {MAX_OBSERVER_QUERY_DAYS}일입니다.",
        ):
            self.execute(start_date=start_date, end_date=end_date)

        analyze.assert_not_called()
