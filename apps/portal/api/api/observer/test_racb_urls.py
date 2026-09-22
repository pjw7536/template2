"""Observer RACB 상세 링크 설정 회귀 테스트입니다."""

from __future__ import annotations

from django.test import SimpleTestCase, override_settings

from api.observer import selectors


class ObserverRacbUrlTests(SimpleTestCase):
    """RACB report URL 활성·비활성 응답을 검증합니다."""

    @override_settings(RACB_REPORT_BASE_URL="")
    def test_racb_serializers_omit_url_when_integration_is_disabled(self) -> None:
        """base URL이 비어 있으면 compact/detail 모두 null 링크를 반환합니다."""

        row = {
            "id": 1,
            "c_racb_id": "RACB-1",
            "eqp_cb": "EQP-A",
            "line_id": "LINE-A",
        }

        compact = selectors.serialize_compact_racb_row(row, report_base_url="")
        detail = selectors._serialize_racb_log_detail(row)

        self.assertIsNone(compact["url"])
        self.assertIsNone(detail["url"])
