"""사내 이미지 저장소의 입력 계약·렌더 결과·데이터 보존 검사를 검증한다."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/manage.py'
spec = importlib.util.spec_from_file_location('registry_manage', SCRIPT)
manage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manage)


def settings(**changes):
    """저장소 기본 env에 테스트용 변경만 적용한다."""
    values = manage.settings(manage.BASE / 'env/k8s.env')
    values.update(changes)
    return values


def write_env(values):
    """검사 대상 env를 임시 파일로 기록한다."""
    handle = tempfile.NamedTemporaryFile('w', suffix='.env', delete=False)
    handle.write(''.join(f'{key}={value}\n' for key, value in values.items()))
    handle.close()
    return Path(handle.name)


class RegistryTests(unittest.TestCase):
    def test_render_pins_node_storage_and_https_ingress(self):
        values = settings(IMAGE_PULL_SECRET='mirror-login')
        items = manage.manifests(values)
        kinds = {item['kind']: item for item in items}
        self.assertEqual(kinds['PersistentVolume']['spec']['local']['path'], '/appdata/registry')
        self.assertEqual(kinds['PersistentVolume']['spec']['persistentVolumeReclaimPolicy'], 'Retain')
        pod = kinds['Deployment']['spec']['template']['spec']
        self.assertEqual(pod['nodeSelector'], {'kubernetes.io/hostname': 'khplanew01'})
        self.assertEqual(pod['imagePullSecrets'], [{'name': 'mirror-login'}])
        self.assertEqual(pod['containers'][0]['image'], values['REGISTRY_IMAGE'])
        ingress = kinds['Ingress']
        annotations = ingress['metadata']['annotations']
        self.assertEqual(annotations['traefik.ingress.kubernetes.io/router.entrypoints'], 'websecure')
        self.assertEqual(annotations['traefik.ingress.kubernetes.io/router.tls'], 'true')
        self.assertNotIn('tls', ingress['spec'])
        self.assertEqual(ingress['spec']['rules'][0]['host'], 'store.etch.samsungds.net')
        self.assertTrue(all(item['metadata'].get('namespace') == 'registry'
                            for item in items if item['kind'] != 'PersistentVolume'))
        self.assertNotIn('__', json.dumps(items))

    def test_zot_config_allows_anonymous_pull_and_authenticated_push(self):
        stack = json.loads((manage.BASE / 'k8s/stack.json').read_text())
        config = json.loads(next(item for item in stack['items'] if item['kind'] == 'ConfigMap')['data']['config.json'])
        policy = config['http']['accessControl']['repositories']['**']
        self.assertEqual(policy['anonymousPolicy'], ['read'])
        self.assertIn('create', policy['defaultPolicy'])
        self.assertEqual(config['http']['auth']['htpasswd']['path'], '/etc/zot/auth/htpasswd')
        self.assertEqual(config['storage']['rootDirectory'], '/var/lib/registry')

    def test_settings_reject_invalid_inputs(self):
        for key, value in (('REGISTRY_HOST', 'https://store.etch.samsungds.net'),
                           ('REGISTRY_HOST', 'store.etch.samsungds.net:5000'),
                           ('REGISTRY_IMAGE', 'mirror.test/zot:latest'),
                           ('REGISTRY_IMAGE', 'mirror.test/zot'),
                           ('DATA_HOST_PATH', 'relative/registry'),
                           ('STORAGE_SIZE', '100G')):
            path = write_env(settings(**{key: value}))
            self.addCleanup(path.unlink)
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                manage.settings(path)

    def test_existing_volume_must_match_path_and_node(self):
        values = settings()
        current = manage.static_volume(values)
        current['status'] = {'phase': 'Bound'}
        with patch.object(manage, 'run', return_value=json.dumps(current)):
            self.assertIsNone(manage.volume_plan(['kubectl'], values))
        moved = settings(DATA_HOST_PATH='/appdata/other-registry')
        with patch.object(manage, 'run', return_value=json.dumps(current)), self.assertRaises(ValueError):
            manage.volume_plan(['kubectl'], moved)
        with patch.object(manage, 'run', return_value=''):
            self.assertEqual(manage.volume_plan(['kubectl'], values)['metadata']['name'], 'registry-data')

    def test_cluster_operations_stop_before_writes_without_registry_tls(self):
        values = settings(REGISTRY_HOST='zot.example.test')
        for check_only in (True, False):
            with self.subTest(check_only=check_only), \
                    patch.object(manage, 'check_node'), patch.object(manage, 'volume_plan'), \
                    patch.object(manage, 'run', return_value='{}') as run, \
                    patch.object(manage.tls, 'check', side_effect=ValueError('공용 TLS 인증서가 없습니다.')) as check_tls:
                with self.assertRaisesRegex(ValueError, '공용 TLS 인증서가 없습니다'):
                    manage.deploy(values, 'prod', check_only=check_only)
                kube = ['kubectl', '--context', 'prod']
                check_tls.assert_called_once_with(kube, 'zot.example.test', {})
                run.assert_called_once_with([*kube, '-n', 'etch-sso', 'get', 'deployment', 'traefik', '-o', 'json'])

    def test_first_up_creates_namespace_secret_folder_and_recomputes_routing(self):
        values = settings()
        with tempfile.TemporaryDirectory() as directory:
            account = Path(directory) / 'push.env'
            account.write_text('# 계정\nREGISTRY_USER=publisher\nREGISTRY_PASSWORD=push-secret-value\n')
            calls = []

            def run(args, data=None):
                calls.append((args, data))
                if 'create' in args and '-o' in args:
                    return json.dumps({'metadata': {'name': 'registry-storage-prepare-x'}})
                if 'job' in args and 'get' in args:
                    return json.dumps({'status': {'succeeded': 1}})
                return ''

            plans = [(['access-1'], ['patch-1']), (['access-2'], ['patch-2'])]
            with patch.object(manage, 'run', run), patch.object(manage, 'check_node'), \
                    patch.object(manage, 'volume_plan', return_value=manage.static_volume(values)), \
                    patch.object(manage, 'routing_plan', side_effect=plans), \
                    patch.object(manage, 'htpasswd_line', return_value='publisher:$2y$05$hash'), \
                    patch.object(manage, 'connect') as connect, patch.object(manage, 'apply'):
                manage.deploy(values, 'prod', push_env=account)
            created = [json.loads(data) for args, data in calls if 'create' in args and '--dry-run=server' not in args and data]
            kinds = [item['kind'] for item in created]
            self.assertEqual(kinds, ['Namespace', 'Secret', 'Job', 'PersistentVolume'])
            self.assertEqual(created[1]['stringData'], {'htpasswd': 'publisher:$2y$05$hash\n'})
            job = created[2]['spec']['template']['spec']
            self.assertEqual(job['volumes'][0]['hostPath']['path'], '/appdata')
            self.assertIn("prepare '/host/0/registry' 1000 1000 0750", job['containers'][0]['command'][2])
            # rollout 대기 뒤 다시 계산한 패치를 적용한다.
            connect.assert_called_once_with(['kubectl', '--context', 'prod'], ['access-2'], ['patch-2'])

    def test_existing_secret_and_volume_are_left_untouched(self):
        values = settings()

        def run(args, data=None):
            if 'namespace' in args:
                return 'namespace/registry'
            if 'secret' in args:
                return 'secret/registry-htpasswd'
            return ''

        calls = []
        recorder = lambda args, data=None: calls.append(args) or run(args, data)
        with patch.object(manage, 'run', recorder), patch.object(manage, 'check_node'), \
                patch.object(manage, 'volume_plan', return_value=None), \
                patch.object(manage, 'routing_plan', return_value=([], [])), \
                patch.object(manage, 'connect'), patch.object(manage, 'apply'):
            manage.deploy(values, 'prod', push_env=None)
        self.assertFalse(any('create' in args for args in calls))

    def test_push_account_rejects_placeholder_and_extra_keys(self):
        for content in ('REGISTRY_USER=publisher\nREGISTRY_PASSWORD=replace-me\n',
                        'REGISTRY_USER=publisher\nREGISTRY_PASSWORD=x\nOTHER=1\n', 'REGISTRY_USER=publisher\n'):
            path = write_env({})
            path.write_text(content)
            self.addCleanup(path.unlink)
            with self.subTest(content=content), self.assertRaises(ValueError):
                manage.push_account(path)

    def test_rotate_account_replaces_secret_and_restarts_without_touching_storage(self):
        with tempfile.TemporaryDirectory() as directory:
            account = Path(directory) / 'new.env'
            account.write_text('REGISTRY_USER=builder\nREGISTRY_PASSWORD=new-secret-value\n')
            calls, applied = [], []

            def run(args, data=None):
                calls.append(args)
                return 'deployment.apps/registry' if 'get' in args else ''

            with patch.object(manage, 'run', run), patch.object(manage, 'htpasswd_line', return_value='builder:$2y$05$new'), \
                    patch.object(manage, 'apply', side_effect=lambda kube, items, dry_run=False: applied.extend(items)):
                manage.rotate_account('prod', account)
            self.assertEqual(applied[0]['stringData'], {'htpasswd': 'builder:$2y$05$new\n'})
            self.assertTrue(any('restart' in call for call in calls))
            self.assertFalse(any('delete' in call or 'pv' in call or 'pvc' in call for call in calls))
            with patch.object(manage, 'run', return_value=''), self.assertRaisesRegex(ValueError, '설치돼 있지 않습니다'):
                manage.rotate_account('prod', account)


if __name__ == '__main__':
    unittest.main()
