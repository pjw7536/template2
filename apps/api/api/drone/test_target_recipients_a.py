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

class DroneSopTargetRecipientTestsPart1(TestCase):
    """DroneSopTargetRecipientTests 분리 회귀 테스트 1부입니다."""

    def setUp(self) -> None:
        """테스트용 사용자와 소속 옵션을 준비합니다."""

        _allow_test_scope_access(self)
        User = get_user_model()
        self.actor = User.objects.create_superuser(
            sabun="S71000",
            password="test-password",
            knox_id="knox-71000",
        )
        self.mail_user = User.objects.create_user(
            sabun="S71001",
            password="test-password",
            knox_id="knox-71001",
            email="mail-user@example.com",
        )
        _set_current_affiliation(self.mail_user, user_sdwt_prod="PHOTO_B")
        self.same_group_user = User.objects.create_user(
            sabun="S71002",
            password="test-password",
            knox_id="knox-71002",
            email="same-group@example.com",
        )
        _set_current_affiliation(self.same_group_user, department="Dept", line="L1", user_sdwt_prod="ETCH_A")
        account_services.ensure_affiliation_option(
            department="Dept",
            line="L1",
            user_sdwt_prod="ETCH_A",
        )

    def test_mail_receiver_lookup_uses_drone_recipients_not_user_affiliation(self) -> None:
        """메일 수신자 조회가 account_user.user_sdwt_prod 직접 조회를 사용하지 않는지 확인합니다."""

        services.replace_drone_sop_channel_recipients(
            line_id="L1",
            target_user_sdwt_prod="ETCH_A",
            channel="mail",
            user_ids=[self.mail_user.id],
            actor=self.actor,
        )

        receiver_emails = selectors.list_mail_receiver_emails_for_user_sdwt_prod(
            line_id="L1",
            user_sdwt_prod="ETCH_A",
        )

        self.assertEqual(receiver_emails, ["mail-user@example.com"])
        self.assertNotIn("same-group@example.com", receiver_emails)

    def test_replace_allows_external_snapshot_recipients(self) -> None:
        """외부 소속 스냅샷 사용자를 메일/메신저 수신인으로 저장할 수 있어야 합니다."""

        account_services.sync_external_affiliations(
            records=[
                {
                    "knox_id": "external-71003",
                    "username": "외부사용자",
                    "department": "ExtDept",
                    "user_sdwt_prod": "ETCH_A",
                    "source_updated_at": timezone.now(),
                }
            ]
        )

        mail_result = services.replace_drone_sop_channel_recipients(
            line_id="L1",
            target_user_sdwt_prod="ETCH_A",
            channel="mail",
            user_ids=[self.mail_user.id],
            external_knox_ids=["external-71003"],
            actor=self.actor,
        )
        services.replace_drone_sop_channel_recipients(
            line_id="L1",
            target_user_sdwt_prod="ETCH_A",
            channel="messenger",
            user_ids=[],
            external_knox_ids=["EXTERNAL-71003"],
            actor=self.actor,
        )

        self.assertEqual(
            selectors.list_mail_receiver_emails_for_user_sdwt_prod(
                line_id="L1",
                user_sdwt_prod="ETCH_A",
            ),
            ["mail-user@example.com", "external-71003@samsung.com"],
        )
        self.assertEqual(
            selectors.list_messenger_receiver_knox_ids_for_user_sdwt_prod(
                line_id="L1",
                user_sdwt_prod="ETCH_A",
            ),
            ["external-71003"],
        )
        external_rows = [row for row in mail_result["recipients"] if row["recipientType"] == "external"]
        self.assertEqual(len(external_rows), 1)
        self.assertEqual(external_rows[0]["recipientKey"], "external:external-71003")
        self.assertEqual(external_rows[0]["username"], "외부사용자")
        self.assertEqual(external_rows[0]["displayName"], "외부사용자")
        self.assertEqual(external_rows[0]["knoxId"], "external-71003")
        self.assertEqual(external_rows[0]["email"], "external-71003@samsung.com")

    def test_replace_mixed_recipients_allows_add_and_remove(self) -> None:
        """가입/미가입 수신인이 섞인 목록에서도 추가와 제거가 저장되어야 합니다."""

        account_services.sync_external_affiliations(
            records=[
                {
                    "knox_id": "external-71009",
                    "username": "제거외부사용자",
                    "department": "ExtDept",
                    "user_sdwt_prod": "ETCH_A",
                    "source_updated_at": timezone.now(),
                },
                {
                    "knox_id": "external-71010",
                    "username": "유지외부사용자",
                    "department": "ExtDept",
                    "user_sdwt_prod": "ETCH_A",
                    "source_updated_at": timezone.now(),
                },
            ]
        )
        for channel in [
            DroneSopTargetRecipient.Channels.MAIL,
            DroneSopTargetRecipient.Channels.MESSENGER,
        ]:
            with self.subTest(channel=channel):
                services.replace_drone_sop_channel_recipients(
                    line_id="L1",
                    target_user_sdwt_prod="ETCH_A",
                    channel=channel,
                    user_ids=[self.same_group_user.id],
                    external_knox_ids=["external-71009", "external-71010"],
                    actor=self.actor,
                )

                result = services.replace_drone_sop_channel_recipients(
                    line_id="L1",
                    target_user_sdwt_prod="ETCH_A",
                    channel=channel,
                    user_ids=[self.mail_user.id],
                    external_knox_ids=["external-71010"],
                    actor=self.actor,
                )

                recipient_keys = [row["recipientKey"] for row in result["recipients"]]
                self.assertCountEqual(recipient_keys, [f"user:{self.mail_user.id}", "external:external-71010"])
                self.assertFalse(
                    DroneSopTargetRecipient.objects.filter(
                        target__target_user_sdwt_prod="ETCH_A",
                        channel=channel,
                        user=self.same_group_user,
                    ).exists()
                )
                self.assertFalse(
                    DroneSopTargetRecipient.objects.filter(
                        target__target_user_sdwt_prod="ETCH_A",
                        channel=channel,
                        external_knox_id="external-71009",
                    ).exists()
                )

    def test_replace_rejects_unknown_external_snapshot_recipient(self) -> None:
        """외부 스냅샷에 없는 knox_id는 수신인으로 저장할 수 없어야 합니다."""

        with self.assertRaisesMessage(ValueError, "external recipients not found"):
            services.replace_drone_sop_channel_recipients(
                line_id="L1",
                target_user_sdwt_prod="ETCH_A",
                channel="mail",
                user_ids=[],
                external_knox_ids=["missing-71004"],
                actor=self.actor,
            )

    def test_replace_promotes_joined_external_payload_to_user_recipient(self) -> None:
        """가입자와 겹치는 externalKnoxIds는 user 수신인으로 저장해야 합니다."""

        account_services.sync_external_affiliations(
            records=[
                {
                    "knox_id": "external-71005",
                    "username": "가입전외부사용자",
                    "department": "ExtDept",
                    "user_sdwt_prod": "ETCH_A",
                    "source_updated_at": timezone.now(),
                }
            ]
        )
        User = get_user_model()
        joined_user = User.objects.create_user(
            sabun="S71005",
            password="test-password",
            knox_id="EXTERNAL-71005",
            email="external-71005@samsung.com",
        )

        result = services.replace_drone_sop_channel_recipients(
            line_id="L1",
            target_user_sdwt_prod="ETCH_A",
            channel="mail",
            user_ids=[],
            external_knox_ids=["external-71005"],
            actor=self.actor,
        )

        self.assertEqual([row["recipientType"] for row in result["recipients"]], ["user"])
        self.assertEqual(result["recipients"][0]["userId"], joined_user.id)
        self.assertTrue(
            DroneSopTargetRecipient.objects.filter(
                target__target_user_sdwt_prod="ETCH_A",
                channel=DroneSopTargetRecipient.Channels.MAIL,
                user_id=joined_user.id,
                external_knox_id="",
            ).exists()
        )

    def test_user_creation_promotes_external_recipient_rows(self) -> None:
        """가입 사용자의 knox_id가 기존 외부 수신인과 같으면 user FK row로 승격되어야 합니다."""

        _create_target_recipient(
            target_user_sdwt_prod="ETCH_A",
            channel=DroneSopTargetRecipient.Channels.MAIL,
            external_knox_id="external-71007",
        )

        User = get_user_model()
        joined_user = User.objects.create_user(
            sabun="S71007",
            password="test-password",
            knox_id="external-71007",
            email="external-71007@samsung.com",
        )

        recipient = DroneSopTargetRecipient.objects.get(
            target__target_user_sdwt_prod="ETCH_A",
            channel=DroneSopTargetRecipient.Channels.MAIL,
        )
        self.assertEqual(recipient.user_id, joined_user.id)
        self.assertEqual(recipient.external_knox_id, "")
        self.assertEqual(
            selectors.list_mail_receiver_emails_for_user_sdwt_prod(
                line_id="L1",
                user_sdwt_prod="ETCH_A",
            ),
            ["external-71007@samsung.com"],
        )

    def test_user_knox_id_update_promotes_external_recipient_rows(self) -> None:
        """가입 후 knox_id가 채워지는 흐름도 외부 수신인 승격을 수행해야 합니다."""

        _create_target_recipient(
            target_user_sdwt_prod="ETCH_A",
            channel=DroneSopTargetRecipient.Channels.MESSENGER,
            external_knox_id="external-71008",
        )

        User = get_user_model()
        joined_user = User.objects.create_user(
            sabun="S71008",
            password="test-password",
            email="external-71008@samsung.com",
        )
        joined_user.knox_id = "external-71008"
        joined_user.save(update_fields=["knox_id"])

        recipient = DroneSopTargetRecipient.objects.get(
            target__target_user_sdwt_prod="ETCH_A",
            channel=DroneSopTargetRecipient.Channels.MESSENGER,
        )
        self.assertEqual(recipient.user_id, joined_user.id)
        self.assertEqual(recipient.external_knox_id, "")
        self.assertEqual(
            selectors.list_messenger_receiver_knox_ids_for_user_sdwt_prod(
                line_id="L1",
                user_sdwt_prod="ETCH_A",
            ),
            ["external-71008"],
        )

    def test_same_target_cannot_be_reused_by_another_line(self) -> None:
        """같은 target_user_sdwt_prod는 다른 line 수신인 설정에 재사용할 수 없어야 합니다."""

        account_services.ensure_affiliation_option(
            department="Dept",
            line="L2",
            user_sdwt_prod="PHOTO_B",
        )
        services.replace_drone_sop_channel_recipients(
            line_id="L1",
            target_user_sdwt_prod="ETCH_A",
            channel="mail",
            user_ids=[self.mail_user.id],
            actor=self.actor,
        )
        with self.assertRaisesMessage(ValueError, "targetUserSdwtProd already belongs to another line"):
            services.replace_drone_sop_channel_recipients(
                line_id="L2",
                target_user_sdwt_prod="ETCH_A",
                channel="mail",
                user_ids=[self.same_group_user.id],
                actor=self.actor,
            )

        self.assertEqual(
            selectors.list_mail_receiver_emails_for_user_sdwt_prod(
                line_id="L1",
                user_sdwt_prod="ETCH_A",
            ),
            ["mail-user@example.com"],
        )

    def test_notification_recipient_get_uses_existing_target_line(self) -> None:
        """기존 target 조회는 요청 line이 달라도 저장된 line 수신인을 반환해야 합니다."""

        services.replace_drone_sop_channel_recipients(
            line_id="L1",
            target_user_sdwt_prod="ETCH_A",
            channel="mail",
            user_ids=[self.mail_user.id],
            actor=self.actor,
        )

        self.client.force_login(self.actor)
        response = self.client.get(
            reverse("line-dashboard-notification-recipients"),
            {
                "lineId": "L2",
                "targetUserSdwtProd": "ETCH_A",
                "channel": "mail",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["lineId"], "L1")
        self.assertEqual(payload["targetUserSdwtProd"], "ETCH_A")
        self.assertEqual([row["userId"] for row in payload["recipients"]], [self.mail_user.id])

    def test_replace_keeps_existing_target_source_payload_custom(self) -> None:
        """Drone runtime target source는 account 소속과 무관하게 custom으로 표시합니다."""

        target = _upsert_target(
            line_id="L1",
            target_user_sdwt_prod="ETCH_A",
        )

        services.replace_drone_sop_channel_recipients(
            line_id="L1",
            target_user_sdwt_prod="ETCH_A",
            channel="mail",
            user_ids=[self.mail_user.id],
            actor=self.actor,
        )

        target.refresh_from_db()
        self.assertEqual(target.line_id, "L1")
        targets = selectors.list_drone_sop_notification_targets_for_line(line_id="L1")
        target_row = next(row for row in targets if row["targetUserSdwtProd"] == "ETCH_A")
        self.assertEqual(target_row["source"], DroneSopTarget.Sources.CUSTOM)

    def test_replace_allows_custom_target_without_affiliation(self) -> None:
        """외부 소속표에 없는 커스텀 target도 Drone target으로 저장할 수 있어야 합니다."""

        custom_target = "CUSTOM_TARGET"

        result = services.replace_drone_sop_channel_recipients(
            line_id="L1",
            target_user_sdwt_prod=custom_target,
            channel="mail",
            user_ids=[self.mail_user.id],
            actor=self.actor,
        )

        self.assertTrue(selectors.affiliation_exists_for_user_sdwt_prod(user_sdwt_prod=custom_target))
        self.assertEqual(result["lineId"], "L1")
        self.assertEqual(result["targetUserSdwtProd"], custom_target)
        self.assertEqual(result["recipients"][0]["userId"], self.mail_user.id)
        target = selectors.get_drone_sop_channel_by_target_user_sdwt_prod(
            target_user_sdwt_prod=custom_target
        )
        self.assertIsNotNone(target)
        if target is None:
            return
        self.assertEqual(target.line_id, "L1")
        targets = selectors.list_drone_sop_notification_targets_for_line(line_id="L1")
        target_row = next(row for row in targets if row["targetUserSdwtProd"] == custom_target)
        self.assertEqual(target_row["source"], DroneSopTarget.Sources.CUSTOM)
        self.assertEqual(
            selectors.list_mail_receiver_emails_for_user_sdwt_prod(
                line_id="L1",
                user_sdwt_prod=custom_target,
            ),
            ["mail-user@example.com"],
        )

    def test_replace_allows_custom_target_for_new_line(self) -> None:
        """커스텀 target은 account에 없는 신규 line_id에도 생성할 수 있습니다."""

        result = services.replace_drone_sop_channel_recipients(
            line_id="CUSTOM_LINE",
            target_user_sdwt_prod="CUSTOM_TARGET",
            channel="mail",
            user_ids=[self.mail_user.id],
            actor=self.actor,
        )

        self.assertEqual(result["lineId"], "CUSTOM_LINE")
        self.assertTrue(
            DroneSopTarget.objects.filter(
                line_id="CUSTOM_LINE",
                target_user_sdwt_prod="CUSTOM_TARGET",
            ).exists()
        )

class DroneSopTargetRecipientTestsPart2(TestCase):
    """DroneSopTargetRecipientTests 분리 회귀 테스트 2부입니다."""

    def setUp(self) -> None:
        """테스트용 사용자와 소속 옵션을 준비합니다."""

        _allow_test_scope_access(self)
        User = get_user_model()
        self.actor = User.objects.create_superuser(
            sabun="S71000",
            password="test-password",
            knox_id="knox-71000",
        )
        self.mail_user = User.objects.create_user(
            sabun="S71001",
            password="test-password",
            knox_id="knox-71001",
            email="mail-user@example.com",
        )
        _set_current_affiliation(self.mail_user, user_sdwt_prod="PHOTO_B")
        self.same_group_user = User.objects.create_user(
            sabun="S71002",
            password="test-password",
            knox_id="knox-71002",
            email="same-group@example.com",
        )
        _set_current_affiliation(self.same_group_user, department="Dept", line="L1", user_sdwt_prod="ETCH_A")
        account_services.ensure_affiliation_option(
            department="Dept",
            line="L1",
            user_sdwt_prod="ETCH_A",
        )

    def test_replace_hard_deletes_removed_recipient_rows(self) -> None:
        """수신인 저장이 제외된 기존 row를 삭제하는지 확인합니다."""

        recipient = _create_target_recipient(
            target_user_sdwt_prod="ETCH_A",
            channel=DroneSopTargetRecipient.Channels.MAIL,
            user=self.same_group_user,
        )

        result = services.replace_drone_sop_channel_recipients(
            line_id="L1",
            target_user_sdwt_prod="ETCH_A",
            channel="mail",
            user_ids=[self.mail_user.id],
            actor=self.actor,
        )

        self.assertFalse(DroneSopTargetRecipient.objects.filter(id=recipient.id).exists())
        self.assertEqual(len(result["recipients"]), 1)
        self.assertEqual(result["recipients"][0]["userId"], self.mail_user.id)

        result = services.replace_drone_sop_channel_recipients(
            line_id="L1",
            target_user_sdwt_prod="ETCH_A",
            channel="mail",
            user_ids=[self.same_group_user.id],
            actor=self.actor,
        )

        self.assertFalse(DroneSopTargetRecipient.objects.filter(id=recipient.id).exists())
        new_recipient = DroneSopTargetRecipient.objects.get(
            target__target_user_sdwt_prod="ETCH_A",
            channel=DroneSopTargetRecipient.Channels.MAIL,
            user=self.same_group_user,
        )
        self.assertNotEqual(new_recipient.id, recipient.id)
        self.assertEqual(len(result["recipients"]), 1)
        self.assertEqual(result["recipients"][0]["userId"], self.same_group_user.id)

    def test_lock_recipient_target_for_replace_uses_row_lock(self) -> None:
        """수신인 교체용 target 잠금이 SELECT FOR UPDATE를 사용하는지 확인합니다."""

        if not connection.features.has_select_for_update:
            self.skipTest("이 DB backend는 SELECT FOR UPDATE를 지원하지 않습니다.")

        target = _upsert_target(
            line_id="L1",
            target_user_sdwt_prod="LOCK_TARGET",
        )

        with transaction.atomic(), CaptureQueriesContext(connection) as captured_queries:
            locked_target = recipient_services._lock_recipient_target_for_replace(target_id=target.id)

        self.assertEqual(locked_target.id, target.id)
        sql = "\n".join(query["sql"] for query in captured_queries.captured_queries)
        self.assertIn('FROM "drone_sop_target"', sql)
        self.assertIn("FOR UPDATE", sql)

    @patch(
        "api.drone.services.channels.recipients._lock_recipient_target_for_replace",
        wraps=recipient_services._lock_recipient_target_for_replace,
    )
    def test_replace_locks_target_row_before_replacing_recipients(self, mock_lock_target: Mock) -> None:
        """수신인 교체가 target row 잠금을 기준으로 수행되는지 확인합니다."""

        services.replace_drone_sop_channel_recipients(
            line_id="L1",
            target_user_sdwt_prod="ETCH_A",
            channel="mail",
            user_ids=[self.mail_user.id],
            actor=self.actor,
        )

        target = selectors.get_drone_sop_channel_by_target_user_sdwt_prod(target_user_sdwt_prod="ETCH_A")
        self.assertIsNotNone(target)
        if target is None:
            return
        mock_lock_target.assert_called_once_with(target_id=target.id)

    def test_replace_rejects_invalid_user_ids_in_service_layer(self) -> None:
        """서비스 직접 호출도 잘못된 user_ids를 명시적으로 거부해야 합니다."""

        with self.assertRaisesMessage(ValueError, "user_ids must contain only integers"):
            services.replace_drone_sop_channel_recipients(
                line_id="L1",
                target_user_sdwt_prod="ETCH_A",
                channel="mail",
                user_ids=["invalid"],
                actor=self.actor,
            )

        with self.assertRaisesMessage(ValueError, "user_ids must contain only positive integers"):
            services.replace_drone_sop_channel_recipients(
                line_id="L1",
                target_user_sdwt_prod="ETCH_A",
                channel="mail",
                user_ids=[-1],
                actor=self.actor,
            )

        with self.assertRaisesMessage(ValueError, "user_ids must contain only integers"):
            services.replace_drone_sop_channel_recipients(
                line_id="L1",
                target_user_sdwt_prod="ETCH_A",
                channel="mail",
                user_ids=[True],
                actor=self.actor,
            )

        with self.assertRaisesMessage(ValueError, "user_ids must contain only integers"):
            services.replace_drone_sop_channel_recipients(
                line_id="L1",
                target_user_sdwt_prod="ETCH_A",
                channel="mail",
                user_ids=[1.0],
                actor=self.actor,
            )

        with self.assertRaisesMessage(ValueError, "user_ids must be a list"):
            services.replace_drone_sop_channel_recipients(
                line_id="L1",
                target_user_sdwt_prod="ETCH_A",
                channel="mail",
                user_ids="12",
                actor=self.actor,
            )

        self.assertFalse(
            DroneSopTargetRecipient.objects.filter(
                target__target_user_sdwt_prod="ETCH_A",
                channel=DroneSopTargetRecipient.Channels.MAIL,
            ).exists()
        )

    def test_get_or_create_recovers_when_concurrent_create_already_inserted_row(self) -> None:
        """동시 요청이 같은 수신인을 먼저 생성해도 기존 row를 재조회해 성공 처리해야 합니다."""

        existing = _create_target_recipient(
            target_user_sdwt_prod="ETCH_A",
            channel=DroneSopTargetRecipient.Channels.MAIL,
            user=self.mail_user,
        )

        with patch(
            "api.drone.services.channels.recipients.DroneSopTargetRecipient.objects.create",
            side_effect=IntegrityError("duplicate key"),
        ):
            recipient = recipient_services._get_or_create_recipient_row(
                target_user_sdwt_prod="ETCH_A",
                channel=DroneSopTargetRecipient.Channels.MAIL,
                user_id=self.mail_user.id,
                actor=self.actor,
            )

        self.assertEqual(recipient.id, existing.id)

    def test_get_or_create_reraises_integrity_error_without_duplicate_row(self) -> None:
        """동시 생성 row가 없으면 원래 IntegrityError를 숨기지 않아야 합니다."""

        with patch(
            "api.drone.services.channels.recipients.DroneSopTargetRecipient.objects.create",
            side_effect=IntegrityError("foreign key failure"),
        ):
            with self.assertRaisesMessage(IntegrityError, "foreign key failure"):
                recipient_services._get_or_create_recipient_row(
                    target_user_sdwt_prod="ETCH_A",
                    channel=DroneSopTargetRecipient.Channels.MAIL,
                    user_id=self.mail_user.id,
                    actor=self.actor,
                )

    @patch("api.drone.services.channels.recipients._get_or_create_recipient_row")
    def test_replace_handles_concurrent_create_fallback_result(self, mock_get_or_create: Mock) -> None:
        """public service도 동시 생성 fallback 결과를 받아 기존 row로 처리해야 합니다."""

        def return_existing_row(**kwargs: object) -> DroneSopTargetRecipient:
            return _create_target_recipient(
                target_user_sdwt_prod=str(kwargs["target_user_sdwt_prod"]),
                channel=str(kwargs["channel"]),
                user_id=int(kwargs["user_id"]),
            )

        mock_get_or_create.side_effect = return_existing_row

        result = services.replace_drone_sop_channel_recipients(
            line_id="L1",
            target_user_sdwt_prod="ETCH_A",
            channel="mail",
            user_ids=[self.mail_user.id],
            actor=self.actor,
        )

        recipient = DroneSopTargetRecipient.objects.get(
            target__target_user_sdwt_prod="ETCH_A",
            channel=DroneSopTargetRecipient.Channels.MAIL,
            user=self.mail_user,
        )
        self.assertEqual(recipient.user_id, self.mail_user.id)
        self.assertEqual([row["userId"] for row in result["recipients"]], [self.mail_user.id])

    def test_notification_recipient_endpoint_replaces_mail_recipients(self) -> None:
        """수신인 API가 최종 userIds 스냅샷으로 메일 수신인을 저장하는지 확인합니다."""

        self.client.force_login(self.actor)
        response = self.client.put(
            reverse("line-dashboard-notification-recipients"),
            data=json.dumps(
                {
                    "lineId": "L1",
                    "targetUserSdwtProd": "ETCH_A",
                    "channel": "mail",
                    "userIds": [self.mail_user.id],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["lineId"], "L1")
        self.assertEqual(payload["targetUserSdwtProd"], "ETCH_A")
        self.assertEqual(payload["channel"], "mail")
        self.assertEqual([row["userId"] for row in payload["recipients"]], [self.mail_user.id])

    def test_notification_recipient_endpoint_replaces_external_recipients(self) -> None:
        """수신인 API가 externalKnoxIds 스냅샷을 함께 저장하는지 확인합니다."""

        account_services.sync_external_affiliations(
            records=[
                {
                    "knox_id": "external-71006",
                    "username": "외부조회사용자",
                    "department": "ExtDept",
                    "user_sdwt_prod": "ETCH_A",
                    "source_updated_at": timezone.now(),
                }
            ]
        )

        self.client.force_login(self.actor)
        response = self.client.put(
            reverse("line-dashboard-notification-recipients"),
            data=json.dumps(
                {
                    "lineId": "L1",
                    "targetUserSdwtProd": "ETCH_A",
                    "channel": "mail",
                    "userIds": [self.mail_user.id],
                    "externalKnoxIds": ["external-71006"],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        recipient_keys = [row["recipientKey"] for row in payload["recipients"]]
        self.assertCountEqual(recipient_keys, [f"user:{self.mail_user.id}", "external:external-71006"])
        external_rows = [row for row in payload["recipients"] if row["recipientType"] == "external"]
        self.assertEqual(external_rows[0]["username"], "외부조회사용자")
        self.assertEqual(external_rows[0]["displayName"], "외부조회사용자")
        self.assertEqual(external_rows[0]["knoxId"], "external-71006")
        self.assertTrue(
            DroneSopTargetRecipient.objects.filter(
                target__target_user_sdwt_prod="ETCH_A",
                channel=DroneSopTargetRecipient.Channels.MAIL,
                external_knox_id="external-71006",
            ).exists()
        )

    def test_notification_recipient_endpoint_returns_mail_recipients(self) -> None:
        """수신인 API가 target/channel의 등록된 메일 수신인을 반환하는지 확인합니다."""

        _create_target_recipient(
            target_user_sdwt_prod="ETCH_A",
            channel=DroneSopTargetRecipient.Channels.MAIL,
            user=self.mail_user,
        )

        self.client.force_login(self.actor)
        response = self.client.get(
            reverse("line-dashboard-notification-recipients"),
            {"lineId": "L1", "targetUserSdwtProd": "etch_a", "channel": "mail"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["lineId"], "L1")
        self.assertEqual(payload["targetUserSdwtProd"], "etch_a")
        self.assertEqual(payload["channel"], "mail")
        self.assertEqual([row["userId"] for row in payload["recipients"]], [self.mail_user.id])

    def test_notification_recipient_endpoint_allows_non_operator_read(self) -> None:
        """운영자가 아닌 사용자도 수신인 목록은 조회할 수 있어야 합니다."""

        _create_target_recipient(
            target_user_sdwt_prod="ETCH_A",
            channel=DroneSopTargetRecipient.Channels.MAIL,
            user=self.mail_user,
        )

        self.client.force_login(self.same_group_user)
        response = self.client.get(
            reverse("line-dashboard-notification-recipients"),
            {"lineId": "L1", "targetUserSdwtProd": "ETCH_A", "channel": "mail"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["lineId"], "L1")
        self.assertEqual(payload["targetUserSdwtProd"], "ETCH_A")
        self.assertEqual(payload["channel"], "mail")
        self.assertEqual([row["userId"] for row in payload["recipients"]], [self.mail_user.id])

    def test_notification_recipient_endpoint_allows_non_operator_update(self) -> None:
        """로그인 사용자는 운영자가 아니어도 수신인을 저장할 수 있어야 합니다."""

        self.client.force_login(self.same_group_user)
        response = self.client.put(
            reverse("line-dashboard-notification-recipients"),
            data=json.dumps(
                {
                    "lineId": "L1",
                    "targetUserSdwtProd": "ETCH_A",
                    "channel": "mail",
                    "userIds": [self.mail_user.id],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            DroneSopTargetRecipient.objects.filter(
                target__target_user_sdwt_prod="ETCH_A",
                channel=DroneSopTargetRecipient.Channels.MAIL,
                user=self.mail_user,
            ).exists()
        )

    def test_notification_recipient_endpoint_allows_account_group_manager_user(self) -> None:
        """account 공통 그룹 manager도 로그인 사용자 기준으로 수신인을 저장할 수 있어야 합니다."""

        User = get_user_model()
        account_manager = User.objects.create_user(
            sabun="S71005",
            password="test-password",
            knox_id="knox-71005",
            email="account-manager@example.com",
        )
        _set_current_affiliation(account_manager, department="Dept", line="L1", user_sdwt_prod="ETCH_A")
        account_services.ensure_self_access(account_manager, role="manager")

        self.client.force_login(account_manager)
        response = self.client.put(
            reverse("line-dashboard-notification-recipients"),
            data=json.dumps(
                {
                    "lineId": "L1",
                    "targetUserSdwtProd": "ETCH_A",
                    "channel": "mail",
                    "userIds": [self.mail_user.id],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            DroneSopTargetRecipient.objects.filter(
                target__target_user_sdwt_prod="ETCH_A",
                channel=DroneSopTargetRecipient.Channels.MAIL,
                user=self.mail_user,
            ).exists()
        )

    def test_notification_recipient_permission_endpoint_returns_drone_context(self) -> None:
        """권한 컨텍스트 API가 변경 가능 여부를 반환하는지 확인합니다."""

        self.client.force_login(self.same_group_user)
        response = self.client.get(reverse("line-dashboard-notification-recipient-permissions"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["canManageRecipients"])
        self.assertNotIn("isOperator", payload)
        self.assertEqual(payload["manageableUserSdwtProds"], [])

    def test_notification_recipient_permission_endpoint_returns_manageable_targets(self) -> None:
        """변경 가능한 사용자에게 모든 Drone SOP 대상 목록을 반환해야 합니다."""

        _upsert_target(line_id="L1", target_user_sdwt_prod="ETCH_A")

        self.client.force_login(self.actor)
        response = self.client.get(reverse("line-dashboard-notification-recipient-permissions"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["canManageRecipients"])
        self.assertIn("ETCH_A", payload["manageableUserSdwtProds"])
