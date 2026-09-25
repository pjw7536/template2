"""사내망 없이 CSV 검증과 선택적인 실제 Keycloak 초기 설정을 검사합니다."""

import base64
import copy
import csv
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch
import uuid


ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("sdwt_init", ROOT / "deploy/keycloak/scripts/init_sdwt.py")
setup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(setup)


class InputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def file(self, name, content):
        path = self.directory / name
        path.write_text(content, encoding="utf-8-sig")
        return path

    def test_reference_and_unaffiliated(self):
        sdwts = self.file("sdwts.csv", "user_sdwt_prod,line_id\nA,L\nB,L\n")
        users = self.file("users.csv", "userid,user_sdwt_prod\n001,A\n002,\n")
        result, people = setup.load_inputs(sdwts, users)
        self.assertEqual(result, {"A": "L", "B": "L"})
        self.assertEqual(people[1]["user_sdwt_prod"], "")
        self.assertEqual(people[0]["userid"], "001")

    def test_invalid_csv(self):
        for content in [
            "user_sdwt_prod,line_id\nA,L\nA,L2\n",
            "user_sdwt_prod,line_id\nA/user,L\n",
            "user_sdwt_prod,line_id\n A,L\n",
            "user_sdwt_prod,line_id\nA,\n",
            "user_sdwt_prod,line_id\nA\n",
            "user_sdwt_prod,line_id,line_id\nA,L,L\n",
        ]:
            with self.subTest(content=content), self.assertRaises(setup.SetupError):
                setup.load_inputs(self.file("sdwts.csv", content), None)

    def test_optional_oidc_grade(self):
        sdwts = self.file("sdwts.csv", "user_sdwt_prod,line_id\nA,L\n")
        users = self.file("users.csv", "userid,user_sdwt_prod,grdname_en\n001,A,CL3\n002,A,\n")
        _, people = setup.load_inputs(sdwts, users)
        self.assertEqual(people[0]["grdname_en"], "CL3")
        self.assertEqual(people[1]["grdname_en"], "")
        for retired in ("grd_name", "career_level"):
            with self.subTest(retired=retired), self.assertRaises(setup.SetupError):
                setup.load_inputs(sdwts, self.file("old.csv", f"userid,user_sdwt_prod,{retired}\n001,A,CL3\n"))

    def test_invalid_users(self):
        sdwts = self.file("sdwts.csv", "user_sdwt_prod,line_id\nA,L\n")
        for content in [
            "userid,user_sdwt_prod\n001,B\n",
            "userid,user_sdwt_prod\n001,A\n001,A\n",
            "userid,user_sdwt_prod\n,A\n",
            "userid,user_sdwt_prod,mail\n001,A,a@example.invalid\n002,A,A@example.invalid\n",
            "userid,user_sdwt_prod,loginid\n001,A,duplicate\n002,A,duplicate\n",
            "epid,user_sdwt_prod\n001,A\n",
            "userid,user_sdwt_prod,knox_id\n001,A,old.login\n",
            "userid,user_sdwt_prod,email\n001,A,old@example.invalid\n",
            "userid,user_sdwt_prod,department\n001,A,old.department\n",
        ]:
            with self.subTest(content=content), self.assertRaises(setup.SetupError):
                setup.load_inputs(sdwts, self.file("users.csv", content))

    def test_credentials_only_use_https_or_loopback(self):
        for url in ["http://sso.example.invalid", "https://user:pass@sso.example.invalid", "https://sso.example.invalid?token=secret"]:
            with patch.dict(os.environ, {"KEYCLOAK_ADMIN_URL": url}), self.assertRaises(setup.SetupError):
                setup.Admin("etch")

    def test_local_scope_matches_common_definition(self):
        local = json.loads((ROOT / "local/keycloak/k8s/realm-portal.json").read_text())
        common = json.loads((ROOT / "deploy/keycloak/k8s/claims/sdwt-access-scope.json").read_text())
        self.assertNotIn("clientScopes", local)
        self.assertIn(common["protocolMappers"][0], local["clients"][0]["protocolMappers"])
        self.assertIn("profile", local["clients"][0]["defaultClientScopes"])
        self.assertNotIn("microprofile-jwt", local["clients"][0]["optionalClientScopes"])


@unittest.skipUnless(os.environ.get("KEYCLOAK_SDWT_TEST_URL"), "실제 Keycloak 검사는 전용 TEST_URL을 지정해야 실행합니다.")
class KeycloakTests(unittest.TestCase):
    """임의 이름의 테스트 realm만 생성·삭제하고 기존 realm에는 접근하지 않습니다."""

    def setUp(self):
        self.realm = "sdwt-test-" + uuid.uuid4().hex
        self.env = patch.dict(os.environ, {"KEYCLOAK_ADMIN_URL": os.environ["KEYCLOAK_SDWT_TEST_URL"]})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.api = setup.Admin(self.realm)
        self.api.login()
        self.api._send("POST", "/admin/realms", {"realm": self.realm, "enabled": True})
        self.addCleanup(self.api.call, "DELETE")
        for client in ["portal", "headlamp"]:
            self.api.call("POST", "clients", {
                "clientId": client, "protocol": "openid-connect", "publicClient": True,
                "directAccessGrantsEnabled": True, "attributes": {"unrelated": "preserve"},
            })
        self.sdwts = {"SDWT-A": "LINE-1", "SDWT-B": "LINE-1"}
        self.users = [{"userid": "001", "user_sdwt_prod": "SDWT-A", "sabun": "S001"},
                      {"userid": "002", "user_sdwt_prod": ""}]

    def run_setup(self, users=None, apply=True):
        plan = setup.Setup(self.api, self.sdwts, self.users if users is None else users, ["portal"])
        plan.inspect()
        with redirect_stdout(io.StringIO()):
            plan.report()
            if apply:
                plan.apply()
        return plan

    def user(self, name):
        return self.api.call("GET", "users", query={"username": name, "exact": "true"})[0]

    def group(self, sdwt, role):
        parent = setup.one(self.api.pages("groups", populateHierarchy="false"), "name", sdwt)
        return setup.one(self.api.pages(f"groups/{parent['id']}/children"), "name", role)

    def test_dry_run_and_repeat_preserve_existing(self):
        plan = self.run_setup(apply=False)
        self.assertEqual(len(plan.new_users), 2)
        self.assertEqual(self.api.pages("users"), [])
        self.assertEqual(self.api.pages("groups"), [])
        self.run_setup()
        user = self.user("001")
        self.assertEqual(user["attributes"]["line_id"], ["LINE-1"])
        group = self.group("SDWT-A", "user")
        self.api.call("DELETE", f"users/{user['id']}/groups/{group['id']}")
        changed = copy.deepcopy(self.users)
        changed[0]["user_sdwt_prod"] = "SDWT-B"
        self.run_setup(changed)
        self.assertEqual(self.user("001")["attributes"]["user_sdwt_prod"], ["SDWT-A"])
        self.assertEqual(self.api.pages(f"users/{user['id']}/groups"), [])
        self.assertNotIn("user_sdwt_prod", self.user("002").get("attributes", {}))
        client = self.api.call("GET", "clients", query={"clientId": "headlamp"})[0]
        self.assertNotIn("access.token.lifespan", client.get("attributes", {}))
        self.assertNotIn("sdwt-access-v1", [s["name"] for s in self.api.call("GET", f"clients/{client['id']}/default-client-scopes")])

    def test_claims_and_refresh_after_revocation(self):
        self.run_setup()
        user = self.user("001")
        self.api.call("PUT", f"users/{user['id']}", {
            "firstName": "Test", "lastName": "User", "email": "test@example.invalid", "emailVerified": True,
        })
        self.api.call("PUT", f"users/{user['id']}/reset-password", {"type": "password", "value": "test-password", "temporary": False})
        for sdwt, role in [("SDWT-A", "admin"), ("SDWT-B", "viewer")]:
            group = self.group(sdwt, role)
            self.api.call("PUT", f"users/{user['id']}/groups/{group['id']}")
        token_path = f"/realms/{self.realm}/protocol/openid-connect/token"
        token = self.api._send("POST", token_path, {
            "grant_type": "password", "client_id": "portal", "username": "001", "password": "test-password", "scope": "openid",
        }, form=True, auth=False)
        self.assertLessEqual(token["expires_in"], 300)
        for kind in ["access_token", "id_token"]:
            payload = token[kind].split(".")[1]
            claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
            self.assertEqual(claims["userid"], "001")
            self.assertEqual(claims["user_sdwt_prod"], "SDWT-A")
            self.assertEqual(set(claims["groups"]), {"/SDWT-A/user", "/SDWT-A/admin", "/SDWT-B/viewer"})
        group = self.group("SDWT-A", "admin")
        self.api.call("DELETE", f"users/{user['id']}/groups/{group['id']}")
        token = self.api._send("POST", token_path, {
            "grant_type": "refresh_token", "client_id": "portal", "refresh_token": token["refresh_token"],
        }, form=True, auth=False)
        payload = token["access_token"].split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        self.assertNotIn("/SDWT-A/admin", claims["groups"])

    def test_oidc_grade_persists_without_overwriting_existing(self):
        users = copy.deepcopy(self.users)
        users[0].update(grdname_en="CL3")
        users[1].update(grdname_en="")
        self.run_setup(users)
        attributes = self.user("001")["attributes"]
        self.assertEqual(attributes["grdname_en"], ["CL3"])
        self.assertNotIn("grd_name", attributes)
        self.assertNotIn("grdname_en", self.user("002").get("attributes", {}))
        profile = self.api.call("GET", "users/profile")
        grade = setup.one(profile["attributes"], "name", "grdname_en")
        self.assertEqual(grade["permissions"]["edit"], ["admin"])
        self.assertIsNone(setup.one(profile["attributes"], "name", "career_level"))
        users[0].update(grdname_en="CL4")
        self.run_setup(users)
        self.assertEqual(self.user("001")["attributes"], attributes)

    def test_csv_claim_names_map_to_existing_keycloak_fields(self):
        values = {"userid": "000003", "user_sdwt_prod": "SDWT-A", "sabun": "S003",
                  "loginid": "example.user", "username": "표시이름", "mail": "example@example.invalid",
                  "deptname": "예시부서", "grdname_en": "CL3"}
        header = (ROOT / "deploy/keycloak/examples/users.template.csv").read_text().strip().split(",")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "users.csv"
            with path.open("w", encoding="utf-8", newline="") as output:
                writer = csv.DictWriter(output, fieldnames=header)
                writer.writeheader()
                writer.writerow(values)
            _, users = setup.load_inputs(ROOT / "deploy/keycloak/examples/sdwts.csv", path)
        self.run_setup(users)
        user = self.user("000003")
        self.assertEqual(user["username"], "000003")
        self.assertEqual(user["email"], "example@example.invalid")
        self.assertEqual(user["attributes"]["knox_id"], ["example.user"])
        self.assertEqual(user["attributes"]["display_name"], ["표시이름"])
        self.assertEqual(user["attributes"]["department"], ["예시부서"])
        self.assertEqual(user["attributes"]["grdname_en"], ["CL3"])
        with self.assertRaises(setup.SetupError):
            self.run_setup([{**values, "userid": "000004", "mail": "other@example.invalid", "sabun": "S004"}])
        with self.assertRaises(setup.SetupError):
            self.run_setup([{**values, "loginid": "different.user"}])

    def test_partial_failure_resumes_without_reset(self):
        original = self.api.call
        calls = 0

        def fail_second_user(method, path="", data=None, query=None):
            nonlocal calls
            if method == "POST" and path == "users":
                calls += 1
                if calls == 2:
                    raise setup.SetupError("의도한 네트워크 실패")
            return original(method, path, data, query)

        with patch.object(self.api, "call", side_effect=fail_second_user), self.assertRaises(setup.SetupError):
            self.run_setup()
        self.assertEqual(len(self.api.pages("users")), 1)
        plan = self.run_setup()
        self.assertEqual(plan.existing_count, 1)
        self.assertEqual(len(self.api.pages("users")), 2)
        self.assertEqual([g["path"] for g in self.api.pages(f"users/{self.user('001')['id']}/groups")], ["/SDWT-A/user"])

    def test_scope_collision_fails_before_writes(self):
        client = self.api.call("GET", "clients", query={"clientId": "portal"})[0]
        mapper = copy.deepcopy(setup.Setup(self.api, {}, [], []).scope_definition["protocolMappers"][0])
        mapper["config"]["full.path"] = "false"
        self.api.call("POST", f"clients/{client['id']}/protocol-mappers/models", mapper)
        with self.assertRaises(setup.SetupError):
            self.run_setup()
        self.assertEqual(self.api.pages("groups"), [])
        self.assertEqual(self.api.pages("users"), [])

    def test_identity_collision_fails_before_writes(self):
        self.api.call("POST", "users", {"username": "old-user", "email": "same@example.invalid"})
        users = [{"userid": "001", "user_sdwt_prod": "SDWT-A", "mail": "same@example.invalid"}]
        with self.assertRaises(setup.SetupError):
            self.run_setup(users)
        self.assertEqual(self.api.pages("groups"), [])

    def test_pagination(self):
        with patch.object(setup, "PAGE_SIZE", 1):
            self.run_setup()
            self.assertEqual(len(self.api.pages("users")), 2)
            self.assertEqual(len(self.api.pages("groups", populateHierarchy="false")), 2)

    def test_local_import_preserves_standard_claims_and_migrates_mapper(self):
        local_realm = "sdwt-test-" + uuid.uuid4().hex
        realm = json.loads((ROOT / "local/keycloak/k8s/realm-portal.json").read_text())
        realm["realm"] = local_realm
        self.api._send("POST", "/admin/realms", realm)
        api = setup.Admin(local_realm)
        self.addCleanup(api.call, "DELETE")
        client = api.call("GET", "clients", query={"clientId": "portal"})[0]
        defaults = api.call("GET", f"clients/{client['id']}/default-client-scopes")
        self.assertIn("profile", [scope["name"] for scope in defaults])
        plan = setup.Setup(api, self.sdwts, [], ["portal"])
        plan.inspect()
        with redirect_stdout(io.StringIO()):
            plan.apply()
        setup.Setup(api, self.sdwts, [], ["portal"]).inspect()
        api.call("PUT", f"clients/{client['id']}", {"directAccessGrantsEnabled": True})
        token = api._send("POST", f"/realms/{local_realm}/protocol/openid-connect/token", {
            "grant_type": "password", "client_id": "portal", "client_secret": "portal-local-secret",
            "username": "dummy.user", "password": "dummy-user-change-me", "scope": "openid",
        }, form=True, auth=False)
        payload = token["id_token"].split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        self.assertEqual(claims["preferred_username"], "dummy.user")
        self.assertEqual(claims["sabun"], "S000001")


if __name__ == "__main__":
    unittest.main()
