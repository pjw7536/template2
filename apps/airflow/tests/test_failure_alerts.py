"""실패 알림의 채널 독립성과 Knox Mail HTTP 계약을 외부 전송 없이 검증합니다."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit


SPEC = importlib.util.spec_from_file_location(
    "failure_alerts_under_test", Path(__file__).resolve().parents[1] / "dags/failure_alerts.py"
)
alerts = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(alerts)

MAIL_ENV = {
    "MAIL_API_URL": "https://mail.test/send",
    "MAIL_API_KEY": "fixture-ticket",
    "MAIL_API_SYSTEM_ID": "airflow-test",
    "MAIL_API_KNOX_ID": "sender-id",
    "AIRFLOW_FAILURE_ALERT_EMAIL_FROM": "airflow@example.test",
    "AIRFLOW_FAILURE_ALERT_EMAIL_TO": " first@example.test, , second@example.test ",
}


class FailureAlertsTests(unittest.TestCase):
    """메신저·메일 한쪽의 생략·오류가 다른 채널에 영향을 주지 않는지 확인합니다."""

    def setUp(self):
        self.context = {
            "task_instance": SimpleNamespace(dag_id="example", task_id="load", log_url="https://airflow.test/log"),
            "run_id": "scheduled__example",
            "exception": ValueError("<script>fail & retry</script>"),
        }
        self.env_patch = patch.dict(os.environ, {}, clear=True)
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

    def test_no_receivers_never_calls_external_apis(self):
        with patch.object(alerts.requests, "post") as post, patch.object(alerts.requests, "get") as get:
            alerts.notify_airflow_task_failure(self.context)
        post.assert_not_called()
        get.assert_not_called()

    def test_mail_without_messenger_uses_existing_http_contract_and_escaped_summary(self):
        response = Mock()
        with patch.dict(os.environ, MAIL_ENV), patch.object(alerts.requests, "post", return_value=response) as post:
            alerts.notify_airflow_task_failure(self.context)
        post.assert_called_once()
        args, kwargs = post.call_args
        self.assertEqual(args, ("https://mail.test/send",))
        self.assertEqual(kwargs["headers"], {"x-dep-ticket": "fixture-ticket"})
        self.assertEqual(dict(kwargs["params"]), {"systemId": "airflow-test", "loginUser.login": "sender-id"})
        self.assertEqual(kwargs["timeout"], 10)
        self.assertNotIn("verify", kwargs)
        payload = kwargs["json"]
        self.assertEqual(payload["senderMailAddress"], "airflow@example.test")
        self.assertEqual(payload["receiverList"], [
            {"email": "first@example.test", "recipientType": "TO"},
            {"email": "second@example.test", "recipientType": "TO"},
        ])
        for text in ("DAG: example", "Task: load", "Run: scheduled__example", "https://airflow.test/log",
                     "&lt;script&gt;fail &amp; retry&lt;/script&gt;"):
            self.assertIn(text, payload["content"])
        self.assertNotIn("<script>", payload["content"])
        response.raise_for_status.assert_called_once()

    def test_existing_mail_query_is_preserved_and_identity_parameters_are_not_duplicated(self):
        url = ("https://mail.test/send?systemId=old&systemId=older&loginUser.login=old-user"
               "&route=a%2Bb&trace=1&trace=2&blank=")
        with patch.dict(os.environ, {**MAIL_ENV, "MAIL_API_URL": url}), \
                patch.object(alerts.requests, "post") as post:
            alerts.notify_airflow_task_failure(self.context)
        args, kwargs = post.call_args
        request = alerts.requests.Request("POST", args[0], params=kwargs["params"]).prepare()
        query = parse_qs(urlsplit(request.url).query, keep_blank_values=True)
        self.assertEqual(query, {"systemId": ["airflow-test"], "loginUser.login": ["sender-id"],
                                 "route": ["a+b"], "trace": ["1", "2"], "blank": [""]})

    def test_messenger_and_mail_are_both_attempted(self):
        with patch.dict(os.environ, {**MAIL_ENV, "AIRFLOW_FAILURE_ALERT_KNOX_IDS": "operator"}), \
                patch.object(alerts, "_prepare_knox_context", return_value={}), \
                patch.object(alerts, "_get_or_create_chatroom_id", return_value=123), \
                patch.object(alerts, "_send_chat_message") as send_chat, \
                patch.object(alerts.requests, "post") as post:
            alerts.notify_airflow_task_failure(self.context)
        send_chat.assert_called_once()
        self.assertEqual(send_chat.call_args.kwargs["chatroom_id"], 123)
        post.assert_called_once()

    def test_messenger_exception_does_not_prevent_mail(self):
        with patch.dict(os.environ, MAIL_ENV), \
                patch.object(alerts, "_notify_messenger_failure", side_effect=RuntimeError("messenger down")), \
                patch.object(alerts.requests, "post") as post, self.assertLogs(alerts.logger, level="ERROR"):
            alerts.notify_airflow_task_failure(self.context)
        post.assert_called_once()

    def test_mail_error_does_not_escape_callback_or_undo_messenger(self):
        response = Mock()
        response.raise_for_status.side_effect = alerts.requests.HTTPError("mail down")
        with patch.dict(os.environ, MAIL_ENV), \
                patch.object(alerts, "_notify_messenger_failure") as messenger, \
                patch.object(alerts.requests, "post", return_value=response), self.assertLogs(alerts.logger, level="ERROR"):
            alerts.notify_airflow_task_failure(self.context)
        messenger.assert_called_once_with(self.context)

    def test_missing_mail_credentials_does_not_send_or_log_secret(self):
        for key in ("MAIL_API_URL", "MAIL_API_KEY", "MAIL_API_KNOX_ID", "AIRFLOW_FAILURE_ALERT_EMAIL_FROM"):
            with self.subTest(key=key), patch.dict(os.environ, {**MAIL_ENV, key: ""}), \
                    patch.object(alerts.requests, "post") as post, self.assertLogs(alerts.logger, level="WARNING") as logs:
                alerts.notify_airflow_task_failure(self.context)
            post.assert_not_called()
            self.assertIn(key, " ".join(logs.output))
            self.assertNotIn("fixture-ticket", " ".join(logs.output))

    def test_messenger_without_mail_receivers_still_sends(self):
        with patch.dict(os.environ, {"AIRFLOW_FAILURE_ALERT_KNOX_IDS": "operator"}), \
                patch.object(alerts, "_prepare_knox_context", return_value={}), \
                patch.object(alerts, "_get_or_create_chatroom_id", return_value=123), \
                patch.object(alerts, "_send_chat_message") as send_chat, \
                patch.object(alerts.requests, "post") as post:
            alerts.notify_airflow_task_failure(self.context)
        send_chat.assert_called_once()
        post.assert_not_called()
