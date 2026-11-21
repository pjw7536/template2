"""IAM 배포의 이미지 일치, 저장소 보존, 순서를 검증합니다."""

import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import manage  # noqa: E402


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.settings = manage.iam_settings(manage.APP / "env/prod.env")
        self.images = {"api": "zot.test/tailwind/iam-api:tag", "web": "zot.test/tailwind/iam-web:tag"}
        self.items = manage.manifests(self.settings, "https://sso.test", "fixture CA", self.images)
        self.volume = next(item for item in self.items if item["kind"] == "PersistentVolume")
        self.claim = next(item for item in self.items if item["kind"] == "PersistentVolumeClaim")

    def test_render_keeps_api_private_and_configures_a_single_persistent_writer(self):
        items = {item["metadata"]["name"]: item for item in self.items if item["kind"] not in ("Service", "Namespace", "PersistentVolume")}
        api = items["iam-api"]["spec"]
        self.assertEqual(api["replicas"], 1)
        self.assertEqual(api["strategy"], {"type": "Recreate"})
        pod = api["template"]["spec"]
        self.assertEqual(pod["containers"][0]["image"], self.images["api"])
        self.assertEqual(pod["nodeSelector"], {"kubernetes.io/hostname": self.settings["node"]})
        env = {item["name"]: item["value"] for item in pod["containers"][0]["env"]}
        self.assertEqual(env["IAM_KEYCLOAK_ISSUER"], "https://sso.test/realms/etch")
        self.assertEqual(env["IAM_WORKLOAD_DB"], "/data/iam/workload.sqlite3")
        self.assertEqual(items["iam-web"]["spec"]["template"]["spec"]["containers"][0]["image"], self.images["web"])
        self.assertEqual(self.volume["spec"]["persistentVolumeReclaimPolicy"], "Retain")
        rule, = items["iam"]["spec"]["rules"]
        self.assertEqual(rule["host"], self.settings["host"])
        self.assertEqual(rule["http"]["paths"][0]["backend"]["service"]["name"], "iam-web")
        config = items["iam-web-config"]["data"]["config.js"]
        self.assertEqual(json.loads(config.removeprefix("window.__IAM_CONFIG__ = ").strip().removesuffix(";")),
                         {"keycloakUrl": "https://sso.test", "realm": "etch", "clientId": "iam"})

    def test_bound_storage_is_reused_and_different_binding_is_rejected(self):
        self.claim["metadata"]["uid"] = "current-pvc"
        self.volume["spec"]["claimRef"]["uid"] = "current-pvc"
        with patch.object(manage, "get", side_effect=[self.volume, self.claim]):
            self.assertFalse(manage.needs_volume([], self.volume, self.claim, True))
        self.volume["spec"]["claimRef"]["uid"] = "deleted-pvc"
        with patch.object(manage, "get", side_effect=[self.volume, self.claim]), self.assertRaisesRegex(ValueError, "기존 IAM PV"):
            manage.needs_volume([], self.volume, self.claim, True)

    def test_existing_bound_claim_without_a_volume_is_rejected(self):
        with patch.object(manage, "get", side_effect=[None, self.claim]), self.assertRaisesRegex(ValueError, "PV가 없습니다"):
            manage.needs_volume([], self.volume, self.claim, True)

    def test_deploy_exposes_ingress_after_keycloak_and_both_rollouts(self):
        events = Mock()
        with patch.object(manage, "check_node"), patch.object(manage, "get", return_value=None), \
                patch.object(manage, "needs_volume", return_value=True), patch.object(manage, "route_plan", return_value=([], [])), \
                patch.object(manage.image_registry, "remote_exists", return_value=True), \
                patch.object(manage.host_dirs, "prepare", events.prepare), patch.object(manage, "keycloak_setup", events.keycloak), \
                patch.object(manage, "run", events.run):
            manage.deploy("fixture", "iam.env", "keycloak.env", self.settings, self.items, self.images)
        self.assertEqual(events.prepare.call_args.args[-1], [(self.settings["path"], 10001, 10001, "0700")])
        sequence = [name if name != "run" else args[0][3:] for name, args, kwargs in events.mock_calls]
        self.assertLess(sequence.index("prepare"), sequence.index("keycloak"))
        self.assertLess(sequence.index("keycloak"), sequence.index(["-n", "iam", "rollout", "status", "deployment/iam-api", "--timeout=300s"]))
        self.assertLess(sequence.index(["-n", "iam", "rollout", "status", "deployment/iam-web", "--timeout=300s"]), len(sequence) - 1)
        self.assertEqual(json.loads(events.run.call_args.kwargs["data"])["kind"], "Ingress")

    def test_publish_only_builds_and_pushes_missing_tags(self):
        env = manage.APP / "env/build.env"
        with patch.object(manage, "image_refs", return_value=self.images), \
                patch.object(manage.image_registry, "remote_exists", side_effect=[True, False]), \
                patch.object(manage.image_registry, "nerdctl", return_value=["nerdctl"]), \
                patch.object(manage.image_registry, "build") as build, patch.object(manage.image_registry, "push") as push:
            manage.publish(env, "registry.env", "account.env")
        self.assertEqual(build.call_args.args[2], self.images["web"])
        self.assertEqual(set(build.call_args.kwargs["build_args"]), {"NODE_BASE_IMAGE", "NGINX_BASE_IMAGE", "NPM_REGISTRY"})
        push.assert_called_once_with(manage.run, ["nerdctl"], self.images["web"], "account.env")


if __name__ == "__main__":
    unittest.main()
