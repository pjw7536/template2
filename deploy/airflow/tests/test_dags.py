"""DAG 폴더 동기화가 같은 이름은 덮어쓰고 폴더에만 있는 파일은 남기며, 임시 Pod를 항상 정리하는지 검증한다."""

import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest

BASE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('airflow_dags', BASE / 'scripts/dags.py')
dags = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dags)
SETTINGS = {'NAMESPACE': 'airflow', 'NODE_NAME': 'worker-a', 'DAGS_HOST_PATH': '/appdata/airflow/dags', 'IMAGE_PULL_SECRET': ''}


def write(root, files):
    for name, content in files.items():
        path = Path(root) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


def run_pod_script(target, mode, bundle):
    """Pod에서와 같은 방식(`python3 -c <파일 내용>`)으로 실행한다."""
    return subprocess.run([sys.executable, '-c', dags.POD_SCRIPT.read_text(), str(target), mode],
                          input=bundle, capture_output=True)


class PodScriptTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.source = Path(self.directory.name) / 'source'
        self.target = Path(self.directory.name) / 'target'
        write(self.source, {'same.py': 'same', 'changed.py': 'new', 'added.py': 'added', 'common/util.py': 'util',
                            '__pycache__/same.cpython-312.pyc': 'cache'})
        write(self.target, {'same.py': 'same', 'changed.py': 'old', 'server_only.py': 'mine', 'notes/readme.txt': 'keep'})

    def test_check_lists_changes_without_writing(self):
        result = run_pod_script(self.target, 'check', dags.archive(self.source))
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        plan = json.loads(result.stdout.decode().splitlines()[-1])
        self.assertEqual(plan['added'], ['added.py', 'common/util.py'])
        self.assertEqual(plan['updated'], ['changed.py'])
        self.assertEqual(plan['unchanged'], ['same.py'])
        self.assertEqual(plan['serverOnly'], ['notes/readme.txt', 'server_only.py'])
        self.assertEqual((self.target / 'changed.py').read_text(), 'old')
        self.assertFalse((self.target / 'added.py').exists())

    def test_apply_overwrites_same_names_adds_new_and_keeps_server_only_files(self):
        result = run_pod_script(self.target, 'apply', dags.archive(self.source))
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual((self.target / 'changed.py').read_text(), 'new')
        self.assertEqual((self.target / 'common/util.py').read_text(), 'util')
        self.assertEqual((self.target / 'server_only.py').read_text(), 'mine')
        self.assertEqual((self.target / 'notes/readme.txt').read_text(), 'keep')
        self.assertFalse((self.target / '__pycache__').exists())
        self.assertFalse(list(self.target.rglob('*' + 'dags-sync.tmp')))
        self.assertEqual((self.target / 'added.py').stat().st_mode & 0o777, 0o644)
        # 다시 실행하면 바뀔 것이 없다.
        again = json.loads(run_pod_script(self.target, 'check', dags.archive(self.source)).stdout.decode().splitlines()[-1])
        self.assertEqual((again['added'], again['updated']), ([], []))

    def test_paths_outside_the_folder_and_links_are_rejected(self):
        for build in (lambda bundle: bundle.addfile(tarfile.TarInfo('../escape.py'), io.BytesIO(b'')),
                      lambda bundle: bundle.addfile(tarfile.TarInfo('/abs.py'), io.BytesIO(b'')),
                      lambda bundle: bundle.addfile(self.link('link.py'))):
            buffer = io.BytesIO()
            with tarfile.open(fileobj=buffer, mode='w') as bundle:
                build(bundle)
            result = run_pod_script(self.target, 'apply', buffer.getvalue())
            self.assertEqual(result.returncode, 1)
            self.assertIn('오류:', result.stderr.decode())
        self.assertFalse((Path(self.directory.name) / 'escape.py').exists())

    @staticmethod
    def link(name):
        info = tarfile.TarInfo(name)
        info.type, info.linkname = tarfile.SYMTYPE, '/etc/passwd'
        return info

    def test_archive_is_stable_and_skips_python_cache(self):
        first = dags.archive(self.source)
        self.assertEqual(first, dags.archive(self.source))
        with tarfile.open(fileobj=io.BytesIO(first)) as bundle:
            self.assertEqual(bundle.getnames(), ['added.py', 'changed.py', 'common/util.py', 'same.py'])

    def test_check_reports_destination_conflicts_before_writing(self):
        write(self.target, {'common': '기존 파일'})
        for mode in ('check', 'apply'):
            result = run_pod_script(self.target, mode, dags.archive(self.source))
            self.assertEqual(result.returncode, 1)
            self.assertIn('DAG 하위 폴더로 쓸 수 없습니다', result.stderr.decode())
            self.assertFalse((self.target / 'added.py').exists())
            self.assertEqual((self.target / 'changed.py').read_text(), 'old')


class SyncFlowTests(unittest.TestCase):
    def fake(self, image='store.test/airflow:3.3.2-abc', fail_exec=False):
        calls = []
        result = {'mode': 'apply', 'added': ['a.py'], 'updated': [], 'unchanged': [], 'serverOnly': ['mine.py']}

        def runner(args, data=None):
            calls.append((args, data))
            verb = args[args.index('-n') + 2]
            if verb == 'get':
                return image
            if verb == 'create':
                return 'airflow-dags-sync-x1'
            if verb == 'exec':
                if fail_exec:
                    raise ValueError('exec 실패')
                return 'log\n' + json.dumps(result)
            return ''
        return runner, calls

    def source(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        write(directory.name, {'a.py': 'a'})
        return Path(directory.name)

    def test_uses_running_scheduler_image_on_the_airflow_worker_and_deletes_the_pod(self):
        runner, calls = self.fake()
        result = dags.sync(SETTINGS, 'ctx', apply=True, source=self.source(), runner=runner)
        self.assertEqual(result['added'], ['a.py'])
        verbs = [args[args.index('-n') + 2] for args, _ in calls]
        self.assertEqual(verbs, ['get', 'create', 'wait', 'exec', 'delete'])
        pod = json.loads(calls[1][1])['spec']
        self.assertEqual(pod['nodeSelector'], {'kubernetes.io/hostname': 'worker-a'})
        self.assertEqual(pod['containers'][0]['image'], 'store.test/airflow:3.3.2-abc')
        self.assertEqual(pod['volumes'][0]['hostPath'], {'path': '/appdata/airflow/dags', 'type': 'Directory'})
        self.assertFalse(pod['containers'][0]['volumeMounts'][0]['readOnly'])
        exec_args = calls[3][0]
        self.assertEqual(exec_args[-2:], ['/dags', 'apply'])
        self.assertTrue(calls[3][1].startswith(b'a.py'))

    def test_check_mounts_the_folder_read_only(self):
        runner, calls = self.fake()
        dags.sync(SETTINGS, 'ctx', apply=False, source=self.source(), runner=runner)
        self.assertTrue(json.loads(calls[1][1])['spec']['containers'][0]['volumeMounts'][0]['readOnly'])
        self.assertEqual(calls[3][0][-1], 'check')

    def test_pod_is_deleted_even_when_the_sync_fails(self):
        runner, calls = self.fake(fail_exec=True)
        with self.assertRaisesRegex(ValueError, 'exec 실패'):
            dags.sync(SETTINGS, 'ctx', apply=True, source=self.source(), runner=runner)
        self.assertEqual(calls[-1][0][calls[-1][0].index('-n') + 2], 'delete')

    def test_stops_before_creating_anything_without_a_deployed_scheduler(self):
        runner, calls = self.fake(image='')
        with self.assertRaisesRegex(ValueError, 'make ops-deploy APP=airflow'):
            dags.sync(SETTINGS, 'ctx', apply=True, source=self.source(), runner=runner)
        self.assertEqual(len(calls), 1)

    def test_report_ends_with_the_success_line(self):
        applied = dags.report({'mode': 'apply', 'added': ['a.py'], 'updated': ['b.py'], 'unchanged': ['c.py'], 'serverOnly': ['mine.py']})
        self.assertEqual(applied.splitlines(), ['추가: a.py', '덮어씀: b.py', '폴더에만 있음(유지): mine.py',
                                                'DAG 폴더 동기화 완료: 추가 1 · 덮어씀 1 · 같음 1 · 폴더에만 있음 1'])
        checked = dags.report({'mode': 'check', 'added': [], 'updated': [], 'unchanged': ['c.py'], 'serverOnly': []})
        self.assertEqual(checked, 'DAG 폴더 검사 완료(폴더는 바꾸지 않음): 추가 0 · 덮어씀 0 · 같음 1 · 폴더에만 있음 0')

    def test_real_dag_folder_can_be_archived(self):
        names = tarfile.open(fileobj=io.BytesIO(dags.archive(dags.SOURCE))).getnames()
        self.assertIn('scheduler_resource_load_test.py', names)
        self.assertFalse([name for name in names if '__pycache__' in name])


if __name__ == '__main__':
    unittest.main()
