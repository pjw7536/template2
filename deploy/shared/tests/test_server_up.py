"""기존 Keycloak·Traefik 보존과 Airflow 첫 기동 연결을 검증한다."""

from copy import deepcopy
import importlib.util
import json
import base64
import subprocess
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[3]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


server = load('server_up', 'deploy/shared/scripts/server-up.py')
routing = load('routing', 'deploy/shared/ingress/routing.py')
airflow = load('airflow', 'deploy/airflow/scripts/manage.py')


def controller(watched='etch-sso'):
    return {'apiVersion': 'apps/v1', 'kind': 'Deployment', 'metadata': {'name': 'traefik', 'namespace': 'etch-sso'},
            'spec': {'replicas': 1, 'selector': {'matchLabels': {'app.kubernetes.io/name': 'traefik'}}, 'template': {'spec': {'serviceAccountName': 'traefik', 'nodeSelector': {'kubernetes.io/hostname': 'worker'},
             'containers': [{'name': 'traefik', 'args': ['--providers.kubernetesingress=true', '--providers.kubernetesingress.ingressclass=traefik', routing.PREFIX + watched, '--entrypoints.websecure.address=:8443']}]}}}}


class RoutingTests(unittest.TestCase):
    def test_preserves_portal_and_other_namespaces_and_is_idempotent(self):
        desired = controller()
        live = controller('etch-sso,tailwind-internal,existing-app')
        original = deepcopy(desired)
        patched = routing.preserve_namespaces(desired, live, 'airflow')
        args = patched['spec']['template']['spec']['containers'][0]['args']
        self.assertIn(routing.PREFIX + 'etch-sso,tailwind-internal,existing-app,airflow', args)
        self.assertEqual(routing.preserve_namespaces(desired, patched, 'airflow'), patched)
        self.assertEqual(desired, original)
        self.assertEqual(patched['metadata'], live['metadata'])
        self.assertEqual(patched['spec']['template']['spec']['nodeSelector'], live['spec']['template']['spec']['nodeSelector'])

    def test_all_namespace_watch_is_not_narrowed(self):
        for remove in (True, False):
            live = controller('')
            if remove:
                live['spec']['template']['spec']['containers'][0]['args'].pop(2)
            result = routing.preserve_namespaces(controller(), live, 'airflow')
            self.assertFalse(any(arg.startswith(routing.PREFIX) for arg in result['spec']['template']['spec']['containers'][0]['args']))

    def test_namespace_permissions_bind_existing_controller_identity(self):
        role, binding = routing.namespace_access('airflow', controller())
        self.assertEqual(role['metadata']['namespace'], 'airflow')
        self.assertEqual(binding['subjects'], [{'kind': 'ServiceAccount', 'name': 'traefik', 'namespace': 'etch-sso'}])
        self.assertFalse(any('*' in rule['resources'] or '*' in rule['verbs'] for rule in role['rules']))
        resources = {resource for rule in role['rules'] for resource in rule['resources']}
        self.assertTrue({'services', 'secrets', 'ingresses', 'endpointslices'} <= resources)
        self.assertNotIn('deployments', resources)


def worker(name, ip):
    """실제 이름과 hostname label이 다른 Node를 만들어 IP 역조회 계약을 검증한다."""
    return {'metadata': {'name': 'node-' + name, 'labels': {'kubernetes.io/hostname': name}}, 'spec': {},
            'status': {'addresses': [{'type': 'InternalIP', 'address': ip}], 'conditions': [{'type': 'Ready', 'status': 'True'}]}}


class VipTests(unittest.TestCase):
    def setUp(self):
        self.ips = ['192.0.2.10', '192.0.2.20']
        self.nodes = [worker('worker', self.ips[0]), worker('second-worker', self.ips[1])]

    def test_two_distinct_workers_and_rolling_update_preserve_runtime(self):
        original = controller()
        result = routing.place_vip_backends(original, original, self.ips, self.nodes, [])
        self.assertEqual(result['spec']['replicas'], 2)
        self.assertEqual(result['spec']['strategy']['rollingUpdate'], {'maxSurge': 0, 'maxUnavailable': 1})
        spec = result['spec']['template']['spec']
        self.assertNotIn('nodeSelector', spec)
        affinity = spec['affinity']
        fields = affinity['nodeAffinity']['requiredDuringSchedulingIgnoredDuringExecution']['nodeSelectorTerms'][0]['matchFields'][0]
        self.assertEqual(fields, {'key': 'metadata.name', 'operator': 'In', 'values': ['node-second-worker', 'node-worker']})
        self.assertEqual(affinity['podAntiAffinity']['requiredDuringSchedulingIgnoredDuringExecution'][0]['topologyKey'], 'kubernetes.io/hostname')
        self.assertEqual(spec['containers'], original['spec']['template']['spec']['containers'])
        self.assertEqual(routing.vip_backend_ips('', result), self.ips)
        self.assertEqual(routing.place_vip_backends(original, result, self.ips, self.nodes, []), result)
        self.assertIn('nodeSelector', original['spec']['template']['spec'])

    def test_invalid_duplicate_or_single_backend_fails(self):
        for text in ('192.0.2.10', '192.0.2.10,192.0.2.10', 'bad,192.0.2.10'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                routing.vip_backend_ips(text, controller())

    def test_missing_not_ready_cordoned_tainted_or_duplicate_hostname_fails(self):
        variants = [self.nodes[:1]]
        for key, value in [('unschedulable', True), ('taints', [{'effect': 'NoSchedule'}])]:
            nodes = deepcopy(self.nodes)
            nodes[1]['spec'][key] = value
            variants.append(nodes)
        nodes = deepcopy(self.nodes)
        nodes[1]['status']['conditions'][0]['status'] = 'False'
        variants.append(nodes)
        nodes = deepcopy(self.nodes)
        nodes[1]['metadata']['labels']['kubernetes.io/hostname'] = 'worker'
        variants.append(nodes)
        for nodes in variants:
            with self.subTest(nodes=nodes), self.assertRaises(ValueError):
                routing.place_vip_backends(controller(), controller(), self.ips, nodes, [])

    def test_existing_entry_worker_must_be_retained(self):
        live = controller()
        live['spec']['template']['spec']['nodeSelector']['kubernetes.io/hostname'] = 'outside'
        with self.assertRaisesRegex(ValueError, '기존 Traefik Worker'):
            routing.place_vip_backends(controller(), live, self.ips, self.nodes, [])

    def test_conflicting_pod_ports_block_but_existing_traefik_is_allowed(self):
        pod = {'metadata': {'name': 'proxy', 'namespace': 'other'}, 'spec': {'nodeName': 'node-second-worker',
               'containers': [{'ports': [{'hostPort': 443}]}]}}
        with self.assertRaisesRegex(ValueError, '443 포트'):
            routing.place_vip_backends(controller(), controller(), self.ips, self.nodes, [pod])
        pod['metadata'] = {'name': 'traefik-old', 'namespace': 'etch-sso', 'labels': {'app.kubernetes.io/name': 'traefik'}}
        routing.place_vip_backends(controller(), controller(), self.ips, self.nodes, [pod])


class ConversionTests(unittest.TestCase):
    def test_kubectl_json_stream_and_list_are_both_supported(self):
        first = controller()
        second = {'kind': 'Service', 'metadata': {'name': 'traefik'}}
        for output in (json.dumps({'kind': 'List', 'items': [first, second]}), json.dumps(first) + '\n' + json.dumps(second)):
            run = Mock(side_effect=['yaml-source', output])
            self.assertEqual(server.render_json(run, ['kubectl', '--context', 'test'], '/source'), [first, second])
            self.assertIn('--dry-run=client', run.call_args[0][0])


class CertificateTests(unittest.TestCase):
    def test_real_openssl_checks_hostname_before_copying(self):
        with tempfile.TemporaryDirectory() as directory:
            certificate = Path(directory) / 'cert.pem'
            key = Path(directory) / 'key.pem'
            subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1', '-subj', '/CN=portal.test', '-addext', 'subjectAltName=DNS:portal.test', '-keyout', str(key), '-out', str(certificate)], check=True, capture_output=True)
            secret = {'type': 'kubernetes.io/tls', 'data': {'tls.crt': base64.b64encode(certificate.read_bytes()).decode(), 'tls.key': base64.b64encode(key.read_bytes()).decode()}}
            def run(args, **kwargs):
                if args[0] == 'kubectl':
                    return json.dumps(secret)
                return airflow.run(args, **kwargs)
            settings = {'NAMESPACE': 'airflow', 'INGRESS_TLS_SECRET': 'airflow-tls', 'AIRFLOW_WEBSERVER_BASE_URL': 'https://portal.test/airflow'}
            self.assertIsNone(server.tls_for_airflow(run, ['kubectl'], settings, None))
            settings['AIRFLOW_WEBSERVER_BASE_URL'] = 'https://different.test/airflow'
            with self.assertRaisesRegex(ValueError, '도메인과 일치'):
                server.tls_for_airflow(run, ['kubectl'], settings, None)


class StartTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.settings = {
            'INGRESS_ENABLED': 'true', 'INGRESS_CLASS_NAME': 'traefik', 'NAMESPACE': 'airflow',
            'NODE_NAME': 'worker', 'AIRFLOW_WEBSERVER_BASE_URL': 'https://portal.test/airflow', 'INGRESS_TLS_SECRET': 'airflow-tls',
        }
        self.tls = {'apiVersion': 'v1', 'kind': 'Secret', 'type': 'kubernetes.io/tls',
                    'data': {'tls.crt': 'ZmFrZS1jZXJ0', 'tls.key': 'ZmFrZS1rZXk='}}
        self.live = controller('etch-sso,tailwind-internal')
        self.source = [controller(), {'apiVersion': 'apps/v1', 'kind': 'Deployment', 'metadata': {'name': 'keycloak', 'namespace': 'etch-sso'}}]
        self.mismatch = False
        self.missing_destination = False
        self.api = Mock()
        self.api.read_env.return_value = self.settings
        self.api.require.side_effect = airflow.require
        self.api.run.side_effect = self.fake_run
        self.api.chart_path.return_value = Path('/chart.tgz')
        self.nodes = [worker('worker', '192.0.2.10'), worker('second-worker', '192.0.2.20')]

    def fake_run(self, args, **kwargs):
        args = list(map(str, args))
        self.calls.append((args, kwargs))
        if args[0] == 'openssl':
            return 'Hostname portal.test does NOT match certificate' if self.mismatch else 'Hostname portal.test does match certificate'
        if 'kustomize' in args:
            return 'rendered-source'
        if 'create' in args:
            self.assertIn('--dry-run=client', args)
            return json.dumps({'kind': 'List', 'items': self.source})
        if 'get' in args and 'deployment' in args and 'traefik' in args:
            return json.dumps(self.live)
        if 'get' in args and 'nodes' in args:
            return json.dumps({'items': self.nodes})
        if 'get' in args and 'pods' in args:
            return json.dumps({'items': []})
        if 'get' in args and 'secret' in args and '-o' in args and args[-1] == 'json':
            if 'airflow-tls' in args and self.missing_destination:
                return ''
            return json.dumps(self.tls)
        return ''

    def test_preflight_then_rbac_then_stack_and_paused_airflow(self):
        server.start(self.api, routing, 'test-context', Path('/test.env'))
        applies = [(args, json.loads(kwargs['data'])) for args, kwargs in self.calls if 'apply' in args]
        self.assertEqual(applies[0][1]['kind'], 'Namespace')
        self.assertEqual(applies[1][1]['items'][0]['kind'], 'Role')
        resources = applies[2][1]['items']
        args = routing.controller(resources)['spec']['template']['spec']['containers'][0]['args']
        self.assertIn(routing.PREFIX + 'etch-sso,tailwind-internal,airflow', args)
        self.assertFalse(any(item['kind'] == 'Secret' for item in resources))
        self.assertFalse(any(item['kind'] == 'Secret' for _, item in applies))
        self.api.deploy.assert_called_once_with(self.settings, 'test-context', Path('/chart.tgz'), pause_new_dags=True)
        self.api.render.assert_called_once()
        for args, _ in self.calls:
            if args[0] == 'kubectl' and 'kustomize' not in args:
                self.assertEqual(args[1:3], ['--context', 'test-context'])
            self.assertNotIn('delete', args)

    def test_wrong_tls_domain_blocks_before_mutation(self):
        self.mismatch = True
        with self.assertRaisesRegex(ValueError, '도메인과 일치'):
            server.start(self.api, routing, 'test-context', Path('/test.env'))
        self.assertFalse(any('apply' in args for args, _ in self.calls))
        self.api.deploy.assert_not_called()

    def test_airflow_input_failure_stops_before_routing_mutation(self):
        self.api.check_cluster_inputs.side_effect = ValueError('기존 Fernet 키 불일치')
        with self.assertRaisesRegex(ValueError, 'Fernet'):
            server.start(self.api, routing, 'test-context', Path('/test.env'))
        self.assertFalse(any('apply' in args for args, _ in self.calls))
        self.api.deploy.assert_not_called()

    def test_airflow_only_preserves_vip_and_never_reads_or_applies_keycloak(self):
        self.live = routing.place_vip_backends(self.live, self.live, ['192.0.2.10', '192.0.2.20'], self.nodes, [])
        self.live['status'] = {'readyReplicas': 2}
        self.live['metadata']['resourceVersion'] = '123'
        server.start(self.api, routing, 'test-context', Path('/test.env'), deploy_keycloak=False)
        applies = [json.loads(kwargs['data']) for args, kwargs in self.calls if 'apply' in args]
        controller = routing.controller(applies[-1]['items'])
        self.assertEqual(controller['spec']['replicas'], 2)
        self.assertEqual(controller['spec']['template']['spec']['affinity'], self.live['spec']['template']['spec']['affinity'])
        self.assertNotIn('status', controller)
        self.assertNotIn('resourceVersion', controller['metadata'])
        self.assertEqual(len(applies[-1]['items']), 1)
        for args, _ in self.calls:
            self.assertNotIn('kustomize', args)
            self.assertFalse(any('keycloak' in arg for arg in args))
        self.api.deploy.assert_called_once()

    def test_airflow_only_check_does_not_apply_or_deploy(self):
        server.start(self.api, routing, 'test-context', Path('/test.env'), deploy_keycloak=False, check_only=True)
        self.assertFalse(any('apply' in args for args, _ in self.calls))
        self.api.deploy.assert_not_called()

    def test_missing_tls_requires_explicit_source(self):
        self.missing_destination = True
        with self.assertRaisesRegex(ValueError, '--tls-source'):
            server.start(self.api, routing, 'test-context', Path('/test.env'))
        self.assertFalse(any('apply' in args for args, _ in self.calls))

    def test_tls_copy_is_only_for_new_destination_without_source_metadata(self):
        self.missing_destination = True
        self.tls['metadata'] = {'name': 'original', 'namespace': 'etch-sso', 'uid': 'never-copy'}
        server.start(self.api, routing, 'test-context', Path('/test.env'), 'etch-sso/keycloak-tls')
        copied = [json.loads(kwargs['data']) for args, kwargs in self.calls if 'apply' in args and kwargs.get('sensitive')]
        self.assertEqual(len(copied), 1)
        self.assertEqual(copied[0]['metadata'], {'name': 'airflow-tls', 'namespace': 'airflow'})
        self.assertEqual(copied[0]['data'], self.tls['data'])

    def test_node_change_blocks_before_mutation(self):
        self.live['spec']['template']['spec']['nodeSelector']['kubernetes.io/hostname'] = 'another-worker'
        with self.assertRaisesRegex(ValueError, 'nodeSelector'):
            server.start(self.api, routing, 'test-context', Path('/test.env'))
        self.assertFalse(any('apply' in args for args, _ in self.calls))

    def test_vip_first_apply_and_repeat_keep_two_workers_and_app_placement(self):
        server.start(self.api, routing, 'test-context', Path('/test.env'), vip_backends='192.0.2.20,192.0.2.10')
        def applied_controller():
            lists = [json.loads(kwargs['data'])['items'] for args, kwargs in self.calls if 'apply' in args and json.loads(kwargs['data']).get('kind') == 'List']
            return routing.controller(lists[-1])
        first = applied_controller()
        self.live = first
        self.calls.clear()
        server.start(self.api, routing, 'test-context', Path('/test.env'))
        self.assertEqual(first, applied_controller())
        self.assertEqual(first['spec']['replicas'], 2)
        self.assertEqual(self.settings['NODE_NAME'], 'worker')

    def test_vip_unknown_node_and_check_only_never_write(self):
        with self.assertRaisesRegex(ValueError, 'InternalIP'):
            server.start(self.api, routing, 'test-context', Path('/test.env'), vip_backends='192.0.2.10,192.0.2.99')
        server.start(self.api, routing, 'test-context', Path('/test.env'), vip_backends='192.0.2.10,192.0.2.20', check_only=True)
        self.assertFalse(any('apply' in args for args, _ in self.calls))
        self.api.deploy.assert_not_called()


class PauseTests(unittest.TestCase):
    def test_first_start_override_does_not_change_normal_compose_parity(self):
        settings = airflow.read_env(airflow.DEFAULT_ENV)
        self.assertNotIn('core', airflow.helm_values(settings)['config'])
        self.assertEqual(airflow.helm_values(settings, pause_new_dags=True)['config']['core']['dags_are_paused_at_creation'], 'True')
        settings.update({'INGRESS_ENABLED': 'true', 'INGRESS_CLASS_NAME': 'traefik', 'AIRFLOW_WEBSERVER_BASE_URL': 'https://portal.test/airflow'})
        route = airflow.helm_values(settings)['ingress']['web']
        self.assertEqual(route['annotations']['traefik.ingress.kubernetes.io/router.entrypoints'], 'websecure')
        self.assertEqual(route['annotations']['traefik.ingress.kubernetes.io/router.tls'], 'true')
        self.assertEqual(route['path'], '/airflow')


if __name__ == '__main__':
    unittest.main()
