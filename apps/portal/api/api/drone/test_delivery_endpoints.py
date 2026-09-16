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

class DroneSopInstantInformTests(TestCase):
    """즉시 인폼 요청 로직을 검증합니다."""

    def test_enqueue_instant_inform_marks_requested(self) -> None:
        """즉시 인폼 체크 요청 시 instant_inform과 target 보정이 반영되는지 확인합니다."""
        _ensure_target_mapping(
            sdwt_prod="SDWT",
            user_sdwt_prod="SDWT",
            target_user_sdwt_prod="TARGET-SDWT",
        )
        _upsert_target(
            target_user_sdwt_prod="TARGET-SDWT",
            jira_key="PROJ",
            jira_template_key="common",
            messenger_enabled=False,
        )
        row = _create_drone_sop(
            sdwt_prod="SDWT",
            user_sdwt_prod="SDWT",
            status="IN_PROGRESS",
            needtosend=0,
            send_jira=-1,
            instant_inform=-1,
            comment="base",
        )

        result = services.enqueue_drone_sop_jira_instant_inform(sop_id=int(row.id), comment="hello")
        self.assertTrue(result.queued)
        self.assertFalse(result.already_informed)
        self.assertEqual(result.updated_fields.get("comment"), "hello")
        self.assertEqual(result.updated_fields.get("instant_inform"), 1)
        self.assertIsNone(result.updated_fields.get("send_jira"))

        refreshed = DroneSOP.objects.get(id=row.id)
        self.assertEqual(refreshed.comment, "hello")
        self.assertEqual(refreshed.instant_inform, 1)
        self.assertEqual(refreshed.target_user_sdwt_prod, "TARGET-SDWT")
        self.assertEqual(_sop_delivery_value(refreshed, "sendJira"), 0)
        self.assertTrue(
            DroneSopDelivery.objects.filter(
                sop=refreshed,
                channel=DroneSopDelivery.Channels.JIRA,
                status=DroneSopDelivery.Statuses.PENDING,
            ).exists()
        )
        self.assertEqual(
            set(refreshed.channel_deliveries.values_list("channel", "status")),
            {
                (DroneSopDelivery.Channels.JIRA, DroneSopDelivery.Statuses.PENDING),
                (DroneSopDelivery.Channels.MESSENGER, DroneSopDelivery.Statuses.DISABLED),
                (DroneSopDelivery.Channels.MAIL, DroneSopDelivery.Statuses.DISABLED),
            },
        )
        self.assertEqual(
            set(refreshed.channel_deliveries.values_list("channel", "reason")),
            {
                (DroneSopDelivery.Channels.JIRA, None),
                (DroneSopDelivery.Channels.MESSENGER, "disabled_by_policy"),
                (DroneSopDelivery.Channels.MAIL, "channel_config_missing"),
            },
        )

    def test_enqueue_instant_inform_resolves_target_case_insensitively(self) -> None:
        """즉시 인폼 대상 매핑이 sdwt/user 소속 대소문자를 무시하는지 확인합니다."""
        _ensure_target_mapping(
            sdwt_prod="SDWT",
            user_sdwt_prod="USR",
            target_user_sdwt_prod="TARGET-SDWT",
        )
        _upsert_target(
            target_user_sdwt_prod="TARGET-SDWT",
            jira_key="PROJ",
            jira_template_key="common",
            messenger_enabled=False,
        )
        row = _create_drone_sop(
            sdwt_prod="sdwt",
            user_sdwt_prod="usr",
            status="IN_PROGRESS",
            needtosend=0,
            send_jira=-1,
            instant_inform=-1,
        )

        result = services.enqueue_drone_sop_jira_instant_inform(sop_id=int(row.id), comment=None)

        self.assertTrue(result.queued)
        self.assertNotIn("target_user_sdwt_prod", result.updated_fields)

        refreshed = DroneSOP.objects.get(id=row.id)
        self.assertEqual(refreshed.target_user_sdwt_prod, "TARGET-SDWT")
        self.assertTrue(
            DroneSopDelivery.objects.filter(
                sop=refreshed,
                channel=DroneSopDelivery.Channels.JIRA,
                status=DroneSopDelivery.Statuses.PENDING,
            ).exists()
        )

    def test_enqueue_instant_inform_without_queueable_channel_does_not_mark_requested(self) -> None:
        """발송 가능한 채널이 없으면 즉시인폼 플래그를 확정하지 않습니다."""
        _ensure_target_mapping(
            sdwt_prod="SDWT-NO-CHANNEL",
            user_sdwt_prod="USER-NO-CHANNEL",
            target_user_sdwt_prod="TARGET-NO-CHANNEL",
        )
        row = _create_drone_sop(
            sdwt_prod="SDWT-NO-CHANNEL",
            user_sdwt_prod="USER-NO-CHANNEL",
            status="IN_PROGRESS",
            needtosend=0,
            instant_inform=0,
            comment="base",
        )

        result = services.enqueue_drone_sop_jira_instant_inform(
            sop_id=int(row.id),
            comment="updated",
        )

        self.assertFalse(result.queued)
        self.assertFalse(result.already_informed)
        self.assertTrue(result.not_queueable)
        self.assertEqual(result.block_reason, "no_queueable_channel")

        refreshed = DroneSOP.objects.get(id=row.id)
        self.assertEqual(refreshed.comment, "updated")
        self.assertEqual(refreshed.instant_inform, 0)
        self.assertEqual(
            set(refreshed.channel_deliveries.values_list("channel", "status", "reason")),
            {
                (
                    DroneSopDelivery.Channels.JIRA,
                    DroneSopDelivery.Statuses.DISABLED,
                    "channel_config_missing",
                ),
                (
                    DroneSopDelivery.Channels.MESSENGER,
                    DroneSopDelivery.Statuses.DISABLED,
                    "channel_config_missing",
                ),
                (
                    DroneSopDelivery.Channels.MAIL,
                    DroneSopDelivery.Statuses.DISABLED,
                    "channel_config_missing",
                ),
            },
        )

    def test_enqueue_instant_inform_queues_remaining_channels_when_jira_already_sent(self) -> None:
        """Jira만 전송된 항목은 메신저/메일까지 즉시인폼 대기 상태로 둡니다."""
        _ensure_target_mapping(
            sdwt_prod="SDWT",
            user_sdwt_prod="SDWT",
            target_user_sdwt_prod="TARGET-SDWT",
        )
        _upsert_target(
            target_user_sdwt_prod="TARGET-SDWT",
            messenger_template_key="common",
            mail_template_key="common",
            chatroom_id=12345,
        )
        row = _create_drone_sop(
            sdwt_prod="SDWT",
            user_sdwt_prod="SDWT",
            send_jira=1,
            instant_inform=0,
            jira_key="JIRA-1",
        )

        result = services.enqueue_drone_sop_jira_instant_inform(sop_id=int(row.id), comment="updated")
        self.assertFalse(result.already_informed)
        self.assertTrue(result.queued)
        self.assertEqual(result.jira_key, "JIRA-1")
        self.assertEqual(result.updated_fields.get("comment"), "updated")
        self.assertEqual(result.updated_fields.get("instant_inform"), 1)

        refreshed = DroneSOP.objects.get(id=row.id)
        self.assertEqual(refreshed.comment, "updated")
        self.assertEqual(refreshed.instant_inform, 1)
        self.assertTrue(
            DroneSopDelivery.objects.filter(
                sop=refreshed,
                channel=DroneSopDelivery.Channels.JIRA,
                status=DroneSopDelivery.Statuses.SUCCESS,
            ).exists()
        )
        self.assertTrue(
            DroneSopDelivery.objects.filter(
                sop=refreshed,
                channel=DroneSopDelivery.Channels.MESSENGER,
                status=DroneSopDelivery.Statuses.PENDING,
            ).exists()
        )
        self.assertTrue(
            DroneSopDelivery.objects.filter(
                sop=refreshed,
                channel=DroneSopDelivery.Channels.MAIL,
                status=DroneSopDelivery.Statuses.PENDING,
            ).exists()
        )

    def test_enqueue_instant_inform_returns_already_informed_when_all_channels_sent(self) -> None:
        """모든 채널이 이미 성공한 경우에만 already_informed를 반환합니다."""
        row = _create_drone_sop(target_user_sdwt_prod="TARGET-SDWT", instant_inform=0)
        for channel in (
            DroneSopDelivery.Channels.JIRA,
            DroneSopDelivery.Channels.MESSENGER,
            DroneSopDelivery.Channels.MAIL,
        ):
            delivery = services.create_channel_delivery_with_dispatch(
                sop=row,
                channel=channel,
                status=DroneSopDelivery.Statuses.SUCCESS,
            )
            if channel == DroneSopDelivery.Channels.JIRA:
                delivery.external_key = "JIRA-1"
                delivery.save(update_fields=["external_key", "updated_at"])

        result = services.enqueue_drone_sop_jira_instant_inform(sop_id=int(row.id), comment="updated")

        self.assertTrue(result.already_informed)
        self.assertFalse(result.queued)
        self.assertEqual(result.jira_key, "JIRA-1")

    def test_enqueue_instant_inform_treats_non_jira_success_as_already_informed(self) -> None:
        """Jira가 비활성이고 다른 채널이 성공했으면 이미 발송 완료로 판단합니다."""

        _upsert_target(
            target_user_sdwt_prod="TARGET-NON-JIRA-DONE",
            jira_enabled=False,
            messenger_enabled=True,
            messenger_template_key="common",
            mail_enabled=True,
            mail_template_key="common",
        )
        sop = DroneSOP.objects.create(
            line_id="L1",
            target_user_sdwt_prod="TARGET-NON-JIRA-DONE",
            eqp_id="EQP-NON-JIRA-DONE",
            chamber_ids="1",
            lot_id="LOT.NON.JIRA.DONE",
            main_step="MS",
            status="COMPLETE",
            needtosend=1,
            instant_inform=0,
        )
        for channel in (
            DroneSopDelivery.Channels.MESSENGER,
            DroneSopDelivery.Channels.MAIL,
        ):
            services.create_channel_delivery_with_dispatch(
                sop=sop,
                channel=channel,
                status=DroneSopDelivery.Statuses.SUCCESS,
            )
        DroneSOP.objects.filter(id=sop.id).update(status="IN_PROGRESS", needtosend=0)

        result = services.enqueue_drone_sop_jira_instant_inform(sop_id=int(sop.id), comment=None)

        self.assertTrue(result.already_informed)
        self.assertFalse(result.queued)
        self.assertIsNone(result.jira_key)

    def test_enqueue_instant_inform_does_not_requeue_failed_delivery(self) -> None:
        """즉시인폼은 실패 delivery를 재시도 대기로 바꾸지 않습니다."""

        _upsert_target(
            target_user_sdwt_prod="TARGET-FAILED-INSTANT",
            jira_enabled=False,
            messenger_enabled=True,
            messenger_template_key="common",
            mail_enabled=False,
        )
        sop = DroneSOP.objects.create(
            line_id="L1",
            target_user_sdwt_prod="TARGET-FAILED-INSTANT",
            eqp_id="EQP-FAILED-INSTANT",
            chamber_ids="1",
            lot_id="LOT.FAILED.INSTANT",
            main_step="MS",
            status="COMPLETE",
            needtosend=1,
            instant_inform=0,
        )
        failed_delivery = services.create_channel_delivery_with_dispatch(
            sop=sop,
            channel=DroneSopDelivery.Channels.MESSENGER,
            status=DroneSopDelivery.Statuses.FAILED,
            reason="send_failed",
        )
        DroneSOP.objects.filter(id=sop.id).update(status="IN_PROGRESS", needtosend=0)

        result = services.enqueue_drone_sop_jira_instant_inform(sop_id=int(sop.id), comment=None)

        self.assertFalse(result.queued)
        self.assertTrue(result.not_queueable)
        failed_delivery.refresh_from_db()
        sop.refresh_from_db()
        self.assertEqual(sop.instant_inform, 0)
        self.assertEqual(failed_delivery.status, DroneSopDelivery.Statuses.FAILED)
        self.assertFalse(
            DroneSopDelivery.objects.filter(
                sop=sop,
                channel=DroneSopDelivery.Channels.MESSENGER,
                status=DroneSopDelivery.Statuses.PENDING,
            ).exists()
        )

    def test_enqueue_instant_inform_does_not_copy_sop_status_to_delivery(self) -> None:
        """즉시 인폼이 SOP 진행 상태를 delivery status로 복사하지 않는지 확인합니다."""

        _ensure_target_mapping(
            sdwt_prod="SDWT",
            user_sdwt_prod="USER",
            target_user_sdwt_prod="TARGET-A",
        )
        _upsert_target(
            target_user_sdwt_prod="TARGET-A",
            jira_key="PROJ",
            jira_template_key="common",
            messenger_enabled=False,
        )
        sop = DroneSOP.objects.create(
            line_id="L1",
            sdwt_prod="SDWT",
            user_sdwt_prod="USER",
            eqp_id="EQP1",
            chamber_ids="1",
            lot_id="LOT.1",
            main_step="MS",
            status="ESOP_STARTED",
            needtosend=0,
            instant_inform=0,
        )

        result = services.enqueue_drone_sop_jira_instant_inform(sop_id=int(sop.id), comment="urgent")

        self.assertTrue(result.queued)
        delivery = DroneSopDelivery.objects.get(
            sop=sop,
            channel=DroneSopDelivery.Channels.JIRA,
        )
        self.assertEqual(delivery.status, DroneSopDelivery.Statuses.PENDING)


class DroneSopDeliveryConstraintTests(TestCase):
    """DroneSOP delivery 데이터 무결성을 검증합니다."""

    def test_create_channel_delivery_rejects_ineligible_sop(self) -> None:
        """명시 생성 helper도 발송 조건 미충족 SOP의 delivery를 만들지 않습니다."""

        sop = DroneSOP.objects.create(
            line_id="L1",
            sdwt_prod="SDWT-SKIP",
            user_sdwt_prod="USER-SKIP",
            target_user_sdwt_prod="TARGET-SKIP",
            eqp_id="EQP-SKIP-MANUAL",
            chamber_ids="1",
            lot_id="LOT.SKIP.MANUAL",
            main_step="MS",
            status="IN_PROGRESS",
            needtosend=0,
            instant_inform=0,
        )

        with self.assertRaises(ValueError):
            services.create_channel_delivery_with_dispatch(
                sop=sop,
                channel=DroneSopDelivery.Channels.JIRA,
            )

        self.assertFalse(DroneSopDelivery.objects.filter(sop=sop).exists())
        self.assertFalse(DroneSopTargetDispatch.objects.filter(sop=sop).exists())

    def test_delivery_snapshot_rechecks_current_sop_before_create(self) -> None:
        """stale 후보 row가 넘어와도 현재 SOP가 발송 조건을 벗어나면 delivery를 만들지 않습니다."""

        sop = DroneSOP.objects.create(
            line_id="L1",
            sdwt_prod="SDWT-RACE",
            user_sdwt_prod="USER-RACE",
            target_user_sdwt_prod="TARGET-RACE",
            eqp_id="EQP-RACE",
            chamber_ids="1",
            lot_id="LOT.RACE",
            main_step="MS",
            status="COMPLETE",
            needtosend=1,
            instant_inform=0,
        )
        stale_row = {
            "id": int(sop.id),
            "sdwt_prod": sop.sdwt_prod,
            "user_sdwt_prod": sop.user_sdwt_prod,
            "target_user_sdwt_prod": sop.target_user_sdwt_prod,
            "status": "COMPLETE",
            "needtosend": 1,
            "instant_inform": 0,
        }
        DroneSOP.objects.filter(id=sop.id).update(needtosend=0)

        result = ensure_channel_delivery_snapshots_for_rows(
            rows=[stale_row],
            channels=[DroneSopDelivery.Channels.JIRA],
        )

        self.assertEqual(result.created_count, 0)
        self.assertFalse(DroneSopDelivery.objects.filter(sop=sop).exists())
        self.assertFalse(DroneSopTargetDispatch.objects.filter(sop=sop).exists())

    def test_delivery_status_rejects_sop_lifecycle_status(self) -> None:
        """SOP 진행 상태값이 delivery status에 저장되지 못하는지 확인합니다."""

        sop = _create_drone_sop()

        with self.assertRaises(IntegrityError), transaction.atomic():
            services.create_channel_delivery_with_dispatch(
                sop=sop,
                channel=DroneSopDelivery.Channels.JIRA,
                status="ESOP_STARTED",
            )

    def test_delivery_summary_treats_cancelled_as_blocked(self) -> None:
        """normalized delivery 요약은 취소 상태를 대기 상태로 오인하지 않습니다."""

        sop = _create_drone_sop(target_user_sdwt_prod="TARGET-CANCELLED")
        delivery = DroneSopDelivery.objects.get(
            sop=sop,
            channel=DroneSopDelivery.Channels.JIRA,
        )
        delivery.status = DroneSopDelivery.Statuses.CANCELLED
        delivery.reason = "cancelled"
        delivery.save(update_fields=["status", "reason", "updated_at"])

        refreshed = DroneSOP.objects.get(id=sop.id)
        self.assertEqual(_sop_delivery_value(refreshed, "sendJira"), -1)
        self.assertEqual(_sop_delivery_value(refreshed, "jiraReason"), "cancelled")

    def test_dispatch_status_treats_success_and_cancelled_as_partial_failed(self) -> None:
        """성공과 취소가 섞인 target dispatch는 일부 실패로 요약합니다."""

        sop = _create_drone_sop(target_user_sdwt_prod="TARGET-PARTIAL")
        deliveries = {
            delivery.channel: delivery
            for delivery in DroneSopDelivery.objects.filter(sop=sop)
        }

        mark_channel_delivery_status(
            delivery_ids=[int(deliveries[DroneSopDelivery.Channels.JIRA].id)],
            status=DroneSopDelivery.Statuses.SUCCESS,
        )
        mark_channel_delivery_status(
            delivery_ids=[int(deliveries[DroneSopDelivery.Channels.MESSENGER].id)],
            status=DroneSopDelivery.Statuses.CANCELLED,
            reason="cancelled",
        )
        mark_channel_delivery_status(
            delivery_ids=[int(deliveries[DroneSopDelivery.Channels.MAIL].id)],
            status=DroneSopDelivery.Statuses.DISABLED,
            reason="disabled_by_policy",
        )

        dispatch = DroneSopTargetDispatch.objects.get(sop=sop)
        self.assertEqual(dispatch.status, DroneSopTargetDispatch.Statuses.PARTIAL_FAILED)

    def test_normalized_delivery_seed_refreshes_dispatch_status(self) -> None:
        """normalized seed가 delivery 상태와 dispatch 요약을 함께 갱신합니다."""

        sop = _create_drone_sop(
            target_user_sdwt_prod="TARGET-SEED-SUCCESS",
            send_jira=1,
            send_messenger=1,
            send_mail=1,
        )

        dispatch = DroneSopTargetDispatch.objects.get(sop=sop)
        self.assertEqual(dispatch.status, DroneSopTargetDispatch.Statuses.SUCCESS)

    def test_config_failure_filter_preserves_existing_failed_delivery(self) -> None:
        """전역 설정 실패 처리는 이미 실패한 delivery 사유를 덮어쓰지 않아야 합니다."""

        sop = _create_drone_sop(target_user_sdwt_prod="TARGET-A")
        failed = DroneSopDelivery.objects.get(
            sop=sop,
            channel=DroneSopDelivery.Channels.JIRA,
        )
        failed.status = DroneSopDelivery.Statuses.FAILED
        failed.reason = "send_failed"
        failed.save(update_fields=["status", "reason", "updated_at"])

        pending = DroneSopDelivery.objects.get(
            sop=sop,
            channel=DroneSopDelivery.Channels.MAIL,
        )
        pending.status = DroneSopDelivery.Statuses.PENDING
        pending.reason = None
        pending.save(update_fields=["status", "reason", "updated_at"])

        disabled = DroneSopDelivery.objects.get(
            sop=sop,
            channel=DroneSopDelivery.Channels.MESSENGER,
        )
        disabled.status = DroneSopDelivery.Statuses.DISABLED
        disabled.reason = "disabled_by_policy"
        disabled.save(update_fields=["status", "reason", "updated_at"])

        self.assertEqual(
            filter_delivery_ids_for_config_failure(
                delivery_ids=[int(failed.id), int(pending.id), int(disabled.id)],
            ),
            [int(pending.id)],
        )


class DroneSopRetryChannelTests(TestCase):
    """단건 채널 재시도 요청 로직을 검증합니다."""

    def test_retry_channel_resets_failed_state_to_pending(self) -> None:
        """실패 delivery 채널을 재시도 시 pending으로 복구하는지 확인합니다."""
        row = _create_drone_sop(
            target_user_sdwt_prod="TARGET-A",
            send_jira=-1,
            jira_reason="send_failed",
            instant_inform=1,
        )
        delivery = DroneSopDelivery.objects.get(
            sop=row,
            channel=DroneSopDelivery.Channels.JIRA,
        )
        delivery.status = DroneSopDelivery.Statuses.FAILED
        delivery.reason = "send_failed"
        delivery.save(update_fields=["status", "reason", "updated_at"])

        result = services.retry_drone_sop_channel(sop_id=int(row.id), channel="jira")
        self.assertTrue(result.queued)
        self.assertFalse(result.already_pending)
        self.assertFalse(result.already_sent)
        self.assertEqual(result.updated_fields, {})

        refreshed = DroneSOP.objects.get(id=row.id)
        self.assertEqual(_sop_delivery_value(refreshed, "sendJira"), 0)
        self.assertIsNone(_sop_delivery_value(refreshed, "jiraReason"))
        self.assertEqual(refreshed.instant_inform, 1)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, DroneSopDelivery.Statuses.PENDING)
        self.assertIsNone(delivery.reason)
        candidate_ids = {int(candidate["id"]) for candidate in selectors.list_drone_sop_jira_candidates()}
        self.assertIn(int(row.id), candidate_ids)

    def test_retry_channel_resolves_target_missing_with_current_mapping(self) -> None:
        """target 미확정 실패는 수동 재시도 시 현재 지정 조합으로 다시 해석합니다."""

        sop = DroneSOP.objects.create(
            line_id="L1",
            sdwt_prod="SDWT-MISSING",
            user_sdwt_prod="USER-MISSING",
            eqp_id="EQP-MISSING",
            chamber_ids="1",
            lot_id="LOT.MISSING",
            main_step="MS",
            status="COMPLETE",
            needtosend=1,
            instant_inform=1,
        )
        result = services.run_drone_sop_jira_create_from_settings()
        self.assertEqual(result.skip_reason, "no_valid_targets")
        failed_delivery = DroneSopDelivery.objects.get(
            sop=sop,
            channel=DroneSopDelivery.Channels.JIRA,
        )
        self.assertEqual(failed_delivery.status, DroneSopDelivery.Statuses.FAILED)
        self.assertEqual(failed_delivery.reason, "target_missing")

        _ensure_target_mapping(
            sdwt_prod="SDWT-MISSING",
            user_sdwt_prod="USER-MISSING",
            target_user_sdwt_prod="TARGET-RESOLVED",
        )
        retry_result = services.retry_drone_sop_channel(sop_id=int(sop.id), channel="jira")

        self.assertTrue(retry_result.queued)
        deliveries = list(
            DroneSopDelivery.objects.filter(
                sop=sop,
                channel=DroneSopDelivery.Channels.JIRA,
            )
        )
        self.assertEqual(len(deliveries), 1)
        sop.refresh_from_db()
        self.assertEqual(sop.target_user_sdwt_prod, "TARGET-RESOLVED")
        self.assertEqual(deliveries[0].status, DroneSopDelivery.Statuses.PENDING)
        self.assertIsNone(deliveries[0].reason)
        candidate_ids = {int(candidate["id"]) for candidate in selectors.list_drone_sop_jira_candidates()}
        self.assertIn(int(sop.id), candidate_ids)

    def test_retry_channel_does_not_resolve_target_missing_when_ineligible(self) -> None:
        """발송 조건을 벗어난 SOP는 target 재해석 재시도에서 delivery를 새로 만들지 않습니다."""

        sop = DroneSOP.objects.create(
            line_id="L1",
            sdwt_prod="SDWT-MISSING",
            user_sdwt_prod="USER-MISSING",
            eqp_id="EQP-MISSING-INELIGIBLE",
            chamber_ids="1",
            lot_id="LOT.MISSING.INELIGIBLE",
            main_step="MS",
            status="COMPLETE",
            needtosend=1,
            instant_inform=0,
        )
        result = services.run_drone_sop_jira_create_from_settings()
        self.assertEqual(result.skip_reason, "no_valid_targets")
        failed_delivery = DroneSopDelivery.objects.get(
            sop=sop,
            channel=DroneSopDelivery.Channels.JIRA,
        )
        self.assertEqual(failed_delivery.reason, "target_missing")

        sop.status = "IN_PROGRESS"
        sop.needtosend = 0
        sop.instant_inform = 0
        sop.save(update_fields=["status", "needtosend", "instant_inform", "updated_at"])
        _ensure_target_mapping(
            sdwt_prod="SDWT-MISSING",
            user_sdwt_prod="USER-MISSING",
            target_user_sdwt_prod="TARGET-RESOLVED",
        )

        retry_result = services.retry_drone_sop_channel(sop_id=int(sop.id), channel="jira")

        self.assertFalse(retry_result.queued)
        self.assertTrue(retry_result.already_disabled)
        self.assertEqual(
            DroneSopDelivery.objects.filter(
                sop=sop,
                channel=DroneSopDelivery.Channels.JIRA,
            ).count(),
            1,
        )
        self.assertFalse(
            DroneSopTargetDispatch.objects.filter(
                sop=sop,
                target_code_snapshot="TARGET-RESOLVED",
            ).exists()
        )

    def test_retry_channel_returns_already_pending_when_not_failed(self) -> None:
        """실패 상태가 아니면 이미 대기 상태로 응답하는지 확인합니다."""
        row = _create_drone_sop(
            send_messenger=0,
            messenger_reason=None,
        )

        result = services.retry_drone_sop_channel(sop_id=int(row.id), channel="messenger")
        self.assertFalse(result.queued)
        self.assertTrue(result.already_pending)
        self.assertFalse(result.already_sent)

        refreshed = DroneSOP.objects.get(id=row.id)
        self.assertEqual(_sop_delivery_value(refreshed, "sendMessenger"), 0)
        self.assertIsNone(_sop_delivery_value(refreshed, "messengerReason"))

    def test_retry_channel_returns_disabled_when_channel_is_disabled(self) -> None:
        """비활성 채널은 대기 상태로 오인하지 않고 비활성 응답을 반환합니다."""
        row = _create_drone_sop(target_user_sdwt_prod="TARGET-A")
        delivery = DroneSopDelivery.objects.get(
            sop=row,
            channel=DroneSopDelivery.Channels.MAIL,
        )
        delivery.status = DroneSopDelivery.Statuses.DISABLED
        delivery.reason = "channel_config_missing"
        delivery.save(update_fields=["status", "reason", "updated_at"])

        result = services.retry_drone_sop_channel(sop_id=int(row.id), channel="mail")

        self.assertFalse(result.queued)
        self.assertFalse(result.already_pending)
        self.assertFalse(result.already_sent)
        self.assertTrue(result.already_disabled)

        refreshed = DroneSOP.objects.get(id=row.id)
        self.assertEqual(_sop_delivery_value(refreshed, "sendMail"), 0)
        self.assertEqual(_sop_delivery_value(refreshed, "mailReason"), "channel_config_missing")

    def test_retry_channel_returns_disabled_when_channel_is_cancelled(self) -> None:
        """취소된 채널은 대기 상태로 오인하지 않고 비활성 응답을 반환합니다."""
        row = _create_drone_sop(target_user_sdwt_prod="TARGET-A")
        delivery = DroneSopDelivery.objects.get(
            sop=row,
            channel=DroneSopDelivery.Channels.MAIL,
        )
        delivery.status = DroneSopDelivery.Statuses.CANCELLED
        delivery.reason = "cancelled"
        delivery.save(update_fields=["status", "reason", "updated_at"])

        result = services.retry_drone_sop_channel(sop_id=int(row.id), channel="mail")

        self.assertFalse(result.queued)
        self.assertFalse(result.already_pending)
        self.assertFalse(result.already_sent)
        self.assertTrue(result.already_disabled)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, DroneSopDelivery.Statuses.CANCELLED)

    def test_retry_channel_rejects_invalid_channel(self) -> None:
        """지원하지 않는 채널 키는 오류로 거부하는지 확인합니다."""
        row = _create_drone_sop(send_mail=-1, mail_reason="send_failed")

        with self.assertRaises(ValueError):
            services.retry_drone_sop_channel(sop_id=int(row.id), channel="sms")


class DroneEndpointTests(TestCase):
    """드론 API 엔드포인트 동작을 검증합니다."""

    def setUp(self) -> None:
        """테스트용 사용자/클라이언트를 준비합니다."""
        _allow_test_scope_access(self)
        User = get_user_model()
        self.user = User.objects.create_user(
            sabun="S60000",
            password="test-password",
            knox_id="knox-60000",
        )
        self.client.force_login(self.user)

    def test_drone_early_inform_crud(self) -> None:
        """조기 알림 CRUD 플로우가 동작하는지 확인합니다."""
        create_response = self.client.post(
            reverse("drone-early-inform"),
            data='{"lineId":"L1","mainStep":"STEP1","customEndStep":"STEP2"}',
            content_type="application/json",
        )
        self.assertEqual(create_response.status_code, 201)
        entry_id = create_response.json()["entry"]["id"]

        list_response = self.client.get(reverse("drone-early-inform"), {"lineId": "L1"})
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()["rowCount"], 1)

        update_response = self.client.patch(
            reverse("drone-early-inform"),
            data='{"id": %d, "customEndStep": "STEP3"}' % entry_id,
            content_type="application/json",
        )
        self.assertEqual(update_response.status_code, 200)

        delete_response = self.client.delete(f"{reverse('drone-early-inform')}?id={entry_id}")
        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(delete_response.json(), {"success": True})
        self.assertFalse(DroneEarlyInform.objects.filter(id=entry_id).exists())

    def test_drone_early_inform_validation_error_contract(self) -> None:
        """생성·수정 serializer 오류가 기존 HTTP 응답 계약을 유지하는지 확인합니다."""

        create_response = self.client.post(
            reverse("drone-early-inform"),
            data='{"mainStep":"STEP1"}',
            content_type="application/json",
        )
        update_response = self.client.patch(
            reverse("drone-early-inform"),
            data='{"id":1}',
            content_type="application/json",
        )

        self.assertEqual(create_response.status_code, 400)
        self.assertEqual(create_response.json(), {"error": "lineId is required"})
        self.assertEqual(update_response.status_code, 400)
        self.assertEqual(
            update_response.json(),
            {"error": "No valid fields to update"},
        )

    @patch("api.drone.views.dashboard.selectors.get_line_history_payload", return_value={"rows": []})
    def test_drone_line_history(self, _mock_history) -> None:
        """라인 히스토리 API가 정상 응답하는지 확인합니다."""
        response = self.client.get(reverse("line-dashboard-history"))
        self.assertEqual(response.status_code, 200)

    @patch("api.drone.views.dashboard.selectors.list_distinct_line_ids", return_value=["L1"])
    def test_drone_line_ids(self, _mock_lines) -> None:
        """라인 ID 목록 API가 정상 응답하는지 확인합니다."""
        response = self.client.get(reverse("line-dashboard-line-ids"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["lineIds"], ["L1"])

    @patch(
        "api.drone.views.dashboard.selectors.get_tip_status_line_sdwt_options_payload",
        return_value={
            "lines": [{"lineId": "L1", "userSdwtProds": ["SD-10"]}],
            "userSdwtProds": ["SD-10"],
        },
    )
    def test_drone_line_sdwt_options(self, _mock_options) -> None:
        """TIP status line/user_sdwt_prod 옵션 API가 정상 응답하는지 확인합니다."""
        response = self.client.get(reverse("line-dashboard-line-sdwt-options"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "lines": [{"lineId": "L1", "userSdwtProds": ["SD-10"]}],
                "userSdwtProds": ["SD-10"],
            },
        )

    @patch(
        "api.drone.views.jira.selectors.list_drone_sop_jira_target_user_sdwt_prods",
        return_value=["SDWT-A", "SDWT-B"],
    )
    def test_drone_jira_user_sdwt_prods(self, _mock_user_sdwt) -> None:
        """Jira user_sdwt_prod 목록 API가 정상 응답하는지 확인합니다."""
        response = self.client.get(reverse("line-dashboard-jira-user-sdwt-prods"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["userSdwtProds"], ["SDWT-A", "SDWT-B"])

    @patch("api.drone.views.delivery.services.enqueue_drone_sop_jira_instant_inform")
    def test_drone_sop_instant_inform(self, mock_service) -> None:
        """즉시 인폼 API가 정상 응답하는지 확인합니다."""
        mock_service.return_value = SimpleNamespace(
            already_informed=False,
            queued=True,
            not_queueable=False,
            block_reason=None,
            jira_key="JIRA-1",
            updated_fields={},
        )
        response = self.client.post(
            reverse("drone-sop-instant-inform", kwargs={"sop_id": 123}),
            data='{"comment":"test"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("status"), "queued")

    @patch("api.drone.views.delivery.services.enqueue_drone_sop_jira_instant_inform")
    def test_drone_sop_instant_inform_returns_not_queueable(self, mock_service) -> None:
        """발송 가능한 채널이 없으면 API status=not_queueable로 응답합니다."""
        mock_service.return_value = SimpleNamespace(
            already_informed=False,
            queued=False,
            not_queueable=True,
            block_reason="no_queueable_channel",
            jira_key=None,
            updated_fields={"comment": "test"},
        )
        response = self.client.post(
            reverse("drone-sop-instant-inform", kwargs={"sop_id": 123}),
            data='{"comment":"test"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("status"), "not_queueable")
        self.assertFalse(response.json().get("queued"))
        self.assertTrue(response.json().get("notQueueable"))
        self.assertEqual(response.json().get("blockReason"), "no_queueable_channel")

    def test_drone_sop_instant_inform_returns_latest_delivery_metadata(self) -> None:
        """즉시 인폼 응답이 최신 delivery 메타를 함께 반환하는지 확인합니다."""

        _upsert_target(
            target_user_sdwt_prod="TARGET-INSTANT",
            jira_key="PROJ",
            jira_template_key="common",
            messenger_enabled=False,
            mail_enabled=False,
        )
        sop = _create_drone_sop(
            target_user_sdwt_prod="TARGET-INSTANT",
            needtosend=0,
            instant_inform=0,
            status="IN_PROGRESS",
        )

        response = self.client.post(
            reverse("drone-sop-instant-inform", kwargs={"sop_id": int(sop.id)}),
            data='{"comment":"now"}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload.get("status"), "queued")
        updated = payload.get("updated")
        self.assertEqual(updated.get("comment"), "now")
        self.assertEqual(updated.get("instant_inform"), 1)
        self.assertIn("deliveryRows", updated)
        jira_rows = [row for row in updated["deliveryRows"] if row["channel"] == "jira"]
        self.assertEqual(jira_rows[0]["status"], "pending")
        self.assertEqual(updated.get("delivery_jira"), 0)

    @patch("api.drone.views.delivery.services.retry_drone_sop_channel")
    def test_drone_sop_retry_channel(self, mock_service) -> None:
        """채널 재시도 API가 정상 응답하는지 확인합니다."""
        mock_service.return_value = SimpleNamespace(
            channel="jira",
            queued=True,
            already_pending=False,
            already_sent=False,
            updated_fields={"send_jira": 0, "jira_reason": None},
        )
        response = self.client.post(
            reverse("drone-sop-retry-channel", kwargs={"sop_id": 123}),
            data='{"channel":"jira"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("status"), "queued")
        self.assertEqual(response.json().get("channel"), "jira")

    def test_drone_sop_retry_channel_returns_latest_delivery_metadata(self) -> None:
        """재시도 응답이 pending으로 갱신된 delivery 메타를 함께 반환하는지 확인합니다."""

        sop = _create_drone_sop(
            target_user_sdwt_prod="TARGET-RETRY",
            send_jira=-1,
            jira_reason="send_failed",
            instant_inform=1,
        )
        delivery = DroneSopDelivery.objects.get(
            sop=sop,
            channel=DroneSopDelivery.Channels.JIRA,
        )
        delivery.status = DroneSopDelivery.Statuses.FAILED
        delivery.reason = "send_failed"
        delivery.save(update_fields=["status", "reason", "updated_at"])

        response = self.client.post(
            reverse("drone-sop-retry-channel", kwargs={"sop_id": int(sop.id)}),
            data='{"channel":"jira"}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload.get("status"), "queued")
        updated = payload.get("updated")
        self.assertIn("deliveryRows", updated)
        jira_rows = [row for row in updated["deliveryRows"] if row["channel"] == "jira"]
        self.assertEqual(jira_rows[0]["status"], "pending")
        self.assertIsNone(jira_rows[0]["reason"])
        self.assertEqual(updated.get("delivery_jira"), 0)

    def test_drone_sop_retry_channel_rejects_invalid_channel(self) -> None:
        """지원하지 않는 채널 요청은 400으로 거부하는지 확인합니다."""
        response = self.client.post(
            reverse("drone-sop-retry-channel", kwargs={"sop_id": 123}),
            data='{"channel":"sms"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json().get("error"), "channel must be one of: jira, messenger, mail")

    @patch("api.drone.views.delivery.services.retry_drone_sop_channel")
    def test_drone_sop_retry_channel_returns_bad_request_when_sop_missing(self, mock_service) -> None:
        """서비스가 SOP 미존재 오류를 반환하면 400으로 응답하는지 확인합니다."""
        mock_service.side_effect = ValueError("DroneSOP not found")

        response = self.client.post(
            reverse("drone-sop-retry-channel", kwargs={"sop_id": 999999}),
            data='{"channel":"jira"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json().get("error"), "DroneSOP not found")

    @patch("api.drone.views.delivery.services.retry_drone_sop_channel")
    def test_drone_sop_retry_channel_returns_already_pending(self, mock_service) -> None:
        """대기 상태 응답이 API status=already_pending으로 매핑되는지 확인합니다."""
        mock_service.return_value = SimpleNamespace(
            channel="mail",
            queued=False,
            already_pending=True,
            already_sent=False,
            updated_fields={"send_mail": 0, "mail_reason": None},
        )

        response = self.client.post(
            reverse("drone-sop-retry-channel", kwargs={"sop_id": 123}),
            data='{"channel":"mail"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("status"), "already_pending")
        self.assertFalse(response.json().get("queued"))
        self.assertTrue(response.json().get("alreadyPending"))
        self.assertFalse(response.json().get("alreadySent"))

    @patch("api.drone.views.delivery.services.retry_drone_sop_channel")
    def test_drone_sop_retry_channel_returns_already_sent(self, mock_service) -> None:
        """완료 상태 응답이 API status=already_sent로 매핑되는지 확인합니다."""
        mock_service.return_value = SimpleNamespace(
            channel="messenger",
            queued=False,
            already_pending=False,
            already_sent=True,
            updated_fields={"send_messenger": 1, "messenger_reason": None},
        )

        response = self.client.post(
            reverse("drone-sop-retry-channel", kwargs={"sop_id": 123}),
            data='{"channel":"messenger"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("status"), "already_sent")
        self.assertFalse(response.json().get("queued"))
        self.assertFalse(response.json().get("alreadyPending"))
        self.assertTrue(response.json().get("alreadySent"))

    @patch("api.drone.views.delivery.services.retry_drone_sop_channel")
    def test_drone_sop_retry_channel_returns_disabled(self, mock_service) -> None:
        """비활성 채널 응답이 API status=disabled로 매핑되는지 확인합니다."""
        mock_service.return_value = SimpleNamespace(
            channel="mail",
            queued=False,
            already_pending=False,
            already_sent=False,
            already_disabled=True,
            updated_fields={},
        )

        response = self.client.post(
            reverse("drone-sop-retry-channel", kwargs={"sop_id": 123}),
            data='{"channel":"mail"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("status"), "disabled")
        self.assertFalse(response.json().get("queued"))
        self.assertFalse(response.json().get("alreadyPending"))
        self.assertFalse(response.json().get("alreadySent"))
        self.assertTrue(response.json().get("alreadyDisabled"))

    @override_settings(AIRFLOW_TRIGGER_TOKEN="token")
    @patch("api.drone.views.triggers.services.run_drone_sop_pop3_ingest_from_settings")
    def test_drone_sop_pop3_trigger(self, mock_service) -> None:
        """POP3 트리거 API가 정상 응답하는지 확인합니다."""
        mock_service.return_value = SimpleNamespace(
            matched_mails=1,
            upserted_rows=1,
            deleted_mails=0,
            pruned_rows=0,
            skipped=False,
            skip_reason=None,
        )
        response = self.client.post(
            reverse("drone-sop-pop3-ingest-trigger"),
            HTTP_AUTHORIZATION="Bearer token",
        )
        self.assertEqual(response.status_code, 200)

    @override_settings(AIRFLOW_TRIGGER_TOKEN="token")
    @patch("api.drone.views.triggers.services.run_drone_sop_pipeline_from_settings")
    def test_drone_sop_pipeline_trigger(self, mock_service) -> None:
        """통합 파이프라인 트리거 API가 정상 응답하는지 확인합니다."""
        mock_service.return_value = SimpleNamespace(
            candidates=1,
            jira_created=1,
            jira_updated_rows=0,
            messenger_sent=0,
            mail_sent=0,
            skipped=False,
            skip_reason=None,
        )
        response = self.client.post(
            reverse("drone-sop-pipeline-trigger"),
            data=json.dumps({}),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer token",
        )
        self.assertEqual(response.status_code, 200)

    @override_settings(AIRFLOW_TRIGGER_TOKEN="token")
    @patch("api.drone.views.triggers.services.has_drone_sop_pipeline_candidates")
    def test_drone_sop_pipeline_precheck(self, mock_service) -> None:
        """통합 파이프라인 precheck API가 정상 응답하는지 확인합니다."""
        mock_service.return_value = True
        response = self.client.post(
            reverse("drone-sop-pipeline-precheck"),
            HTTP_AUTHORIZATION="Bearer token",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get("hasCandidates"))
