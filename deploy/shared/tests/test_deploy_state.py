"""배포 기록 작성과 checkout·기록·워크로드 대조 판정을 검증한다."""

import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import unittest.mock

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location('deploy_state', ROOT / 'deploy/shared/scripts/deploy_state.py')
state = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(state)

APP = {'deployPath': 'deploy/demo', 'sourcePaths': ['apps/demo'],
       'runtime': {'namespace': 'demo', 'selector': 'app=demo'}}
CHECKOUT = {'commit': 'b' * 40, 'branch': 'main'}


def workload(template='t1', images=('demo:1',), ready=1, desired=1, generation=1, observed=None):
    return {'templateHash': template, 'generation': generation, 'observedGeneration': generation if observed is None else observed,
            'images': list(images), 'desired': desired, 'ready': ready}


def record(**changes):
    base = {'app': 'demo', 'namespace': 'demo', 'commit': 'a' * 40, 'contentId': 'same', 'dirtyPaths': [],
            'inputs': {}, 'workloads': {'Deployment/demo': {'templateHash': 't1', 'images': ['demo:1']}},
            'appliedAt': '2026-11-19T00:00:00Z'}
    base.update(changes)
    return base


def judge(rec=None, checkout=CHECKOUT, content='same', dirty=(), changed=(), workloads=None, problems=(), digests=None,
          manifest=()):
    workloads = {'Deployment/demo': workload()} if workloads is None else workloads
    return state.compare('demo', APP, rec, checkout, content, list(dirty), list(changed), workloads, list(problems),
                         digests or {}, manifest)


def levels(result):
    return [(item['level'], item['area']) for item in result['findings']]


class CompareTest(unittest.TestCase):
    def test_matching_state_is_ok(self):
        result = judge(record(), manifest=[('ok', '리소스 3/3개 일치')])
        self.assertEqual(levels(result), [('ok', 'manifest')])
        self.assertEqual(state.exit_code([result]), 0)

    def test_commit_change_without_content_change_is_not_drift(self):
        # 다른 앱·문서만 바뀐 커밋은 배포 commit과 HEAD가 달라도 일치로 본다.
        result = judge(record(commit='c' * 40))
        self.assertEqual(state.exit_code([result]), 0)

    def test_content_change_lists_changed_files(self):
        result = judge(record(), content='new', changed=['deploy/demo/k8s/stack.yaml'])
        self.assertIn(('drift', 'record'), levels(result))
        self.assertIn('deploy/demo/k8s/stack.yaml', result['findings'][0]['message'])
        self.assertEqual(state.exit_code([result]), 1)

    def test_manual_cluster_edit_is_drift(self):
        changed_image = judge(record(), workloads={'Deployment/demo': workload(images=['demo:2'])})
        changed_spec = judge(record(), workloads={'Deployment/demo': workload(template='t2')})
        scaled = judge(record(), workloads={'Deployment/demo': workload(generation=5, desired=3, ready=3)})
        self.assertEqual(state.exit_code([scaled]), 0)
        missing = judge(record(), workloads={})
        self.assertIn(('drift', 'workload'), levels(changed_image))
        self.assertIn(('drift', 'workload'), levels(changed_spec))
        self.assertIn(('drift', 'workload'), levels(missing))

    def test_input_change_and_missing_input(self):
        rec = record(inputs={'/cfg/a.env': 'x', '/cfg/b.env': 'y'})
        result = judge(rec, digests={'/cfg/a.env': 'changed', '/cfg/b.env': None})
        self.assertIn(('drift', 'input'), levels(result))
        self.assertIn(('unknown', 'input'), levels(result))

    def test_missing_record_is_undecidable(self):
        result = judge(None)
        self.assertEqual(levels(result), [('unknown', 'record')])
        # 리소스 비교가 일치하면 기록이 없어도 불일치로 보지 않는다.
        self.assertEqual(state.exit_code([judge(None, manifest=[('ok', '일치')])]), 2)
        self.assertEqual(state.exit_code([result]), 2)

    def test_dirty_checkout_and_dirty_deploy(self):
        result = judge(record(dirtyPaths=['deploy/demo/env/k8s.env']), dirty=['deploy/demo/x.py'])
        self.assertIn(('warn', 'checkout'), levels(result))
        self.assertIn(('warn', 'record'), levels(result))

    def test_health_problems_are_warnings(self):
        result = judge(record(), workloads={'Deployment/demo': workload(ready=0, observed=0)},
                       problems=['demo-1/app: CrashLoopBackOff'])
        self.assertEqual({lv for lv, area in levels(result) if area == 'health'}, {'warn'})
        self.assertEqual(state.exit_code([result]), 1)


def deployment(name='web', image='web:1', replicas=1, **meta):
    return {'apiVersion': 'apps/v1', 'kind': 'Deployment',
            'metadata': {'name': name, 'namespace': 'demo', **meta},
            'spec': {'replicas': replicas, 'template': {'spec': {'containers': [{'name': 'app', 'image': image}]}}}}


class ManifestTest(unittest.TestCase):
    def test_select_skips_values_and_one_off_resources(self):
        items = [deployment(), {'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': 's'}},
                 {'apiVersion': 'batch/v1', 'kind': 'Job', 'metadata': {'name': 'j'}},
                 {'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': 'hook', 'annotations': {'helm.sh/hook': 'pre-install'}}},
                 {'apiVersion': 'v1', 'kind': 'Service', 'metadata': {'name': 'svc'}},
                 {'apiVersion': 'v1', 'kind': 'PersistentVolume', 'metadata': {'name': 'pv'}}]
        selected, skipped = state.select_desired(items, 'demo', {'PersistentVolume'})
        self.assertEqual([i['kind'] for i in selected], ['Deployment', 'Service', 'PersistentVolume'])
        self.assertEqual(selected[1]['metadata']['namespace'], 'demo')
        self.assertNotIn('namespace', selected[2]['metadata'])
        self.assertEqual(skipped, {'Secret': 1, 'Job': 1, 'Helm hook': 1})

    def test_volatile_metadata_is_ignored(self):
        live = deployment(resourceVersion='9', uid='u', generation=4, managedFields=[{}],
                          annotations={'kubectl.kubernetes.io/last-applied-configuration': '{}'})
        live['status'] = {'readyReplicas': 1}
        applied = deployment(resourceVersion='10', generation=5)
        key = state.resource_key(live)
        findings, matched = state.compare_manifests([deployment()], {key: applied}, {key: live}, {})
        self.assertEqual((findings, matched), ([], 1))

    def test_declared_difference_missing_and_error(self):
        desired = [deployment(), deployment('api'), deployment('db')]
        keys = [state.resource_key(item) for item in desired]
        applied = {keys[0]: deployment(image='web:2')}
        live = {keys[0]: deployment(), keys[2]: deployment('db')}
        findings, matched = state.compare_manifests(desired, applied, live, {keys[2]: 'immutable'})
        messages = [m for _, m in findings]
        self.assertEqual(matched, 0)
        self.assertIn('spec.template.spec.containers[app].image', messages[0])
        self.assertIn('클러스터에 없음', messages[1])
        self.assertIn('적용할 수 없음', messages[2])
        self.assertEqual({lv for lv, _ in findings}, {'drift'})

    def test_named_lists_ignore_order(self):
        live = deployment()
        live['spec']['template']['spec']['containers'][0]['env'] = [{'name': 'A', 'value': '1'}, {'name': 'B', 'value': '2'}]
        applied = deployment()
        applied['spec']['template']['spec']['containers'][0]['env'] = [{'name': 'B', 'value': '3'}, {'name': 'A', 'value': '1'}]
        self.assertEqual(state.differences(live, applied), ['spec.template.spec.containers[app].env[B].value'])

    def test_replica_only_difference_is_warning(self):
        key = state.resource_key(deployment())
        findings, _ = state.compare_manifests([deployment()], {key: deployment(replicas=1)}, {key: deployment(replicas=3)}, {})
        self.assertEqual([lv for lv, _ in findings], ['warn'])

    def test_manifest_findings_uses_render_dry_run_and_live(self):
        calls = []
        rendered = [deployment(), {'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': 's'}}]

        def kube(args, data=None):
            calls.append(args)
            if args[0] == 'create':
                return json.dumps({'kind': 'List', 'items': rendered})
            if args[0] == 'apply':
                self.assertIn('--dry-run=server', args)
                return json.dumps({'kind': 'List', 'items': [deployment()]})
            if args[0] == 'get':
                return json.dumps({'kind': 'List', 'items': [deployment(image='web:0')]})
            raise AssertionError(args)
        # 렌더 명령은 실행하지 않고 stdout만 흉내 낸다.
        with unittest.mock.patch.object(state, 'render_plan', return_value=(['true'], 'demo.yaml', ['demo.yaml'])), \
                unittest.mock.patch.object(state, 'run', return_value='kind: List'):
            findings = state.manifest_findings(kube, 'demo', APP, None, 'ctx', '', set())
        self.assertEqual(findings[0][0], 'drift')
        self.assertEqual(findings[-1][0], 'info')
        self.assertIn('리소스 0/1개 일치 (비교 제외: Secret 1)', findings[-1][1])
        self.assertFalse(any(a[0] == 'apply' and '--dry-run=server' not in a for a in calls))

    def test_render_plan_covers_every_app(self):
        for name in state.read_catalog()['apps']:
            command, _, files = state.render_plan(name, 'env', 'ctx', '', '/tmp/x')
            self.assertTrue(command and files, name)


class CollectTest(unittest.TestCase):
    def test_relevant_skips_docs_and_tests(self):
        self.assertFalse(state.relevant('deploy/demo/README.md'))
        self.assertFalse(state.relevant('deploy/demo/docs/01-install.md'))
        self.assertFalse(state.relevant('apps/demo/tests/test_x.py'))
        self.assertTrue(state.relevant('deploy/demo/env/k8s.env'))

    def test_content_id_ignores_docs_only_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            def git(args):
                return subprocess.run(['git', '-C', directory, *args], capture_output=True, text=True, check=True).stdout
            git(['init', '-q'])
            git(['config', 'user.email', 'test@example.invalid'])
            git(['config', 'user.name', 'test'])
            base = Path(directory) / 'deploy/demo'
            base.mkdir(parents=True)
            (base / 'stack.yaml').write_text('a: 1\n')
            (base / 'README.md').write_text('doc\n')
            git(['add', '.'])
            git(['commit', '-qm', 'init'])
            first = state.content_id(git, ['deploy/demo'])
            (base / 'README.md').write_text('doc 2\n')
            git(['commit', '-qam', 'docs'])
            self.assertEqual(state.content_id(git, ['deploy/demo']), first)
            (base / 'stack.yaml').write_text('a: 2\n')
            self.assertEqual(state.dirty_paths(git, ['deploy/demo']), ['deploy/demo/stack.yaml'])
            git(['commit', '-qam', 'change'])
            self.assertNotEqual(state.content_id(git, ['deploy/demo']), first)

    def test_snapshot_and_record_manifest(self):
        items = {'items': [
            {'kind': 'Deployment', 'metadata': {'name': 'web', 'generation': 2},
             'spec': {'replicas': 2, 'template': {'spec': {'containers': [{'image': 'web:1'}],
                                                            'initContainers': [{'image': 'init:1'}]}}},
             'status': {'readyReplicas': 1, 'observedGeneration': 2}},
            {'kind': 'DaemonSet', 'metadata': {'name': 'agent', 'generation': 1},
             'spec': {'template': {'spec': {'containers': [{'image': 'agent:1'}]}}},
             'status': {'desiredNumberScheduled': 3, 'numberReady': 3, 'observedGeneration': 1}}]}
        calls = []

        def kube(args, data=None):
            calls.append(args)
            return json.dumps(items)
        snapshot = state.workload_snapshot(kube, 'demo', 'app=demo')
        self.assertEqual(calls[0][:4], ['-n', 'demo', 'get', '-l'])
        self.assertEqual(snapshot['Deployment/web']['images'], ['init:1', 'web:1'])
        self.assertEqual((snapshot['Deployment/web']['ready'], snapshot['Deployment/web']['desired']), (1, 2))
        self.assertEqual(snapshot['DaemonSet/agent']['desired'], 3)
        self.assertNotEqual(snapshot['Deployment/web']['templateHash'], snapshot['DaemonSet/agent']['templateHash'])
        manifest = state.record_manifest(record())
        self.assertEqual(manifest['metadata']['labels'], {'deploy-record': 'demo'})
        self.assertEqual(json.loads(manifest['data']['record.json'])['commit'], 'a' * 40)

    def test_duplicate_records_are_rejected(self):
        item = {'metadata': {'namespace': 'a', 'name': 'deploy-record-demo'}, 'data': {'record.json': '{}'}}
        with self.assertRaises(state.QueryError):
            state.read_record(lambda args: json.dumps({'items': [item, item]}), 'demo')

    def test_catalog_has_runtime_for_every_app(self):
        catalog = state.read_catalog()
        self.assertEqual(state.resolve_apps(catalog, 'all'), catalog['groups']['all'])


if __name__ == '__main__':
    unittest.main()
