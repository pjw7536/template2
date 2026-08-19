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

class DroneSopTargetChannelServiceTests(TestCase):
    """Drone SOP target/channel 설정 서비스의 경계 동작을 검증합니다."""

    def test_create_target_or_reselect_handles_concurrent_unique_conflict(self) -> None:
        """동시 생성 unique 충돌 시 기존 target을 다시 조회하는지 확인합니다."""

        existing = DroneSopTarget.objects.create(target_user_sdwt_prod="SDWT", line_id="L1")

        with patch.object(
            channel_services.DroneSopTarget.objects,
            "create",
            side_effect=IntegrityError("duplicate target"),
        ):
            target, created = channel_services._create_target_or_reselect(
                normalized_target="sdwt",
                line_id="L1",
            )

        self.assertFalse(created)
        self.assertEqual(target.id, existing.id)

    def test_get_or_create_channel_config_handles_concurrent_unique_conflict(self) -> None:
        """동시 생성 unique 충돌 시 기존 채널 설정을 다시 조회하는지 확인합니다."""

        target = DroneSopTarget.objects.create(target_user_sdwt_prod="SDWT", line_id="L1")
        existing = DroneSopTargetChannelConfig.objects.create(
            target=target,
            channel=DroneSopTargetChannelConfig.Channels.JIRA,
        )

        with patch.object(
            channel_services.DroneSopTargetChannelConfig.objects,
            "create",
            side_effect=IntegrityError("duplicate channel config"),
        ):
            config, created = channel_services._get_or_create_channel_config(
                target=target,
                channel=DroneSopTargetChannelConfig.Channels.JIRA,
            )

        self.assertFalse(created)
        self.assertEqual(config.id, existing.id)

    def test_target_configuration_serializer_reuses_prefetched_rows(self) -> None:
        """target 설정 직렬화가 prefetch된 normalized row를 재사용하는지 확인합니다."""

        _upsert_target(
            target_user_sdwt_prod="SDWT",
            jira_key="PROJ",
            jira_template_key="common",
            mail_template_key="mail",
            messenger_template_key="messenger",
            chatroom_id=12345,
            force_new_chatroom=True,
        )
        target = DroneSopTarget.objects.prefetch_related(
            "channel_configs",
            "needtosend_rule",
        ).get(target_user_sdwt_prod="SDWT")

        with CaptureQueriesContext(connection) as captured:
            configuration = serialize_drone_sop_target_configuration(target)

        self.assertEqual(configuration["jiraKey"], "PROJ")
        self.assertEqual(configuration["jiraTemplateKey"], "common")
        self.assertEqual(configuration["mailTemplateKey"], "mail")
        self.assertEqual(configuration["messengerTemplateKey"], "messenger")
        messenger = target.channel_configs.get(
            channel=DroneSopTargetChannelConfig.Channels.MESSENGER,
        )
        self.assertEqual(messenger.chatroom_id, 12345)
        self.assertTrue(configuration["messengerForceNewChatroom"])

        self.assertEqual(len(captured), 0)


class DroneEarlyInformInputSerializerTests(SimpleTestCase):
    """Drone 조기 알림 생성·수정 입력 정규화 계약을 검증합니다."""

    def test_create_normalizes_existing_camel_case_inputs(self) -> None:
        """생성 입력의 공백과 숫자 mainStep을 기존 규칙대로 정규화합니다."""

        serializer = DroneEarlyInformCreateSerializer(
            data={
                "lineId": " L1 ",
                "mainStep": 123,
                "customEndStep": " STEP2 ",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["normalized_line_id"], "L1")
        self.assertEqual(serializer.validated_data["normalized_main_step"], "123")
        self.assertEqual(
            serializer.validated_data["normalized_custom_end_step"],
            "STEP2",
        )

    def test_update_builds_only_provided_service_fields(self) -> None:
        """PATCH에서 제공된 필드만 snake_case 변경값으로 구성합니다."""

        serializer = DroneEarlyInformUpdateFieldsSerializer(
            data={"customEndStep": ""}
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            serializer.validated_data["normalized_updates"],
            {"custom_end_step": None},
        )

    def test_serializers_preserve_existing_validation_messages(self) -> None:
        """필수값과 길이 오류가 기존 API 문구를 유지하는지 확인합니다."""

        missing_line = DroneEarlyInformCreateSerializer(
            data={"mainStep": "STEP1"}
        )
        long_custom_end_step = DroneEarlyInformCreateSerializer(
            data={
                "lineId": "L1",
                "mainStep": "STEP1",
                "customEndStep": "A" * 51,
            }
        )
        empty_update = DroneEarlyInformUpdateFieldsSerializer(data={})

        self.assertFalse(missing_line.is_valid())
        self.assertEqual(
            str(missing_line.errors["non_field_errors"][0]),
            "lineId is required",
        )
        self.assertFalse(long_custom_end_step.is_valid())
        self.assertEqual(
            str(long_custom_end_step.errors["non_field_errors"][0]),
            "customEndStep must be 50 characters or fewer",
        )
        self.assertFalse(empty_update.is_valid())
        self.assertEqual(
            str(empty_update.errors["non_field_errors"][0]),
            "No valid fields to update",
        )


class DroneNotificationTargetMappingInputSerializerTests(SimpleTestCase):
    """Drone 알림 target mapping operation별 입력 계약을 검증합니다."""

    def test_create_normalizes_common_fields_and_defaults_policy(self) -> None:
        """생성 입력을 정규화하고 Comment 생략 정책 기본값을 False로 설정합니다."""

        serializer = DroneNotificationTargetMappingCreateSerializer(
            data={
                "lineId": " L1 ",
                "targetUserSdwtProd": " TARGET_A ",
                "sdwtProd": " SDWT_A ",
                "userSdwtProd": " USER_A ",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["normalized_line_id"], "L1")
        self.assertEqual(
            serializer.validated_data["normalized_target_user_sdwt_prod"],
            "TARGET_A",
        )
        self.assertEqual(serializer.validated_data["normalized_sdwt_prod"], "SDWT_A")
        self.assertEqual(
            serializer.validated_data["normalized_user_sdwt_prod"],
            "USER_A",
        )
        self.assertFalse(
            serializer.validated_data["normalized_needtosend_without_comment"]
        )

    def test_update_requires_boolean_policy(self) -> None:
        """PATCH에서는 Comment 생략 정책 boolean이 반드시 필요한지 확인합니다."""

        serializer = DroneNotificationTargetMappingUpdateSerializer(
            data={
                "lineId": "L1",
                "targetUserSdwtProd": "TARGET_A",
                "sdwtProd": "SDWT_A",
                "userSdwtProd": "USER_A",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertEqual(
            str(serializer.errors["non_field_errors"][0]),
            "needtosendWithoutComment must be bool",
        )

    def test_delete_preserves_common_field_error_order(self) -> None:
        """삭제 입력도 기존 공통 필드 오류 순서를 유지하는지 확인합니다."""

        serializer = DroneNotificationTargetMappingDeleteSerializer(
            data={"lineId": "L1"}
        )

        self.assertFalse(serializer.is_valid())
        self.assertEqual(
            str(serializer.errors["non_field_errors"][0]),
            "targetUserSdwtProd is required",
        )


class DroneEarlyInformServiceTests(TestCase):
    """DroneEarlyInform 설정 서비스의 삭제 경계를 검증합니다."""

    def test_delete_returns_pre_delete_snapshot(self) -> None:
        """삭제 후에도 감사 로그용 이전 상태의 ID가 보존되는지 확인합니다."""

        entry = DroneEarlyInform.objects.create(
            line_id="L1",
            main_step="STEP1",
            custom_end_step="STEP2",
            updated_by="tester",
        )
        entry_id = entry.id

        previous_entry = services.delete_early_inform_entry(entry_id=entry_id)

        self.assertEqual(previous_entry.id, entry_id)
        self.assertEqual(previous_entry.line_id, "L1")
        self.assertEqual(previous_entry.main_step, "STEP1")
        self.assertEqual(previous_entry.custom_end_step, "STEP2")
        self.assertFalse(DroneEarlyInform.objects.filter(id=entry_id).exists())


class DroneSopPop3ParsingTestsPart1(TestCase):
    """DroneSopPop3ParsingTests 분리 회귀 테스트 1부입니다."""

    def test_build_drone_sop_row_parses_html_data_tag(self) -> None:
        """data 태그에서 필드를 추출하는지 확인합니다."""
        html = """
        <html><body>
          <data>
            <line_id>L1</line_id>
            <sdwt_prod>SDWT</sdwt_prod>
            <sample_type>NORMAL</sample_type>
            <sample_group>G1</sample_group>
            <eqp_id>EQP1</eqp_id>
            <chamber_ids>1,2</chamber_ids>
            <lot_id>LOT.1</lot_id>
            <proc_id>P</proc_id>
            <ppid>PP</ppid>
            <main_step>MS</main_step>
            <metro_current_step>ST003</metro_current_step>
            <metro_steps>ST001,ST002,ST003</metro_steps>
            <metro_end_step>ST010</metro_end_step>
            <status>IN_PROGRESS</status>
            <knoxid>knox</knoxid>
            <user_sdwt_prod>dummy-prod</user_sdwt_prod>
            <comment>hello@$SETUP_EQP</comment>
            <defect_url>"https://example.com"</defect_url>
            <defect_png_url>"https://example.com/defect.png"</defect_png_url>
          </data>
        </body></html>
        """

        early_inform_map = {("dummy-prod", "MS"): "ST002"}
        _ensure_target_mapping(sdwt_prod=None, user_sdwt_prod="dummy-prod", target_user_sdwt_prod="dummy-target")
        row = build_drone_sop_row(html=html, early_inform_map=early_inform_map)
        assert row is not None

        self.assertEqual(row["line_id"], "L1")
        self.assertEqual(row["chamber_ids"], "12")
        self.assertEqual(row["knox_id"], "knox")
        self.assertEqual(row["needtosend"], 0)
        self.assertEqual(row["status"], "COMPLETE")
        self.assertIsNone(row["defect_url"])
        self.assertNotIn("defect_png_url", row)
        self.assertEqual(row["custom_end_step"], "ST002")
        self.assertEqual(row["target_user_sdwt_prod"], "dummy-target")

    def test_build_drone_sop_row_parses_defect_json_links(self) -> None:
        """defect_json과 defect_png_url에서 map metadata와 image_rows를 추출하는지 확인합니다."""
        def _image_url(*, map_file: str, selected_row: int) -> str:
            return (
                "https://app.nyms.abc.net/map/api/map-image/v3/defect-map"
                f"?file={map_file}&amp;selected_row={selected_row}&amp;profileid=DEFAULT"
            )

        map_url_a = "https://app.nyms.abc.net/map/api/mapg/map?dtype=PQ&file=abc_df.parquet&mtype=DEFECT&signin_yn=y"
        map_url_b = "https://app.nyms.abc.net/map/api/mapg/map?dtype=PQ&file=other_df.parquet&mtype=DEFECT&signin_yn=y"
        defect_png_urls = ",".join(
            [
                _image_url(map_file="abc_df.parquet", selected_row=0),
                _image_url(map_file="abc_df.parquet", selected_row=1),
                _image_url(map_file="abc_df.parquet", selected_row=2),
                _image_url(map_file="other_df.parquet", selected_row=3),
            ]
        )
        defect_json = json.dumps(
            [
                {
                    "LINE_ID": "L1",
                    "PROC_ID": "P1",
                    "ROOT_LOT_ID": "ROOT.1",
                    "LOT_ID": "LOT.1",
                    "STEP_SEQ": "ST001",
                    "STEP_DESC": "Desc 1",
                    "DEFECT_MAP_URL": map_url_a,
                },
                {
                    "STEP_SEQ": "ST002",
                    "STEP_DESC": "Desc 2",
                    "DEFECT_MAP_URL": map_url_b,
                },
            ]
        ).replace("&", "&amp;")
        html = f"""
        <html><body>
          <data>
            <lot_id>LOT.1</lot_id>
            <defect_png_url>{defect_png_urls}</defect_png_url>
            <defect_json>{defect_json}</defect_json>
          </data>
        </body></html>
        """

        row = build_drone_sop_row(html=html, early_inform_map={})
        assert row is not None

        defect_entries = json.loads(str(row["defect_url"]))
        self.assertEqual(
            defect_entries,
            [
                {
                    "map_url": map_url_a,
                    "line_id": "L1",
                    "proc_id": "P1",
                    "root_lot_id": "ROOT.1",
                    "lot_id": "LOT.1",
                    "step_seq": "ST001",
                    "step_desc": "Desc 1",
                    "map_file": "abc_df.parquet",
                    "image_rows": [0, 1, 2],
                    "label": "ST001",
                },
                {
                    "map_url": map_url_b,
                    "step_seq": "ST002",
                    "step_desc": "Desc 2",
                    "map_file": "other_df.parquet",
                    "image_rows": [3],
                    "label": "ST002",
                },
            ],
        )

    @override_settings(
        DRONE_CTTTM_TABLE_NAME="ctttm_table",
        DRONE_CTTTM_BASE_URL="https://ctttm.example.local/view?mode=detail",
    )
    @patch("api.drone.services.jira.ctttm.selectors.load_drone_sop_ctttm_latest_workorders_by_eqp_ids")
    def test_build_drone_sop_row_enriches_ctttm_urls(self, mock_load_workorders: Mock) -> None:
        """POP3 row 생성 시 CTTTM URL을 함께 계산하는지 확인합니다."""

        mock_load_workorders.return_value = {
            "EQP1-1": {"eqp_id": "EQP1-1", "workorder_id": "WO-1", "line_id": "L1"},
            "EQP1-2": {"eqp_id": "EQP1-2", "workorder_id": "WO-2", "line_id": "L1"},
        }
        html = """
        <html><body>
          <data>
            <line_id>L1</line_id>
            <eqp_id>EQP1</eqp_id>
            <chamber_ids>1,2</chamber_ids>
            <lot_id>LOT.1</lot_id>
            <main_step>MS</main_step>
          </data>
        </body></html>
        """

        row = build_drone_sop_row(html=html, early_inform_map={})
        assert row is not None

        self.assertEqual(
            row["ctttm_urls"],
            [
                {
                    "eqp_id": "EQP1-1",
                    "url": "https://ctttm.example.local/view?mode=detail&wono=WO-1&lineId=L1",
                },
                {
                    "eqp_id": "EQP1-2",
                    "url": "https://ctttm.example.local/view?mode=detail&wono=WO-2&lineId=L1",
                },
            ],
        )
        mock_load_workorders.assert_called_once_with(
            eqp_ids=["EQP1-1", "EQP1-2"],
            ctttm_table="ctttm_table",
        )

    @override_settings(
        DRONE_CTTTM_TABLE_NAME="ctttm_table",
        DRONE_CTTTM_BASE_URL="https://ctttm.example.local/view",
    )
    @patch("api.drone.services.jira.ctttm.selectors.load_drone_sop_ctttm_latest_workorders_by_eqp_ids")
    def test_build_drone_sop_row_keeps_row_when_ctttm_lookup_fails(self, mock_load_workorders: Mock) -> None:
        """CTTTM 조회 실패 시에도 POP3 row 생성은 유지합니다."""

        mock_load_workorders.side_effect = RuntimeError("ctttm unavailable")
        html = """
        <data>
          <line_id>L1</line_id>
          <eqp_id>EQP1</eqp_id>
          <chamber_ids>1</chamber_ids>
          <lot_id>LOT.1</lot_id>
          <main_step>MS</main_step>
        </data>
        """

        row = build_drone_sop_row(html=html, early_inform_map={})
        assert row is not None

        self.assertEqual(row["eqp_id"], "EQP1")
        self.assertNotIn("ctttm_urls", row)

    def test_build_drone_sop_row_skips_no_data_defect_map_url(self) -> None:
        """DEFECT_MAP_URL이 No data placeholder이면 해당 defect step을 제외합니다."""

        valid_map_url = "https://example.com/map/api/mapg/map?file=valid_df.parquet"
        defect_json = json.dumps(
            [
                {"STEP_SEQ": "ST001", "DEFECT_MAP_URL": "No data"},
                {"STEP_SEQ": "ST002", "DEFECT_MAP_URL": "https://No Data"},
                {"STEP_SEQ": "ST003", "DEFECT_MAP_URL": valid_map_url},
            ]
        )
        html = f"""
        <html><body>
          <data>
            <lot_id>LOT.1</lot_id>
            <defect_json>{defect_json}</defect_json>
          </data>
        </body></html>
        """

        row = build_drone_sop_row(html=html, early_inform_map={})
        assert row is not None

        defect_entries = json.loads(str(row["defect_url"]))
        self.assertEqual(len(defect_entries), 1)
        self.assertEqual(defect_entries[0]["step_seq"], "ST003")
        self.assertEqual(defect_entries[0]["map_url"], valid_map_url)

    def test_build_drone_sop_row_uses_operator_id_when_knox_and_user_missing(self) -> None:
        """knox_id/user_sdwt_prod 누락 시 operator_id를 user_sdwt_prod로 사용합니다."""
        html = """
        <data>
          <operator_id>EARSAUTO</operator_id>
          <comment>system-comment</comment>
        </data>
        """

        row = build_drone_sop_row(html=html, early_inform_map={})
        assert row is not None
        self.assertEqual(row["knox_id"], "System")
        self.assertEqual(row["user_sdwt_prod"], "EARSAUTO")

    def test_build_drone_sop_row_treats_literal_none_user_sdwt_prod_as_missing(self) -> None:
        """user_sdwt_prod 문자열 None은 누락값으로 처리합니다."""
        html = """
        <data>
          <operator_id>EARSAUTO</operator_id>
          <user_sdwt_prod>None</user_sdwt_prod>
          <comment>system-comment</comment>
        </data>
        """

        row = build_drone_sop_row(html=html, early_inform_map={})
        assert row is not None
        self.assertEqual(row["knox_id"], "System")
        self.assertEqual(row["user_sdwt_prod"], "EARSAUTO")

    def test_build_drone_sop_row_cleans_operator_id_markup_and_quotes(self) -> None:
        """operator_id의 HTML 태그와 따옴표를 제거해 저장합니다."""
        html = """
        <data>
          <operator_id><span class="keyword">EARS</span>"AUTO"</operator_id>
          <comment>system-comment</comment>
        </data>
        """

        row = build_drone_sop_row(html=html, early_inform_map={})
        assert row is not None
        self.assertEqual(row["knox_id"], "System")
        self.assertEqual(row["user_sdwt_prod"], "EARSAUTO")

    def test_build_drone_sop_row_maps_rpa_operator_id(self) -> None:
        """operator_id에 .rpa가 포함되면 user_sdwt_prod를 RPA로 저장합니다."""
        html = """
        <data>
          <operator_id>dummy.rpa.operator</operator_id>
          <comment>system-comment</comment>
        </data>
        """

        row = build_drone_sop_row(html=html, early_inform_map={})
        assert row is not None
        self.assertEqual(row["knox_id"], "System")
        self.assertEqual(row["user_sdwt_prod"], "RPA")

    def test_build_drone_sop_row_falls_back_to_system_when_operator_id_missing(self) -> None:
        """operator_id도 없으면 기존처럼 System 소속 fallback을 사용합니다."""
        html = """
        <data>
          <comment>abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890</comment>
        </data>
        """

        row = build_drone_sop_row(html=html, early_inform_map={})
        assert row is not None
        self.assertEqual(row["knox_id"], "System")
        self.assertEqual(row["user_sdwt_prod"], "System")

    @override_settings(
        DRONE_SOP_USER_SDWT_OVERRIDE_MAP=(
            '{"auto_skew":"AUTO_SKEW","ssb fullauto":"SSB FULLAUTO","isop":"ISOP"}'
        ),
    )
    def test_build_drone_sop_row_overrides_user_sdwt_prod_from_automation_comment(self) -> None:
        """자동화 comment 키워드는 user_sdwt_prod만 override합니다."""
        cases = [
            ("AUTO_SKEW", "AUTO_SKEW"),
            ("SSB FULLAUTO", "SSB FULLAUTO"),
            ("ISOP", "ISOP"),
            ("  auto_skew  $@$ reserved", "AUTO_SKEW"),
            ("manual comment $@$ AUTO_SKEW", "AUTO_SKEW"),
            ("prefix AUTO_SKEW suffix", "AUTO_SKEW"),
            ("예약 요청: ssb fullauto 알림", "SSB FULLAUTO"),
            ("manual isop fallback", "ISOP"),
        ]

        for comment, expected in cases:
            with self.subTest(comment=comment):
                html = f"""
                <data>
                  <operator_id>EARSAUTO</operator_id>
                  <comment>{comment}</comment>
                </data>
                """

                row = build_drone_sop_row(html=html, early_inform_map={})
                assert row is not None
                self.assertEqual(row["knox_id"], "System")
                self.assertEqual(row["user_sdwt_prod"], expected)

    def test_build_drone_sop_row_keeps_user_sdwt_prod_without_automation_comment(self) -> None:
        """자동화 comment 키워드가 없으면 기존 user_sdwt_prod 값을 유지합니다."""
        html = """
        <data>
          <knox_id>USER1</knox_id>
          <user_sdwt_prod>ORIGINAL_SDWT</user_sdwt_prod>
          <comment>normal comment</comment>
        </data>
        """

        row = build_drone_sop_row(html=html, early_inform_map={})
        assert row is not None
        self.assertEqual(row["knox_id"], "USER1")
        self.assertEqual(row["user_sdwt_prod"], "ORIGINAL_SDWT")

    @override_settings(DRONE_SOP_USER_SDWT_OVERRIDE_MAP='{"auto_skew":"AUTO_SKEW"}')
    def test_build_drone_sop_row_overrides_existing_user_sdwt_prod_from_comment(self) -> None:
        """자동화 comment 키워드가 있으면 기존 user_sdwt_prod도 override합니다."""
        html = """
        <data>
          <knox_id>USER1</knox_id>
          <user_sdwt_prod>ORIGINAL_SDWT</user_sdwt_prod>
          <comment>prefix AUTO_SKEW suffix</comment>
        </data>
        """

        row = build_drone_sop_row(html=html, early_inform_map={})
        assert row is not None
        self.assertEqual(row["knox_id"], "USER1")
        self.assertEqual(row["user_sdwt_prod"], "AUTO_SKEW")

    @override_settings(DRONE_SOP_USER_SDWT_OVERRIDE_MAP='{"custom-auto":"CUSTOM_AUTO"}')
    def test_build_drone_sop_row_uses_settings_comment_override_map(self) -> None:
        """settings override map이 comment 기반 user_sdwt_prod에 반영됩니다."""
        html = """
        <data>
          <operator_id>EARSAUTO</operator_id>
          <comment>prefix custom-auto suffix</comment>
        </data>
        """

        row = build_drone_sop_row(html=html, early_inform_map={})
        assert row is not None
        self.assertEqual(row["knox_id"], "System")
        self.assertEqual(row["user_sdwt_prod"], "CUSTOM_AUTO")

    def test_build_drone_sop_row_applies_needtosend_db_rule(self) -> None:
        """DB 규칙 키워드가 comment에 포함되면 needtosend가 1인지 확인합니다."""
        html = """
        <data>
          <sample_type>NORMAL</sample_type>
          <user_sdwt_prod>prod-1</user_sdwt_prod>
          <comment>hello $abc suffix</comment>
        </data>
        """
        _ensure_target_mapping(sdwt_prod=None, user_sdwt_prod="prod-1", target_user_sdwt_prod="target-1")
        _upsert_target(
            target_user_sdwt_prod="target-1",
            needtosend_comment_last_at="$abc",
            needtosend_ignore_sample_type=False,
            needtosend_enabled=True,
        )
        row = build_drone_sop_row(html=html, early_inform_map={})
        assert row is not None
        self.assertEqual(row["needtosend"], 1)

    def test_build_drone_sop_row_needtosend_zero_when_db_rule_inactive(self) -> None:
        """DB 규칙이 비활성화되면 needtosend가 0인지 확인합니다."""
        html = """
        <data>
          <sample_type>NORMAL</sample_type>
          <user_sdwt_prod>prod-inactive</user_sdwt_prod>
          <comment>hello@$inactive</comment>
        </data>
        """
        _ensure_target_mapping(
            sdwt_prod=None,
            user_sdwt_prod="prod-inactive",
            target_user_sdwt_prod="target-inactive",
        )
        _upsert_target(
            target_user_sdwt_prod="target-inactive",
            needtosend_comment_last_at="$inactive",
            needtosend_ignore_sample_type=False,
            needtosend_enabled=False,
        )

        row = build_drone_sop_row(html=html, early_inform_map={})
        assert row is not None
        self.assertEqual(row["needtosend"], 0)

    def test_build_drone_sop_row_reserves_matching_mapping_without_comment(self) -> None:
        """지정 조합 정책이 켜지면 Comment 키워드가 없어도 예약합니다."""

        html = """
        <data>
          <sample_type>NORMAL</sample_type>
          <sdwt_prod>A</sdwt_prod>
          <user_sdwt_prod>EARSAUTO</user_sdwt_prod>
          <comment>일반 작업 요청</comment>
        </data>
        """
        _ensure_target_mapping(
            sdwt_prod="A",
            user_sdwt_prod="EARSAUTO",
            target_user_sdwt_prod="target-a",
            needtosend_without_comment=True,
        )
        _upsert_target(
            target_user_sdwt_prod="target-a",
            needtosend_comment_last_at="$SETUP_EQP",
            needtosend_ignore_sample_type=False,
            needtosend_enabled=True,
        )

        row = build_drone_sop_row(html=html, early_inform_map={})

        assert row is not None
        self.assertEqual(row["target_user_sdwt_prod"], "target-a")
        self.assertEqual(row["needtosend"], 1)

class DroneSopPop3ParsingTestsPart2(TestCase):
    """DroneSopPop3ParsingTests 분리 회귀 테스트 2부입니다."""

    def test_build_drone_sop_row_allows_commentless_mapping_without_keyword(self) -> None:
        """Comment 생략 지정 조합만 사용하는 target은 빈 키워드로도 예약합니다."""

        html = """
        <data>
          <sample_type>NORMAL</sample_type>
          <sdwt_prod>A</sdwt_prod>
          <user_sdwt_prod>EARSAUTO</user_sdwt_prod>
        </data>
        """
        _ensure_target_mapping(
            sdwt_prod="A",
            user_sdwt_prod="EARSAUTO",
            target_user_sdwt_prod="target-a",
            needtosend_without_comment=True,
        )
        _upsert_target(
            target_user_sdwt_prod="target-a",
            needtosend_comment_last_at="",
            needtosend_ignore_sample_type=False,
            needtosend_enabled=True,
        )

        row = build_drone_sop_row(html=html, early_inform_map={})

        assert row is not None
        self.assertEqual(row["needtosend"], 1)

    def test_build_drone_sop_row_keeps_comment_rule_for_other_mapping(self) -> None:
        """정책이 꺼진 다른 지정 조합은 기존 Comment 키워드 규칙을 유지합니다."""

        html = """
        <data>
          <sample_type>NORMAL</sample_type>
          <sdwt_prod>A</sdwt_prod>
          <user_sdwt_prod>OTHER</user_sdwt_prod>
          <comment>일반 작업 요청</comment>
        </data>
        """
        _ensure_target_mapping(
            sdwt_prod="A",
            user_sdwt_prod="OTHER",
            target_user_sdwt_prod="target-a",
        )
        _upsert_target(
            target_user_sdwt_prod="target-a",
            needtosend_comment_last_at="$SETUP_EQP",
            needtosend_ignore_sample_type=False,
            needtosend_enabled=True,
        )

        row = build_drone_sop_row(html=html, early_inform_map={})

        assert row is not None
        self.assertEqual(row["needtosend"], 0)

    def test_build_drone_sop_row_commentless_mapping_respects_sample_type_rule(self) -> None:
        """Comment 생략 정책도 ENGR_PRODUCTION 제외 규칙을 우회하지 않습니다."""

        html = """
        <data>
          <sample_type>ENGR_PRODUCTION</sample_type>
          <sdwt_prod>A</sdwt_prod>
          <user_sdwt_prod>EARSAUTO</user_sdwt_prod>
          <comment>일반 작업 요청</comment>
        </data>
        """
        _ensure_target_mapping(
            sdwt_prod="A",
            user_sdwt_prod="EARSAUTO",
            target_user_sdwt_prod="target-a",
            needtosend_without_comment=True,
        )
        _upsert_target(
            target_user_sdwt_prod="target-a",
            needtosend_comment_last_at="$SETUP_EQP",
            needtosend_ignore_sample_type=False,
            needtosend_enabled=True,
        )

        row = build_drone_sop_row(html=html, early_inform_map={})

        assert row is not None
        self.assertEqual(row["needtosend"], 0)

    def test_build_drone_sop_row_commentless_mapping_respects_master_switch(self) -> None:
        """Comment 생략 정책도 비활성 자동 예약 규칙을 우회하지 않습니다."""

        html = """
        <data>
          <sample_type>NORMAL</sample_type>
          <sdwt_prod>A</sdwt_prod>
          <user_sdwt_prod>EARSAUTO</user_sdwt_prod>
        </data>
        """
        _ensure_target_mapping(
            sdwt_prod="A",
            user_sdwt_prod="EARSAUTO",
            target_user_sdwt_prod="target-a",
            needtosend_without_comment=True,
        )
        _upsert_target(
            target_user_sdwt_prod="target-a",
            needtosend_comment_last_at="$SETUP_EQP",
            needtosend_ignore_sample_type=True,
            needtosend_enabled=False,
        )

        row = build_drone_sop_row(html=html, early_inform_map={})

        assert row is not None
        self.assertEqual(row["needtosend"], 0)

    def test_build_drone_sop_row_needtosend_zero_when_mapping_missing(self) -> None:
        """매핑이 없으면 needtosend가 0인지 확인합니다."""
        html = """
        <data>
          <sample_type>NORMAL</sample_type>
          <user_sdwt_prod>no-map</user_sdwt_prod>
          <comment>hello@$SETUP_EQP</comment>
        </data>
        """
        row = build_drone_sop_row(html=html, early_inform_map={})
        assert row is not None
        self.assertEqual(row["needtosend"], 0)
        self.assertIsNone(row["target_user_sdwt_prod"])

    def test_build_drone_sop_row_needtosend_zero_for_engr_production(self) -> None:
        """ENGR_PRODUCTION 샘플 타입의 needtosend가 0인지 확인합니다."""
        html = """
        <data>
          <sample_type>ENGR_PRODUCTION</sample_type>
          <user_sdwt_prod>prod-2</user_sdwt_prod>
          <comment>hello@$SETUP_EQP</comment>
        </data>
        """
        _ensure_target_mapping(sdwt_prod=None, user_sdwt_prod="prod-2", target_user_sdwt_prod="target-2")
        row = build_drone_sop_row(html=html, early_inform_map={})
        assert row is not None
        self.assertEqual(row["needtosend"], 0)
