"""Monitoring의 데이터 보존·미러·중복 설치 차단을 검증한다."""

import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / 'scripts/manage.py'
spec = importlib.util.spec_from_file_location('monitoring_manage', MODULE)
manage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manage)


def settings():
    """실제 비밀값 없이 테스트용 서버 입력을 만든다."""
    result = manage.read_env(manage.EXAMPLE)
    result['NODE_NAME'] = 'worker-one'
    for key in ('DOCKER_REGISTRY', 'QUAY_REGISTRY', 'GHCR_REGISTRY', 'K8S_REGISTRY'):
        result[key] = 'mirror.test/' + key.lower()
    return result


class MonitoringTests(unittest.TestCase):
    """네트워크 호출 없이 필수 배포 경계를 확인한다."""

    def test_placeholder_and_unknown_keys_are_rejected(self):
        with self.assertRaisesRegex(ValueError, '실제 값'):
            manage.validate(manage.read_env(manage.EXAMPLE))
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

        with patch.object(manage, 'run', run), self.assertRaisesRegex(ValueError, '기존 Prometheus Operator'):
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
        with patch.object(manage, 'run', run), self.assertRaisesRegex(ValueError, 'CRD upgrade'):
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
            return ''

        with patch.object(manage, 'run', run), patch.object(manage, 'render', return_value=['-n', 'monitoring']):
            manage.deploy(settings(), 'test-context', Path('chart.tgz'))
        apply = next(i for i, call in enumerate(calls) if 'apply' in call)
        install = next(i for i, call in enumerate(calls) if 'upgrade' in call)
        self.assertLess(apply, install)
        self.assertTrue(all('test-context' in call for call in calls))
        self.assertFalse(any('delete' in call or '--atomic' in call for call in calls))
        waits = [call for call in calls if '--for=create' in call]
        self.assertEqual(len(waits), 3)
        self.assertTrue(any('statefulset/prometheus-monitoring-prometheus' in call for call in waits))

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
            rendered = (Path(directory) / 'monitoring.yaml').read_text()
            self.assertIn('claimName: monitoring-grafana', rendered)
            self.assertIn('volumeName: monitoring-monitoring-prometheus', rendered)
            self.assertIn('volumeName: monitoring-monitoring-alertmanager', rendered)
            self.assertIn('name: registry-login', rendered)
            self.assertNotIn('kind: Ingress\n', rendered)
            self.assertNotIn('admin-password:', rendered)


if __name__ == '__main__':
    unittest.main()
