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

class DroneSopTargetAdminTests(TestCase):
    """Line Dashboard 관리자 전용 DroneSopTarget 관리 API를 검증합니다."""

    def setUp(self) -> None:
        """테스트용 앱 관리자와 일반 사용자를 준비합니다."""

        User = get_user_model()
        self.admin_user = User.objects.create_user(
            sabun="S72000",
            password="test-password",
            knox_id="knox-72000",
        )
        self.user = User.objects.create_user(
            sabun="S72001",
            password="test-password",
            knox_id="knox-72001",
        )
        authority = User.objects.create_superuser(
            sabun="S72002",
            password="test-password",
            knox_id="knox-72002",
        )
        for scope_key, role in (("portal", "user"), ("line-dashboard", "admin")):
            _payload, status_code = account_services.decide_user_access(
                actor=authority,
                user_id=self.admin_user.id,
                scope_key=scope_key,
                action="grant",
                reason="Drone target 관리자 테스트 권한 부여",
                role=role,
            )
            self.assertEqual(status_code, 200)
        self.endpoint = reverse("line-dashboard-admin-drone-targets")

    def _json(self, payload: dict[str, object]) -> str:
        """JSON 요청 본문을 생성합니다."""

        return json.dumps(payload)

    def test_admin_drone_targets_requires_app_admin(self) -> None:
        """target 관리 API가 Line Dashboard admin만 허용되는지 확인합니다."""

        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, 401)

        self.client.force_login(self.user)
        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, 403)

    def test_admin_drone_targets_crud_flow(self) -> None:
        """target 생성, 조회, 수정, 삭제 흐름이 동작하는지 확인합니다."""

        self.client.force_login(self.admin_user)
        response = self.client.post(
            self.endpoint,
            data=self._json({"lineId": "L1", "targetUserSdwtProd": "TARGET_A"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        created = response.json()["target"]
        self.assertEqual(created["lineId"], "L1")
        self.assertEqual(created["targetUserSdwtProd"], "TARGET_A")

        response = self.client.patch(
            self.endpoint,
            data=self._json(
                {
                    "id": created["id"],
                    "lineId": "L2",
                    "targetUserSdwtProd": "TARGET_B",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        updated = response.json()["target"]
        self.assertEqual(updated["lineId"], "L2")
        self.assertEqual(updated["targetUserSdwtProd"], "TARGET_B")

        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["rowCount"], 1)
        self.assertEqual(response.json()["targets"][0]["targetUserSdwtProd"], "TARGET_B")

        response = self.client.delete(
            self.endpoint,
            data=self._json({"id": created["id"]}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["deleted"])
        self.assertFalse(DroneSopTarget.objects.filter(id=created["id"]).exists())

    def test_admin_drone_targets_rejects_duplicate_target(self) -> None:
        """target 이름 중복을 대소문자 비구분으로 차단하는지 확인합니다."""

        DroneSopTarget.objects.create(line_id="L1", target_user_sdwt_prod="TARGET_A")
        self.client.force_login(self.admin_user)

        response = self.client.post(
            self.endpoint,
            data=self._json({"lineId": "L2", "targetUserSdwtProd": "target_a"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"], "target already exists")

    def test_admin_drone_targets_validates_and_normalizes_write_payloads(self) -> None:
        """관리자 쓰기 입력을 serializer가 검증하고 공백을 정규화하는지 확인합니다."""

        self.client.force_login(self.admin_user)

        missing_line_response = self.client.post(
            self.endpoint,
            data=self._json({"targetUserSdwtProd": "TARGET_A"}),
            content_type="application/json",
        )
        self.assertEqual(missing_line_response.status_code, 400)
        self.assertEqual(missing_line_response.json()["error"], "lineId is required")

        created_response = self.client.post(
            self.endpoint,
            data=self._json(
                {
                    "lineId": " L1 ",
                    "targetUserSdwtProd": " TARGET_A ",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(created_response.status_code, 201)
        created = created_response.json()["target"]
        self.assertEqual(created["lineId"], "L1")
        self.assertEqual(created["targetUserSdwtProd"], "TARGET_A")

        invalid_id_response = self.client.patch(
            self.endpoint,
            data=self._json(
                {
                    "id": "invalid",
                    "lineId": "L1",
                    "targetUserSdwtProd": "TARGET_B",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(invalid_id_response.status_code, 400)
        self.assertEqual(invalid_id_response.json()["error"], "id is required")

    def test_admin_drone_targets_returns_related_counts(self) -> None:
        """target 관리 목록이 연결 설정 count를 함께 반환하는지 확인합니다."""

        target = DroneSopTarget.objects.create(line_id="L1", target_user_sdwt_prod="TARGET_A")
        DroneSopTargetMapping.objects.create(sdwt_prod="SDWT_A", user_sdwt_prod="USER_A", target=target)
        DroneSopTargetChannelConfig.objects.create(target=target, channel=DroneSopTargetChannelConfig.Channels.JIRA)
        DroneSopNeedToSendRule.objects.create(target=target, enabled=True, comment_keyword="go")
        DroneSopTargetRecipient.objects.create(
            target=target,
            channel=DroneSopTargetRecipient.Channels.MAIL,
            user=self.user,
        )
        sop = DroneSOP.objects.create(
            line_id="L1",
            target_user_sdwt_prod="TARGET_A",
            eqp_id="EQP-A",
            chamber_ids="CH-A",
            lot_id="LOT-A",
            main_step="STEP-A",
        )
        DroneSopTargetDispatch.objects.create(
            sop=sop,
            target=target,
            target_code_snapshot="TARGET_A",
        )

        self.client.force_login(self.admin_user)
        response = self.client.get(self.endpoint)

        self.assertEqual(response.status_code, 200)
        row = response.json()["targets"][0]
        self.assertEqual(row["mappingCount"], 1)
        self.assertEqual(row["recipientCount"], 1)
        self.assertEqual(row["channelConfigCount"], 1)
        self.assertEqual(row["dispatchCount"], 1)
        self.assertTrue(row["hasNeedToSendRule"])


class DroneSopJsonTargetSeedTests(TestCase):
    """JSON row 기반 Drone SOP 알림 초기 세팅을 검증합니다."""

    def setUp(self) -> None:
        """테스트용 account 소속과 사용자 pool을 준비합니다."""

        User = get_user_model()
        account_services.ensure_affiliation_option(
            department="Dept",
            line="LSEED",
            user_sdwt_prod="SEED_A",
        )
        self.user = User.objects.create_user(
            sabun="S72001",
            password="test-password",
            knox_id="seed-user",
            email="seed-user@example.com",
        )
        _set_current_affiliation(self.user, department="Dept", line="LSEED", user_sdwt_prod="SEED_A")
        account_services.sync_external_affiliations(
            records=[
                {
                    "knox_id": "seed-external",
                    "department": "ExtDept",
                    "user_sdwt_prod": "SEED_A",
                    "source_updated_at": timezone.now(),
                }
            ]
        )

    def test_seed_from_rows_resets_before_rebuild(self) -> None:
        """JSON row 기반 seed는 기존 알림 설정을 초기화한 뒤 다시 생성합니다."""

        stale_target = _upsert_target(line_id="OLD_LINE", target_user_sdwt_prod="OLD_TARGET")
        DroneSopTargetMapping.objects.create(
            sdwt_prod="OLD",
            user_sdwt_prod="OLD",
            target=stale_target,
        )
        DroneSopTargetChannelConfig.objects.create(
            target=stale_target,
            channel=DroneSopTargetChannelConfig.Channels.MAIL,
            enabled=False,
            template_key="old-template",
        )
        DroneSopTargetRecipient.objects.create(
            target=stale_target,
            channel=DroneSopTargetRecipient.Channels.MAIL,
            user=self.user,
        )
        stale_sop = _create_drone_sop(
            line_id="OLD_LINE",
            target_user_sdwt_prod="OLD_TARGET",
        )
        stale_dispatch, _ = DroneSopTargetDispatch.objects.get_or_create(
            sop=stale_sop,
            target_code_snapshot="OLD_TARGET",
            defaults={"target": stale_target},
        )
        DroneSopDelivery.objects.get_or_create(
            sop=stale_sop,
            dispatch=stale_dispatch,
            channel=DroneSopDelivery.Channels.MAIL,
        )

        seed_rows = [
            {
                "department": "Dept",
                "line": "LSEED",
                "target_user_sdwt_prod": "SEED_A",
                "recipient_user_sdwt_prod": "SEED_A",
            }
        ]
        first_result = services.seed_drone_sop_notification_defaults_from_rows(rows=seed_rows)

        target = DroneSopTarget.objects.get(target_user_sdwt_prod="SEED_A")
        self.assertEqual(target.line_id, "LSEED")
        self.assertEqual(first_result.targets_created, 1)
        self.assertEqual(first_result.targets_deleted, 1)
        self.assertEqual(first_result.mappings_deleted, 1)
        self.assertEqual(first_result.channel_configs_deleted, 1)
        self.assertEqual(first_result.recipients_deleted, 1)
        self.assertEqual(first_result.sop_rows_deleted, 1)
        self.assertGreaterEqual(first_result.dispatches_deleted, 1)
        self.assertGreaterEqual(first_result.deliveries_deleted, 1)
        self.assertFalse(DroneSopTarget.objects.filter(target_user_sdwt_prod="OLD_TARGET").exists())
        self.assertFalse(DroneSOP.objects.filter(target_user_sdwt_prod="OLD_TARGET").exists())
        self.assertFalse(DroneSopTargetDispatch.objects.filter(target_code_snapshot="OLD_TARGET").exists())
        self.assertFalse(DroneSopDelivery.objects.exists())
        self.assertTrue(
            DroneSopTargetMapping.objects.filter(
                sdwt_prod="SEED_A",
                user_sdwt_prod="SEED_A",
                target=target,
            ).exists()
        )

        jira_config = target.channel_configs.get(channel=DroneSopTargetChannelConfig.Channels.JIRA)
        messenger_config = target.channel_configs.get(channel=DroneSopTargetChannelConfig.Channels.MESSENGER)
        mail_config = target.channel_configs.get(channel=DroneSopTargetChannelConfig.Channels.MAIL)
        self.assertFalse(jira_config.enabled)
        self.assertTrue(messenger_config.enabled)
        self.assertTrue(mail_config.enabled)
        self.assertEqual(jira_config.template_key, "common")
        self.assertEqual(messenger_config.template_key, "common")
        self.assertEqual(mail_config.template_key, "common")
        self.assertFalse(target.needtosend_rule.enabled)
        self.assertEqual(target.needtosend_rule.comment_keyword, "$SETUP_EQP")

        self.assertEqual(
            selectors.list_mail_receiver_emails_for_user_sdwt_prod(
                line_id="LSEED",
                user_sdwt_prod="SEED_A",
            ),
            ["seed-user@example.com"],
        )
        self.assertEqual(
            selectors.list_messenger_receiver_knox_ids_for_user_sdwt_prod(
                line_id="LSEED",
                user_sdwt_prod="SEED_A",
            ),
            ["seed-user"],
        )

        second_result = services.seed_drone_sop_notification_defaults_from_rows(rows=seed_rows)
        self.assertEqual(second_result.targets_deleted, 1)
        self.assertEqual(second_result.targets_created, 1)
        self.assertEqual(second_result.mappings_created, 1)
        self.assertEqual(second_result.channel_configs_created, 3)
        self.assertEqual(second_result.needtosend_rules_created, 1)
        self.assertEqual(second_result.recipients_created, 2)

    def test_seed_from_rows_uses_department_filter_and_creates_defaults(self) -> None:
        """JSON형 row는 canonical target/recipient 조합으로 수신인을 자동 생성합니다."""

        account_services.sync_external_affiliations(
            records=[
                {
                    "knox_id": "json-external",
                    "department": "Dept",
                    "user_sdwt_prod": "SEED_A",
                    "source_updated_at": timezone.now(),
                },
                {
                    "knox_id": "other-dept-external",
                    "department": "OtherDept",
                    "user_sdwt_prod": "SEED_A",
                    "source_updated_at": timezone.now(),
                },
            ]
        )

        result = services.seed_drone_sop_notification_defaults_from_rows(
            rows=[
                {
                    "department": "Dept",
                    "line": "LJSON",
                    "target_user_sdwt_prod": "SEED_A",
                    "recipient_user_sdwt_prod": "SEED_A",
                }
            ]
        )

        target = DroneSopTarget.objects.get(target_user_sdwt_prod="SEED_A")
        self.assertEqual(target.line_id, "LJSON")
        self.assertEqual(result.targets_created, 1)
        self.assertEqual(result.targets_deleted, 0)
        self.assertEqual(result.mappings_created, 1)
        self.assertEqual(result.channel_configs_created, 3)
        self.assertEqual(result.needtosend_rules_created, 1)
        self.assertEqual(
            selectors.list_mail_receiver_emails_for_user_sdwt_prod(
                line_id="LJSON",
                user_sdwt_prod="SEED_A",
            ),
            ["seed-user@example.com", "json-external@samsung.com"],
        )
        self.assertEqual(
            selectors.list_messenger_receiver_knox_ids_for_user_sdwt_prod(
                line_id="LJSON",
                user_sdwt_prod="SEED_A",
            ),
            ["seed-user", "json-external"],
        )

    def test_seed_from_rows_rejects_legacy_target_alias_before_reset(self) -> None:
        """구형 target 별칭은 기존 운영 row를 지우기 전에 거부합니다."""

        stale_target = _upsert_target(
            line_id="OLD_LINE",
            target_user_sdwt_prod="OLD_TARGET",
        )

        with self.assertRaisesRegex(ValueError, "target_user_sdwt_prod"):
            services.seed_drone_sop_notification_defaults_from_rows(
                rows=[
                    {
                        "department": "Dept",
                        "line": "LJSON",
                        "user_sdwt_prod": "SEED_A",
                    }
                ]
            )

        self.assertTrue(DroneSopTarget.objects.filter(id=stale_target.id).exists())

    def test_seed_from_rows_applies_explicit_target_configs_and_mappings(self) -> None:
        """확장 JSON row는 target/channel/mapping/rule을 명시값으로 생성합니다."""

        result = services.seed_drone_sop_notification_defaults_from_rows(
            rows=[
                {
                    "department": "Dept",
                    "line": "LJSON",
                    "target_user_sdwt_prod": "TARGET_A",
                    "recipient_user_sdwt_prod": "SEED_A",
                    "channels": {
                        "jira": {
                            "enabled": True,
                            "template_key": "jira-custom",
                            "jira_project_key": "DRONE",
                        },
                        "messenger": {
                            "enabled": False,
                            "template_key": "msg-custom",
                            "chatroom_id": 12345,
                            "force_new_chatroom": False,
                        },
                        "mail": {
                            "enabled": True,
                            "template_key": "mail-custom",
                        },
                    },
                    "mappings": [
                        {
                            "sdwt_prod": "SOURCE_SDWT",
                            "user_sdwt_prod": "SOURCE_USER",
                        },
                        {
                            "sdwt_prod": "SOURCE_ONLY",
                            "user_sdwt_prod": "",
                        },
                    ],
                    "needtosend_rule": {
                        "enabled": True,
                        "comment_keyword": "$AUTO_SEND",
                        "ignore_sample_type": True,
                    },
                }
            ]
        )

        target = DroneSopTarget.objects.get(target_user_sdwt_prod="TARGET_A")
        self.assertEqual(target.line_id, "LJSON")
        self.assertEqual(result.targets_created, 1)
        self.assertEqual(result.mappings_created, 2)
        self.assertEqual(result.channel_configs_created, 3)
        self.assertEqual(result.needtosend_rules_created, 1)

        self.assertTrue(
            DroneSopTargetMapping.objects.filter(
                target=target,
                sdwt_prod="SOURCE_SDWT",
                user_sdwt_prod="SOURCE_USER",
            ).exists()
        )
        self.assertTrue(
            DroneSopTargetMapping.objects.filter(
                target=target,
                sdwt_prod="SOURCE_ONLY",
                user_sdwt_prod__isnull=True,
            ).exists()
        )

        jira_config = target.channel_configs.get(channel=DroneSopTargetChannelConfig.Channels.JIRA)
        messenger_config = target.channel_configs.get(channel=DroneSopTargetChannelConfig.Channels.MESSENGER)
        mail_config = target.channel_configs.get(channel=DroneSopTargetChannelConfig.Channels.MAIL)
        self.assertTrue(jira_config.enabled)
        self.assertEqual(jira_config.template_key, "jira-custom")
        self.assertEqual(jira_config.jira_project_key, "DRONE")
        self.assertFalse(messenger_config.enabled)
        self.assertEqual(messenger_config.template_key, "msg-custom")
        self.assertEqual(messenger_config.chatroom_id, 12345)
        self.assertFalse(messenger_config.force_new_chatroom)
        self.assertTrue(mail_config.enabled)
        self.assertEqual(mail_config.template_key, "mail-custom")

        self.assertTrue(target.needtosend_rule.enabled)
        self.assertEqual(target.needtosend_rule.comment_keyword, "$AUTO_SEND")
        self.assertTrue(target.needtosend_rule.ignore_sample_type)
        self.assertEqual(
            selectors.list_mail_receiver_emails_for_user_sdwt_prod(
                line_id="LJSON",
                user_sdwt_prod="TARGET_A",
            ),
            ["seed-user@example.com"],
        )
        self.assertEqual(
            selectors.list_messenger_receiver_knox_ids_for_user_sdwt_prod(
                line_id="LJSON",
                user_sdwt_prod="TARGET_A",
            ),
            ["seed-user"],
        )

    def test_seed_targets_from_file_command_dry_run_rolls_back(self) -> None:
        """파일 seed command의 dry-run 옵션은 DB 변경을 롤백합니다."""

        payload = {
            "targets": [
                {
                    "department": "Dept",
                    "line": "LJSON",
                    "target_user_sdwt_prod": "SEED_A",
                    "recipient_user_sdwt_prod": "SEED_A",
                }
            ]
        }
        with NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as handle:
            json.dump(payload, handle)
            file_path = handle.name

        try:
            output = StringIO()
            call_command(
                "seed_drone_targets_from_file",
                "--file",
                file_path,
                "--dry-run",
                stdout=output,
            )
        finally:
            os.unlink(file_path)

        self.assertIn("dry-run:", output.getvalue())
        self.assertFalse(DroneSopTarget.objects.filter(target_user_sdwt_prod="SEED_A").exists())

    def test_seed_targets_from_json_rejects_legacy_target_alias(self) -> None:
        """JSON seed command는 구형 top-level target 별칭을 거부합니다."""

        payload = {
            "targets": [
                {
                    "department": "Dept",
                    "line": "LJSON",
                    "user_sdwt_prod": "SEED_A",
                }
            ]
        }
        with NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as handle:
            json.dump(payload, handle)
            file_path = handle.name

        try:
            with self.assertRaisesMessage(CommandError, "target_user_sdwt_prod"):
                call_command("seed_drone_targets_from_file", "--file", file_path)
        finally:
            os.unlink(file_path)

    def test_seed_targets_from_csv_rejects_legacy_target_alias(self) -> None:
        """CSV seed command는 구형 top-level target 별칭을 거부합니다."""

        csv_body = "\n".join(
            [
                "department,line,user_sdwt_prod,recipient_user_sdwt_prod",
                "Dept,LCSV,SEED_A,SEED_A",
            ]
        )
        with NamedTemporaryFile("w", encoding="utf-8", suffix=".csv", delete=False) as handle:
            handle.write(csv_body)
            handle.write("\n")
            file_path = handle.name

        try:
            with self.assertRaisesMessage(CommandError, "target_user_sdwt_prod"):
                call_command("seed_drone_targets_from_file", "--file", file_path)
        finally:
            os.unlink(file_path)

    def test_seed_targets_from_csv_applies_mappings_json_cell(self) -> None:
        """CSV seed command는 mappings JSON 셀의 여러 mapping을 생성합니다."""

        csv_body = "\n".join(
            [
                (
                    "department,line,target_user_sdwt_prod,recipient_user_sdwt_prod,"
                    "jira_enabled,jira_template_key,jira_project_key,"
                    "messenger_enabled,messenger_template_key,messenger_chatroom_id,"
                    "messenger_force_new_chatroom,mail_enabled,mail_template_key,"
                    "mappings,"
                    "needtosend_enabled,needtosend_comment_keyword,needtosend_ignore_sample_type"
                ),
                (
                    "Dept,LCSV,TARGET_A,SEED_A,true,jira-custom,DRONE,"
                    "false,msg-custom,12345,false,true,mail-custom,"
                    '"[{""sdwt_prod"":""SOURCE_SDWT"",""user_sdwt_prod"":""SOURCE_USER""},'
                    '{""sdwt_prod"":""SOURCE_ONLY"",""user_sdwt_prod"":""""}]",'
                    "true,$AUTO_SEND,true"
                ),
            ]
        )
        with NamedTemporaryFile("w", encoding="utf-8", suffix=".csv", delete=False) as handle:
            handle.write(csv_body)
            handle.write("\n")
            file_path = handle.name

        try:
            output = StringIO()
            call_command(
                "seed_drone_targets_from_file",
                "--file",
                file_path,
                stdout=output,
            )
        finally:
            os.unlink(file_path)

        target = DroneSopTarget.objects.get(target_user_sdwt_prod="TARGET_A")
        self.assertIn("drone CSV target seed complete:", output.getvalue())
        self.assertEqual(target.line_id, "LCSV")
        self.assertEqual(
            set(
                DroneSopTargetMapping.objects.filter(target=target).values_list(
                    "sdwt_prod",
                    "user_sdwt_prod",
                )
            ),
            {
                ("SOURCE_SDWT", "SOURCE_USER"),
                ("SOURCE_ONLY", None),
            },
        )

        jira_config = target.channel_configs.get(channel=DroneSopTargetChannelConfig.Channels.JIRA)
        messenger_config = target.channel_configs.get(channel=DroneSopTargetChannelConfig.Channels.MESSENGER)
        mail_config = target.channel_configs.get(channel=DroneSopTargetChannelConfig.Channels.MAIL)
        self.assertTrue(jira_config.enabled)
        self.assertEqual(jira_config.template_key, "jira-custom")
        self.assertEqual(jira_config.jira_project_key, "DRONE")
        self.assertFalse(messenger_config.enabled)
        self.assertEqual(messenger_config.template_key, "msg-custom")
        self.assertEqual(messenger_config.chatroom_id, 12345)
        self.assertFalse(messenger_config.force_new_chatroom)
        self.assertTrue(mail_config.enabled)
        self.assertEqual(mail_config.template_key, "mail-custom")
        self.assertTrue(target.needtosend_rule.enabled)
        self.assertEqual(target.needtosend_rule.comment_keyword, "$AUTO_SEND")
        self.assertTrue(target.needtosend_rule.ignore_sample_type)

    def test_seed_targets_from_csv_rejects_duplicate_target_rows(self) -> None:
        """CSV seed command는 같은 target의 반복 row를 오류로 처리합니다."""

        csv_body = "\n".join(
            [
                "department,line,target_user_sdwt_prod,recipient_user_sdwt_prod,mappings",
                'Dept,LCSV,TARGET_A,TARGET_A,"[{""sdwt_prod"":""SOURCE_A"",""user_sdwt_prod"":""USER_A""}]"',
                'Dept,LCSV,TARGET_A,TARGET_A,"[{""sdwt_prod"":""SOURCE_B"",""user_sdwt_prod"":""USER_B""}]"',
            ]
        )
        with NamedTemporaryFile("w", encoding="utf-8", suffix=".csv", delete=False) as handle:
            handle.write(csv_body)
            handle.write("\n")
            file_path = handle.name

        try:
            with self.assertRaisesMessage(CommandError, "duplicates target_user_sdwt_prod"):
                call_command("seed_drone_targets_from_file", "--file", file_path)
        finally:
            os.unlink(file_path)

    def test_seed_targets_from_csv_rejects_deprecated_mapping_columns(self) -> None:
        """CSV seed command는 예전 mapping 분리 컬럼을 허용하지 않습니다."""

        csv_body = "\n".join(
            [
                "department,line,target_user_sdwt_prod,mapping_sdwt_prod,mapping_user_sdwt_prod",
                "Dept,LCSV,TARGET_A,SOURCE_A,USER_A",
            ]
        )
        with NamedTemporaryFile("w", encoding="utf-8", suffix=".csv", delete=False) as handle:
            handle.write(csv_body)
            handle.write("\n")
            file_path = handle.name

        try:
            with self.assertRaisesMessage(CommandError, "mappings JSON column"):
                call_command("seed_drone_targets_from_file", "--file", file_path)
        finally:
            os.unlink(file_path)


class DroneSopDummySeedCommandTests(TestCase):
    """Drone 통합 검증용 더미 데이터 커맨드를 검증합니다."""

    def test_seed_drone_dummy_data_populates_required_tables(self) -> None:
        """더미 seed command가 Drone 기능 테스트용 주요 테이블을 채웁니다."""

        output = StringIO()

        with patch.dict(os.environ, {"ENVIRONMENT": "development", "DRONE_SEED_ALLOWED": "1"}):
            call_command(
                "seed_drone_dummy_data",
                "--prefix",
                "DTEST",
                "--reset",
                stdout=output,
            )

        self.assertIn("recipients=", output.getvalue())
        self.assertEqual(DroneSOP.objects.filter(line_id__startswith="DTEST-").count(), 11)
        self.assertEqual(
            DroneSopTarget.objects.filter(target_user_sdwt_prod__startswith="DTEST_").count(),
            4,
        )
        self.assertEqual(
            DroneSopTargetMapping.objects.filter(
                target__target_user_sdwt_prod__startswith="DTEST_",
            ).count(),
            4,
        )
        self.assertEqual(
            DroneSopTargetChannelConfig.objects.filter(
                target__target_user_sdwt_prod__startswith="DTEST_",
            ).count(),
            12,
        )
        self.assertEqual(
            DroneSopTargetRecipient.objects.filter(
                target__target_user_sdwt_prod__startswith="DTEST_",
            ).count(),
            8,
        )
        self.assertEqual(
            DroneEarlyInform.objects.filter(line_id__startswith="DTEST-").count(),
            2,
        )
        for target_name in ("DTEST_BETA", "DTEST_DELTA"):
            target = DroneSopTarget.objects.get(target_user_sdwt_prod=target_name)
            channel_keys = {
                config.channel: config.template_key
                for config in target.channel_configs.filter(
                    channel__in=(
                        DroneSopTargetChannelConfig.Channels.JIRA,
                        DroneSopTargetChannelConfig.Channels.MAIL,
                        DroneSopTargetChannelConfig.Channels.MESSENGER,
                    )
                )
            }
            self.assertEqual(channel_keys[DroneSopTargetChannelConfig.Channels.JIRA], "H1")
            self.assertEqual(channel_keys[DroneSopTargetChannelConfig.Channels.MAIL], "H1")
            self.assertEqual(channel_keys[DroneSopTargetChannelConfig.Channels.MESSENGER], "H1")
        self.assertTrue(
            DroneSopTargetDispatch.objects.filter(
                sop__line_id__startswith="DTEST-",
                target_code_snapshot="DTEST_ALPHA",
            ).exists()
        )
        self.assertTrue(
            DroneSopDelivery.objects.filter(
                sop__line_id__startswith="DTEST-",
                dispatch__target_code_snapshot="DTEST_ALPHA",
            ).exists()
        )

        recipients = selectors.list_drone_sop_channel_recipients(
            line_id="DTEST-L1",
            target_user_sdwt_prod="DTEST_ALPHA",
            channel=DroneSopTargetRecipient.Channels.MAIL,
        )
        self.assertEqual(len(recipients), 1)
        self.assertEqual(recipients[0]["externalKnoxId"], "dtest-01-mail")
        self.assertEqual(recipients[0]["email"], "dtest-01-mail@samsung.com")

    def test_seed_drone_dummy_data_dry_run_rolls_back_rows(self) -> None:
        """dry-run은 전체 seed 경로를 실행하되 생성 row를 남기지 않습니다."""

        output = StringIO()
        with patch.dict(os.environ, {"ENVIRONMENT": "development", "DRONE_SEED_ALLOWED": "1"}):
            call_command(
                "seed_drone_dummy_data",
                "--prefix",
                "DRYTEST",
                "--dry-run",
                stdout=output,
            )

        self.assertIn("[drone-seed] dry-run", output.getvalue())
        self.assertFalse(DroneSOP.objects.filter(line_id__startswith="DRYTEST-").exists())
        self.assertFalse(
            DroneSopTarget.objects.filter(
                target_user_sdwt_prod__startswith="DRYTEST_",
            ).exists()
        )
