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
        self.nodes = [worker()]
        self.secret = ''
        self.calls = []
        self.runner = patch.object(ftp, 'run', side_effect=self.run_command)
        self.runner.start()
        self.addCleanup(self.runner.stop)

    def run_command(self, args, **kwargs):
        self.calls.append((args, kwargs))
        if 'kustomize' in args:
            return 'rendered-stack'
        if 'get' in args and 'nodes' in args:
            return json.dumps({'items': self.nodes})
        if 'get' in args and 'secret' in args:
            return self.secret
        return ''

    def start(self, **kwargs):
        ftp.start('test-context', 'worker-a', str(self.credentials), **kwargs)

    def writes(self):
        return [(args, kw) for args, kw in self.calls
                if any(verb in args for verb in ('apply', 'create', 'label', 'delete'))]

    def test_check_only_never_mutates_cluster(self):
        self.start(check_only=True)
        self.assertEqual(self.writes(), [])

    def test_new_install_orders_secret_before_labels_and_stack(self):
        self.start()
        writes = self.writes()
        self.assertEqual([args[3] for args, _ in writes], ['apply', 'create', 'label', 'apply'])
        self.assertEqual(json.loads(writes[1][1]['data'])['metadata']['namespace'], 'etch-ftp')
        self.assertTrue(writes[1][1]['sensitive'])
        self.assertEqual(writes[-1][1]['data'], 'rendered-stack')
        for args, _ in self.calls:
            if 'kustomize' not in args:
                self.assertEqual(args[:3], ['kubectl', '--context', 'test-context'])
            self.assertNotIn('test-password', ' '.join(map(str, args)))

    def test_existing_matching_secret_is_not_written(self):
        self.secret = json.dumps({'data': {key: base64.b64encode(value.encode()).decode()
                                          for key, value in ftp.read_credentials(self.credentials).items()}})
        self.start()
        self.assertFalse(any('create' in args for args, _ in self.calls))

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
