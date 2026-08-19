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

class DroneSopInformPolicyTestsPart1(TestCase):
    """DroneSopInformPolicyTests 분리 회귀 테스트 1부입니다."""

    def setUp(self) -> None:
        """테스트에 필요한 기본 매핑을 준비합니다."""

        _ensure_target_mapping(sdwt_prod="SDWT1", user_sdwt_prod="SDWT1")

    @override_settings(DRONE_JIRA_BASE_URL="http://example.local/jira")
    @patch("api.drone.services.inform.sop_inform.send_drone_sop_mail")
    @patch("api.drone.services.messenger.messenger_api.send_drone_sop_messenger_message")
    @patch("api.drone.services.jira.sop_jira._jira_session")
    def test_inform_marks_missing_target_as_failed(
        self,
        mock_session: Mock,
        mock_messenger: Mock,
        mock_mail: Mock,
    ) -> None:
        """sdwt_prod/user_sdwt_prod가 없으면 실패 처리되는지 확인합니다."""
        mock_session.return_value = Mock()

        sop = _create_drone_sop(
            sdwt_prod=None,
            user_sdwt_prod=None,
            send_messenger=0,
            send_mail=0,
            instant_inform=1,
            metro_current_step="ST001",
        )

        result = services.run_drone_sop_pipeline_from_settings()
        self.assertEqual(result.candidates, 1)
        self.assertTrue(result.skipped)
        self.assertEqual(result.skip_reason, "no_valid_targets")

        mock_session.assert_not_called()
        mock_messenger.assert_not_called()
        mock_mail.assert_not_called()

        refreshed = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(_sop_delivery_value(refreshed, "sendJira"), -1)
        self.assertEqual(_sop_delivery_value(refreshed, "sendMessenger"), -1)
        self.assertEqual(_sop_delivery_value(refreshed, "sendMail"), -1)
        self.assertEqual(_sop_delivery_value(refreshed, "jiraReason"), "target_missing")
        self.assertEqual(_sop_delivery_value(refreshed, "messengerReason"), "target_missing")
        self.assertEqual(_sop_delivery_value(refreshed, "mailReason"), "target_missing")
        self.assertEqual(refreshed.instant_inform, 1)

@override_settings(
    KNOX_MESSENGER_API_BASE_URL="http://example.local/messenger/",
    KNOX_MESSENGER_AUTHORIZATION="dummy-auth",
    KNOX_MESSENGER_SYSTEM_ID="dummy-system",
)
class DroneSopInformPolicyTestsPart1Continuation(TestCase):
    """DroneSopInformPolicyTests 분리 회귀 테스트 1부의 후속 묶음입니다."""

    def setUp(self) -> None:
        """테스트에 필요한 기본 매핑을 준비합니다."""

        _ensure_target_mapping(sdwt_prod="SDWT1", user_sdwt_prod="SDWT1")

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_MAIL_SENDER="sender@example.com",
    )
    @patch("api.drone.services.inform.sop_inform.send_drone_sop_messenger_message")
    @patch("api.drone.services.inform.sop_inform.send_drone_sop_mail")
    def test_inform_continues_pending_channels_when_one_channel_already_sent(
        self,
        mock_mail: Mock,
        mock_messenger: Mock,
    ) -> None:
        """한 채널이 완료되어도 남은 미전송 채널은 계속 처리하는지 확인합니다."""
        _upsert_target(
            target_user_sdwt_prod="SDWT1",
            messenger_template_key="common",
            mail_template_key="common",
            chatroom_id=12345,
        )
        _create_drone_sop(
            sdwt_prod="SDWT1",
            user_sdwt_prod="SDWT1",
            send_jira=1,
            send_messenger=0,
            send_mail=1,
            instant_inform=1,
            metro_current_step="ST001",
        )

        result = services.run_drone_sop_pipeline_from_settings()
        self.assertEqual(result.candidates, 1)
        self.assertEqual(result.messenger_sent, 1)
        mock_messenger.assert_called_once()
        mock_mail.assert_not_called()

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_MAIL_SENDER="sender@example.com",
    )
    @patch("api.drone.services.jira.sop_jira._jira_session")
    @patch("api.drone.services.inform.sop_inform.send_drone_sop_messenger_message")
    @patch("api.drone.services.inform.sop_inform.send_drone_sop_mail")
    def test_inform_skips_failed_delivery_until_manual_retry(
        self,
        mock_mail: Mock,
        mock_messenger: Mock,
        mock_jira_session: Mock,
    ) -> None:
        """실패 delivery는 자동 재발송하지 않고 pending 채널만 처리하는지 확인합니다."""
        _upsert_target(
            target_user_sdwt_prod="SDWT1",
            jira_template_key="common",
            jira_key="PROJ1",
            messenger_template_key="common",
            mail_template_key="common",
            chatroom_id=12345,
        )
        sop = _create_drone_sop(
            sdwt_prod="SDWT1",
            user_sdwt_prod="SDWT1",
            send_jira=-1,
            jira_reason="send_failed",
            send_messenger=0,
            send_mail=-1,
            mail_reason="send_failed",
            instant_inform=1,
            metro_current_step="ST001",
        )
        jira_delivery = DroneSopDelivery.objects.get(
            sop=sop,
            channel=DroneSopDelivery.Channels.JIRA,
        )
        jira_delivery.status = DroneSopDelivery.Statuses.FAILED
        jira_delivery.reason = "send_failed"
        jira_delivery.save(update_fields=["status", "reason", "updated_at"])
        messenger_delivery = DroneSopDelivery.objects.get(
            sop=sop,
            channel=DroneSopDelivery.Channels.MESSENGER,
        )
        messenger_delivery.status = DroneSopDelivery.Statuses.PENDING
        messenger_delivery.reason = None
        messenger_delivery.save(update_fields=["status", "reason", "updated_at"])

        result = services.run_drone_sop_pipeline_from_settings()

        self.assertEqual(result.candidates, 1)
        self.assertEqual(result.jira_created, 0)
        self.assertEqual(result.messenger_sent, 1)
        mock_jira_session.assert_not_called()
        mock_messenger.assert_called_once()
        mock_mail.assert_not_called()

        jira_delivery.refresh_from_db()
        messenger_delivery.refresh_from_db()
        self.assertEqual(jira_delivery.status, DroneSopDelivery.Statuses.FAILED)
        self.assertEqual(jira_delivery.reason, "send_failed")
        self.assertEqual(messenger_delivery.status, DroneSopDelivery.Statuses.SUCCESS)

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_MAIL_SENDER="sender@example.com",
    )
    @patch("api.drone.services.jira.sop_jira._jira_session")
    @patch("api.drone.services.inform.sop_inform.send_drone_sop_messenger_message")
    @patch("api.drone.services.inform.sop_inform.send_drone_sop_mail")
    def test_inform_skips_cancelled_delivery_until_manual_retry(
        self,
        mock_mail: Mock,
        mock_messenger: Mock,
        mock_jira_session: Mock,
    ) -> None:
        """취소 delivery는 자동 재발송하지 않고 pending 채널만 처리하는지 확인합니다."""
        User = get_user_model()
        user = User.objects.create_user(sabun="S85001", password="test-password")
        user.email = "target85001@example.com"
        user.save(update_fields=["email"])
        _set_current_affiliation(user, user_sdwt_prod="SDWT1")
        _upsert_target(
            target_user_sdwt_prod="SDWT1",
            jira_template_key="common",
            jira_key="PROJ1",
            messenger_template_key="common",
            mail_template_key="common",
            chatroom_id=12345,
        )
        _create_target_recipient(
            target_user_sdwt_prod="SDWT1",
            channel=DroneSopTargetRecipient.Channels.MAIL,
            user=user,
        )
        sop = _create_drone_sop(
            sdwt_prod="SDWT1",
            user_sdwt_prod="SDWT1",
            send_jira=0,
            send_messenger=0,
            send_mail=0,
            instant_inform=1,
            metro_current_step="ST001",
        )
        for channel in (DroneSopDelivery.Channels.JIRA, DroneSopDelivery.Channels.MESSENGER):
            delivery = DroneSopDelivery.objects.get(sop=sop, channel=channel)
            delivery.status = DroneSopDelivery.Statuses.CANCELLED
            delivery.reason = "cancelled"
            delivery.save(update_fields=["status", "reason", "updated_at"])

        result = services.run_drone_sop_pipeline_from_settings()

        self.assertEqual(result.candidates, 1)
        self.assertEqual(result.jira_created, 0)
        self.assertEqual(result.messenger_sent, 0)
        self.assertEqual(result.mail_sent, 1)
        mock_jira_session.assert_not_called()
        mock_messenger.assert_not_called()
        mock_mail.assert_called_once()

        jira_delivery = DroneSopDelivery.objects.get(sop=sop, channel=DroneSopDelivery.Channels.JIRA)
        messenger_delivery = DroneSopDelivery.objects.get(sop=sop, channel=DroneSopDelivery.Channels.MESSENGER)
        mail_delivery = DroneSopDelivery.objects.get(sop=sop, channel=DroneSopDelivery.Channels.MAIL)
        self.assertEqual(jira_delivery.status, DroneSopDelivery.Statuses.CANCELLED)
        self.assertEqual(messenger_delivery.status, DroneSopDelivery.Statuses.CANCELLED)
        self.assertEqual(mail_delivery.status, DroneSopDelivery.Statuses.SUCCESS)

    def test_inform_persists_mapping_target_on_sop(self) -> None:
        """발송 준비가 매핑 target을 DroneSOP에 저장하는지 확인합니다."""
        sop = _create_drone_sop(
            sdwt_prod="SDWT1",
            user_sdwt_prod="SDWT1",
            send_jira=1,
            send_messenger=0,
            send_mail=1,
            instant_inform=1,
            metro_current_step="ST001",
        )

        result = services.run_drone_sop_pipeline_from_settings()
        self.assertEqual(result.candidates, 1)

        refreshed = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(refreshed.target_user_sdwt_prod, "SDWT1")
        delivery = DroneSopDelivery.objects.get(
            sop=sop,
            channel=DroneSopDelivery.Channels.MESSENGER,
        )
        self.assertIsNotNone(delivery.id)

    @override_settings(DRONE_JIRA_BASE_URL="")
    def test_inform_marks_jira_failed_when_base_url_missing(self) -> None:
        """Jira 설정이 없으면 send_jira가 실패 처리되는지 확인합니다."""
        _upsert_target(
            target_user_sdwt_prod="SDWT1",
            jira_template_key="common",
            jira_key="PROJ1",
        )
        sop = _create_drone_sop(
            sdwt_prod="SDWT1",
            user_sdwt_prod="SDWT1",
            send_messenger=-1,
            send_mail=-1,
            instant_inform=1,
            metro_current_step="ST001",
        )

        result = services.run_drone_sop_pipeline_from_settings()
        self.assertEqual(result.candidates, 1)

        refreshed = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(_sop_delivery_value(refreshed, "sendJira"), -1)
        self.assertEqual(_sop_delivery_value(refreshed, "jiraReason"), "config_missing")
        self.assertEqual(refreshed.instant_inform, 1)
        self.assertEqual(_sop_delivery_value(refreshed, "sendMessenger"), -1)
        self.assertEqual(_sop_delivery_value(refreshed, "sendMail"), -1)

    @override_settings(
        DRONE_JIRA_BASE_URL="",
        DRONE_MAIL_SENDER="sender@example.com",
    )
    def test_inform_marks_jira_disabled_when_base_url_missing(self) -> None:
        """Jira 설정이 없어도 비활성 채널은 실패 대신 비활성 사유를 기록하는지 확인합니다."""
        _upsert_target(
            target_user_sdwt_prod="SDWT1",
            jira_template_key="common",
            jira_key="PROJ1",
            jira_enabled=False,
        )

        sop = _create_drone_sop(
            sdwt_prod="SDWT1",
            user_sdwt_prod="SDWT1",
            send_messenger=-1,
            send_mail=-1,
            instant_inform=1,
            metro_current_step="ST001",
        )

        result = services.run_drone_sop_pipeline_from_settings()
        self.assertEqual(result.candidates, 1)

        refreshed = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(_sop_delivery_value(refreshed, "sendJira"), 0)
        self.assertEqual(_sop_delivery_value(refreshed, "jiraReason"), "disabled_by_policy")
        self.assertEqual(refreshed.instant_inform, 1)

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_MAIL_SENDER="",
    )
    def test_inform_marks_mail_failed_when_sender_missing(self) -> None:
        """메일 발신자 미설정 시 send_mail이 실패 처리되는지 확인합니다."""
        _upsert_target(
            target_user_sdwt_prod="SDWT1",
            mail_template_key="common",
        )
        sop = _create_drone_sop(
            sdwt_prod="SDWT1",
            user_sdwt_prod="SDWT1",
            send_jira=-1,
            send_messenger=-1,
            send_mail=0,
            metro_current_step="ST001",
        )

        result = services.run_drone_sop_pipeline_from_settings()
        self.assertEqual(result.candidates, 1)

        refreshed = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(_sop_delivery_value(refreshed, "sendMail"), -1)
        self.assertEqual(_sop_delivery_value(refreshed, "mailReason"), "config_missing")
        self.assertEqual(_sop_delivery_value(refreshed, "sendJira"), -1)
        self.assertEqual(_sop_delivery_value(refreshed, "sendMessenger"), -1)

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_MAIL_SENDER="",
    )
    def test_inform_marks_mail_disabled_when_sender_missing(self) -> None:
        """메일 발신자 설정이 없어도 비활성 채널은 실패 대신 비활성 사유를 기록하는지 확인합니다."""
        _upsert_target(
            target_user_sdwt_prod="SDWT1",
            mail_template_key="common",
            mail_enabled=False,
        )

        sop = _create_drone_sop(
            line_id="L1",
            sdwt_prod="SDWT1",
            user_sdwt_prod="SDWT1",
            eqp_id="EQP1",
            chamber_ids="1",
            lot_id="LOT.1",
            main_step="MS",
            status="COMPLETE",
            target_user_sdwt_prod="SDWT1",
            needtosend=1,
            send_jira=-1,
            send_messenger=-1,
            send_mail=0,
            metro_current_step="ST001",
        )

        result = services.run_drone_sop_pipeline_from_settings()
        self.assertEqual(result.candidates, 1)

        refreshed = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(_sop_delivery_value(refreshed, "sendMail"), 0)
        self.assertEqual(_sop_delivery_value(refreshed, "mailReason"), "disabled_by_policy")

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_MAIL_SENDER="sender@example.com",
    )
    @patch("api.drone.services.messenger.messenger_api.send_drone_sop_messenger_message")
    def test_inform_marks_messenger_failed_when_template_missing(self) -> None:
        """메신저 템플릿 설정이 없으면 send_messenger가 실패 처리되는지 확인합니다."""
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
            send_jira=-1,
            send_messenger=0,
            send_mail=-1,
            metro_current_step="ST001",
        )

        result = services.run_drone_sop_pipeline_from_settings()
        self.assertEqual(result.candidates, 1)

        refreshed = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(_sop_delivery_value(refreshed, "sendMessenger"), -1)
        self.assertEqual(_sop_delivery_value(refreshed, "messengerReason"), "template_missing")
        self.assertEqual(_sop_delivery_value(refreshed, "sendJira"), -1)
        self.assertEqual(_sop_delivery_value(refreshed, "sendMail"), -1)

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_MAIL_SENDER="sender@example.com",
    )
    @patch("api.drone.services.messenger.messenger_api.send_drone_sop_messenger_message")
    def test_inform_marks_messenger_failed_when_template_missing(self, mock_messenger: Mock) -> None:
        """메신저 템플릿 키가 없으면 send_messenger가 실패 처리되는지 확인합니다."""
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
            send_jira=-1,
            send_messenger=0,
            send_mail=-1,
            metro_current_step="ST001",
        )
        _upsert_target(
            target_user_sdwt_prod="SDWT1",
            chatroom_id=12345,
        )

        result = services.run_drone_sop_pipeline_from_settings()
        self.assertEqual(result.candidates, 1)

        refreshed = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(_sop_delivery_value(refreshed, "sendMessenger"), -1)
        self.assertEqual(_sop_delivery_value(refreshed, "messengerReason"), "template_missing")
        mock_messenger.assert_not_called()

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_MAIL_SENDER="sender@example.com",
    )
    @patch("api.drone.services.inform.sop_inform.send_drone_sop_messenger_message")
    def test_inform_marks_messenger_failed_when_template_key_invalid(self, mock_messenger: Mock) -> None:
        """지원하지 않는 메신저 템플릿 키는 API 호출 전에 설정 오류로 처리합니다."""
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
            send_jira=-1,
            send_messenger=0,
            send_mail=-1,
            metro_current_step="ST001",
        )
        _upsert_target(
            target_user_sdwt_prod="SDWT1",
            messenger_template_key="messenger",
            chatroom_id=12345,
        )

        result = services.run_drone_sop_pipeline_from_settings()
        self.assertEqual(result.candidates, 1)

        refreshed = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(_sop_delivery_value(refreshed, "sendMessenger"), -1)
        self.assertEqual(_sop_delivery_value(refreshed, "messengerReason"), "channel_config_invalid")
        mock_messenger.assert_not_called()

@override_settings(
    KNOX_MESSENGER_API_BASE_URL="http://example.local/messenger/",
    KNOX_MESSENGER_AUTHORIZATION="dummy-auth",
    KNOX_MESSENGER_SYSTEM_ID="dummy-system",
)
class DroneSopInformPolicyTestsPart2(TestCase):
    """DroneSopInformPolicyTests 분리 회귀 테스트 2부입니다."""

    def setUp(self) -> None:
        """테스트에 필요한 기본 매핑을 준비합니다."""

        _ensure_target_mapping(sdwt_prod="SDWT1", user_sdwt_prod="SDWT1")

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_MAIL_SENDER="sender@example.com",
        KNOX_MESSENGER_API_BASE_URL="",
        KNOX_MESSENGER_AUTHORIZATION="",
        KNOX_MESSENGER_SYSTEM_ID="",
    )
    @patch("api.drone.services.messenger.messenger_api.send_drone_sop_messenger_message")
    def test_inform_marks_messenger_failed_when_knox_config_missing(self, mock_messenger: Mock) -> None:
        """Knox 메신저 설정이 없으면 send_messenger가 실패 처리되는지 확인합니다."""
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
            send_jira=-1,
            send_messenger=0,
            send_mail=-1,
            metro_current_step="ST001",
        )
        _upsert_target(
            target_user_sdwt_prod="SDWT1",
            chatroom_id=12345,
        )

        result = services.run_drone_sop_pipeline_from_settings()
        self.assertEqual(result.candidates, 1)

        refreshed = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(_sop_delivery_value(refreshed, "sendMessenger"), -1)
        self.assertEqual(_sop_delivery_value(refreshed, "messengerReason"), "config_missing")
        mock_messenger.assert_not_called()

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_MAIL_SENDER="sender@example.com",
        KNOX_MESSENGER_API_BASE_URL="",
        KNOX_MESSENGER_AUTHORIZATION="",
        KNOX_MESSENGER_SYSTEM_ID="",
    )
    @patch("api.drone.services.messenger.messenger_api.send_drone_sop_messenger_message")
    def test_inform_marks_messenger_disabled_when_knox_config_missing(self, mock_messenger: Mock) -> None:
        """Knox 설정이 없어도 비활성 채널은 실패 대신 비활성 사유를 기록하는지 확인합니다."""
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
            send_jira=-1,
            send_messenger=0,
            send_mail=-1,
            metro_current_step="ST001",
        )
        _upsert_target(
            target_user_sdwt_prod="SDWT1",
            chatroom_id=12345,
            messenger_enabled=False,
        )

        result = services.run_drone_sop_pipeline_from_settings()
        self.assertEqual(result.candidates, 1)

        refreshed = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(_sop_delivery_value(refreshed, "sendMessenger"), 0)
        self.assertEqual(_sop_delivery_value(refreshed, "messengerReason"), "disabled_by_policy")
        mock_messenger.assert_not_called()

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_MAIL_SENDER="sender@example.com",
    )
    @patch("api.drone.services.jira.sop_jira._jira_session")
    def test_inform_marks_jira_disabled_without_failure(self, mock_session: Mock) -> None:
        """비활성화된 Jira 채널은 실패(-1) 없이 비활성 사유만 기록하는지 확인합니다."""
        mock_session.return_value = Mock()

        _upsert_target(
            target_user_sdwt_prod="SDWT1",
            jira_template_key="common",
            jira_key="PROJ1",
            jira_enabled=False,
        )

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
            send_messenger=-1,
            send_mail=-1,
            metro_current_step="ST001",
        )

        result = services.run_drone_sop_pipeline_from_settings()
        self.assertEqual(result.candidates, 1)
        mock_session.assert_not_called()

        refreshed = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(_sop_delivery_value(refreshed, "sendJira"), 0)
        self.assertEqual(_sop_delivery_value(refreshed, "jiraReason"), "disabled_by_policy")

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_MAIL_SENDER="sender@example.com",
    )
    @patch("api.drone.services.inform.sop_inform.run_drone_sop_jira_create_from_rows")
    def test_inform_uses_shared_jira_service_path(self, mock_run_jira: Mock) -> None:
        """inform 경로가 공통 Jira 서비스 함수를 사용해 결과를 반영하는지 확인합니다."""
        mock_run_jira.return_value = services.DroneSopJiraCreateResult(
            candidates=1,
            created=1,
            updated_rows=1,
        )

        _upsert_target(
            target_user_sdwt_prod="SDWT1",
            jira_template_key="common",
            jira_key="PROJ1",
        )
        _create_drone_sop(
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
            send_messenger=-1,
            send_mail=-1,
            metro_current_step="ST001",
        )

        result = services.run_drone_sop_pipeline_from_settings()
        self.assertEqual(result.candidates, 1)
        self.assertEqual(result.jira_created, 1)
        self.assertEqual(result.jira_updated_rows, 1)
        mock_run_jira.assert_called_once()

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_MAIL_SENDER="sender@example.com",
    )
    @patch("api.drone.services.inform.sop_inform.send_drone_sop_messenger_message")
    @patch("api.drone.services.inform.sop_inform.run_drone_sop_jira_create_from_rows")
    def test_inform_continues_messenger_when_jira_pipeline_fails(
        self,
        mock_run_jira: Mock,
        mock_messenger: Mock,
    ) -> None:
        """Jira 처리 예외가 발생해도 메신저 채널 처리가 계속되는지 확인합니다."""
        mock_run_jira.side_effect = RuntimeError("jira unavailable")

        _upsert_target(
            target_user_sdwt_prod="SDWT1",
            jira_template_key="common",
            jira_key="PROJ1",
            messenger_template_key="common",
            chatroom_id=12345,
        )
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
            send_messenger=0,
            send_mail=-1,
            metro_current_step="ST001",
        )

        result = services.run_drone_sop_pipeline_from_settings()
        self.assertEqual(result.candidates, 1)
        self.assertEqual(result.jira_created, 0)
        self.assertEqual(result.messenger_sent, 1)
        mock_run_jira.assert_called_once()
        mock_messenger.assert_called_once()

        refreshed = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(_sop_delivery_value(refreshed, "sendJira"), 0)
        self.assertIsNone(_sop_delivery_value(refreshed, "jiraReason"))
        self.assertEqual(_sop_delivery_value(refreshed, "sendMessenger"), 1)
        self.assertIsNotNone(_sop_delivery_value(refreshed, "informedAt"))
        messenger_delivery = DroneSopDelivery.objects.get(
            sop=sop,
            channel=DroneSopDelivery.Channels.MESSENGER,
        )
        self.assertEqual(messenger_delivery.sent_step, "ST001")

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_MAIL_SENDER="sender@example.com",
    )
    @patch("api.drone.services.inform.sop_inform.send_drone_sop_mail")
    def test_inform_sets_informed_at_when_mail_succeeds(self, mock_mail: Mock) -> None:
        """메일 전송 성공 시 informed_at이 설정되는지 확인합니다."""
        User = get_user_model()
        user = User.objects.create_user(sabun="S84001", password="test-password")
        user.email = "user84001@example.com"
        user.save(update_fields=["email"])
        _set_current_affiliation(user, user_sdwt_prod="SDWT1")

        _upsert_target(
            target_user_sdwt_prod="SDWT1",
            mail_template_key="common",
        )
        _create_target_recipient(
            target_user_sdwt_prod="SDWT1",
            channel=DroneSopTargetRecipient.Channels.MAIL,
            user=user,
        )

        sop = _create_drone_sop(
            line_id="L1",
            sdwt_prod="SDWT1",
            user_sdwt_prod="SDWT1",
            eqp_id="EQP1",
            chamber_ids="1",
            lot_id="LOT.1",
            main_step="MS",
            status="COMPLETE",
            comment="mail comment $@$ rule",
            target_user_sdwt_prod="SDWT1",
            needtosend=1,
            send_jira=-1,
            send_messenger=-1,
            send_mail=0,
            metro_current_step="ST001",
        )

        result = services.run_drone_sop_pipeline_from_settings()
        self.assertEqual(result.candidates, 1)
        mock_mail.assert_called_once()

        refreshed = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(_sop_delivery_value(refreshed, "sendMail"), 1)
        self.assertIsNotNone(_sop_delivery_value(refreshed, "informedAt"))
        mail_delivery = DroneSopDelivery.objects.get(
            sop=sop,
            channel=DroneSopDelivery.Channels.MAIL,
        )
        self.assertEqual(mail_delivery.sent_comment, "mail comment")
        self.assertEqual(mail_delivery.sent_step, "ST001")

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_MAIL_SENDER="sender@example.com",
    )
    @patch("api.drone.services.inform.sop_inform.send_drone_sop_mail")
    def test_inform_sends_mail_to_configured_delivery_target(self, mock_mail: Mock) -> None:
        """한 SOP 조합의 고정 target에만 메일을 발송합니다."""
        User = get_user_model()
        user_a = User.objects.create_user(sabun="S84011", password="test-password")
        user_a.email = "target-a@example.com"
        user_a.save(update_fields=["email"])

        _ensure_target_mapping(
            sdwt_prod="SDWT_MULTI",
            user_sdwt_prod="USR_MULTI",
            target_user_sdwt_prod="TARGET_A",
        )
        _upsert_target(
            target_user_sdwt_prod="TARGET_A",
            mail_template_key="common",
        )
        _create_target_recipient(
            target_user_sdwt_prod="TARGET_A",
            channel=DroneSopTargetRecipient.Channels.MAIL,
            user=user_a,
        )

        sop = _create_drone_sop(
            sdwt_prod="SDWT_MULTI",
            user_sdwt_prod="USR_MULTI",
            send_jira=-1,
            send_messenger=-1,
            send_mail=0,
            metro_current_step="ST001",
        )

        result = services.run_drone_sop_pipeline_from_settings()
        self.assertEqual(result.candidates, 1)
        self.assertEqual(result.mail_sent, 1)
        self.assertEqual(mock_mail.call_count, 1)
        self.assertEqual(
            mock_mail.call_args.kwargs.get("receiver_emails"),
            ["target-a@example.com"],
        )

        sop.refresh_from_db()
        deliveries = DroneSopDelivery.objects.filter(
            sop=sop,
            channel=DroneSopTargetRecipient.Channels.MAIL,
        ).order_by("channel")
        self.assertEqual(deliveries.count(), 1)
        self.assertEqual(
            [(sop.target_user_sdwt_prod, delivery.status) for delivery in deliveries],
            [
                ("TARGET_A", DroneSopDelivery.Statuses.SUCCESS),
            ],
        )

        refreshed = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(_sop_delivery_value(refreshed, "sendMail"), 1)
        self.assertIsNotNone(_sop_delivery_value(refreshed, "informedAt"))

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_MAIL_SENDER="sender@example.com",
    )
    @patch("api.drone.services.messenger.messenger_api.send_drone_sop_messenger_message")
    def test_inform_marks_messenger_disabled_without_failure(self, mock_messenger: Mock) -> None:
        """비활성화된 메신저 채널은 실패(-1) 없이 비활성 사유만 기록하는지 확인합니다."""
        _upsert_target(
            target_user_sdwt_prod="SDWT1",
            messenger_template_key="common",
            chatroom_id=12345,
            messenger_enabled=False,
        )

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
            send_jira=-1,
            send_messenger=0,
            send_mail=-1,
            metro_current_step="ST001",
        )

        result = services.run_drone_sop_pipeline_from_settings()
        self.assertEqual(result.candidates, 1)
        mock_messenger.assert_not_called()

        refreshed = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(_sop_delivery_value(refreshed, "sendMessenger"), 0)
        self.assertEqual(_sop_delivery_value(refreshed, "messengerReason"), "disabled_by_policy")

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_MAIL_SENDER="sender@example.com",
    )
    @patch("api.drone.services.mail.mail_sender.send_drone_sop_mail")
    def test_inform_marks_mail_disabled_without_failure(self, mock_mail: Mock) -> None:
        """비활성화된 메일 채널은 실패(-1) 없이 비활성 사유만 기록하는지 확인합니다."""
        _upsert_target(
            target_user_sdwt_prod="SDWT1",
            mail_template_key="common",
            mail_enabled=False,
        )

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
            send_jira=-1,
            send_messenger=-1,
            send_mail=0,
            metro_current_step="ST001",
        )

        result = services.run_drone_sop_pipeline_from_settings()
        self.assertEqual(result.candidates, 1)
        mock_mail.assert_not_called()

        refreshed = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(_sop_delivery_value(refreshed, "sendMail"), 0)
        self.assertEqual(_sop_delivery_value(refreshed, "mailReason"), "disabled_by_policy")

@override_settings(
    KNOX_MESSENGER_API_BASE_URL="http://example.local/messenger/",
    KNOX_MESSENGER_AUTHORIZATION="dummy-auth",
    KNOX_MESSENGER_SYSTEM_ID="dummy-system",
)
class DroneSopInformPolicyTestsPart3(TestCase):
    """DroneSopInformPolicyTests 분리 회귀 테스트 3부입니다."""

    def setUp(self) -> None:
        """테스트에 필요한 기본 매핑을 준비합니다."""

        _ensure_target_mapping(sdwt_prod="SDWT1", user_sdwt_prod="SDWT1")

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_MAIL_SENDER="sender@example.com",
    )
    @patch("api.drone.services.inform.sop_inform.send_drone_sop_messenger_message")
    @patch("api.drone.services.inform.sop_inform.messenger_services.create_chatroom")
    @patch("api.drone.services.inform.sop_inform.messenger_services.resolve_user_ids_by_single_ids")
    def test_inform_creates_chatroom_when_chatroom_id_missing(
        self,
        mock_resolve_user_ids: Mock,
        mock_create_chatroom: Mock,
        mock_messenger: Mock,
    ) -> None:
        """chatroom_id가 없으면 채팅방을 생성하고 전송하는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) Knox userID/채팅방 생성 mock 준비
        # -----------------------------------------------------------------------------
        mock_resolve_user_ids.return_value = ["user-001", "user-002"]
        mock_create_chatroom.return_value = 4567

        # -----------------------------------------------------------------------------
        # 2) 수신자 사용자/채널/SOP 데이터 준비
        # -----------------------------------------------------------------------------
        User = get_user_model()

        user_a = User.objects.create_user(sabun="S83001", password="test-password")
        user_a.knox_id = "knox-001"
        user_a.save(update_fields=["knox_id"])
        _set_current_affiliation(user_a, user_sdwt_prod="SDWT1")

        user_b = User.objects.create_user(sabun="S83002", password="test-password")
        user_b.knox_id = " knox-002 "
        user_b.save(update_fields=["knox_id"])
        _set_current_affiliation(user_b, user_sdwt_prod="SDWT1")

        _upsert_target(
            target_user_sdwt_prod="SDWT1",
            messenger_template_key="common",
        )
        _create_target_recipient(
            target_user_sdwt_prod="SDWT1",
            channel=DroneSopTargetRecipient.Channels.MESSENGER,
            user=user_a,
        )
        _create_target_recipient(
            target_user_sdwt_prod="SDWT1",
            channel=DroneSopTargetRecipient.Channels.MESSENGER,
            user=user_b,
        )

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
            send_jira=-1,
            send_messenger=0,
            send_mail=-1,
            metro_current_step="ST001",
        )

        # -----------------------------------------------------------------------------
        # 3) 멀티 채널 전송 실행
        # -----------------------------------------------------------------------------
        result = services.run_drone_sop_pipeline_from_settings()
        self.assertEqual(result.candidates, 1)
        self.assertEqual(result.messenger_sent, 1)

        # -----------------------------------------------------------------------------
        # 4) 채팅방 생성/전송/상태 반영 검증
        # -----------------------------------------------------------------------------
        mock_resolve_user_ids.assert_called_once()
        self.assertEqual(
            mock_resolve_user_ids.call_args.kwargs.get("single_ids"),
            ["knox-001", "knox-002"],
        )

        mock_create_chatroom.assert_called_once()
        self.assertEqual(
            mock_create_chatroom.call_args.kwargs.get("user_ids"),
            ["user-001", "user-002"],
        )
        self.assertEqual(
            mock_create_chatroom.call_args.kwargs.get("title"),
            "Drone SOP - SDWT1",
        )

        mock_messenger.assert_called_once()
        self.assertEqual(
            mock_messenger.call_args.kwargs.get("chatroom_id"),
            4567,
        )
        self.assertEqual(
            mock_messenger.call_args.kwargs.get("messenger_template_key"),
            "common",
        )

        refreshed_channel = DroneSopTargetChannelConfig.objects.get(
            target__target_user_sdwt_prod="SDWT1",
            channel=DroneSopTargetChannelConfig.Channels.MESSENGER,
        )
        self.assertEqual(refreshed_channel.chatroom_id, 4567)

        refreshed_sop = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(_sop_delivery_value(refreshed_sop, "sendMessenger"), 1)
        self.assertIsNone(_sop_delivery_value(refreshed_sop, "messengerReason"))

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_MAIL_SENDER="sender@example.com",
    )
    @patch("api.drone.services.inform.sop_inform.send_drone_sop_messenger_message")
    @patch("api.drone.services.inform.sop_inform.messenger_services.create_chatroom")
    @patch("api.drone.services.inform.sop_inform.messenger_services.resolve_user_ids_by_single_ids")
    def test_inform_creates_chatroom_once_per_target_with_multiple_rows(
        self,
        mock_resolve_user_ids: Mock,
        mock_create_chatroom: Mock,
        mock_messenger: Mock,
    ) -> None:
        """동일 target 다건 처리 시 채팅방을 1회만 생성하는지 확인합니다."""
        mock_resolve_user_ids.return_value = ["user-001", "user-002"]
        mock_create_chatroom.return_value = 4567

        User = get_user_model()
        user_a = User.objects.create_user(sabun="S83003", password="test-password")
        user_a.knox_id = "knox-003"
        user_a.save(update_fields=["knox_id"])
        _set_current_affiliation(user_a, user_sdwt_prod="SDWT1")

        user_b = User.objects.create_user(sabun="S83004", password="test-password")
        user_b.knox_id = "knox-004"
        user_b.save(update_fields=["knox_id"])
        _set_current_affiliation(user_b, user_sdwt_prod="SDWT1")

        _upsert_target(
            target_user_sdwt_prod="SDWT1",
            messenger_template_key="common",
        )
        _create_target_recipient(
            target_user_sdwt_prod="SDWT1",
            channel=DroneSopTargetRecipient.Channels.MESSENGER,
            user=user_a,
        )
        _create_target_recipient(
            target_user_sdwt_prod="SDWT1",
            channel=DroneSopTargetRecipient.Channels.MESSENGER,
            user=user_b,
        )

        sop_1 = _create_drone_sop(
            line_id="L1",
            sdwt_prod="SDWT1",
            user_sdwt_prod="SDWT1",
            eqp_id="EQP1",
            chamber_ids="1",
            lot_id="LOT.11",
            main_step="MS",
            status="COMPLETE",
            needtosend=1,
            send_jira=-1,
            send_messenger=0,
            send_mail=-1,
            metro_current_step="ST001",
        )
        sop_2 = _create_drone_sop(
            line_id="L1",
            sdwt_prod="SDWT1",
            user_sdwt_prod="SDWT1",
            eqp_id="EQP1",
            chamber_ids="1",
            lot_id="LOT.12",
            main_step="MS",
            status="COMPLETE",
            needtosend=1,
            send_jira=-1,
            send_messenger=0,
            send_mail=-1,
            metro_current_step="ST001",
        )

        result = services.run_drone_sop_pipeline_from_settings()
        self.assertEqual(result.candidates, 2)
        self.assertEqual(result.messenger_sent, 2)

        mock_resolve_user_ids.assert_called_once()
        mock_create_chatroom.assert_called_once()
        self.assertEqual(mock_messenger.call_count, 2)

        refreshed_channel = DroneSopTargetChannelConfig.objects.get(
            target__target_user_sdwt_prod="SDWT1",
            channel=DroneSopTargetChannelConfig.Channels.MESSENGER,
        )
        self.assertEqual(refreshed_channel.chatroom_id, 4567)

        refreshed_1 = DroneSOP.objects.get(id=sop_1.id)
        refreshed_2 = DroneSOP.objects.get(id=sop_2.id)
        self.assertEqual(_sop_delivery_value(refreshed_1, "sendMessenger"), 1)
        self.assertEqual(_sop_delivery_value(refreshed_2, "sendMessenger"), 1)

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_MAIL_SENDER="sender@example.com",
    )
    @patch("api.drone.services.inform.sop_inform.send_drone_sop_messenger_message")
    @patch("api.drone.services.inform.sop_inform.messenger_services.create_chatroom")
    @patch("api.drone.services.inform.sop_inform.messenger_services.resolve_user_ids_by_single_ids")
    def test_inform_reuses_chatroom_id_when_present(
        self,
        mock_resolve_user_ids: Mock,
        mock_create_chatroom: Mock,
        mock_messenger: Mock,
    ) -> None:
        """chatroom_id가 있으면 채팅방 생성 없이 재사용하는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 채널/SOP 데이터 준비
        # -----------------------------------------------------------------------------
        _upsert_target(
            target_user_sdwt_prod="SDWT1",
            messenger_template_key="common",
            chatroom_id=12345,
        )

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
            send_jira=-1,
            send_messenger=0,
            send_mail=-1,
            metro_current_step="ST001",
        )

        # -----------------------------------------------------------------------------
        # 2) 멀티 채널 전송 실행
        # -----------------------------------------------------------------------------
        result = services.run_drone_sop_pipeline_from_settings()
        self.assertEqual(result.candidates, 1)
        self.assertEqual(result.messenger_sent, 1)

        # -----------------------------------------------------------------------------
        # 3) 채팅방 재사용/전송 검증
        # -----------------------------------------------------------------------------
        mock_resolve_user_ids.assert_not_called()
        mock_create_chatroom.assert_not_called()
        mock_messenger.assert_called_once()
        self.assertEqual(
            mock_messenger.call_args.kwargs.get("chatroom_id"),
            12345,
        )
        self.assertEqual(
            mock_messenger.call_args.kwargs.get("messenger_template_key"),
            "common",
        )

        refreshed_channel = DroneSopTargetChannelConfig.objects.get(
            target__target_user_sdwt_prod="SDWT1",
            channel=DroneSopTargetChannelConfig.Channels.MESSENGER,
        )
        self.assertEqual(refreshed_channel.chatroom_id, 12345)

        refreshed_sop = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(_sop_delivery_value(refreshed_sop, "sendMessenger"), 1)
        self.assertIsNone(_sop_delivery_value(refreshed_sop, "messengerReason"))

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_MAIL_SENDER="sender@example.com",
    )
    @patch("api.drone.services.inform.sop_inform.send_drone_sop_messenger_message")
    @patch("api.drone.services.inform.sop_inform.messenger_services.create_chatroom")
    @patch("api.drone.services.inform.sop_inform.messenger_services.resolve_user_ids_by_single_ids")
    def test_inform_force_new_chatroom_recreates_and_resets_flag(
        self,
        mock_resolve_user_ids: Mock,
        mock_create_chatroom: Mock,
        mock_messenger: Mock,
    ) -> None:
        """새 채팅방 생성 요청이 있으면 기존 chatroom_id 대신 새 방을 만들고 플래그를 해제합니다."""
        mock_resolve_user_ids.return_value = ["user-101", "user-102"]
        mock_create_chatroom.return_value = 4567

        User = get_user_model()
        user_a = User.objects.create_user(sabun="S83101", password="test-password")
        user_a.knox_id = "knox-101"
        user_a.save(update_fields=["knox_id"])
        _set_current_affiliation(user_a, user_sdwt_prod="SDWT1")

        user_b = User.objects.create_user(sabun="S83102", password="test-password")
        user_b.knox_id = "knox-102"
        user_b.save(update_fields=["knox_id"])
        _set_current_affiliation(user_b, user_sdwt_prod="SDWT1")

        _upsert_target(
            target_user_sdwt_prod="SDWT1",
            messenger_template_key="common",
            chatroom_id=12345,
            force_new_chatroom=True,
        )
        _create_target_recipient(
            target_user_sdwt_prod="SDWT1",
            channel=DroneSopTargetRecipient.Channels.MESSENGER,
            user=user_a,
        )
        _create_target_recipient(
            target_user_sdwt_prod="SDWT1",
            channel=DroneSopTargetRecipient.Channels.MESSENGER,
            user=user_b,
        )

        _create_drone_sop(
            line_id="L1",
            sdwt_prod="SDWT1",
            user_sdwt_prod="SDWT1",
            eqp_id="EQP1",
            chamber_ids="1",
            lot_id="LOT.2",
            main_step="MS",
            status="COMPLETE",
            needtosend=1,
            send_jira=-1,
            send_messenger=0,
            send_mail=-1,
            metro_current_step="ST001",
        )

        result = services.run_drone_sop_pipeline_from_settings()
        self.assertEqual(result.candidates, 1)
        self.assertEqual(result.messenger_sent, 1)

        mock_resolve_user_ids.assert_called_once()
        mock_create_chatroom.assert_called_once()
        mock_messenger.assert_called_once()
        self.assertEqual(mock_messenger.call_args.kwargs.get("chatroom_id"), 4567)

        refreshed_channel = DroneSopTargetChannelConfig.objects.get(
            target__target_user_sdwt_prod="SDWT1",
            channel=DroneSopTargetChannelConfig.Channels.MESSENGER,
        )
        self.assertEqual(refreshed_channel.chatroom_id, 4567)
        self.assertFalse(refreshed_channel.force_new_chatroom)
