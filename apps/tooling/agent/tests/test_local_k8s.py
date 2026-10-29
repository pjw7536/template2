"""로컬 Kubernetes의 데이터 보존·외부 DB·실행 경계를 검사합니다."""

import base64
import importlib.util
import json
from pathlib import Path
import tempfile
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
SPEC = importlib.util.spec_from_file_location('local_k8s_config', ROOT / 'local/shared/scripts/k8s_config.py')
config = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(config)


def fixture_credentials():
    """실제 로컬 자격증명을 읽지 않는 렌더 전용 fixture입니다."""
    with tempfile.TemporaryDirectory() as directory, patch.object(config, 'RUNTIME', Path(directory)):
        return config.credentials()


def runner_module():
    """실제 클러스터를 호출하지 않고 실행 도구를 테스트에 불러옵니다."""
    with patch.object(sys, 'path', [str(ROOT / 'local/shared/scripts'), *sys.path]):
        spec = importlib.util.spec_from_file_location('local_k8s_runner', ROOT / 'local/shared/scripts/k8s.py')
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        return runner


class LocalKubernetesTests(unittest.TestCase):
    def test_database_endpoint_tracks_current_docker_address(self):
        """DB 주소가 달라져도 두 namespace가 새 EndpointSlice를 받습니다."""
        runner = runner_module()
        for address in ('172.28.0.7', '172.28.0.9'):
            def fake_run(args, **kwargs):
                if 'inspect' in args:
                    return address + '\n'
                if 'ps' in args:
                    return 'database-container\n'
                return ''
            with patch.object(runner, 'run', fake_run), patch.object(runner, 'apply') as apply:
                runner.database_up()
            endpoints = [call.args[0][1] for call in apply.call_args_list]
            self.assertEqual({item['metadata']['namespace'] for item in endpoints}, {'tailwind-local', 'airflow'})
            self.assertTrue(all(item['endpoints'][0]['addresses'] == [address] for item in endpoints))

    def test_dependency_rebuild_keeps_service_and_generated_configmap(self):
        """선택 갱신은 앱 소유 원본 전체를 적용하고 선택한 Deployment만 재시작합니다."""
        runner = runner_module()
        for app, directory, name in [('keycloak', 'local/keycloak/k8s', 'keycloak'),
                                     ('mock', 'local/adfs_dummy/k8s', 'adfs')]:
            items = [{'kind': kind, 'metadata': {'name': name}} for kind in ('Deployment', 'Service')]
            if app == 'keycloak':
                items.append({'kind': 'ConfigMap', 'metadata': {'name': 'keycloak-realm-hashed'}})
            with self.subTest(app=app), patch.object(runner, 'resources', return_value=items) as render, \
                    patch.object(runner, 'apply') as apply, patch.object(runner, 'run') as run, \
                    patch.object(runner, 'rollout') as rollout:
                runner.dependency_up(app)
                render.assert_called_once_with(directory)
                apply.assert_called_once_with(items)
                run.assert_called_once_with([*runner.KUBE, '-n', 'tailwind-local', 'rollout', 'restart',
                                             'deployment/' + name])
                rollout.assert_called_once_with('tailwind-local', 'deployment/' + name)

    def test_dependency_apply_failure_does_not_restart_workload(self):
        """설정 적용이 실패하면 기존 Deployment를 재시작하지 않습니다."""
        runner = runner_module()
        with patch.object(runner, 'resources', return_value=[]), \
                patch.object(runner, 'apply', side_effect=RuntimeError('적용 실패')), \
                patch.object(runner, 'run') as run, patch.object(runner, 'rollout') as rollout:
            with self.assertRaises(RuntimeError):
                runner.dependency_up('keycloak')
            run.assert_not_called()
            rollout.assert_not_called()

    def test_credentials_survive_repeated_preparation(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(config, 'RUNTIME', Path(directory)):
            first = config.credentials(create=True)
            self.assertEqual(first, config.credentials(create=True))
            self.assertEqual((Path(directory) / 'credentials.env').stat().st_mode & 0o777, 0o600)
            self.assertEqual(len(base64.urlsafe_b64decode(first['AIRFLOW_FERNET_KEY'])), 32)
            self.assertEqual(len({first[key] for key in ('PORTAL_DB_PASSWORD', 'AIRFLOW_DB_PASSWORD', 'KEYCLOAK_DB_PASSWORD')}), 3)

    def test_render_credentials_do_not_write_files(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(config, 'RUNTIME', Path(directory)):
            config.credentials()
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_kind_mounts_persist_outside_nodes_and_ports_are_loopback(self):
        values = config.settings()
        values.update(LOCAL_FTP_PORT='16380', LOCAL_FTP_PASSIVE_START='18076')
        nodes = config.kind_config(values)['nodes']
        for node in nodes:
            self.assertTrue(all(port['listenAddress'] == '127.0.0.1' for port in node['extraPortMappings']))
        worker = nodes[1]
        self.assertEqual(worker['extraPortMappings'][0]['containerPort'], 6380)
        self.assertEqual(worker['extraPortMappings'][0]['hostPort'], 16380)
        self.assertEqual([p['containerPort'] for p in worker['extraPortMappings'][1:]], list(range(18076, 18080)))
        mounts = {item['containerPath']: item for item in worker['extraMounts']}
        self.assertTrue(mounts['/data/pm_spider']['readOnly'])
        self.assertFalse(mounts['/data/data_movement']['readOnly'])
        self.assertTrue(Path(mounts['/data/local-runtime']['hostPath']).is_absolute())

    def test_external_database_has_no_workload_or_database_volume(self):
        airflow = config.module('airflow')
        values = config.airflow_settings(fixture_credentials())
        airflow.validate(values)
        manifests = airflow.manifests(values)
        self.assertEqual(manifests['postgres']['items'], [])
        self.assertTrue(manifests['storage']['items'])
        self.assertNotIn('airflow-postgres', json.dumps(manifests['storage']))
        secret = next(item for item in airflow.secret_manifest(values)['items'] if item['metadata']['name'] == 'airflow-metadata')
        self.assertIn('@external-postgres:5432/airflow', base64.b64decode(secret['data']['connection']).decode())

    def test_legacy_server_env_retains_internal_database_defaults(self):
        airflow = config.module('airflow')
        values = airflow.read_env(airflow.DEFAULT_ENV)
        for key in airflow.DB_DEFAULTS:
            values.pop(key)
        airflow.validate(values, example=True)
        self.assertEqual(values['POSTGRES_MODE'], 'internal')
        self.assertTrue(airflow.manifests(values)['postgres']['items'])

    def test_shared_trigger_and_external_credentials_match(self):
        creds = fixture_credentials()
        api = config.api_overrides(creds)
        airflow = config.airflow_settings(creds)
        self.assertEqual(api['AIRFLOW_TRIGGER_TOKEN'], airflow['AIRFLOW_TRIGGER_TOKEN'])
        self.assertEqual(api['AIRFLOW_PASSWORD'], airflow['AIRFLOW_ADMIN_PASSWORD'])
        self.assertTrue(api['AIRFLOW_BASE_URL'].endswith('/airflow'))
        self.assertEqual(api['KNOX_MESSENGER_API_BASE_URL'], '')



class PlatformKubernetesTests(unittest.TestCase):
    def test_platform_database_does_not_read_portal_env(self):
        """독립 DB 연결에서 Portal 설정 합성·migration을 호출하지 않습니다."""
        runner = runner_module()
        def fake_run(args, **kwargs):
            if 'inspect' in args:
                return '172.28.0.9\n'
            if 'ps' in args:
                return 'database-container\n'
            return ''
        with patch.object(runner, 'run', side_effect=fake_run) as run, \
                patch.object(runner, 'apply'), patch.object(runner, 'portal_database_up') as portal:
            runner.database_up(include_portal=False)
        portal.assert_not_called()
        self.assertFalse(any('local/portal' in str(call) for call in run.call_args_list))

    def test_platform_preparation_preserves_existing_portal_overrides(self):
        """기존 API override는 platform 준비로 덮어쓰지 않습니다."""
        with tempfile.TemporaryDirectory() as directory, patch.object(config, 'RUNTIME', Path(directory) / 'runtime'):
            config.RUNTIME.mkdir()
            overrides = config.RUNTIME / 'api-overrides.env'
            overrides.write_text('EXISTING=value\n')
            values = config.settings()
            for key in values:
                if key.endswith('_HOST_PATH'):
                    values[key] = str(Path(directory) / key)
            config.prepare(values, include_portal=False)
            self.assertEqual(overrides.read_text(), 'EXISTING=value\n')
            self.assertTrue((config.RUNTIME / 'airflow.env').exists())

    def test_oidc_credentials_upgrade_preserves_all_existing_values(self):
        """기존 DB·Fernet·Airflow client 값을 유지하고 새 키만 추가합니다."""
        with tempfile.TemporaryDirectory() as directory, patch.object(config, 'RUNTIME', Path(directory)):
            original = config.credentials(create=True)
            old = {key: value for key, value in original.items() if not key.startswith('HEADLAMP_')}
            path = config.RUNTIME / 'credentials.env'
            config.write_env(path, old)
            before = path.read_bytes()
            self.assertTrue(config.credentials()['HEADLAMP_OIDC_CLIENT_SECRET'])
            self.assertEqual(path.read_bytes(), before)
            upgraded = config.credentials(create=True)
            self.assertEqual({key: upgraded[key] for key in old}, old)
            self.assertEqual(config.credentials(create=True), upgraded)

    def test_apiserver_oidc_merge_is_idempotent_and_rejects_other_contract(self):
        """로컬 인증은 반복 적용 가능하며 다른 issuer·구조화된 인증 설정은 거부합니다."""
        import copy
        with patch.object(sys, 'path', [str(ROOT / 'local/shared/scripts'), *sys.path]):
            from k8s_platform import headlamp
        source = {'spec': {'containers': [{'name': 'kube-apiserver', 'command': ['kube-apiserver'],
                                           'volumeMounts': [{'name': 'existing', 'mountPath': '/existing'}]}],
                           'volumes': [{'name': 'existing', 'hostPath': {'path': '/existing'}}]}}
        merged = headlamp.apiserver_manifest(copy.deepcopy(source))
        self.assertEqual(headlamp.apiserver_manifest(copy.deepcopy(merged)), merged)
        self.assertEqual(merged['spec']['volumes'][0], source['spec']['volumes'][0])
        self.assertIn('--oidc-groups-prefix=headlamp:', merged['spec']['containers'][0]['command'])
        for flag in ('--oidc-issuer-url=https://other.test/realms/other', '--authentication-config=/other'):
            other = copy.deepcopy(source)
            other['spec']['containers'][0]['command'].append(flag)
            with self.assertRaises(ValueError):
                headlamp.apiserver_manifest(other)

    def test_invalid_credentials_are_rejected_without_writing_upgrade(self):
        """기존 키 오류가 있으면 새 OIDC 키 추가도 파일에 기록하지 않습니다."""
        with tempfile.TemporaryDirectory() as directory, patch.object(config, 'RUNTIME', Path(directory)):
            original = config.credentials(create=True)
            original.pop('HEADLAMP_OIDC_CLIENT_SECRET')
            original['UNKNOWN_KEY'] = 'existing-value'
            path = config.RUNTIME / 'credentials.env'
            config.write_env(path, original)
            before = path.read_bytes()
            with self.assertRaises(ValueError):
                config.credentials(create=True)
            self.assertEqual(path.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
