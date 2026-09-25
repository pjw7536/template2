"""Discovery 입력과 설정 Job의 순서·실패 중단을 검증합니다."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("discovery_setup", ROOT / "deploy/keycloak/scripts/setup_discovery.py")
setup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(setup)

METADATA = {
    "issuer": "http://adfs.test/adfs/services/trust",
    "authorization_endpoint": "https://adfs.test/auth",
    "token_endpoint": "https://adfs.test/token",
    "jwks_uri": "https://adfs.test/keys",
    "response_types_supported": ["code"],
    "token_endpoint_auth_methods_supported": ["client_secret_post"],
}
VALUES = {
    "CORP_OIDC_DISCOVERY_URL": "https://adfs.test/.well-known/openid-configuration",
    "CORP_OIDC_CLIENT_ID": "client",
    "CORP_OIDC_CLIENT_SECRET": "private-marker",
    "CORP_OIDC_CLIENT_AUTH_METHOD": "client_secret_post",
}


class MetadataTests(unittest.TestCase):
    def test_missing_credentials_are_reported_before_network(self):
        with patch.object(setup, "urlopen") as request:
            with self.assertRaisesRegex(ValueError, "CORP_OIDC_CLIENT_SECRET"):
                setup.discover({**VALUES, "CORP_OIDC_CLIENT_SECRET": ""})
            request.assert_not_called()

    def test_discovery_precedence_and_adfs_issuer(self):
        result = setup.resolve_metadata({**VALUES, "CORP_OIDC_TOKEN_URL": "https://old.test/token"}, METADATA)
        self.assertEqual(result["CORP_OIDC_TOKEN_URL"], METADATA["token_endpoint"])
        self.assertEqual(result["CORP_OIDC_ISSUER"], METADATA["issuer"])
        self.assertEqual(result["CORP_OIDC_CLIENT_SECRET"], "private-marker")
        self.assertEqual(result["CORP_OIDC_VALIDATE_SIGNATURE"], "true")

    def test_rejects_incomplete_or_unsafe_metadata(self):
        for key, value in [("jwks_uri", None), ("token_endpoint", "http://adfs.test/token"),
                           ("token_endpoint", "https://user:password@adfs.test/token"),
                           ("response_types_supported", ["id_token"]),
                           ("token_endpoint_auth_methods_supported", ["private_key_jwt"])]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                setup.resolve_metadata(VALUES, {**METADATA, key: value})
        with self.assertRaises(ValueError):
            setup.resolve_metadata({**VALUES, "CORP_OIDC_VALIDATE_SIGNATURE": "false"}, METADATA)

    def test_optional_endpoints_and_default_auth_method(self):
        metadata = dict(METADATA)
        del metadata["token_endpoint_auth_methods_supported"]
        result = setup.resolve_metadata({**VALUES, "CORP_OIDC_CLIENT_AUTH_METHOD": "client_secret_basic",
                                         "CORP_OIDC_LOGOUT_URL": "https://adfs.test/logout"}, metadata)
        self.assertEqual(result["CORP_OIDC_USERINFO_URL"], "")
        self.assertEqual(result["CORP_OIDC_LOGOUT_URL"], "https://adfs.test/logout")

    def test_real_env_validation_accepts_resolved_metadata(self):
        values = setup.resolve_metadata(VALUES, METADATA)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "resolved.env"
            setup.write_resolved(path, values)
            setup.run(["bash", setup.SHARED / "check-env.sh", "keycloak", "prod", "oidc", path])


class FlowTests(unittest.TestCase):
    def execute(self, action="apply", fail=None, portal=True, step="all"):
        calls = []

        def command(args, **kwargs):
            args = [str(arg) for arg in args]
            calls.append(args)
            if fail and fail in args:
                raise ValueError("시험 실패")
            if "create" in args and "configmap" in args:
                return json.dumps({"kind": "ConfigMap"})
            if "create" in args and "--dry-run=client" in args:
                return json.dumps({"metadata": {}, "spec": {"template": {"metadata": {}, "spec": {
                    "containers": [{"env": [], "envFrom": [{"secretRef": {"name": "oidc"}}]}]}}}})
            if "env" in kwargs:
                wrapper = Path(kwargs["env"]["KUBECTL_BIN"]).read_text()
                self.assertIn("--context test-context", wrapper)
            return ""

        with patch.object(setup, "discover", return_value=setup.resolve_metadata(VALUES, METADATA)), \
                patch.object(setup, "read_env", return_value=VALUES), \
                patch.object(setup, "run", side_effect=command):
            if fail:
                with self.assertRaises(ValueError):
                    setup.setup(action, "test-context", Path("unused"), Path("portal.env") if portal else None, step)
            else:
                setup.setup(action, "test-context", Path("unused"), Path("portal.env") if portal else None, step)
        return calls

    def test_check_does_not_write_cluster(self):
        calls = self.execute("check")
        self.assertFalse(any("apply" in call or "delete" in call for call in calls))

    def test_jobs_run_in_order_and_context_is_explicit(self):
        calls = self.execute()
        jobs = [call for call in calls if "wait" in call]
        self.assertEqual([call[-2] for call in jobs], ["job/keycloak-oidc-setup", "job/keycloak-oidc-claim-mappers", "job/portal-keycloak-client"])
        for call in calls:
            if call[0] == "kubectl" and "kustomize" not in call:
                self.assertEqual(call[1:3], ["--context", "test-context"])

    def test_idp_failure_prevents_mapper_and_client_jobs(self):
        calls = self.execute(fail="job/keycloak-oidc-setup")
        self.assertFalse(any("keycloak-oidc-claim-mappers" in call or "portal-keycloak-client" in call for call in calls))

    def test_portal_is_optional(self):
        calls = self.execute(portal=False)
        self.assertEqual(len([call for call in calls if "wait" in call]), 2)

    def test_each_step_runs_only_its_own_job(self):
        names = {"realm": "keycloak-realm-setup", "idp": "keycloak-oidc-setup",
                 "profile": "keycloak-user-profile-setup", "mappers": "keycloak-idp-mappers-setup",
                 "portal": "portal-keycloak-client"}
        for step, name in names.items():
            with self.subTest(step=step):
                calls = self.execute(step=step, portal=step == "portal")
                self.assertEqual([call[-2] for call in calls if "wait" in call], ["job/" + name])
                secrets = [call for call in calls if str(setup.SHARED / "apply-env.sh") in call]
                self.assertEqual(len(secrets), int(step in ("idp", "portal")))

    def test_profile_does_not_require_discovery_env(self):
        with patch.object(setup, "discover") as discover, patch.object(setup, "read_env") as read:
            setup.setup("check", "test", Path("missing"), step="profile")
            discover.assert_not_called()
            read.assert_not_called()

    def test_step_jobs_have_independent_modes_and_realm_needs_no_oidc_secret(self):
        for step, key in (("profile", "KEYCLOAK_PROFILE_ONLY"), ("mappers", "KEYCLOAK_SKIP_PROFILE"), ("realm", None)):
            payload = {"metadata": {}, "spec": {"template": {"metadata": {}, "spec": {
                "containers": [{"env": [], "envFrom": ["oidc-secret"]}]}}}}
            result = setup.step_job(payload, "test-job", step)
            container = result["spec"]["template"]["spec"]["containers"][0]
            if key:
                self.assertIn({"name": key, "value": "true"}, container["env"])
            else:
                self.assertNotIn("envFrom", container)
                self.assertEqual(container["command"][-1], "/opt/keycloak-config/setup-realm.sh")


class ShellEntryTests(unittest.TestCase):
    """실제 shell 진입점과 Python 변환을 연결하고 외부 I/O만 대체합니다."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.input = self.directory / "input.env"
        self.input.write_text("".join(f"{key}={value}\n" for key, value in VALUES.items()))
        self.metadata = self.directory / "metadata.json"
        self.metadata.write_text(json.dumps(METADATA))
        # 자식 Python에서 metadata HTTP 조회만 가짜 응답으로 교체합니다.
        (self.directory / "sitecustomize.py").write_text('''
import io, os, pathlib, urllib.request
class Response(io.BytesIO):
    def geturl(self):
        return "https://adfs.test/.well-known/openid-configuration"
def fetch(*args, **kwargs):
    with open(os.environ["FETCH_LOG"], "a") as log:
        log.write("fetch\\n")
    return Response(pathlib.Path(os.environ["METADATA_FILE"]).read_bytes())
urllib.request.urlopen = fetch
''')
        kubectl = self.directory / "kubectl"
        kubectl.write_text('''#!/usr/bin/env python3
import os, pathlib, sys
args = sys.argv[1:]
with open(os.environ["KUBE_LOG"], "a") as log:
    log.write(" ".join(args) + "\\n")
if "create" in args:
    source = next(arg.split("=", 1)[1] for arg in args if arg.startswith("--from-env-file="))
    pathlib.Path(os.environ["SECRET_INPUT"]).write_text(pathlib.Path(source).read_text())
    print("{}")
else:
    sys.stdin.read()
''')
        kubectl.chmod(0o700)
        self.env = {**os.environ, "PYTHONPATH": str(self.directory), "METADATA_FILE": str(self.metadata),
                    "KUBECTL_BIN": str(kubectl), "FETCH_LOG": str(self.directory / "fetch.log"),
                    "KUBE_LOG": str(self.directory / "kube.log"), "SECRET_INPUT": str(self.directory / "secret.env")}

    def command(self, name):
        result = subprocess.run(["bash", setup.SHARED / name, "keycloak", "prod", "oidc", self.input],
                                env=self.env, text=True, capture_output=True)
        self.assertNotIn("private-marker", result.stdout + result.stderr)
        return result

    def test_existing_check_command_accepts_discovery_only_env(self):
        result = self.command("check-env.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.directory / "kube.log").exists())
        self.assertEqual((self.directory / "fetch.log").read_text(), "fetch\n")

    def test_existing_secret_command_passes_resolved_endpoints(self):
        result = self.command("apply-env.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        values = setup.read_env(self.directory / "secret.env")
        self.assertEqual(values["CORP_OIDC_TOKEN_URL"], METADATA["token_endpoint"])
        self.assertEqual(values["CORP_OIDC_ISSUER"], METADATA["issuer"])
        self.assertEqual(values["CORP_OIDC_CLIENT_SECRET"], "private-marker")
        self.assertNotIn("CORP_OIDC_DISCOVERY_URL", values)
        self.assertEqual((self.directory / "fetch.log").read_text(), "fetch\n")

    def test_discovery_failure_prevents_secret_write(self):
        self.metadata.write_text("{}")
        result = self.command("apply-env.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("authorization_endpoint", result.stderr)
        self.assertFalse((self.directory / "kube.log").exists())

    def test_resolved_env_is_private_and_does_not_trigger_discovery_again(self):
        resolved = self.directory / "resolved.env"
        setup.write_resolved(resolved, setup.resolve_metadata(VALUES, METADATA))
        self.assertEqual(resolved.stat().st_mode & 0o777, 0o600)
        self.input = resolved
        result = self.command("check-env.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.directory / "fetch.log").exists())


if __name__ == "__main__":
    unittest.main()
