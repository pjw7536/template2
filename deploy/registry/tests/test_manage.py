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
    def test_render_pins_node_storage_and_http_ingress(self):
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
        self.assertEqual(ingress['metadata']['annotations']['traefik.ingress.kubernetes.io/router.entrypoints'], 'web')
        self.assertNotIn('tls', ingress['spec'])
        self.assertEqual(ingress['spec']['rules'][0]['host'], 'registry.etch.samsungds.net')
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
        for key, value in (('REGISTRY_HOST', 'http://registry.etch.samsungds.net'),
                           ('REGISTRY_HOST', 'registry.etch.samsungds.net:5000'),
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


if __name__ == '__main__':
    unittest.main()
