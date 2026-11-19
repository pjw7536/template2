"""개발 조직 확장 시 인원·직책 분배와 일반 사용자 보존을 검증합니다."""

import copy
import importlib.util
import unittest
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("keycloak_dummy", ROOT / "local/keycloak/scripts/seed_org_dummy.py")
dummy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dummy)


class DummyTests(unittest.TestCase):
    def tree(self):
        return [{"id": "t1", "name": "TEAM-1", "lines": [{"id": "l1", "name": "LINE-1", "sdwts": [{"id": "a", "name": "SDWT-A"}]}]},
                {"id": "t2", "name": "TEAM-2", "lines": [{"id": "l2", "name": "LINE-1", "sdwts": [{"id": "b", "name": "SDWT-B"}]}]}]

    def test_expansion_preserves_existing_groups_and_is_repeatable(self):
        original = self.tree()
        layout = dummy.scale_layout(original, 12)
        self.assertEqual([len(team["lines"]) for team in layout], [6, 6])
        counts = [len(line["sdwts"]) for team in layout for line in team["lines"]]
        self.assertEqual(counts, [4, 5] * 6)
        self.assertEqual(layout[0]["lines"][0]["sdwts"][0]["id"], "a")
        self.assertEqual(original, self.tree())
        self.assertEqual(dummy.scale_layout(layout, 12), layout)

    def test_distribution_has_exact_people_and_representatives(self):
        people = dummy.scale_people(dummy.scale_layout(self.tree(), 12), 2000)
        self.assertEqual(len({person["username"] for person in people}), 2000)
        counts = Counter(person["attributes"]["user_sdwt_prod"][0] for person in people)
        self.assertEqual(len(counts), 54)
        self.assertEqual(set(counts.values()), {37, 38})
        self.assertEqual(sum(person["attributes"].get("job_title") == ["PL"] for person in people), 12)
        self.assertEqual(sum(person["attributes"].get("job_title") == ["파트장"] for person in people), 54)
        self.assertEqual(len({person["attributes"]["grdName"][0] for person in people}), 4)
        self.assertTrue(all(dummy.is_dummy(person) for person in people))

    def test_invalid_sizes_never_shrink_existing_groups(self):
        with self.assertRaises(dummy.SetupError):
            dummy.scale_layout(self.tree(), 1)
        with self.assertRaises(dummy.SetupError):
            dummy.scale_layout([], 12)
        with self.assertRaises(dummy.SetupError):
            dummy.scale_people(dummy.scale_layout(self.tree(), 12), 100)

    def test_large_mode_is_local_only(self):
        for url, realm in [("https://example.invalid", "portal"), ("http://localhost:8180", "etch")]:
            with self.assertRaises(dummy.SetupError):
                dummy.check_local(SimpleNamespace(url=url, realm=realm))
        dummy.check_local(SimpleNamespace(url="http://localhost:8180", realm="portal"))

    def test_normal_user_is_never_modified(self):
        api = Mock()
        with self.assertRaises(dummy.SetupError):
            dummy.update_dummy(api, {"id": "real", "username": "99000001", "email": "real@example.invalid"}, {"username": "99000001"})
        self.assertEqual(api.mock_calls, [])

    def test_moving_dummy_preserves_other_groups_and_latest_attributes(self):
        user = {"id": "u", "username": "99000001", "email": "a@dummy.example.invalid", "attributes": {"other": ["keep"], "job_title": ["PL"]}}
        current = copy.deepcopy(user)
        current["attributes"]["concurrent"] = ["keep"]
        desired = {"username": "99000001", "sdwt_id": "new", "attributes": {"line_id": ["LINE-2"]}}
        api = Mock()
        api.pages.return_value = [{"id": "old", "path": "/org/T/L/A"}, {"id": "infra", "path": "/headlamp-admins"}]
        api.call.return_value = current
        dummy.update_dummy(api, user, desired)
        calls = api.call.call_args_list
        self.assertEqual(calls[0].args, ("DELETE", "users/u/groups/old"))
        self.assertEqual(calls[1].args, ("PUT", "users/u/groups/new"))
        self.assertEqual(calls[-1].args[2]["attributes"], {"other": ["keep"], "concurrent": ["keep"], "line_id": ["LINE-2"]})
        self.assertFalse(any("role-mappings" in call.args[1] for call in calls))
        api.reset_mock()
        current["attributes"] = calls[-1].args[2]["attributes"]
        api.pages.return_value = [{"id": "new", "path": "/org/T/L/B"}]
        dummy.update_dummy(api, current, desired)
        api.call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
