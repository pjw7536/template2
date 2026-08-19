from . import *  # noqa: F403


class ObserverLogRegistryTests(TestCase):
    """Observer source registry와 batch 조회 계약을 검증합니다."""

    def setUp(self) -> None:
        """보호된 Observer endpoint를 호출할 인증 사용자를 준비합니다."""

        _allow_test_scope_access(self)
        User = get_user_model()
        self.user = User.objects.create_user(
            sabun="S-OBSERVER",
            password="test-password",
            knox_id="knox-observer",
        )
        self.client.force_login(self.user)

    def test_observer_eqp_page_builds_compact_payload_and_cursor(self) -> None:
        """EQP page는 comment preview와 source PK cursor를 생성합니다."""

        event_time = datetime(2026, 7, 6, 10, 30, tzinfo=ZoneInfo("UTC"))
        with patch(
            f"{OBSERVER_SELECTORS}.eqp_status_chg_selectors.fetch_eqp_timeline_page",
            return_value=(
                [
                    {
                        "id": 11,
                        "eqp_event_key": 101,
                        "eqp_cb": "EQP-ALPHA",
                        "eqp_status_type": "RUN",
                        "chg_time": event_time,
                        "operator_emp_id": "USER",
                        "chg_comment": "가" * 250,
                    }
                ],
                True,
            ),
        ):
            page = selectors.get_log_page(
                eqp_id="EQP-ALPHA",
                log_key="eqp",
                start_at="2026-07-01T00:00:00",
                end_at="2026-07-07T23:59:59.999999",
                page_size=1,
                range_key=(
                    "2026-07-01T00:00:00:"
                    "2026-07-07T23:59:59.999999"
                ),
            )

        self.assertEqual(len(page["items"][0]["comment"]), 200)
        self.assertTrue(page["items"][0]["commentTruncated"])
        self.assertEqual(page["items"][0]["detailId"], 11)
        self.assertEqual(
            page["items"][0]["eventTime"],
            "2026-07-06T19:30:00+09:00",
        )
        self.assertTrue(page["page"]["hasMore"])
        cursor = observer_serializers.decode_observer_cursor(
            page["page"]["nextCursor"]
        )
        self.assertEqual(cursor["tieBreaker"], 11)
        self.assertEqual(cursor["logType"], "eqp")

    def test_observer_compact_page_registry_wires_all_sources(self) -> None:
        """일곱 source registry가 조회 함수와 cursor 시간 기준을 올바르게 연결합니다."""

        event_time = datetime(2026, 7, 6, 10, 30, tzinfo=ZoneInfo("UTC"))
        cases = (
            (
                "eqp",
                "eqp_status_chg_selectors.fetch_eqp_timeline_page",
                "chg_time",
                "EQP",
                None,
            ),
            (
                "tip",
                "mi_tip_update_hist_selectors.fetch_tip_timeline_page",
                "gpm_update_date",
                "TIP",
                None,
            ),
            (
                "spc-interlock",
                "m_interlock_selectors.fetch_interlock_timeline_page",
                "event_time",
                "SPC_ITL",
                "SPC",
            ),
            (
                "fdc-interlock",
                "m_interlock_selectors.fetch_interlock_timeline_page",
                "event_time",
                "FDC_ITL",
                "FDC",
            ),
            (
                "ctttm",
                "ctttm_workorder_selectors.fetch_ctttm_timeline_page",
                "inprg_date",
                "CTTTM",
                None,
            ),
            (
                "racb",
                "racb_list_selectors.fetch_racb_timeline_page",
                "update_date",
                "RACB",
                None,
            ),
            (
                "esop",
                "drone_selectors.fetch_drone_sop_timeline_page",
                "created_at",
                "ESOP",
                None,
            ),
        )

        for index, (log_key, fetch_path, time_field, log_type, interlock_kind) in enumerate(
            cases,
            start=1,
        ):
            with self.subTest(log_key=log_key), patch(
                f"{OBSERVER_SELECTORS}.{fetch_path}",
                return_value=([{"id": index, time_field: event_time}], True),
            ) as fetch_page:
                page = selectors.get_log_page(
                    eqp_id="eqp-alpha",
                    log_key=log_key,
                    start_at="2026-07-01T00:00:00",
                    end_at="2026-07-07T23:59:59.999999",
                    page_size=10,
                    range_key="range",
                )

            expected_options = {
                "eqp_id": "EQP-ALPHA",
                "start_at": "2026-07-01T00:00:00",
                "end_at": "2026-07-07T23:59:59.999999",
                "page_size": 10,
                "cursor_time": None,
                "cursor_id": None,
            }
            if interlock_kind is not None:
                expected_options["interlock_kind"] = interlock_kind
            fetch_page.assert_called_once_with(**expected_options)
            self.assertEqual(page["items"][0]["logType"], log_type)
            cursor = observer_serializers.decode_observer_cursor(
                page["page"]["nextCursor"]
            )
            self.assertEqual(cursor["logType"], log_key)
            self.assertEqual(cursor["tieBreaker"], index)

    def test_observer_batch_page_preserves_successful_types(self) -> None:
        """한 source 실패가 성공한 다른 source 결과를 제거하지 않습니다."""

        successful_page = {
            "items": [{"id": "EQP-1"}],
            "page": {
                "nextCursor": None,
                "hasMore": False,
                "pageSize": 10,
            },
            "meta": {},
        }
        with patch(
            f"{OBSERVER_LOG_SELECTORS}.get_log_page",
            side_effect=[successful_page, RuntimeError("source failed")],
        ):
            payload = selectors.get_log_pages(
                eqp_id="EQP-ALPHA",
                log_types=["eqp", "tip"],
                start_at="2026-07-01T00:00:00",
                end_at="2026-07-07T23:59:59.999999",
                page_size=10,
                range_key="range",
            )

        self.assertEqual(payload["data"]["eqp"]["items"], [{"id": "EQP-1"}])
        self.assertEqual(
            payload["data"]["tip"]["error"]["code"],
            "SOURCE_QUERY_FAILED",
        )
        self.assertTrue(payload["meta"]["partial"])
