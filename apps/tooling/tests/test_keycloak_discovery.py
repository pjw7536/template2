"""Discovery 입력과 설정 Job의 순서·실패 중단을 검증합니다."""

import importlib.util
import json
from pathlib import Path
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
            path.write_text("".join(f"{key}={value}\n" for key, value in values.items()))
            setup.run(["bash", setup.SHARED / "check-env.sh", "keycloak", "prod", "oidc", path])


class FlowTests(unittest.TestCase):
    def execute(self, action="apply", fail=None, portal=True):
        calls = []

        def command(args, **kwargs):
            args = [str(arg) for arg in args]
            calls.append(args)
            if fail and fail in args:
                raise ValueError("시험 실패")
            if "create" in args and "configmap" in args:
                return json.dumps({"kind": "ConfigMap"})
            if "env" in kwargs:
                wrapper = Path(kwargs["env"]["KUBECTL_BIN"]).read_text()
                self.assertIn("--context test-context", wrapper)
            return ""

        with patch.object(setup, "discover", return_value=setup.resolve_metadata(VALUES, METADATA)), \
                patch.object(setup, "read_env", return_value=VALUES), \
                patch.object(setup, "run", side_effect=command):
            if fail:
                with self.assertRaises(ValueError):
                    setup.setup(action, "test-context", Path("unused"), Path("portal.env") if portal else None)
            else:
                setup.setup(action, "test-context", Path("unused"), Path("portal.env") if portal else None)
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


if __name__ == "__main__":
    unittest.main()
