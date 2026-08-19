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

class DroneTriggerAuthTests(TestCase):
    """트리거 엔드포인트 인증을 검증합니다."""
    @override_settings(AIRFLOW_TRIGGER_TOKEN="expected-token")
    @patch("api.drone.views.triggers.services.run_drone_sop_pop3_ingest_from_settings")
    def test_pop3_ingest_trigger_requires_token(self, mock_run: Mock) -> None:
        """POP3 트리거가 토큰을 요구하는지 확인합니다."""
        mock_run.return_value = SimpleNamespace(
            matched_mails=1,
            upserted_rows=2,
            deleted_mails=3,
            pruned_rows=4,
            skipped=False,
            skip_reason=None,
        )

        url = reverse("drone-sop-pop3-ingest-trigger")

        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(mock_run.call_count, 0)

        resp = self.client.post(url, HTTP_AUTHORIZATION="Bearer wrong-token")
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(mock_run.call_count, 0)

        resp = self.client.post(
            url,
            data=json.dumps({}),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer expected-token",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["matched"], 1)
        self.assertEqual(mock_run.call_count, 1)

    @override_settings(AIRFLOW_TRIGGER_TOKEN="expected-token")
    @patch("api.drone.views.triggers.services.run_drone_sop_pipeline_from_settings")
    def test_pipeline_trigger_requires_token(self, mock_run: Mock) -> None:
        """통합 파이프라인 트리거가 토큰을 요구하는지 확인합니다."""
        mock_run.return_value = SimpleNamespace(
            candidates=1,
            jira_created=1,
            jira_updated_rows=0,
            messenger_sent=0,
            mail_sent=0,
            skipped=False,
            skip_reason=None,
        )

        url = reverse("drone-sop-pipeline-trigger")

        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(mock_run.call_count, 0)

        resp = self.client.post(
            url,
            data=json.dumps({}),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer expected-token",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["jiraCreated"], 1)
        mock_run.assert_called_once_with(limit=None)

    @override_settings(AIRFLOW_TRIGGER_TOKEN="expected-token")
    @patch("api.drone.views.triggers.services.run_drone_sop_pipeline_from_settings")
    def test_legacy_inform_trigger_alias_is_removed(self, mock_run: Mock) -> None:
        """레거시 inform 트리거 경로가 제거되었는지 확인합니다."""

        url = "/api/v1/line-dashboard/sop/inform/trigger"
        resp = self.client.post(url, HTTP_AUTHORIZATION="Bearer expected-token")
        self.assertEqual(resp.status_code, 404)
        mock_run.assert_not_called()

    @override_settings(AIRFLOW_TRIGGER_TOKEN="expected-token")
    @patch("api.drone.views.triggers.services.has_drone_sop_pipeline_candidates")
    def test_pipeline_precheck_requires_token(self, mock_service: Mock) -> None:
        """통합 파이프라인 precheck가 토큰을 요구하는지 확인합니다."""
        mock_service.return_value = True
        url = reverse("drone-sop-pipeline-precheck")

        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(mock_service.call_count, 0)

        resp = self.client.post(url, HTTP_AUTHORIZATION="Bearer expected-token")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json().get("hasCandidates"))
        mock_service.assert_called_once_with()

    @override_settings(AIRFLOW_TRIGGER_TOKEN="expected-token")
    @patch("api.drone.views.triggers.services.run_drone_sop_pipeline_from_settings")
    def test_pipeline_trigger_prefers_payload_limit_over_query_param(self, mock_run: Mock) -> None:
        """통합 파이프라인에서 payload limit가 query param보다 우선되는지 확인합니다."""
        mock_run.return_value = SimpleNamespace(
            candidates=1,
            jira_created=1,
            jira_updated_rows=1,
            messenger_sent=1,
            mail_sent=1,
            skipped=False,
            skip_reason=None,
        )

        url = reverse("drone-sop-pipeline-trigger") + "?limit=5"
        payload = json.dumps({"limit": 2})
        resp = self.client.post(
            url,
            data=payload,
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer expected-token",
        )

        self.assertEqual(resp.status_code, 200)
        mock_run.assert_called_once_with(limit=2)

    @override_settings(AIRFLOW_TRIGGER_TOKEN="expected-token")
    @patch("api.drone.views.triggers.services.run_drone_sop_pipeline_from_settings")
    def test_pipeline_trigger_ignores_channels_payload(self, mock_run: Mock) -> None:
        """통합 파이프라인 트리거는 channels 입력을 무시하는지 확인합니다."""
        mock_run.return_value = SimpleNamespace(
            candidates=1,
            jira_created=1,
            jira_updated_rows=1,
            messenger_sent=1,
            mail_sent=1,
            skipped=False,
            skip_reason=None,
        )

        url = reverse("drone-sop-pipeline-trigger")
        payload = json.dumps({"channels": ["jira", "mail"]})
        resp = self.client.post(
            url,
            data=payload,
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer expected-token",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("channels", resp.json())
        mock_run.assert_called_once_with(limit=None)

    @override_settings(AIRFLOW_TRIGGER_TOKEN="expected-token")
    @patch("api.drone.views.triggers.services.has_drone_sop_pipeline_candidates")
    def test_pipeline_precheck_ignores_channels_payload(self, mock_service: Mock) -> None:
        """통합 파이프라인 precheck는 channels 입력을 무시하는지 확인합니다."""
        mock_service.return_value = True
        url = reverse("drone-sop-pipeline-precheck")
        payload = json.dumps({"channels": ["messenger"]})
        resp = self.client.post(
            url,
            data=payload,
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer expected-token",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("channels", resp.json())
        mock_service.assert_called_once_with()


class DroneSopPruneTests(TestCase):
    """DroneSOP 보관 기간 정리 정책을 검증합니다."""

    def test_prune_deletes_rows_older_than_days_regardless_status(self) -> None:
        """보관 기간 초과 데이터는 상태와 무관하게 삭제합니다."""

        old_sop = _create_drone_sop(
            lot_id="LOT-OLD",
            status="IN_PROGRESS",
            needtosend=1,
            instant_inform=1,
        )
        recent_sop = _create_drone_sop(lot_id="LOT-RECENT")
        old_created_at = timezone.now() - timedelta(days=181)
        recent_created_at = timezone.now() - timedelta(days=179)
        DroneSOP.objects.filter(id=old_sop.id).update(created_at=old_created_at)
        DroneSOP.objects.filter(id=recent_sop.id).update(created_at=recent_created_at)

        from api.drone.services.pop3.persistence import prune_old_drone_sop_rows

        deleted = prune_old_drone_sop_rows(days=180, batch_size=10)

        self.assertEqual(deleted, 1)
        self.assertFalse(DroneSOP.objects.filter(id=old_sop.id).exists())
        self.assertTrue(DroneSOP.objects.filter(id=recent_sop.id).exists())
        self.assertFalse(DroneSopDelivery.objects.filter(sop_id=old_sop.id).exists())

    def test_prune_command_dry_run_keeps_rows(self) -> None:
        """dry-run은 삭제 후보 수만 출력하고 실제 데이터를 유지합니다."""

        old_sop = _create_drone_sop(lot_id="LOT-DRY-RUN")
        DroneSOP.objects.filter(id=old_sop.id).update(
            created_at=timezone.now() - timedelta(days=181)
        )
        output = StringIO()

        call_command(
            "prune_drone_sop",
            "--days",
            "180",
            "--batch-size",
            "10",
            "--dry-run",
            stdout=output,
        )

        self.assertIn("matched=1", output.getvalue())
        self.assertTrue(DroneSOP.objects.filter(id=old_sop.id).exists())

    def test_purge_command_requires_confirm_delete_all(self) -> None:
        """전체 삭제 커맨드는 확인 옵션 없이는 삭제하지 않습니다."""

        sop = _create_drone_sop(lot_id="LOT-PURGE-DRY")
        output = StringIO()

        call_command("purge_drone_sop", stdout=output)

        self.assertIn("dry-run", output.getvalue())
        self.assertTrue(DroneSOP.objects.filter(id=sop.id).exists())

    def test_purge_command_deletes_all_sop_rows_with_confirm(self) -> None:
        """확인 옵션이 있으면 DroneSOP와 cascade 이력을 모두 삭제합니다."""

        first = _create_drone_sop(lot_id="LOT-PURGE-1")
        second = _create_drone_sop(lot_id="LOT-PURGE-2")
        dispatch = DroneSopTargetDispatch.objects.create(
            sop=first,
            target_code_snapshot="TARGET-PURGE",
        )
        delivery = DroneSopDelivery.objects.create(
            sop=first,
            dispatch=dispatch,
            channel=DroneSopDelivery.Channels.JIRA,
        )
        output = StringIO()

        call_command("purge_drone_sop", "--confirm-delete-all", stdout=output)

        self.assertIn("deleted=", output.getvalue())
        self.assertFalse(DroneSOP.objects.exists())
        self.assertFalse(DroneSopTargetDispatch.objects.filter(id=dispatch.id).exists())
        self.assertFalse(DroneSopDelivery.objects.filter(id=delivery.id).exists())


class DroneEarlyInformAuthTests(TestCase):
    """조기 알림 API 인증을 검증합니다."""

    def test_early_inform_requires_login(self) -> None:
        """로그인 없이 접근 시 401을 반환하는지 확인합니다."""
        url = reverse("drone-early-inform")
        resp = self.client.get(url, data={"lineId": "L1"})
        self.assertEqual(resp.status_code, 401)


class DroneSopPop3DummyModeDeleteTests(TestCase):
    """더미 모드 삭제 조건을 검증합니다."""
    @override_settings(
        DRONE_SOP_DUMMY_MODE=True,
        DRONE_SOP_DUMMY_MAIL_MESSAGES_URL="http://example.local/mail/messages",
        DRONE_SOP_POP3_SUBJECT="[drone_sop] a,[drone_sop] b,[drone_sop] c",
    )
    @patch("api.drone.services.pop3.sop_pop3._delete_dummy_mail_messages")
    @patch("api.drone.services.pop3.sop_pop3._upsert_drone_sop_rows")
    @patch("api.drone.services.pop3.sop_pop3._list_dummy_mail_messages")
    @patch("api.drone.services.pop3.sop_pop3.selectors.load_drone_sop_custom_end_step_map", return_value={})
    def test_dummy_mode_deletes_only_successfully_upserted_mails(
        self,
        _mock_end_step: Mock,
        mock_list: Mock,
        mock_upsert: Mock,
        mock_delete: Mock,
    ) -> None:
        """업서트 성공한 메일만 삭제되는지 확인합니다."""
        mock_list.return_value = [
            {"id": 1, "subject": "[drone_sop] a", "body_html": "<data><lot_id>LOT-1</lot_id></data>"},
            {"id": 2, "subject": "[drone_sop] b", "body_html": "<data><lot_id>LOT-FAIL</lot_id></data>"},
            {"id": 3, "subject": "[drone_sop] c", "body_html": "<data><lot_id>LOT-3</lot_id></data>"},
        ]

        def upsert_side_effect(*, rows: list[dict[str, object]]) -> int:
            lot_id = rows[0].get("lot_id") if rows else None
            if lot_id == "LOT-FAIL":
                raise RuntimeError("upsert failed")
            return 1

        mock_upsert.side_effect = upsert_side_effect
        mock_delete.side_effect = lambda *, url, mail_ids, timeout: len(mail_ids)

        result = services.run_drone_sop_pop3_ingest_from_settings()
        self.assertEqual(result.matched_mails, 3)
        self.assertEqual(result.upserted_rows, 2)
        self.assertEqual(result.deleted_mails, 2)

        called_mail_ids = mock_delete.call_args.kwargs.get("mail_ids")
        self.assertEqual(called_mail_ids, [1, 3])


class DroneSopPop3MailboxTransportTests(SimpleTestCase):
    """POP3 mailbox transport 동작을 검증합니다."""

    def test_retrieve_pop3_message_allows_long_html_lines(self) -> None:
        """기본 poplib 제한보다 긴 HTML 라인도 메시지로 파싱하는지 확인합니다."""

        long_html = b"<html><body>" + (b"A" * 3000) + b"</body></html>"
        raw_response = (
            b"+OK message follows\r\n"
            b"Subject: [drone_sop] long-line\r\n"
            b"Content-Type: text/html; charset=utf-8\r\n"
            b"\r\n"
            + long_html
            + b"\r\n.\r\n"
        )

        class FakePop3(pop3_mailbox._LongLinePOP3):
            """네트워크 없이 long response를 재현하는 테스트 client입니다."""

            def __init__(self) -> None:
                self.file = BytesIO(raw_response)
                self._debugging = 0

            def _putcmd(self, line: str) -> None:
                self.sent_command = line

        msg = pop3_mailbox.retrieve_pop3_message(client=FakePop3(), msg_num=1)

        self.assertEqual(msg.get("Subject"), "[drone_sop] long-line")
        self.assertIn("A" * 3000, msg.get_content())


class DroneSopPop3SubjectFilterTests(TestCase):
    """제목 필터 동작을 검증합니다."""
    @override_settings(
        DRONE_SOP_DUMMY_MODE=True,
        DRONE_SOP_DUMMY_MAIL_MESSAGES_URL="http://example.local/mail/messages",
        DRONE_SOP_POP3_SUBJECT="[DRONE_SOP] A,[drone_sop] c",
    )
    @patch("api.drone.services.pop3.sop_pop3._delete_dummy_mail_messages")
    @patch("api.drone.services.pop3.sop_pop3._upsert_drone_sop_rows")
    @patch("api.drone.services.pop3.sop_pop3._list_dummy_mail_messages")
    @patch("api.drone.services.pop3.sop_pop3.selectors.load_drone_sop_custom_end_step_map", return_value={})
    def test_dummy_mode_filters_subject_case_insensitive(
        self,
        _mock_end_step: Mock,
        mock_list: Mock,
        mock_upsert: Mock,
        mock_delete: Mock,
    ) -> None:
        """제목 필터가 대소문자를 무시하는지 확인합니다."""
        mock_list.return_value = [
            {"id": 1, "subject": "[drone_sop] a", "body_html": "<data><lot_id>LOT-1</lot_id></data>"},
            {"id": 2, "subject": "other", "body_html": "<data><lot_id>LOT-2</lot_id></data>"},
            {"id": 3, "subject": "[DRONE_SOP] c", "body_html": "<data><lot_id>LOT-3</lot_id></data>"},
        ]
        mock_upsert.return_value = 1
        mock_delete.side_effect = lambda *, url, mail_ids, timeout: len(mail_ids)

        result = services.run_drone_sop_pop3_ingest_from_settings()

        self.assertEqual(result.matched_mails, 2)
        self.assertEqual(result.upserted_rows, 2)
        self.assertEqual(result.deleted_mails, 2)

        called_mail_ids = mock_delete.call_args.kwargs.get("mail_ids")
        self.assertEqual(called_mail_ids, [1, 3])

    @override_settings(
        DRONE_SOP_DUMMY_MODE=True,
        DRONE_SOP_DUMMY_MAIL_MESSAGES_URL="http://example.local/mail/messages",
        DRONE_SOP_POP3_SUBJECT="[drone_sop]",
    )
    @patch("api.drone.services.pop3.sop_pop3._delete_dummy_mail_messages")
    @patch("api.drone.services.pop3.sop_pop3._upsert_drone_sop_rows")
    @patch("api.drone.services.pop3.sop_pop3._list_dummy_mail_messages")
    @patch("api.drone.services.pop3.sop_pop3.selectors.load_drone_sop_custom_end_step_map", return_value={})
    def test_dummy_mode_filters_subject_prefix(
        self,
        _mock_end_step: Mock,
        mock_list: Mock,
        mock_upsert: Mock,
        mock_delete: Mock,
    ) -> None:
        """제목 prefix가 포함된 경우에도 필터가 동작하는지 확인합니다."""
        mock_list.return_value = [
            {"id": 1, "subject": "[drone_sop] alert-1", "body_html": "<data><lot_id>LOT-1</lot_id></data>"},
            {"id": 2, "subject": "other", "body_html": "<data><lot_id>LOT-2</lot_id></data>"},
        ]
        mock_upsert.return_value = 1
        mock_delete.side_effect = lambda *, url, mail_ids, timeout: len(mail_ids)

        result = services.run_drone_sop_pop3_ingest_from_settings()

        self.assertEqual(result.matched_mails, 1)
        self.assertEqual(result.upserted_rows, 1)
        self.assertEqual(result.deleted_mails, 1)

        called_mail_ids = mock_delete.call_args.kwargs.get("mail_ids")
        self.assertEqual(called_mail_ids, [1])

    @override_settings(
        DRONE_SOP_DUMMY_MODE=True,
        DRONE_SOP_DUMMY_MAIL_MESSAGES_URL="http://example.local/mail/messages",
        DRONE_SOP_POP3_SUBJECT="",
    )
    @patch("api.drone.services.pop3.sop_pop3._delete_dummy_mail_messages")
    @patch("api.drone.services.pop3.sop_pop3._upsert_drone_sop_rows")
    @patch("api.drone.services.pop3.sop_pop3._list_dummy_mail_messages")
    @patch("api.drone.services.pop3.sop_pop3.selectors.load_drone_sop_custom_end_step_map", return_value={})
    def test_dummy_mode_skips_all_when_subject_env_missing(
        self,
        _mock_end_step: Mock,
        mock_list: Mock,
        mock_upsert: Mock,
        mock_delete: Mock,
    ) -> None:
        """제목 환경변수가 없으면 기본 fallback 없이 전체 스킵하는지 확인합니다."""
        mock_list.return_value = [
            {"id": 1, "subject": "[drone_sop] alert-1", "body_html": "<data><lot_id>LOT-1</lot_id></data>"},
        ]
        mock_upsert.return_value = 1
        mock_delete.side_effect = lambda *, url, mail_ids, timeout: len(mail_ids)

        result = services.run_drone_sop_pop3_ingest_from_settings()

        self.assertEqual(result.matched_mails, 0)
        self.assertEqual(result.upserted_rows, 0)
        self.assertEqual(result.deleted_mails, 0)
        mock_upsert.assert_not_called()
        mock_delete.assert_not_called()


class DroneSopDefectMapPostTests(TestCase):
    """defectmap POST 연동을 검증합니다."""

    @override_settings(
        DRONE_SOP_DUMMY_MODE=True,
        DRONE_SOP_DUMMY_MAIL_MESSAGES_URL="http://example.local/mail/messages",
        DRONE_SOP_DEFECTMAP_URL="http://10.172.114.185:30912/defectmap",
        DRONE_SOP_POP3_SUBJECT="[drone_sop]",
    )
    @patch("api.drone.services.pop3.defectmap_sidecar.requests.post")
    @patch("api.drone.services.pop3.sop_pop3._delete_dummy_mail_messages")
    @patch("api.drone.services.pop3.sop_pop3._upsert_drone_sop_rows")
    @patch("api.drone.services.pop3.sop_pop3._list_dummy_mail_messages")
    @patch("api.drone.services.pop3.sop_pop3.selectors.load_drone_sop_custom_end_step_map", return_value={})
    @patch(
        "api.drone.services.pop3.sop_pop3.timezone.now",
        return_value=datetime(2026, 2, 5, 4, 0, 0, 750000, tzinfo=dt_timezone.utc),
    )
    def test_dummy_mode_posts_defect_json_image_urls_to_defectmap(
        self,
        _mock_now: Mock,
        _mock_end_step: Mock,
        mock_list: Mock,
        mock_upsert: Mock,
        mock_delete: Mock,
        mock_post: Mock,
    ) -> None:
        """defect_url JSON에서 defectmap image URL을 재구성해 POST하는지 확인합니다."""
        map_url = "https://app.nyms.abc.net/map/api/mapg/map?dtype=PQ&file=abc_df.parquet&mtype=DEFECT&signin_yn=y"
        defect_json = json.dumps(
            [
                {
                    "STEP_SEQ": "ST003",
                    "DEFECT_MAP_URL": map_url,
                }
            ]
        ).replace("&", "&amp;")
        defect_png_url = (
            "https://ignored.local/map/api/map-image/v3/defect-map"
            "?file=abc_df.parquet&amp;selected_row=0&amp;width=999,"
            "https://ignored.local/map/api/map-image/v3/defect-map"
            "?file=abc_df.parquet&amp;selected_row=1&amp;width=999"
        )
        expected_data = (
            "https://app.nyms.samsungds.net/map/api/map-image/v3/defect-map"
            "?file=abc_df.parquet&selected_row=0&profileid=DEFAULT&themeid=DEFAULT"
            "&width=500&height=500&site=GH&targetDB=APP&useCache=true&includeCoordinate=false,"
            "https://app.nyms.samsungds.net/map/api/map-image/v3/defect-map"
            "?file=abc_df.parquet&selected_row=1&profileid=DEFAULT&themeid=DEFAULT"
            "&width=500&height=500&site=GH&targetDB=APP&useCache=true&includeCoordinate=false"
        )
        mock_list.return_value = [
            {
                "id": 1,
                "subject": "[drone_sop] alert-1",
                "body_html": (
                    "<data>"
                    "<lot_id>LOT-1</lot_id>"
                    "<metro_current_step>ST003</metro_current_step>"
                    f"<defect_png_url>{defect_png_url}</defect_png_url>"
                    f"<defect_json>{defect_json}</defect_json>"
                    "</data>"
                ),
            }
        ]
        mock_upsert.return_value = 1
        mock_delete.side_effect = lambda *, url, mail_ids, timeout: len(mail_ids)

        result = services.run_drone_sop_pop3_ingest_from_settings()

        self.assertEqual(result.matched_mails, 1)
        self.assertEqual(result.upserted_rows, 1)
        self.assertEqual(result.deleted_mails, 1)
        mock_post.assert_called_once()
        self.assertEqual(mock_post.call_args.args[0], "http://10.172.114.185:30912/defectmap")
        self.assertEqual(
            mock_post.call_args.kwargs.get("json"),
            {
                "lotid": "LOT-1",
                "scandate": "2026-02-05 13:00:00.750 +0900",
                "step": "",
                "stepid": "ST003",
                "data": expected_data,
            },
        )

    @override_settings(
        DRONE_SOP_DUMMY_MODE=True,
        DRONE_SOP_DUMMY_MAIL_MESSAGES_URL="http://example.local/mail/messages",
        DRONE_SOP_DEFECTMAP_URL="http://10.172.114.185:30912/defectmap",
        DRONE_SOP_POP3_SUBJECT="[drone_sop]",
    )
    @patch("api.drone.services.pop3.defectmap_sidecar.requests.post")
    @patch("api.drone.services.pop3.sop_pop3._delete_dummy_mail_messages")
    @patch("api.drone.services.pop3.sop_pop3._upsert_drone_sop_rows")
    @patch("api.drone.services.pop3.sop_pop3._list_dummy_mail_messages")
    @patch("api.drone.services.pop3.sop_pop3.selectors.load_drone_sop_custom_end_step_map", return_value={})
    def test_dummy_mode_skips_defectmap_post_when_defect_url_json_empty(
        self,
        _mock_end_step: Mock,
        mock_list: Mock,
        mock_upsert: Mock,
        mock_delete: Mock,
        mock_post: Mock,
    ) -> None:
        """defect_url JSON이 없으면 defect_png_url 원문만으로 POST하지 않는지 확인합니다."""
        mock_list.return_value = [
            {
                "id": 1,
                "subject": "[drone_sop] alert-1",
                "body_html": (
                    "<data>"
                    "<lot_id>LOT-1</lot_id>"
                    "<metro_current_step>ST003</metro_current_step>"
                    '<defect_png_url>"https://example.com/defect.png"</defect_png_url>'
                    "</data>"
                ),
            }
        ]
        mock_upsert.return_value = 1
        mock_delete.side_effect = lambda *, url, mail_ids, timeout: len(mail_ids)

        result = services.run_drone_sop_pop3_ingest_from_settings()

        self.assertEqual(result.matched_mails, 1)
        self.assertEqual(result.upserted_rows, 1)
        self.assertEqual(result.deleted_mails, 1)
        mock_post.assert_not_called()


class DroneSopJiraHtmlDescriptionTests(TestCase):
    """Jira 설명 HTML 렌더링을 검증합니다."""

    def test_build_jira_issue_fields_uses_html(self) -> None:
        """HTML 템플릿이 포함되는지 확인합니다."""
        from api.drone.services.jira import delivery as jira_delivery

        config = services.DroneJiraConfig(
            base_url="http://example.local/jira",
            token="dummy-token",
            issue_type="Task",
            use_bulk_api=False,
            bulk_size=20,
            connect_timeout=5,
            read_timeout=20,
        )
        row = {
            "sdwt_prod": "SDWT",
            "main_step": "ST003",
            "ppid": "PPID",
            "eqp_id": "EQP",
            "chamber_ids": "1",
            "lot_id": "LOT.1",
            "knox_id": "knox",
            "user_sdwt_prod": "prod",
            "comment": "hello",
            "defect_url": json.dumps(
                [
                    {
                        "step_seq": "ST001",
                        "map_url": "https://example.com/defect",
                        "label": "LOT.1",
                    }
                ]
            ),
        }

        fields = jira_delivery._build_jira_issue_fields(
            row=row,
            project_key="DUMMY",
            template_key="common",
            config=config,
        )
        description = fields.get("description") or ""
        self.assertIn("<table", description)
        self.assertIn("CTTTM URL", description)
        self.assertIn("Defect URL", description)
        self.assertIn("https://example.com/defect", description)
        self.assertIn(">ST001<", description)

    def test_build_jira_issue_fields_renders_multiple_defect_links(self) -> None:
        """defect_url JSON 문자열의 여러 링크가 렌더링되는지 확인합니다."""
        from api.drone.services.jira import delivery as jira_delivery

        config = services.DroneJiraConfig(
            base_url="http://example.local/jira",
            token="dummy-token",
            issue_type="Task",
            use_bulk_api=False,
            bulk_size=20,
            connect_timeout=5,
            read_timeout=20,
        )
        row = {
            "sdwt_prod": "SDWT",
            "main_step": "ST003",
            "ppid": "PPID",
            "eqp_id": "EQP",
            "chamber_ids": "1",
            "lot_id": "LOT.1",
            "knox_id": "knox",
            "user_sdwt_prod": "prod",
            "defect_url": json.dumps(
                [
                    {
                        "step_seq": "ST001",
                        "map_url": "https://example.com/defect-a",
                        "label": "LOT.1",
                    },
                    {
                        "step_seq": "ST002",
                        "map_url": "https://example.com/defect-b",
                        "label": "LOT.1",
                    },
                ]
            ),
        }

        fields = jira_delivery._build_jira_issue_fields(
            row=row,
            project_key="DUMMY",
            template_key="common",
            config=config,
        )
        description = fields.get("description") or ""
        self.assertIn("https://example.com/defect-a", description)
        self.assertIn("https://example.com/defect-b", description)
        self.assertIn(">ST001<", description)
        self.assertIn(">ST002<", description)
        self.assertIn(">ST001</a>,", description)

    def test_build_jira_issue_fields_renders_ctttm_links(self) -> None:
        """CTTTM 링크가 렌더링되는지 확인합니다."""
        from api.drone.services.jira import delivery as jira_delivery

        config = services.DroneJiraConfig(
            base_url="http://example.local/jira",
            token="dummy-token",
            issue_type="Task",
            use_bulk_api=False,
            bulk_size=20,
            connect_timeout=5,
            read_timeout=20,
        )
        row = {
            "sdwt_prod": "SDWT",
            "main_step": "ST003",
            "ppid": "PPID",
            "eqp_id": "EQP",
            "chamber_ids": "1",
            "lot_id": "LOT.1",
            "knox_id": "knox",
            "user_sdwt_prod": "prod",
            "comment": "hello",
            "ctttm_urls": [{"eqp_id": "EQP-1", "url": "https://example.com/ctttm"}],
        }

        fields = jira_delivery._build_jira_issue_fields(
            row=row,
            project_key="DUMMY",
            template_key="common",
            config=config,
        )
        description = fields.get("description") or ""
        self.assertIn("https://example.com/ctttm", description)
        self.assertIn(">EQP-1<", description)


class DroneSopMailHtmlBodyTests(TestCase):
    """메일 본문 HTML 렌더링을 검증합니다."""

    def test_render_mail_body_renders_every_defect_image_from_images_rows(self) -> None:
        """메일 본문은 images_rows의 모든 defect image를 각각 표시합니다."""
        from api.drone.services.mail import mail_sender

        map_url_a = "https://app.nyms.example.net/map/api/mapg/map?dtype=PQ&file=abc_df.parquet"
        map_url_b = "https://app.nyms.example.net/map/api/mapg/map?dtype=PQ&file=other_df.parquet"
        body = mail_sender._render_mail_body(
            template_key="common",
            row={
                "sdwt_prod": "SDWT",
                "main_step": "ST003",
                "ppid": "PPID",
                "eqp_id": "EQP",
                "chamber_ids": "1",
                "lot_id": "LOT.1",
                "knox_id": "knox",
                "user_sdwt_prod": "prod",
                "defect_url": json.dumps(
                    [
                        {
                            "step_seq": "ST001",
                            "map_url": map_url_a,
                            "label": "ST001",
                            "map_file": "abc_df.parquet",
                            "images_rows": [0, 1],
                        },
                        {
                            "step_seq": "ST002",
                            "map_url": map_url_b,
                            "label": "ST002",
                            "map_file": "other_df.parquet",
                            "images_rows": [3],
                        },
                    ]
                ),
            },
        )

        self.assertIn("Defect Image", body)
        self.assertEqual(body.count("<img"), 3)
        self.assertIn("alt=\"Defect ST001\"", body)
        self.assertIn("alt=\"Defect ST002\"", body)
        self.assertIn("/map/api/map-image/v3/defect-map?file=abc_df.parquet&amp;selected_row=0", body)
        self.assertIn("/map/api/map-image/v3/defect-map?file=abc_df.parquet&amp;selected_row=1", body)
        self.assertIn("/map/api/map-image/v3/defect-map?file=other_df.parquet&amp;selected_row=3", body)
        self.assertIn(
            "href=\"https://app.nyms.example.net/map/api/mapg/map?dtype=PQ&amp;file=abc_df.parquet",
            body,
        )
        self.assertNotIn("Defect URL", body)
        self.assertNotIn(">ST001</a>", body)
        self.assertNotIn(">ST002</a>", body)

    def test_render_mail_body_keeps_defect_link_when_image_is_missing(self) -> None:
        """이미지 URL을 만들 수 없는 항목은 기존 defect link를 유지합니다."""
        from api.drone.services.mail import mail_sender

        body = mail_sender._render_mail_body(
            template_key="common",
            row={
                "sdwt_prod": "SDWT",
                "main_step": "ST003",
                "ppid": "PPID",
                "eqp_id": "EQP",
                "chamber_ids": "1",
                "lot_id": "LOT.1",
                "defect_url": json.dumps(
                    [
                        {
                            "step_seq": "ST001",
                            "map_url": "https://example.com/defect",
                            "label": "ST001",
                        }
                    ]
                ),
            },
        )

        self.assertIn("https://example.com/defect", body)
        self.assertIn(">ST001</a>", body)


class DroneSopJiraSummaryTests(TestCase):
    """Jira 요약 템플릿 적용을 검증합니다."""

    def test_build_jira_issue_fields_uses_template_summary(self) -> None:
        """템플릿별 summary 포맷이 적용되는지 확인합니다."""
        from api.drone.services.jira import delivery as jira_delivery

        config = services.DroneJiraConfig(
            base_url="http://example.local/jira",
            token="dummy-token",
            issue_type="Task",
            use_bulk_api=False,
            bulk_size=20,
            connect_timeout=5,
            read_timeout=20,
        )
        row = {
            "line_id": "L1",
            "sdwt_prod": "SDWT",
            "main_step": "ST003",
            "ppid": "PPID",
            "eqp_id": "EQP",
            "chamber_ids": "1",
            "lot_id": "LOT.1",
        }

        def build_common_summary(data: dict[str, object]) -> str:
            sdwt = str(data.get("sdwt_prod") or "?").strip() or "?"
            return f"{data.get('line_id')}-{sdwt[:1]}"

        def build_H1_summary(data: dict[str, object]) -> str:
            sdwt = str(data.get("sdwt_prod") or "?").strip() or "?"
            step = str(data.get("main_step") or "??").strip() or "??"
            normalized_step = step[2:].upper() if len(step) >= 3 else step.upper()
            return f"{sdwt[:1]}-{normalized_step}"

        with patch.dict(
            jira_delivery.SUMMARY_BUILDERS,
            {
                "common": build_common_summary,
                "H1": build_H1_summary,
            },
            clear=True,
        ):
            fields_a = jira_delivery._build_jira_issue_fields(
                row=row,
                project_key="DUMMY",
                template_key="common",
                config=config,
            )
            fields_b = jira_delivery._build_jira_issue_fields(
                row=row,
                project_key="DUMMY",
                template_key="H1",
                config=config,
            )

        self.assertEqual(fields_a.get("summary"), "L1-S")
        self.assertEqual(fields_b.get("summary"), "S-003")

    def test_H1_summary_uses_layer_main_step_lot_id(self) -> None:
        """H1 summary가 layer/main_step/lot_id 규칙을 반영하는지 확인합니다."""
        from api.drone.services.jira.templates import jira_template_h1

        row = {
            "sdwt_prod": "SDWT",
            "main_step": "A-000320",
            "ppid": "N000000",
            "lot_id": "LOT.1",
        }
        summary = jira_template_h1.build_summary(row)

        self.assertEqual(summary, "S FA A-000320 LOT.1")

    def test_H1_find_layer_supports_zero_padded_rule_bounds(self) -> None:
        """H1 layer 규칙에서 선행 0 문자열 범위를 처리하는지 확인합니다."""
        from api.drone.services.jira.templates import jira_template_h1

        with patch.object(
            jira_template_h1,
            "_LAYER_RULES",
            (("A", "000320", "058120", "AA"),),
        ):
            self.assertEqual(jira_template_h1.find_layer("AB000320"), "AA")
            self.assertEqual(jira_template_h1.find_layer("AB058120"), "AA")
            self.assertEqual(jira_template_h1.find_layer("AB058121"), "[BEOL 인폼 필요]")

    def test_mail_template_h1_builds_layer_subject(self) -> None:
        """mail H1 템플릿이 자체 layer 제목을 생성하는지 확인합니다."""
        from api.drone.services.mail.templates import mail_template_h1

        row = {
            "sdwt_prod": "SDWT",
            "main_step": "A-000320",
            "ppid": "N000000",
            "lot_id": "LOT.1",
        }
        self.assertEqual(mail_template_h1.find_layer("AB000320"), "FA")
        self.assertEqual(mail_template_h1.build_subject(row), "S FA A-000320 LOT.1")

    def test_mail_template_common_builds_default_subject(self) -> None:
        """common 메일 템플릿이 기존 기본 제목 형식을 유지하는지 확인합니다."""
        from api.drone.services.mail.mail_sender import _build_mail_subject
        from api.drone.services.mail.templates import mail_template_common
        from api.drone.services.mail.templates.mail_template_registry import (
            MAIL_SUBJECT_BUILDERS,
            MAIL_TEMPLATE_SOURCES,
        )

        row = {
            "sdwt_prod": "SDWT",
            "main_step": "ST003",
            "eqp_id": "EQP",
            "chamber_ids": "1",
            "lot_id": "LOT.1",
            "ppid": "PPID",
        }

        self.assertIs(MAIL_TEMPLATE_SOURCES["common"], mail_template_common.BODY_TEMPLATE)
        self.assertIs(MAIL_SUBJECT_BUILDERS["common"], mail_template_common.build_subject)
        self.assertEqual(mail_template_common.build_subject(row), "S 003 EQP-1")
        self.assertEqual(_build_mail_subject(template_key="common", row=row), "S 003 EQP-1")

    def test_mail_template_auto_sp_builds_requested_subject(self) -> None:
        """Auto S/P 메일 템플릿이 요청된 제목 형식을 생성하는지 확인합니다."""
        from api.drone.services.mail.templates import mail_template_auto_sp

        row = {
            "main_step": "ST003",
            "eqp_id": "EQP",
            "chamber_ids": "1",
            "lot_id": "LOT.1",
            "ppid": "PPID",
        }
        subject = mail_template_auto_sp.build_subject(row)

        self.assertEqual(subject, "[Auto S/P][ST003][EQP-1][LOT.1][PPID]")

    def test_mail_sender_accepts_auto_sp_template_key(self) -> None:
        """메일 발송 제목 생성기가 Auto S/P 템플릿 키를 지원하는지 확인합니다."""
        from api.drone.services.mail.mail_sender import _build_mail_subject
        from api.drone.services.mail.templates import mail_template_auto_sp
        from api.drone.services.mail.templates.mail_template_registry import (
            MAIL_SUBJECT_BUILDERS,
            MAIL_TEMPLATE_SOURCES,
        )

        row = {
            "step_seq": "ST009",
            "eqpid": "EQP9",
            "chamber_ids": "9",
            "lot_id": "LOT.9",
            "ppid": "PPID9",
        }

        self.assertIn("auto_sp", MAIL_TEMPLATE_SOURCES)
        self.assertIs(MAIL_TEMPLATE_SOURCES["auto_sp"], mail_template_auto_sp.BODY_TEMPLATE)
        self.assertIs(MAIL_SUBJECT_BUILDERS["auto_sp"], mail_template_auto_sp.build_subject)
        self.assertEqual(
            _build_mail_subject(template_key="auto_sp", row=row),
            "[Auto S/P][ST009][EQP9-9][LOT.9][PPID9]",
        )


class DroneSopMessengerLineATemplateTests(TestCase):
    """common 메신저 템플릿의 Excel Table 전송 경로를 검증합니다."""

    @patch("api.drone.services.messenger.templates.messenger_template_common.messenger_services.send_excel_table_message_from_file")
    def test_send_excel_table_message_uses_knox_excel_sender(self, mock_send_excel: Mock) -> None:
        """common 템플릿이 Excel Table API를 호출하는지 확인합니다."""

        from api.drone.services.messenger.templates import messenger_template_common as common_template
        import api.common.services as messenger_services

        captured: dict[str, str] = {}

        def _capture_excel_payload(**kwargs: object) -> None:
            html_path = str(kwargs.get("html_path") or "")
            with open(html_path, "r", encoding="utf-8") as file:
                captured["html"] = file.read()
            captured["html_path"] = html_path

        mock_send_excel.side_effect = _capture_excel_payload
        config = messenger_services.KnoxMessengerConfig(
            base_url="http://example.local/messenger/",
            authorization="Bearer test",
            system_id="sys-test",
            timeout_seconds=5,
        )

        common_template.send_excel_table_message(
            chatroom_id=123,
            context={
                "sop_id": "1",
                "main_step": "ST003",
                "ppid": "PPID",
                "eqp_cb": "EQP-1",
                "lot_id": "LOT-1",
                "user_sdwt_prod": "SDWT",
                "knoxid": "knox",
                "comment_raw": "코멘트",
            },
            actions=[
                {
                    "type": "Action.OpenUrl",
                    "title": "CTTTM",
                    "url": "https://example.com/ctttm",
                }
            ],
            ttl=900,
            config=config,
        )

        mock_send_excel.assert_called_once()
        self.assertIn("<table ", captured.get("html", ""))
        self.assertIn("Step_seq", captured.get("html", ""))
        self.assertIn("📄 CTTTM URL", captured.get("html", ""))
        self.assertIn("https://example.com/ctttm", captured.get("html", ""))
        self.assertFalse(os.path.exists(captured.get("html_path", "")))

    @patch("api.drone.services.messenger.templates.messenger_template_common.messenger_services.send_excel_table_message_from_file")
    def test_send_excel_table_message_renders_multiple_defect_links(self, mock_send_excel: Mock) -> None:
        """common 메신저 템플릿이 여러 Defect 링크를 렌더링하는지 확인합니다."""

        from api.drone.services.messenger.messenger_sender import (
            build_drone_sop_messenger_template_inputs,
        )
        from api.drone.services.messenger.templates import messenger_template_common as common_template
        import api.common.services as messenger_services

        captured: dict[str, str] = {}

        def _capture_excel_payload(**kwargs: object) -> None:
            html_path = str(kwargs.get("html_path") or "")
            with open(html_path, "r", encoding="utf-8") as file:
                captured["html"] = file.read()
            captured["html_path"] = html_path

        mock_send_excel.side_effect = _capture_excel_payload
        context, actions = build_drone_sop_messenger_template_inputs(
            row={
                "id": 1,
                "main_step": "ST003",
                "ppid": "PPID",
                "eqp_id": "EQP",
                "chamber_ids": "1",
                "lot_id": "LOT-1",
                "user_sdwt_prod": "SDWT",
                "knox_id": "knox",
                "defect_url": json.dumps(
                    [
                        {"step_seq": "ST001", "map_url": "https://example.com/defect-a", "label": "ST001"},
                        {"step_seq": "ST002", "map_url": "https://example.com/defect-b", "label": "ST002"},
                    ]
                ),
            }
        )
        config = messenger_services.KnoxMessengerConfig(
            base_url="http://example.local/messenger/",
            authorization="Bearer test",
            system_id="sys-test",
            timeout_seconds=5,
        )

        common_template.send_excel_table_message(
            chatroom_id=123,
            context=context,
            actions=actions,
            ttl=900,
            config=config,
        )

        self.assertIn("https://example.com/defect-a", captured.get("html", ""))
        self.assertIn("https://example.com/defect-b", captured.get("html", ""))
        self.assertIn(">ST001<", captured.get("html", ""))
        self.assertIn(">ST002<", captured.get("html", ""))
        self.assertFalse(os.path.exists(captured.get("html_path", "")))


class DroneSopMessengerLineBTemplateTests(TestCase):
    """H1 메신저 템플릿의 Excel Table 전송 경로를 검증합니다."""

    @patch("api.drone.services.messenger.templates.messenger_template_h1.messenger_services.send_excel_table_message_from_file")
    def test_send_excel_table_message_uses_knox_excel_sender(self, mock_send_excel: Mock) -> None:
        """H1 템플릿이 Excel Table API를 호출하는지 확인합니다."""

        from api.drone.services.messenger.templates import messenger_template_h1 as H1_template
        import api.common.services as messenger_services

        captured: dict[str, str] = {}

        def _capture_excel_payload(**kwargs: object) -> None:
            html_path = str(kwargs.get("html_path") or "")
            with open(html_path, "r", encoding="utf-8") as file:
                captured["html"] = file.read()
            captured["html_path"] = html_path

        mock_send_excel.side_effect = _capture_excel_payload
        config = messenger_services.KnoxMessengerConfig(
            base_url="http://example.local/messenger/",
            authorization="Bearer test",
            system_id="sys-test",
            timeout_seconds=5,
        )

        H1_template.send_excel_table_message(
            chatroom_id=456,
            context={
                "main_step": "A-000320",
                "ppid": "AB000320",
                "eqp_cb": "EQP-9",
                "lot_id": "LOT-9",
                "user_sdwt_prod": "SDWT-B",
                "knoxid": "knox-b",
                "comment_raw": "H1 코멘트",
            },
            actions=[
                {
                    "type": "Action.OpenUrl",
                    "title": "Defect",
                    "url": "https://example.com/defect",
                }
            ],
            ttl=1200,
            config=config,
        )

        mock_send_excel.assert_called_once()
        self.assertIn("<table ", captured.get("html", ""))
        self.assertIn("Step_seq", captured.get("html", ""))
        self.assertIn("🧩 Layer : ", captured.get("html", ""))
        self.assertIn("</span>FA</td>", captured.get("html", ""))
        self.assertIn("💿 Defect URL", captured.get("html", ""))
        self.assertIn("https://example.com/defect", captured.get("html", ""))
        self.assertFalse(os.path.exists(captured.get("html_path", "")))


class DroneSopMessengerApiRoutingTests(TestCase):
    """템플릿 키별 메신저 전송 라우팅을 검증합니다."""

    def _build_config(self):
        from api.drone.services.messenger import messenger_api
        import api.common.services as messenger_services

        return messenger_api.DroneMessengerConfig(
            ttl=1800,
            knox_config=messenger_services.KnoxMessengerConfig(
                base_url="http://example.local/messenger/",
                authorization="Bearer test",
                system_id="sys-test",
                timeout_seconds=5,
            ),
        )

    @patch("api.drone.services.messenger.messenger_api.build_drone_sop_messenger_template_inputs")
    def test_common_uses_excel_table_sender(self, mock_build_inputs: Mock) -> None:
        """common는 Excel Table sender를 사용하는지 확인합니다."""

        from api.drone.services.messenger import messenger_api

        config = self._build_config()
        row = {"id": 1}
        mock_build_inputs.return_value = ({"sop_id": "1"}, [])
        mock_sender = Mock()

        with patch.dict(
            messenger_api.EXCEL_TABLE_TEMPLATE_SENDERS,
            {"common": mock_sender},
            clear=False,
        ):
            messenger_api.send_drone_sop_messenger_message(
                row=row,
                chatroom_id=777,
                messenger_template_key="common",
                config=config,
            )

        mock_build_inputs.assert_called_once_with(row=row)
        mock_sender.assert_called_once_with(
            chatroom_id=777,
            context={"sop_id": "1"},
            actions=[],
            ttl=1800,
            config=config.knox_config,
        )

    @patch("api.drone.services.messenger.messenger_api.build_drone_sop_messenger_template_inputs")
    def test_H1_uses_excel_table_sender(self, mock_build_inputs: Mock) -> None:
        """H1도 Excel Table sender를 사용하는지 확인합니다."""

        from api.drone.services.messenger import messenger_api

        config = self._build_config()
        row = {"id": 2}
        mock_build_inputs.return_value = ({"main_step": "ST009"}, [])
        mock_sender = Mock()

        with patch.dict(
            messenger_api.EXCEL_TABLE_TEMPLATE_SENDERS,
            {"H1": mock_sender},
            clear=False,
        ):
            messenger_api.send_drone_sop_messenger_message(
                row=row,
                chatroom_id=888,
                messenger_template_key="H1",
                config=config,
            )

        mock_build_inputs.assert_called_once_with(row=row)
        mock_sender.assert_called_once_with(
            chatroom_id=888,
            context={"main_step": "ST009"},
            actions=[],
            ttl=1800,
            config=config.knox_config,
        )

    def test_unsupported_template_key_raises_error(self) -> None:
        """미지원 템플릿 키는 ValueError를 발생시키는지 확인합니다."""

        from api.drone.services.messenger import messenger_api

        config = self._build_config()
        with self.assertRaises(ValueError):
            messenger_api.send_drone_sop_messenger_message(
                row={"id": 3},
                chatroom_id=999,
                messenger_template_key="unknown-template",
                config=config,
            )
