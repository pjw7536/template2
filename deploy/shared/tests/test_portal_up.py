"""Portal 단일 배포 타깃의 migration 판단과 실행 순서를 검증한다."""

import datetime
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location('portal_up', ROOT / 'deploy/portal/scripts/up.py')
portal = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(portal)
IMAGES = {('api', 'api'): 'store/api:2', ('portal-migrate', 'migrate'): 'store/api:2'}
NOW = datetime.datetime(2026, 11, 20, 1, 2, 3, tzinfo=datetime.timezone.utc)


def deployment(image, replicas=2, saved=None):
    annotations = {portal.REPLICAS_ANNOTATION: str(saved)} if saved is not None else {}
    return json.dumps({'metadata': {'annotations': annotations},
                       'spec': {'replicas': replicas, 'selector': {'matchLabels': {'app': 'api'}}, 'template': {'spec': {'containers': [{'name': 'api', 'image': image}]}}}})


class PortalUpTests(unittest.TestCase):
    def run_up(self, live=None, job=None, check_only=False, force=False, fail=None, retry=False):
        """kubectl·셸 호출을 기록하고 마지막 인자가 fail인 호출만 실패시킨다. 기록은 실패해도 self.calls에 남는다."""
        calls = self.calls = []

        def run(args, data=None, env=None):
            args = [str(arg) for arg in args]
            calls.append((args, env or {}))
            if fail and args[-1] == fail:
                raise ValueError('단계 실패')
            if args[-4:] == ['namespace', 'tailwind-internal', '--ignore-not-found', '-o'] or 'namespace' in args and 'get' in args:
                return 'namespace/tailwind-internal' if live is not None or job is not None else ''
            if 'deployment' in args and 'get' in args:
                return live or ''
            if 'job' in args and 'get' in args:
                return json.dumps({'status': job}) if job is not None else ''
            return ''

        with patch.object(portal, 'run', run), patch.object(portal, 'rendered_images', return_value=IMAGES), \
                patch.object(portal, 'render', return_value=[{'kind': 'Deployment', 'metadata': {'name': 'api'}}]):
            portal.start('prod', 'api.env', 'web.env', check_only, force, NOW, retry_failed=retry)
        return calls

    def phases(self, calls):
        return [args[-1] for args, env in calls if any('migration-job.sh' in arg for arg in args)]

    def test_fresh_install_migrates_without_stopping_api_or_precheck(self):
        calls = self.run_up()
        self.assertEqual(self.phases(calls), ['migrate', 'post-migration'])
        flat = [' '.join(args) for args, env in calls]
        self.assertFalse(any('scale' in line or 'rollout restart' in line or 'delete' in line for line in flat))
        apply = next(i for i, line in enumerate(flat) if 'apply -f -' in line)
        migrate = next(i for i, (args, env) in enumerate(calls) if args[-1] == 'migrate')
        self.assertLess(migrate, apply)
        self.assertTrue(any('manage.py connect --context prod --app portal' in line for line in flat))
        checks = [env.get('PORTAL_CHECK_JOB') for args, env in calls if args[-1] == 'post-migration']
        self.assertEqual(checks, ['portal-postcheck-20261120010203'])

    def test_image_change_stops_api_runs_precheck_and_restores_replicas(self):
        calls = self.run_up(live=deployment('store/api:1', 3), job={'succeeded': 1})
        flat = [' '.join(args) for args, env in calls]
        self.assertEqual(self.phases(calls), ['pre-migration', 'migrate', 'post-migration'])
        stop = next(i for i, line in enumerate(flat) if '--replicas=0' in line)
        delete = next(i for i, line in enumerate(flat) if 'delete job portal-migrate' in line)
        restore = next(i for i, line in enumerate(flat) if '--replicas=3' in line)
        apply = next(i for i, line in enumerate(flat) if 'apply -f -' in line)
        gone = next(i for i, line in enumerate(flat) if 'wait --for=delete pod -l app=api' in line)
        precheck = next(i for i, (args, env) in enumerate(calls) if args[-1] == 'pre-migration')
        self.assertLess(stop, gone)
        self.assertLess(gone, precheck)
        self.assertLess(stop, delete)
        self.assertLess(delete, apply)
        self.assertLess(apply, restore)
        # 지우는 것은 끝난 migration Job뿐이다. Pod 종료 대기(wait --for=delete)는 삭제가 아니다.
        self.assertEqual([line for line in flat if ' delete ' in line], [next(line for line in flat if 'delete job portal-migrate' in line)])
        # 중지 전 수를 기록하고 복원 뒤 지운다. web·edge-nginx는 Secret 반영을 위해 다시 시작한다.
        record = next(i for i, line in enumerate(flat) if f'{portal.REPLICAS_ANNOTATION}=3' in line)
        clear = next(i for i, line in enumerate(flat) if f'{portal.REPLICAS_ANNOTATION}-' in line)
        self.assertLess(record, stop)
        self.assertLess(restore, clear)
        self.assertTrue(any('rollout restart deployment/web deployment/edge-nginx' in line for line in flat))
        self.assertFalse(any('rollout restart deployment/api' in line for line in flat))

    def test_same_image_skips_migration_and_restarts_for_secret_changes(self):
        calls = self.run_up(live=deployment('store/api:2'))
        flat = [' '.join(args) for args, env in calls]
        self.assertEqual(self.phases(calls), [])
        self.assertTrue(any('rollout restart deployment/api deployment/web deployment/edge-nginx' in line for line in flat))
        self.assertFalse(any('scale' in line for line in flat))
        self.assertEqual(self.phases(self.run_up(live=deployment('store/api:2'), force=True)),
                         ['pre-migration', 'migrate', 'post-migration'])

    def test_active_or_failed_migration_job_blocks_before_any_change(self):
        for status, message in (({'active': 1}, '진행 중'), ({'failed': 1}, 'PORTAL_RETRY_MIGRATE=1')):
            with self.subTest(status=status), self.assertRaisesRegex(ValueError, message):
                self.run_up(live=deployment('store/api:1'), job=status)

    def test_retry_after_failure_resumes_and_restores_recorded_replicas(self):
        # 이전 실행이 API를 멈춘 채 실패했다: replica 0, 기록 3, 실패한 Job이 남아 있다.
        calls = self.run_up(live=deployment('store/api:2', replicas=0, saved=3), job={'failed': 1}, retry=True)
        flat = [' '.join(args) for args, env in calls]
        self.assertEqual(self.phases(calls), ['pre-migration', 'migrate', 'post-migration'])
        self.assertTrue(any('delete job portal-migrate' in line for line in flat))
        self.assertTrue(any('--replicas=3' in line for line in flat))
        self.assertTrue(any(f'{portal.REPLICAS_ANNOTATION}-' in line for line in flat))

    def test_check_only_never_changes_cluster(self):
        calls = self.run_up(live=deployment('store/api:1'), check_only=True)
        flat = [' '.join(args) for args, env in calls]
        self.assertFalse(any(word in line for line in flat for word in ('apply', 'scale', 'delete', 'migration-job.sh', 'restart')))

    def test_auto_tag_is_replaced_by_source_tag_and_pinned_tags_are_kept(self):
        items = [{'kind': 'Deployment', 'metadata': {'name': name}, 'spec': {'template': {'spec': {
                     'initContainers': [{'name': 'wait', 'image': 'mirror/busybox:1'}],
                     'containers': [{'name': name, 'image': image}]}}}}
                 for name, image in (('api', 'store.test/portal-api:auto'), ('web', 'store.test/portal-web:auto'),
                                     ('edge-nginx', 'mirror/nginx:1.27-alpine'), ('pinned', 'store.test/portal-api:2.0'))]
        with patch.object(portal.runtime, 'render_json', return_value=items), \
                patch.object(portal.image_registry, 'source_tag', side_effect=lambda root, trees, files: 'tag-' + trees[0].rsplit('/', 1)[-1]):
            rendered = portal.render(['kubectl'], portal.OVERLAY)
        images = [item['spec']['template']['spec']['containers'][0]['image'] for item in rendered]
        self.assertEqual(images, ['store.test/portal-api:tag-api', 'store.test/portal-web:tag-web',
                                  'mirror/nginx:1.27-alpine', 'store.test/portal-api:2.0'])
        with patch.object(portal.runtime, 'render_json', return_value=[items[0]]), \
                patch.dict(portal.os.environ, {'PORTAL_IMAGE_TAG': 'release-7'}):
            items[0]['spec']['template']['spec']['containers'][0]['image'] = 'store.test/portal-api:auto'
            self.assertEqual(portal.render(['kubectl'], portal.OVERLAY)[0]['spec']['template']['spec']['containers'][0]['image'],
                             'store.test/portal-api:release-7')

    def test_failed_migration_reports_stopped_api_and_skips_apply(self):
        for phase in ('migrate', 'post-migration'):
            with self.subTest(phase=phase), \
                    self.assertRaisesRegex(ValueError, r'API는 중지 상태입니다\(이전 replica 2\).*PORTAL_RETRY_MIGRATE=1'):
                self.run_up(live=deployment('store/api:1'), fail=phase)

    def test_failure_before_migration_restores_api(self):
        with self.assertRaisesRegex(ValueError, r'migration 전 단계 실패.*DB는 바뀌지 않았고 API를 replica 2') as raised:
            self.run_up(live=deployment('store/api:1'), fail='pre-migration')
        self.assertNotIn('PORTAL_RETRY_MIGRATE', str(raised.exception))
        flat = [' '.join(args) for args, env in self.calls]
        stop = next(i for i, line in enumerate(flat) if '--replicas=0' in line)
        restore = next(i for i, line in enumerate(flat) if '--replicas=2' in line)
        self.assertLess(stop, restore)
        self.assertTrue(any(f'{portal.REPLICAS_ANNOTATION}-' in line for line in flat))
        self.assertEqual(self.phases(self.calls), ['pre-migration'])
        self.assertFalse(any('apply -f -' in line for line in flat))

    def test_failure_before_migration_keeps_api_stopped_when_resuming(self):
        # 이전 migration이 도중에 끝난 뒤의 재시도는 DB 상태를 알 수 없으므로 자동 복원하지 않는다.
        with self.assertRaisesRegex(ValueError, r'API는 중지 상태입니다\(이전 replica 3\)'):
            self.run_up(live=deployment('store/api:2', replicas=0, saved=3), job={'failed': 1}, retry=True, fail='pre-migration')
        self.assertFalse(any('--replicas=3' in ' '.join(args) for args, env in self.calls))


if __name__ == '__main__':
    unittest.main()
