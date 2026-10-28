"""기존 Keycloak·Traefik 보존과 Airflow 첫 기동 연결을 검증한다."""

from copy import deepcopy
import importlib.util
import json
import base64
import subprocess
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[3]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


server = load('airflow_server', 'deploy/airflow/scripts/server.py')
routing = load('routing', 'deploy/shared/ingress/routing.py')
airflow = load('airflow', 'deploy/airflow/scripts/manage.py')


def controller(watched='etch-sso'):
    return {'apiVersion': 'apps/v1', 'kind': 'Deployment', 'metadata': {'name': 'traefik', 'namespace': 'etch-sso'},
            'spec': {'replicas': 1, 'selector': {'matchLabels': {'app.kubernetes.io/name': 'traefik'}}, 'template': {'spec': {'serviceAccountName': 'traefik', 'nodeSelector': {'kubernetes.io/hostname': 'worker'},
             'volumes': [{'name': 'dynamic', 'projected': {'sources': [{'secret': {'name': 'traefik-tls'}}]}}],
             'containers': [{'name': 'traefik', 'volumeMounts': [{'name': 'dynamic', 'mountPath': '/etc/traefik/dynamic'}], 'args': ['--providers.file.directory=/etc/traefik/dynamic', '--providers.kubernetesingress=true', '--providers.kubernetesingress.ingressclass=traefik', routing.PREFIX + watched, '--entrypoints.websecure.address=:8443']}]}}}}


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
        terms = affinity['nodeAffinity']['requiredDuringSchedulingIgnoredDuringExecution']['nodeSelectorTerms']
        self.assertEqual([term['matchFields'][0] for term in terms], [
            {'key': 'metadata.name', 'operator': 'In', 'values': ['node-second-worker']},
            {'key': 'metadata.name', 'operator': 'In', 'values': ['node-worker']}])
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
    def test_legacy_server_cli_preserves_airflow_arguments(self):
        result = subprocess.run(['python3', ROOT / 'deploy/shared/scripts/server-up.py', '--help'],
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        for flag in ('--context', '--airflow-env', '--tls-source', '--vip-backends', '--check-only'):
            self.assertIn(flag, result.stdout)

    def test_kubectl_json_stream_and_list_are_both_supported(self):
        first = controller()
        second = {'kind': 'Service', 'metadata': {'name': 'traefik'}}
        for output in (json.dumps({'kind': 'List', 'items': [first, second]}), json.dumps(first) + '\n' + json.dumps(second)):
            run = Mock(side_effect=['yaml-source', output])
            self.assertEqual(server.render_json(run, ['kubectl', '--context', 'test'], '/source'), [first, second])
            self.assertIn('--dry-run=client', run.call_args[0][0])


class StartTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.settings = {
            'INGRESS_ENABLED': 'true', 'INGRESS_CLASS_NAME': 'traefik', 'NAMESPACE': 'airflow',
            'NODE_NAME': 'worker', 'AIRFLOW_WEBSERVER_BASE_URL': 'https://portal.test/airflow', 'INGRESS_TLS_SECRET': 'airflow-tls',
            'AIRFLOW_OIDC_CA_CONFIGMAP': '', 'IMAGE_PULL_SECRET': '', 'ODBC_SECRET_NAME': '',
        }
        self.tls = {'apiVersion': 'v1', 'kind': 'Secret', 'type': 'kubernetes.io/tls',
                    'data': {'tls.crt': 'ZmFrZS1jZXJ0', 'tls.key': 'ZmFrZS1rZXk='}}
        self.live = controller('etch-sso,tailwind-internal')
        self.live['metadata']['resourceVersion'] = '17'
        self.source = [controller(), {'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {
            'name': 'etch-sso', 'labels': {'operator.test/policy': 'initial'}}},
            {'apiVersion': 'apps/v1', 'kind': 'Deployment', 'metadata': {'name': 'keycloak', 'namespace': 'etch-sso'}}]
        self.namespace = ''
        self.mismatch = False
        self.key_mismatch = False
        self.missing_destination = False
        self.missing_resources = set()
        self.api = Mock()
        self.api.read_env.return_value = self.settings
        self.api.require.side_effect = airflow.require
        self.api.run.side_effect = self.fake_run
        self.api.check_required_resources.side_effect = self.check_required_resources
        self.api.chart_path.return_value = Path('/chart.tgz')
        self.addCleanup(patch.stopall)
        patch.object(server.tls, 'run', side_effect=self.fake_run).start()
        data = {f'portal.test.{suffix}': value for suffix, value in [('crt', 'ZmFrZS1jZXJ0'), ('key', 'ZmFrZS1rZXk=')]}
        data['tls.yaml'] = base64.b64encode(server.tls.configuration(data).encode()).decode()
        self.central = {'apiVersion': 'v1', 'kind': 'Secret', 'type': 'Opaque', 'data': data,
            'metadata': {'name': 'traefik-tls', 'namespace': 'etch-sso', 'resourceVersion': '1'}}
        self.nodes = [worker('worker', '192.0.2.10'), worker('second-worker', '192.0.2.20')]

    def check_required_resources(self, *args, **kwargs):
        """공통 진입점 테스트에서도 실제 필수 리소스 검사를 실행합니다."""
        with patch.object(airflow, 'run', self.fake_run):
            return airflow.check_required_resources(*args, **kwargs)

    def fake_run(self, args, **kwargs):
        args = list(map(str, args))
        self.calls.append((args, kwargs))
        if 'get' in args and any(kind in args and name in args for kind, name in self.missing_resources):
            raise ValueError('필수 리소스가 없습니다.')
        if args[0] == 'openssl':
            if '-pubkey' in args:
                return 'public-key'
            if '-pubout' in args:
                return 'wrong-key' if self.key_mismatch else 'public-key'
            return 'Hostname portal.test does NOT match certificate' if self.mismatch else 'Hostname portal.test does match certificate'
        if 'kustomize' in args:
            return 'rendered-source'
        if 'create' in args:
            if '--dry-run=client' in args:
                return json.dumps({'kind': 'List', 'items': self.source})
            self.assertIn(json.loads(kwargs['data'])['kind'], ('Namespace', 'Secret'))
            return ''
        if 'get' in args and 'namespace' in args:
            return self.namespace
        if 'get' in args and 'deployment' in args and 'traefik' in args:
            return json.dumps(self.live)
        if 'patch' in args and 'deployment' in args and 'traefik' in args:
            changes = json.loads(args[args.index('--patch') + 1])
            version = self.live['metadata']['resourceVersion']
            if changes[0] != {'op': 'test', 'path': '/metadata/resourceVersion', 'value': version}:
                raise ValueError('Traefik이 동시에 변경됐습니다.')
            index = int(changes[1]['path'].split('/')[5])
            self.live['spec']['template']['spec']['containers'][index]['args'] = changes[1]['value']
            self.live['metadata']['resourceVersion'] = str(int(version) + 1)
            return ''
        if 'get' in args and 'nodes' in args:
            return json.dumps({'items': self.nodes})
        if 'get' in args and 'pods' in args:
            return json.dumps({'items': []})
        if 'get' in args and 'secret' in args and '-o' in args and args[-1] == 'json':
            if 'traefik-tls' in args:
                return '' if self.missing_destination else json.dumps(self.central)
            return json.dumps(self.tls)
        return ''

    def test_preflight_then_rbac_then_stack_and_paused_airflow(self):
        server.start(self.api, routing, 'test-context', Path('/test.env'))
        applies = [(args, json.loads(kwargs['data'])) for args, kwargs in self.calls if 'apply' in args]
        created = [(args, json.loads(kwargs['data'])) for args, kwargs in self.calls
                   if 'create' in args and '--dry-run=client' not in args]
        self.assertEqual(created[0][1], {'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': 'airflow'}})
        namespace_created = next(index for index, (args, _) in enumerate(self.calls)
                                 if 'create' in args and '--dry-run=client' not in args)
        first_apply = next(index for index, (args, _) in enumerate(self.calls) if 'apply' in args)
        self.assertLess(namespace_created, first_apply)
        self.assertEqual(applies[0][1]['items'][0]['kind'], 'Role')
        resources = applies[1][1]['items']
        args = routing.controller(resources)['spec']['template']['spec']['containers'][0]['args']
        self.assertIn(routing.PREFIX + 'etch-sso,tailwind-internal,airflow', args)
        self.assertEqual(routing.controller(resources)['metadata']['resourceVersion'], '17')
        self.assertFalse(any(item['kind'] == 'Secret' for item in resources))
        self.assertFalse(any(item['kind'] == 'Namespace' for item in resources))
        self.assertFalse(any(item['kind'] == 'Secret' for _, item in applies))
        self.api.deploy.assert_called_once_with(self.settings, 'test-context', Path('/chart.tgz'), pause_new_dags=True)
        self.api.render.assert_called_once()
        for args, _ in self.calls:
            if args[0] == 'kubectl' and 'kustomize' not in args:
                self.assertEqual(args[1:3], ['--context', 'test-context'])
            self.assertNotIn('delete', args)

    def test_existing_namespaces_are_never_written_in_standalone_or_legacy_stack(self):
        """기존 Airflow Namespace와 legacy 목록의 Keycloak Namespace를 모두 보존합니다."""
        self.namespace = 'namespace/airflow'
        for deploy_keycloak in (False, True):
            with self.subTest(deploy_keycloak=deploy_keycloak):
                self.calls.clear()
                self.live = controller('etch-sso,tailwind-internal')
                self.live['metadata']['resourceVersion'] = '17'
                server.start(self.api, routing, 'test-context', Path('/test.env'), deploy_keycloak=deploy_keycloak)
                self.assertTrue(any('get' in args and 'namespace' in args for args, _ in self.calls))
                for args, kwargs in self.calls:
                    if '--dry-run=client' in args or not any(verb in args for verb in ('apply', 'create', 'patch')):
                        continue
                    if 'data' in kwargs:
                        body = json.loads(kwargs['data'])
                        self.assertNotEqual(body.get('kind'), 'Namespace')
                        self.assertTrue(all(item.get('kind') != 'Namespace' for item in body.get('items', [])))

    def test_wrong_tls_domain_blocks_before_mutation(self):
        self.mismatch = True
        with self.assertRaisesRegex(ValueError, '공개 도메인'):
            server.start(self.api, routing, 'test-context', Path('/test.env'))
        self.assertFalse(any('apply' in args for args, _ in self.calls))
        self.api.deploy.assert_not_called()

    def test_wrong_tls_private_key_blocks_before_mutation(self):
        self.key_mismatch = True
        with self.assertRaisesRegex(ValueError, '개인키.*일치'):
            server.start(self.api, routing, 'test-context', Path('/test.env'))
        self.assertFalse(any('apply' in args for args, _ in self.calls))
        self.api.deploy.assert_not_called()

    def test_legacy_stack_requires_sso_certificate_before_removing_its_secret_reference(self):
        self.source.append({'kind': 'Ingress', 'spec': {'rules': [{'host': 'sso.test'}]}})
        with self.assertRaisesRegex(ValueError, 'sso.test.*공용 TLS'):
            server.start(self.api, routing, 'test-context', Path('/test.env'))
        self.assertFalse(any('apply' in args for args, _ in self.calls))
        self.api.deploy.assert_not_called()

    def test_airflow_input_failure_stops_before_routing_mutation(self):
        self.api.check_cluster_inputs.side_effect = ValueError('기존 Fernet 키 불일치')
        with self.assertRaisesRegex(ValueError, 'Fernet'):
            server.start(self.api, routing, 'test-context', Path('/test.env'))
        self.assertFalse(any('apply' in args for args, _ in self.calls))
        self.api.deploy.assert_not_called()

    def test_missing_dependencies_fail_check_and_deploy_before_shared_mutation(self):
        for key, kind, name in [('IMAGE_PULL_SECRET', 'secret', 'missing-pull'),
                                ('ODBC_SECRET_NAME', 'secret', 'missing-odbc'),
                                ('AIRFLOW_OIDC_CA_CONFIGMAP', 'configmap', 'missing-ca'),
                                ('INGRESS_CLASS_NAME', 'ingressclass', 'traefik')]:
            for check_only in (False, True):
                for deploy_keycloak in (False, True):
                    with self.subTest(key=key, check_only=check_only, deploy_keycloak=deploy_keycloak):
                        self.settings.update({'IMAGE_PULL_SECRET': '', 'ODBC_SECRET_NAME': '',
                                              'AIRFLOW_OIDC_CA_CONFIGMAP': '', key: name})
                        self.missing_resources = {(kind, name)}
                        self.calls.clear()
                        with self.assertRaisesRegex(ValueError, '필수 리소스'):
                            server.start(self.api, routing, 'test-context', Path('/test.env'),
                                         check_only=check_only, deploy_keycloak=deploy_keycloak)
                        self.assertFalse(any('apply' in args for args, _ in self.calls))
                        self.api.deploy.assert_not_called()

    def test_pending_tls_does_not_skip_other_required_secrets(self):
        self.missing_destination = True
        self.settings['IMAGE_PULL_SECRET'] = 'missing-pull'
        self.missing_resources = {('secret', 'missing-pull')}
        with self.assertRaisesRegex(ValueError, '필수 리소스'):
            server.start(self.api, routing, 'test-context', Path('/test.env'), 'source/tls')
        self.assertFalse(any('apply' in args for args, _ in self.calls))
        self.api.deploy.assert_not_called()

    def test_legacy_tls_env_never_requires_an_app_namespace_copy(self):
        self.missing_resources = {('secret', 'airflow-tls')}
        self.check_required_resources(self.settings, 'test-context')
        self.assertFalse(any('airflow-tls' in args for args, _ in self.calls))

    def test_airflow_only_preserves_vip_and_never_reads_or_applies_keycloak(self):
        self.live = routing.place_vip_backends(self.live, self.live, ['192.0.2.10', '192.0.2.20'], self.nodes, [])
        self.live['status'] = {'readyReplicas': 2}
        self.live['metadata']['resourceVersion'] = '123'
        original = deepcopy(self.live)
        server.start(self.api, routing, 'test-context', Path('/test.env'), deploy_keycloak=False)
        applies = [json.loads(kwargs['data']) for args, kwargs in self.calls if 'apply' in args]
        self.assertTrue(all(item.get('kind') != 'Deployment' for body in applies
                            for item in body.get('items', [body])))
        self.assertEqual(self.live['spec']['replicas'], original['spec']['replicas'])
        self.assertEqual(self.live['spec']['template']['spec']['affinity'], original['spec']['template']['spec']['affinity'])
        self.assertEqual(self.live['status'], original['status'])
        self.assertTrue(any('patch' in args for args, _ in self.calls))
        for args, _ in self.calls:
            self.assertNotIn('kustomize', args)
            self.assertFalse(any('keycloak' in arg for arg in args))
        self.api.deploy.assert_called_once()

    def test_airflow_only_preserves_portal_connected_during_preflight(self):
        """사전 검사 후 추가된 Portal과 기존 Headlamp 감시를 최신 패치에 함께 보존합니다."""
        self.live = controller('etch-sso,headlamp')
        self.live['metadata']['resourceVersion'] = '17'

        def run(args, **kwargs):
            if 'create' in args and '--dry-run=client' not in args and json.loads(kwargs['data']).get('kind') == 'Namespace':
                self.live['spec']['template']['spec']['containers'][0]['args'][3] = (
                    routing.PREFIX + 'etch-sso,headlamp,tailwind-internal')
                self.live['metadata']['resourceVersion'] = '18'
            return self.fake_run(args, **kwargs)

        self.api.run.side_effect = run
        server.start(self.api, routing, 'test-context', Path('/test.env'), deploy_keycloak=False)
        args = self.live['spec']['template']['spec']['containers'][0]['args']
        self.assertIn(routing.PREFIX + 'etch-sso,headlamp,tailwind-internal,airflow', args)
        changes = [json.loads(args[args.index('--patch') + 1]) for args, _ in self.calls if 'patch' in args]
        self.assertEqual(changes[0][0]['value'], '18')
        rbac = next(i for i, (args, kwargs) in enumerate(self.calls)
                    if 'apply' in args and json.loads(kwargs['data']).get('kind') == 'List')
        patched = next(i for i, (args, _) in enumerate(self.calls) if 'patch' in args)
        self.assertLess(rbac, patched)
        self.api.deploy.assert_called_once()

    def test_airflow_only_conflict_keeps_new_portal_watch_and_stops_airflow(self):
        """최신 조회 뒤의 동시 변경은 resourceVersion 검사로 막고 앱 배포도 중단합니다."""
        def run(args, **kwargs):
            if 'apply' in args and json.loads(kwargs['data']).get('kind') == 'List':
                self.live['spec']['template']['spec']['containers'][0]['args'][3] = (
                    routing.PREFIX + 'etch-sso,tailwind-internal,headlamp')
                self.live['metadata']['resourceVersion'] = '18'
            return self.fake_run(args, **kwargs)

        self.api.run.side_effect = run
        with self.assertRaisesRegex(ValueError, '동시에 변경'):
            server.start(self.api, routing, 'test-context', Path('/test.env'), deploy_keycloak=False)
        self.assertIn(routing.PREFIX + 'etch-sso,tailwind-internal,headlamp',
                      self.live['spec']['template']['spec']['containers'][0]['args'])
        self.api.deploy.assert_not_called()
        self.assertFalse(any('rollout' in args for args, _ in self.calls))

    def test_airflow_only_existing_or_all_namespace_watch_never_patches_controller(self):
        for watched in ('etch-sso,airflow', ''):
            with self.subTest(watched=watched):
                self.calls.clear()
                self.live = controller(watched)
                self.live['metadata']['resourceVersion'] = '17'
                server.start(self.api, routing, 'test-context', Path('/test.env'), deploy_keycloak=False)
                self.assertFalse(any('patch' in args for args, _ in self.calls))

    def test_airflow_only_check_does_not_apply_or_deploy(self):
        server.start(self.api, routing, 'test-context', Path('/test.env'), deploy_keycloak=False, check_only=True)
        self.assertFalse(any('apply' in args for args, _ in self.calls))
        self.api.deploy.assert_not_called()

    def test_missing_tls_requires_explicit_source(self):
        self.missing_destination = True
        with self.assertRaisesRegex(ValueError, 'ingress-tls-up'):
            server.start(self.api, routing, 'test-context', Path('/test.env'))
        self.assertFalse(any('apply' in args for args, _ in self.calls))

    def test_explicit_source_registers_only_the_common_store(self):
        self.missing_destination = True
        self.tls['metadata'] = {'name': 'original', 'namespace': 'etch-sso', 'uid': 'never-copy'}
        server.start(self.api, routing, 'test-context', Path('/test.env'), 'etch-sso/keycloak-tls')
        registered = [json.loads(kwargs['data']) for args, kwargs in self.calls
                      if 'create' in args and '--dry-run=client' not in args and json.loads(kwargs.get('data', '{}')).get('kind') == 'Secret']
        self.assertEqual(len(registered), 1)
        self.assertEqual(registered[0]['metadata'], {'name': 'traefik-tls', 'namespace': 'etch-sso'})
        self.assertEqual(registered[0]['data']['portal.test.crt'], self.tls['data']['tls.crt'])
        self.assertNotIn('uid', registered[0]['metadata'])
        self.assertFalse(any('airflow-tls' in args for args, _ in self.calls))

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
