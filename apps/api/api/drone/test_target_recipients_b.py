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

class DroneSopTargetRecipientTestsPart3(TestCase):
    """DroneSopTargetRecipientTests 분리 회귀 테스트 3부입니다."""

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

    def test_my_notification_recipient_targets_returns_current_user_targets(self) -> None:
        """일반 사용자도 본인이 수신인으로 등록된 target 목록은 조회할 수 있어야 합니다."""

        target = _upsert_target(line_id="L1", target_user_sdwt_prod="ETCH_A")
        other_target = _upsert_target(line_id="L1", target_user_sdwt_prod="PHOTO_B")
        DroneSopTargetRecipient.objects.create(
            target=target,
            channel=DroneSopTargetRecipient.Channels.MAIL,
            user=self.same_group_user,
        )
        DroneSopTargetRecipient.objects.create(
            target=target,
            channel=DroneSopTargetRecipient.Channels.MESSENGER,
            user=self.same_group_user,
        )
        DroneSopTargetRecipient.objects.create(
            target=other_target,
            channel=DroneSopTargetRecipient.Channels.MAIL,
            user=self.mail_user,
        )

        self.client.force_login(self.same_group_user)
        response = self.client.get(
            reverse("line-dashboard-my-notification-recipient-targets"),
            {"lineId": "L1"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["lineId"], "L1")
        self.assertEqual(len(payload["targets"]), 1)
        self.assertEqual(payload["targets"][0]["targetUserSdwtProd"], "ETCH_A")
        self.assertEqual(payload["targets"][0]["lineId"], "L1")
        self.assertEqual(payload["targets"][0]["channels"], ["mail", "messenger"])

    def test_my_notification_recipient_targets_filters_by_line(self) -> None:
        """본인 수신 target 목록은 요청 lineId 범위로 제한되어야 합니다."""

        line_one_target = _upsert_target(line_id="L1", target_user_sdwt_prod="ETCH_A")
        line_two_target = _upsert_target(line_id="L2", target_user_sdwt_prod="DIFF_A")
        DroneSopTargetRecipient.objects.create(
            target=line_one_target,
            channel=DroneSopTargetRecipient.Channels.MAIL,
            user=self.same_group_user,
        )
        DroneSopTargetRecipient.objects.create(
            target=line_two_target,
            channel=DroneSopTargetRecipient.Channels.MAIL,
            user=self.same_group_user,
        )

        self.client.force_login(self.same_group_user)
        response = self.client.get(
            reverse("line-dashboard-my-notification-recipient-targets"),
            {"lineId": "L2"},
        )

        self.assertEqual(response.status_code, 200)
        targets = response.json()["targets"]
        self.assertEqual([row["targetUserSdwtProd"] for row in targets], ["DIFF_A"])

    @override_settings(
        DRONE_SOP_ENGR_FALLBACK_VALUES="",
        DRONE_SOP_USER_SDWT_OVERRIDE_MAP="",
    )
    def test_notification_target_endpoint_uses_drone_targets_for_mapping_options(self) -> None:
        """알림 target 및 지정 조합 옵션은 Drone target 기준으로 반환합니다."""

        _upsert_target(
            line_id="L1",
            target_user_sdwt_prod="CUSTOM_TARGET",
            jira_enabled=False,
            messenger_enabled=True,
            mail_enabled=False,
        )
        _upsert_target(
            line_id="L2",
            target_user_sdwt_prod="OTHER_LINE_TARGET",
        )
        _ensure_target_mapping(
            sdwt_prod="SDWT_A",
            user_sdwt_prod="USER_A",
            target_user_sdwt_prod="CUSTOM_TARGET",
        )
        account_services.ensure_affiliation_option(
            department="Dept",
            line="L1",
            user_sdwt_prod="ETCH_A",
        )
        DroneSOP.objects.create(
            line_id="L1",
            sdwt_prod="SDWT_A",
            user_sdwt_prod="USER_A",
            eqp_id="EQP-A",
            chamber_ids="CH-A",
            lot_id="LOT-A",
            main_step="STEP-A",
        )
        DroneSOP.objects.create(
            line_id="L1",
            sdwt_prod="SOP_ONLY_S",
            user_sdwt_prod="SOP_ONLY_U",
            eqp_id="EQP-A2",
            chamber_ids="CH-A2",
            lot_id="LOT-A2",
            main_step="STEP-A2",
        )
        DroneSOP.objects.create(
            line_id="L2",
            sdwt_prod="SDWT_B",
            user_sdwt_prod="USER_B",
            eqp_id="EQP-B",
            chamber_ids="CH-B",
            lot_id="LOT-B",
            main_step="STEP-B",
        )

        self.client.force_login(self.actor)
        response = self.client.get(reverse("line-dashboard-notification-targets"), {"lineId": "L1"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("CUSTOM_TARGET", payload["targetUserSdwtProds"])
        self.assertNotIn("ETCH_A", payload["targetUserSdwtProds"])
        custom_target = next(
            row for row in payload["targets"] if row["targetUserSdwtProd"] == "CUSTOM_TARGET"
        )
        self.assertFalse(custom_target["jiraEnabled"])
        self.assertTrue(custom_target["messengerEnabled"])
        self.assertFalse(custom_target["mailEnabled"])
        self.assertEqual(
            custom_target["mappings"],
            [
                {
                    "sdwtProd": "SDWT_A",
                    "userSdwtProd": "USER_A",
                    "needtosendWithoutComment": False,
                }
            ],
        )
        self.assertEqual(
            payload["mappingOptions"]["userSdwtProds"],
            ["CUSTOM_TARGET"],
        )
        self.assertEqual(
            payload["mappingOptions"]["sdwtProds"],
            ["CUSTOM_TARGET"],
        )
        self.assertEqual(
            payload["mappingOptionLines"],
            [
                {"lineId": "L1", "userSdwtProds": ["CUSTOM_TARGET"]},
                {"lineId": "L2", "userSdwtProds": ["OTHER_LINE_TARGET"]},
            ],
        )

    @override_settings(
        DRONE_SOP_ENGR_FALLBACK_VALUES="EARSAUTO",
        DRONE_SOP_USER_SDWT_OVERRIDE_MAP='{"custom-key":"CUSTOM_ENV"}',
    )
    def test_notification_target_endpoint_uses_settings_for_engr_mapping_options(self) -> None:
        """Engr 지정 조합 옵션은 settings fallback과 override map을 반영합니다."""

        _upsert_target(
            line_id="L1",
            target_user_sdwt_prod="CUSTOM_TARGET",
        )

        self.client.force_login(self.actor)
        response = self.client.get(reverse("line-dashboard-notification-targets"), {"lineId": "L1"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            payload["mappingOptions"]["userSdwtProds"],
            ["CUSTOM_TARGET"],
        )
        self.assertEqual(payload["mappingOptions"]["sdwtProds"], ["CUSTOM_TARGET"])
        self.assertEqual(
            payload["mappingOptionLines"],
            [
                {"lineId": "L1", "userSdwtProds": ["CUSTOM_TARGET"]},
                {"lineId": "System", "userSdwtProds": ["CUSTOM_ENV", "EARSAUTO"]},
            ],
        )

    def test_notification_target_endpoint_creates_custom_target(self) -> None:
        """외부 소속표에 없는 임의 line에도 커스텀 target을 생성할 수 있어야 합니다."""

        self.client.force_login(self.actor)
        response = self.client.post(
            reverse("line-dashboard-notification-targets"),
            data=json.dumps({"lineId": "BRAND_NEW_LINE", "targetUserSdwtProd": "L1_NIGHT_SHIFT"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        target = DroneSopTarget.objects.get(target_user_sdwt_prod="L1_NIGHT_SHIFT")
        self.assertEqual(target.line_id, "BRAND_NEW_LINE")
        self.assertEqual(response.json()["target"]["source"], DroneSopTarget.Sources.CUSTOM)

    def test_notification_target_endpoint_rejects_duplicate_target(self) -> None:
        """이미 등록된 알림 target은 중복 생성하지 않고 409를 반환해야 합니다."""

        _upsert_target(
            line_id="L1",
            target_user_sdwt_prod="L1_NIGHT_SHIFT",
        )

        self.client.force_login(self.actor)
        response = self.client.post(
            reverse("line-dashboard-notification-targets"),
            data=json.dumps({"lineId": "L1", "targetUserSdwtProd": "l1_night_shift"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"], "notification target already exists")
        self.assertEqual(
            DroneSopTarget.objects.filter(target_user_sdwt_prod__iexact="L1_NIGHT_SHIFT").count(),
            1,
        )

    def test_notification_target_mapping_validation_error_contract(self) -> None:
        """mapping operation별 serializer 오류가 기존 HTTP 문구를 유지하는지 확인합니다."""

        self.client.force_login(self.actor)
        url = reverse("line-dashboard-notification-target-mappings")
        create_response = self.client.post(
            url,
            data=json.dumps({"lineId": "L1"}),
            content_type="application/json",
        )
        update_response = self.client.patch(
            url,
            data=json.dumps(
                {
                    "lineId": "L1",
                    "targetUserSdwtProd": "TARGET_A",
                    "sdwtProd": "SDWT_A",
                    "userSdwtProd": "USER_A",
                }
            ),
            content_type="application/json",
        )
        delete_response = self.client.delete(
            url,
            data=json.dumps(
                {
                    "lineId": "L1",
                    "targetUserSdwtProd": "TARGET_A",
                    "sdwtProd": "SDWT_A",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(create_response.status_code, 400)
        self.assertEqual(
            create_response.json(),
            {"error": "targetUserSdwtProd is required"},
        )
        self.assertEqual(update_response.status_code, 400)
        self.assertEqual(
            update_response.json(),
            {"error": "needtosendWithoutComment must be bool"},
        )
        self.assertEqual(delete_response.status_code, 400)
        self.assertEqual(
            delete_response.json(),
            {"error": "userSdwtProd is required"},
        )

    def test_notification_target_mapping_endpoint_adds_mapping(self) -> None:
        """지정 조합 API가 target row와 mapping row를 함께 생성하는지 확인합니다."""

        self.client.force_login(self.actor)
        response = self.client.post(
            reverse("line-dashboard-notification-target-mappings"),
            data=json.dumps(
                {
                    "lineId": "L1",
                    "targetUserSdwtProd": "CUSTOM_TARGET",
                    "sdwtProd": "SDWT_A",
                    "userSdwtProd": "USER_A",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["target"]["targetUserSdwtProd"], "CUSTOM_TARGET")
        self.assertEqual(
            payload["target"]["mappings"],
            [
                {
                    "sdwtProd": "SDWT_A",
                    "userSdwtProd": "USER_A",
                    "needtosendWithoutComment": False,
                }
            ],
        )
        self.assertTrue(
            DroneSopTargetMapping.objects.filter(
                sdwt_prod="SDWT_A",
                user_sdwt_prod="USER_A",
                target__target_user_sdwt_prod="CUSTOM_TARGET",
            ).exists()
        )
        self.assertTrue(
            DroneSopTarget.objects.filter(
                line_id="L1",
                target_user_sdwt_prod="CUSTOM_TARGET",
            ).exists()
        )

    def test_notification_target_mapping_endpoint_rejects_duplicate_mapping(self) -> None:
        """이미 등록된 지정 조합은 중복 생성하지 않고 409를 반환해야 합니다."""

        _ensure_target_mapping(
            sdwt_prod="SDWT_A",
            user_sdwt_prod="USER_A",
            target_user_sdwt_prod="CUSTOM_TARGET",
        )

        self.client.force_login(self.actor)
        response = self.client.post(
            reverse("line-dashboard-notification-target-mappings"),
            data=json.dumps(
                {
                    "lineId": "L1",
                    "targetUserSdwtProd": "CUSTOM_TARGET",
                    "sdwtProd": "sdwt_a",
                    "userSdwtProd": "user_a",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"], "target mapping already exists")
        self.assertFalse(
            DroneSopTarget.objects.filter(
                line_id="L1",
                target_user_sdwt_prod="CUSTOM_TARGET",
            ).exists()
        )

    def test_notification_target_mapping_endpoint_deletes_mapping(self) -> None:
        """지정 조합 삭제 API가 대상 mapping row를 제거하고 갱신된 target을 반환해야 합니다."""

        target = _upsert_target(line_id="L1", target_user_sdwt_prod="CUSTOM_TARGET")
        DroneSopTargetMapping.objects.create(
            sdwt_prod="SDWT_A",
            user_sdwt_prod="USER_A",
            target=target,
        )
        DroneSopTargetMapping.objects.create(
            sdwt_prod="SDWT_B",
            user_sdwt_prod="USER_B",
            target=target,
        )

        self.client.force_login(self.actor)
        response = self.client.delete(
            reverse("line-dashboard-notification-target-mappings"),
            data=json.dumps(
                {
                    "lineId": "L1",
                    "targetUserSdwtProd": "CUSTOM_TARGET",
                    "sdwtProd": "sdwt_a",
                    "userSdwtProd": "user_a",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["deleted"], {"sdwtProd": "sdwt_a", "userSdwtProd": "user_a"})
        self.assertEqual(
            payload["target"]["mappings"],
            [
                {
                    "sdwtProd": "SDWT_B",
                    "userSdwtProd": "USER_B",
                    "needtosendWithoutComment": False,
                }
            ],
        )
        self.assertFalse(
            DroneSopTargetMapping.objects.filter(
                sdwt_prod="SDWT_A",
                user_sdwt_prod="USER_A",
                target__target_user_sdwt_prod="CUSTOM_TARGET",
            ).exists()
        )
        self.assertTrue(
            DroneSopTargetMapping.objects.filter(
                sdwt_prod="SDWT_B",
                user_sdwt_prod="USER_B",
                target__target_user_sdwt_prod="CUSTOM_TARGET",
            ).exists()
        )

class DroneSopTargetRecipientTestsPart4(TestCase):
    """DroneSopTargetRecipientTests 분리 회귀 테스트 4부입니다."""

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

    def test_notification_target_mapping_endpoint_updates_commentless_reservation(self) -> None:
        """지정 조합 PATCH가 Comment 생략 예약 정책과 응답을 갱신합니다."""

        target = _upsert_target(line_id="L1", target_user_sdwt_prod="CUSTOM_TARGET")
        DroneSopTargetMapping.objects.create(
            sdwt_prod="A",
            user_sdwt_prod="EARSAUTO",
            target=target,
        )

        self.client.force_login(self.actor)
        response = self.client.patch(
            reverse("line-dashboard-notification-target-mappings"),
            data=json.dumps(
                {
                    "lineId": "L1",
                    "targetUserSdwtProd": "CUSTOM_TARGET",
                    "sdwtProd": "A",
                    "userSdwtProd": "EARSAUTO",
                    "needtosendWithoutComment": True,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        mapping = DroneSopTargetMapping.objects.get(target=target)
        self.assertTrue(mapping.needtosend_without_comment)
        self.assertEqual(
            response.json()["mapping"],
            {
                "sdwtProd": "A",
                "userSdwtProd": "EARSAUTO",
                "needtosendWithoutComment": True,
            },
        )
        self.assertTrue(response.json()["target"]["mappings"][0]["needtosendWithoutComment"])

    def test_notification_target_mapping_endpoint_delete_returns_404_for_missing_mapping(self) -> None:
        """삭제할 지정 조합이 없으면 404를 반환해야 합니다."""

        self.client.force_login(self.actor)
        response = self.client.delete(
            reverse("line-dashboard-notification-target-mappings"),
            data=json.dumps(
                {
                    "lineId": "L1",
                    "targetUserSdwtProd": "CUSTOM_TARGET",
                    "sdwtProd": "SDWT_A",
                    "userSdwtProd": "USER_A",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"], "target mapping not found")

    def test_notification_target_mapping_endpoint_rejects_same_pair_for_multiple_targets(self) -> None:
        """같은 지정 조합은 다른 알림 target에도 중복 연결할 수 없어야 합니다."""

        _ensure_target_mapping(
            sdwt_prod="SDWT_A",
            user_sdwt_prod="USER_A",
            target_user_sdwt_prod="CUSTOM_TARGET_A",
        )

        self.client.force_login(self.actor)
        response = self.client.post(
            reverse("line-dashboard-notification-target-mappings"),
            data=json.dumps(
                {
                    "lineId": "L1",
                    "targetUserSdwtProd": "CUSTOM_TARGET_B",
                    "sdwtProd": "SDWT_A",
                    "userSdwtProd": "USER_A",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"], "target mapping already exists")
        self.assertEqual(
            DroneSopTargetMapping.objects.filter(
                sdwt_prod__iexact="SDWT_A",
                user_sdwt_prod__iexact="USER_A",
            ).count(),
            1,
        )
        self.assertFalse(
            DroneSopTarget.objects.filter(
                line_id="L1",
                target_user_sdwt_prod="CUSTOM_TARGET_B",
            ).exists()
        )

    def test_target_mapping_db_constraint_rejects_same_pair_for_multiple_targets(self) -> None:
        """DB constraint도 같은 지정 조합의 다중 target 연결을 거부해야 합니다."""

        _ensure_target_mapping(
            sdwt_prod="SDWT_A",
            user_sdwt_prod="USER_A",
            target_user_sdwt_prod="CUSTOM_TARGET_A",
        )
        duplicate_target, _ = DroneSopTarget.objects.get_or_create(
            target_user_sdwt_prod="CUSTOM_TARGET_B",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                DroneSopTargetMapping.objects.create(
                    sdwt_prod="sdwt_a",
                    user_sdwt_prod="user_a",
                    target=duplicate_target,
                )

    def test_notification_target_endpoint_allows_new_line(self) -> None:
        """알림 target 생성은 account에 없는 신규 line도 허용해야 합니다."""

        self.client.force_login(self.actor)
        response = self.client.post(
            reverse("line-dashboard-notification-targets"),
            data=json.dumps({"lineId": "CUSTOM_LINE", "targetUserSdwtProd": "CUSTOM_TARGET"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            DroneSopTarget.objects.filter(
                line_id="CUSTOM_LINE",
                target_user_sdwt_prod="CUSTOM_TARGET",
            ).exists()
        )

    def test_notification_recipient_endpoint_empty_list_deletes_recipients(self) -> None:
        """빈 userIds 저장은 기존 수신인을 모두 삭제해야 합니다."""

        recipient = _create_target_recipient(
            target_user_sdwt_prod="ETCH_A",
            channel=DroneSopTargetRecipient.Channels.MAIL,
            user=self.mail_user,
        )

        self.client.force_login(self.actor)
        response = self.client.put(
            reverse("line-dashboard-notification-recipients"),
            data=json.dumps(
                {
                    "lineId": "L1",
                    "targetUserSdwtProd": "ETCH_A",
                    "channel": "mail",
                    "userIds": [],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(DroneSopTargetRecipient.objects.filter(id=recipient.id).exists())
        self.assertEqual(response.json()["recipients"], [])

    def test_notification_recipient_endpoint_empty_list_deletes_joined_external_recipient(self) -> None:
        """가입자 knox_id와 겹치는 기존 외부 수신인도 빈 목록 저장으로 삭제해야 합니다."""

        recipient = _create_target_recipient(
            target_user_sdwt_prod="ETCH_A",
            channel=DroneSopTargetRecipient.Channels.MAIL,
            external_knox_id="external-71031",
        )
        User = get_user_model()
        User.objects.create_user(
            sabun="S71031",
            password="test-password",
            knox_id="external-71031",
            email="external-71031@samsung.com",
        )

        self.client.force_login(self.actor)
        response = self.client.put(
            reverse("line-dashboard-notification-recipients"),
            data=json.dumps(
                {
                    "lineId": "L1",
                    "targetUserSdwtProd": "ETCH_A",
                    "channel": "mail",
                    "userIds": [],
                    "externalKnoxIds": [],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(DroneSopTargetRecipient.objects.filter(id=recipient.id).exists())
        self.assertEqual(response.json()["recipients"], [])

    def test_notification_recipient_endpoint_rejects_boolean_user_id(self) -> None:
        """userIds의 boolean 값은 정수 id로 오해하지 않고 거부해야 합니다."""

        self.client.force_login(self.actor)
        response = self.client.put(
            reverse("line-dashboard-notification-recipients"),
            data=json.dumps(
                {
                    "lineId": "L1",
                    "targetUserSdwtProd": "ETCH_A",
                    "channel": "mail",
                    "userIds": [True],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "userIds must contain only integers")
        self.assertFalse(
            DroneSopTargetRecipient.objects.filter(
                target__target_user_sdwt_prod="ETCH_A",
                channel=DroneSopTargetRecipient.Channels.MAIL,
            ).exists()
        )

    def test_notification_recipient_endpoint_rejects_mail_user_without_email(self) -> None:
        """메일 수신인에는 email이 있는 사용자만 저장할 수 있어야 합니다."""

        User = get_user_model()
        no_email_user = User.objects.create_user(
            sabun="S71003",
            password="test-password",
            knox_id="knox-71003",
        )
        _set_current_affiliation(no_email_user, user_sdwt_prod="PHOTO_B")

        self.client.force_login(self.actor)
        response = self.client.put(
            reverse("line-dashboard-notification-recipients"),
            data=json.dumps(
                {
                    "lineId": "L1",
                    "targetUserSdwtProd": "ETCH_A",
                    "channel": "mail",
                    "userIds": [no_email_user.id],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "mail recipients require email")
        self.assertFalse(
            DroneSopTargetRecipient.objects.filter(
                target__target_user_sdwt_prod="ETCH_A",
                channel=DroneSopTargetRecipient.Channels.MAIL,
                user=no_email_user,
            ).exists()
        )

    def test_notification_recipient_endpoint_replaces_messenger_recipients(self) -> None:
        """수신인 API가 메신저 채널도 최종 userIds 스냅샷으로 저장하는지 확인합니다."""

        self.client.force_login(self.actor)
        response = self.client.put(
            reverse("line-dashboard-notification-recipients"),
            data=json.dumps(
                {
                    "lineId": "L1",
                    "targetUserSdwtProd": "ETCH_A",
                    "channel": "messenger",
                    "userIds": [self.mail_user.id],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["channel"], "messenger")
        self.assertEqual([row["userId"] for row in payload["recipients"]], [self.mail_user.id])

    def test_notification_recipient_endpoint_rejects_messenger_user_without_knox_id(self) -> None:
        """메신저 수신인에는 knox_id가 있는 사용자만 저장할 수 있어야 합니다."""

        User = get_user_model()
        no_knox_user = User.objects.create_user(
            sabun="S71004",
            password="test-password",
            email="no-knox@example.com",
        )
        _set_current_affiliation(no_knox_user, user_sdwt_prod="PHOTO_B")

        self.client.force_login(self.actor)
        response = self.client.put(
            reverse("line-dashboard-notification-recipients"),
            data=json.dumps(
                {
                    "lineId": "L1",
                    "targetUserSdwtProd": "ETCH_A",
                    "channel": "messenger",
                    "userIds": [no_knox_user.id],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "messenger recipients require knox_id")
        self.assertFalse(
            DroneSopTargetRecipient.objects.filter(
                target__target_user_sdwt_prod="ETCH_A",
                channel=DroneSopTargetRecipient.Channels.MESSENGER,
                user=no_knox_user,
            ).exists()
        )
