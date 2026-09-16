"""Keycloak 전용 배포의 Secret 보존과 앱별 실행 범위를 검사한다."""

import base64
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from test_server_up import controller, load, worker

keycloak = load('keycloak_up', 'deploy/keycloak/scripts/up.py')
REAL_RUN = keycloak.run


class KeycloakTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.certs = Path(self.directory.name)
        (self.certs / 'keycloak-fullchain.crt').write_text('certificate')
        (self.certs / 'keycloak.key').write_text('private-key')
        self.settings = dict(zip(keycloak.KEYS, ['db-password', 'admin', 'admin-password', 'https://sso.test']))
        self.calls = []
        self.secrets = {}
        self.pvc = ''
        self.live = None
        self.public_matches = True
        self.source = [controller(), {'apiVersion': 'networking.k8s.io/v1', 'kind': 'Ingress',
                                      'metadata': {'name': 'keycloak'}, 'spec': {'rules': [{'host': 'sso.test'}]}}]
        self.nodes = [worker('worker', '192.0.2.10'), worker('second-worker', '192.0.2.20')]
        self.addCleanup(patch.stopall)
        patch.object(keycloak, 'read_settings', return_value=self.settings).start()
        patch.object(keycloak, 'run', side_effect=self.fake_run).start()
        patch.object(keycloak.server, 'render_json', side_effect=lambda *args: deepcopy(self.source)).start()

    def fake_run(self, args, **kwargs):
        args = list(map(str, args))
        self.calls.append((args, kwargs))
        if args[0] == 'openssl':
            if '-checkhost' in args:
                return 'Hostname sso.test does match certificate'
            if '-pubkey' in args:
                return 'public-key'
            if '-pubout' in args:
                return 'public-key' if self.public_matches else 'wrong-key'
            return ''
        if 'get' in args:
            if 'secret' in args:
                secret = self.secrets.get(args[args.index('secret') + 1])
                return json.dumps(secret) if secret else ''
            if 'pvc' in args:
                return self.pvc
            if 'deployment' in args:
                return json.dumps(self.live) if self.live else ''
            if 'nodes' in args:
                return json.dumps({'items': self.nodes})
            if 'pods' in args:
                return json.dumps({'items': []})
        return ''

    def start(self, **kwargs):
        keycloak.start('test-context', Path('/env'), self.certs, **kwargs)

    def mutations(self):
        return [(args, kwargs) for args, kwargs in self.calls if 'apply' in args or 'create' in args]

    def existing(self):
        for name, values, kind in [('keycloak-runtime', self.settings, 'Opaque'),
                                   ('keycloak-tls', {'tls.crt': 'certificate', 'tls.key': 'private-key'}, 'kubernetes.io/tls')]:
            self.secrets[name] = {'type': kind, 'data': {key: base64.b64encode(value.encode()).decode() for key, value in values.items()}}
        self.live = controller('etch-sso,airflow,tailwind-internal')
        self.pvc = 'persistentvolumeclaim/keycloak-postgres-data'

    def test_fresh_install_creates_secrets_before_stack_and_never_deletes(self):
        self.start()
        writes = self.mutations()
        self.assertEqual([json.loads(kw['data'])['kind'] for _, kw in writes], ['Namespace', 'Secret', 'Secret', 'List'])
        self.assertTrue(all('create' in args and kw['sensitive'] for args, kw in writes[1:3]))
        for args, _ in self.calls:
            if args[0] == 'kubectl':
                self.assertEqual(args[1:3], ['--context', 'test-context'])
            self.assertNotIn('delete', args)
            self.assertFalse(any('airflow' in arg for arg in args))

    def test_reapply_preserves_secrets_namespaces_and_vip(self):
        self.existing()
        self.live = keycloak.routing.place_vip_backends(self.live, self.live, ['192.0.2.10', '192.0.2.20'], self.nodes, [])
        self.start()
        writes = self.mutations()
        self.assertFalse(any('create' in args for args, _ in writes))
        updated = keycloak.routing.controller(json.loads(writes[-1][1]['data'])['items'])
        self.assertEqual(updated['spec']['replicas'], 2)
        args = updated['spec']['template']['spec']['containers'][0]['args']
        self.assertIn(keycloak.routing.PREFIX + 'etch-sso,airflow,tailwind-internal', args)

    def test_credential_mismatch_stops_before_mutation(self):
        self.existing()
        self.secrets['keycloak-runtime']['data']['postgres-password'] = 'ZGlmZmVyZW50'
        with self.assertRaisesRegex(ValueError, '기존 Secret과 입력'):
            self.start()
        self.assertEqual(self.mutations(), [])

    def test_existing_tls_mismatch_is_not_overwritten(self):
        self.existing()
        self.secrets['keycloak-tls']['data']['tls.crt'] = 'ZGlmZmVyZW50'
        with self.assertRaisesRegex(ValueError, 'keycloak-tls'):
            self.start()
        self.assertEqual(self.mutations(), [])

    def test_certificate_mismatch_and_missing_runtime_with_pvc_stop(self):
        self.public_matches = False
        with self.assertRaisesRegex(ValueError, '개인키'):
            self.start()
        self.public_matches = True
        self.pvc = 'existing-pvc'
        with self.assertRaisesRegex(ValueError, '기존 PVC'):
            self.start()
        self.assertEqual(self.mutations(), [])

    def test_check_only_does_not_create_first_install_resources(self):
        self.start(check_only=True)
        self.assertEqual(self.mutations(), [])

    def test_real_certificate_validation_accepts_matching_key_and_rejects_wrong_host(self):
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
                        '-subj', '/CN=sso.test', '-addext', 'subjectAltName=DNS:sso.test',
                        '-keyout', self.certs / 'keycloak.key', '-out', self.certs / 'keycloak-fullchain.crt'],
                       check=True, capture_output=True, timeout=15)
        keycloak.run.side_effect = lambda args, **kwargs: REAL_RUN(args, **kwargs) if args[0] == 'openssl' else self.fake_run(args, **kwargs)
        self.start(check_only=True)
        self.settings['keycloak-public-url'] = 'https://other.test'
        with self.assertRaisesRegex(ValueError, '인증서 도메인'):
            self.start(check_only=True)
        self.assertEqual(self.mutations(), [])

    def test_empty_context_stops_before_any_command(self):
        with self.assertRaisesRegex(ValueError, 'context'):
            keycloak.start('', Path('/env'), self.certs)
        self.assertEqual(self.calls, [])


class InputTests(unittest.TestCase):
    def test_env_is_read_as_data_without_shell_expansion(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'prod.env'
            marker = Path(directory) / 'must-not-exist'
            path.write_text('postgres-password=$(touch ' + str(marker) + ')\n'
                            'bootstrap-admin-username=admin\nbootstrap-admin-password=test-password\n'
                            'keycloak-public-url=https://sso.test\n')
            values = keycloak.read_settings(path)
            self.assertTrue(values['postgres-password'].startswith('$(touch '))
            self.assertFalse(marker.exists())

    def test_keycloak_cli_loads_without_airflow_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in ('deploy/keycloak/scripts/up.py', 'deploy/shared/scripts/server-up.py', 'deploy/shared/ingress/routing.py'):
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(keycloak.ROOT / relative, target)
            result = subprocess.run(['python3', root / 'deploy/keycloak/scripts/up.py', '--help'], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((root / 'deploy/airflow').exists())


if __name__ == '__main__':
    unittest.main()
