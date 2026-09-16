from . import *  # noqa: F403


class ObserverMetadataEndpointTests(TestCase):
    """Observer 메타데이터와 설비 조회 계약을 검증합니다."""

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

    def test_observer_lines_returns_list(self) -> None:
        with patch(f"{OBSERVER_VIEW_SELECTORS}.list_lines", return_value=[]) as selector:
            response = self.client.get(reverse("observer-lines"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.json(), list))
        selector.assert_called_once_with()

    def test_observer_sdwts_requires_line(self) -> None:
        response = self.client.get(reverse("observer-sdwts"))
        self.assertEqual(response.status_code, 400)

    def test_observer_sdwts_returns_results(self) -> None:
        with patch(
            f"{OBSERVER_VIEW_SELECTORS}.list_sdwt_for_line",
            return_value=[],
        ) as selector:
            response = self.client.get(
                reverse("observer-sdwts"),
                {"lineId": "LINE-A"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.json(), list))
        selector.assert_called_once_with(line_id="LINE-A")

    def test_observer_lines_selector_uses_drone_tip_status_options(self) -> None:
        with patch(
            f"{OBSERVER_METADATA_SELECTORS}.drone_selectors.get_tip_status_line_sdwt_options_payload",
            return_value={
                "lines": [
                    {"lineId": "LINE-A", "userSdwtProds": ["SD-10"]},
                    {"lineId": "", "userSdwtProds": ["SD-EMPTY"]},
                ],
                "userSdwtProds": ["SD-10"],
            },
        ) as options:
            lines = selectors.list_lines()

        self.assertEqual(lines, [{"id": "LINE-A", "name": "LINE-A"}])
        options.assert_called_once_with()

    def test_observer_sdwt_selector_uses_drone_tip_status_options(self) -> None:
        with patch(
            f"{OBSERVER_METADATA_SELECTORS}.drone_selectors.get_tip_status_line_sdwt_options_payload",
            return_value={
                "lines": [
                    {"lineId": "LINE-A", "userSdwtProds": ["SD-10", ""]},
                    {"lineId": "LINE-B", "userSdwtProds": ["SD-20"]},
                ],
                "userSdwtProds": ["SD-10", "SD-20"],
            },
        ) as options:
            sdwts = selectors.list_sdwt_for_line(line_id="line-a")

        self.assertEqual(sdwts, [{"id": "SD-10", "name": "SD-10", "lineId": "LINE-A"}])
        options.assert_called_once_with()

    def test_observer_prc_groups_returns_results(self) -> None:
        with patch(
            f"{OBSERVER_VIEW_SELECTORS}.list_prc_groups",
            return_value=[],
        ) as selector:
            response = self.client.get(
                reverse("observer-prc-groups"),
                {"lineId": "LINE-A", "sdwtId": "SD-10"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.json(), list))
        selector.assert_called_once_with(line_id="LINE-A", sdwt_id="SD-10")

    def test_observer_prc_groups_normalizes_query_values(self) -> None:
        with patch(
            f"{OBSERVER_VIEW_SELECTORS}.list_prc_groups",
            return_value=[],
        ) as selector:
            response = self.client.get(
                reverse("observer-prc-groups"),
                {"lineId": "line-a", "sdwtId": "sd-10"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.json(), list))
        selector.assert_called_once_with(line_id="LINE-A", sdwt_id="SD-10")

    def test_observer_equipments_returns_results(self) -> None:
        with patch(
            f"{OBSERVER_VIEW_SELECTORS}.list_equipments",
            return_value=[],
        ) as selector:
            response = self.client.get(
                reverse("observer-equipments"),
                {"lineId": "LINE-A", "sdwtId": "SD-10", "prcGroup": "ETCH"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.json(), list))
        selector.assert_called_once_with(
            line_id="LINE-A",
            sdwt_id="SD-10",
            prc_group="ETCH",
        )

    def test_observer_prc_groups_selector_uses_station_master(self) -> None:
        with (
            patch(
                f"{OBSERVER_METADATA_SELECTORS}.drone_selectors.get_tip_status_line_sdwt_options_payload",
                return_value={
                    "lines": [{"lineId": "LINE-A", "userSdwtProds": ["SD-10"]}],
                    "userSdwtProds": ["SD-10"],
                },
            ) as options,
            patch(
                f"{OBSERVER_METADATA_SELECTORS}._fetch_all",
                return_value=[{"id": "ETCH"}],
            ) as fetch_all,
        ):
            groups = selectors.list_prc_groups(line_id="LINE-A", sdwt_id="sd-10")

        query, params = fetch_all.call_args.args
        self.assertEqual(groups[0]["id"], "ETCH")
        self.assertIn("from station_master", query)
        self.assertIn("sdwt_prod_lookup = %s", query)
        self.assertEqual(params, ["SD-10"])
        options.assert_called_once_with()

    def test_observer_prc_groups_selector_rejects_unowned_sdwt(self) -> None:
        with (
            patch(
                f"{OBSERVER_METADATA_SELECTORS}.drone_selectors.get_tip_status_line_sdwt_options_payload",
                return_value={
                    "lines": [{"lineId": "LINE-B", "userSdwtProds": ["SD-10"]}],
                    "userSdwtProds": ["SD-10"],
                },
            ),
            patch(f"{OBSERVER_METADATA_SELECTORS}._fetch_all") as fetch_all,
        ):
            groups = selectors.list_prc_groups(line_id="LINE-A", sdwt_id="sd-10")

        self.assertEqual(groups, [])
        fetch_all.assert_not_called()

    def test_observer_equipments_selector_uses_station_master(self) -> None:
        with (
            patch(
                f"{OBSERVER_METADATA_SELECTORS}.drone_selectors.get_tip_status_line_sdwt_options_payload",
                return_value={
                    "lines": [{"lineId": "LINE-A", "userSdwtProds": ["SD-10"]}],
                    "userSdwtProds": ["SD-10"],
                },
            ) as options,
            patch(
                f"{OBSERVER_METADATA_SELECTORS}._fetch_all",
                return_value=[
                    {
                        "id": "EQP-ALPHA",
                        "line_id": "LINE-A",
                        "sdwt_prod": "SD-10",
                        "prc_group": "ETCH",
                    },
                    {
                        "id": "EQP-ALPHA",
                        "line_id": "LINE-A",
                        "sdwt_prod": "SD-10",
                        "prc_group": "ETCH",
                    },
                ],
            ) as fetch_all,
        ):
            equipments = selectors.list_equipments(
                line_id="LINE-A",
                sdwt_id="sd-10",
                prc_group="etch",
            )

        query, params = fetch_all.call_args.args
        self.assertEqual(equipments[0]["id"], "EQP-ALPHA")
        self.assertEqual(equipments[0]["lineId"], "LINE-A")
        self.assertEqual(len(equipments), 1)
        self.assertIn("select distinct on (station.station)", query)
        self.assertIn("from station_master station", query)
        self.assertNotIn("mes_line_mapping_info", query)
        self.assertIn("station.prc_group_lookup = %s", query)
        self.assertIn("station.sdwt_prod_lookup = %s", query)
        self.assertEqual(params, ["LINE-A", "ETCH", "SD-10"])
        options.assert_called_once_with()

    def test_observer_equipments_normalizes_query_values(self) -> None:
        with patch(
            f"{OBSERVER_VIEW_SELECTORS}.list_equipments",
            return_value=[],
        ) as selector:
            response = self.client.get(
                reverse("observer-equipments"),
                {"lineId": "line-a", "sdwtId": "sd-10", "prcGroup": "etch"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.json(), list))
        selector.assert_called_once_with(
            line_id="LINE-A",
            sdwt_id="SD-10",
            prc_group="ETCH",
        )

    def test_observer_equipment_info_returns_result(self) -> None:
        payload = {
            "id": "EQP-ALPHA",
            "lineId": "LINE-A",
            "sdwtId": "SD-10",
            "prcGroup": "ETCH",
        }
        with patch(
            f"{OBSERVER_VIEW_SELECTORS}.get_equipment_info",
            return_value=payload,
        ) as selector:
            response = self.client.get(
                reverse("observer-equipment-info", kwargs={"eqp_id": "EQP-ALPHA"})
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], "EQP-ALPHA")
        selector.assert_called_once_with(eqp_id="EQP-ALPHA", line_id="")

    def test_observer_equipment_info_selector_uses_drone_target_line(self) -> None:
        with (
            patch(
                f"{OBSERVER_METADATA_SELECTORS}.drone_selectors.get_tip_status_line_sdwt_options_payload",
                return_value={
                    "lines": [{"lineId": "LINE-A", "userSdwtProds": ["SD-10"]}],
                    "userSdwtProds": ["SD-10"],
                },
            ) as options,
            patch(
                f"{OBSERVER_METADATA_SELECTORS}._fetch_one",
                return_value={
                    "id": "EQP-ALPHA",
                    "sdwt_prod": "Sd-10",
                    "sdwt_prod_lookup": "SD-10",
                    "prc_group": "ETCH",
                },
            ) as fetch_one,
        ):
            info = selectors.get_equipment_info(eqp_id="eqp-alpha")

        query, params = fetch_one.call_args.args
        self.assertEqual(info["id"], "EQP-ALPHA")
        self.assertEqual(info["lineId"], "LINE-A")
        self.assertEqual(info["sdwtId"], "SD-10")
        self.assertIn("from station_master station", query)
        self.assertNotIn("mes_line_mapping_info", query)
        self.assertIn("station.station_lookup = %s", query)
        self.assertEqual(params, ["EQP-ALPHA"])
        options.assert_called_once_with()
