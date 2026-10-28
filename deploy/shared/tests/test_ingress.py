"""독립 Ingress 준비와 나중에 추가하는 Portal 연결의 보존 계약을 검증한다."""

from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('ingress_manage', ROOT / 'deploy/shared/ingress/manage.py')
manage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manage)


def controller(watched='etch-sso'):
    """원본과 다른 운영 배치를 비교할 최소 Traefik Deployment를 만든다."""
    return {
        'apiVersion': 'apps/v1', 'kind': 'Deployment',
        'metadata': {'name': 'traefik', 'namespace': 'etch-sso', 'resourceVersion': '17'},
        'spec': {
            'replicas': 1, 'strategy': {'type': 'Recreate'},
            'selector': {'matchLabels': {'app.kubernetes.io/name': 'traefik'}},
            'template': {'spec': {
                'serviceAccountName': 'traefik',
                'nodeSelector': {'kubernetes.io/hostname': 'worker'},
                'containers': [{'name': 'traefik', 'image': 'registry.test/traefik:new',
                    'ports': [{'containerPort': 8000, 'hostPort': 80}, {'containerPort': 8443, 'hostPort': 443}], 'args': [
                    '--entrypoints.websecure.address=:8443', '--providers.kubernetesingress=true',
                    manage.routing.PREFIX + watched]}],
            }},
        },
    }


def worker(hostname, ip):
    """Worker 이름과 hostname label이 다른 정상 노드를 만든다."""
    return {
        'metadata': {'name': 'node-' + hostname, 'labels': {
            'kubernetes.io/hostname': hostname, 'kubernetes.io/os': 'linux'}},
        'spec': {},
        'status': {'addresses': [{'type': 'InternalIP', 'address': ip}],
                   'conditions': [{'type': 'Ready', 'status': 'True'}]},
    }


class IngressFixtures(unittest.TestCase):
    def setUp(self):
        self.context = 'explicit-server-context'
        self.source = [{'apiVersion': 'v1', 'kind': 'ServiceAccount',
                        'metadata': {'name': 'traefik', 'namespace': 'etch-sso'}}, controller()]
        self.source[-1]['metadata'].pop('resourceVersion')
        self.live = None
        self.namespace_exists = False
        self.nodes = [worker('worker', '192.0.2.10'), worker('second', '192.0.2.20')]
        self.pods = []
        self.calls = []
        self.patch_error = None
        self.role, self.binding = manage.routing.namespace_access('tailwind-internal', controller())
        self.role['metadata']['name'] = 'portal-traefik'
        self.binding['metadata']['name'] = 'portal-traefik'
        self.binding['roleRef']['name'] = 'portal-traefik'
        self.addCleanup(patch.stopall)
        patch.object(manage.runtime, 'render_json', side_effect=lambda *args: deepcopy(self.source)).start()
        patch.object(manage, 'run', side_effect=self.fake_run).start()
        patch.object(manage.tls, 'check').start()

    def fake_run(self, args, data=None):
        """명령을 기록하고 입력 fixture만 반환해 실제 클러스터를 사용하지 않는다."""
        args = list(map(str, args))
        self.calls.append((args, data))
        if 'patch' in args and self.patch_error:
            raise self.patch_error
        if 'get' in args and 'ingress' in args:
            return json.dumps({'spec': {'rules': [{'host': 'portal.test'}]}})
        if 'get' in args:
            resource = args[args.index('get') + 1]
            if resource == 'deployment':
                return json.dumps(self.live) if self.live else ''
            if resource == 'namespace':
                return 'namespace/etch-sso' if self.namespace_exists else ''
            if resource == 'nodes':
                return json.dumps({'items': self.nodes})
            if resource == 'pods':
                return json.dumps({'items': self.pods})
            if resource == 'role':
                return json.dumps(self.role) if self.role else ''
            if resource == 'rolebinding':
                return json.dumps(self.binding) if self.binding else ''
        return ''

    def writes(self):
        return [(args, data) for args, data in self.calls
                if any(action in args for action in ('apply', 'patch', 'create', 'delete', 'label'))]

    def assert_contexts(self):
        for args, _ in self.calls:
            if args[0] == 'kubectl':
                self.assertEqual(args[args.index('--context') + 1], self.context)


class FoundationTests(IngressFixtures):
    def test_first_check_uses_shared_source_without_any_application_resource(self):
        manage.start(self.context, check_only=True)
        self.assertEqual(self.writes(), [])
        self.assertFalse(any('rollout' in args for args, _ in self.calls))
        render = manage.runtime.render_json.call_args.args
        self.assertEqual(render[1], ['kubectl', '--context', self.context])
        self.assertEqual(render[2], manage.BASE)
        self.assertEqual(manage.BASE, ROOT / 'deploy/shared/ingress')
        self.assertFalse(any('keycloak' in args or 'airflow' in args or 'portal' in args
                             for args, _ in self.calls))
        self.assert_contexts()

    def test_first_up_applies_namespace_then_shared_resources_and_waits_only_traefik(self):
        manage.start(self.context)
        writes = self.writes()
        self.assertEqual([json.loads(data)['kind'] for _, data in writes], ['Namespace', 'List'])
        self.assertIn('create', writes[0][0])
        self.assertNotIn('apply', writes[0][0])
        self.assertIn('apply', writes[1][0])
        items = json.loads(writes[1][1])['items']
        self.assertEqual({item['metadata']['name'] for item in items}, {'traefik'})
        rollouts = [args for args, _ in self.calls if 'rollout' in args]
        self.assertEqual(len(rollouts), 1)
        self.assertIn('deployment/traefik', rollouts[0])
        self.assert_contexts()

    def test_existing_namespace_is_not_rewritten_when_shared_resources_are_applied(self):
        self.namespace_exists = True
        manage.start(self.context)
        writes = self.writes()
        self.assertEqual(len(writes), 1)
        self.assertIn('apply', writes[0][0])
        self.assertEqual(json.loads(writes[0][1])['kind'], 'List')
        self.assertFalse(any(json.loads(data).get('kind') == 'Namespace' for _, data in writes))
        namespace_reads = [args for args, _ in self.calls if 'get' in args and 'namespace' in args]
        self.assertEqual(len(namespace_reads), 1)
        self.assertIn('--ignore-not-found', namespace_reads[0])
        self.assert_contexts()

    def test_reapply_preserves_layout_annotations_and_existing_app_namespaces(self):
        self.live = controller('etch-sso,headlamp,airflow,tailwind-internal')
        self.live['metadata']['annotations'] = {'operator.test/owner': 'keep'}
        self.live['spec']['template']['metadata'] = {
            'labels': {'operator.test/role': 'ingress'}, 'annotations': {'operator.test/config': 'keep'}}
        self.live['spec']['replicas'] = 2
        self.live['spec']['strategy'] = {'type': 'RollingUpdate', 'rollingUpdate': {'maxSurge': 0, 'maxUnavailable': 1}}
        placement = self.live['spec']['template']['spec']
        placement['nodeSelector'] = {'custom.test/pool': 'ingress'}
        for node in self.nodes:
            node['metadata']['labels']['custom.test/pool'] = 'ingress'
        placement['affinity'] = {'nodeAffinity': {'preferredDuringSchedulingIgnoredDuringExecution': []}}
        placement['tolerations'] = [{'key': 'operator.test/dedicated', 'operator': 'Exists'}]
        placement['topologySpreadConstraints'] = [{'maxSkew': 1, 'topologyKey': 'kubernetes.io/hostname',
                                                 'whenUnsatisfiable': 'ScheduleAnyway'}]
        result = manage.routing.controller(manage.prepare(self.context))
        for key in ('replicas', 'strategy'):
            self.assertEqual(result['spec'][key], self.live['spec'][key])
        for key in ('nodeSelector', 'affinity', 'tolerations', 'topologySpreadConstraints'):
            self.assertEqual(result['spec']['template']['spec'][key], placement[key])
        self.assertEqual(result['metadata']['annotations'], self.live['metadata']['annotations'])
        self.assertEqual(result['spec']['template']['metadata'], self.live['spec']['template']['metadata'])
        args = result['spec']['template']['spec']['containers'][0]['args']
        self.assertIn(manage.routing.PREFIX + 'etch-sso,headlamp,airflow,tailwind-internal', args)
        self.assertEqual(self.writes(), [])

    def test_explicit_vip_checks_two_workers_and_prepares_spread(self):
        result = manage.routing.controller(manage.prepare(self.context, '192.0.2.20,192.0.2.10'))
        self.assertEqual(result['spec']['replicas'], 2)
        self.assertNotIn('nodeSelector', result['spec']['template']['spec'])
        self.assertIn('affinity', result['spec']['template']['spec'])
        self.assertEqual(result['metadata']['annotations'][manage.routing.VIP_BACKENDS], '192.0.2.10,192.0.2.20')
        self.assertEqual(self.writes(), [])
        self.assert_contexts()

    def test_non_vip_reapply_accepts_existing_matching_tolerations_only(self):
        self.live = controller('etch-sso,headlamp')
        self.nodes[0]['spec']['taints'] = [{'key': 'operator.test/dedicated', 'value': 'ingress', 'effect': 'NoSchedule'}]
        for toleration, allowed in (
                ({'key': 'operator.test/dedicated', 'operator': 'Exists'}, True),
                ({'key': 'operator.test/dedicated', 'operator': 'Equal', 'value': 'ingress', 'effect': 'NoSchedule'}, True),
                ({'key': 'operator.test/dedicated', 'value': 'ingress'}, True),
                ({'key': 'operator.test/dedicated', 'operator': 'Exists', 'effect': 'NoExecute'}, False),
                ({'key': 'operator.test/dedicated', 'operator': 'Equal', 'value': 'other'}, False)):
            with self.subTest(toleration=toleration):
                self.calls.clear()
                self.live['spec']['template']['spec']['tolerations'] = [toleration]
                if allowed:
                    result = manage.routing.controller(manage.prepare(self.context))
                    self.assertEqual(result['spec']['template']['spec']['tolerations'], [toleration])
                else:
                    with self.assertRaises(ValueError):
                        manage.prepare(self.context)
                self.assertEqual(self.writes(), [])

    def test_recorded_vip_is_validated_without_rewriting_operator_layout(self):
        original = controller('etch-sso,headlamp')
        self.live = manage.routing.place_vip_backends(original, original,
                            ['192.0.2.10', '192.0.2.20'], self.nodes, [])
        self.live['spec']['template']['spec']['tolerations'] = [{'key': 'keep', 'operator': 'Exists'}]
        self.live['spec']['template']['spec']['affinity']['nodeAffinity']['preferredDuringSchedulingIgnoredDuringExecution'] = []
        expected = deepcopy(self.live['spec']['template']['spec'])
        result = manage.routing.controller(manage.prepare(self.context))
        self.assertEqual(result['spec']['template']['spec']['affinity'], expected['affinity'])
        self.assertEqual(result['spec']['template']['spec']['tolerations'], expected['tolerations'])
        self.assertNotIn('nodeSelector', result['spec']['template']['spec'])
        self.nodes[1]['status']['conditions'][0]['status'] = 'False'
        with self.assertRaises(ValueError):
            manage.prepare(self.context)
        self.assertEqual(self.writes(), [])

    def test_recorded_vip_rejects_actual_missing_replica_or_excluded_backend(self):
        original = controller('etch-sso,headlamp')
        live = manage.routing.place_vip_backends(original, original,
                    ['192.0.2.10', '192.0.2.20'], self.nodes, [])
        for failure in ('replicas', 'affinity'):
            with self.subTest(failure=failure):
                self.calls.clear()
                self.live = deepcopy(live)
                if failure == 'replicas':
                    self.live['spec']['replicas'] = 1
                else:
                    self.live['spec']['template']['spec']['affinity']['nodeAffinity'][
                        'requiredDuringSchedulingIgnoredDuringExecution']['nodeSelectorTerms'] = [
                            {'matchFields': [{'key': 'metadata.name', 'operator': 'In', 'values': ['node-worker']}]}]
                with self.assertRaises(ValueError):
                    manage.start(self.context)
                self.assertEqual(self.writes(), [])

    def test_explicit_vip_affinity_uses_api_valid_singleton_field_terms(self):
        updated = manage.routing.controller(manage.prepare(self.context, '192.0.2.10,192.0.2.20'))
        terms = updated['spec']['template']['spec']['affinity']['nodeAffinity'][
            'requiredDuringSchedulingIgnoredDuringExecution']['nodeSelectorTerms']
        selected = set()
        for term in terms:
            for field in term['matchFields']:
                self.assertEqual(field['key'], 'metadata.name')
                self.assertIn(field['operator'], ('In', 'NotIn'))
                self.assertEqual(len(field['values']), 1)
                selected.update(field['values'])
        self.assertEqual(selected, {'node-worker', 'node-second'})
        self.assertTrue(all(manage.routing.node_matches(updated['spec']['template']['spec'], node)
                            for node in self.nodes))
        self.assertFalse(manage.routing.node_matches(updated['spec']['template']['spec'], worker('other', '192.0.2.30')))
        self.live = deepcopy(updated)
        self.live['metadata']['resourceVersion'] = 'invalid-operator-config'
        self.live['spec']['template']['spec']['affinity']['nodeAffinity'][
            'requiredDuringSchedulingIgnoredDuringExecution']['nodeSelectorTerms'] = [
                {'matchFields': [{'key': 'metadata.name', 'operator': 'In', 'values': sorted(selected)}]}]
        with self.assertRaisesRegex(ValueError, '노드 이름 하나'):
            manage.start(self.context)
        self.assertEqual(self.writes(), [])

    def test_recorded_vip_cannot_leave_backend_uncovered_by_using_extra_candidates(self):
        original = controller()
        self.live = manage.routing.place_vip_backends(original, original,
                    ['192.0.2.10', '192.0.2.20'], self.nodes, [])
        self.nodes.append(worker('third', '192.0.2.30'))
        self.live['spec']['template']['spec'].pop('affinity')
        with self.assertRaises(ValueError):
            manage.prepare(self.context)
        self.assertEqual(self.writes(), [])

    def test_non_vip_pool_uses_healthy_free_candidates_and_enforces_replica_capacity(self):
        self.live = controller()
        self.live['spec']['template']['spec']['nodeSelector'] = {'operator.test/pool': 'ingress'}
        for node in self.nodes:
            node['metadata']['labels']['operator.test/pool'] = 'ingress'
        for failure in ('cordoned', 'not-ready', 'tainted', 'port-conflict'):
            with self.subTest(failure=failure):
                self.calls.clear()
                self.live['spec']['replicas'] = 1
                self.nodes[1]['spec'] = {}
                self.nodes[1]['status']['conditions'][0]['status'] = 'True'
                self.pods = []
                if failure == 'cordoned':
                    self.nodes[1]['spec']['unschedulable'] = True
                elif failure == 'not-ready':
                    self.nodes[1]['status']['conditions'][0]['status'] = 'False'
                elif failure == 'tainted':
                    self.nodes[1]['spec']['taints'] = [{'key': 'dedicated', 'value': 'other', 'effect': 'NoSchedule'}]
                else:
                    self.pods = [{'metadata': {'name': 'other-controller', 'namespace': 'other'},
                                  'spec': {'nodeName': 'node-second', 'containers': [{'ports': [{'hostPort': 443}]}]}}]
                result = manage.routing.controller(manage.prepare(self.context))
                self.assertEqual(result['spec']['replicas'], 1)
                self.assertEqual(result['spec']['template']['spec']['nodeSelector'], {'operator.test/pool': 'ingress'})
                self.live['spec']['replicas'] = 2
                with self.assertRaises(ValueError):
                    manage.start(self.context)
                self.assertEqual(self.writes(), [])

    def test_required_node_affinity_limits_real_pool_capacity(self):
        self.live = controller()
        settings = self.live['spec']['template']['spec']
        settings.pop('nodeSelector')
        settings['affinity'] = {'nodeAffinity': {'requiredDuringSchedulingIgnoredDuringExecution': {
            'nodeSelectorTerms': [{'matchExpressions': [
                {'key': 'operator.test/pool', 'operator': 'In', 'values': ['ingress']},
                {'key': 'operator.test/generation', 'operator': 'Gt', 'values': ['2']},
                {'key': 'operator.test/retired', 'operator': 'DoesNotExist'}],
                'matchFields': [{'key': 'metadata.name', 'operator': 'NotIn', 'values': ['node-second']}]}]}}}
        self.nodes[0]['metadata']['labels'].update({'operator.test/pool': 'ingress', 'operator.test/generation': '3'})
        self.nodes[1]['metadata']['labels'].update({'operator.test/pool': 'ingress', 'operator.test/generation': '1'})
        result = manage.routing.controller(manage.prepare(self.context))
        self.assertEqual(result['spec']['template']['spec']['affinity'], settings['affinity'])
        self.live['spec']['replicas'] = 2
        with self.assertRaises(ValueError):
            manage.prepare(self.context)
        self.assertEqual(self.writes(), [])

    def test_bad_node_or_port_conflict_stops_before_namespace_or_resource_writes(self):
        for failure in ('missing', 'not-ready', 'port'):
            with self.subTest(failure=failure):
                self.calls.clear()
                self.nodes = [worker('worker', '192.0.2.10'), worker('second', '192.0.2.20')]
                self.pods = []
                if failure == 'missing':
                    self.nodes.pop()
                elif failure == 'not-ready':
                    self.nodes[1]['status']['conditions'][0]['status'] = 'False'
                else:
                    self.pods = [{'metadata': {'name': 'unrelated', 'namespace': 'other'},
                                  'spec': {'nodeName': 'node-second', 'containers': [{'ports': [{'hostPort': 443}]}]}}]
                with self.assertRaises(ValueError):
                    manage.start(self.context, '192.0.2.10,192.0.2.20')
                self.assertEqual(self.writes(), [])

    def test_empty_context_stops_before_any_external_command(self):
        for invoke in (lambda: manage.start(''), lambda: manage.connect('', 'portal')):
            with self.assertRaises(ValueError):
                invoke()
        self.assertEqual(self.calls, [])


class SparseCliTests(unittest.TestCase):
    def test_shared_only_cli_loads_and_empty_context_never_calls_kubectl(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in ('deploy/shared/ingress/manage.py', 'deploy/shared/ingress/routing.py', 'deploy/shared/ingress/tls.py',
                             'deploy/shared/scripts/runtime.py'):
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, target)
            cli = root / 'deploy/shared/ingress/manage.py'
            result = subprocess.run(['python3', cli, '--help'], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('connect', result.stdout)
            binary = root / 'bin/kubectl'
            binary.parent.mkdir()
            binary.write_text('#!/bin/sh\nprintf invoked > "$CALL_MARKER"\nexit 1\n')
            binary.chmod(0o755)
            marker = root / 'kubectl-called'
            env = {**os.environ, 'PATH': str(binary.parent) + os.pathsep + os.environ['PATH'],
                   'CALL_MARKER': str(marker)}
            result = subprocess.run(['python3', cli, 'check', '--context', ''], env=env,
                                    text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('KUBE_CONTEXT', result.stderr)
            self.assertFalse(marker.exists())
            self.assertFalse((root / 'apps').exists())
            self.assertFalse((root / 'local').exists())


class PortalConnectTests(IngressFixtures):
    def setUp(self):
        super().setUp()
        self.live = controller('etch-sso,headlamp,airflow')

    def test_later_portal_adds_only_namespace_with_revision_guard_and_named_container(self):
        containers = self.live['spec']['template']['spec']['containers']
        containers.insert(0, {'name': 'sidecar', 'image': 'registry.test/helper', 'args': ['keep']})
        before = deepcopy(self.live)
        manage.connect(self.context, 'portal')
        writes = self.writes()
        self.assertEqual(len(writes), 1)
        args, _ = writes[0]
        self.assertIn('patch', args)
        operations = json.loads(args[args.index('--patch') + 1])
        self.assertIn({'op': 'test', 'path': '/metadata/resourceVersion', 'value': '17'}, operations)
        changes = [operation for operation in operations if operation['op'] != 'test']
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]['path'], '/spec/template/spec/containers/1/args')
        self.assertIn(manage.routing.PREFIX + 'etch-sso,headlamp,airflow,tailwind-internal', changes[0]['value'])
        self.assertEqual(self.live, before)
        self.assertEqual(sum('rollout' in args for args, _ in self.calls), 1)
        self.assert_contexts()

    def test_existing_portal_and_all_namespace_watch_do_not_patch_or_rollout(self):
        for watched in ('etch-sso,headlamp,tailwind-internal', '', None):
            with self.subTest(watched=watched):
                self.calls.clear()
                self.live = controller(watched or '')
                if watched is None:
                    self.live['spec']['template']['spec']['containers'][0]['args'].pop()
                manage.connect(self.context, 'portal')
                self.assertEqual(self.writes(), [])
                self.assertFalse(any('rollout' in args for args, _ in self.calls))

    def test_missing_or_wrong_role_or_binding_blocks_changes(self):
        original_role, original_binding = deepcopy(self.role), deepcopy(self.binding)
        for failure in ('missing-role', 'missing-binding', 'permissions', 'role-ref', 'identity'):
            with self.subTest(failure=failure):
                self.calls.clear()
                self.role, self.binding = deepcopy(original_role), deepcopy(original_binding)
                if failure == 'missing-role':
                    self.role = None
                elif failure == 'missing-binding':
                    self.binding = None
                elif failure == 'permissions':
                    self.role['rules'][0]['verbs'] = ['get']
                elif failure == 'role-ref':
                    self.binding['roleRef']['name'] = 'unrelated-role'
                else:
                    self.binding['subjects'][0]['name'] = 'unrelated-account'
                with self.assertRaises(ValueError):
                    manage.connect(self.context, 'portal')
                self.assertEqual(self.writes(), [])

    def test_concurrent_update_failure_propagates_without_retry_or_rollout(self):
        self.patch_error = RuntimeError('resourceVersion changed')
        with self.assertRaisesRegex(RuntimeError, 'resourceVersion changed'):
            manage.connect(self.context, 'portal')
        self.assertEqual(sum('patch' in args for args, _ in self.calls), 1)
        self.assertFalse(any('rollout' in args for args, _ in self.calls))

    def test_unknown_app_stops_without_reading_or_writing_cluster(self):
        with self.assertRaises(ValueError):
            manage.connect(self.context, 'other')
        self.assertEqual(self.calls, [])


if __name__ == '__main__':
    unittest.main()
