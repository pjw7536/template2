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

class DroneJiraKeyEndpointTests(TestCase):
    """Jira 키/템플릿 키 엔드포인트를 검증합니다."""

    def setUp(self) -> None:
        """테스트용 사용자/소속 데이터를 준비합니다."""
        _allow_test_scope_access(self)
        User = get_user_model()
        self.user = User.objects.create_user(
            sabun="S70000",
            password="test-password",
            knox_id="knox-70000",
        )
        self.superuser = User.objects.create_superuser(
            sabun="S70001",
            password="test-password",
            knox_id="knox-70001",
        )
        self.staff_user = User.objects.create_user(
            sabun="S70002",
            password="test-password",
            knox_id="knox-70002",
            is_staff=True,
        )
        account_services.ensure_affiliation_option(
            department="Dept",
            line="L1",
            user_sdwt_prod="SDWT",
        )

    def test_jira_key_get_requires_authentication(self) -> None:
        """Jira 키 조회는 인증이 필요합니다."""
        response = self.client.get(reverse("line-dashboard-jira-keys"), {"targetUserSdwtProd": "SDWT"})
        self.assertEqual(response.status_code, 401)

    def test_jira_key_get_returns_values(self) -> None:
        """Jira 키/템플릿 키 조회가 정상 응답하는지 확인합니다."""
        _upsert_target(
            target_user_sdwt_prod="SDWT",
            jira_template_key="common",
            messenger_template_key="H1",
            mail_template_key="auto_sp",
            jira_key="PROJ",
            jira_enabled=False,
            messenger_enabled=False,
            force_new_chatroom=True,
            mail_enabled=True,
            needtosend_comment_last_at="$SETUP_EQP",
            needtosend_ignore_sample_type=True,
            needtosend_enabled=True,
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("line-dashboard-jira-keys"), {"targetUserSdwtProd": "SDWT"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["jiraKey"], "PROJ")
        self.assertNotIn("templateKey", response.json())
        self.assertEqual(response.json()["jiraTemplateKey"], "common")
        self.assertEqual(response.json()["messengerTemplateKey"], "H1")
        self.assertEqual(response.json()["mailTemplateKey"], "auto_sp")
        self.assertFalse(response.json()["jiraEnabled"])
        self.assertFalse(response.json()["messengerEnabled"])
        self.assertTrue(response.json()["messengerForceNewChatroom"])
        self.assertTrue(response.json()["mailEnabled"])
        self.assertEqual(response.json()["needtosendCommentLastAt"], "$SETUP_EQP")
        self.assertTrue(response.json()["needtosendIgnoreSampleType"])
        self.assertTrue(response.json()["needtosendEnabled"])

    def test_jira_key_get_matches_user_sdwt_prod_case_insensitively(self) -> None:
        """GET 조회가 targetUserSdwtProd 대소문자를 구분하지 않는지 확인합니다."""
        _upsert_target(
            target_user_sdwt_prod="SDWT",
            jira_template_key="common",
            jira_key="PROJ",
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("line-dashboard-jira-keys"), {"targetUserSdwtProd": "sdwt"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["jiraKey"], "PROJ")
        self.assertNotIn("templateKey", response.json())

    def test_jira_key_get_returns_existing_channel(self) -> None:
        """GET 조회가 저장된 채널 설정을 반환하는지 확인합니다."""
        _upsert_target(
            target_user_sdwt_prod="SDWT",
            jira_template_key="common",
            jira_key="PROJ",
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("line-dashboard-jira-keys"), {"targetUserSdwtProd": "SDWT"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["jiraKey"], "PROJ")
        self.assertNotIn("templateKey", response.json())

    def test_notification_template_options_requires_authentication(self) -> None:
        """템플릿 옵션 조회는 인증이 필요합니다."""

        response = self.client.get(reverse("line-dashboard-notification-template-options"))

        self.assertEqual(response.status_code, 401)

    def test_notification_template_options_returns_registry_keys(self) -> None:
        """템플릿 옵션 조회가 registry 기반 key 목록을 반환하는지 확인합니다."""

        self.client.force_login(self.user)
        response = self.client.get(reverse("line-dashboard-notification-template-options"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()["templates"]
        self.assertEqual([item["key"] for item in payload["jira"]], ["common", "H1"])
        self.assertEqual([item["key"] for item in payload["messenger"]], ["common", "H1"])
        self.assertEqual([item["key"] for item in payload["mail"]], ["common", "H1", "auto_sp"])
        self.assertEqual(payload["mail"][2]["label"], "Auto S/P")

    def test_jira_key_get_rejects_snake_case_query_key(self) -> None:
        """GET 조회는 target_user_sdwt_prod(snake_case) 쿼리 키를 허용하지 않는지 확인합니다."""

        self.client.force_login(self.user)
        response = self.client.get(
            reverse("line-dashboard-jira-keys"),
            {"target_user_sdwt_prod": "SDWT"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "targetUserSdwtProd is required")

    def test_jira_key_get_rejects_legacy_user_sdwt_prod_alias(self) -> None:
        """GET 조회는 제거된 userSdwtProd 별칭을 명시적으로 거부합니다."""

        self.client.force_login(self.user)
        response = self.client.get(
            reverse("line-dashboard-jira-keys"),
            {"userSdwtProd": "SDWT"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["error"],
            "userSdwtProd is not supported; use targetUserSdwtProd",
        )

    def test_jira_key_update_allows_authenticated_user(self) -> None:
        """Jira 키 갱신은 로그인 사용자와 staff 모두 허용되는지 확인합니다."""
        payload = {"lineId": "L1", "targetUserSdwtProd": "SDWT", "jiraKey": "PROJ", "jiraTemplateKey": "common"}

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("line-dashboard-jira-keys"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        self.client.force_login(self.staff_user)
        response = self.client.post(
            reverse("line-dashboard-jira-keys"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        refreshed = DroneSopTarget.objects.get(target_user_sdwt_prod="SDWT")
        self.assertEqual(_target_configuration_value(refreshed, "jiraKey"), "PROJ")
        self.assertEqual(_target_configuration_value(refreshed, "jiraTemplateKey"), "common")
        self.assertEqual(_target_configuration_value(refreshed, "messengerTemplateKey"), "common")
        self.assertEqual(refreshed.line_id, "L1")

    def test_jira_key_update_saves_channel_enabled_flags(self) -> None:
        """Jira/Teams/Mail 활성화 값을 함께 저장하는지 확인합니다."""
        payload = {
            "lineId": "L1",
            "targetUserSdwtProd": "SDWT",
            "jiraKey": "PROJ",
            "jiraEnabled": False,
            "messengerEnabled": True,
            "mailEnabled": False,
        }

        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse("line-dashboard-jira-keys"),
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["jiraEnabled"])
        self.assertTrue(response.json()["messengerEnabled"])
        self.assertFalse(response.json()["mailEnabled"])

        refreshed = DroneSopTarget.objects.get(target_user_sdwt_prod="SDWT")
        self.assertFalse(_target_configuration_value(refreshed, "jiraEnabled"))
        self.assertTrue(_target_configuration_value(refreshed, "messengerEnabled"))
        self.assertFalse(_target_configuration_value(refreshed, "mailEnabled"))

    def test_jira_key_update_saves_channel_template_keys(self) -> None:
        """Jira/Teams/Mail 템플릿 키를 채널별로 저장하는지 확인합니다."""
        payload = {
            "lineId": "L1",
            "targetUserSdwtProd": "SDWT",
            "jiraTemplateKey": "H1",
            "messengerTemplateKey": "common",
            "mailTemplateKey": "auto_sp",
        }

        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse("line-dashboard-jira-keys"),
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("templateKey", response.json())
        self.assertEqual(response.json()["jiraTemplateKey"], "H1")
        self.assertEqual(response.json()["messengerTemplateKey"], "common")
        self.assertEqual(response.json()["mailTemplateKey"], "auto_sp")

        refreshed = DroneSopTarget.objects.get(target_user_sdwt_prod="SDWT")
        self.assertEqual(_target_configuration_value(refreshed, "jiraTemplateKey"), "H1")
        self.assertEqual(_target_configuration_value(refreshed, "messengerTemplateKey"), "common")
        self.assertEqual(_target_configuration_value(refreshed, "mailTemplateKey"), "auto_sp")

    def test_jira_key_update_rejects_unknown_channel_template_key(self) -> None:
        """등록되지 않은 채널 템플릿 키는 저장하지 않는지 확인합니다."""
        payload = {
            "lineId": "L1",
            "targetUserSdwtProd": "SDWT",
            "mailTemplateKey": "unknown_template",
        }

        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse("line-dashboard-jira-keys"),
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "mailTemplateKey is not supported")
        self.assertFalse(DroneSopTarget.objects.filter(target_user_sdwt_prod="SDWT").exists())

    def test_jira_key_update_defaults_empty_channel_template_key_to_common(self) -> None:
        """빈 채널 템플릿 키는 common 기본값으로 저장하는지 확인합니다."""
        payload = {
            "lineId": "L1",
            "targetUserSdwtProd": "SDWT",
            "jiraTemplateKey": "",
            "messengerTemplateKey": "",
            "mailTemplateKey": "",
        }

        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse("line-dashboard-jira-keys"),
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["jiraTemplateKey"], "common")
        self.assertEqual(response.json()["messengerTemplateKey"], "common")
        self.assertEqual(response.json()["mailTemplateKey"], "common")

        refreshed = DroneSopTarget.objects.get(target_user_sdwt_prod="SDWT")
        self.assertEqual(_target_configuration_value(refreshed, "jiraTemplateKey"), "common")
        self.assertEqual(_target_configuration_value(refreshed, "messengerTemplateKey"), "common")
        self.assertEqual(_target_configuration_value(refreshed, "mailTemplateKey"), "common")

    def test_jira_key_update_saves_messenger_force_new_chatroom(self) -> None:
        """다음 메신저 발송 시 새 채팅방 생성 옵션을 저장하는지 확인합니다."""
        payload = {
            "lineId": "L1",
            "targetUserSdwtProd": "SDWT",
            "messengerForceNewChatroom": True,
        }

        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse("line-dashboard-jira-keys"),
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["messengerForceNewChatroom"])

        refreshed = DroneSopTarget.objects.get(target_user_sdwt_prod="SDWT")
        self.assertTrue(_target_configuration_value(refreshed, "messengerForceNewChatroom"))

    def test_jira_key_update_saves_needtosend_rule(self) -> None:
        """자동 예약 코멘트 포함 규칙을 함께 저장하는지 확인합니다."""
        payload = {
            "lineId": "L1",
            "targetUserSdwtProd": "SDWT",
            "needtosendCommentLastAt": "$SETUP_EQP",
            "needtosendEnabled": True,
            "needtosendIgnoreSampleType": False,
        }

        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse("line-dashboard-jira-keys"),
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["needtosendCommentLastAt"], "$SETUP_EQP")
        self.assertTrue(response.json()["needtosendEnabled"])
        self.assertFalse(response.json()["needtosendIgnoreSampleType"])

        refreshed = DroneSopTarget.objects.get(target_user_sdwt_prod="SDWT")
        self.assertEqual(_target_configuration_value(refreshed, "needtosendCommentLastAt"), "$SETUP_EQP")
        self.assertTrue(_target_configuration_value(refreshed, "needtosendEnabled"))
        self.assertFalse(_target_configuration_value(refreshed, "needtosendIgnoreSampleType"))

    def test_jira_key_update_reuses_existing_channel_case_insensitively(self) -> None:
        """POST 갱신이 target_user_sdwt_prod 대소문자를 무시하고 기존 채널을 재사용하는지 확인합니다."""
        _upsert_target(
            target_user_sdwt_prod="SDWT",
            jira_template_key="old",
            jira_key="OLD",
        )

        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse("line-dashboard-jira-keys"),
            data=json.dumps(
                {
                    "targetUserSdwtProd": "sdwt",
                    "jiraKey": "PROJ",
                    "jiraTemplateKey": "common",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(DroneSopTarget.objects.count(), 1)
        refreshed = DroneSopTarget.objects.get(target_user_sdwt_prod="SDWT")
        self.assertEqual(_target_configuration_value(refreshed, "jiraKey"), "PROJ")
        self.assertEqual(_target_configuration_value(refreshed, "jiraTemplateKey"), "common")

    def test_jira_key_post_requires_line_id_for_new_target(self) -> None:
        """새 알림 target의 Jira 키를 저장할 때는 lineId가 필요합니다."""

        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse("line-dashboard-jira-keys"),
            data=json.dumps({"targetUserSdwtProd": "CUSTOM_TARGET", "jiraKey": "PROJ"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "line_id is required for new target")
        self.assertFalse(
            DroneSopTarget.objects.filter(target_user_sdwt_prod="CUSTOM_TARGET").exists()
        )

    def test_jira_key_post_rejects_snake_case_target_user_sdwt_prod(self) -> None:
        """POST 갱신은 target_user_sdwt_prod(snake_case) 키를 허용하지 않는지 확인합니다."""
        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse("line-dashboard-jira-keys"),
            data=json.dumps(
                {
                    "target_user_sdwt_prod": "SDWT",
                    "jiraKey": "PROJ2",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "targetUserSdwtProd is required")

    def test_jira_key_post_rejects_legacy_user_sdwt_prod_alias(self) -> None:
        """POST 갱신은 제거된 userSdwtProd 별칭을 명시적으로 거부합니다."""

        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse("line-dashboard-jira-keys"),
            data=json.dumps({"userSdwtProd": "SDWT", "jiraKey": "PROJ"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["error"],
            "userSdwtProd is not supported; use targetUserSdwtProd",
        )

    def test_jira_key_post_rejects_snake_case_jira_template_keys(self) -> None:
        """POST 갱신은 jira_key/template_key(snake_case) 키를 허용하지 않는지 확인합니다."""
        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse("line-dashboard-jira-keys"),
            data=json.dumps(
                {
                    "targetUserSdwtProd": "SDWT",
                    "jira_key": "PROJ2",
                    "template_key": "H1",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "at least one configuration field is required")

    def test_jira_key_post_keeps_existing_messenger_template_key(self) -> None:
        """Jira 템플릿 갱신 시 기존 메신저 템플릿 키는 덮어쓰지 않는지 확인합니다."""
        _upsert_target(
            target_user_sdwt_prod="SDWT",
            messenger_template_key="H1",
        )

        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse("line-dashboard-jira-keys"),
            data=json.dumps(
                {
                    "targetUserSdwtProd": "SDWT",
                    "jiraTemplateKey": "common",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        refreshed = DroneSopTarget.objects.get(target_user_sdwt_prod="SDWT")
        self.assertEqual(_target_configuration_value(refreshed, "jiraTemplateKey"), "common")
        self.assertEqual(_target_configuration_value(refreshed, "messengerTemplateKey"), "H1")

    def test_jira_key_post_rejects_non_string_jira_key(self) -> None:
        """POST 갱신은 jiraKey에 문자열/Null 외 타입을 허용하지 않는지 확인합니다."""
        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse("line-dashboard-jira-keys"),
            data=json.dumps(
                {
                    "targetUserSdwtProd": "SDWT",
                    "jiraKey": 123,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "jiraKey must be a string or null")

    def test_jira_key_post_rejects_legacy_template_key_alias(self) -> None:
        """POST 갱신은 제거된 templateKey 별칭을 명시적으로 거부합니다."""
        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse("line-dashboard-jira-keys"),
            data=json.dumps(
                {
                    "targetUserSdwtProd": "SDWT",
                    "templateKey": "common",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["error"],
            "templateKey is not supported; use jiraTemplateKey",
        )

    def test_jira_key_post_updates_existing_channel(self) -> None:
        """갱신 요청이 기존 채널 설정을 재사용하는지 확인합니다."""
        _upsert_target(
            target_user_sdwt_prod="SDWT",
            jira_template_key="common",
            jira_key="OLD",
        )

        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse("line-dashboard-jira-keys"),
            data=json.dumps({"targetUserSdwtProd": "SDWT", "jiraKey": "NEW"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["jiraKey"], "NEW")

        refreshed = DroneSopTarget.objects.get(target_user_sdwt_prod="SDWT")
        self.assertEqual(_target_configuration_value(refreshed, "jiraKey"), "NEW")


class DroneSopJiraCreateProjectKeyTestsPart1(TestCase):
    """DroneSopJiraCreateProjectKeyTests 분리 회귀 테스트 1부입니다."""

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_JIRA_USE_BULK_API=True,
        DRONE_JIRA_BULK_SIZE=50,
    )
    @patch("api.drone.services.jira.sop_jira._jira_session")
    def test_jira_create_uses_project_key_per_user_sdwt_prod_and_marks_missing_as_failed(
        self, mock_session: Mock
    ) -> None:
        """user_sdwt_prod 기준 프로젝트 키가 적용되고 누락은 실패 처리되는지 확인합니다."""
        session = Mock()
        resp = Mock(status_code=201)
        resp.json.return_value = {"issues": [{"key": "PROJ1-1"}, {"key": "PROJ2-2"}]}
        session.post.return_value = resp
        mock_session.return_value = session

        account_services.ensure_affiliation_option(
            department="D",
            line="L1",
            user_sdwt_prod="SDWT1",
        )
        account_services.ensure_affiliation_option(
            department="D",
            line="L2",
            user_sdwt_prod="SDWT2",
        )
        account_services.ensure_affiliation_option(
            department="D",
            line="L3",
            user_sdwt_prod="SDWT3",
        )
        _upsert_target(
            target_user_sdwt_prod="SDWT1",
            jira_template_key="common",
            jira_key="PROJ1",
        )
        _upsert_target(
            target_user_sdwt_prod="SDWT2",
            jira_template_key="H1",
            jira_key="PROJ2",
        )
        _upsert_target(
            target_user_sdwt_prod="SDWT3",
            jira_template_key="common",
        )
        _ensure_target_mapping(sdwt_prod="SDWT1", user_sdwt_prod="SDWT1")
        _ensure_target_mapping(sdwt_prod="SDWT2", user_sdwt_prod="SDWT2")
        _ensure_target_mapping(sdwt_prod="SDWT3", user_sdwt_prod="SDWT3")

        sop1 = _create_drone_sop(
            line_id="L1",
            sdwt_prod="SDWT1",
            user_sdwt_prod="SDWT1",
            metro_current_step="ST001",
            comment="jira comment $@$ rule",
        )
        sop2 = _create_drone_sop(
            line_id="L2",
            sdwt_prod="SDWT2",
            user_sdwt_prod="SDWT2",
            eqp_id="EQP2",
            lot_id="LOT.2",
            metro_current_step="ST002",
        )
        sop_missing = _create_drone_sop(
            line_id="L3",
            sdwt_prod="SDWT3",
            user_sdwt_prod="SDWT3",
            eqp_id="EQP3",
            lot_id="LOT.3",
            metro_current_step="ST003",
        )

        result = services.run_drone_sop_jira_create_from_settings()
        self.assertEqual(result.candidates, 3)
        self.assertEqual(result.created, 2)

        session.post.assert_called_once()
        sent_payload = session.post.call_args.kwargs.get("json") or {}
        updates = sent_payload.get("issueUpdates") or []
        self.assertEqual(len(updates), 2)
        self.assertEqual(updates[0].get("fields", {}).get("project", {}).get("key"), "PROJ1")
        self.assertEqual(updates[1].get("fields", {}).get("project", {}).get("key"), "PROJ2")

        refreshed1 = DroneSOP.objects.get(id=sop1.id)
        refreshed2 = DroneSOP.objects.get(id=sop2.id)
        refreshed_missing = DroneSOP.objects.get(id=sop_missing.id)

        self.assertEqual(_sop_delivery_value(refreshed1, "sendJira"), 1)
        self.assertIsNone(_sop_delivery_value(refreshed1, "jiraReason"))
        self.assertEqual(_sop_delivery_value(refreshed1, "jiraKey"), "PROJ1-1")
        jira_delivery = DroneSopDelivery.objects.get(
            sop=sop1,
            channel=DroneSopDelivery.Channels.JIRA,
        )
        self.assertEqual(jira_delivery.sent_comment, "jira comment")
        self.assertEqual(_sop_delivery_value(refreshed2, "sendJira"), 1)
        self.assertIsNone(_sop_delivery_value(refreshed2, "jiraReason"))
        self.assertEqual(_sop_delivery_value(refreshed2, "jiraKey"), "PROJ2-2")
        self.assertEqual(_sop_delivery_value(refreshed_missing, "sendJira"), -1)
        self.assertEqual(_sop_delivery_value(refreshed_missing, "jiraReason"), "channel_config_invalid")

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_JIRA_USE_BULK_API=True,
        DRONE_JIRA_BULK_SIZE=50,
    )
    @patch("api.drone.services.jira.sop_jira._jira_session")
    def test_jira_create_uses_user_template_override(self, mock_session: Mock) -> None:
        """user_sdwt_prod 템플릿 매핑이 적용되는지 확인합니다."""
        session = Mock()
        resp = Mock(status_code=201)
        resp.json.return_value = {"issues": [{"key": "PROJ1-1"}]}
        session.post.return_value = resp
        mock_session.return_value = session

        account_services.ensure_affiliation_option(
            department="D",
            line="L1",
            user_sdwt_prod="SDWT",
        )
        _upsert_target(
            target_user_sdwt_prod="SDWT",
            jira_template_key="common",
            jira_key="PROJ1",
        )
        _ensure_target_mapping(sdwt_prod="SDWT", user_sdwt_prod="SDWT")

        sop1 = _create_drone_sop(
            sdwt_prod="SDWT",
            user_sdwt_prod="SDWT",
            metro_current_step="ST001",
        )

        result = services.run_drone_sop_jira_create_from_settings()
        self.assertEqual(result.candidates, 1)
        self.assertEqual(result.created, 1)

        refreshed = DroneSOP.objects.get(id=sop1.id)
        self.assertEqual(_sop_delivery_value(refreshed, "sendJira"), 1)

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_JIRA_USE_BULK_API=False,
    )
    @patch("api.drone.services.jira.sop_jira._jira_session")
    def test_jira_create_marks_missing_template_as_failed(self, mock_session: Mock) -> None:
        """템플릿 누락 시 실패로 마킹되는지 확인합니다."""
        session = Mock()
        resp = Mock(status_code=201)
        resp.json.return_value = {"key": "PROJ1-1"}
        session.post.return_value = resp
        mock_session.return_value = session

        account_services.ensure_affiliation_option(
            department="D",
            line="L1",
            user_sdwt_prod="SDWT1",
        )
        account_services.ensure_affiliation_option(
            department="D",
            line="L2",
            user_sdwt_prod="SDWT2",
        )
        _upsert_target(
            target_user_sdwt_prod="SDWT1",
            jira_template_key="common",
            jira_key="PROJ1",
        )
        _upsert_target(
            target_user_sdwt_prod="SDWT2",
            jira_key="PROJ2",
        )
        _ensure_target_mapping(sdwt_prod="SDWT1", user_sdwt_prod="SDWT1")
        _ensure_target_mapping(sdwt_prod="SDWT2", user_sdwt_prod="SDWT2")

        sop1 = _create_drone_sop(
            line_id="L1",
            sdwt_prod="SDWT1",
            user_sdwt_prod="SDWT1",
            metro_current_step="ST001",
        )
        sop2 = _create_drone_sop(
            line_id="L2",
            sdwt_prod="SDWT2",
            user_sdwt_prod="SDWT2",
            eqp_id="EQP2",
            lot_id="LOT.2",
            metro_current_step="ST002",
        )

        result = services.run_drone_sop_jira_create_from_settings()
        self.assertEqual(result.candidates, 2)
        self.assertEqual(result.created, 1)

        session.post.assert_called_once()

        refreshed1 = DroneSOP.objects.get(id=sop1.id)
        refreshed2 = DroneSOP.objects.get(id=sop2.id)

        self.assertEqual(_sop_delivery_value(refreshed1, "sendJira"), 1)
        self.assertIsNone(_sop_delivery_value(refreshed1, "jiraReason"))
        self.assertEqual(_sop_delivery_value(refreshed2, "sendJira"), -1)
        self.assertEqual(_sop_delivery_value(refreshed2, "jiraReason"), "channel_config_invalid")

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_JIRA_USE_BULK_API=True,
        DRONE_JIRA_BULK_SIZE=50,
    )
    @patch("api.drone.services.jira.sop_jira._jira_session")
    def test_jira_create_uses_target_user_sdwt_mapping(self, mock_session: Mock) -> None:
        """target_user_sdwt_prod 매핑이 적용되는지 확인합니다."""
        session = Mock()
        resp = Mock(status_code=201)
        resp.json.return_value = {"issues": [{"key": "PROJ-1"}]}
        session.post.return_value = resp
        mock_session.return_value = session

        target = _upsert_target(
            target_user_sdwt_prod="TARGET",
            jira_template_key="common",
            jira_key="PROJ",
        )
        DroneSopTargetMapping.objects.create(
            sdwt_prod="SDWTX",
            user_sdwt_prod="USERX",
            target=target,
        )

        sop = _create_drone_sop(
            sdwt_prod="SDWTX",
            user_sdwt_prod="USERX",
            metro_current_step="ST001",
        )

        result = services.run_drone_sop_jira_create_from_settings()
        self.assertEqual(result.candidates, 1)
        self.assertEqual(result.created, 1)

        session.post.assert_called_once()
        sent_payload = session.post.call_args.kwargs.get("json") or {}
        updates = sent_payload.get("issueUpdates") or []
        self.assertEqual(updates[0].get("fields", {}).get("project", {}).get("key"), "PROJ")

        refreshed = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(_sop_delivery_value(refreshed, "sendJira"), 1)
        self.assertEqual(refreshed.target_user_sdwt_prod, "TARGET")
        delivery = DroneSopDelivery.objects.get(sop=sop, channel=DroneSopDelivery.Channels.JIRA)
        self.assertEqual(delivery.external_key, "PROJ-1")

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_JIRA_USE_BULK_API=True,
        DRONE_JIRA_BULK_SIZE=50,
    )
    @patch("api.drone.services.jira.sop_jira._jira_session")
    def test_jira_create_skips_when_channel_config_incomplete(self, mock_session: Mock) -> None:
        """채널 설정이 불완전하면 스킵되는지 확인합니다."""
        mock_session.return_value = Mock()

        sop = _create_drone_sop(
            sdwt_prod="SDWT_NO",
            user_sdwt_prod="SDWT_NO",
            metro_current_step="ST001",
        )
        _ensure_target_mapping(sdwt_prod="SDWT_NO", user_sdwt_prod="SDWT_NO")
        _upsert_target(target_user_sdwt_prod="SDWT_NO", jira_enabled=True)

        result = services.run_drone_sop_jira_create_from_settings()
        self.assertEqual(result.candidates, 1)
        self.assertEqual(result.created, 0)
        mock_session.assert_not_called()

        refreshed = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(_sop_delivery_value(refreshed, "sendJira"), -1)
        self.assertEqual(_sop_delivery_value(refreshed, "jiraReason"), "channel_config_invalid")

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_JIRA_USE_BULK_API=True,
        DRONE_JIRA_BULK_SIZE=50,
    )
    @patch("api.drone.services.jira.sop_jira._jira_session")
    def test_jira_create_marks_disabled_channel_without_failure(self, mock_session: Mock) -> None:
        """비활성화된 Jira 채널은 실패(-1) 없이 비활성 사유만 기록하는지 확인합니다."""
        mock_session.return_value = Mock()

        _upsert_target(
            target_user_sdwt_prod="SDWT1",
            jira_template_key="common",
            jira_key="PROJ1",
            jira_enabled=False,
        )
        _ensure_target_mapping(sdwt_prod="SDWT1", user_sdwt_prod="SDWT1")

        sop = _create_drone_sop(
            line_id="L1",
            sdwt_prod="SDWT1",
            user_sdwt_prod="SDWT1",
            eqp_id="EQP1",
            chamber_ids="1",
            lot_id="LOT.1",
            main_step="MS",
            status="COMPLETE",
            needtosend=1,
            send_jira=0,
            metro_current_step="ST001",
        )

        result = services.run_drone_sop_jira_create_from_settings()
        self.assertEqual(result.candidates, 1)
        self.assertEqual(result.created, 0)
        mock_session.assert_not_called()

        refreshed = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(_sop_delivery_value(refreshed, "sendJira"), 0)
        self.assertEqual(_sop_delivery_value(refreshed, "jiraReason"), "disabled_by_policy")

    @override_settings(DRONE_JIRA_BASE_URL="")
    @patch("api.drone.services.jira.sop_jira._jira_session")
    def test_jira_create_marks_failed_when_base_url_missing(self, mock_session: Mock) -> None:
        """Jira 설정이 없으면 실패로 마킹되는지 확인합니다."""
        mock_session.return_value = Mock()

        sop = _create_drone_sop(
            sdwt_prod="SDWT1",
            user_sdwt_prod="SDWT1",
            instant_inform=1,
            metro_current_step="ST001",
        )
        _ensure_target_mapping(sdwt_prod="SDWT1", user_sdwt_prod="SDWT1")
        _upsert_target(
            target_user_sdwt_prod="SDWT1",
            jira_template_key="common",
            jira_key="PROJ1",
        )

        result = services.run_drone_sop_jira_create_from_settings()
        self.assertTrue(result.skipped)
        self.assertEqual(result.skip_reason, "jira_disabled")
        mock_session.assert_not_called()

        refreshed = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(_sop_delivery_value(refreshed, "sendJira"), -1)
        self.assertEqual(_sop_delivery_value(refreshed, "jiraReason"), "config_missing")
        self.assertEqual(refreshed.instant_inform, 1)

    @override_settings(DRONE_JIRA_BASE_URL="")
    @patch("api.drone.services.jira.sop_jira._jira_session")
    def test_jira_create_marks_disabled_when_base_url_missing(self, mock_session: Mock) -> None:
        """Jira 설정이 없어도 비활성 채널은 실패 대신 비활성 사유를 기록하는지 확인합니다."""
        mock_session.return_value = Mock()

        _upsert_target(
            target_user_sdwt_prod="SDWT1",
            jira_template_key="common",
            jira_key="PROJ1",
            jira_enabled=False,
        )

        sop = _create_drone_sop(
            sdwt_prod="SDWT1",
            user_sdwt_prod="SDWT1",
            instant_inform=1,
            metro_current_step="ST001",
        )
        _ensure_target_mapping(sdwt_prod="SDWT1", user_sdwt_prod="SDWT1")

        result = services.run_drone_sop_jira_create_from_settings()
        self.assertTrue(result.skipped)
        self.assertEqual(result.skip_reason, "jira_disabled")
        mock_session.assert_not_called()

        refreshed = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(_sop_delivery_value(refreshed, "sendJira"), 0)
        self.assertEqual(_sop_delivery_value(refreshed, "jiraReason"), "disabled_by_policy")
        self.assertEqual(refreshed.instant_inform, 1)

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_JIRA_USE_BULK_API=True,
        DRONE_JIRA_BULK_SIZE=50,
    )
    @patch("api.drone.services.jira.sop_jira._jira_session")
    def test_jira_create_marks_missing_target_as_failed(self, mock_session: Mock) -> None:
        """sdwt_prod/user_sdwt_prod가 모두 없으면 실패 처리되는지 확인합니다."""
        mock_session.return_value = Mock()

        sop = _create_drone_sop(
            sdwt_prod=None,
            user_sdwt_prod=None,
            instant_inform=1,
            metro_current_step="ST001",
        )

        result = services.run_drone_sop_jira_create_from_settings()
        self.assertEqual(result.candidates, 1)
        self.assertEqual(result.created, 0)
        self.assertTrue(result.skipped)
        self.assertEqual(result.skip_reason, "no_valid_targets")
        mock_session.assert_not_called()

        refreshed = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(_sop_delivery_value(refreshed, "sendJira"), -1)
        self.assertEqual(_sop_delivery_value(refreshed, "jiraReason"), "target_missing")
        self.assertEqual(refreshed.instant_inform, 1)

class DroneSopJiraCreateProjectKeyTestsPart2(TestCase):
    """DroneSopJiraCreateProjectKeyTests 분리 회귀 테스트 2부입니다."""

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_JIRA_USE_BULK_API=False,
    )
    @patch("api.drone.services.jira.sop_jira._jira_session")
    @patch("api.drone.services.jira.sop_jira._single_create_jira_issues")
    def test_jira_create_marks_failed_when_create_fails(
        self,
        mock_single_create: Mock,
        mock_session: Mock,
    ) -> None:
        """Jira 생성 실패 delivery가 실패 상태로 요약되는지 확인합니다."""
        mock_session.return_value = Mock()

        _upsert_target(
            target_user_sdwt_prod="SDWT1",
            jira_template_key="common",
            jira_key="PROJ1",
        )
        _upsert_target(
            target_user_sdwt_prod="SDWT2",
            jira_template_key="common",
            jira_key="PROJ2",
        )
        _ensure_target_mapping(sdwt_prod="SDWT1", user_sdwt_prod="SDWT1")
        _ensure_target_mapping(sdwt_prod="SDWT2", user_sdwt_prod="SDWT2")

        instant = _create_drone_sop(
            sdwt_prod="SDWT1",
            user_sdwt_prod="SDWT1",
            status="IN_PROGRESS",
            needtosend=0,
            instant_inform=1,
            metro_current_step="ST001",
        )
        normal = _create_drone_sop(
            line_id="L2",
            sdwt_prod="SDWT2",
            user_sdwt_prod="SDWT2",
            eqp_id="EQP2",
            lot_id="LOT.2",
            metro_current_step="ST002",
        )

        def _single_create_side_effect(*args: Any, **kwargs: Any) -> tuple[list[int], dict[int, str]]:
            rows = kwargs.get("rows") or []
            normal_delivery_id = next(
                int(row["delivery_id"])
                for row in rows
                if isinstance(row, dict) and row.get("id") == normal.id and isinstance(row.get("delivery_id"), int)
            )
            return [normal_delivery_id], {normal_delivery_id: "PROJ2-1"}

        mock_single_create.side_effect = _single_create_side_effect

        result = services.run_drone_sop_jira_create_from_settings()
        self.assertEqual(result.candidates, 2)
        self.assertEqual(result.created, 1)

        refreshed_instant = DroneSOP.objects.get(id=instant.id)
        refreshed_normal = DroneSOP.objects.get(id=normal.id)

        self.assertEqual(refreshed_instant.instant_inform, 1)
        self.assertEqual(_sop_delivery_value(refreshed_instant, "sendJira"), -1)
        self.assertEqual(_sop_delivery_value(refreshed_instant, "jiraReason"), "send_failed")
        self.assertEqual(_sop_delivery_value(refreshed_normal, "sendJira"), 1)
        mock_single_create.assert_called_once()

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_JIRA_USE_BULK_API=False,
    )
    @patch("api.drone.services.jira.sop_jira._jira_session")
    def test_jira_create_marks_failed_when_request_error_occurs(
        self,
        mock_session: Mock,
    ) -> None:
        """일부 요청 예외가 나도 성공 건은 반영하고 실패 건은 실패로 요약되는지 확인합니다."""
        session = Mock()
        mock_session.return_value = session

        _upsert_target(
            target_user_sdwt_prod="SDWT_ENABLED_1",
            jira_template_key="common",
            jira_key="PROJ1",
            jira_enabled=True,
        )
        _upsert_target(
            target_user_sdwt_prod="SDWT_ENABLED_2",
            jira_template_key="common",
            jira_key="PROJ2",
            jira_enabled=True,
        )
        _upsert_target(
            target_user_sdwt_prod="SDWT_DISABLED",
            jira_template_key="common",
            jira_key="PROJ3",
            jira_enabled=False,
        )
        _ensure_target_mapping(sdwt_prod="SDWT_ENABLED_1", user_sdwt_prod="SDWT_ENABLED_1")
        _ensure_target_mapping(sdwt_prod="SDWT_ENABLED_2", user_sdwt_prod="SDWT_ENABLED_2")
        _ensure_target_mapping(sdwt_prod="SDWT_DISABLED", user_sdwt_prod="SDWT_DISABLED")

        enabled_row_1 = _create_drone_sop(
            sdwt_prod="SDWT_ENABLED_1",
            user_sdwt_prod="SDWT_ENABLED_1",
            metro_current_step="ST001",
        )
        enabled_row_2 = _create_drone_sop(
            line_id="L2",
            sdwt_prod="SDWT_ENABLED_2",
            user_sdwt_prod="SDWT_ENABLED_2",
            eqp_id="EQP2",
            lot_id="LOT.2",
            metro_current_step="ST001",
        )
        disabled_row = _create_drone_sop(
            line_id="L3",
            sdwt_prod="SDWT_DISABLED",
            user_sdwt_prod="SDWT_DISABLED",
            eqp_id="EQP3",
            lot_id="LOT.3",
            metro_current_step="ST001",
        )

        ok_resp = Mock(status_code=201)
        ok_resp.json.return_value = {"key": "PROJ2-1"}

        def _post_side_effect(*args: Any, **kwargs: Any) -> Mock:
            payload = kwargs.get("json") or {}
            project_key = (
                payload.get("fields", {})
                .get("project", {})
                .get("key")
            )
            if project_key == "PROJ1":
                raise requests.Timeout("jira unavailable")
            return ok_resp

        session.post.side_effect = _post_side_effect

        result = services.run_drone_sop_jira_create_from_settings()
        self.assertEqual(result.candidates, 3)
        self.assertEqual(result.created, 1)

        refreshed_enabled_1 = DroneSOP.objects.get(id=enabled_row_1.id)
        refreshed_enabled_2 = DroneSOP.objects.get(id=enabled_row_2.id)
        refreshed_disabled = DroneSOP.objects.get(id=disabled_row.id)

        self.assertEqual(_sop_delivery_value(refreshed_enabled_1, "sendJira"), -1)
        self.assertEqual(_sop_delivery_value(refreshed_enabled_1, "jiraReason"), "send_failed")
        self.assertEqual(_sop_delivery_value(refreshed_enabled_2, "sendJira"), 1)
        self.assertIsNone(_sop_delivery_value(refreshed_enabled_2, "jiraReason"))
        self.assertEqual(_sop_delivery_value(refreshed_disabled, "sendJira"), 0)
        self.assertEqual(_sop_delivery_value(refreshed_disabled, "jiraReason"), "disabled_by_policy")
        self.assertEqual(session.post.call_count, 2)
