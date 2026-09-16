"""Headlamp 배포 입력과 변경 전 차단 조건을 검증한다."""

import importlib.util
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/manage.py'
spec = importlib.util.spec_from_file_location('headlamp_manage', SCRIPT)
manage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manage)


class DeploymentTest(unittest.TestCase):
    """외부 명령 실행 전에 잘못된 입력이 거부되는지 확인한다."""

    def test_env_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'input.env'
            for value in ['HEADLAMP_REGISTRY=https://mirror.test',
                          'HEADLAMP_REGISTRY=registry.example.invalid/ghcr',
                          'HEADLAMP_REGISTRY=mirror.test\nHEADLAMP_REGISTRY=other.test',
                          'HEADLAMP_REGISTRY=mirror.test\nUNKNOWN=value']:
                path.write_text(value)
                with self.assertRaises(ValueError):
                    manage.settings(path)
            path.write_text('HEADLAMP_REGISTRY=mirror.test:5000/ghcr\nIMAGE_PULL_SECRET=pull-secret')
            self.assertEqual(manage.settings(path)['imagePullSecrets'], [{'name': 'pull-secret'}])

    def test_chart_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'chart.tgz'
            path.write_bytes(b'wrong archive')
            with self.assertRaisesRegex(ValueError, 'SHA-256'):
                manage.verify_chart(path)

    def test_https_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'input.env'
            for extra in ['HEADLAMP_HOST=etch.example.test', 'HEADLAMP_TLS_SECRET=headlamp-tls',
                          'HEADLAMP_HOST=https://etch.example.test\nHEADLAMP_TLS_SECRET=headlamp-tls']:
                path.write_text('HEADLAMP_REGISTRY=mirror.test\n' + extra)
                with self.assertRaises(ValueError):
                    manage.settings(path)
            path.write_text('HEADLAMP_REGISTRY=mirror.test\nHEADLAMP_HOST=etch.example.test\nHEADLAMP_TLS_SECRET=headlamp-tls')
            values = manage.settings(path)
            self.assertEqual(values['config']['baseURL'], '/headlamp')
            self.assertEqual(values['ingress']['tls'][0]['secretName'], 'headlamp-tls')

    def test_ingress_preserves_live_placement_and_namespaces(self):
        current = {'metadata': {'namespace': 'etch-sso', 'resourceVersion': '12'}, 'spec': {
            'replicas': 2, 'template': {'spec': {'serviceAccountName': 'traefik',
            'affinity': {'existing': 'placement'}, 'containers': [{'name': 'traefik', 'image': 'keep:1',
            'args': ['--providers.kubernetesingress=true', '--providers.kubernetesingress.namespaces=etch-sso,airflow',
                     '--entrypoints.websecure.address=:8443']}]}}}}
        original = copy.deepcopy(current)
        values = {'ingress': {'tls': [{'secretName': 'headlamp-tls'}]}}
        for watch_all in (False, True):
            if watch_all:
                current['spec']['template']['spec']['containers'][0]['args'].pop(1)
            with patch.object(manage, 'run', side_effect=[
                subprocess.CompletedProcess([], 0, 'kubernetes.io/tls tls.crt tls.key'),
                subprocess.CompletedProcess([], 0, json.dumps(current)),
            ]):
                access, changes = manage.ingress_plan('prod', values)
            self.assertEqual(changes[0]['op'], 'test')
            if watch_all:
                self.assertEqual(len(changes), 1)
            else:
                self.assertEqual(changes[1]['path'], '/spec/template/spec/containers/0/args')
                self.assertIn('--providers.kubernetesingress.namespaces=etch-sso,airflow,headlamp', changes[1]['value'])
                self.assertEqual(current, original)
            self.assertTrue(all(x['metadata']['namespace'] == 'headlamp' for x in access['items']))
            self.assertEqual(access['items'][1]['subjects'][0]['namespace'], 'etch-sso')

    def test_invalid_tls_stops_before_controller_access(self):
        with patch.object(manage, 'run', return_value=subprocess.CompletedProcess([], 0, 'Opaque tls.crt tls.key')) as run:
            with self.assertRaisesRegex(ValueError, 'TLS Secret'):
                manage.ingress_plan('prod', {'ingress': {'tls': [{'secretName': 'headlamp-tls'}]}})
            self.assertEqual(run.call_count, 1)

    def test_rbac_failure_prevents_controller_patch(self):
        with patch.object(manage, 'run', side_effect=subprocess.CalledProcessError(1, ['kubectl'])) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                manage.connect_ingress('prod', {'items': []}, [{'op': 'test'}, {'op': 'replace'}])
            self.assertEqual(run.call_count, 1)
            self.assertIn('apply', run.call_args.args[0])

    def test_context_required(self):
        for action in ['deploy', 'ui']:
            result = subprocess.run(['python3', str(SCRIPT), action], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('KUBE_CONTEXT', result.stderr)


if __name__ == '__main__':
    unittest.main()
