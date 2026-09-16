from . import *  # noqa: F403


class ObserverTkinEndpointTests(TestCase):
    """Observer TKIN Prevent 조회 계약을 검증합니다."""

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

    def test_tkin_prevent_prc_groups_requires_user_sdwt_prod(self) -> None:
        response = self.client.get(reverse("observer-tkin-prevent-prc-groups"))
        self.assertEqual(response.status_code, 400)

    def test_tkin_prevent_prc_groups_returns_results(self) -> None:
        with patch(
            f"{OBSERVER_VIEW_SELECTORS}.list_tkin_prevent_prc_groups",
            return_value=[],
        ) as selector:
            response = self.client.get(
                reverse("observer-tkin-prevent-prc-groups"),
                {"userSdwtProd": "sd-10"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.json(), list))
        selector.assert_called_once_with(user_sdwt_prod="SD-10")

    def test_tkin_prevent_processes_requires_scope(self) -> None:
        response = self.client.get(reverse("observer-tkin-prevent-processes"))
        self.assertEqual(response.status_code, 400)

    def test_tkin_prevent_processes_returns_results(self) -> None:
        with patch(
            f"{OBSERVER_VIEW_SELECTORS}.list_tkin_prevent_processes",
            return_value=[],
        ) as selector:
            response = self.client.get(
                reverse("observer-tkin-prevent-processes"),
                {"userSdwtProd": "sd-10", "prcGroup": "etch"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.json(), list))
        selector.assert_called_once_with(
            user_sdwt_prod="SD-10",
            prc_group="ETCH",
        )

    def test_tkin_prevent_step_seqs_requires_process(self) -> None:
        with patch(
            f"{OBSERVER_VIEW_SELECTORS}.list_tkin_prevent_step_seqs",
            return_value=[],
        ) as selector:
            response = self.client.get(
                reverse("observer-tkin-prevent-step-seqs"),
                {"userSdwtProd": "SD-10", "prcGroup": "ETCH"},
            )

        self.assertEqual(response.status_code, 400)
        selector.assert_not_called()

    def test_tkin_prevent_step_seqs_returns_results(self) -> None:
        with patch(
            f"{OBSERVER_VIEW_SELECTORS}.list_tkin_prevent_step_seqs",
            return_value=[],
        ) as selector:
            response = self.client.get(
                reverse("observer-tkin-prevent-step-seqs"),
                {
                    "userSdwtProd": "sd-10",
                    "prcGroup": "etch",
                    "processId": "proc-1",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.json(), list))
        selector.assert_called_once_with(
            user_sdwt_prod="SD-10",
            prc_group="ETCH",
            process_id="PROC-1",
        )

    def test_tkin_prevent_matrix_requires_process_and_step(self) -> None:
        with patch(
            f"{OBSERVER_VIEW_SELECTORS}.get_tkin_prevent_matrix",
            return_value={},
        ) as selector:
            response = self.client.get(
                reverse("observer-tkin-prevent-matrix"),
                {
                    "userSdwtProd": "SD-10",
                    "prcGroup": "ETCH",
                    "processId": "PROC-1",
                },
            )

        self.assertEqual(response.status_code, 400)
        selector.assert_not_called()

    def test_tkin_prevent_matrix_returns_results(self) -> None:
        payload = {"columns": [], "rows": [], "totalRows": 0, "totalColumns": 0}
        with patch(
            f"{OBSERVER_VIEW_SELECTORS}.get_tkin_prevent_matrix",
            return_value=payload,
        ) as selector:
            response = self.client.get(
                reverse("observer-tkin-prevent-matrix"),
                {
                    "userSdwtProd": "sd-10",
                    "prcGroup": "etch",
                    "processId": "proc-1",
                    "stepSeq": "10",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), payload)
        selector.assert_called_once_with(
            user_sdwt_prod="SD-10",
            prc_group="ETCH",
            process_id="PROC-1",
            step_seq="10",
        )

    def test_tkin_prevent_process_selector_uses_station_ch_main_scope(self) -> None:
        with patch(
            f"{OBSERVER_TKIN_SELECTORS}._fetch_all",
            return_value=[{"process_id": "PROC-1"}],
        ) as fetch_all:
            processes = selectors.list_tkin_prevent_processes(
                user_sdwt_prod="sd-10",
                prc_group="etch",
            )

        query, params = fetch_all.call_args.args
        self.assertEqual(processes[0]["id"], "PROC-1")
        self.assertIn("from station_master station", query)
        self.assertIn("station.ch_main as eqp_id", query)
        self.assertIn("from m_tkin_prevent prevent", query)
        self.assertIn("prevent.eqp_id = target_eqp.eqp_id", query)
        self.assertNotIn("upper(trim(prevent.eqp_id))", query)
        self.assertNotIn("upper(trim(target_eqp.eqp_id))", query)
        self.assertNotIn("mes_line_mapping_info", query)
        self.assertNotIn("gpm_line_name_lookup", query)
        self.assertIn("station.sdwt_prod_lookup = %s", query)
        self.assertIn("station.prc_group_lookup = %s", query)
        self.assertIn(
            "prevent.registration_level in (%s, %s, %s)",
            query,
        )
        self.assertEqual(params, ["SD-10", "ETCH", "LEVEL1", "LEVEL2", "LEVEL3"])

    def test_tkin_prevent_prc_groups_selector_uses_station_master(self) -> None:
        with patch(
            f"{OBSERVER_TKIN_SELECTORS}._fetch_all",
            return_value=[{"id": "ETCH"}],
        ) as fetch_all:
            groups = selectors.list_tkin_prevent_prc_groups(user_sdwt_prod="sd-10")

        query, params = fetch_all.call_args.args
        self.assertEqual(groups[0]["id"], "ETCH")
        self.assertIn("from station_master", query)
        self.assertIn("sdwt_prod_lookup = %s", query)
        self.assertIn("prc_group_lookup as id", query)
        self.assertNotIn("mes_line_mapping_info", query)
        self.assertEqual(params, ["SD-10"])

    def test_tkin_prevent_step_selector_filters_process(self) -> None:
        with patch(
            f"{OBSERVER_TKIN_SELECTORS}._fetch_all",
            return_value=[{"step_seq": "10"}],
        ) as fetch_all:
            steps = selectors.list_tkin_prevent_step_seqs(
                user_sdwt_prod="SD-10",
                prc_group="ETCH",
                process_id="proc-1",
            )

        query, params = fetch_all.call_args.args
        self.assertEqual(steps[0]["id"], "10")
        self.assertIn("prevent.process_id = %s", query)
        self.assertNotIn("upper(trim(prevent.process_id))", query)
        self.assertIn(
            "prevent.registration_level in (%s, %s, %s)",
            query,
        )
        self.assertEqual(
            params,
            ["SD-10", "ETCH", "PROC-1", "LEVEL1", "LEVEL2", "LEVEL3"],
        )

    def test_tkin_prevent_matrix_formats_cells(self) -> None:
        with patch(
            f"{OBSERVER_TKIN_SELECTORS}._fetch_all",
            return_value=[
                {
                    "ppid": "PPID-A",
                    "line_id": "LINE-A",
                    "eqp_id": "EQP-1",
                    "tkin_prevent_chamber_id": "CH-1",
                    "tkin_prevent_type": "DOING",
                    "tkin_prevent_comment": "DOING COMMENT",
                    "registration_level": None,
                    "tkin_restrc_lot_count": None,
                    "tkin_lot_count": None,
                    "level2_restrc_lot_count": None,
                },
                {
                    "ppid": "PPID-A",
                    "line_id": "LINE-A",
                    "eqp_id": "EQP-1",
                    "tkin_prevent_chamber_id": "CH-2",
                    "tkin_prevent_type": "PREVENT",
                    "tkin_prevent_comment": "PREVENT COMMENT",
                    "registration_level": "LEVEL2",
                    "tkin_restrc_lot_count": 4.0,
                    "tkin_lot_count": 10.0,
                    "level2_restrc_lot_count": 2.0,
                },
            ],
        ) as fetch_all:
            matrix = selectors.get_tkin_prevent_matrix(
                user_sdwt_prod="SD-10",
                prc_group="ETCH",
                process_id="proc-1",
                step_seq="10",
            )

        query, params = fetch_all.call_args.args
        self.assertEqual(matrix["totalRows"], 1)
        self.assertEqual(matrix["totalColumns"], 2)
        self.assertIn(
            "prevent.registration_level in (%s, %s, %s)",
            query,
        )
        self.assertEqual(
            params,
            ["SD-10", "ETCH", "PROC-1", "10", "LEVEL1", "LEVEL2", "LEVEL3"],
        )
        first_column_id = "LINE-A::EQP-1::CH-1"
        second_column_id = "LINE-A::EQP-1::CH-2"
        self.assertEqual(matrix["columns"][0]["id"], first_column_id)
        self.assertEqual(matrix["columns"][0]["label"], "EQP-1-CH-1")
        self.assertEqual(matrix["columns"][0]["lineId"], "LINE-A")
        self.assertEqual(matrix["rows"][0]["cells"][first_column_id][0]["status"], "DOING")
        self.assertEqual(
            matrix["rows"][0]["cells"][first_column_id][0]["comment"],
            "DOING COMMENT",
        )
        self.assertEqual(
            matrix["rows"][0]["cells"][second_column_id][0]["status"],
            "LEVEL2(2/4/10)",
        )
        self.assertEqual(
            matrix["rows"][0]["cells"][second_column_id][0]["comment"],
            "PREVENT COMMENT",
        )
        self.assertIn("prevent.tkin_prevent_comment", query)
        self.assertIn("prevent.process_id = %s", query)
        self.assertIn("prevent.step_seq = %s", query)
        self.assertIn(
            (
                "order by prevent.ppid, prevent.line_id, prevent.eqp_id, "
                "prevent.tkin_prevent_chamber_id"
            ),
            query,
        )
        self.assertNotIn("upper(trim(prevent.process_id))", query)
        self.assertNotIn("upper(trim(prevent.step_seq))", query)

    def test_tkin_prevent_matrix_separates_columns_by_line_id(self) -> None:
        with patch(
            f"{OBSERVER_TKIN_SELECTORS}._fetch_all",
            return_value=[
                {
                    "ppid": "PPID-A",
                    "line_id": "LINE-A",
                    "eqp_id": "EQP-1",
                    "tkin_prevent_chamber_id": "CH-1",
                    "tkin_prevent_type": "DOING",
                    "tkin_prevent_comment": "SAME COMMENT",
                    "registration_level": None,
                    "tkin_restrc_lot_count": None,
                    "tkin_lot_count": None,
                    "level2_restrc_lot_count": None,
                },
                {
                    "ppid": "PPID-A",
                    "line_id": "LINE-B",
                    "eqp_id": "EQP-1",
                    "tkin_prevent_chamber_id": "CH-1",
                    "tkin_prevent_type": "DOING",
                    "tkin_prevent_comment": "SAME COMMENT",
                    "registration_level": None,
                    "tkin_restrc_lot_count": None,
                    "tkin_lot_count": None,
                    "level2_restrc_lot_count": None,
                },
            ],
        ):
            matrix = selectors.get_tkin_prevent_matrix(
                user_sdwt_prod="SD-10",
                prc_group="ETCH",
                process_id="proc-1",
                step_seq="10",
            )

        first_column_id = "LINE-A::EQP-1::CH-1"
        second_column_id = "LINE-B::EQP-1::CH-1"
        self.assertEqual(matrix["totalRows"], 1)
        self.assertEqual(matrix["totalColumns"], 2)
        self.assertEqual(
            [column["id"] for column in matrix["columns"]],
            [first_column_id, second_column_id],
        )
        self.assertEqual(
            [column["lineId"] for column in matrix["columns"]],
            ["LINE-A", "LINE-B"],
        )
        self.assertEqual(
            matrix["rows"][0]["cells"][first_column_id][0]["status"],
            "DOING",
        )
        self.assertEqual(
            matrix["rows"][0]["cells"][second_column_id][0]["status"],
            "DOING",
        )
