"""기존 사용자 값 복사의 보존·충돌·재실행 및 초기 등록 신원 검사를 검증합니다."""

from contextlib import redirect_stdout
from copy import deepcopy
import importlib.util
import io
from pathlib import Path
import sys
import unittest


SCRIPTS = Path(__file__).resolve().parents[3] / "deploy/keycloak/scripts"
sys.path.insert(0, str(SCRIPTS))
try:
    SPEC = importlib.util.spec_from_file_location("claim_migration", SCRIPTS / "migrate_claim_attributes.py")
    migration = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(migration)
finally:
    sys.path.pop(0)
from init_sdwt import Setup, SetupError


class FakeAdmin:
    def __init__(self, users):
        self.users = deepcopy(users)
        self.writes = []
        self.changed = False
        self.profile = {"attributes": [{"name": n} for n in migration.RENAMES.values()],
                        "unmanagedAttributePolicy": "ADMIN_EDIT"}

    def pages(self, path, **query):
        return deepcopy(self.users)

    def call(self, method, path, data=None):
        if path == "users/profile":
            return self.profile
        user = next(u for u in self.users if path == "users/" + u["id"])
        if method == "GET":
            result = deepcopy(user)
            if self.changed:
                result["attributes"]["new_attribute"] = ["updated"]
            return result
        self.writes.append((path, deepcopy(data)))
        user.update(deepcopy(data))


class MigrationTests(unittest.TestCase):
    def run_migration(self, api, apply=False):
        with redirect_stdout(io.StringIO()):
            migration.migrate(api, apply)

    def test_dry_run_copy_preservation_and_repeat(self):
        user = {"id": "1", "username": "001", "email": "user@example.invalid",
                "attributes": {"knox_id": ["login"], "department": ["dept"],
                               "grd_name": ["grade"], "line_id": ["line"]}}
        api = FakeAdmin([user])
        self.run_migration(api)
        self.assertEqual(api.users, [user])
        self.assertEqual(api.writes, [])
        self.run_migration(api, True)
        attrs = api.users[0]["attributes"]
        for old, new in migration.RENAMES.items():
            self.assertEqual(attrs[old], attrs[new])
        self.assertEqual(attrs["line_id"], ["line"])
        self.assertEqual(api.users[0]["username"], "001")
        self.assertEqual(set(api.writes[0][1]), {"attributes"})
        self.run_migration(api, True)
        self.assertEqual(len(api.writes), 1)

    def test_late_conflict_prevents_all_writes(self):
        api = FakeAdmin([
            {"id": "1", "attributes": {"knox_id": ["a"]}},
            {"id": "2", "attributes": {"department": ["old"], "deptname": ["new"]}},
        ])
        with self.assertRaises(SetupError):
            self.run_migration(api, True)
        self.assertEqual(api.writes, [])

    def test_invalid_multivalue_and_scalar(self):
        for values in (["a", "b"], "a", [1]):
            with self.subTest(values=values), self.assertRaises(SetupError):
                migration.migrated_attributes({"knox_id": values})

    def test_empty_values(self):
        self.assertEqual(migration.migrated_attributes({"knox_id": [""]}), {"knox_id": [""]})
        self.assertEqual(migration.migrated_attributes({"knox_id": ["a"], "loginid": [""]})["loginid"], ["a"])

    def test_missing_profile_and_concurrent_change(self):
        api = FakeAdmin([{"id": "1", "attributes": {"knox_id": ["a"]}}])
        api.profile["attributes"] = []
        with self.assertRaises(SetupError):
            self.run_migration(api, True)
        api.profile["attributes"] = [{"name": n} for n in migration.RENAMES.values()]
        api.changed = True
        with self.assertRaises(SetupError):
            self.run_migration(api, True)
        self.assertEqual(api.writes, [])

    def test_initial_registration_rejects_legacy_and_new_identity_collision(self):
        for key in ("knox_id", "loginid"):
            with self.subTest(key=key):
                api = FakeAdmin([{"id": "1", "username": "001", "attributes": {key: ["login"]}}])
                task = Setup(api, {}, [{"userid": "002", "loginid": "login"}], [])
                with self.assertRaises(SetupError):
                    task.inspect_users()
                task = Setup(api, {}, [{"userid": "001", "loginid": "login"}], [])
                task.inspect_users()
                self.assertEqual(task.existing_count, 1)
                self.assertEqual(task.new_users, [])


if __name__ == "__main__":
    unittest.main()
