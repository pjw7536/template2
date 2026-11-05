"""FTP 배포의 대상 제한·계정 보존·검사 전용 실행을 검증한다."""

import base64
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[2] / 'ftp/scripts/up.py'
spec = importlib.util.spec_from_file_location('ftp_up', SCRIPT)
ftp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ftp)


def worker(name='worker-a', labeled=False):
    """배치 가능한 IPv4 Linux Worker를 만든다."""
    labels = {'kubernetes.io/os': 'linux'}
    if labeled:
        labels[ftp.LABEL] = 'true'
    return {'metadata': {'name': name, 'labels': labels}, 'spec': {},
            'status': {'conditions': [{'type': 'Ready', 'status': 'True'}],
                       'addresses': [{'type': 'InternalIP', 'address': '192.0.2.10'}]}}


class FtpTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.credentials = Path(self.directory.name) / 'ftp.env'
        self.credentials.write_text('FTP_USER=test-user\nFTP_PASS=test-password\n')
        self.credentials.chmod(0o600)
        self.env = Path(self.directory.name) / 'prod.env'
        self.image = 'registry.example.test/mirror/fauria/vsftpd@sha256:' + 'a' * 64
        self.env.write_text(f'FTP_IMAGE={self.image}\nIMAGE_PULL_SECRET=\n')
        self.nodes = [worker()]
        self.secret = ''
        self.namespace = ''
        self.source = [
            {'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {
                'name': 'etch-ftp', 'labels': {'operator.test/policy': 'initial'}}},
            {'apiVersion': 'apps/v1', 'kind': 'DaemonSet', 'metadata': {'name': 'ftp', 'namespace': 'etch-ftp'},
             'spec': {'template': {'spec': {'containers': [{'name': 'ftp', 'image': self.image}]}}}},
        ]
        self.calls = []
        self.runner = patch.object(ftp, 'run', side_effect=self.run_command)
        self.runner.start()
        self.addCleanup(self.runner.stop)

    def run_command(self, args, **kwargs):
        self.calls.append((args, kwargs))
        if 'kustomize' in args:
            return 'rendered-stack'
        if 'create' in args and '--dry-run=client' in args:
            return json.dumps({'kind': 'List', 'items': self.source})
        if 'get' in args and 'namespace' in args:
            return self.namespace
        if 'get' in args and 'nodes' in args:
            return json.dumps({'items': self.nodes})
        if 'get' in args and 'secret' in args:
            return self.secret
        return ''

    def start(self, **kwargs):
        ftp.start('test-context', 'worker-a', str(self.credentials), env_file=self.env, **kwargs)

    def writes(self):
        return [(args, kw) for args, kw in self.calls
                if '--dry-run=client' not in args and any(verb in args for verb in ('apply', 'create', 'label', 'delete'))]

    def test_check_only_never_mutates_cluster(self):
        self.start(check_only=True)
        self.assertEqual(self.writes(), [])

    def test_image_from_env_replaces_public_image_in_applied_stack(self):
        """공개 원본이 렌더되어도 실제 적용은 지정한 미러 이미지를 사용한다."""
        self.source[1]['spec']['template']['spec']['containers'][0]['image'] = 'fauria/vsftpd:old'
        self.start()
        applied = json.loads(self.writes()[-1][1]['data'])['items'][0]
        self.assertEqual(applied['spec']['template']['spec']['containers'][0]['image'], self.image)

    def test_default_env_uses_mirror_and_preserves_base_digest(self):
        """env를 따로 지정하지 않아도 운영 미러를 적용하고 기존 digest를 유지한다."""
        ftp.start('test-context', 'worker-a', str(self.credentials))
        applied = json.loads(self.writes()[-1][1]['data'])['items'][0]
        image = applied['spec']['template']['spec']['containers'][0]['image']
        base = (ftp.BASE / 'k8s/stack.yaml').read_text()
        self.assertNotEqual(image.split('/')[0], 'fauria')
        self.assertIn('proxy-docker-registry-1.docker.io/fauria/vsftpd@', image)
        self.assertIn(image.split('@')[1], base)

    def test_pull_secret_is_checked_and_applied(self):
        self.env.write_text(f'FTP_IMAGE={self.image}\nIMAGE_PULL_SECRET=registry-auth\n')
        self.start()
        lookup = next(index for index, (args, _) in enumerate(self.calls)
                      if 'get' in args and 'registry-auth' in args)
        first_write = next(index for index, call in enumerate(self.calls) if call in self.writes())
        self.assertLess(lookup, first_write)
        applied = json.loads(self.writes()[-1][1]['data'])['items'][0]
        self.assertEqual(applied['spec']['template']['spec']['imagePullSecrets'], [{'name': 'registry-auth'}])

    def test_missing_pull_secret_stops_before_any_write(self):
        self.env.write_text(f'FTP_IMAGE={self.image}\nIMAGE_PULL_SECRET=missing-auth\n')
        original = self.run_command

        def missing_secret(args, **kwargs):
            if 'get' in args and 'missing-auth' in args:
                raise ValueError('Secret 처리 실패')
            return original(args, **kwargs)

        self.runner.stop()
        with patch.object(ftp, 'run', side_effect=missing_secret):
            with self.assertRaisesRegex(ValueError, 'Secret 처리 실패'):
                self.start()
        self.assertEqual(self.writes(), [])

    def test_invalid_image_settings_stop_before_commands(self):
        for content in ('FTP_IMAGE=\n', 'FTP_IMAGE=fauria/vsftpd\n',
                        'FTP_IMAGE=fauria/vsftpd:latest\n', 'FTP_IMAGE=fauria/vsftpd@sha256:bad\n',
                        'FTP_IMAGE=https://registry.test/ftp:fixed\n',
                        f'FTP_IMAGE={self.image}\nFTP_IMAGE={self.image}\n',
                        f'FTP_IMAGE={self.image}\nIMAGE_PULL_SECRET=bad/name\n'):
            with self.subTest(content=content):
                self.env.write_text(content)
                with self.assertRaises(ValueError):
                    self.start()
                self.assertEqual(self.calls, [])

    def test_new_install_orders_secret_before_labels_and_stack(self):
        self.start()
        writes = self.writes()
        self.assertEqual([args[3] for args, _ in writes], ['create', 'create', 'label', 'apply'])
        self.assertEqual(json.loads(writes[0][1]['data']), self.source[0])
        self.assertEqual(json.loads(writes[1][1]['data'])['metadata']['namespace'], 'etch-ftp')
        self.assertTrue(writes[1][1]['sensitive'])
        self.assertEqual(json.loads(writes[-1][1]['data'])['items'], self.source[1:])
        for args, _ in self.calls:
            if 'kustomize' not in args:
                self.assertEqual(args[:3], ['kubectl', '--context', 'test-context'])
            self.assertNotIn('test-password', ' '.join(map(str, args)))

    def test_existing_matching_secret_is_not_written(self):
        self.namespace = 'namespace/etch-ftp'
        self.secret = json.dumps({'data': {key: base64.b64encode(value.encode()).decode()
                                          for key, value in ftp.read_credentials(self.credentials).items()}})
        self.start()
        self.assertFalse(any('create' in args and '--dry-run=client' not in args for args, _ in self.calls))

    def test_existing_namespace_is_never_written_or_included_in_stack(self):
        """기존 Namespace에는 쓰지 않고 앱 리소스만 적용해 운영 metadata를 보존합니다."""
        self.namespace = 'namespace/etch-ftp'
        self.start()
        self.assertTrue(any('get' in args and 'namespace' in args for args, _ in self.calls))
        for _, kwargs in self.writes():
            if 'data' not in kwargs:
                continue
            body = json.loads(kwargs['data'])
            self.assertNotEqual(body.get('kind'), 'Namespace')
            self.assertTrue(all(item.get('kind') != 'Namespace' for item in body.get('items', [])))

    def test_secret_mismatch_stops_before_any_write(self):
        self.secret = json.dumps({'data': {'FTP_PASS': 'different'}})
        with self.assertRaisesRegex(ValueError, '기존 FTP Secret'):
            self.start()
        self.assertEqual(self.writes(), [])

    def test_omitted_existing_node_stops_before_any_write(self):
        self.nodes.append(worker('worker-b', labeled=True))
        with self.assertRaisesRegex(ValueError, 'worker-b'):
            self.start()
        self.assertEqual(self.writes(), [])

    def test_unusable_workers_are_rejected(self):
        for problem in ('not-ready', 'cordon', 'taint', 'windows', 'control-plane', 'ipv6'):
            with self.subTest(problem=problem):
                node = worker()
                if problem == 'not-ready':
                    node['status']['conditions'][0]['status'] = 'False'
                elif problem == 'cordon':
                    node['spec']['unschedulable'] = True
                elif problem == 'taint':
                    node['spec']['taints'] = [{'effect': 'NoSchedule'}]
                elif problem == 'windows':
                    node['metadata']['labels']['kubernetes.io/os'] = 'windows'
                elif problem == 'control-plane':
                    node['metadata']['labels']['node-role.kubernetes.io/control-plane'] = ''
                else:
                    node['status']['addresses'][0]['address'] = '2001:db8::1'
                with self.assertRaises(ValueError):
                    ftp.check_nodes([node], ['worker-a'])

    def test_missing_inputs_rejected_without_commands(self):
        for context, nodes, path in (('', 'worker-a', str(self.credentials)),
                                     ('test', '', str(self.credentials)), ('test', 'worker-a', '')):
            with self.assertRaises(ValueError):
                ftp.start(context, nodes, path)
        self.assertEqual(self.calls, [])

    def test_invalid_credentials_rejected_without_exposing_values(self):
        for content in ('FTP_USER=test\nFTP_PASS=secret\\bad', 'FTP_USER=test\nFTP_PASS=',
                        'FTP_USER=test\nFTP_PASS=secret\nFTP_PASS=duplicate',
                        'FTP_USER=bad user\nFTP_PASS=secret'):
            self.credentials.write_text(content)
            with self.assertRaises(ValueError) as caught:
                ftp.read_credentials(self.credentials)
            self.assertNotIn('secret', str(caught.exception))

    def test_world_readable_file_rejected(self):
        self.credentials.chmod(0o644)
        with self.assertRaisesRegex(ValueError, 'chmod 600'):
            ftp.read_credentials(self.credentials)

    def test_sensitive_subprocess_errors_are_redacted(self):
        self.runner.stop()
        result = subprocess.CompletedProcess([], 1, '', 'leaked-password')
        with patch.object(ftp.subprocess, 'run', return_value=result):
            with self.assertRaises(ValueError) as caught:
                ftp.run(['kubectl'], data='secret', sensitive=True)
        self.assertNotIn('leaked-password', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
