from . import *  # noqa: F403


class ObserverLogPageEndpointTests(TestCase):
    """Observer canonical 로그 page/detail 계약을 검증합니다."""

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

    def test_observer_logs_page_returns_bounded_type_payload(self) -> None:
        """최초 page endpoint가 정규화된 bounded query를 selector에 전달합니다."""

        payload = {
            "data": {
                "eqp": {
                    "items": [],
                    "nextCursor": None,
                    "hasMore": False,
                    "error": None,
                }
            },
            "meta": {
                "from": "2026-07-01T00:00:00+09:00",
                "to": "2026-07-07T23:59:59.999999+09:00",
                "pageSize": 250,
                "partial": False,
                "allFailed": False,
            },
        }
        with patch(
            f"{OBSERVER_VIEW_SELECTORS}.get_log_pages",
            return_value=payload,
        ) as selector:
            response = self.client.get(
                reverse("observer-logs-page"),
                {
                    "eqpId": "eqp-alpha",
                    "from": "2026-07-01",
                    "to": "2026-07-07",
                    "types": "eqp",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), payload)
        selector.assert_called_once_with(
            eqp_id="EQP-ALPHA",
            log_types=["eqp"],
            start_at="2026-07-01T00:00:00+09:00",
            end_at="2026-07-07T23:59:59.999999+09:00",
            page_size=observer_serializers.DEFAULT_OBSERVER_PAGE_SIZE,
            range_key=(
                "2026-07-01T00:00:00+09:00:"
                "2026-07-07T23:59:59.999999+09:00"
            ),
        )

    def test_observer_logs_page_converts_utc_range_to_seoul(self) -> None:
        """offset query도 같은 instant의 Asia/Seoul 범위로 전달합니다."""

        with patch(
            f"{OBSERVER_VIEW_SELECTORS}.get_log_pages",
            return_value={
                "data": {},
                "meta": {
                    "partial": False,
                    "allFailed": False,
                },
            },
        ) as selector:
            response = self.client.get(
                reverse("observer-logs-page"),
                {
                    "eqpId": "EQP-ALPHA",
                    "from": "2026-06-30T15:00:00Z",
                    "to": "2026-07-01T14:59:59Z",
                    "types": "eqp",
                },
            )

        self.assertEqual(response.status_code, 200)
        selector.assert_called_once_with(
            eqp_id="EQP-ALPHA",
            log_types=["eqp"],
            start_at="2026-07-01T00:00:00+09:00",
            end_at="2026-07-01T23:59:59+09:00",
            page_size=observer_serializers.DEFAULT_OBSERVER_PAGE_SIZE,
            range_key=(
                "2026-07-01T00:00:00+09:00:"
                "2026-07-01T23:59:59+09:00"
            ),
        )

    def test_observer_logs_page_rejects_more_than_ninety_days(self) -> None:
        """backend도 frontend와 같은 최대 90일 조회 범위를 강제합니다."""

        response = self.client.get(
            reverse("observer-logs-page"),
            {
                "eqpId": "EQP-ALPHA",
                "from": "2026-01-01",
                "to": "2026-07-07",
            },
        )

        self.assertEqual(response.status_code, 400)

    def test_observer_log_type_page_validates_cursor_scope(self) -> None:
        """다른 설비에서 발급한 cursor는 현재 page query에 재사용할 수 없습니다."""

        cursor = observer_serializers.encode_observer_cursor(
            {
                "eqpId": "OTHER-EQP",
                "logType": "eqp",
                "range": (
                    "2026-07-01T00:00:00:"
                    "2026-07-07T23:59:59.999999"
                ),
                "eventTime": "2026-07-06T10:00:00",
                "tieBreaker": 10,
            }
        )

        response = self.client.get(
            reverse("observer-logs-type-page", kwargs={"log_key": "eqp"}),
            {
                "eqpId": "EQP-ALPHA",
                "from": "2026-07-01",
                "to": "2026-07-07",
                "cursor": cursor,
            },
        )

        self.assertEqual(response.status_code, 400)

    def test_observer_log_detail_returns_selected_source(self) -> None:
        """detail endpoint가 설비/type/source ID를 selector에 전달합니다."""

        payload = {
            "id": "EQP-100",
            "sourceId": 7,
            "logType": "EQP",
        }
        with patch(
            f"{OBSERVER_VIEW_SELECTORS}.get_log_detail",
            return_value=payload,
        ) as selector:
            response = self.client.get(
                reverse("observer-log-detail", kwargs={"log_key": "eqp"}),
                {"eqpId": "eqp-alpha", "logId": "7"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), payload)
        selector.assert_called_once_with(
            eqp_id="EQP-ALPHA",
            log_key="eqp",
            log_id="7",
        )

    def test_observer_evidence_log_restores_analysis_source(self) -> None:
        """근거 endpoint가 분석 범위와 evidence ID를 selector에 전달합니다."""

        payload = {
            "id": "EQP-100",
            "logType": "EQP",
            "eventTime": "2026-08-01T10:00:00+09:00",
        }
        with patch(
            f"{OBSERVER_VIEW_SELECTORS}.get_analysis_evidence_log",
            return_value=payload,
        ) as selector:
            response = self.client.get(
                reverse("observer-evidence-log", kwargs={"log_key": "eqp"}),
                {
                    "eqpId": "eqp-alpha",
                    "evidenceId": "EQP:EQP-100",
                    "from": "2026-08-01",
                    "to": "2026-08-03",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), payload)
        selector.assert_called_once_with(
            eqp_id="EQP-ALPHA",
            log_key="eqp",
            evidence_id="EQP:EQP-100",
            start_at="2026-08-01T00:00:00+09:00",
            end_at="2026-08-03T23:59:59.999999+09:00",
        )

    def test_observer_log_detail_serializes_times_in_seoul(self) -> None:
        """상세 응답의 event와 갱신 시각을 Asia/Seoul로 직렬화합니다."""

        with patch(
            f"{OBSERVER_SELECTORS}.eqp_status_chg_selectors.get_eqp_timeline_detail",
            return_value={
                "id": 7,
                "eqp_event_key": 100,
                "eqp_cb": "EQP-ALPHA",
                "eqp_status_type": "RUN",
                "chg_time": datetime(
                    2026,
                    7,
                    6,
                    10,
                    30,
                    tzinfo=ZoneInfo("UTC"),
                ),
                "last_update_time": datetime(
                    2026,
                    7,
                    6,
                    10,
                    31,
                    tzinfo=ZoneInfo("UTC"),
                ),
            },
        ):
            detail = selectors.get_log_detail(
                eqp_id="EQP-ALPHA",
                log_key="eqp",
                log_id="7",
            )

        self.assertEqual(detail["eventTime"], "2026-07-06T19:30:00+09:00")
        self.assertEqual(
            detail["lastUpdateTime"],
            "2026-07-06T19:31:00+09:00",
        )

    def test_observer_detail_registry_wires_all_sources(self) -> None:
        """일곱 상세 source가 조회 인자와 고유 payload 계약을 유지하는지 확인합니다."""

        event_time = datetime(2026, 7, 6, 10, 30, tzinfo=ZoneInfo("UTC"))
        cases = (
            (
                "eqp",
                "eqp_status_chg_selectors.get_eqp_timeline_detail",
                {"id": 21, "eqp_event_key": 101, "chg_time": event_time},
                {"eqp_id": "EQP-ALPHA", "log_id": "21"},
                {"logType": "EQP", "sourceId": 21},
            ),
            (
                "tip",
                "mi_tip_update_hist_selectors.get_tip_timeline_detail",
                {
                    "id": 22,
                    "gpm_update_date": event_time,
                    "register_name": "USER-사용자",
                },
                {"eqp_id": "EQP-ALPHA", "log_id": "22"},
                {"logType": "TIP", "sourceId": 22, "operator": "USER"},
            ),
            (
                "spc-interlock",
                "m_interlock_selectors.get_interlock_timeline_detail",
                {
                    "id": 23,
                    "event_time": event_time,
                    "interlock_kind": "SPC",
                    "prod_eqp_id": "EQP-ALPHA",
                },
                {
                    "eqp_id": "EQP-ALPHA",
                    "interlock_kind": "SPC",
                    "source_id": 23,
                },
                {"logType": "SPC_ITL", "sourceId": 23, "eqpId": "EQP-ALPHA"},
            ),
            (
                "fdc-interlock",
                "m_interlock_selectors.get_interlock_timeline_detail",
                {
                    "id": 24,
                    "event_time": event_time,
                    "interlock_kind": "FDC",
                    "prod_eqp_id": "EQP-ALPHA",
                },
                {
                    "eqp_id": "EQP-ALPHA",
                    "interlock_kind": "FDC",
                    "source_id": 24,
                },
                {"logType": "FDC_ITL", "sourceId": 24, "eqpId": "EQP-ALPHA"},
            ),
            (
                "ctttm",
                "ctttm_workorder_selectors.get_ctttm_timeline_detail",
                {
                    "id": 25,
                    "workorder_id": "WO-25",
                    "inprg_date": event_time,
                },
                {"eqp_id": "EQP-ALPHA", "source_id": 25},
                {"logType": "CTTTM", "sourceId": 25, "coreSummary": "핵심 요약"},
            ),
            (
                "racb",
                "racb_list_selectors.get_racb_timeline_detail",
                {
                    "id": 26,
                    "c_racb_id": "R-26",
                    "eqp_cb": "EQP-ALPHA",
                    "update_date": event_time,
                },
                {"eqp_id": "EQP-ALPHA", "log_id": "26"},
                {"logType": "RACB", "sourceId": 26},
            ),
            (
                "esop",
                "drone_selectors.get_drone_sop_timeline_detail",
                {
                    "id": 27,
                    "created_at": event_time,
                    "sample_group": "SAMPLE-A",
                },
                {"eqp_id": "EQP-ALPHA", "source_id": 27},
                {"logType": "ESOP", "sourceId": 27, "sampleGroup": "SAMPLE-A"},
            ),
        )

        with patch(
            f"{OBSERVER_SELECTORS}._fetch_one",
            return_value={
                "llm_core_summary": "핵심 요약",
                "llm_summary": "전체 요약",
            },
        ):
            for log_key, fetch_path, row, fetch_options, expected in cases:
                with self.subTest(log_key=log_key), patch(
                    f"{OBSERVER_SELECTORS}.{fetch_path}",
                    return_value=row,
                ) as fetch_detail:
                    detail = selectors.get_log_detail(
                        eqp_id="EQP-ALPHA",
                        log_key=log_key,
                        log_id=str(row["id"]),
                    )

                fetch_detail.assert_called_once_with(**fetch_options)
                self.assertEqual(
                    {key: detail[key] for key in expected},
                    expected,
                )
                self.assertEqual(
                    detail["eventTime"],
                    "2026-07-06T19:30:00+09:00",
                )
