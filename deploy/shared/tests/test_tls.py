"""공용 인증서의 실제 PEM 검사·도메인 보존·갱신·오류 비노출을 검증한다."""

import base64
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('shared_tls', ROOT / 'deploy/shared/ingress/tls.py')
tls = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tls)
REAL_RUN = tls.run


def encode(value):
    """Secret 테스트 입력을 Kubernetes 인코딩으로 변환한다."""
    return base64.b64encode(value.encode()).decode()


class TlsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        cls.files = {}
        for host in ('portal.test', 'sso.test'):
            cert, key = [Path(cls.directory.name) / f'{host}.{suffix}' for suffix in ('crt', 'key')]
            subprocess.run(['openssl', 'req', '-x509', '-newkey', 'ec', '-pkeyopt', 'ec_paramgen_curve:P-256',
                            '-nodes', '-days', '1', '-subj', f'/CN={host}', '-addext', f'subjectAltName=DNS:{host}',
                            '-keyout', key, '-out', cert], check=True, capture_output=True)
            cls.files[host] = (cert, key)

    def setUp(self):
        self.kube = ['kubectl', '--context', 'explicit-context']
        self.current = None
        self.original = None
        self.calls = []
        self.controller_exists = True
        self.addCleanup(patch.stopall)
        patch.object(tls, 'run', side_effect=self.fake_run).start()

    def fake_run(self, args, data=None):
        self.calls.append((args, data))
        if args[0] == 'openssl':
            return REAL_RUN(args, data)
        self.assertEqual(args[:3], self.kube)
        if 'get' in args and 'secret' in args:
            secret = self.current if tls.SECRET in args else self.original
            return json.dumps(secret) if secret else ''
        if 'get' in args and 'deployment' in args:
            return 'deployment.apps/traefik' if self.controller_exists else ''
        return ''

    def register(self, host):
        cert, key = self.files[host]
        return tls.prepare(self.kube, host, cert, key)

    def test_two_domains_share_one_store_without_copying_source_metadata(self):
        first = self.register('portal.test')
        first['metadata'].update(resourceVersion='7', labels={'owner': 'keep'})
        self.current = first
        cert, key = self.files['sso.test']
        self.original = {'type': 'kubernetes.io/tls', 'metadata': {'uid': 'do-not-copy'},
                         'data': {'tls.crt': encode(cert.read_text()), 'tls.key': encode(key.read_text())}}
        updated = tls.prepare(self.kube, 'sso.test', source='legacy/sso-tls')
        self.assertEqual(updated['metadata'], first['metadata'])
        self.assertEqual(updated['data']['portal.test.key'], first['data']['portal.test.key'])
        self.assertEqual(set(updated['data']), {'portal.test.crt', 'portal.test.key', 'sso.test.crt', 'sso.test.key', 'tls.yaml'})
        config = json.loads(tls.decode(updated['data']['tls.yaml']))
        self.assertEqual(len(config['tls']['certificates']), 2)
        tls.save(self.kube, updated)
        writes = [(args, data) for args, data in self.calls if 'replace' in args]
        self.assertEqual(len(writes), 1)
        self.assertEqual(json.loads(writes[0][1])['metadata']['resourceVersion'], '7')
        self.assertTrue(any('restart' in args for args, _ in self.calls))
        self.assertFalse(any('delete' in args for args, _ in self.calls))

    def test_existing_common_certificate_needs_no_namespace_copy(self):
        self.current = self.register('portal.test')
        self.current['metadata']['resourceVersion'] = '1'
        self.calls.clear()
        self.assertIsNone(tls.prepare(self.kube, 'portal.test'))
        self.assertIsNone(self.register('portal.test'))
        self.assertTrue(all(args[args.index('-n') + 1] == 'etch-sso'
                            for args, _ in self.calls if args[0] == 'kubectl'))

    def test_missing_certificate_stops_without_writes(self):
        with self.assertRaisesRegex(ValueError, 'ingress-tls-up'):
            tls.prepare(self.kube, 'portal.test')
        self.assertFalse(any('create' in args or 'replace' in args for args, _ in self.calls))

    def test_real_hostname_and_private_key_mismatch_stop_registration(self):
        cert, key = self.files['portal.test']
        with self.assertRaisesRegex(ValueError, '공개 도메인'):
            tls.prepare(self.kube, 'sso.test', cert, key)
        with self.assertRaisesRegex(ValueError, '개인키.*일치'):
            tls.prepare(self.kube, 'portal.test', cert, self.files['sso.test'][1])
        self.assertFalse(any('create' in args or 'replace' in args for args, _ in self.calls))

    def test_expired_certificate_is_rejected(self):
        cert, key = self.files['portal.test']
        expired = Path(self.directory.name) / 'expired.crt'
        subprocess.run(['openssl', 'x509', '-in', cert, '-signkey', key, '-days', '-1', '-out', expired],
                       check=True, capture_output=True)
        with self.assertRaisesRegex(ValueError, '공용 TLS 처리 실패'):
            tls.prepare(self.kube, 'portal.test', expired, key)

    def test_configuration_mismatch_and_missing_key_are_rejected(self):
        self.current = self.register('portal.test')
        self.current['data']['tls.yaml'] = encode('{}')
        with self.assertRaisesRegex(ValueError, 'PEM 목록'):
            tls.prepare(self.kube, 'portal.test')
        del self.current['data']['portal.test.key']
        with self.assertRaisesRegex(ValueError, '공용 TLS 인증서'):
            tls.prepare(self.kube, 'portal.test')

    def test_file_provider_mount_must_include_common_secret(self):
        pod = {'containers': [{'name': 'traefik', 'args': [f'--providers.file.directory={tls.DIRECTORY}'],
                              'volumeMounts': [{'name': 'dynamic', 'mountPath': tls.DIRECTORY}]}],
               'volumes': [{'name': 'dynamic', 'projected': {'sources': [{'secret': {'name': tls.SECRET}}]}}]}
        current = {'spec': {'template': {'spec': pod}}}
        tls.check_mount(current)
        broken = deepcopy(current)
        broken['spec']['template']['spec']['volumes'][0]['projected']['sources'] = []
        with self.assertRaisesRegex(ValueError, 'ingress-up'):
            tls.check_mount(broken)
        pod['containers'][0]['volumeMounts'][0]['subPath'] = 'tls.yaml'
        with self.assertRaisesRegex(ValueError, 'ingress-up'):
            tls.check_mount(current)

    def test_first_registration_before_controller_does_not_require_rollout(self):
        self.controller_exists = False
        pending = self.register('portal.test')
        tls.save(self.kube, pending)
        creates = [json.loads(data) for args, data in self.calls if 'create' in args]
        self.assertEqual(len(creates), 1)
        self.assertEqual(creates[0]['metadata'], {'namespace': 'etch-sso', 'name': 'traefik-tls'})
        self.assertFalse(any('rollout' in args for args, _ in self.calls))

    def test_conflict_error_never_includes_secret_payload(self):
        pending = self.register('portal.test')
        with patch.object(tls, 'run', side_effect=REAL_RUN), patch.object(tls.subprocess, 'run', return_value=
                subprocess.CompletedProcess([], 1, '', 'conflict: PRIVATE KEY confidential')):
            with self.assertRaisesRegex(ValueError, '동시 변경') as raised:
                tls.save(self.kube, pending)
        self.assertNotIn('PRIVATE KEY', str(raised.exception))
        self.assertNotIn('confidential', str(raised.exception))

    def test_retry_of_same_certificate_restarts_controller_after_failed_rollout(self):
        tls.save(self.kube, None)
        self.assertTrue(any('restart' in args for args, _ in self.calls))
        self.assertFalse(any('create' in args or 'replace' in args for args, _ in self.calls))
