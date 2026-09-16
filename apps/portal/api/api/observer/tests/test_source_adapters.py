from . import *  # noqa: F403


class ObserverSourceAdapterTests(TestCase):
    """Observer source adapter 정규화 계약을 검증합니다."""

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

    def test_observer_default_period_uses_seoul_midnight(self) -> None:
        """기본 조회 시작일을 Asia/Seoul 현지 자정으로 계산합니다."""

        with patch(
            "api.observer.services.timezone.timezone.now",
            return_value=datetime(
                2026,
                7,
                31,
                0,
                30,
                tzinfo=ZoneInfo("UTC"),
            ),
        ):
            start_at = observer_period_start(days=1)

        self.assertEqual(start_at, "2026-07-30T00:00:00+09:00")

    def test_observer_eqp_selector_uses_eqp_status_chg_selector(self) -> None:
        with patch(
            f"{OBSERVER_SOURCE_SELECTORS}.eqp_status_chg_selectors.fetch_eqp_timeline_logs",
            return_value=[
                {
                    "id": "EQP-100",
                    "eqpId": "EQP-ALPHA",
                    "logType": "EQP",
                    "eventType": "STATE",
                    "eventTime": "2026-01-01T00:00:00",
                    "operator": "USER",
                    "comment": "EQP comment",
                }
            ],
        ) as fetch_logs:
            logs = _fetch_observer_source_logs(
                eqp_id="EQP-ALPHA",
                log_key="eqp",
                start_at="2026-01-01T00:00:00",
                limit=20,
            )

        self.assertEqual(logs[0]["id"], "EQP-100")
        fetch_logs.assert_called_once_with(
            eqp_id="EQP-ALPHA",
            start_at="2026-01-01T00:00:00",
            end_at=None,
            limit=20,
        )

    def test_observer_tip_selector_uses_mi_tip_update_hist_selector(self) -> None:
        with patch(
            f"{OBSERVER_SOURCE_SELECTORS}.mi_tip_update_hist_selectors.fetch_tip_timeline_logs",
            return_value=[
                {
                    "id": "TIP-EQP-ALPHA-20260101000000000000-CREATE-P-S-PPID-abc",
                    "eqpId": "EQP-ALPHA",
                    "logType": "TIP",
                    "eventType": "CREATE",
                    "eventTime": "2026-01-01T00:00:00",
                    "operator": "USER",
                    "comment": "TIP comment",
                    "lineId": "LINE-A",
                    "process": "P",
                    "step": "S",
                    "ppid": "PPID",
                }
            ],
        ) as fetch_logs:
            logs = _fetch_observer_source_logs(
                eqp_id="EQP-ALPHA",
                log_key="tip",
                start_at="2026-01-01T00:00:00",
                limit=20,
            )

        self.assertEqual(logs[0]["id"], "TIP-EQP-ALPHA-20260101000000000000-CREATE-P-S-PPID-abc")
        fetch_logs.assert_called_once_with(
            eqp_id="EQP-ALPHA",
            start_at="2026-01-01T00:00:00",
            end_at=None,
            limit=20,
        )

    def test_observer_spc_interlock_selector_maps_detail_payload(self) -> None:
        """m_interlock 원천 필드를 SPC Observer 공통/상세 계약으로 변환합니다."""

        source_time = datetime(
            2026,
            7,
            28,
            14,
            55,
            2,
            tzinfo=ZoneInfo("Asia/Seoul"),
        )
        with patch(
            f"{OBSERVER_SOURCE_SELECTORS}.m_interlock_selectors.fetch_interlock_timeline_rows",
            return_value=[
                {
                    "id": 17,
                    "event_time": source_time,
                    "interlock_kind": "SPC",
                    "interlock_no": "SPC-017",
                    "interlock_type": "SPEC",
                    "interlock_comment": "상한 초과",
                    "interlock_desc": "SPC 인터락",
                    "prod_eqp_id": "EQP-ALPHA",
                    "prod_chamber_id": "CH-A",
                    "prod_progs_time": "20260728 145502",
                    "item_value": "10.5",
                    "usl": "10.0",
                }
            ],
        ) as fetch_rows:
            logs = _fetch_observer_source_logs(
                eqp_id="eqp-alpha",
                log_key="spc-interlock",
                start_at="2026-07-28",
                end_at="2026-07-28",
                limit=20,
            )

        self.assertEqual(logs[0]["id"], "SPC_ITL:17")
        self.assertEqual(logs[0]["sourceId"], 17)
        self.assertEqual(logs[0]["logType"], "SPC_ITL")
        self.assertEqual(logs[0]["eventType"], "SPC-017")
        self.assertEqual(logs[0]["eventTime"], "2026-07-28T14:55:02+09:00")
        self.assertEqual(logs[0]["eqpId"], "EQP-ALPHA")
        self.assertEqual(logs[0]["prodChamberId"], "CH-A")
        self.assertEqual(logs[0]["usl"], "10.0")
        fetch_rows.assert_called_once_with(
            eqp_id="EQP-ALPHA",
            interlock_kind="SPC",
            start_at="2026-07-28",
            end_at="2026-07-28",
            limit=20,
        )

    def test_observer_fdc_interlock_selector_uses_short_log_type(self) -> None:
        """FDC interlock 응답에 단축된 logType과 ID 접두어를 적용합니다."""

        with patch(
            f"{OBSERVER_SOURCE_SELECTORS}.m_interlock_selectors.fetch_interlock_timeline_rows",
            return_value=[
                {
                    "id": 18,
                    "event_time": datetime(
                        2026,
                        7,
                        28,
                        15,
                        0,
                        tzinfo=ZoneInfo("Asia/Seoul"),
                    ),
                    "interlock_kind": "FDC",
                    "interlock_no": "FDC-018",
                    "prod_eqp_id": "EQP-ALPHA",
                }
            ],
        ) as fetch_rows:
            logs = _fetch_observer_source_logs(
                eqp_id="eqp-alpha",
                log_key="fdc-interlock",
                start_at="2026-07-28",
            )

        self.assertEqual(logs[0]["id"], "FDC_ITL:18")
        self.assertEqual(logs[0]["logType"], "FDC_ITL")
        fetch_rows.assert_called_once_with(
            eqp_id="EQP-ALPHA",
            interlock_kind="FDC",
            start_at="2026-07-28",
            end_at=None,
            limit=None,
        )

    def test_observer_ctttm_selector_joins_ct_process_comment_summary(self) -> None:
        with patch(
            f"{OBSERVER_SOURCE_SELECTORS}._fetch_all_on_default",
            return_value=[
                {
                    "id": "WO-1",
                    "eqp_id": "EQP-ALPHA",
                    "log_type": "CTTTM",
                    "event_type": "CBM",
                    "event_time": "2026-01-01T00:00:00",
                    "operator": None,
                    "comment": "CTTTM comment",
                    "url": "https://example.local?wono=WO-1&lineId=L1",
                    "core_summary": "Core summary",
                    "summary": "LLM summary",
                }
            ],
        ) as fetch_all:
            logs = _fetch_observer_source_logs(
                eqp_id="EQP-ALPHA",
                log_key="ctttm",
                start_at="2026-01-01T00:00:00",
                limit=20,
            )

        query, params = fetch_all.call_args.args
        self.assertEqual(logs[0]["coreSummary"], "Core summary")
        self.assertEqual(logs[0]["summary"], "LLM summary")
        self.assertIn("from ctttm_workorder_list workorder", query)
        self.assertIn("left join ct_process_comment comment", query)
        self.assertIn("comment.llm_core_summary as core_summary", query)
        self.assertIn("comment.llm_summary as summary", query)
        self.assertIn("comment.workorder_id = workorder.workorder_id", query)
        self.assertEqual(params[1:], ["EQP-ALPHA", "2026-01-01T00:00:00", 20])

    def test_observer_racb_selector_uses_racb_list_selector(self) -> None:
        with patch(
            f"{OBSERVER_SOURCE_SELECTORS}.racb_list_selectors.fetch_racb_timeline_logs",
            return_value=[
                {
                    "id": "LINE-A-EQP-ALPHA-2026-01-01-ALARM",
                    "eventType": "ALARM",
                    "eventTime": "2026-01-01T00:00:00",
                    "operator": "USER",
                    "comment": "RACB title",
                    "lineId": "LINE-A",
                    "eqpId": "EQP-ALPHA",
                    "logType": "RACB",
                }
            ],
        ) as selector:
            logs = _fetch_observer_source_logs(
                eqp_id="EQP-ALPHA",
                log_key="racb",
                start_at="2026-01-01T00:00:00",
                end_at="2026-01-02T23:59:59.999999",
                limit=20,
            )

        self.assertEqual(logs[0]["eqpId"], "EQP-ALPHA")
        self.assertEqual(logs[0]["logType"], "RACB")
        selector.assert_called_once_with(
            eqp_id="EQP-ALPHA",
            start_at="2026-01-01T00:00:00",
            end_at="2026-01-02T23:59:59.999999",
            limit=20,
        )

    def test_observer_esop_selector_uses_lookup_eqp_filter(self) -> None:
        with patch(
            f"{OBSERVER_SOURCE_SELECTORS}._fetch_all_on_default",
            return_value=[],
        ) as fetch_all:
            logs = _fetch_observer_source_logs(
                eqp_id="eqpalpha",
                log_key="esop",
                start_at="2026-01-01T00:00:00",
                limit=20,
            )

        query, params = fetch_all.call_args.args
        self.assertEqual(logs, [])
        self.assertIn("sop.eqp_id_lookup = %s", query)
        self.assertEqual(params, ["2026-01-01T00:00:00", "EQPALPHA", 20])

    def test_observer_esop_selector_maps_log_type_to_esop(self) -> None:
        with patch(
            f"{OBSERVER_SOURCE_SELECTORS}._fetch_all_on_default",
            return_value=[
                {
                    "id": 1,
                    "event_type": "AUTO",
                    "event_time": "2026-01-01T00:00:00",
                    "operator": "KNOX01",
                    "status": "DONE",
                    "comment": "SOP done",
                    "line_id": "LINE-A",
                    "eqp_id": "EQP-ALPHA",
                    "chamber_ids": "1",
                    "lot_id": "LOT-1",
                    "defect_url": json.dumps(
                        [
                            {
                                "label": "ST001",
                                "map_url": "https://example.com/defect-map",
                                "map_file": "MAP001.png",
                                "image_rows": [0, 1, 1, -1, "bad"],
                            }
                        ]
                    ),
                }
            ],
        ):
            logs = _fetch_observer_source_logs(
                eqp_id="EQP-ALPHA",
                log_key="esop",
            )

        self.assertEqual(logs[0]["logType"], "ESOP")
        self.assertEqual(logs[0]["operator"], "KNOX01")
        self.assertEqual(logs[0]["eqpId"], "EQP-ALPHA")
        self.assertEqual(logs[0]["eqpCb"], "EQP-ALPHA-1")
        self.assertEqual(logs[0]["lotId"], "LOT-1")
        image_url_base = (
            "https://example.com/map/api/map-image/v3/defect-map"
            "?file=MAP001.png&selected_row={row}&profileid=DEFAULT&themeid=DEFAULT"
            "&width=500&height=500&site=GH&targetDB=APP&useCache=true"
            "&includeCoordinate=false"
        )
        self.assertEqual(
            logs[0]["defectMaps"],
            [
                {
                    "label": "ST001",
                    "url": "https://example.com/defect-map",
                    "imageUrls": [
                        image_url_base.format(row=0),
                        image_url_base.format(row=1),
                    ],
                }
            ],
        )
