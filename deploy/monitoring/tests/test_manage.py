"""Monitoring의 데이터 보존·미러·중복 설치 차단을 검증한다."""

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / 'scripts/manage.py'
spec = importlib.util.spec_from_file_location('monitoring_manage', MODULE)
manage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manage)


def settings():
    """실제 비밀값 없이 테스트용 서버 입력을 만든다."""
    result = manage.read_env(manage.BASE / 'env/k8s.env')
    result['NODE_NAME'] = 'worker-one'
    for key in ('DOCKER_REGISTRY', 'QUAY_REGISTRY', 'GHCR_REGISTRY', 'K8S_REGISTRY'):
        result[key] = 'mirror.test/' + key.lower()
    return result


def rendered_fixture(components=('prometheus', 'alertmanager', 'grafana'), names=None):
    """CRD 내부 kind와 최상위 서비스 리소스를 구별할 고정 chart 형식 입력을 만든다."""
    names = names or {}
    documents = ['apiVersion: apiextensions.k8s.io/v1\nkind: CustomResourceDefinition\n'
                 'metadata:\n  name: alertmanagers.monitoring.coreos.com\n'
                 'spec:\n  names:\n    kind: Alertmanager\n']
    for component in components:
        kind = {'prometheus': 'Prometheus', 'alertmanager': 'Alertmanager', 'grafana': 'Deployment'}[component]
        source = ('kube-prometheus-stack/charts/grafana/templates/deployment.yaml' if component == 'grafana'
                  else f'kube-prometheus-stack/templates/{component}/{component}.yaml')
        documents.append(f'# Source: {source}\napiVersion: monitoring.coreos.com/v1\nkind: {kind}\n'
                         f'metadata:\n  name: {names.get(component, "monitoring-" + component)}\n  namespace: monitoring\n')
    return '\n---\n'.join(documents)


def fake_render(data, directory, chart, values_file=None, components=('prometheus', 'alertmanager', 'grafana'), names=None):
    """클러스터 흐름 검사에 최종 렌더·스토리지 파일 계약을 제공한다."""
    content = rendered_fixture(components, names)
    (Path(directory) / 'monitoring.yaml').write_text(content)
    (Path(directory) / 'storage.json').write_text(json.dumps(
        manage.storage(data, manage.rendered_components(content))))
    return ['-n', data['NAMESPACE'], *(['-f', values_file] if values_file else [])]


class MonitoringTests(unittest.TestCase):
    """네트워크 호출 없이 필수 배포 경계를 확인한다."""

    def run_storage_script(self, root, components, existing=()):
        """실제 준비 셸을 임시 폴더에서 실행하고 소유권 변경 요청만 기록한다."""
        tools = root.parent / 'bin'
        tools.mkdir(exist_ok=True)
        owner_log = root.parent / 'ownership.log'
        chown = tools / 'chown'
        chown.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$MONITORING_TEST_OWNER_LOG"\n')
        chown.chmod(0o755)
        job = manage.storage_job(settings(), components, existing)
        command = job['spec']['template']['spec']['containers'][0]['command']
        environment = {**os.environ, 'PATH': str(tools) + os.pathsep + os.environ.get('PATH', ''),
                       'MONITORING_TEST_OWNER_LOG': str(owner_log)}
        return subprocess.run([*command[:-1], str(root)], env=environment, capture_output=True, text=True), owner_log

    def test_storage_script_creates_only_missing_active_directories_and_preserves_existing_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'data'
            root.mkdir()
            grafana = root / 'grafana'
            grafana.mkdir(mode=0o751)
            database = grafana / 'grafana.db'
            database.write_text('existing-data')
            database.chmod(0o640)
            old_metadata = [(path.stat().st_uid, path.stat().st_gid, path.stat().st_mode) for path in (grafana, database)]
            active = {'prometheus': {}, 'grafana': {}}
            for _ in range(2):
                result, owner_log = self.run_storage_script(root, active, {'grafana'})
                self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((root / 'prometheus').stat().st_mode & 0o777, 0o770)
            self.assertEqual(owner_log.read_text().splitlines(), [f'1000:2000 {root}/prometheus'])
            self.assertEqual(database.read_text(), 'existing-data')
            self.assertEqual([(path.stat().st_uid, path.stat().st_gid, path.stat().st_mode) for path in (grafana, database)], old_metadata)
            self.assertFalse((root / 'alertmanager').exists())

    def test_storage_script_blocks_symlinks_files_and_missing_existing_pv_before_creation(self):
        for problem in ('symlink', 'file', 'missing-pv'):
            with self.subTest(problem=problem), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / 'data'
                root.mkdir()
                if problem == 'symlink':
                    (root / 'grafana').symlink_to(root, target_is_directory=True)
                elif problem == 'file':
                    (root / 'grafana').write_text('keep-this-file')
                active = {'prometheus': {}, 'grafana': {}}
                result, owner_log = self.run_storage_script(root, active, {'grafana'} if problem == 'missing-pv' else ())
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((root / 'prometheus').exists())
                self.assertFalse(owner_log.exists())
                if problem == 'file':
                    self.assertEqual((root / 'grafana').read_text(), 'keep-this-file')

    def test_storage_job_uses_selected_worker_mirror_and_pull_secret(self):
        data = {**settings(), 'IMAGE_PULL_SECRET': 'registry-login'}
        job = manage.storage_job(data, {'alertmanager': {}})
        pod = job['spec']['template']['spec']
        self.assertEqual(pod['nodeSelector'], {'kubernetes.io/hostname': data['NODE_NAME']})
        self.assertEqual(pod['volumes'][0]['hostPath'], {'path': data['DATA_HOST_PATH'], 'type': 'DirectoryOrCreate'})
        self.assertEqual(pod['imagePullSecrets'], [{'name': 'registry-login'}])
        self.assertEqual(pod['containers'][0]['image'], data['DOCKER_REGISTRY'] + '/library/busybox:1.37.0')
        self.assertIn('prepare_directory alertmanager 1000 2000', pod['containers'][0]['command'][2])
        self.assertNotIn('prepare_directory grafana', pod['containers'][0]['command'][2])
        self.assertEqual(job['metadata']['namespace'], data['NAMESPACE'])
        self.assertEqual(job['spec']['backoffLimit'], 0)
        self.assertGreater(job['spec']['ttlSecondsAfterFinished'], 0)
        self.assertIsNone(manage.storage_job(data, {}))

    def test_existing_pv_job_requires_existing_directory(self):
        data = settings()
        components = {'prometheus': {'name': 'monitoring-prometheus'}}
        resources = manage.storage(data, components)
        created = []

        def run(args, data=None):
            if 'get' in args:
                return json.dumps(resources['items'][0])
            if 'create' in args:
                created.append(json.loads(data))
                return json.dumps({'metadata': {'name': 'monitoring-storage-prepare-test'}})
            return ''

        with patch.object(manage, 'run', run):
            manage.prepare_storage(['kubectl', '--context', 'prod'], data, components, resources)
        pod = created[-1]['spec']['template']['spec']
        self.assertEqual(pod['volumes'][0]['hostPath']['type'], 'Directory')
        self.assertIn('check_directory prometheus existing', pod['containers'][0]['command'][2])

    def test_existing_pv_location_or_claim_mismatch_stops_before_storage_job(self):
        for problem in ('path', 'node', 'claim'):
            with self.subTest(problem=problem):
                data = settings()
                components = {'prometheus': {'name': 'monitoring-prometheus'}}
                resources = manage.storage(data, components)
                current = json.loads(json.dumps(resources['items'][0]))
                if problem == 'path':
                    current['spec']['local']['path'] = '/old/location'
                elif problem == 'node':
                    current['spec']['nodeAffinity'] = {}
                else:
                    current['spec']['claimRef']['namespace'] = 'another-app'
                with patch.object(manage, 'run', return_value=json.dumps(current)) as run, self.assertRaises(ValueError):
                    manage.prepare_storage(['kubectl', '--context', 'prod'], data, components, resources)
                self.assertTrue(all('get' in call.args[0] for call in run.call_args_list))

    def test_placeholder_and_unknown_keys_are_rejected(self):
        with self.assertRaisesRegex(ValueError, '실제 값'):
            manage.validate({**settings(), 'NODE_NAME': 'replace-me'})
        data = settings()
        manage.validate(data)
        data['PASSWORD'] = 'not-allowed'
        with self.assertRaisesRegex(ValueError, 'env 키'):
            manage.validate(data)

    def test_duplicate_env_and_relative_path_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'test.env'
            path.write_text('NAMESPACE=one\nNAMESPACE=two\n')
            with self.assertRaises(ValueError):
                manage.read_env(path)
        data = settings()
        data['DATA_HOST_PATH'] = '/srv/../data'
        with self.assertRaises(ValueError):
            manage.validate(data)

    def test_ingress_requires_dns_and_tls_and_can_be_disabled_for_local(self):
        for changes in ({'INGRESS_HOST': 'https://portal.test/path'}, {'INGRESS_HOST': ''},
                        {'INGRESS_ENABLED': 'yes'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                manage.validate({**settings(), **changes})
        data = {**settings(), 'INGRESS_ENABLED': 'false', 'INGRESS_HOST': '', 'INGRESS_TLS_SECRET': ''}
        manage.validate(data)
        self.assertTrue(all('ingress' not in manage.values(data)[name] for name in manage.VOLUMES))

    def test_ingress_connect_preserves_vip_placement_and_other_apps(self):
        content = ('kind: Ingress\nmetadata:\n  namespace: monitoring\nspec:\n'
                   '  ingressClassName: traefik\n  rules:\n    - host: portal.test\n')
        current = {'metadata': {'namespace': 'etch-sso', 'resourceVersion': '20'}, 'spec': {
            'replicas': 2, 'template': {'spec': {'serviceAccountName': 'traefik',
            'affinity': {'existing': 'placement'}, 'containers': [{'name': 'traefik',
            'args': ['--providers.kubernetesingress.namespaces=etch-sso,airflow,headlamp,tailwind-internal']}]}}}}
        for dry_run in (True, False):
            with self.subTest(dry_run=dry_run), patch.object(manage, 'run', side_effect=[
                    json.dumps(current), '', '', '']) as run, patch.object(manage.tls, 'check') as check:
                manage.connect_ingress(settings(), 'prod', content, dry_run=dry_run)
            calls = [call.args[0] for call in run.call_args_list]
            self.assertTrue(all('prod' in call for call in calls))
            check.assert_called_once_with(['kubectl', '--context', 'prod'], 'portal.test', current)
            self.assertFalse(any('secret' in call for call in calls))
            patch_call = next(call for call in calls if 'patch' in call)
            changes = json.loads(patch_call[patch_call.index('--patch') + 1])
            self.assertEqual(changes[0], {'op': 'test', 'path': '/metadata/resourceVersion', 'value': '20'})
            self.assertEqual(changes[1]['path'], '/spec/template/spec/containers/0/args')
            self.assertIn('--providers.kubernetesingress.namespaces=etch-sso,airflow,headlamp,tailwind-internal,monitoring',
                          changes[1]['value'])
            self.assertEqual('--dry-run=server' in patch_call, dry_run)
            self.assertEqual(any('rollout' in call for call in calls), not dry_run)

    def test_missing_common_tls_stops_before_rbac_or_controller_mutation(self):
        content = 'kind: Ingress\nspec:\n  ingressClassName: traefik\n  rules:\n    - host: portal.test\n'
        with patch.object(manage, 'run', return_value='{}') as run, \
                patch.object(manage.tls, 'check', side_effect=ValueError('공용 TLS 인증서 없음')), \
                self.assertRaisesRegex(ValueError, '공용 TLS'):
            manage.connect_ingress(settings(), 'prod', content)
        self.assertEqual(run.call_count, 1)
        self.assertNotIn('apply', run.call_args.args[0])

    def test_no_public_ingress_needs_no_controller_or_tls(self):
        with patch.object(manage, 'run') as run:
            manage.connect_ingress(settings(), 'prod', rendered_fixture())
        run.assert_not_called()

    def test_local_volumes_bind_operator_claims_on_selected_worker(self):
        data = settings()
        data['NAMESPACE'] = 'observability'
        resources = manage.storage(data)['items']
        volumes = [item for item in resources if item['kind'] == 'PersistentVolume']
        self.assertEqual(len(volumes), 3)
        for volume in volumes:
            self.assertEqual(volume['spec']['persistentVolumeReclaimPolicy'], 'Retain')
            self.assertEqual(volume['spec']['claimRef']['namespace'], 'observability')
            self.assertEqual(volume['spec']['nodeAffinity']['required']['nodeSelectorTerms'][0]['matchExpressions'][0]['values'], ['worker-one'])
        self.assertEqual(volumes[0]['spec']['claimRef']['name'], 'prometheus-monitoring-prometheus-db-prometheus-monitoring-prometheus-0')
        self.assertEqual(volumes[1]['spec']['claimRef']['name'], 'alertmanager-monitoring-alertmanager-db-alertmanager-monitoring-alertmanager-0')
        values = manage.values(data)
        self.assertEqual(values['prometheus']['prometheusSpec']['storageSpec']['volumeClaimTemplate']['spec']['volumeName'], volumes[0]['metadata']['name'])
        self.assertEqual(values['alertmanager']['alertmanagerSpec']['storage']['volumeClaimTemplate']['spec']['volumeName'], volumes[1]['metadata']['name'])

    def test_existing_operator_blocks_new_install_without_mutation(self):
        calls = []

        def run(args, data=None):
            calls.append(args)
            if 'version' in args:
                return json.dumps({'serverVersion': {'gitVersion': 'v1.30.13'}})
            if 'list' in args:
                return '[]'
            return 'customresourcedefinition/prometheuses.monitoring.coreos.com'

        with patch.object(manage, 'run', run), patch.object(manage, 'render', fake_render), \
                self.assertRaisesRegex(ValueError, '기존 Prometheus Operator'):
            manage.deploy(settings(), 'test-context', Path('chart.tgz'))
        self.assertFalse(any('apply' in call or 'upgrade' in call for call in calls))
        self.assertTrue(all('test-context' in call for call in calls))

    def test_missing_context_never_calls_cluster(self):
        with patch.object(manage, 'run') as run, self.assertRaisesRegex(ValueError, '--context'):
            manage.deploy(settings(), '', Path('chart.tgz'))
        run.assert_not_called()

    def test_unexpected_chart_version_blocks_upgrade(self):
        def run(args, data=None):
            if 'version' in args:
                return json.dumps({'serverVersion': {'gitVersion': 'v1.30.13'}})
            return json.dumps([{'name': 'monitoring', 'chart': 'kube-prometheus-stack-1.0.0'}])
        with patch.object(manage, 'run', run), patch.object(manage, 'render', fake_render), \
                self.assertRaisesRegex(ValueError, 'CRD upgrade'):
            manage.deploy(settings(), 'test-context', Path('chart.tgz'))

    def test_deploy_applies_storage_before_helm_and_waits_for_operator_workloads(self):
        calls = []

        def run(args, data=None):
            calls.append(args)
            if 'version' in args:
                return json.dumps({'serverVersion': {'gitVersion': 'v1.30.13'}})
            if 'list' in args:
                return '[]'
            if 'crd' in args:
                return ''
            if 'nodes' in args:
                return json.dumps({'items': [{'spec': {}, 'status': {'conditions': [{'type': 'Ready', 'status': 'True'}]}}]})
            if 'secret' in args:
                return 'admin-user\nadmin-password\n'
            if 'create' in args:
                return json.dumps({'metadata': {'name': 'monitoring-storage-prepare-test'}})
            return ''

        with patch.object(manage, 'run', run), patch.object(manage, 'render', fake_render):
            manage.deploy(settings(), 'test-context', Path('chart.tgz'))
        apply = next(i for i, call in enumerate(calls) if 'apply' in call)
        install = next(i for i, call in enumerate(calls) if 'upgrade' in call)
        self.assertLess(apply, install)
        prepare = next(i for i, call in enumerate(calls) if 'job/monitoring-storage-prepare-test' in call)
        self.assertLess(prepare, apply)
        self.assertTrue(all('test-context' in call for call in calls))
        self.assertFalse(any('delete' in call or '--atomic' in call for call in calls))
        waits = [call for call in calls if '--for=create' in call]
        self.assertEqual(len(waits), 2)
        self.assertTrue(any('statefulset/prometheus-monitoring-prometheus' in call for call in waits))
        self.assertTrue(any('statefulset/alertmanager-monitoring-alertmanager' in call for call in waits))
        self.assertIn('--wait', calls[install])
        self.assertTrue(any(settings()['GRAFANA_ADMIN_SECRET'] in call for call in calls))

    def test_disabled_services_skip_waits_secret_and_new_storage(self):
        for disabled in ({'alertmanager'}, {'prometheus'}, {'grafana'}, set(manage.VOLUMES)):
            with self.subTest(disabled=disabled):
                calls, applied = [], []
                active = tuple(name for name in manage.VOLUMES if name not in disabled)

                def render(data, directory, chart, values_file=None):
                    return fake_render(data, directory, chart, values_file, active)

                def run(args, data=None):
                    calls.append(args)
                    if 'version' in args:
                        return json.dumps({'serverVersion': {'gitVersion': 'v1.30.13'}})
                    if 'list' in args:
                        return '[]'
                    if 'crd' in args:
                        return ''
                    if 'nodes' in args:
                        return json.dumps({'items': [{'spec': {}, 'status': {'conditions': [{'type': 'Ready', 'status': 'True'}]}}]})
                    if 'secret' in args:
                        self.assertNotIn('grafana', disabled)
                        return 'admin-user\nadmin-password\n'
                    if 'create' in args:
                        return json.dumps({'metadata': {'name': 'monitoring-storage-prepare-test'}})
                    if 'apply' in args:
                        applied.extend(json.loads(Path(args[-1]).read_text())['items'])
                    return ''

                with patch.object(manage, 'run', run), patch.object(manage, 'render', render):
                    manage.deploy(settings(), 'test-context', Path('/chart.tgz'), Path('/override.yaml'))
                waits = [args for args in calls if '--for=create' in args]
                self.assertEqual(len(waits), len(set(active) & {'prometheus', 'alertmanager'}))
                for component in disabled:
                    self.assertFalse(any(any(arg.startswith('statefulset/' + component + '-') for arg in args)
                                         for args in waits))
                    self.assertFalse(any(item['metadata']['name'].endswith('-monitoring-' + component)
                                         for item in applied))
                self.assertEqual(any('secret' in args for args in calls), 'grafana' in active)
                upgrade = next(args for args in calls if 'upgrade' in args)
                self.assertIn(Path('/override.yaml'), upgrade)
                self.assertIn('--wait', upgrade)
                self.assertFalse(any('delete' in args for args in calls))
                self.assertEqual(any('create' in args for args in calls), bool(active))
                if not active:
                    self.assertFalse(any('apply' in args or 'rollout' in args for args in calls))

    def test_custom_operator_names_drive_statefulsets_and_claim_refs(self):
        names = {'prometheus': 'metrics', 'alertmanager': 'alerts'}
        components = manage.rendered_components(rendered_fixture(names=names))
        volumes = {item['metadata']['name']: item for item in manage.storage(settings(), components)['items']}
        self.assertEqual(volumes['monitoring-monitoring-prometheus']['spec']['claimRef']['name'],
                         'prometheus-metrics-db-prometheus-metrics-0')
        self.assertEqual(volumes['monitoring-monitoring-alertmanager']['spec']['claimRef']['name'],
                         'alertmanager-alerts-db-alertmanager-alerts-0')
        calls = []

        def run(args, data=None):
            calls.append(args)
            if 'version' in args:
                return json.dumps({'serverVersion': {'gitVersion': 'v1.30.13'}})
            if 'list' in args:
                return '[]'
            if 'nodes' in args:
                return json.dumps({'items': [{'spec': {}, 'status': {'conditions': [{'type': 'Ready', 'status': 'True'}]}}]})
            if 'secret' in args:
                return 'admin-user\nadmin-password\n'
            if 'create' in args:
                return json.dumps({'metadata': {'name': 'monitoring-storage-prepare-test'}})
            return ''

        with patch.object(manage, 'run', run), patch.object(
                manage, 'render', side_effect=lambda *args: fake_render(*args, names=names)):
            manage.deploy(settings(), 'test-context', Path('/chart.tgz'))
        waits = [args[args.index('--for=create') + 1] for args in calls if '--for=create' in args]
        self.assertEqual(waits, ['statefulset/prometheus-metrics', 'statefulset/alertmanager-alerts'])

    def test_header_parser_ignores_crd_kinds_and_validates_service_metadata(self):
        self.assertEqual(manage.rendered_components(rendered_fixture(components=())), {})
        self.assertEqual(set(manage.rendered_components(rendered_fixture())), set(manage.VOLUMES))
        for malformed in ('kind: Alertmanager\n', 'kind: Alertmanager\nmetadata:\n  name: INVALID\n'):
            with self.subTest(malformed=malformed), self.assertRaises(ValueError):
                manage.rendered_components(malformed)

    def test_render_needs_no_kubectl_or_installed_crds(self):
        data = settings()
        content = rendered_fixture(components=()) + f'\n---\nkind: Deployment\nmetadata:\n  name: operator\n' \
                  f'spec:\n  template:\n    spec:\n      containers:\n        - name: operator\n          image: {data["QUAY_REGISTRY"]}/operator:v1\n'
        with tempfile.TemporaryDirectory() as directory, patch.object(
                manage, 'run', side_effect=['', content]) as run:
            manage.render(data, directory, Path('/chart.tgz'))
            self.assertEqual(json.loads((Path(directory) / 'storage.json').read_text())['items'], [])
            self.assertTrue(all(call.args[0][0] == 'helm' for call in run.call_args_list))

    def test_render_failure_happens_before_any_cluster_lookup(self):
        with patch.object(manage, 'render', side_effect=ValueError('잘못된 최종 렌더')), \
                patch.object(manage, 'run') as run, self.assertRaisesRegex(ValueError, '최종 렌더'):
            manage.deploy(settings(), 'test-context', Path('/chart.tgz'))
        run.assert_not_called()

    def test_ingress_preflight_failure_prevents_storage_and_helm_changes(self):
        calls = []

        def run(args, data=None):
            calls.append(args)
            if 'version' in args:
                return json.dumps({'serverVersion': {'gitVersion': 'v1.30.13'}})
            if 'list' in args:
                return '[]'
            if 'nodes' in args:
                return json.dumps({'items': [{'spec': {}, 'status': {'conditions': [{'type': 'Ready', 'status': 'True'}]}}]})
            if 'secret' in args:
                return 'admin-user\nadmin-password\n'
            return ''

        with patch.object(manage, 'run', run), patch.object(manage, 'render', fake_render), \
                patch.object(manage, 'connect_ingress', side_effect=ValueError('TLS 준비 필요')) as ingress, \
                self.assertRaisesRegex(ValueError, 'TLS 준비'):
            manage.deploy(settings(), 'prod', Path('/chart.tgz'))
        self.assertTrue(ingress.call_args.kwargs['dry_run'])
        self.assertFalse(any('apply' in call or 'upgrade' in call for call in calls))

    def test_storage_job_failure_prevents_pv_and_helm_changes(self):
        calls = []

        def run(args, data=None):
            calls.append(args)
            if 'version' in args:
                return json.dumps({'serverVersion': {'gitVersion': 'v1.30.13'}})
            if 'list' in args:
                return '[]'
            if 'nodes' in args:
                return json.dumps({'items': [{'spec': {}, 'status': {'conditions': [{'type': 'Ready', 'status': 'True'}]}}]})
            if 'secret' in args:
                return 'admin-user\nadmin-password\n'
            if 'create' in args:
                return json.dumps({'metadata': {'name': 'monitoring-storage-prepare-test'}})
            if '--for=condition=complete' in args:
                raise ValueError('폴더 준비 실패')
            return ''

        with patch.object(manage, 'run', run), patch.object(manage, 'render', fake_render), \
                self.assertRaisesRegex(ValueError, '폴더 준비 실패'):
            manage.deploy(settings(), 'prod', Path('/chart.tgz'))
        self.assertFalse(any('apply' in args or 'upgrade' in args for args in calls))

    @unittest.skipUnless(shutil.which('helm'), 'Helm 미설치: 실제 렌더 검사는 별도 실행')
    def test_real_chart_disables_each_optional_component_and_all_together(self):
        try:
            chart = manage.chart_path()
        except ValueError as error:
            if 'chart 준비' in str(error):
                self.skipTest(str(error))
            raise
        for disabled in ({'alertmanager'}, {'prometheus'}, {'grafana'}, set(manage.VOLUMES)):
            with self.subTest(disabled=disabled), tempfile.TemporaryDirectory() as directory:
                override = Path(directory) / 'override.json'
                values = {name: {'enabled': False} for name in disabled}
                if 'prometheus' in disabled:
                    # 고정 chart는 Prometheus 전용 token Secret을 참조하는 감시 대상도 함께 해제해야 한다.
                    values['kubernetesServiceMonitors'] = {'enabled': False}
                override.write_text(json.dumps(values))
                flags = manage.render(settings(), directory, chart, override)
                components = manage.rendered_components((Path(directory) / 'monitoring.yaml').read_text())
                self.assertEqual(set(components), set(manage.VOLUMES) - disabled)
                self.assertEqual(flags[-1], override)
                resources = json.loads((Path(directory) / 'storage.json').read_text())['items']
                volumes = [item for item in resources if item['kind'] == 'PersistentVolume']
                self.assertEqual(len(volumes), len(components))
                self.assertTrue(all(item['spec']['persistentVolumeReclaimPolicy'] == 'Retain' for item in volumes))

    @unittest.skipUnless(shutil.which('helm'), 'Helm 미설치: 실제 렌더 검사는 별도 실행')
    def test_real_chart_custom_cr_names_match_reserved_claims(self):
        try:
            chart = manage.chart_path()
        except ValueError as error:
            if 'chart 준비' in str(error):
                self.skipTest(str(error))
            raise
        with tempfile.TemporaryDirectory() as directory:
            override = Path(directory) / 'override.json'
            override.write_text(json.dumps({'fullnameOverride': 'observability'}))
            manage.render(settings(), directory, chart, override)
            components = manage.rendered_components((Path(directory) / 'monitoring.yaml').read_text())
            self.assertEqual(components['prometheus']['name'], 'observability-prometheus')
            self.assertEqual(components['alertmanager']['name'], 'observability-alertmanager')
            volumes = json.loads((Path(directory) / 'storage.json').read_text())['items']
            prometheus = next(item for item in volumes if item['metadata']['name'] == 'monitoring-monitoring-prometheus')
            self.assertEqual(prometheus['spec']['claimRef']['name'],
                             'prometheus-observability-prometheus-db-prometheus-observability-prometheus-0')

    @unittest.skipUnless(shutil.which('helm'), 'Helm 미설치: 실제 렌더 검사는 별도 실행')
    def test_real_chart_mirrors_all_images_and_keeps_persistence(self):
        try:
            chart = manage.chart_path()
        except ValueError as error:
            if 'chart 준비' in str(error):
                self.skipTest(str(error))
            raise
        data = settings()
        data['IMAGE_PULL_SECRET'] = 'registry-login'
        with tempfile.TemporaryDirectory() as directory:
            manage.render(data, directory, chart)
            images = (Path(directory) / 'images.txt').read_text().splitlines()
            self.assertGreaterEqual(len(images), 9)
            self.assertTrue(all(image.startswith('mirror.test/') for image in images))
            self.assertTrue(any('prometheus-config-reloader' in image for image in images))
            self.assertTrue(any('kube-webhook-certgen' in image for image in images))
            self.assertIn(data['DOCKER_REGISTRY'] + '/library/busybox:1.37.0', images)
            rendered = (Path(directory) / 'monitoring.yaml').read_text()
            self.assertIn('claimName: monitoring-grafana', rendered)
            self.assertIn('volumeName: monitoring-monitoring-prometheus', rendered)
            self.assertIn('volumeName: monitoring-monitoring-alertmanager', rendered)
            self.assertIn('name: registry-login', rendered)
            self.assertEqual(rendered.count('kind: Ingress\n'), 3)
            self.assertEqual(manage.ingress_hosts(data, rendered), {data['INGRESS_HOST']})
            for component in manage.VOLUMES:
                self.assertIn(f'path: /{component}', rendered)
            self.assertIn('root_url = https://etch.samsungds.net/grafana/', rendered)
            self.assertIn('serve_from_sub_path = true', rendered)
            for component in ('prometheus', 'alertmanager'):
                self.assertIn(f'routePrefix: "/{component}"', rendered)
                self.assertIn(f'path: "/{component}/metrics"', rendered)
                self.assertIn(f'url: http://monitoring-{component}.monitoring:', rendered)
            self.assertIn('pathPrefix: "/alertmanager"', rendered)
            self.assertNotIn('admin-password:', rendered)


if __name__ == '__main__':
    unittest.main()
