"""로컬 Secret 갱신에서 폐기된 인증 설정이 남지 않는지 검증합니다."""

import base64
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[3] / 'local/shared/scripts'
with patch.object(sys, 'path', [str(SCRIPTS), *sys.path]):
    SPEC = importlib.util.spec_from_file_location('local_runtime', SCRIPTS / 'k8s.py')
    runtime = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(runtime)


class SecretTests(unittest.TestCase):
    def test_minio_update_preserves_existing_job_and_only_applies_storage_and_routing(self):
        """독립 갱신에서 Portal을 재배포하거나 기존 버킷·Job을 삭제하지 않습니다."""
        shared = [{'kind': 'ConfigMap', 'metadata': {'name': 'paths'}, 'data': {'paths.yaml': 'content'}},
                  {'kind': 'Deployment', 'metadata': {'name': 'traefik'}},
                  {'kind': 'Deployment', 'metadata': {'name': 'api'}}]
        storage = [{'kind': 'Deployment', 'metadata': {'name': 'minio'}},
                   {'kind': 'PersistentVolumeClaim', 'metadata': {'name': 'minio-data'}},
                   {'kind': 'Job', 'metadata': {'name': 'minio-init'}}]
        with patch.object(runtime, 'minio_secrets'), patch.object(runtime, 'resources', side_effect=[shared, storage]), \
                patch.object(runtime, 'apply') as apply, patch.object(runtime, 'run', return_value='job/minio-init') as run, \
                patch.object(runtime, 'rollout'), patch.object(runtime, 'wait_job'):
            runtime.minio_up()
        items = [item for call in apply.call_args_list for item in call.args[0]]
        self.assertNotIn('api', [item['metadata']['name'] for item in items])
        self.assertFalse(any(item['kind'] == 'Job' for item in items))
        self.assertFalse(any('delete' in call.args[0] for call in run.call_args_list))

    def test_update_replaces_old_keys_without_deleting_secret(self):
        state = {'ADFS_AUTH_URL': 'b2xk', 'OIDC_CLIENT_SECRET': 'b2xk'}
        calls = []

        def run(args, **kwargs):
            calls.append((args, kwargs))
            if 'get' in args:
                return 'secret/api-env'
            self.assertIn('patch', args)
            self.assertNotIn('private-value', ' '.join(args))
            self.assertTrue(kwargs['sensitive'])
            for operation in json.loads(kwargs['data']):
                self.assertEqual(operation['path'], '/data')
                self.assertEqual(operation['op'], 'add')
                state.clear()
                state.update(operation['value'])
            return ''

        with patch.object(runtime, 'run', side_effect=run):
            runtime.secret('tailwind-local', 'api-env', {'OIDC_CLIENT_SECRET': 'private-value'})
        self.assertNotIn('ADFS_AUTH_URL', state)
        self.assertEqual(base64.b64decode(state['OIDC_CLIENT_SECRET']).decode(), 'private-value')
        self.assertEqual(len(calls), 2)

    def test_first_start_creates_secret(self):
        with patch.object(runtime, 'run', return_value=''), patch.object(runtime, 'apply') as apply:
            runtime.secret('tailwind-local', 'api-env', {'OIDC_CLIENT_ID': 'portal'})
        items = apply.call_args.args[0]
        self.assertEqual(items[0]['metadata']['name'], 'api-env')
        self.assertEqual(base64.b64decode(items[0]['data']['OIDC_CLIENT_ID']), b'portal')
        self.assertTrue(apply.call_args.kwargs['sensitive'])


class AirflowCredentialTests(unittest.TestCase):
    def test_local_routes_do_not_inherit_production_host_or_tls(self):
        """운영 기본 주소가 바뀌어도 로컬 인증·port-forward 계약을 유지합니다."""
        import k8s_config
        monitoring = k8s_config.monitoring_settings()
        runtime.module('monitoring').validate(monitoring)
        self.assertEqual(monitoring['INGRESS_ENABLED'], 'false')
        self.assertEqual(monitoring['INGRESS_HOST'], '')
        self.assertEqual(monitoring['INGRESS_TLS_SECRET'], '')
        with patch.object(k8s_config, 'RUNTIME', Path('/nonexistent/local-web-routing-test')):
            airflow = k8s_config.airflow_settings(k8s_config.credentials())
        runtime.module('airflow').validate(airflow)
        self.assertEqual(airflow['AIRFLOW_WEBSERVER_BASE_URL'], 'http://localhost:8080/airflow')
        self.assertEqual(airflow['AIRFLOW_OIDC_ISSUER'], 'http://localhost:8180/realms/portal')
        self.assertEqual(airflow['INGRESS_TLS_SECRET'], '')

    def test_upgrade_adds_only_client_secret_and_read_only_check_does_not_write(self):
        """기존 DB·Fernet 키를 유지하며 쓰기 실행에서만 누락 secret을 추가한다."""
        import tempfile
        import k8s_config
        with tempfile.TemporaryDirectory() as directory, patch.object(k8s_config, 'RUNTIME', Path(directory)):
            current = k8s_config.credentials(create=True)
            current.pop('AIRFLOW_OIDC_CLIENT_SECRET')
            path = Path(directory) / 'credentials.env'
            k8s_config.write_env(path, current)
            original = path.read_bytes()
            checked = k8s_config.credentials()
            self.assertIn('AIRFLOW_OIDC_CLIENT_SECRET', checked)
            self.assertEqual(path.read_bytes(), original)
            upgraded = k8s_config.credentials(create=True)
            self.assertEqual({key: upgraded[key] for key in current}, current)
            self.assertGreaterEqual(len(upgraded['AIRFLOW_OIDC_CLIENT_SECRET']), 32)
            self.assertEqual(k8s_config.credentials(create=True), upgraded)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
