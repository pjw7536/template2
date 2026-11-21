"""IAM 단일 배포에서 권한 추가 순서와 적용 후 조회 결과를 검증합니다."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, call, patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/setup_keycloak.py"
SPEC = importlib.util.spec_from_file_location("iam_setup_keycloak", SCRIPT)
iam = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(iam)
PUBLIC_URL = "https://iam.example.test"


class SetupTests(unittest.TestCase):
    def test_missing_feature_stops_before_any_write(self):
        api = Mock(realm="custom")
        api.call.return_value = {"adminPermissionsEnabled": False}
        api.server_info.return_value = {"features": [{"name": "ADMIN_FINE_GRAINED_AUTHZ_V2", "enabled": False}]}
        with patch.object(iam, "OrgSync", return_value=Mock(client=None, plan=["org 생성"])), \
                self.assertRaisesRegex(iam.SetupError, "세분화 관리 권한 v2"):
            iam.reconcile(api, PUBLIC_URL, [], [], "apply")
        self.assertEqual(api.call.call_args_list, [call("GET")])

    def test_member_selection_requires_an_exact_existing_username(self):
        api = Mock()
        api.pages.side_effect = [
            [{"id": "root", "path": "/iam"}],
            [{"id": "admins", "name": "platform-admins"}],
            [{"id": "similar", "username": "named-user-added"}],
        ]
        task = iam.Setup(api, PUBLIC_URL, None, ["named-user"])
        with patch.object(task, "missing_roles", return_value=[]), \
                self.assertRaisesRegex(iam.SetupError, "기존 사용자 'named-user'"):
            task.inspect_group()
        api.pages.assert_called_with("users", username="named-user", exact="true")
        api.call.assert_not_called()

    def test_public_url_must_be_an_origin(self):
        for value in ("https://iam.example.test/subpath", "https://iam.example.test?next=/", "http://iam.example.test"):
            with self.subTest(value=value), self.assertRaises(iam.SetupError):
                iam.check_public_url(value)
        self.assertEqual(iam.check_public_url(PUBLIC_URL + "/"), PUBLIC_URL)

    def test_apply_uses_one_api_and_finishes_with_a_fresh_inspection(self):
        api = SimpleNamespace(realm="custom")
        calls = Mock()
        org = Mock(plan=["org 생성"], client={"id": "org"})
        setting = Mock(plan=["IAM 생성"], parent={"id": "iam"}, org=None)
        initial = SimpleNamespace(plan=["앱 역할 생성"], warnings=[])
        catalog = Mock(plan=["카탈로그 게시"])
        for name, task in (("org", org), ("setting", setting), ("catalog", catalog)):
            calls.attach_mock(task, name)
        unchanged = SimpleNamespace(plan=[], warnings=[])
        with patch.object(iam, "inspect", side_effect=[(org, setting, initial), (unchanged, unchanged, unchanged)]) as inspect, \
                patch.object(iam, "AccessApply", return_value=catalog) as access, patch("builtins.print") as output:
            iam.reconcile(api, PUBLIC_URL, ["named-user"], [], "apply")
        self.assertEqual(inspect.call_args_list, [call(api, PUBLIC_URL, ["named-user"], [])] * 2)
        access.assert_called_once_with(api, [])
        self.assertEqual(setting.org, org.client)
        self.assertEqual(calls.mock_calls, [
            call.setting.enable_permissions(), call.org.apply(), call.setting.apply(),
            call.catalog.inspect(), call.catalog.apply(), call.setting.apply_members(),
        ])
        output.assert_any_call("IAM Keycloak 설정 검증 통과.")

    def test_verify_reports_drift_without_applying(self):
        api = SimpleNamespace(realm="custom")
        ready = SimpleNamespace(plan=[], warnings=[], client={"id": "org"})
        setting = Mock(plan=["관리 정책 연결"], parent={"id": "iam"})
        with patch.object(iam, "inspect", return_value=(ready, setting, ready)), patch("builtins.print"), \
                self.assertRaisesRegex(iam.SetupError, "설정 검증 불일치: 관리 정책 연결"):
            iam.reconcile(api, PUBLIC_URL, [], [], "verify")
        setting.apply.assert_not_called()
        setting.apply_members.assert_not_called()


if __name__ == "__main__":
    unittest.main()
