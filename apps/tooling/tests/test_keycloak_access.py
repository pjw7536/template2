"""앱 역할 카탈로그 검사와 역할·기본 역할·공개 카탈로그 계산을 서버 없이 검사합니다."""

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2].parent
SCRIPTS = ROOT / "deploy/keycloak/scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("access_apply", SCRIPTS / "access_apply.py")
access = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(access)

PORTAL = {"client": "portal", "name": "Portal", "features": [
    {"key": "emails", "name": "Emails", "default": "open"},
    {"key": "access-stats", "name": "접속 현황", "default": "closed"},
]}
AIRFLOW = {"client": "airflow", "name": "Airflow", "default": "open"}


class CatalogTests(unittest.TestCase):
    def load(self, data):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            return access.load_catalog(path)

    def test_repository_catalog_is_valid(self):
        apps = access.load_catalog(ROOT / "deploy/keycloak/access/catalog.json")
        self.assertIn("portal", [app.get("client") for app in apps])

    def test_invalid_catalogs(self):
        for apps in [
            [],
            [{"name": "x"}],
            [{"client": "a", "group": "/g", "name": "x"}],
            [AIRFLOW, AIRFLOW],
            [{"client": "a", "name": "A", "default": "maybe"}],
            [{"client": "a", "name": "A", "default": "open", "dataAll": True}],
            [{"client": "p", "name": "P", "features": [{"key": "all", "name": "x", "default": "open"}]}],
            [{"client": "p", "name": "P", "features": [{"key": "Bad Key", "name": "x", "default": "open"}]}],
            [{"client": "p", "name": "P", "features": [{"key": "a", "name": "x", "default": "open"}] * 2}],
            [{"group": "headlamp-admins", "name": "H"}],
        ]:
            with self.subTest(apps=apps), self.assertRaises(access.SetupError):
                self.load({"apps": apps})


class RoleTests(unittest.TestCase):
    def test_single_app_levels_are_nested(self):
        roles = access.desired_roles(AIRFLOW)
        self.assertEqual(list(roles), ["viewer", "user", "admin"])
        self.assertEqual(roles["user"]["composites"], ["viewer"])
        self.assertEqual(roles["admin"]["composites"], ["user"])

    def test_feature_roles_and_bundles(self):
        roles = access.desired_roles(PORTAL)
        self.assertEqual(len(roles), 9)
        self.assertEqual(roles["all:viewer"]["composites"], ["emails:viewer", "access-stats:viewer"])
        self.assertEqual(roles["all:admin"]["composites"], ["all:user", "emails:admin", "access-stats:admin"])

    def test_default_roles_follow_open_and_closed(self):
        self.assertEqual(access.default_roles(PORTAL), ({"emails:viewer"}, {"access-stats:viewer"}))
        self.assertEqual(access.default_roles(AIRFLOW), ({"viewer"}, set()))


class PublishTests(unittest.TestCase):
    def test_public_entries_include_client_id_and_no_internal_fields(self):
        entry = access.public_entry(PORTAL, "uuid-1")
        self.assertEqual(entry["uuid"], "uuid-1")
        self.assertEqual(entry["features"][0], {"key": "emails", "name": "Emails", "default": "open"})
        self.assertEqual(access.public_entry({"group": "/h", "name": "H", "infra": True}, None), {"group": "/h", "name": "H", "infra": True})

    def test_chunks_fit_group_attribute_and_round_trip(self):
        text = json.dumps({"apps": [access.public_entry(PORTAL, "u")] * 20}, ensure_ascii=False)
        parts = access.chunk(text)
        self.assertTrue(all(len(part) <= 255 for part in parts))
        self.assertEqual(access.unchunk(list(reversed(parts))), text)


if __name__ == "__main__":
    unittest.main()
