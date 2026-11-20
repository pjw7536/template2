"""SSH 없이 Kubernetes API로 노드 명령을 실행하는 도구의 계약을 검증한다."""

import base64
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'deploy/shared/scripts'))

import node_exec  # noqa: E402

SETTINGS = {'NODE_EXEC_IMAGE': 'mirror/busybox:1', 'NODE_EXEC_NAMESPACE': 'kube-system'}


class FakeCluster:
    """kubectl 호출을 기록하고 Job 상태를 차례로 돌려준다."""

    def __init__(self, states, node=True, logs='node-a\n0\n', pods=None, errors=0):
        self.calls, self.states, self.node, self.logs = [], list(states), node, logs
        self.pods, self.errors = pods or [], errors
        self.created = None

    def __call__(self, args, data=None):
        self.calls.append(list(args))
        if 'node' in args and 'get' in args:
            return 'node/node-a\n' if self.node else ''
        if 'create' in args:
            self.created = json.loads(data)
            return json.dumps({'metadata': {'name': 'node-exec-abc'}})
        if 'job' in args and 'get' in args:
            if self.errors:
                self.errors -= 1
                raise node_exec.NodeError('connection refused')
            return json.dumps({'status': self.states.pop(0) if len(self.states) > 1 else self.states[0]})
        if 'pods' in args:
            return json.dumps({'items': self.pods})
        if 'logs' in args:
            return self.logs
        raise AssertionError(args)


class ScriptTests(unittest.TestCase):
    def test_command_and_script_run_after_copies_and_stop_on_first_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'ca.pem'
            source.write_bytes(b'CERT\n')
            block = Path(directory) / 'block.sh'
            block.write_text('echo one\necho "$HOME" \'quoted\'\n')
            script = node_exec.build_script('echo last', str(block), [f'{source}:/etc/kubernetes/oidc/ca.pem'])
        self.assertTrue(script.startswith('set -e\n'))
        copy, body, last = script.index('base64 -d'), script.index('echo one'), script.index('echo last')
        self.assertLess(copy, body)
        self.assertLess(body, last)
        self.assertIn(base64.b64encode(b'CERT\n').decode(), script)
        # 이미 있는 폴더(/tmp 등)의 권한을 바꾸지 않도록 mkdir -p만 쓴다.
        self.assertIn("mkdir -p '/etc/kubernetes/oidc'", script)
        self.assertNotIn('install -d', script)
        # 블록의 `$`와 따옴표는 그대로 전달된다.
        self.assertIn('echo "$HOME" \'quoted\'', script)

    def test_rejects_empty_request_bad_copy_target_and_large_files(self):
        with self.assertRaisesRegex(node_exec.NodeError, '하나 이상'):
            node_exec.build_script()
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'file'
            source.write_bytes(b'x')
            for target in ('relative/path', '/etc/../root/x', '/toplevel'):
                with self.subTest(target=target), self.assertRaisesRegex(node_exec.NodeError, '절대 경로'):
                    node_exec.build_script(copies=[f'{source}:{target}'])
            with self.assertRaisesRegex(node_exec.NodeError, '형식'):
                node_exec.build_script(copies=[str(source)])
            source.write_bytes(b'x' * (node_exec.MAX_COPY_BYTES + 1))
            with self.assertRaisesRegex(node_exec.NodeError, 'KiB 이하'):
                node_exec.build_script(copies=[f'{source}:/etc/demo/file'])


class JobTests(unittest.TestCase):
    def test_job_is_pinned_to_the_node_and_enters_host_namespaces(self):
        job = node_exec.job('node-a', 'set -e\nhostname\n', 'mirror/busybox:1', 'kube-system', 300)
        pod = job['spec']['template']['spec']
        self.assertEqual(pod['nodeName'], 'node-a')
        self.assertTrue(pod['hostPID'] and pod['hostNetwork'])
        self.assertEqual(pod['tolerations'], [{'operator': 'Exists'}])
        self.assertEqual(pod['restartPolicy'], 'Never')
        container = pod['containers'][0]
        self.assertTrue(container['securityContext']['privileged'])
        # 스크립트는 셸 코드에 끼워 넣지 않고 인자 하나로 전달한다.
        self.assertEqual(container['command'][:2], ['/bin/sh', '-c'])
        self.assertEqual(container['command'][3], 'set -e\nhostname\n')
        self.assertIn('nsenter -t 1', container['command'][2])
        self.assertIn('chroot /host', container['command'][2])
        self.assertEqual(pod['volumes'][0]['hostPath'], {'path': '/'})
        self.assertEqual((job['spec']['backoffLimit'], job['spec']['activeDeadlineSeconds'], job['spec']['ttlSecondsAfterFinished']), (0, 300, 600))
        self.assertEqual(job['metadata']['namespace'], 'kube-system')


class ExecuteTests(unittest.TestCase):
    def test_success_returns_output_and_never_deletes(self):
        cluster = FakeCluster([{}, {'succeeded': 1}])
        succeeded, output = node_exec.execute('node-a', 'hostname\n', 'ctx', SETTINGS, kube=cluster, sleep=lambda _: None)
        self.assertTrue(succeeded)
        self.assertEqual(output, 'node-a\n0\n')
        self.assertEqual(cluster.created['spec']['template']['spec']['containers'][0]['image'], 'mirror/busybox:1')
        self.assertFalse(any('delete' in call for call in cluster.calls))

    def test_failed_command_still_returns_its_output(self):
        cluster = FakeCluster([{'failed': 1}], logs='bash: line 2: nosuch: command not found\n')
        succeeded, output = node_exec.execute('node-a', 'nosuch\n', 'ctx', SETTINGS, kube=cluster, sleep=lambda _: None)
        self.assertFalse(succeeded)
        self.assertIn('command not found', output)

    def test_unknown_node_stops_before_creating_anything(self):
        cluster = FakeCluster([{}], node=False)
        with self.assertRaisesRegex(node_exec.NodeError, '클러스터에 없는 노드'):
            node_exec.execute('new-node', 'true\n', 'ctx', SETTINGS, kube=cluster, sleep=lambda _: None)
        self.assertIsNone(cluster.created)

    def test_api_outage_during_the_command_is_retried(self):
        # 노드 명령이 API server를 다시 시작하면 조회가 잠시 실패한다.
        cluster = FakeCluster([{'succeeded': 1}], errors=3)
        succeeded, _ = node_exec.execute('node-a', 'true\n', 'ctx', SETTINGS, kube=cluster, sleep=lambda _: None)
        self.assertTrue(succeeded)

    def test_image_pull_failure_is_reported_at_once(self):
        pods = [{'status': {'containerStatuses': [{'state': {'waiting': {'reason': 'ImagePullBackOff'}}}]}}]
        cluster = FakeCluster([{}], pods=pods)
        with self.assertRaisesRegex(node_exec.NodeError, 'NODE_EXEC_IMAGE'):
            node_exec.execute('node-a', 'true\n', 'ctx', SETTINGS, kube=cluster, sleep=lambda _: None)

    def test_timeout_is_an_error(self):
        cluster = FakeCluster([{}])
        with self.assertRaisesRegex(node_exec.NodeError, '시간 초과'):
            node_exec.wait(cluster, 'kube-system', 'node-exec-abc', 9, interval=3, sleep=lambda _: None)


class CommandLineTests(unittest.TestCase):
    def test_settings_file_names_an_image_and_namespace_and_environment_overrides(self):
        values = node_exec.read_settings(environ={})
        self.assertTrue(values['NODE_EXEC_IMAGE'] and values['NODE_EXEC_NAMESPACE'])
        self.assertEqual(node_exec.read_settings(environ={'NODE_EXEC_IMAGE': 'other/image:1'})['NODE_EXEC_IMAGE'], 'other/image:1')

    def test_exit_code_and_last_line_report_the_result(self):
        for succeeded, code, word in ((True, 0, '완료'), (False, 1, '실패')):
            printed = []
            with patch.object(node_exec, 'execute', return_value=(succeeded, 'output line')), \
                    patch('builtins.print', side_effect=lambda *a, **k: printed.append(a[0])), patch('sys.stdout.write'):
                self.assertEqual(node_exec.main(['node-a', '--context', 'ctx', '--command', 'true']), code)
            self.assertEqual(printed[-1], f'노드 명령 {word}: node-a')

    def test_missing_context_or_request_never_reaches_the_cluster(self):
        with patch.object(node_exec, 'execute') as execute, patch('builtins.print'), patch.dict('os.environ', {'KUBE_CONTEXT': ''}):
            self.assertEqual(node_exec.main(['node-a', '--command', 'true']), 1)
            self.assertEqual(node_exec.main(['node-a', '--context', 'ctx']), 1)
        execute.assert_not_called()


if __name__ == '__main__':
    unittest.main()
