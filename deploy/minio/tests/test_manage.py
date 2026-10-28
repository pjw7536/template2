"""공용 MinIO의 독립 소유권·데이터 보존·라우팅 변경 순서를 검증한다."""

import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/manage.py'
spec = importlib.util.spec_from_file_location('minio_manage', SCRIPT)
manage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manage)


def settings():
    """실제 운영 계정은 사용하지 않는 독립 입력이다."""
    values = manage.settings(manage.BASE / 'env/prod.env')
    values.update(MINIO_ROOT_USER='fixture-user', MINIO_ROOT_PASSWORD='fixture-password',
                  MINIO_IMAGE='mirror.test/minio@sha256:' + 'a' * 64,
                  MINIO_CLIENT_IMAGE='mirror.test/mc:release', IMAGE_PULL_SECRET='registry-login')
    return values


class MinioTests(unittest.TestCase):
    def test_public_render_uses_common_namespace_and_contains_no_credentials(self):
        values = settings()
        items = manage.manifests(values)
        self.assertTrue(all(item['metadata']['namespace'] == 'minio' for item in items))
        rendered = json.dumps(items)
        self.assertNotIn(values['MINIO_ROOT_PASSWORD'], rendered)
        self.assertNotIn(values['MINIO_ROOT_USER'], rendered)
        for item in items:
            if item['kind'] in ('Deployment', 'Job'):
                pod = item['spec']['template']['spec']
                self.assertEqual(pod['imagePullSecrets'], [{'name': 'registry-login'}])
                self.assertTrue(pod['containers'][0]['image'].startswith('mirror.test/'))
        self.assertEqual({item['spec']['rules'][0]['http']['paths'][0]['path']
                          for item in items if item['kind'] == 'Ingress'}, {'/minio', '/minio-console'})

    def test_portal_overlay_no_longer_owns_storage_or_minio_ingress(self):
        root = manage.BASE.parents[1]
        portal = subprocess.check_output(['kubectl', 'kustomize', 'deploy/portal/k8s/overlays/prod'], cwd=root, text=True)
        self.assertNotIn('name: minio\n', portal)
        self.assertNotIn('name: minio-console\n', portal)
        self.assertNotIn('name: minio-data\n', portal)

    def test_missing_duplicate_and_floating_images_are_rejected(self):
        original = (manage.BASE / 'env/prod.env').read_text()
        for content in (original + '\nNODE_NAME=duplicate\n', original.replace('STORAGE_SIZE=10Gi', ''),
                        original.replace('2025.7.21-debian-12-r3', 'latest')):
            with self.subTest(), tempfile.TemporaryDirectory() as directory:
                env = Path(directory) / 'input.env'
                env.write_text(content)
                with self.assertRaises(ValueError):
                    manage.settings(env)

    def test_bucket_list_is_an_input_and_not_hardcoded_in_bootstrap(self):
        job = next(item for item in manage.manifests(settings()) if item['kind'] == 'Job')
        command = job['spec']['template']['spec']['containers'][0]['command'][-1]
        self.assertIn('MINIO_BUCKETS', command)
        self.assertNotIn('local/emails', command)
        self.assertNotIn('local/profile', command)

    def test_server_starts_native_binary_with_existing_data_path_and_uid(self):
        """배포판 wrapper 차이로 server 인자가 실행 파일로 해석되는 회귀를 방지한다."""
        item = next(item for item in manage.manifests(settings()) if item['kind'] == 'Deployment')
        container = item['spec']['template']['spec']['containers'][0]
        self.assertEqual(container['command'], ['minio'])
        self.assertEqual(container['args'], ['server', '/data', '--console-address', ':9001'])
        self.assertEqual(container['securityContext']['runAsUser'], 0)
        self.assertEqual(container['volumeMounts'], [{'name': 'data', 'mountPath': '/data'}])
        self.assertEqual(item['spec']['template']['spec']['volumes'][0]['persistentVolumeClaim']['claimName'], 'minio-data')

    def test_legacy_deployment_blocks_changes_and_preserves_old_data(self):
        with patch.object(manage, 'run', return_value='deployment.apps/minio') as run, \
                self.assertRaisesRegex(ValueError, '기존 tailwind-internal'):
            manage.deploy(settings(), 'prod')
        self.assertEqual(run.call_count, 1)
        self.assertNotIn('delete', run.call_args.args[0])

    def test_missing_tls_stops_before_controller_or_secret_changes(self):
        with patch.object(manage, 'run', return_value='Opaque password') as run, \
                self.assertRaisesRegex(ValueError, 'TLS Secret'):
            manage.routing_plan(['kubectl', '--context', 'prod'], settings())
        self.assertEqual(run.call_count, 1)

    def test_ingress_patch_only_adds_common_namespace_and_checks_resource_version(self):
        current = {'metadata': {'namespace': 'etch-sso', 'resourceVersion': '50'}, 'spec': {
            'replicas': 2, 'template': {'spec': {'serviceAccountName': 'traefik',
            'affinity': {'keep': 'vip-placement'},
            'volumes': [{'name': 'middlewares', 'configMap': {'name': 'paths-hash'}}],
            'containers': [{'name': 'traefik', 'args': ['--providers.file.directory=/etc/traefik/dynamic',
                '--providers.kubernetesingress.namespaces=etch-sso,headlamp,tailwind-internal,airflow'],
                'volumeMounts': [{'name': 'middlewares', 'mountPath': '/etc/traefik/dynamic'}]}]}}}}
        before = json.dumps(current)
        responses = ['kubernetes.io/tls tls.crt tls.key', json.dumps(current),
                     json.dumps({'data': {'paths.yaml': 'minio-api:\nminio-console:'}})]
        with patch.object(manage, 'run', side_effect=responses):
            access, changes = manage.routing_plan(['kubectl', '--context', 'prod'], settings())
        self.assertEqual(json.dumps(current), before)
        self.assertTrue(all(item['metadata']['namespace'] == 'minio' for item in access))
        self.assertEqual(changes[0], {'op': 'test', 'path': '/metadata/resourceVersion', 'value': '50'})
        self.assertEqual(changes[1]['path'], '/spec/template/spec/containers/0/args')
        self.assertIn('--providers.kubernetesingress.namespaces=etch-sso,headlamp,tailwind-internal,airflow,minio', changes[1]['value'])

    def deployment_calls(self, *, existing=False, fail_preflight=False, check_only=False, available_pv=True,
                         pv_phase='Bound', pv_uid='current-claim'):
        calls = []

        def run(args, data=None, sensitive=False):
            calls.append((args, data, sensitive))
            if '-n' in args and args[args.index('-n') + 1] == 'tailwind-internal':
                return ''
            if 'nodes' in args:
                return json.dumps({'items': [{'spec': {}, 'status': {'conditions': [{'type': 'Ready', 'status': 'True'}]}}]})
            if 'pv' in args:
                return json.dumps({'items': [{'metadata': {'name': 'data'}, 'spec': {'claimRef': {
                    'namespace': 'minio', 'name': 'minio-data', 'uid': pv_uid}}, 'status': {'phase': pv_phase}}] if available_pv else []})
            if 'pvc' in args:
                return json.dumps({'metadata': {'uid': 'current-claim'}, 'spec': {'storageClassName': ''}})
            if 'get' in args and 'deployment' in args:
                return 'deployment.apps/minio' if existing else ''
            if 'get' in args and 'job' in args:
                return 'job.batch/minio-init' if existing else ''
            return ''

        def connect(*args, **kwargs):
            if fail_preflight:
                raise ValueError('권한 검사 실패')

        with patch.object(manage, 'run', run), patch.object(manage, 'routing_plan', return_value=([], [])), \
                patch.object(manage, 'connect', connect):
            if fail_preflight or not available_pv or pv_phase == 'Released' or pv_uid != 'current-claim':
                with self.assertRaises(ValueError):
                    manage.deploy(settings(), 'prod', check_only=check_only)
            else:
                manage.deploy(settings(), 'prod', check_only=check_only)
        return calls

    def test_preflight_failure_and_missing_pv_prevent_all_changes(self):
        for kwargs in ({'fail_preflight': True}, {'available_pv': False}, {'check_only': True}):
            calls = self.deployment_calls(**kwargs)
            self.assertFalse(any('apply' in args or 'delete' in args or 'restart' in args for args, _, _ in calls))

    def test_new_install_waits_for_server_before_job_and_never_deletes_pvc(self):
        calls = self.deployment_calls()
        rollout = next(i for i, (args, _, _) in enumerate(calls) if 'rollout' in args)
        job_apply = next(i for i, (args, data, _) in enumerate(calls) if data and
                         any(item['kind'] == 'Job' for item in json.loads(data)['items']))
        self.assertLess(rollout, job_apply)
        self.assertTrue(all('prod' in args for args, _, _ in calls))
        self.assertFalse(any('delete' in args for args, _, _ in calls))
        secrets = [data for _, data, sensitive in calls if sensitive]
        self.assertEqual(len(secrets), 1)
        self.assertTrue(all('fixture-password' not in ' '.join(args) for args, _, _ in calls))

    def test_redeploy_reuses_bound_volume_and_does_not_replace_existing_job(self):
        calls = self.deployment_calls(existing=True)
        self.assertTrue(any('restart' in args for args, _, _ in calls))
        self.assertFalse(any(data and any(item['kind'] == 'Job' for item in json.loads(data)['items'])
                             for _, data, _ in calls))

    def test_released_pv_and_previous_claim_uid_require_manual_recovery(self):
        for kwargs in ({'pv_phase': 'Released'}, {'pv_uid': 'previous-claim'}):
            calls = self.deployment_calls(**kwargs)
            self.assertFalse(any('apply' in args or 'delete' in args or 'patch' in args for args, _, _ in calls))


if __name__ == '__main__':
    unittest.main()
