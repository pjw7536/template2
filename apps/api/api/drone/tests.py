from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse

from api.account.models import Affiliation
from api.drone import selectors, services
from api.drone.models import DroneSOP
from api.drone.services_sop_jira import DroneJiraConfig
from api.drone.services_sop_pop3 import NeedToSendRule


class DroneSopPop3ParsingTests(TestCase):
    def test_build_drone_sop_row_parses_html_data_tag(self) -> None:
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
          </data>
        </body></html>
        """

        early_inform_map = {("dummy-prod", "MS"): "ST002"}
        row = services._build_drone_sop_row(html=html, early_inform_map=early_inform_map)
        assert row is not None

        self.assertEqual(row["line_id"], "L1")
        self.assertEqual(row["chamber_ids"], "12")
        self.assertEqual(row["knox_id"], "knox")
        self.assertEqual(row["needtosend"], 1)
        self.assertEqual(row["status"], "COMPLETE")
        self.assertEqual(row["defect_url"], "https://example.com")
        self.assertEqual(row["custom_end_step"], "ST002")

    def test_build_drone_sop_row_applies_needtosend_override_rule(self) -> None:
        html = """
        <data>
          <sample_type>NORMAL</sample_type>
          <user_sdwt_prod>prod-1</user_sdwt_prod>
          <comment>hello@$abc</comment>
        </data>
        """
        rules = [NeedToSendRule(pattern="prod-*", comment_last_at="$abc", ignore_sample_type=False)]
        row = services._build_drone_sop_row(html=html, early_inform_map={}, needtosend_rules=rules)
        assert row is not None
        self.assertEqual(row["needtosend"], 1)

    def test_build_drone_sop_row_needtosend_zero_for_engr_production(self) -> None:
        html = """
        <data>
          <sample_type>ENGR_PRODUCTION</sample_type>
          <comment>hello@$SETUP_EQP</comment>
        </data>
        """
        row = services._build_drone_sop_row(html=html, early_inform_map={})
        assert row is not None
        self.assertEqual(row["needtosend"], 0)


class DroneSopUpsertTests(TestCase):
    def test_upsert_does_not_update_comment_or_needtosend_on_conflict(self) -> None:
        existing = DroneSOP.objects.create(
            line_id="L1",
            eqp_id="EQP1",
            chamber_ids="1",
            lot_id="LOT.1",
            main_step="MS",
            comment="old",
            needtosend=0,
            status="IN_PROGRESS",
            metro_current_step="ST001",
        )

        services._upsert_drone_sop_rows(
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
                }
            ]
        )

        refreshed = DroneSOP.objects.get(id=existing.id)
        self.assertEqual(refreshed.comment, "old")
        self.assertEqual(refreshed.needtosend, 0)
        self.assertEqual(refreshed.status, "COMPLETE")
        self.assertEqual(refreshed.metro_current_step, "ST002")


class DroneSopJiraCandidateTests(TestCase):
    def test_list_drone_sop_jira_candidates_filters_rows(self) -> None:
        DroneSOP.objects.create(
            line_id="L1",
            eqp_id="EQP1",
            chamber_ids="1",
            lot_id="LOT.1",
            main_step="MS",
            status="COMPLETE",
            needtosend=1,
            send_jira=0,
        )
        DroneSOP.objects.create(
            line_id="L2",
            eqp_id="EQP2",
            chamber_ids="1",
            lot_id="LOT.2",
            main_step="MS",
            status="IN_PROGRESS",
            needtosend=1,
            send_jira=0,
        )

        rows = selectors.list_drone_sop_jira_candidates()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["line_id"], "L1")


class DroneSopJiraUpdateTests(TestCase):
    def test_update_drone_sop_jira_status_sets_send_jira_and_key(self) -> None:
        row = DroneSOP.objects.create(
            line_id="L1",
            eqp_id="EQP1",
            chamber_ids="1",
            lot_id="LOT.1",
            main_step="MS",
            status="COMPLETE",
            needtosend=1,
            send_jira=0,
            metro_current_step="ST003",
        )

        updated = services._update_drone_sop_jira_status(
            done_ids=[int(row.id)],
            rows=[{"id": int(row.id), "metro_current_step": "ST003"}],
            key_by_id={int(row.id): "DUMMY-1"},
        )
        self.assertEqual(updated, 1)

        refreshed = DroneSOP.objects.get(id=row.id)
        self.assertEqual(refreshed.send_jira, 1)
        self.assertEqual(refreshed.inform_step, "ST003")
        self.assertEqual(refreshed.jira_key, "DUMMY-1")
        self.assertIsNotNone(refreshed.informed_at)


class DroneSopInstantInformTests(TestCase):
    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_JIRA_PROJECT_KEY_BY_LINE={"L1": "DUMMY"},
        DRONE_JIRA_USE_BULK_API=False,
    )
    @patch("api.drone.services_sop_jira._jira_session")
    def test_instant_inform_creates_jira_even_when_not_candidate(self, mock_session: Mock) -> None:
        session = Mock()
        resp = Mock(status_code=201)
        resp.json.return_value = {"key": "DUMMY-123"}
        session.post.return_value = resp
        mock_session.return_value = session

        Affiliation.objects.create(department="D", line="L1", user_sdwt_prod="SDWT")
        row = DroneSOP.objects.create(
            line_id="L1",
            sdwt_prod="SDWT",
            eqp_id="EQP1",
            chamber_ids="1",
            lot_id="LOT.1",
            main_step="MS",
            status="IN_PROGRESS",
            needtosend=0,
            send_jira=0,
            metro_current_step="ST001",
        )

        result = services.run_drone_sop_jira_instant_inform(sop_id=int(row.id), comment="hello")
        self.assertTrue(result.created)
        self.assertEqual(result.jira_key, "DUMMY-123")

        session.post.assert_called_once()
        sent_payload = session.post.call_args.kwargs.get("json") or {}
        self.assertEqual(sent_payload.get("fields", {}).get("project", {}).get("key"), "DUMMY")

        refreshed = DroneSOP.objects.get(id=row.id)
        self.assertEqual(refreshed.send_jira, 1)
        self.assertEqual(refreshed.instant_inform, 1)
        self.assertEqual(refreshed.jira_key, "DUMMY-123")
        self.assertEqual(refreshed.comment, "hello")

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_JIRA_PROJECT_KEY_BY_LINE={"L1": "DUMMY"},
        DRONE_JIRA_USE_BULK_API=False,
    )
    @patch("api.drone.services_sop_jira._jira_session")
    def test_instant_inform_does_not_create_duplicate(self, mock_session: Mock) -> None:
        row = DroneSOP.objects.create(
            line_id="L1",
            eqp_id="EQP1",
            chamber_ids="1",
            lot_id="LOT.1",
            main_step="MS",
            status="COMPLETE",
            needtosend=1,
            send_jira=1,
            jira_key="DUMMY-9",
        )

        result = services.run_drone_sop_jira_instant_inform(sop_id=int(row.id), comment="updated")
        self.assertTrue(result.already_informed)
        self.assertEqual(result.jira_key, "DUMMY-9")
        mock_session.assert_not_called()

        refreshed = DroneSOP.objects.get(id=row.id)
        self.assertEqual(refreshed.send_jira, 1)
        self.assertEqual(refreshed.jira_key, "DUMMY-9")
        self.assertEqual(refreshed.comment, "updated")


class DroneSopJiraCreateProjectKeyTests(TestCase):
    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_JIRA_PROJECT_KEY_BY_LINE={"L1": "PROJ1", "L2": "PROJ2"},
        DRONE_JIRA_USE_BULK_API=True,
        DRONE_JIRA_BULK_SIZE=50,
    )
    @patch("api.drone.services_sop_jira._jira_session")
    def test_jira_create_uses_project_key_per_line_and_marks_missing_as_failed(self, mock_session: Mock) -> None:
        session = Mock()
        resp = Mock(status_code=201)
        resp.json.return_value = {"issues": [{"key": "PROJ1-1"}, {"key": "PROJ2-2"}]}
        session.post.return_value = resp
        mock_session.return_value = session

        Affiliation.objects.create(department="D", line="L1", user_sdwt_prod="SDWT")
        Affiliation.objects.create(department="D", line="L2", user_sdwt_prod="SDWT")
        Affiliation.objects.create(department="D", line="L3", user_sdwt_prod="SDWT")

        sop1 = DroneSOP.objects.create(
            line_id="L1",
            sdwt_prod="SDWT",
            eqp_id="EQP1",
            chamber_ids="1",
            lot_id="LOT.1",
            main_step="MS",
            status="COMPLETE",
            needtosend=1,
            send_jira=0,
            metro_current_step="ST001",
        )
        sop2 = DroneSOP.objects.create(
            line_id="L2",
            sdwt_prod="SDWT",
            eqp_id="EQP2",
            chamber_ids="1",
            lot_id="LOT.2",
            main_step="MS",
            status="COMPLETE",
            needtosend=1,
            send_jira=0,
            metro_current_step="ST002",
        )
        sop_missing = DroneSOP.objects.create(
            line_id="L3",
            sdwt_prod="SDWT",
            eqp_id="EQP3",
            chamber_ids="1",
            lot_id="LOT.3",
            main_step="MS",
            status="COMPLETE",
            needtosend=1,
            send_jira=0,
            metro_current_step="ST003",
        )

        result = services.run_drone_sop_jira_create_from_env()
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

        self.assertEqual(refreshed1.send_jira, 1)
        self.assertEqual(refreshed1.jira_key, "PROJ1-1")
        self.assertEqual(refreshed2.send_jira, 1)
        self.assertEqual(refreshed2.jira_key, "PROJ2-2")
        self.assertEqual(refreshed_missing.send_jira, -1)


class DroneTriggerAuthTests(TestCase):
    @override_settings(DRONE_SOP_POP3_INGEST_TRIGGER_TOKEN="expected-token")
    @patch("api.drone.views.services.run_drone_sop_pop3_ingest_from_env")
    def test_pop3_ingest_trigger_uses_email_ingest_trigger_token(self, mock_run: Mock) -> None:
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

        resp = self.client.post(url, HTTP_AUTHORIZATION="Bearer expected-token")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["matched"], 1)
        self.assertEqual(mock_run.call_count, 1)

    @override_settings(DRONE_SOP_JIRA_TRIGGER_TOKEN="expected-token")
    @patch("api.drone.views.services.run_drone_sop_jira_create_from_env")
    def test_jira_trigger_uses_email_ingest_trigger_token(self, mock_run: Mock) -> None:
        mock_run.return_value = SimpleNamespace(
            candidates=1,
            created=1,
            updated_rows=0,
            skipped=False,
            skip_reason=None,
        )

        url = reverse("drone-sop-jira-trigger")

        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(mock_run.call_count, 0)

        resp = self.client.post(url, HTTP_AUTHORIZATION="Bearer expected-token")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["created"], 1)
        mock_run.assert_called_once_with(limit=None)


class DroneSopPop3DummyModeDeleteTests(TestCase):
    @override_settings(DRONE_SOP_DUMMY_MODE=True, DRONE_SOP_DUMMY_MAIL_MESSAGES_URL="http://example.local/mail/messages")
    @patch("api.drone.services_sop_pop3._delete_dummy_mail_messages")
    @patch("api.drone.services_sop_pop3._upsert_drone_sop_rows")
    @patch("api.drone.services_sop_pop3._list_dummy_mail_messages")
    @patch("api.drone.services_sop_pop3.selectors.load_drone_sop_custom_end_step_map", return_value={})
    def test_dummy_mode_deletes_only_successfully_upserted_mails(
        self,
        _mock_end_step: Mock,
        mock_list: Mock,
        mock_upsert: Mock,
        mock_delete: Mock,
    ) -> None:
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

        result = services.run_drone_sop_pop3_ingest_from_env()
        self.assertEqual(result.matched_mails, 3)
        self.assertEqual(result.upserted_rows, 2)
        self.assertEqual(result.deleted_mails, 2)

        called_mail_ids = mock_delete.call_args.kwargs.get("mail_ids")
        self.assertEqual(called_mail_ids, [1, 3])


class DroneSopJiraHtmlDescriptionTests(TestCase):
    def test_build_jira_issue_fields_uses_html(self) -> None:
        from api.drone import services_sop_jira

        config = DroneJiraConfig(
            base_url="http://example.local/jira",
            token="dummy-token",
            issue_type="Task",
            use_bulk_api=False,
            bulk_size=20,
            connect_timeout=5,
            read_timeout=20,
            project_key_by_line={},
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
            "defect_url": "https://example.com/defect",
        }

        fields = services_sop_jira._build_jira_issue_fields(row=row, project_key="DUMMY", config=config)
        description = fields.get("description") or ""
        self.assertIn("<table", description)
        self.assertIn("CTTTM URL", description)
        self.assertIn("Defect URL", description)
        self.assertIn("https://example.com/defect", description)

    def test_build_jira_issue_fields_renders_ctttm_links(self) -> None:
        from api.drone import services_sop_jira

        config = DroneJiraConfig(
            base_url="http://example.local/jira",
            token="dummy-token",
            issue_type="Task",
            use_bulk_api=False,
            bulk_size=20,
            connect_timeout=5,
            read_timeout=20,
            project_key_by_line={},
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
            "url": [{"eqp_id": "EQP-1", "url": "https://example.com/ctttm"}],
        }

        fields = services_sop_jira._build_jira_issue_fields(row=row, project_key="DUMMY", config=config)
        description = fields.get("description") or ""
        self.assertIn("https://example.com/ctttm", description)
        self.assertIn(">EQP-1<", description)
