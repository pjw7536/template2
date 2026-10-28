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
    def test_default_certificate_directory_uses_shared_site(self):
        with patch('sys.argv', ['up.py', '--context', 'test-context', '--check-only']), \
                patch.object(keycloak, 'start') as start:
            keycloak.main()
        self.assertEqual(start.call_args.args[2], keycloak.BASE.parent / 'shared/certs/etch-sso.samsungds.net')

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.certs = Path(self.directory.name)
        (self.certs / 'fullchain.crt').write_text('certificate')
        (self.certs / 'private.key').write_text('private-key')
        self.settings = dict(zip(keycloak.KEYS, ['db-password', 'admin', 'admin-password', 'https://sso.test']))
        self.calls = []
        self.secrets = {}
        self.pvc = None
        self.pv = None
        self.namespace = None
        self.live = None
        self.pods = []
        self.public_matches = True
        self.source = [{'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {
                            'name': 'etch-sso', 'labels': {'app.kubernetes.io/part-of': 'etch-sso'},
                            'annotations': {'source.test/policy': 'configured'}}},
                       controller(), {'apiVersion': 'networking.k8s.io/v1', 'kind': 'Ingress',
                                      'metadata': {'name': 'keycloak'}, 'spec': {'rules': [{'host': 'sso.test'}]}}]
        self.nodes = [worker('worker', '192.0.2.10'), worker('second-worker', '192.0.2.20')]
        self.addCleanup(patch.stopall)
        patch.object(keycloak, 'read_settings', return_value=self.settings).start()
        patch.object(keycloak, 'run', side_effect=self.fake_run).start()
        patch.object(keycloak.runtime, 'render_json', side_effect=lambda *args: deepcopy(self.source)).start()

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
                return json.dumps(self.pvc) if self.pvc is not None else ''
            if 'pv' in args:
                return json.dumps(self.pv) if self.pv is not None else ''
            if 'namespace' in args:
                return 'namespace/etch-sso' if self.namespace is not None else ''
            if 'deployment' in args:
                return json.dumps(self.live) if self.live else ''
            if 'nodes' in args:
                return json.dumps({'items': self.nodes})
            if 'pods' in args:
                return json.dumps({'items': self.pods})
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
        self.live['metadata']['resourceVersion'] = 'existing-version'
        self.pvc = {'metadata': {'name': 'keycloak-postgres-data', 'namespace': 'etch-sso', 'uid': 'existing-claim'}}
        self.pv = {'spec': {'persistentVolumeReclaimPolicy': 'Retain', 'claimRef': {
            'name': 'keycloak-postgres-data', 'namespace': 'etch-sso', 'uid': 'existing-claim'}},
            'status': {'phase': 'Bound'}}
        self.namespace = {'metadata': {'name': 'etch-sso',
            'labels': {'operator.test/security': 'keep'}, 'annotations': {'operator.test/policy': 'keep'}}}

    def test_fresh_install_creates_secrets_before_stack_and_never_deletes(self):
        self.start()
        writes = self.mutations()
        self.assertEqual([json.loads(kw['data'])['kind'] for _, kw in writes], ['Namespace', 'Secret', 'Secret', 'List'])
        self.assertIn('create', writes[0][0])
        self.assertEqual(json.loads(writes[0][1]['data']), self.source[0])
        self.assertFalse(any(item['kind'] == 'Namespace' for item in json.loads(writes[-1][1]['data'])['items']))
        self.assertTrue(all('create' in args and kw['sensitive'] for args, kw in writes[1:3]))
        for args, _ in self.calls:
            if args[0] == 'kubectl':
                self.assertEqual(args[1:3], ['--context', 'test-context'])
            self.assertNotIn('delete', args)
            self.assertFalse(any('airflow' in arg for arg in args))

    def test_existing_namespace_metadata_is_never_written_even_when_source_contains_namespace(self):
        self.existing()
        before = deepcopy(self.namespace)
        self.start()
        writes = self.mutations()
        self.assertEqual(len(writes), 1)
        stack = json.loads(writes[0][1]['data'])
        self.assertEqual(stack['kind'], 'List')
        self.assertFalse(any(item['kind'] == 'Namespace' for item in stack['items']))
        self.assertEqual(self.namespace, before)
        self.assertTrue(any('get' in args and 'namespace' in args for args, _ in self.calls))

    def test_missing_runtime_with_any_retained_pv_blocks_all_writes_before_namespace_recreation(self):
        for phase in ('Bound', 'Released', 'Available'):
            for check_only in (True, False):
                with self.subTest(phase=phase, check_only=check_only):
                    self.calls.clear()
                    self.pv = {'spec': {'persistentVolumeReclaimPolicy': 'Retain'}, 'status': {'phase': phase}}
                    if phase != 'Available':
                        self.pv['spec']['claimRef'] = {'name': 'keycloak-postgres-data',
                            'namespace': 'etch-sso', 'uid': 'deleted-claim'}
                    with self.assertRaisesRegex(ValueError, '기존 PV'):
                        self.start(check_only=check_only)
                    self.assertEqual(self.mutations(), [])
                    self.assertTrue(any('get' in args and 'pv' in args for args, _ in self.calls))

    def test_restored_runtime_does_not_bypass_released_or_old_claim_recovery(self):
        self.existing()
        for phase, pvc_uid in (('Released', 'existing-claim'), ('Bound', 'new-claim'), ('Available', None)):
            with self.subTest(phase=phase, pvc_uid=pvc_uid):
                self.calls.clear()
                self.pv['status']['phase'] = phase
                self.pvc = {'metadata': {'uid': pvc_uid}} if pvc_uid is not None else None
                with self.assertRaisesRegex(ValueError, '이전 PVC'):
                    self.start()
                self.assertEqual(self.mutations(), [])

    def test_unschedulable_worker_stops_before_mutation(self):
        for state in ({'unschedulable': True}, {'taints': [{'effect': 'NoSchedule'}]},
                      {'taints': [{'effect': 'NoExecute'}]}):
            with self.subTest(state=state):
                self.calls.clear()
                self.nodes[0]['spec'] = state
                with self.assertRaisesRegex(ValueError, 'cordon|taint'):
                    self.start()
                self.assertEqual(self.mutations(), [])

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

    def test_operator_worker_pool_is_preserved_by_check_and_deploy(self):
        """공용 Ingress가 허용한 pool을 Keycloak 재배포에서도 유지한다."""
        self.existing()
        self.live['metadata']['resourceVersion'] = 'operator-version'
        self.live['metadata']['annotations'] = {'operator.test/owner': 'keep'}
        template = self.live['spec']['template']
        template['metadata'] = {'labels': {'operator.test/controller': 'ingress'}}
        placement = template['spec']
        placement['nodeSelector'] = {'operator.test/pool': 'ingress'}
        placement['affinity'] = {'nodeAffinity': {'requiredDuringSchedulingIgnoredDuringExecution': {
            'nodeSelectorTerms': [{'matchExpressions': [{'key': 'operator.test/pool', 'operator': 'In', 'values': ['ingress']}]}]}}}
        placement['tolerations'] = [{'key': 'operator.test/dedicated', 'operator': 'Exists'}]
        for node in self.nodes:
            node['metadata']['labels']['operator.test/pool'] = 'ingress'
        # pool의 다른 Worker가 cordon 상태여도 앱 Worker와 남은 후보가 정상이면 배포한다.
        self.nodes[1]['spec']['unschedulable'] = True
        original = deepcopy(self.live)
        self.start(check_only=True)
        self.assertEqual(self.mutations(), [])
        self.start()
        updated = keycloak.routing.controller(json.loads(self.mutations()[-1][1]['data'])['items'])
        for key in ('nodeSelector', 'affinity', 'tolerations'):
            self.assertEqual(updated['spec']['template']['spec'][key], placement[key])
        self.assertEqual(updated['spec']['template']['metadata']['labels']['operator.test/controller'], 'ingress')
        self.assertEqual(updated['metadata']['resourceVersion'], 'operator-version')
        self.assertEqual(updated['metadata']['annotations'], original['metadata']['annotations'])
        self.assertIn(keycloak.routing.PREFIX + 'etch-sso,airflow,tailwind-internal',
                      updated['spec']['template']['spec']['containers'][0]['args'])
        self.assertEqual(self.live, original)
        self.assertFalse(any('create' in args for args, _ in self.mutations()))

    def test_invalid_recorded_vip_stops_before_any_keycloak_or_secret_write(self):
        """이미 기록된 VIP의 실제 배치 오류를 공통 검사로 차단한다."""
        self.existing()
        self.live = keycloak.routing.place_vip_backends(self.live, self.live,
                           ['192.0.2.10', '192.0.2.20'], self.nodes, [])
        self.live['spec']['replicas'] = 1
        with self.assertRaises(ValueError):
            self.start()
        self.assertEqual(self.mutations(), [])

    def test_worker_pool_port_conflict_stops_before_any_write(self):
        """모든 pool 후보의 80/443이 충돌하면 앱에도 적용하지 않는다."""
        self.existing()
        self.live['spec']['template']['spec']['nodeSelector'] = {'operator.test/pool': 'ingress'}
        for node in self.nodes:
            node['metadata']['labels']['operator.test/pool'] = 'ingress'
            self.pods.append({'metadata': {'name': 'other-proxy', 'namespace': 'other'},
                              'spec': {'nodeName': node['metadata']['name'],
                                       'containers': [{'ports': [{'hostPort': 443}]}]}})
        with self.assertRaises(ValueError):
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
        self.pvc = {'metadata': {'name': 'keycloak-postgres-data', 'uid': 'existing-claim'}}
        with self.assertRaisesRegex(ValueError, '기존 PVC'):
            self.start()
        self.assertEqual(self.mutations(), [])

    def test_check_only_does_not_create_first_install_resources(self):
        self.start(check_only=True)
        self.assertEqual(self.mutations(), [])

    def test_real_certificate_validation_accepts_matching_key_and_rejects_wrong_host(self):
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
                        '-subj', '/CN=sso.test', '-addext', 'subjectAltName=DNS:sso.test',
                        '-keyout', self.certs / 'private.key', '-out', self.certs / 'fullchain.crt'],
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
            for relative in ('deploy/keycloak/scripts/up.py', 'deploy/shared/scripts/runtime.py',
                             'deploy/shared/ingress/routing.py'):
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(keycloak.ROOT / relative, target)
            result = subprocess.run(['python3', root / 'deploy/keycloak/scripts/up.py', '--help'], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((root / 'deploy/airflow').exists())
            self.assertFalse((root / 'deploy/shared/scripts/server-up.py').exists())

    def test_reads_credentials_only_from_selected_env(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'prod.env'
            path.write_text('postgres-password=fixture-db\nbootstrap-admin-username=admin\n'
                            'bootstrap-admin-password=fixture-admin\nkeycloak-public-url=https://sso.test\n')
            path.with_suffix('.secrets.env').write_text('postgres-password=stale-value\n')
            self.assertEqual(keycloak.read_settings(path)['postgres-password'], 'fixture-db')
            path.write_text(path.read_text().replace('postgres-password=fixture-db', 'postgres-password='))
            with self.assertRaises(ValueError):
                keycloak.read_settings(path)


if __name__ == '__main__':
    unittest.main()
