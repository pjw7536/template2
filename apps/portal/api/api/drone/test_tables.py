# =============================================================================
# 모듈: 분리된 Drone 회귀 테스트
# 주요 가정: 공통 fixture와 import는 api.drone.tests에서 공유합니다.
# =============================================================================
from api.drone.tests import *  # noqa: F403
from api.drone.tests import (
    _allow_test_scope_access,
    _create_drone_sop,
    _create_target_recipient,
    _ensure_target_mapping,
    _set_current_affiliation,
    _sop_delivery_value,
    _target_configuration_value,
    _upsert_target,
)

class DroneTableSchemaHelpersTests(SimpleTestCase):
    """Drone 테이블 스키마 유틸 정규화/필터 규칙을 검증합니다."""

    def test_sanitize_identifier_returns_value_when_valid(self) -> None:
        """유효한 식별자는 그대로 반환되는지 확인합니다."""

        from api.drone.services import table_schema

        self.assertEqual(table_schema.sanitize_identifier(" table_1 "), "table_1")

    def test_sanitize_identifier_uses_fallback_when_invalid(self) -> None:
        """유효하지 않은 값은 fallback으로 대체되는지 확인합니다."""

        from api.drone.services import table_schema

        self.assertEqual(table_schema.sanitize_identifier("table-name", "fallback_table"), "fallback_table")

    def test_sanitize_identifier_rejects_invalid_fallback(self) -> None:
        """fallback도 유효하지 않으면 None을 반환하는지 확인합니다."""

        from api.drone.services import table_schema

        self.assertIsNone(table_schema.sanitize_identifier(None, "bad-name"))

    def test_sanitize_identifier_trims_fallback(self) -> None:
        """fallback 공백이 제거되어 반환되는지 확인합니다."""

        from api.drone.services import table_schema

        self.assertEqual(table_schema.sanitize_identifier(123, "  ok_table "), "ok_table")

    def test_build_line_filters_returns_empty_when_line_missing(self) -> None:
        """lineId가 없으면 필터가 비어있는지 확인합니다."""

        from api.drone.services import table_schema

        result = table_schema.build_line_filters(["sdwt_prod", "line_id"], None)

        self.assertEqual(result["filters"], [])
        self.assertEqual(result["params"], [])

    def test_normalize_line_filter_mode_defaults_to_target_when_invalid(self) -> None:
        """lineFilterMode가 유효하지 않으면 target_user_sdwt_prod 기본값으로 보정되는지 확인합니다."""

        from api.drone.services import table_schema

        self.assertEqual(
            table_schema.normalize_line_filter_mode("invalid-mode"),
            table_schema.LINE_FILTER_MODE_TARGET_USER_SDWT,
        )

    def test_build_line_filters_defaults_to_target_then_user_sdwt_prod(self) -> None:
        """기본 target 모드에서 target 컬럼이 없으면 user 소속 필터를 사용합니다."""

        from api.drone.services import table_schema

        result = table_schema.build_line_filters(["user_sdwt_prod", "sdwt_prod", "line_id"], "L1")

        expected = (
            "(LOWER(user_sdwt_prod) IN ("
            f"SELECT LOWER(mapping.user_sdwt_prod) FROM {table_schema.DRONE_TARGET_MAPPING_TABLE_NAME} mapping "
            f"JOIN {table_schema.DRONE_TARGET_TABLE_NAME} target ON target.id = mapping.target_id "
            "WHERE LOWER(target.line_id) = LOWER(%s) "
            "AND mapping.user_sdwt_prod IS NOT NULL "
            "AND mapping.user_sdwt_prod <> ''"
            ") OR LOWER(line_id) = LOWER(%s))"
        )
        self.assertEqual(result["filters"], [expected])
        self.assertEqual(result["params"], ["L1", "L1"])

    def test_build_line_filters_uses_target_user_sdwt_prod_when_requested(self) -> None:
        """target_user_sdwt_prod 모드에서 target_user_sdwt_prod 기준 필터를 사용하는지 확인합니다."""

        from api.drone.services import table_schema

        result = table_schema.build_line_filters(
            ["target_user_sdwt_prod", "sdwt_prod", "user_sdwt_prod", "line_id"],
            "L1",
            filter_mode=table_schema.LINE_FILTER_MODE_TARGET_USER_SDWT,
        )

        expected = (
            "(LOWER(target_user_sdwt_prod) IN ("
            f"SELECT LOWER(target_user_sdwt_prod) FROM {table_schema.DRONE_TARGET_TABLE_NAME} "
            "WHERE LOWER(line_id) = LOWER(%s) "
            "AND target_user_sdwt_prod IS NOT NULL "
            "AND target_user_sdwt_prod <> ''"
            ") OR LOWER(line_id) = LOWER(%s))"
        )
        self.assertEqual(result["filters"], [expected])
        self.assertEqual(result["params"], ["L1", "L1"])

    def test_build_line_filters_uses_user_sdwt_prod_when_requested(self) -> None:
        """user_sdwt_prod 모드에서 user_sdwt_prod 기준 필터를 사용하는지 확인합니다."""

        from api.drone.services import table_schema

        result = table_schema.build_line_filters(
            ["target_user_sdwt_prod", "sdwt_prod", "user_sdwt_prod", "line_id"],
            "L1",
            filter_mode=table_schema.LINE_FILTER_MODE_USER_SDWT,
        )

        expected = (
            "(LOWER(user_sdwt_prod) IN ("
            f"SELECT LOWER(mapping.user_sdwt_prod) FROM {table_schema.DRONE_TARGET_MAPPING_TABLE_NAME} mapping "
            f"JOIN {table_schema.DRONE_TARGET_TABLE_NAME} target ON target.id = mapping.target_id "
            "WHERE LOWER(target.line_id) = LOWER(%s) "
            "AND mapping.user_sdwt_prod IS NOT NULL "
            "AND mapping.user_sdwt_prod <> ''"
            ") OR LOWER(line_id) = LOWER(%s))"
        )
        self.assertEqual(result["filters"], [expected])
        self.assertEqual(result["params"], ["L1", "L1"])

    def test_build_line_filters_uses_sdwt_prod_only_when_requested(self) -> None:
        """sdwt_prod 모드에서 sdwt_prod 기준 필터를 사용하는지 확인합니다."""

        from api.drone.services import table_schema

        result = table_schema.build_line_filters(
            ["target_user_sdwt_prod", "sdwt_prod", "user_sdwt_prod", "line_id"],
            "L1",
            filter_mode=table_schema.LINE_FILTER_MODE_SDWT,
        )

        expected = (
            "(LOWER(sdwt_prod) IN ("
            f"SELECT LOWER(mapping.sdwt_prod) FROM {table_schema.DRONE_TARGET_MAPPING_TABLE_NAME} mapping "
            f"JOIN {table_schema.DRONE_TARGET_TABLE_NAME} target ON target.id = mapping.target_id "
            "WHERE LOWER(target.line_id) = LOWER(%s) "
            "AND mapping.sdwt_prod IS NOT NULL "
            "AND mapping.sdwt_prod <> ''"
            ") OR LOWER(line_id) = LOWER(%s))"
        )
        self.assertEqual(result["filters"], [expected])
        self.assertEqual(result["params"], ["L1", "L1"])

    def test_build_line_filters_uses_user_sdwt_prod_when_sdwt_missing(self) -> None:
        """sdwt_prod가 없으면 user_sdwt_prod 기준 필터를 사용하는지 확인합니다."""

        from api.drone.services import table_schema

        result = table_schema.build_line_filters(["user_sdwt_prod", "line_id"], "L1")

        expected = (
            "(LOWER(user_sdwt_prod) IN ("
            f"SELECT LOWER(mapping.user_sdwt_prod) FROM {table_schema.DRONE_TARGET_MAPPING_TABLE_NAME} mapping "
            f"JOIN {table_schema.DRONE_TARGET_TABLE_NAME} target ON target.id = mapping.target_id "
            "WHERE LOWER(target.line_id) = LOWER(%s) "
            "AND mapping.user_sdwt_prod IS NOT NULL "
            "AND mapping.user_sdwt_prod <> ''"
            ") OR LOWER(line_id) = LOWER(%s))"
        )
        self.assertEqual(result["filters"], [expected])
        self.assertEqual(result["params"], ["L1", "L1"])

    def test_build_line_filters_falls_back_to_line_id(self) -> None:
        """sdwt_prod가 없으면 line_id 직접 비교로 fallback 되는지 확인합니다."""

        from api.drone.services import table_schema

        result = table_schema.build_line_filters(["line_id", "created_at"], "L1")

        self.assertEqual(result["filters"], ["LOWER(line_id) = LOWER(%s)"])
        self.assertEqual(result["params"], ["L1"])


class DroneTablesEndpointTestsPart1(TestCase):
    """DroneTablesEndpointTests 분리 회귀 테스트 1부입니다."""

    def setUp(self) -> None:
        """테스트용 사용자/클라이언트를 준비합니다."""

        _allow_test_scope_access(self)
        User = get_user_model()
        self.user = User.objects.create_user(
            sabun="S41000",
            password="test-password",
            knox_id="knox-41000",
        )
        self.client.force_login(self.user)

    @patch("api.drone.services.table_ops._fetch_rows")
    @patch("api.drone.services.table_ops.table_schema.resolve_table_schema")
    def test_tables_list_returns_payload(self, mock_schema: Mock, mock_fetch_rows: Mock) -> None:
        """테이블 목록 조회가 정상 응답하는지 확인합니다."""

        mock_schema.return_value = SimpleNamespace(
            name="drone_sop",
            columns=["id", "created_at"],
            timestamp_column="created_at",
        )
        mock_fetch_rows.return_value = [{"id": 1, "created_at": "2024-01-01 00:00:00"}]

        response = self.client.get(reverse("drone-tables"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["table"], "drone_sop")
        self.assertEqual(payload["rowCount"], 1)

    @patch("api.drone.services.table_ops._fetch_rows")
    @patch("api.drone.services.table_ops.table_schema.resolve_table_schema")
    def test_tables_list_returns_ctttm_urls_as_array(
        self,
        mock_schema: Mock,
        mock_fetch_rows: Mock,
    ) -> None:
        """CTTTM URL JSON 문자열을 응답 배열로 정규화하는지 확인합니다."""

        ctttm_urls = [{"eqp_id": "ABCD-1", "url": "https://ctttm.example.local"}]
        mock_schema.return_value = SimpleNamespace(
            name="drone_sop",
            columns=["id", "created_at", "ctttm_urls"],
            timestamp_column="created_at",
        )
        mock_fetch_rows.return_value = [
            {
                "id": 1,
                "created_at": "2024-01-01 00:00:00",
                "ctttm_urls": json.dumps(ctttm_urls),
            }
        ]

        response = self.client.get(reverse("drone-tables"))

        self.assertEqual(response.status_code, 200)
        row = response.json()["rows"][0]
        self.assertEqual(row["ctttm_urls"], ctttm_urls)

    def test_tables_list_includes_delivery_rows_metadata(self) -> None:
        """테이블 조회 row에 channel delivery 메타가 포함되는지 확인합니다."""

        sop = _create_drone_sop(target_user_sdwt_prod="SOP-TARGET")
        DroneSopDelivery.objects.filter(sop=sop).delete()
        delivery = services.create_channel_delivery_with_dispatch(
            sop=sop,
            channel=DroneSopDelivery.Channels.JIRA,
            status=DroneSopDelivery.Statuses.SUCCESS,
            target_user_sdwt_prod="DELIVERY-SNAPSHOT",
        )
        delivery.external_key = "PROJ-1"
        delivery.sent_comment = "sent snapshot"
        delivery.sent_step = "ST-JIRA"
        delivery.sent_at = datetime(2024, 1, 1, 1, 0, 0, tzinfo=dt_timezone.utc)
        delivery.save(update_fields=["external_key", "sent_comment", "sent_step", "sent_at", "updated_at"])

        response = self.client.get(reverse("drone-tables"), {"table": "drone_sop", "recentHoursStart": "24"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertNotIn("deliveryRows", payload["columns"])
        self.assertIn("delivery_status", payload["columns"])
        self.assertIn("informed_at", payload["columns"])
        self.assertIn("jira_key", payload["columns"])
        self.assertNotIn("delivery_jira", payload["columns"])
        row = payload["rows"][0]
        self.assertEqual(row["id"], sop.id)
        self.assertEqual(row["delivery_status"], 1)
        self.assertEqual(row["delivery_targets"], "SOP-TARGET")
        self.assertEqual(row["delivery_jira"], 1)
        self.assertIsNone(row["delivery_messenger"])
        self.assertIsNone(row["delivery_mail"])
        self.assertEqual(row["delivery_visible_channels"], ["jira"])
        self.assertEqual(row["jira_key"], "PROJ-1")
        self.assertEqual(row["inform_step"], "ST-JIRA")
        self.assertIsNotNone(row["informed_at"])
        self.assertEqual(
            [
                (
                    delivery["targetUserSdwtProd"],
                    delivery["channel"],
                    delivery["status"],
                    delivery["sentComment"],
                    delivery["sentStep"],
                )
                for delivery in row["deliveryRows"]
            ],
            [
                ("DELIVERY-SNAPSHOT", "jira", "success", "sent snapshot", "ST-JIRA"),
            ],
        )

    def test_tables_list_uses_visible_non_jira_success_step_for_inform_step(self) -> None:
        """Jira 외 성공 delivery의 발송 step도 완료 표시 위치로 반환합니다."""

        sop = _create_drone_sop(
            target_user_sdwt_prod="MAIL-TARGET",
            send_jira=-1,
            send_mail=1,
        )
        DroneSopDelivery.objects.filter(sop=sop).delete()
        delivery = services.create_channel_delivery_with_dispatch(
            sop=sop,
            channel=DroneSopDelivery.Channels.MAIL,
            status=DroneSopDelivery.Statuses.SUCCESS,
            target_user_sdwt_prod="MAIL-TARGET",
        )
        delivery.sent_step = "ST-INSTANT"
        delivery.sent_at = datetime(2024, 1, 1, 2, 0, 0, tzinfo=dt_timezone.utc)
        delivery.save(update_fields=["sent_step", "sent_at", "updated_at"])

        response = self.client.get(reverse("drone-tables"), {"table": "drone_sop", "recentHoursStart": "24"})

        self.assertEqual(response.status_code, 200)
        row = next(row for row in response.json()["rows"] if row["id"] == sop.id)
        self.assertEqual(row["delivery_mail"], 1)
        self.assertEqual(row["inform_step"], "ST-INSTANT")
        self.assertIsNone(row.get("jira_key"))

    def test_tables_list_uses_sop_target_when_delivery_missing(self) -> None:
        """delivery가 없어도 SOP의 target_user_sdwt_prod를 알림 Target으로 반환합니다."""

        sop = _create_drone_sop(
            target_user_sdwt_prod="TARGET-VISIBLE",
            status="IN_PROGRESS",
            needtosend=0,
            instant_inform=0,
        )

        response = self.client.get(reverse("drone-tables"), {"table": "drone_sop", "recentHoursStart": "24"})

        self.assertEqual(response.status_code, 200)
        row = next(row for row in response.json()["rows"] if row["id"] == sop.id)
        self.assertFalse(DroneSopDelivery.objects.filter(sop=sop).exists())
        self.assertEqual(row["delivery_targets"], "TARGET-VISIBLE")
        self.assertIsNone(row["delivery_status"])
        self.assertIsNone(row["delivery_jira"])
        self.assertIsNone(row["delivery_messenger"])
        self.assertIsNone(row["delivery_mail"])

    def test_tables_list_uses_enabled_channel_flags_when_delivery_missing(self) -> None:
        """delivery row가 아직 없어도 활성 채널은 전송 상태에 대기로 표시합니다."""

        _upsert_target(
            target_user_sdwt_prod="TARGET-ACTIVE",
            jira_enabled=False,
            messenger_enabled=True,
            mail_enabled=True,
        )
        sop = DroneSOP.objects.create(
            line_id="L1",
            target_user_sdwt_prod="TARGET-ACTIVE",
            eqp_id="EQP-ACTIVE",
            chamber_ids="1",
            lot_id="LOT.ACTIVE",
            main_step="MS",
            status="COMPLETE",
            needtosend=1,
            instant_inform=0,
        )

        response = self.client.get(reverse("drone-tables"), {"table": "drone_sop", "recentHoursStart": "24"})

        self.assertEqual(response.status_code, 200)
        row = next(row for row in response.json()["rows"] if row["id"] == sop.id)
        self.assertFalse(DroneSopDelivery.objects.filter(sop=sop).exists())
        self.assertEqual(row["delivery_status"], 0)
        self.assertIsNone(row["delivery_jira"])
        self.assertEqual(row["delivery_messenger"], 0)
        self.assertEqual(row["delivery_mail"], 0)
        self.assertEqual(row["delivery_visible_channels"], ["messenger", "mail"])

    def test_tables_list_uses_enabled_channel_flags_before_complete(self) -> None:
        """예약된 SOP는 COMPLETE 전이어도 예정 채널을 대기로 표시합니다."""

        _upsert_target(
            target_user_sdwt_prod="TARGET-PLANNED",
            jira_enabled=True,
            messenger_enabled=True,
            mail_enabled=False,
        )
        sop = DroneSOP.objects.create(
            line_id="L1",
            target_user_sdwt_prod="TARGET-PLANNED",
            eqp_id="EQP-PLANNED",
            chamber_ids="1",
            lot_id="LOT.PLANNED",
            main_step="MS",
            status="IN_PROGRESS",
            needtosend=1,
            instant_inform=0,
        )

        response = self.client.get(reverse("drone-tables"), {"table": "drone_sop", "recentHoursStart": "24"})

        self.assertEqual(response.status_code, 200)
        row = next(row for row in response.json()["rows"] if row["id"] == sop.id)
        self.assertFalse(DroneSopDelivery.objects.filter(sop=sop).exists())
        self.assertEqual(row["delivery_status"], 0)
        self.assertEqual(row["delivery_jira"], 0)
        self.assertEqual(row["delivery_messenger"], 0)
        self.assertIsNone(row["delivery_mail"])
        self.assertEqual(row["delivery_visible_channels"], ["jira", "messenger"])

    def test_tables_list_marks_cancelled_delivery_as_blocked_status(self) -> None:
        """취소 delivery는 비활성이 아니라 차단 상태로 요약합니다."""

        _upsert_target(
            target_user_sdwt_prod="TARGET-CANCELLED",
            jira_key="PROJ",
            jira_template_key="common",
        )
        sop = _create_drone_sop(target_user_sdwt_prod="TARGET-CANCELLED")
        delivery = DroneSopDelivery.objects.get(
            sop=sop,
            channel=DroneSopDelivery.Channels.JIRA,
        )
        delivery.status = DroneSopDelivery.Statuses.CANCELLED
        delivery.reason = "cancelled"
        delivery.save(update_fields=["status", "reason", "updated_at"])

        response = self.client.get(reverse("drone-tables"), {"table": "drone_sop", "recentHoursStart": "24"})

        self.assertEqual(response.status_code, 200)
        row = next(row for row in response.json()["rows"] if row["id"] == sop.id)
        self.assertEqual(row["delivery_status"], -1)
        self.assertEqual(row["delivery_jira"], -1)

    def test_tables_list_hides_existing_delivery_when_channel_disabled(self) -> None:
        """현재 비활성화된 채널은 기존 pending delivery가 있어도 표시하지 않습니다."""

        _upsert_target(
            target_user_sdwt_prod="TARGET-HIDDEN",
            jira_key="PROJ",
            jira_template_key="common",
        )
        sop = _create_drone_sop(target_user_sdwt_prod="TARGET-HIDDEN", send_jira=0)
        _upsert_target(
            target_user_sdwt_prod="TARGET-HIDDEN",
            jira_enabled=False,
        )

        response = self.client.get(reverse("drone-tables"), {"table": "drone_sop", "recentHoursStart": "24"})

        self.assertEqual(response.status_code, 200)
        row = next(row for row in response.json()["rows"] if row["id"] == sop.id)
        self.assertIsNone(row["delivery_jira"])
        self.assertNotIn("jira", row["delivery_visible_channels"])
        self.assertIsNone(row.get("jira_key"))
        self.assertIsNone(row.get("informed_at"))

    def test_table_record_delivery_update_payload_excludes_base_target(self) -> None:
        """단건 갱신 payload는 화면 row target을 덮어쓰지 않는지 확인합니다."""

        sop = _create_drone_sop(target_user_sdwt_prod="TARGET-A")
        payload = services.get_table_record_delivery_update_payload(record_id=int(sop.id))

        self.assertIn("deliveryRows", payload)
        self.assertIn("delivery_jira", payload)
        self.assertIn("delivery_visible_channels", payload)
        self.assertNotIn("target_user_sdwt_prod", payload)

    def test_tables_list_rejects_non_drone_sop_table(self) -> None:
        """drone_sop 외 테이블 조회를 거부하는지 확인합니다."""

        response = self.client.get(reverse("drone-tables"), {"table": "demo_table"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json().get("error"), "Only drone_sop table is supported")

    @patch("api.drone.services.table_ops._fetch_rows")
    @patch("api.drone.services.table_ops.table_schema.build_line_filters")
    @patch("api.drone.services.table_ops.table_schema.resolve_table_schema")
    def test_tables_list_defaults_to_target_user_sdwt_filter_mode(
        self,
        mock_schema: Mock,
        mock_build_line_filters: Mock,
        mock_fetch_rows: Mock,
    ) -> None:
        """lineFilterMode 미지정 시 target_user_sdwt_prod 모드가 기본 적용되는지 확인합니다."""

        from api.drone.services import table_schema

        mock_schema.return_value = SimpleNamespace(
            name="drone_sop",
            columns=["id", "created_at", "target_user_sdwt_prod"],
            timestamp_column="created_at",
        )
        mock_build_line_filters.return_value = {"filters": [], "params": []}
        mock_fetch_rows.return_value = []

        response = self.client.get(reverse("drone-tables"), {"lineId": "L1"})
        self.assertEqual(response.status_code, 200)
        mock_build_line_filters.assert_called_once_with(
            ["id", "created_at", "target_user_sdwt_prod"],
            "L1",
            filter_mode=table_schema.LINE_FILTER_MODE_TARGET_USER_SDWT,
        )

    @patch("api.drone.services.table_ops._fetch_rows")
    @patch("api.drone.services.table_ops.table_schema.build_line_filters")
    @patch("api.drone.services.table_ops.table_schema.resolve_table_schema")
    def test_tables_list_accepts_sdwt_filter_mode_override(
        self,
        mock_schema: Mock,
        mock_build_line_filters: Mock,
        mock_fetch_rows: Mock,
    ) -> None:
        """lineFilterMode=sdwt_prod가 전달되면 sdwt_prod 모드로 조회하는지 확인합니다."""

        from api.drone.services import table_schema

        mock_schema.return_value = SimpleNamespace(
            name="drone_sop",
            columns=["id", "created_at", "sdwt_prod"],
            timestamp_column="created_at",
        )
        mock_build_line_filters.return_value = {"filters": [], "params": []}
        mock_fetch_rows.return_value = []

        response = self.client.get(
            reverse("drone-tables"),
            {"lineId": "L1", "lineFilterMode": table_schema.LINE_FILTER_MODE_SDWT},
        )
        self.assertEqual(response.status_code, 200)
        mock_build_line_filters.assert_called_once_with(
            ["id", "created_at", "sdwt_prod"],
            "L1",
            filter_mode=table_schema.LINE_FILTER_MODE_SDWT,
        )

    @patch("api.drone.services.table_ops._fetch_rows")
    @patch("api.drone.services.table_ops.table_schema.build_line_filters")
    @patch("api.drone.services.table_ops.table_schema.resolve_table_schema")
    def test_tables_list_accepts_user_sdwt_filter_mode_override(
        self,
        mock_schema: Mock,
        mock_build_line_filters: Mock,
        mock_fetch_rows: Mock,
    ) -> None:
        """lineFilterMode=user_sdwt_prod가 전달되면 user_sdwt_prod 모드로 조회하는지 확인합니다."""

        from api.drone.services import table_schema

        mock_schema.return_value = SimpleNamespace(
            name="drone_sop",
            columns=["id", "created_at", "user_sdwt_prod"],
            timestamp_column="created_at",
        )
        mock_build_line_filters.return_value = {"filters": [], "params": []}
        mock_fetch_rows.return_value = []

        response = self.client.get(
            reverse("drone-tables"),
            {"lineId": "L1", "lineFilterMode": table_schema.LINE_FILTER_MODE_USER_SDWT},
        )
        self.assertEqual(response.status_code, 200)
        mock_build_line_filters.assert_called_once_with(
            ["id", "created_at", "user_sdwt_prod"],
            "L1",
            filter_mode=table_schema.LINE_FILTER_MODE_USER_SDWT,
        )

    @patch("api.drone.services.table_ops._fetch_rows")
    @patch("api.drone.services.table_ops.table_schema.resolve_table_schema")
    def test_tables_list_returns_raw_reason_columns_without_aliases(
        self,
        mock_schema: Mock,
        mock_fetch_rows: Mock,
    ) -> None:
        """테이블 조회 응답은 reason 원본 컬럼만 반환하고 별칭을 추가하지 않는지 확인합니다."""

        mock_schema.return_value = SimpleNamespace(
            name="drone_sop",
            columns=["id", "created_at", "jira_reason", "messenger_reason", "mail_reason"],
            timestamp_column="created_at",
        )
        mock_fetch_rows.return_value = [
            {
                "id": 1,
                "created_at": "2024-01-01 00:00:00",
                "jira_reason": "disabled_by_policy",
                "messenger_reason": None,
                "mail_reason": "send_failed",
            }
        ]

        response = self.client.get(reverse("drone-tables"), {"table": "drone_sop"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            payload["columns"],
            [
                "id",
                "created_at",
                "jira_reason",
                "messenger_reason",
                "mail_reason",
                "informed_at",
                "jira_key",
                "delivery_targets",
                "delivery_status",
            ],
        )
        row = payload["rows"][0]
        self.assertEqual(row["jira_reason"], "disabled_by_policy")
        self.assertIsNone(row["messenger_reason"])
        self.assertEqual(row["mail_reason"], "send_failed")
        self.assertNotIn("jiraReason", row)
        self.assertNotIn("messengerReason", row)
        self.assertNotIn("mailReason", row)

class DroneTablesEndpointTestsPart2(TestCase):
    """DroneTablesEndpointTests 분리 회귀 테스트 2부입니다."""

    def setUp(self) -> None:
        """테스트용 사용자/클라이언트를 준비합니다."""

        _allow_test_scope_access(self)
        User = get_user_model()
        self.user = User.objects.create_user(
            sabun="S41000",
            password="test-password",
            knox_id="knox-41000",
        )
        self.client.force_login(self.user)

    @patch("api.drone.services.table_ops.execute")
    @patch("api.drone.services.table_ops._fetch_row")
    @patch("api.drone.services.table_ops.table_schema.list_table_columns")
    def test_tables_update_returns_success(
        self,
        mock_columns: Mock,
        mock_fetch_row: Mock,
        mock_execute: Mock,
    ) -> None:
        """테이블 업데이트가 성공 응답을 반환하는지 확인합니다."""

        mock_columns.return_value = ["id", "comment"]
        mock_execute.return_value = (1, None)
        mock_fetch_row.side_effect = [
            {"id": 10, "comment": "before"},
            {"id": 10, "comment": "updated"},
            {"id": 10, "comment": "updated"},
        ]

        response = self.client.patch(
            reverse("drone-tables-update"),
            data='{"table":"drone_sop","id":10,"updates":{"comment":"updated"}}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertEqual(response.json()["updated"]["comment"], "updated")

    @patch("api.drone.services.table_ops.execute")
    @patch("api.drone.services.table_ops._fetch_row")
    @patch("api.drone.services.table_ops.table_schema.list_table_columns")
    def test_tables_update_allows_needtosend(
        self,
        mock_columns: Mock,
        mock_fetch_row: Mock,
        mock_execute: Mock,
    ) -> None:
        """사용자 수정 필드인 needtosend 업데이트가 허용되는지 확인합니다."""

        mock_columns.return_value = ["id", "needtosend"]
        mock_execute.return_value = (1, None)
        mock_fetch_row.side_effect = [
            {"id": 12, "needtosend": 0},
            {"id": 12},
            {"id": 12, "needtosend": 1},
            {"id": 12, "needtosend": 1},
        ]

        response = self.client.patch(
            reverse("drone-tables-update"),
            data='{"table":"drone_sop","id":12,"updates":{"needtosend":true}}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertEqual(response.json()["updated"]["needtosend"], 1)
        self.assertEqual(mock_execute.call_args.args[1], [1, 12])

    @patch("api.drone.services.table_ops.execute")
    @patch("api.drone.services.table_ops.table_schema.list_table_columns")
    def test_tables_update_rejects_invalid_needtosend_value(
        self,
        mock_columns: Mock,
        mock_execute: Mock,
    ) -> None:
        """needtosend는 0/1 외 값을 저장하지 않습니다."""

        mock_columns.return_value = ["id", "needtosend"]

        response = self.client.patch(
            reverse("drone-tables-update"),
            data='{"table":"drone_sop","id":12,"updates":{"needtosend":2}}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json().get("error"), "needtosend는 0 또는 1만 입력할 수 있습니다.")
        mock_execute.assert_not_called()

    def test_tables_update_needtosend_zero_rejects_when_delivery_exists(self) -> None:
        """delivery 생성 이후에는 예약 수정을 거부합니다."""

        sop = _create_drone_sop(
            target_user_sdwt_prod="TARGET-LOCK",
            eqp_id="EQP-LOCK",
            lot_id="LOT.LOCK",
            status="COMPLETE",
            needtosend=1,
        )
        delivery = services.create_channel_delivery_with_dispatch(
            sop=sop,
            channel=DroneSopDelivery.Channels.JIRA,
            status=DroneSopDelivery.Statuses.PENDING,
        )

        response = self.client.patch(
            reverse("drone-tables-update"),
            data=json.dumps({"table": "drone_sop", "id": sop.id, "updates": {"needtosend": 0}}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json().get("error"), "이미 전송 작업이 생성되어 예약을 수정할 수 없습니다.")
        sop.refresh_from_db()
        delivery.refresh_from_db()
        self.assertEqual(sop.needtosend, 1)
        self.assertEqual(delivery.status, DroneSopDelivery.Statuses.PENDING)

    def test_tables_update_needtosend_one_rejects_when_delivery_exists(self) -> None:
        """delivery 생성 이후에는 예약 재설정도 거부합니다."""

        sop = _create_drone_sop(
            target_user_sdwt_prod="TARGET-REENABLE-LOCK",
            eqp_id="EQP-REENABLE-LOCK",
            lot_id="LOT.REENABLE.LOCK",
            status="COMPLETE",
            needtosend=1,
        )
        delivery = services.create_channel_delivery_with_dispatch(
            sop=sop,
            channel=DroneSopDelivery.Channels.JIRA,
            status=DroneSopDelivery.Statuses.DISABLED,
        )
        DroneSOP.objects.filter(id=sop.id).update(needtosend=0)

        response = self.client.patch(
            reverse("drone-tables-update"),
            data=json.dumps({"table": "drone_sop", "id": sop.id, "updates": {"needtosend": 1}}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json().get("error"), "이미 전송 작업이 생성되어 예약을 수정할 수 없습니다.")
        sop.refresh_from_db()
        delivery.refresh_from_db()
        self.assertEqual(sop.needtosend, 0)
        self.assertEqual(delivery.status, DroneSopDelivery.Statuses.DISABLED)

    def test_tables_update_needtosend_zero_allows_before_delivery_exists(self) -> None:
        """delivery 생성 전에는 예약 해제를 허용합니다."""

        sop = DroneSOP.objects.create(
            line_id="L1",
            sdwt_prod="SDWT-BEFORE-DELIVERY",
            user_sdwt_prod="USER-BEFORE-DELIVERY",
            target_user_sdwt_prod="TARGET-BEFORE-DELIVERY",
            eqp_id="EQP-BEFORE-DELIVERY",
            chamber_ids="1",
            lot_id="LOT.BEFORE.DELIVERY",
            main_step="MS",
            status="COMPLETE",
            needtosend=1,
        )
        self.assertFalse(DroneSopDelivery.objects.filter(sop=sop).exists())

        response = self.client.patch(
            reverse("drone-tables-update"),
            data=json.dumps({"table": "drone_sop", "id": sop.id, "updates": {"needtosend": 0}}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        sop.refresh_from_db()
        self.assertEqual(sop.needtosend, 0)
        updated = response.json()["updated"]
        self.assertIsNone(updated["delivery_status"])
        self.assertIsNone(updated["delivery_jira"])
        self.assertIsNone(updated["delivery_messenger"])
        self.assertIsNone(updated["delivery_mail"])
        self.assertEqual(updated["delivery_visible_channels"], [])

    def test_tables_update_needtosend_returns_delivery_flags(self) -> None:
        """예약 수정 직후 응답에도 활성 채널 전송 상태를 포함합니다."""

        _upsert_target(
            target_user_sdwt_prod="TARGET-UPDATE",
            jira_enabled=False,
            messenger_enabled=True,
            mail_enabled=True,
        )
        sop = DroneSOP.objects.create(
            line_id="L1",
            target_user_sdwt_prod="TARGET-UPDATE",
            eqp_id="EQP-UPDATE",
            chamber_ids="1",
            lot_id="LOT.UPDATE",
            main_step="MS",
            status="COMPLETE",
            needtosend=0,
            instant_inform=0,
        )

        response = self.client.patch(
            reverse("drone-tables-update"),
            data=json.dumps({"table": "drone_sop", "id": sop.id, "updates": {"needtosend": 1}}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        updated = response.json()["updated"]
        self.assertEqual(updated["needtosend"], 1)
        self.assertEqual(updated["delivery_status"], 0)
        self.assertIsNone(updated["delivery_jira"])
        self.assertEqual(updated["delivery_messenger"], 0)
        self.assertEqual(updated["delivery_mail"], 0)
        self.assertEqual(updated["delivery_visible_channels"], ["messenger", "mail"])

    @patch("api.drone.services.table_ops.execute")
    def test_tables_update_rejects_parsing_controlled_fields(self, mock_execute: Mock) -> None:
        """일반 수정 API에서 관리하지 않는 필드는 거부되는지 확인합니다."""

        for field_name, value in (
            ("status", "COMPLETE"),
            ("instant_inform", 1),
        ):
            with self.subTest(field_name=field_name):
                response = self.client.patch(
                    reverse("drone-tables-update"),
                    data=json.dumps({"table": "drone_sop", "id": 11, "updates": {field_name: value}}),
                    content_type="application/json",
                )

                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json().get("error"), "No valid updates provided")

        mock_execute.assert_not_called()

    @patch("api.drone.services.table_ops.execute")
    def test_tables_update_rejects_values_alias(self, mock_execute: Mock) -> None:
        """values 별칭만 전달하면 400 오류를 반환하는지 확인합니다."""

        response = self.client.patch(
            reverse("drone-tables-update"),
            data='{"table":"drone_sop","id":11,"values":{"comment":"updated"}}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json().get("error"), "Updates must be an object")
        mock_execute.assert_not_called()

    @patch("api.drone.services.table_ops.execute")
    def test_tables_update_rejects_non_drone_sop_table(self, mock_execute: Mock) -> None:
        """drone_sop 외 테이블 수정 요청을 거부하는지 확인합니다."""

        response = self.client.patch(
            reverse("drone-tables-update"),
            data='{"table":"demo_table","id":11,"updates":{"comment":"updated"}}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json().get("error"), "Only drone_sop table is supported")
        mock_execute.assert_not_called()
