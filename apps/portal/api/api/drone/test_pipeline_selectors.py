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

class DroneSopDeliveryEligibilityTests(TestCase):
    """delivery 생성 대상 판정 기준을 검증합니다."""

    def test_python_predicate_matches_queryset_filter(self) -> None:
        """Python 판정과 DB 후보 조건이 같은 SOP를 대상으로 삼는지 확인합니다."""

        cases = [
            ("ELIGIBLE-COMPLETE", "COMPLETE", 1, 0),
            ("ELIGIBLE-INSTANT", "IN_PROGRESS", 0, 1),
            ("SKIP-COMPLETE", "COMPLETE", 0, 0),
            ("SKIP-IN-PROGRESS", "IN_PROGRESS", 1, 0),
        ]
        expected_ids: set[int] = set()
        for eqp_id, status, needtosend, instant_inform in cases:
            sop = DroneSOP.objects.create(
                line_id="L1",
                sdwt_prod="SDWT",
                user_sdwt_prod="USER",
                eqp_id=eqp_id,
                chamber_ids="1",
                lot_id=f"LOT.{eqp_id}",
                main_step="MS",
                status=status,
                needtosend=needtosend,
                instant_inform=instant_inform,
            )
            row = {
                "status": status,
                "needtosend": needtosend,
                "instant_inform": instant_inform,
            }
            if is_sop_delivery_eligible(row):
                expected_ids.add(int(sop.id))

        queryset_ids = set(
            DroneSOP.objects.filter(build_sop_delivery_eligible_q()).values_list("id", flat=True)
        )

        self.assertEqual(queryset_ids, expected_ids)


class DroneSopUpsertTests(TestCase):
    """UPSERT 동작을 검증합니다."""

    def test_upsert_writes_normalized_eqp_lookup(self) -> None:
        """POP3 raw SQL 신규 적재가 Observer 설비 lookup을 함께 저장합니다."""

        upsert_drone_sop_rows(
            rows=[
                {
                    "line_id": "L1",
                    "eqp_id": " eqp01 ",
                    "chamber_ids": "A",
                    "lot_id": "LOT.LOOKUP.NEW",
                    "main_step": "MS",
                    "needtosend": 0,
                    "status": "IN_PROGRESS",
                }
            ]
        )

        sop = DroneSOP.objects.get(lot_id="LOT.LOOKUP.NEW")
        self.assertEqual(sop.eqp_id_lookup, "EQP01")

    def test_upsert_repairs_missing_eqp_lookup_on_conflict(self) -> None:
        """기존 lookup이 비어 있어도 동일 SOP upsert 시 정규화 값을 복구합니다."""

        existing = _create_drone_sop(
            line_id="L1",
            eqp_id="EQP01",
            chamber_ids="A",
            lot_id="LOT.LOOKUP.EXISTING",
            main_step="MS",
        )
        DroneSOP.objects.filter(id=existing.id).update(eqp_id_lookup=None)

        upsert_drone_sop_rows(
            rows=[
                {
                    "line_id": "L1",
                    "eqp_id": "EQP01",
                    "chamber_ids": "A",
                    "lot_id": "LOT.LOOKUP.EXISTING",
                    "main_step": "MS",
                    "needtosend": 0,
                    "status": "IN_PROGRESS",
                }
            ]
        )

        existing.refresh_from_db()
        self.assertEqual(existing.eqp_id_lookup, "EQP01")

    def test_upsert_skips_delivery_snapshot_for_ineligible_row_with_target(self) -> None:
        """target이 이미 확정되어도 발송 조건 미충족 row는 delivery를 만들지 않습니다."""

        _ensure_target_mapping(
            sdwt_prod="SDWT-SKIP",
            user_sdwt_prod="USER-SKIP",
            target_user_sdwt_prod="TARGET-SKIP",
        )
        upsert_drone_sop_rows(
            rows=[
                {
                    "line_id": "L1",
                    "sdwt_prod": "SDWT-SKIP",
                    "user_sdwt_prod": "USER-SKIP",
                    "eqp_id": "EQP-SKIP",
                    "chamber_ids": "1",
                    "lot_id": "LOT.SKIP",
                    "main_step": "MS",
                    "needtosend": 0,
                    "instant_inform": 0,
                    "status": "IN_PROGRESS",
                }
            ]
        )

        sop = DroneSOP.objects.get(eqp_id="EQP-SKIP")
        self.assertEqual(sop.target_user_sdwt_prod, "TARGET-SKIP")
        self.assertFalse(DroneSopDelivery.objects.filter(sop=sop).exists())
        self.assertFalse(DroneSopTargetDispatch.objects.filter(sop=sop).exists())

    def test_upsert_marks_unconfigured_channel_snapshots_disabled(self) -> None:
        """신규 SOP upsert 시 미설정 채널 snapshot은 pending이 아니어야 합니다."""

        _ensure_target_mapping(
            sdwt_prod="SDWT-MULTI",
            user_sdwt_prod="USER-MULTI",
            target_user_sdwt_prod="TARGET-A",
        )
        upsert_drone_sop_rows(
            rows=[
                {
                    "line_id": "L1",
                    "sdwt_prod": "SDWT-MULTI",
                    "user_sdwt_prod": "USER-MULTI",
                    "eqp_id": "EQP-SNAPSHOT",
                    "chamber_ids": "1",
                    "lot_id": "LOT.SNAPSHOT",
                    "main_step": "MS",
                    "needtosend": 1,
                    "status": "COMPLETE",
                }
            ]
        )

        sop = DroneSOP.objects.get(eqp_id="EQP-SNAPSHOT")
        self.assertEqual(sop.target_user_sdwt_prod, "TARGET-A")
        deliveries = DroneSopDelivery.objects.filter(sop=sop).order_by("channel")
        self.assertEqual(deliveries.count(), 3)
        self.assertEqual(
            {
                (sop.target_user_sdwt_prod, delivery.channel, delivery.status, delivery.reason)
                for delivery in deliveries
            },
            {
                (
                    "TARGET-A",
                    DroneSopDelivery.Channels.JIRA,
                    DroneSopDelivery.Statuses.DISABLED,
                    "channel_config_missing",
                ),
                (
                    "TARGET-A",
                    DroneSopDelivery.Channels.MAIL,
                    DroneSopDelivery.Statuses.DISABLED,
                    "channel_config_missing",
                ),
                (
                    "TARGET-A",
                    DroneSopDelivery.Channels.MESSENGER,
                    DroneSopDelivery.Statuses.DISABLED,
                    "channel_config_missing",
                ),
            },
        )
        dispatch = DroneSopTargetDispatch.objects.get(sop=sop)
        self.assertEqual(dispatch.status, DroneSopTargetDispatch.Statuses.DISABLED)

    def test_existing_delivery_snapshot_ignores_later_mapping_changes(self) -> None:
        """snapshot 생성 후 추가된 mapping은 기존 SOP target에 자동 소급되지 않아야 합니다."""

        _ensure_target_mapping(
            sdwt_prod="SDWT-SNAPSHOT",
            user_sdwt_prod="USER-SNAPSHOT",
            target_user_sdwt_prod="TARGET-OLD",
        )
        upsert_drone_sop_rows(
            rows=[
                {
                    "line_id": "L1",
                    "sdwt_prod": "SDWT-SNAPSHOT",
                    "user_sdwt_prod": "USER-SNAPSHOT",
                    "eqp_id": "EQP-SNAPSHOT-LOCK",
                    "chamber_ids": "1",
                    "lot_id": "LOT.SNAPSHOT.LOCK",
                    "main_step": "MS",
                    "needtosend": 1,
                    "status": "COMPLETE",
                }
            ]
        )
        sop = DroneSOP.objects.get(eqp_id="EQP-SNAPSHOT-LOCK")

        DroneSopTargetMapping.objects.filter(
            sdwt_prod="SDWT-SNAPSHOT",
            user_sdwt_prod="USER-SNAPSHOT",
            target__target_user_sdwt_prod="TARGET-OLD",
        ).delete()
        _ensure_target_mapping(
            sdwt_prod="SDWT-SNAPSHOT",
            user_sdwt_prod="USER-SNAPSHOT",
            target_user_sdwt_prod="TARGET-NEW",
        )

        services.run_drone_sop_pipeline_from_settings()

        sop.refresh_from_db()
        self.assertEqual(sop.target_user_sdwt_prod, "TARGET-OLD")
        self.assertEqual(DroneSopDelivery.objects.filter(sop=sop).count(), 3)

    def test_upsert_does_not_update_comment_or_needtosend_on_conflict(self) -> None:
        """충돌 시 comment/needtosend가 덮어쓰이지 않는지 확인합니다."""
        existing = _create_drone_sop(
            comment="old",
            needtosend=0,
            status="IN_PROGRESS",
            metro_current_step="ST001",
            defect_url="https://example.com/old",
            target_user_sdwt_prod="old-target",
        )

        upsert_drone_sop_rows(
            rows=[
                {
                    "line_id": "L1",
                    "eqp_id": "EQP1",
                    "chamber_ids": "1",
                    "lot_id": "LOT.1",
                    "main_step": "MS",
                    "comment": "new",
                    "needtosend": 1,
                    "status": "COMPLETE",
                    "metro_current_step": "ST002",
                    "defect_url": "https://example.com/new",
                    "target_user_sdwt_prod": "new-target",
                }
            ]
        )

        refreshed = DroneSOP.objects.get(id=existing.id)
        self.assertEqual(refreshed.comment, "old")
        self.assertEqual(refreshed.needtosend, 0)
        self.assertEqual(refreshed.status, "COMPLETE")
        self.assertEqual(refreshed.metro_current_step, "ST002")
        self.assertEqual(refreshed.defect_url, "https://example.com/new")
        self.assertEqual(refreshed.target_user_sdwt_prod, "old-target")

    def test_upsert_persists_ctttm_urls(self) -> None:
        """POP3 upsert가 CTTTM URL JSON을 저장하는지 확인합니다."""

        ctttm_urls = [
            {"eqp_id": "EQP1-1", "url": "https://example.com/ctttm-1"},
            {"eqp_id": "EQP1-2", "url": "https://example.com/ctttm-2"},
        ]

        upsert_drone_sop_rows(
            rows=[
                {
                    "line_id": "L1",
                    "eqp_id": "EQP1",
                    "chamber_ids": "12",
                    "lot_id": "LOT.CTTTM",
                    "main_step": "MS",
                    "status": "COMPLETE",
                    "ctttm_urls": ctttm_urls,
                    "needtosend": 1,
                    "target_user_sdwt_prod": "TARGET-CTTTM",
                }
            ]
        )

        sop = DroneSOP.objects.get(lot_id="LOT.CTTTM")
        self.assertEqual(sop.ctttm_urls, ctttm_urls)

    def test_upsert_refreshes_updated_at_on_conflict(self) -> None:
        """POP3 upsert 충돌 갱신 시 updated_at도 최신화되는지 확인합니다."""

        existing = _create_drone_sop(
            line_id="L1",
            eqp_id="EQP-FRESH",
            chamber_ids="1",
            lot_id="LOT.FRESH",
            main_step="MS",
            metro_current_step="ST001",
            target_user_sdwt_prod="TARGET-FRESH",
        )
        old_updated_at = timezone.now() - timedelta(days=1)
        DroneSOP.objects.filter(id=existing.id).update(updated_at=old_updated_at)

        upsert_drone_sop_rows(
            rows=[
                {
                    "line_id": "L1",
                    "eqp_id": "EQP-FRESH",
                    "chamber_ids": "1",
                    "lot_id": "LOT.FRESH",
                    "main_step": "MS",
                    "metro_current_step": "ST002",
                    "needtosend": 1,
                    "status": "COMPLETE",
                    "target_user_sdwt_prod": "TARGET-FRESH",
                }
            ]
        )

        refreshed = DroneSOP.objects.get(id=existing.id)
        self.assertEqual(refreshed.metro_current_step, "ST002")
        self.assertGreater(refreshed.updated_at, old_updated_at)

    def test_upsert_does_not_clear_scalar_target_user_sdwt_prod_on_conflict(self) -> None:
        """충돌 시 비어 있는 target 값으로 기존 목적지 요약을 지우지 않아야 합니다."""
        existing = _create_drone_sop(
            line_id="L1",
            eqp_id="EQP1",
            chamber_ids="1",
            lot_id="LOT.1",
            main_step="MS",
            target_user_sdwt_prod="old-target",
        )

        upsert_drone_sop_rows(
            rows=[
                {
                    "line_id": "L1",
                    "eqp_id": "EQP1",
                    "chamber_ids": "1",
                    "lot_id": "LOT.1",
                    "main_step": "MS",
                    "needtosend": 1,
                    "status": "COMPLETE",
                    "target_user_sdwt_prod": None,
                }
            ]
        )

        refreshed = DroneSOP.objects.get(id=existing.id)
        self.assertEqual(refreshed.target_user_sdwt_prod, "old-target")
        self.assertEqual(DroneSopDelivery.objects.filter(sop=refreshed).count(), 3)

    def test_upsert_uses_single_target_dispatch_for_single_target_sop(self) -> None:
        """단일 target SOP는 하나의 dispatch만 생성한다는 전제를 고정합니다."""

        _ensure_target_mapping(
            sdwt_prod="SDWT-SINGLE",
            user_sdwt_prod="USER-SINGLE",
            target_user_sdwt_prod="TARGET-SINGLE",
        )
        upsert_drone_sop_rows(
            rows=[
                {
                    "line_id": "L1",
                    "sdwt_prod": "SDWT-SINGLE",
                    "user_sdwt_prod": "USER-SINGLE",
                    "eqp_id": "EQP-SINGLE",
                    "chamber_ids": "1",
                    "lot_id": "LOT.SINGLE",
                    "main_step": "MS",
                    "needtosend": 1,
                    "status": "COMPLETE",
                }
            ]
        )

        sop = DroneSOP.objects.get(eqp_id="EQP-SINGLE")
        dispatch_targets = list(
            DroneSopTargetDispatch.objects.filter(sop=sop).values_list(
                "target_code_snapshot",
                flat=True,
            )
        )
        self.assertEqual(dispatch_targets, ["TARGET-SINGLE"])


class DroneSopJiraCandidateTests(TestCase):
    """Jira 후보 조회 로직을 검증합니다."""

    def test_list_drone_sop_jira_candidates_filters_rows(self) -> None:
        """send_jira/needtosend/status/instant_inform 조건이 반영되는지 확인합니다."""
        _create_drone_sop(
            line_id="L1",
            eqp_id="EQP1",
            chamber_ids="1",
            lot_id="LOT.1",
            main_step="MS",
            status="COMPLETE",
            needtosend=1,
            send_jira=0,
        )
        _create_drone_sop(
            line_id="L2",
            eqp_id="EQP2",
            lot_id="LOT.2",
            status="IN_PROGRESS",
            needtosend=1,
            send_jira=0,
        )
        _create_drone_sop(
            line_id="L3",
            eqp_id="EQP3",
            lot_id="LOT.3",
            status="IN_PROGRESS",
            needtosend=0,
            instant_inform=1,
            send_jira=0,
        )

        rows = selectors.list_drone_sop_jira_candidates()
        self.assertEqual(len(rows), 2)
        self.assertEqual({row["line_id"] for row in rows}, {"L1", "L3"})

    def test_has_drone_sop_jira_candidates_returns_true_when_exists(self) -> None:
        """Jira 후보가 있으면 True를 반환하는지 확인합니다."""
        _create_drone_sop()

        self.assertTrue(selectors.has_drone_sop_jira_candidates())

    def test_has_drone_sop_jira_candidates_returns_false_when_empty(self) -> None:
        """Jira 후보가 없으면 False를 반환하는지 확인합니다."""
        self.assertFalse(selectors.has_drone_sop_jira_candidates())

    def test_list_drone_sop_jira_candidates_excludes_failed_delivery(self) -> None:
        """실패 delivery만 있는 SOP는 자동 Jira 후보에서 제외되는지 확인합니다."""
        sop = _create_drone_sop(send_jira=-1, jira_reason="send_failed", instant_inform=1)
        services.create_channel_delivery_with_dispatch(
            sop=sop,
            channel=DroneSopDelivery.Channels.JIRA,
            status=DroneSopDelivery.Statuses.FAILED,
            reason="send_failed",
        )

        rows = selectors.list_drone_sop_jira_candidates()

        self.assertNotIn(int(sop.id), {int(row["id"]) for row in rows})
        self.assertFalse(selectors.has_drone_sop_jira_candidates())


class DroneSopJiraUpdateTests(TestCase):
    """Jira 상태 업데이트 로직을 검증합니다."""

    def test_update_drone_sop_jira_status_skips_ineligible_row(self) -> None:
        """기존 delivery가 없으면 발송 조건 미충족 row의 delivery를 만들지 않습니다."""

        row = DroneSOP.objects.create(
            line_id="L1",
            sdwt_prod="SDWT-SKIP",
            user_sdwt_prod="USER-SKIP",
            target_user_sdwt_prod="TARGET-SKIP",
            eqp_id="EQP-SKIP",
            chamber_ids="1",
            lot_id="LOT.SKIP",
            main_step="MS",
            status="IN_PROGRESS",
            needtosend=0,
            instant_inform=0,
        )

        updated = update_drone_sop_jira_status(
            done_ids=[int(row.id)],
            rows=[{"id": int(row.id), "target_user_sdwt_prod": "TARGET-SKIP"}],
            key_by_id={int(row.id): "DUMMY-1"},
        )

        self.assertEqual(updated, 0)
        self.assertFalse(DroneSopDelivery.objects.filter(sop=row).exists())

    def test_update_drone_sop_jira_status_records_existing_delivery_when_unreserved(self) -> None:
        """예약 해제 후에도 이미 생성된 Jira delivery 성공 결과는 기록합니다."""

        row = _create_drone_sop(
            target_user_sdwt_prod="TARGET-DONE",
            eqp_id="EQP-DONE",
            lot_id="LOT.DONE",
            status="COMPLETE",
            needtosend=1,
        )
        delivery = services.create_channel_delivery_with_dispatch(
            sop=row,
            channel=DroneSopDelivery.Channels.JIRA,
            status=DroneSopDelivery.Statuses.PENDING,
        )
        row.status = "IN_PROGRESS"
        row.needtosend = 0
        row.save(update_fields=["status", "needtosend", "updated_at"])

        updated = update_drone_sop_jira_status(
            done_ids=[int(row.id)],
            rows=[{"id": int(row.id), "metro_current_step": "ST-DONE", "comment": "sent comment"}],
            key_by_id={int(row.id): "DUMMY-DONE-1"},
        )

        self.assertEqual(updated, 1)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, DroneSopDelivery.Statuses.SUCCESS)
        self.assertEqual(delivery.external_key, "DUMMY-DONE-1")
        self.assertEqual(delivery.sent_step, "ST-DONE")
        self.assertEqual(delivery.sent_comment, "sent comment")

    def test_update_drone_sop_jira_status_does_not_overwrite_cancelled_delivery(self) -> None:
        """취소된 Jira delivery는 뒤늦은 성공 동기화가 있어도 성공으로 덮어쓰지 않습니다."""

        row = _create_drone_sop(
            target_user_sdwt_prod="TARGET-CANCELLED",
            eqp_id="EQP-CANCELLED",
            lot_id="LOT.CANCELLED",
            status="COMPLETE",
            needtosend=1,
        )
        delivery = services.create_channel_delivery_with_dispatch(
            sop=row,
            channel=DroneSopDelivery.Channels.JIRA,
            status=DroneSopDelivery.Statuses.CANCELLED,
            reason="cancelled",
        )

        updated = update_drone_sop_jira_status(
            done_ids=[int(row.id)],
            rows=[{"id": int(row.id), "metro_current_step": "ST-CANCELLED", "comment": "sent comment"}],
            key_by_id={int(row.id): "DUMMY-CANCELLED-1"},
        )

        self.assertEqual(updated, 0)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, DroneSopDelivery.Statuses.CANCELLED)
        self.assertIsNone(delivery.external_key)
        self.assertIsNone(delivery.sent_step)
        self.assertIsNone(delivery.sent_comment)

    def test_update_drone_sop_jira_status_sets_send_jira_and_key(self) -> None:
        """send_jira/jira_key/inform_step이 갱신되는지 확인합니다."""
        row = _create_drone_sop(
            send_jira=0,
            metro_current_step="ST003",
        )

        updated = update_drone_sop_jira_status(
            done_ids=[int(row.id)],
            rows=[{"id": int(row.id), "metro_current_step": "ST003"}],
            key_by_id={int(row.id): "DUMMY-1"},
        )
        self.assertEqual(updated, 1)

        refreshed = DroneSOP.objects.get(id=row.id)
        self.assertEqual(_sop_delivery_value(refreshed, "sendJira"), 1)
        self.assertEqual(_sop_delivery_value(refreshed, "informStep"), "ST003")
        self.assertEqual(_sop_delivery_value(refreshed, "jiraKey"), "DUMMY-1")
        self.assertIsNotNone(_sop_delivery_value(refreshed, "informedAt"))

    def test_delivery_status_properties_use_prefetched_rows_without_queries(self) -> None:
        """delivery property가 prefetch된 row를 재사용하는지 확인합니다."""

        sent_at = timezone.now()
        row = _create_drone_sop(
            send_jira=1,
            send_mail=-1,
            jira_key="DUMMY-1",
            inform_step="ST003",
            informed_at=sent_at,
            mail_reason="send_failed",
            target_user_sdwt_prod="TARGET-PREFETCH",
        )
        prefetched = DroneSOP.objects.prefetch_related("channel_deliveries").get(id=row.id)

        with CaptureQueriesContext(connection) as captured_queries:
            self.assertEqual(_sop_delivery_value(prefetched, "sendJira"), 1)
            self.assertEqual(_sop_delivery_value(prefetched, "jiraKey"), "DUMMY-1")
            self.assertEqual(_sop_delivery_value(prefetched, "informStep"), "ST003")
            self.assertEqual(_sop_delivery_value(prefetched, "informedAt"), sent_at)
            self.assertEqual(_sop_delivery_value(prefetched, "sendMail"), -1)
            self.assertEqual(_sop_delivery_value(prefetched, "mailReason"), "send_failed")

        self.assertEqual(len(captured_queries), 0)


class DroneSelectorCaseInsensitiveTests(TestCase):
    """sdwt/user/target 소속 비교의 대소문자 비구분 동작을 검증합니다."""

    def test_list_distinct_line_ids_uses_drone_targets_only(self) -> None:
        """line 선택지는 Drone target에 설정된 line만 반환해야 합니다."""

        _upsert_target(
            line_id="CUSTOM_LINE",
            target_user_sdwt_prod="CUSTOM_TARGET",
        )
        DroneSOP.objects.create(
            line_id="L1",
            eqp_id="EQP-LINE",
            chamber_ids="CH-LINE",
            lot_id="LOT-LINE",
            main_step="STEP-LINE",
        )

        self.assertTrue(selectors.line_id_exists(line_id="l1"))
        self.assertTrue(selectors.line_id_exists(line_id="CUSTOM_LINE"))
        self.assertEqual(selectors.list_distinct_line_ids(), ["CUSTOM_LINE"])

    def test_tip_status_line_sdwt_options_use_drone_targets_with_station_match(self) -> None:
        """TIP status 선택지는 station_master에 있는 Drone target만 반환합니다."""

        _upsert_target(line_id="L1", target_user_sdwt_prod="SD-10")
        _upsert_target(line_id="L1", target_user_sdwt_prod="SD-20")
        _upsert_target(line_id="L2", target_user_sdwt_prod="SD-99")
        _upsert_target(line_id="", target_user_sdwt_prod="SD-EMPTY-LINE")

        with patch(
            "api.drone.selectors.targets.station_master_selectors.list_distinct_sdwt_prod_lookup_values",
            return_value={"SD-10", "SD-99"},
        ):
            payload = selectors.get_tip_status_line_sdwt_options_payload()

        self.assertEqual(
            payload,
            {
                "lines": [
                    {"lineId": "L1", "userSdwtProds": ["SD-10"]},
                    {"lineId": "L2", "userSdwtProds": ["SD-99"]},
                ],
                "userSdwtProds": ["SD-10", "SD-99"],
            },
        )

    def test_selector_lookups_ignore_case_for_user_sdwt_prod_and_target(self) -> None:
        """소속/채널/수신자 조회가 대소문자를 무시하는지 확인합니다."""
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S71000",
            password="test-password",
            knox_id="knox-71000",
            email="user71000@example.com",
        )
        _set_current_affiliation(user, department="Dept", line="L1", user_sdwt_prod="TARGET-SDWT")
        account_services.ensure_affiliation_option(
            department="Dept",
            line="L1",
            user_sdwt_prod="TARGET-SDWT",
        )
        _upsert_target(
            line_id="L1",
            target_user_sdwt_prod="TARGET-SDWT",
            jira_key="PROJ",
            jira_template_key="common",
            needtosend_comment_last_at="$END",
            needtosend_ignore_sample_type=False,
            needtosend_enabled=True,
        )
        _create_target_recipient(
            target_user_sdwt_prod="TARGET-SDWT",
            channel=DroneSopTargetRecipient.Channels.MAIL,
            user=user,
        )
        _create_target_recipient(
            target_user_sdwt_prod="TARGET-SDWT",
            channel=DroneSopTargetRecipient.Channels.MESSENGER,
            user=user,
        )

        rule = selectors.get_drone_sop_needtosend_rule_by_target(target_user_sdwt_prod="target-sdwt")
        channel = selectors.get_drone_sop_channel_by_target_user_sdwt_prod(
            target_user_sdwt_prod="target-sdwt"
        )
        line_ids = selectors.list_line_ids_for_user_sdwt_prod(user_sdwt_prod="target-sdwt")
        emails = selectors.list_mail_receiver_emails_for_user_sdwt_prod(line_id="L1", user_sdwt_prod="target-sdwt")
        knox_ids = selectors.list_messenger_receiver_knox_ids_for_user_sdwt_prod(
            line_id="L1",
            user_sdwt_prod="target-sdwt"
        )

        self.assertIsNotNone(rule)
        if rule is None:
            return
        self.assertEqual(rule.comment_keyword, "$END")
        self.assertIsNotNone(channel)
        if channel is None:
            return
        self.assertEqual(_target_configuration_value(channel, "jiraKey"), "PROJ")
        self.assertEqual(line_ids, ["L1"])
        self.assertEqual(emails, ["user71000@example.com"])
        self.assertEqual(knox_ids, ["knox-71000"])

    def test_build_drone_sop_row_applies_custom_end_step_case_insensitively(self) -> None:
        """조기 알림 custom_end_step 매핑이 user_sdwt_prod 대소문자를 무시하는지 확인합니다."""
        _upsert_target(line_id="L1", target_user_sdwt_prod="TARGET-SDWT")
        DroneEarlyInform.objects.create(
            line_id="L1",
            main_step="MS",
            custom_end_step="ST003",
        )

        early_inform_map = selectors.load_drone_sop_custom_end_step_map()
        row = build_drone_sop_row(
            html=(
                "<html><body><data>"
                "<line_id>L1</line_id>"
                "<main_step>MS</main_step>"
                "<metro_current_step>ST003</metro_current_step>"
                "<status>IN_PROGRESS</status>"
                "<user_sdwt_prod>target-sdwt</user_sdwt_prod>"
                "</data></body></html>"
            ),
            early_inform_map=early_inform_map,
        )

        self.assertIsNotNone(row)
        if row is None:
            return
        self.assertEqual(row["custom_end_step"], "ST003")
        self.assertEqual(row["status"], "COMPLETE")


class DroneSopObserverSelectorTests(TestCase):
    """Observer ESOP 설비·챔버 조회 규칙을 검증합니다."""

    @classmethod
    def setUpTestData(cls) -> None:
        """여러 챔버를 포함한 ESOP와 비교용 다른 설비를 생성합니다."""

        cls.esop = DroneSOP.objects.create(
            line_id="L1",
            eqp_id="EQP01",
            chamber_ids="ABC",
            lot_id="LOT.OBSERVER.ABC",
            main_step="MS",
        )
        DroneSOP.objects.create(
            line_id="L1",
            eqp_id="EQP02",
            chamber_ids="ABC",
            lot_id="LOT.OBSERVER.OTHER",
            main_step="MS",
        )

    def _fetch_ids(self, eqp_id: str) -> list[int]:
        """지정한 Observer EQP 범위의 ESOP source ID 목록을 반환합니다."""

        now = timezone.now()
        rows, _ = selectors.fetch_drone_sop_timeline_page(
            eqp_id=eqp_id,
            start_at=now - timedelta(days=1),
            end_at=now + timedelta(days=1),
            page_size=10,
        )
        return [int(row["id"]) for row in rows]

    def test_page_matches_each_character_in_multi_chamber_value(self) -> None:
        """ABC 저장값은 A, B, C 챔버 조회에 각각 포함됩니다."""

        for chamber in ("A", "B", "C"):
            with self.subTest(chamber=chamber):
                self.assertEqual(
                    self._fetch_ids(f"EQP01-{chamber}"),
                    [self.esop.id],
                )

    def test_page_excludes_unmatched_chamber(self) -> None:
        """저장값에 없는 챔버는 ESOP page에서 제외됩니다."""

        self.assertEqual(self._fetch_ids("EQP01-D"), [])

    def test_page_without_chamber_returns_all_base_eqp_chambers(self) -> None:
        """챔버 suffix가 없으면 기본 설비의 모든 챔버를 반환합니다."""

        self.assertEqual(self._fetch_ids("eqp01"), [self.esop.id])

    def test_detail_uses_same_eqp_chamber_scope_as_page(self) -> None:
        """상세 조회도 page와 동일한 설비·챔버 범위를 적용합니다."""

        matched = selectors.get_drone_sop_timeline_detail(
            eqp_id="EQP01-B",
            source_id=self.esop.id,
        )
        unmatched = selectors.get_drone_sop_timeline_detail(
            eqp_id="EQP01-D",
            source_id=self.esop.id,
        )

        self.assertIsNotNone(matched)
        self.assertIsNone(unmatched)
