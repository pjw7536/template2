"""Airflow 배포 진입점의 사전 준비(namespace·OIDC CA·Worker 폴더)와 이미지 tag를 검증한다."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('airflow_up', BASE / 'scripts/up.py')
up = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(up)
SETTINGS = {'NAMESPACE': 'airflow', 'NODE_NAME': 'worker-a', 'POSTGRES_IMAGE': 'mirror/postgres:16', 'IMAGE_PULL_SECRET': '',
            'POSTGRES_HOST_PATH': '/appdata/airflow/postgres', 'POSTGRES_UID': '999', 'POSTGRES_GID': '999',
            'LOGS_HOST_PATH': '/appdata/airflow/logs', 'DAGS_HOST_PATH': '/appdata/airflow/dags',
            'ODBC_HOST_PATH': '/appdata/airflow/odbc', 'AIRFLOW_OIDC_CA_CONFIGMAP': 'airflow-oidc-ca',
            'AIRFLOW_IMAGE_REPOSITORY': 'airflow', 'AIRFLOW_IMAGE_TAG': '3.3.2-release-1'}


class FakeAirflow:
    """manage.py의 run·require만 흉내 낸다."""

    def __init__(self, existing=()):
        self.calls, self.existing = [], set(existing)

    def run(self, args, data=None, sensitive=False):
        self.calls.append((list(map(str, args)), data))
        if 'get' in args and 'namespace' in args:
            return 'namespace/airflow' if 'namespace' in self.existing else ''
        if 'get' in args and 'configmap' in args:
            return 'configmap/airflow-oidc-ca' if 'configmap' in self.existing else ''
        if 'get' in args and 'deployment' in args:
            return 'deployment.apps/airflow-scheduler' if 'scheduler' in self.existing else ''
        if 'create' in args and '-o' in args:
            return json.dumps({'metadata': {'name': 'job-x'}})
        return ''

    @staticmethod
    def require(condition, message):
        if not condition:
            raise ValueError(message)


class HostDirs:
    def __init__(self):
        self.prepared = []

    def prepare(self, run, kube, name, namespace, node, image, directories, pull_secret=''):
        self.prepared.append((name, namespace, node, image, directories))

    def wait_job(self, run, kube, namespace, name):
        self.waited = (namespace, name)


class PrepareTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.ca = Path(self.directory.name) / 'ca.pem'
        self.ca.write_text('PEM')

    def test_directories_follow_container_accounts(self):
        self.assertEqual(up.storage_directories(SETTINGS), [
            ('/appdata/airflow/postgres', '999', '999', '0700'), ('/appdata/airflow/logs', 50000, 0, '0770'),
            ('/appdata/airflow/dags', 0, 0, '0755'), ('/appdata/airflow/odbc', 50000, 0, '0750')])
        external = {**SETTINGS, 'POSTGRES_MODE': 'external', 'ODBC_HOST_PATH': ''}
        self.assertEqual(up.storage_directories(external), [
            ('/appdata/airflow/logs', 50000, 0, '0770'), ('/appdata/airflow/dags', 0, 0, '0755')])

    def test_fresh_install_creates_namespace_ca_and_folders_without_copying_dags(self):
        airflow, dirs = FakeAirflow(), HostDirs()
        up.prepare(airflow, dirs, SETTINGS, 'ctx', self.ca, check_only=False)
        created = [json.loads(data) for args, data in airflow.calls if 'create' in args]
        # DAG 폴더는 만들기만 한다. 이미지에서 파일을 복사하는 Job은 없다.
        self.assertEqual([item['kind'] for item in created], ['Namespace', 'ConfigMap'])
        self.assertEqual(created[1]['data'], {'ca.crt': 'PEM'})
        self.assertEqual(dirs.prepared[0][2:4], ('worker-a', 'mirror/postgres:16'))

    def test_existing_resources_are_not_recreated(self):
        airflow, dirs = FakeAirflow(existing=('namespace', 'configmap')), HostDirs()
        up.prepare(airflow, dirs, SETTINGS, 'ctx', Path('/missing'), check_only=False)
        self.assertFalse(any('create' in args for args, data in airflow.calls))
        self.assertEqual(len(dirs.prepared), 1)

    def test_check_only_marks_pending_configmap_and_requires_ca_file(self):
        airflow, dirs = FakeAirflow(), HostDirs()
        self.assertEqual(up.prepare(airflow, dirs, SETTINGS, 'ctx', self.ca, check_only=True), {'airflow-oidc-ca'})
        self.assertEqual(up.prepare(FakeAirflow(existing=('namespace', 'configmap')), dirs, SETTINGS, 'ctx', self.ca, check_only=True), set())
        self.assertFalse(any('create' in args for args, data in airflow.calls))
        self.assertEqual(dirs.prepared, [])
        with self.assertRaisesRegex(ValueError, 'AIRFLOW_OIDC_CA_FILE'):
            up.prepare(FakeAirflow(), dirs, SETTINGS, 'ctx', Path('/missing'), check_only=True)


class ImageChangeTests(unittest.TestCase):
    def test_reports_first_install_same_and_changed_image(self):
        class Airflow:
            def __init__(self, current):
                self.current = current

            def run(self, args, data=None, sensitive=False):
                return self.current

        self.assertEqual(up.image_change(Airflow(''), SETTINGS, 'ctx'), '이미지 변경: 최초 설치(airflow:3.3.2-release-1)')
        self.assertEqual(up.image_change(Airflow('airflow:3.3.2-release-1'), SETTINGS, 'ctx'), '이미지 변경: 없음')
        self.assertEqual(up.image_change(Airflow('airflow:3.3.2-old'), SETTINGS, 'ctx'),
                         '이미지 변경: 있음(airflow:3.3.2-old → airflow:3.3.2-release-1)')


class MainOrderTests(unittest.TestCase):
    def run_main(self, *extra):
        """실제 클러스터 없이 main의 호출 순서만 기록한다."""
        from unittest.mock import patch
        events, pending = [], []
        self.pending = pending

        class Airflow:
            require = staticmethod(FakeAirflow.require)
            read_env = staticmethod(lambda path: {**SETTINGS, 'INGRESS_ENABLED': 'true', 'AIRFLOW_OIDC_ISSUER': 'https://sso.test/realms/etch'})
            validate = staticmethod(lambda settings: None)
            require_image_tag = staticmethod(lambda settings: events.append('tag'))

        def start(airflow, routing, context, env, tls_source, check_only=False, pending_configmaps=()):
            events.append('check' if check_only else 'deploy')
            pending.append(set(pending_configmaps))

        def prepare(airflow, host_dirs, settings, context, ca_file, check_only):
            events.append('prepare-check' if check_only else 'prepare')
            return {'airflow-oidc-ca'} if check_only else None

        with patch.object(up.server, 'module', side_effect=lambda name, path: Airflow if name == 'airflow_deploy' else object()), \
                patch.object(up.server, 'start', start), patch.object(up, 'prepare', prepare), \
                patch.object(up.sys, 'argv', ['up.py', '--context', 'ctx', *extra]):
            with patch.object(up, 'image_change', return_value='이미지 변경: 없음'):
                up.main()
        return events

    def test_deploy_validates_everything_before_creating_resources(self):
        self.assertEqual(self.run_main(), ['prepare-check', 'check', 'tag', 'prepare', 'deploy'])
        # 검사는 이번 실행에서 만들 ConfigMap을 허용하고, 배포는 이미 만든 뒤이므로 허용 목록 없이 확인한다.
        self.assertEqual(self.pending, [{'airflow-oidc-ca'}, set()])

    def test_check_only_never_prepares_or_deploys(self):
        self.assertEqual(self.run_main('--check-only'), ['prepare-check', 'check'])


class PublishImageTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('airflow_manage', BASE / 'scripts/manage.py')
        self.manage = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.manage)
        self.settings = {'AIRFLOW_IMAGE_REPOSITORY': 'store.test/airflow', 'AIRFLOW_IMAGE_TAG': '3.3.2-abc'}

    def test_auto_tag_changes_only_with_what_goes_into_the_image(self):
        # 이미지 내용이 같은데 tag가 바뀌면 같은 이미지를 다시 빌드·배포하게 된다.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('apps/airflow/image/Dockerfile', 'apps/airflow/plugins/.gitkeep', 'apps/airflow/dags/sample.py',
                         'apps/airflow/tests/test_sample.py', 'apps/airflow/README.md', 'deploy/airflow/env/build.env'):
                (root / name).parent.mkdir(parents=True, exist_ok=True)
                (root / name).write_text('처음\n')
            for args in (['init', '-q'], ['add', '.'], ['-c', 'user.name=test', '-c', 'user.email=test@example.test', 'commit', '-q', '-m', 'init']):
                subprocess.run(['git', '-C', directory, *args], check=True, capture_output=True)
            with patch.object(self.manage, 'BASE', root / 'deploy/airflow'), patch.dict(os.environ, {'AIRFLOW_BUILD_ENV': ''}):
                base = self.manage.auto_image_tag()
                for name in ('apps/airflow/dags/sample.py', 'apps/airflow/dags/added.py', 'apps/airflow/tests/test_sample.py', 'apps/airflow/README.md'):
                    (root / name).write_text('변경\n')
                self.assertEqual(self.manage.auto_image_tag(), base)
                (root / 'apps/airflow/plugins/listener.py').write_text('변경\n')
                with_plugin = self.manage.auto_image_tag()
                self.assertNotEqual(with_plugin, base)
                (root / 'apps/airflow/image/Dockerfile').write_text('변경\n')
                with_image = self.manage.auto_image_tag()
                self.assertNotEqual(with_image, with_plugin)
                (root / 'deploy/airflow/env/build.env').write_text('변경\n')
                self.assertNotEqual(self.manage.auto_image_tag(), with_image)

    def test_image_never_contains_dags_or_tests(self):
        source = self.manage.BASE.parents[1] / 'apps/airflow/image'
        copies = [line for line in (source / 'Dockerfile').read_text().splitlines() if line.startswith('COPY')]
        self.assertTrue(copies)
        self.assertFalse([line for line in copies if 'dags' in line or 'tests' in line])
        allowed = [line for line in (source / 'Dockerfile.dockerignore').read_text().splitlines() if line.startswith('!')]
        self.assertFalse([line for line in allowed if 'dags' in line or 'tests' in line])
        self.assertEqual(self.manage.IMAGE_SOURCES, ('apps/airflow/image', 'apps/airflow/plugins'))

    def test_default_env_resolves_auto_tag_and_targets_internal_registry(self):
        values = self.manage.read_env(self.manage.DEFAULT_ENV)
        self.assertRegex(values['AIRFLOW_IMAGE_TAG'], r'^3\.3\.2-[0-9a-f]{12}$')
        self.assertEqual(values['AIRFLOW_IMAGE_TAG'], self.manage.read_env(self.manage.DEFAULT_ENV)['AIRFLOW_IMAGE_TAG'])
        self.assertTrue(self.manage.image_registry.split(values['AIRFLOW_IMAGE_REPOSITORY'] + ':x')[0])

    def test_existing_tag_skips_build_and_push(self):
        from unittest.mock import patch
        with patch.object(self.manage.image_registry, 'remote_exists', return_value=True), \
                patch.object(self.manage, 'build_image') as build, patch.object(self.manage.image_registry, 'push') as push:
            self.manage.publish_image(self.settings, Path('build.env'), Path('push.env'))
        build.assert_not_called()
        push.assert_not_called()

    def test_missing_tag_builds_with_nerdctl_then_pushes_same_reference(self):
        from unittest.mock import patch
        with patch.object(self.manage.image_registry, 'remote_exists', return_value=False), \
                patch.object(self.manage.image_registry, 'privilege', return_value=['sudo', '-n']), \
                patch.object(self.manage, 'build_image') as build, patch.object(self.manage.image_registry, 'push') as push:
            self.manage.publish_image(self.settings, Path('build.env'), Path('push.env'))
        self.assertEqual(build.call_args.kwargs['builder'], 'nerdctl')
        self.assertEqual(build.call_args.kwargs['prefix'], ['sudo', '-n'])
        command, reference, account = push.call_args.args[1:]
        self.assertEqual(command[:3], ['sudo', '-n', 'nerdctl'])
        self.assertEqual(reference, 'store.test/airflow:3.3.2-abc')
        self.assertEqual(account, Path('push.env'))

    def test_restore_secrets_creates_only_missing_secrets_from_env(self):
        from unittest.mock import patch
        settings = {'NAMESPACE': 'airflow', 'POSTGRES_PASSWORD': 'db-original', 'AIRFLOW_FERNET_KEY': 'fernet-original'}
        created = []

        def run(args, data=None, sensitive=False):
            if 'get' in args:
                return 'secret/airflow-postgres' if 'airflow-postgres' in args else ''
            created.append(json.loads(data))
            return ''

        with patch.object(self.manage, 'run', run):
            self.manage.restore_secrets(settings, 'ctx')
        self.assertEqual([item['metadata']['name'] for item in created], ['airflow-fernet'])
        self.assertEqual(created[0]['stringData'], {'fernet-key': 'fernet-original'})

    def test_repository_without_registry_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'registry 주소'):
            self.manage.publish_image({**self.settings, 'AIRFLOW_IMAGE_REPOSITORY': 'airflow'}, Path('b'), Path('p'))


if __name__ == '__main__':
    unittest.main()
