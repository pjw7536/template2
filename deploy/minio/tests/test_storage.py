"""MinIO 저장소 자동 준비와 기존 볼륨·데이터 보존을 검증한다."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_manage import manage, settings


def node(values):
    """hostname label이 실제 노드 이름과 다른 Worker다."""
    return {'metadata': {'name': 'actual-node-name', 'labels': {'kubernetes.io/hostname': values['NODE_NAME']}},
            'spec': {}, 'status': {'conditions': [{'type': 'Ready', 'status': 'True'}]}}


def claim(name='custom-existing-pv'):
    """기존 데이터가 결합된 PVC다."""
    return {'metadata': {'uid': 'current-claim', 'annotations': {'pv.kubernetes.io/bind-completed': 'yes'}},
            'spec': {'volumeName': name, 'storageClassName': '', 'resources': {'requests': {'storage': '10Gi'}}},
            'status': {'phase': 'Bound'}}


def volume(values, name='custom-existing-pv'):
    """현재 PVC에 결합된 PV다."""
    result = manage.static_volume({**values, 'VOLUME_NAME': name})
    result['spec']['claimRef']['uid'] = 'current-claim'
    result['status'] = {'phase': 'Bound'}
    return result


class StorageTests(unittest.TestCase):
    def test_old_env_gets_default_path_and_invalid_paths_are_rejected(self):
        original = (manage.BASE / 'env/prod.env').read_text()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'input.env'
            path.write_text('\n'.join(line for line in original.splitlines() if not line.startswith('MINIO_DATA_HOST_PATH=')))
            self.assertEqual(manage.settings(path)['MINIO_DATA_HOST_PATH'], '/data/minio')
            for invalid in ('/', 'relative/path', '/data/../other', '/data/minio/'):
                path.write_text(original.replace('MINIO_DATA_HOST_PATH=/data/minio', 'MINIO_DATA_HOST_PATH=' + invalid))
                with self.subTest(path=invalid), self.assertRaisesRegex(ValueError, 'MINIO_DATA_HOST_PATH'):
                    manage.settings(path)

    def test_new_static_render_has_reserved_pv_and_explicit_pvc_binding(self):
        values = {**settings(), 'NODE_NAME': 'storage-worker', 'MINIO_DATA_HOST_PATH': '/mnt/objects/minio',
                  'VOLUME_NAME': 'chosen-pv', 'STORAGE_SIZE': '2Ti'}
        items = manage.manifests(values)
        pv = next(item for item in items if item['kind'] == 'PersistentVolume')
        pvc = next(item for item in items if item['kind'] == 'PersistentVolumeClaim')
        self.assertNotIn('namespace', pv['metadata'])
        self.assertEqual(pv['metadata']['name'], pvc['spec']['volumeName'])
        self.assertEqual(pv['spec']['claimRef'], {'namespace': 'minio', 'name': 'minio-data'})
        self.assertEqual(pv['spec']['local']['path'], '/mnt/objects/minio')
        self.assertEqual(pv['spec']['capacity']['storage'], '2Ti')
        self.assertEqual(pv['spec']['persistentVolumeReclaimPolicy'], 'Retain')
        self.assertEqual(pv['spec']['nodeAffinity']['required']['nodeSelectorTerms'][0]['matchExpressions'][0]['values'],
                         ['storage-worker'])

    def test_new_storage_is_planned_without_creating_any_resources(self):
        values = settings()
        with patch.object(manage, 'run', return_value='') as run:
            effective, pending = manage.storage_plan(['kubectl'], values, node(values), None)
        self.assertEqual(effective['VOLUME_NAME'], 'minio-data-pv')
        self.assertEqual(pending['spec']['local']['path'], values['MINIO_DATA_HOST_PATH'])
        self.assertTrue(all(call.args[0][1] == 'get' for call in run.call_args_list))

    def test_existing_bound_pv_name_and_all_metadata_are_preserved(self):
        values = settings()
        pv = volume(values)
        pv['metadata']['annotations'] = {'operator/preserve': 'yes'}
        original = deepcopy(pv)
        with patch.object(manage, 'run', return_value=json.dumps(pv)) as run:
            effective, pending = manage.storage_plan(['kubectl'], values, node(values), claim())
        self.assertEqual(effective['VOLUME_NAME'], 'custom-existing-pv')
        self.assertIsNone(pending)
        self.assertEqual(pv, original)
        self.assertEqual(run.call_count, 1)
        self.assertIn('custom-existing-pv', run.call_args.args[0])

    def test_mismatched_existing_pv_is_rejected_before_mutation(self):
        values = settings()
        cases = []
        def changed(change):
            pv = volume(values)
            change(pv)
            cases.append(pv)
        changed(lambda pv: pv['spec']['local'].update(path='/data/other'))
        changed(lambda pv: pv['spec']['capacity'].update(storage='1Gi'))
        changed(lambda pv: pv['spec'].update(storageClassName='other'))
        changed(lambda pv: pv['spec'].update(volumeMode='Block'))
        changed(lambda pv: pv['spec'].update(accessModes=['ReadOnlyMany']))
        changed(lambda pv: pv['spec']['claimRef'].update(namespace='another-app'))
        changed(lambda pv: pv['spec']['claimRef'].update(uid='previous-claim'))
        changed(lambda pv: pv['status'].update(phase='Released'))
        changed(lambda pv: pv['status'].update(phase='Failed'))
        changed(lambda pv: pv['metadata'].update(deletionTimestamp='2026-10-28T00:00:00Z'))
        changed(lambda pv: pv['spec']['nodeAffinity']['required']['nodeSelectorTerms'][0]['matchExpressions'][0].update(values=['other-worker']))
        for pv in cases:
            with self.subTest(pv=pv), patch.object(manage, 'run', return_value=json.dumps(pv)) as run, self.assertRaises(ValueError):
                manage.storage_plan(['kubectl'], values, node(values), claim())
            self.assertEqual(run.call_count, 1)
            self.assertIn('get', run.call_args.args[0])

    def test_missing_bound_pv_or_lost_pvc_never_gets_replaced_with_empty_storage(self):
        values = settings()
        for current in (claim(), {**claim(), 'status': {'phase': 'Lost'}},
                        {**claim(), 'status': {'phase': 'Pending'}}):
            with self.subTest(claim=current), patch.object(manage, 'run', return_value='') as run, self.assertRaises(ValueError):
                manage.storage_plan(['kubectl'], values, node(values), current)
            self.assertFalse(any('create' in call.args[0] for call in run.call_args_list))

    def test_conflicting_pvc_inputs_are_rejected_before_pv_lookup(self):
        for changes in ({'VOLUME_NAME': 'different'}, {'STORAGE_CLASS_NAME': 'dynamic'}, {'STORAGE_SIZE': '20Gi'}):
            with self.subTest(changes=changes), patch.object(manage, 'run') as run, self.assertRaises(ValueError):
                manage.storage_plan(['kubectl'], {**settings(), **changes}, node(settings()), claim())
            run.assert_not_called()

    def test_equivalent_quantity_units_do_not_trigger_capacity_changes(self):
        values = settings()
        pv = volume(values)
        pv['spec']['capacity']['storage'] = '10240Mi'
        with patch.object(manage, 'run', return_value=json.dumps(pv)):
            _, pending = manage.storage_plan(['kubectl'], values, node(values), claim())
        self.assertIsNone(pending)
        self.assertEqual(manage.storage_bytes('1Ti'), manage.storage_bytes('1024Gi'))

    def test_dynamic_class_skips_static_pv_and_keeps_existing_pvc_binding(self):
        values = {**settings(), 'STORAGE_CLASS_NAME': 'company-csi'}
        with patch.object(manage, 'run', return_value='storageclass/company-csi') as run:
            effective, pending = manage.storage_plan(['kubectl'], values, node(values), None)
        self.assertIsNone(pending)
        self.assertEqual(run.call_count, 1)
        self.assertIn('storageclass', run.call_args.args[0])
        items = manage.manifests(effective)
        self.assertFalse(any(item['kind'] == 'PersistentVolume' for item in items))
        self.assertNotIn('volumeName', next(item for item in items if item['kind'] == 'PersistentVolumeClaim')['spec'])

    def test_directory_job_reuses_mirrored_image_without_application_credentials(self):
        values = settings()
        job = manage.storage_job(values)
        pod = job['spec']['template']['spec']
        self.assertEqual(pod['nodeSelector']['kubernetes.io/hostname'], values['NODE_NAME'])
        self.assertEqual(pod['containers'][0]['image'], values['MINIO_CLIENT_IMAGE'])
        self.assertEqual(pod['imagePullSecrets'], [{'name': values['IMAGE_PULL_SECRET']}])
        self.assertFalse(pod['automountServiceAccountToken'])
        self.assertNotIn('envFrom', pod['containers'][0])
        self.assertEqual(pod['volumes'][0]['hostPath'], {'path': values['MINIO_DATA_HOST_PATH'], 'type': 'DirectoryOrCreate'})
        existing = manage.storage_job(values, create_directory=False)
        self.assertEqual(existing['spec']['template']['spec']['volumes'][0]['hostPath']['type'], 'Directory')
        rendered = json.dumps(job)
        for secret in (values['MINIO_ROOT_USER'], values['MINIO_ROOT_PASSWORD']):
            self.assertNotIn(secret, rendered)
        for operation in ('chmod', 'chown', 'rm ', 'mkfs'):
            self.assertNotIn(operation, pod['containers'][0]['command'][-1])
        self.assertEqual(job['spec']['ttlSecondsAfterFinished'], 600)

    def test_directory_failure_and_concurrent_pv_creation_stop_storage_setup(self):
        values = settings()
        pending = manage.static_volume(values)
        for failed_stage in ('wait', 'pv-create'):
            calls = []
            def run(args, data=None, sensitive=False):
                calls.append((args, data))
                if 'wait' in args:
                    if failed_stage == 'wait':
                        raise ValueError('폴더 준비 실패')
                    return ''
                body = json.loads(data)
                if body['kind'] == 'Job':
                    return json.dumps({'metadata': {'name': 'prepare-test'}})
                raise ValueError('동시 PV 생성 충돌')
            with self.subTest(stage=failed_stage), patch.object(manage, 'run', side_effect=run), self.assertRaises(ValueError):
                manage.prepare_storage(['kubectl'], values, pending)
            self.assertFalse(any('apply' in args or 'delete' in args for args, _ in calls))
            creates = [json.loads(data) for args, data in calls if data]
            self.assertEqual(len(creates), 1 if failed_stage == 'wait' else 2)


class DeploymentStorageTests(unittest.TestCase):
    def run_deploy(self, *, check_only=False, namespace_exists=False, dynamic=False, fail_job=False, fail_tls=False):
        values = {**settings(), 'IMAGE_PULL_SECRET': '', 'STORAGE_CLASS_NAME': 'company-csi' if dynamic else ''}
        calls = []
        def run(args, data=None, sensitive=False):
            calls.append((args, data))
            if 'get' in args:
                if 'nodes' in args:
                    return json.dumps({'items': [node(values)]})
                if 'namespace' in args:
                    return 'namespace/minio' if namespace_exists else ''
                return ''
            if 'create' in args and '--dry-run=server' not in args and data:
                if json.loads(data)['kind'] == 'Job':
                    return json.dumps({'metadata': {'name': 'prepare-test'}})
            if 'wait' in args and 'job/prepare-test' in args and fail_job:
                raise ValueError('폴더 준비 실패')
            return ''
        with patch.object(manage, 'run', side_effect=run), patch.object(manage, 'connect'), \
                patch.object(manage, 'routing_plan', side_effect=ValueError('공용 TLS 없음') if fail_tls else None,
                             return_value=([], [])):
            if fail_job or fail_tls:
                with self.assertRaises(ValueError):
                    manage.deploy(values, 'prod', check_only=check_only)
            else:
                manage.deploy(values, 'prod', check_only=check_only)
        return calls

    def test_fresh_check_with_missing_namespace_and_pv_changes_nothing(self):
        for exists in (True, False):
            calls = self.run_deploy(check_only=True, namespace_exists=exists)
            self.assertFalse(any('apply' in args or 'delete' in args or
                                 'create' in args and '--dry-run=server' not in args for args, _ in calls))

    def test_namespace_then_directory_then_pv_then_application_order(self):
        calls = self.run_deploy()
        written = [json.loads(data) for args, data in calls
                   if data and '--dry-run=server' not in args and ('create' in args or 'apply' in args)]
        self.assertEqual([item['kind'] for item in written[:3]], ['Namespace', 'Job', 'PersistentVolume'])
        self.assertEqual(written[3]['items'][0]['kind'], 'Secret')
        self.assertTrue(all(item['kind'] != 'PersistentVolume' for body in written if body['kind'] == 'List' for item in body['items']))
        self.assertFalse(any('delete' in args for args, _ in calls))

    def test_failed_directory_or_tls_check_never_applies_minio(self):
        for failure in ({'fail_job': True}, {'fail_tls': True}):
            calls = self.run_deploy(**failure)
            self.assertFalse(any('apply' in args or 'restart' in args for args, _ in calls))
            self.assertFalse(any(data and json.loads(data).get('kind') == 'PersistentVolume'
                                 and '--dry-run=server' not in args for args, data in calls))

    def test_dynamic_install_creates_no_local_volume_or_directory_job(self):
        calls = self.run_deploy(dynamic=True)
        written = [json.loads(data) for args, data in calls if data and '--dry-run=server' not in args]
        self.assertFalse(any(item['kind'] == 'PersistentVolume' for item in written))
        self.assertFalse(any(item['kind'] == 'Job' for item in written))
