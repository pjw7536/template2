"""Airflow 배포의 민감값·스토리지·재배포 순서를 검증한다."""

import base64
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
import re
import shlex
from pathlib import Path
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit, unquote
from uuid import uuid4

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/manage.py'
SPEC = importlib.util.spec_from_file_location('airflow_deploy', SCRIPT)
deploy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(deploy)


def settings():
    """실제 자격증명 없이 운영 형식에 맞는 독립 입력을 만든다."""
    result = deploy.read_env(deploy.DEFAULT_ENV)
    result.update({
        'NODE_NAME': 'test-node', 'AIRFLOW_IMAGE_REPOSITORY': 'registry.test/airflow',
        'AIRFLOW_ADMIN_EMAIL': 'airflow@test.invalid',
        'AIRFLOW_OIDC_CLIENT_SECRET': 'fixture-oidc-secret-0123456789',
        **deploy.MAIL_DEFAULTS,
        **{key: 'fixture-credential-0123456789' for key in deploy.SECRET_KEYS},
        'AIRFLOW_FERNET_KEY': base64.urlsafe_b64encode(b'x' * 32).decode(),
    })
    return result


class ChartDownloadTests(unittest.TestCase):
    def test_fetch_uses_internal_repository_and_preserves_cache_on_bad_checksum(self):
        """사내 미러에서 고정 버전을 받고 손상된 다운로드는 기존 캐시에 반영하지 않습니다."""
        content = b'fixture-chart-archive'
        filename = f'{deploy.LOCK["name"]}-{deploy.LOCK["version"]}.tgz'
        self.assertEqual(deploy.LOCK['repository'],
                         'http://repository.samsungds.net/repository/proxy-helm-airflow.apache.org')
        for downloaded in (content, b'corrupt-chart'):
            with self.subTest(downloaded=downloaded), tempfile.TemporaryDirectory() as directory:
                target = Path(directory) / 'helm/vendor' / filename
                target.parent.mkdir(parents=True)
                target.write_bytes(b'existing-chart')
                calls = []

                def fake_run(args, **kwargs):
                    calls.append(args)
                    if args == ['helm', 'version', '--short']:
                        return 'v3.19.0'
                    self.assertEqual(args[:-1], [
                        'helm', 'pull', 'airflow', '--repo', deploy.LOCK['repository'],
                        '--version', '1.22.0', '--destination'])
                    (Path(args[-1]) / filename).write_bytes(downloaded)
                    return ''

                with patch.object(deploy, 'BASE', Path(directory)), \
                        patch.object(deploy, 'run', fake_run), \
                        patch.object(deploy.shutil, 'which', return_value='/tools/helm'), \
                        patch.dict(deploy.LOCK, {'sha256': hashlib.sha256(content).hexdigest()}), \
                        patch('sys.argv', ['manage.py', 'fetch-chart']), patch('builtins.print'):
                    if downloaded == content:
                        deploy.main()
                        self.assertEqual(target.read_bytes(), content)
                    else:
                        with self.assertRaisesRegex(ValueError, 'SHA-256'):
                            deploy.main()
                        self.assertEqual(target.read_bytes(), b'existing-chart')
                self.assertEqual(len(calls), 2)
                self.assertFalse(Path(calls[1][-1]).exists())


class ConfigurationTests(unittest.TestCase):
    def test_dotenv_is_data_and_duplicates_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'input.env'
            path.write_text('TOKEN=$(touch /tmp/never-execute-airflow)\n')
            self.assertEqual(deploy.read_env(path)['TOKEN'], '$(touch /tmp/never-execute-airflow)')
            path.write_text('TOKEN=one\nTOKEN=two\n')
            with self.assertRaisesRegex(ValueError, '중복 설정'):
                deploy.read_env(path)

    def test_init_secrets_is_private_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'k8s.env'
            args = ['python3', str(SCRIPT), 'init-secrets', '--env', str(path)]
            first = subprocess.run(args, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            before = path.read_bytes()
            self.assertFalse(path.with_suffix('.secrets.env').exists())
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(len(base64.urlsafe_b64decode(deploy.read_env(path)['AIRFLOW_FERNET_KEY'])), 32)
            self.assertNotEqual(subprocess.run(args, capture_output=True).returncode, 0)
            self.assertEqual(path.read_bytes(), before)
            for key in deploy.SECRET_KEYS[:-1]:
                self.assertNotIn(deploy.read_env(path)[key], first.stdout)
                self.assertIn(deploy.read_env(path)[key], path.read_text())

    def test_init_secrets_preserves_existing_public_env(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'k8s.env'
            content = '\n'.join(f'{key}=' for key in deploy.SECRET_KEYS) + '\nNODE_NAME=existing-node\n'
            path.write_text(content)
            result = subprocess.run(['python3', str(SCRIPT), 'init-secrets', '--env', str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(deploy.read_env(path)['NODE_NAME'], 'existing-node')
            self.assertFalse(path.with_suffix('.secrets.env').exists())
            self.assertEqual(len(base64.urlsafe_b64decode(deploy.read_env(path)['AIRFLOW_FERNET_KEY'])), 32)

    def test_actual_settings_reject_example(self):
        deploy.validate(settings())
        with self.assertRaisesRegex(ValueError, '실제 값으로 교체'):
            deploy.validate({**settings(), 'POSTGRES_PASSWORD': 'replace-me'})

    def test_config_rejects_typos_and_helm_template_execution(self):
        values = settings()
        values['TYPO'] = 'test'
        with self.assertRaisesRegex(ValueError, '설정 키'):
            deploy.validate(values)
        values = settings()
        values['AIRFLOW_WEBSERVER_BASE_URL'] = 'https://{{lookup}}/airflow'
        with self.assertRaisesRegex(ValueError, '템플릿'):
            deploy.validate(values)

    def test_legacy_env_defaults_to_disabled_mail_notifications(self):
        values = {key: value for key, value in settings().items() if key not in deploy.MAIL_DEFAULTS}
        deploy.validate(values)
        self.assertEqual(values['AIRFLOW_FAILURE_ALERT_EMAIL_TO'], '')
        self.assertEqual(values['MAIL_API_SYSTEM_ID'], 'plane')

    def test_enabled_mail_requires_credentials_and_valid_addresses(self):
        configured = {**settings(), 'MAIL_API_URL': 'https://mail.test/send',
                      'MAIL_API_KEY': 'fixture-mail-ticket', 'MAIL_API_SYSTEM_ID': 'test',
                      'MAIL_API_KNOX_ID': 'sender', 'AIRFLOW_FAILURE_ALERT_EMAIL_FROM': 'sender@example.test',
                      'AIRFLOW_FAILURE_ALERT_EMAIL_TO': 'one@example.test, two@example.test'}
        deploy.validate(configured)
        for key in ('MAIL_API_URL', 'MAIL_API_KEY', 'MAIL_API_SYSTEM_ID', 'MAIL_API_KNOX_ID', 'AIRFLOW_FAILURE_ALERT_EMAIL_FROM'):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, '메일 실패 알림 필수 설정 누락'):
                deploy.validate({**configured, key: ''})
        for change in ({'AIRFLOW_FAILURE_ALERT_EMAIL_TO': 'not-an-email'},
                       {'AIRFLOW_FAILURE_ALERT_EMAIL_FROM': 'Name <sender@example.test>'},
                       {'MAIL_API_URL': 'ftp://mail.test/send'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                deploy.validate({**configured, **change})

    def test_mail_configuration_is_only_passed_via_runtime_secret(self):
        values = {**settings(), 'MAIL_API_KEY': 'fixture-mail-ticket'}
        secret = next(item for item in deploy.secret_manifest(values)['items']
                      if item['metadata']['name'] == 'airflow-runtime')
        for key in deploy.MAIL_DEFAULTS:
            self.assertEqual(base64.b64decode(secret['data'][key]).decode(), values[key])
        self.assertNotIn('fixture-mail-ticket', json.dumps(deploy.helm_values(values)))

    def test_mail_url_accepts_existing_query_without_relaxing_other_url_checks(self):
        deploy.validate({**settings(), 'MAIL_API_URL': 'https://mail.test/send?systemId=plane&loginUser.login=sender'})
        for key, value in (('MAIL_API_URL', 'https://user:password@mail.test/send?systemId=plane'),
                           ('MAIL_API_URL', 'https://mail.test/send?systemId=plane#fragment'),
                           ('AIRFLOW_API_BASE_URL', 'https://portal.test?query=value'),
                           ('KNOX_MESSENGER_API_BASE_URL', 'https://messenger.test?query=value')):
            with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, 'URL 형식 오류'):
                deploy.validate({**settings(), key: value})

    def test_config_rejects_overlapping_storage_and_wrong_versions(self):
        for change in (
            {'LOGS_HOST_PATH': '/appdata/airflow/postgres/logs'},
            {'POSTGRES_IMAGE': 'postgres:17'},
            {'AIRFLOW_IMAGE_TAG': 'latest'},
            {'AIRFLOW_FERNET_KEY': 'wrong-key-value-0123456789'},
            {'ODBC_HOST_PATH': 'relative/odbc'},
            {'ODBC_HOST_PATH': '/appdata/airflow/postgres/odbc'},
            {'ODBC_SECRET_NAME': 'odbc-with-default-host'},
        ):
            with self.subTest(change=list(change)):
                with self.assertRaises(ValueError):
                    deploy.validate({**settings(), **change})

    def test_ingress_requires_class_and_tls_and_preserves_prefix(self):
        values = {**settings(), 'INGRESS_ENABLED': 'true', 'AIRFLOW_WEBSERVER_BASE_URL': 'https://airflow.test/airflow',
                  'INGRESS_CLASS_NAME': '', 'INGRESS_TLS_SECRET': ''}
        with self.assertRaisesRegex(ValueError, 'INGRESS_CLASS_NAME'):
            deploy.validate(values)
        values['INGRESS_CLASS_NAME'] = 'nginx'
        with self.assertRaisesRegex(ValueError, 'INGRESS_TLS_SECRET'):
            deploy.validate(values)
        values['INGRESS_TLS_SECRET'] = 'airflow-tls'
        deploy.validate(values)
        web = deploy.helm_values(values)['ingress']['apiServer']
        self.assertEqual(web['path'], '/airflow')
        self.assertEqual(web['hosts'][0]['tls']['secretName'], 'airflow-tls')

    def test_storage_is_retained_and_bound_to_one_node(self):
        manifests = deploy.manifests(settings())
        volumes = manifests['storage']['items']
        for volume in volumes:
            spec = volume['spec']
            self.assertEqual(spec['storageClassName'], '')
            self.assertEqual(spec['accessModes'], ['ReadWriteOnce'])
            if volume['kind'] == 'PersistentVolume':
                self.assertEqual(spec['persistentVolumeReclaimPolicy'], 'Retain')
                self.assertIn('test-node', json.dumps(spec['nodeAffinity']))
        database = manifests['postgres']['items'][1]['spec']['template']['spec']
        self.assertEqual(database['securityContext']['runAsUser'], 999)
        self.assertNotIn('hostPath', json.dumps(database))
        self.assertNotIn('hostPort', json.dumps(database))

    def test_secret_url_encoding_and_public_render_separation(self):
        values = {**settings(), 'POSTGRES_PASSWORD': 'fixture-password@:/?#%0123456789'}
        secrets = deploy.secret_manifest(values)['items']
        database = next(item for item in secrets if item['metadata']['name'] == 'airflow-metadata')
        url = base64.b64decode(database['data']['connection']).decode()
        self.assertEqual(unquote(urlsplit(url).password), values['POSTGRES_PASSWORD'])
        public = json.dumps(deploy.helm_values(values)) + json.dumps(deploy.manifests(values))
        for key in deploy.SECRET_KEYS:
            self.assertNotIn(values[key], public)
        self.assertTrue(all('stringData' not in item for item in secrets))

    def test_odbc_and_registry_secret_references(self):
        values = {**settings(), 'ODBC_HOST_PATH': '', 'ODBC_SECRET_NAME': 'odbc', 'IMAGE_PULL_SECRET': 'registry'}
        overlay = deploy.helm_values(values)
        self.assertTrue(overlay['volumeMounts'][0]['readOnly'])
        self.assertEqual(overlay['volumes'][0]['secret']['secretName'], 'odbc')
        self.assertEqual(deploy.manifests(values)['postgres']['items'][1]['spec']['template']['spec']['imagePullSecrets'], [{'name': 'registry'}])

    def test_odbc_host_directory_preserves_all_files_read_only(self):
        values = settings()
        deploy.validate(values)
        overlay = deploy.helm_values(values)
        self.assertEqual(overlay['volumes'], [{'name': 'odbc', 'hostPath': {'path': '/appdata/airflow/odbc', 'type': 'Directory'}}])
        self.assertEqual(overlay['volumeMounts'], [{'name': 'odbc', 'mountPath': '/usr/local/odbc', 'readOnly': True}])
        self.assertEqual(overlay['nodeSelector'], {'kubernetes.io/hostname': 'test-node'})

    def test_no_odbc_mount_when_both_inputs_are_empty(self):
        values = {**settings(), 'ODBC_HOST_PATH': '', 'ODBC_SECRET_NAME': ''}
        deploy.validate(values)
        self.assertNotIn('volumes', deploy.helm_values(values))

    def test_corrupt_chart_is_rejected_without_cluster_access(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'chart.tgz'
            path.write_bytes(b'corrupt chart')
            with patch.dict(os.environ, {'AIRFLOW_CHART_FILE': str(path)}):
                with self.assertRaisesRegex(ValueError, 'SHA-256'):
                    deploy.chart_path()


class InternalBuildParityTests(unittest.TestCase):
    def test_internal_build_inputs_match_dockerfile_contract(self):
        """공개 빌드 입력이 이미지 인자와 일치하고 사내 의존성을 유지합니다."""
        actual = deploy.read_env(deploy.BASE / 'env/build.env')
        dockerfile = deploy.BASE.parents[1] / 'apps/airflow/image/Dockerfile.dependencies'
        arguments = dict(shlex.split(line[4:])[0].split('=', 1)
                         for line in dockerfile.read_text().splitlines() if line.startswith('ARG '))
        self.assertEqual(arguments, actual)
        self.assertEqual(actual['INSTALL_BIGDATAQUERY_PYTHON'], 'true')
        self.assertEqual(actual['INSTALL_BIGDATAQUERY_ODBC'], 'true')

    def test_build_uses_original_dockerfile_and_forwards_every_internal_argument(self):
        calls = []
        original = (deploy.BASE.parents[1] / 'apps/airflow/image/Dockerfile.dependencies').read_bytes()

        def fake_run(args, **kwargs):
            args = list(map(str, args))
            calls.append(args)
            if len(calls) == 1:
                context = Path(args[-1])
                self.assertEqual((context / 'Dockerfile').read_bytes(), original)
                self.assertEqual([p.name for p in context.iterdir()], ['Dockerfile'])
            return ''

        build_path = deploy.BASE / 'env/build.env'
        with patch.object(deploy, 'run', fake_run):
            deploy.build_image(settings(), build_path)
        self.assertEqual(len(calls), 2)
        for key, value in deploy.read_env(build_path).items():
            index = calls[0].index(f'{key}={value}')
            self.assertEqual(calls[0][index - 1], '--build-arg')
        self.assertIn('AIRFLOW_DEPENDENCY_IMAGE=registry.test/airflow:3.3.2-release-1-dependencies', calls[1])
        self.assertNotIn('push', calls[0] + calls[1])
        source = deploy.BASE.parents[1] / 'apps/airflow'
        self.assertEqual(calls[1][-1], str(source))
        self.assertEqual(calls[1][calls[1].index('-f') + 1], str(source / 'image/Dockerfile'))

    def test_missing_source_stops_before_docker_with_checkout_guidance(self):
        with patch.object(Path, 'exists', return_value=False), patch.object(deploy, 'run') as run:
            with self.assertRaisesRegex(ValueError, '--with-source'):
                deploy.build_image(settings(), deploy.BASE / 'env/build.env')
            run.assert_not_called()


@unittest.skipUnless(os.environ.get('AIRFLOW_DOCKER_TESTS') == '1', '명시적인 Docker 이미지 통합 검사에서 실행')
class ImageBuildIntegrationTests(unittest.TestCase):
    """사내망 접근 없이 실제 이미지의 pip 상속과 COPY 원본 포함을 검증합니다."""

    def test_corporate_pip_defaults_survive_final_image_and_virtualenv(self):
        base = 'apache/airflow:3.3.2-python3.12'
        if not shutil.which('docker') or subprocess.run(
            ['docker', 'image', 'inspect', base], capture_output=True
        ).returncode:
            self.skipTest('로컬 Docker daemon과 캐시된 Airflow 3.3.2 이미지가 필요합니다.')
        tag = 'tailwind-airflow-image-check:3.3.2-check-' + uuid4().hex[:12]
        self.addCleanup(subprocess.run, ['docker', 'image', 'rm', '-f', tag, tag + '-dependencies'], capture_output=True)
        build = {**deploy.read_env(deploy.BASE / 'env/build.env'), 'AIRFLOW_BASE_IMAGE': base,
                 'INSTALL_BIGDATAQUERY_PYTHON': 'false', 'INSTALL_BIGDATAQUERY_ODBC': 'false'}
        expected = {key: build[key] for key in ('PIP_INDEX_URL', 'PIP_EXTRA_INDEX_URL', 'PIP_TRUSTED_HOST')}
        original_run = deploy.run

        def offline_run(args, **kwargs):
            args = list(map(str, args))
            if args[:2] == ['docker', 'build']:
                args.insert(2, '--network=none')
            return original_run(args, **kwargs)

        with tempfile.TemporaryDirectory() as directory:
            build_path = Path(directory) / 'build.env'
            build_path.write_text(''.join(f'{key}={value}\n' for key, value in build.items()))
            with patch.object(deploy, 'run', offline_run):
                deploy.build_image({**settings(), 'AIRFLOW_IMAGE_REPOSITORY': tag.split(':')[0],
                                    'AIRFLOW_IMAGE_TAG': tag.split(':')[1]}, build_path)
        script = textwrap.dedent('''
            import json
            import os
            from pathlib import Path
            import subprocess
            import sys
            import failure_alerts
            expected = json.loads(sys.argv[1])
            from airflow.providers.standard.utils.python_virtualenv import _generate_pip_conf
            for key in (*expected, 'PIP_CONFIG_FILE'):
                assert not os.environ.get(key), key
            assert os.environ['PIP_NO_INPUT'] == '1'
            assert os.environ['PIP_DISABLE_PIP_VERSION_CHECK'] == '1'
            for filename in ('bootstrap-user.py', 'webserver_config.py', 'keycloak_security.py', 'oidc_claims.py'):
                assert Path('/opt/airflow', filename).is_file(), filename
            subprocess.run([sys.executable, '-m', 'venv', '/tmp/airflow-check-venv'], check=True, capture_output=True)
            inspect_options = (
                'import json,sys; from pip._internal.commands import create_command; '
                'options,args=create_command("install").parse_args(sys.argv[1:]); '
                'print(json.dumps([options.index_url, options.extra_index_urls, options.no_index, options.trusted_hosts]))'
            )
            for python in (sys.executable, '/tmp/airflow-check-venv/bin/python'):
                options = json.loads(subprocess.check_output([python, '-c', inspect_options], text=True))
                assert options[:2] == [expected['PIP_INDEX_URL'], [expected['PIP_EXTRA_INDEX_URL']]], options
                assert set(options[3]) == set(expected['PIP_TRUSTED_HOST'].split()), options
                override = {**os.environ, 'PIP_INDEX_URL': 'https://override.test/simple'}
                options = json.loads(subprocess.check_output([python, '-c', inspect_options], env=override, text=True))
                assert options[0] == 'https://override.test/simple', options
                options = json.loads(subprocess.check_output(
                    [python, '-c', inspect_options, '--index-url', 'https://cli.test/simple'], env=override, text=True))
                assert options[0] == 'https://cli.test/simple', options
            conf = Path('/tmp/airflow-check-venv/pip.conf')
            python = '/tmp/airflow-check-venv/bin/python'
            for indexes in (['https://dag.test/simple'], ['https://dag.test/simple', 'https://dag-extra.test/simple'], []):
                _generate_pip_conf(conf, indexes)
                options = json.loads(subprocess.check_output([python, '-c', inspect_options], text=True))
                if indexes:
                    assert options[0] == indexes[0], options
                    if len(indexes) > 1:
                        assert options[1] == indexes[1:], options
                else:
                    assert options[2], options
            print('기본 mirror·DAG별 index_urls·no-index·override와 이미지 코드 포함 검증 통과')
        ''')
        result = original_run(['docker', 'run', '--rm', '--network=none', '--entrypoint', 'python',
                               tag, '-c', script, json.dumps(expected)])
        self.assertIn('검증 통과', result)


class DeploymentTests(unittest.TestCase):
    def fake_run(self, args, **kwargs):
        args = list(map(str, args))
        self.calls.append((args, kwargs))
        if 'version' in args:
            return json.dumps({'serverVersion': {'gitVersion': 'v1.34.0'}})
        if 'nodes' in args:
            return json.dumps({'items': [{'spec': self.node_spec, 'status': {'conditions': [{'type': 'Ready', 'status': 'True'}]}}]})
        if 'create' in args and '--dry-run=client' in args:
            return json.dumps({'kind': 'List', 'items': self.pod_resources})
        if 'get' in args and any(kind in args and name in args for kind, name in self.missing_resources):
            raise ValueError('필수 리소스가 없습니다.')
        if 'secret' in args and 'get' in args:
            if self.changed_key and self.changed_key in args:
                return json.dumps({'data': {'password': base64.b64encode(b'old-password').decode()}})
            name = args[args.index('secret') + 1]
            if name in self.existing_secrets:
                return json.dumps(self.existing_secrets[name])
            return ''
        if 'get' in args:
            for kind in ('pvc', 'deployment', 'namespace'):
                if kind in args:
                    name = args[args.index(kind) + 1]
                    return self.existing_resources.get((kind, name), '')
        return ''

    def setUp(self):
        self.addCleanup(patch.stopall)
        patch.object(deploy, 'check_ingress_tls').start()
        self.calls = []
        self.changed_key = None
        self.node_spec = {}
        self.existing_secrets = {}
        self.existing_resources = {}
        self.missing_resources = set()
        self.pod_resources = [{'kind': 'Deployment', 'metadata': {'name': 'airflow-scheduler'},
                               'spec': {'template': {'spec': {
                                   'nodeSelector': {'kubernetes.io/hostname': 'test-node'},
                                   'tolerations': [
                                       {'key': 'node-role.kubernetes.io/control-plane', 'operator': 'Exists', 'effect': 'NoSchedule'},
                                       {'key': 'node-role.kubernetes.io/master', 'operator': 'Exists', 'effect': 'NoSchedule'}]}}}}]
        # 배포 순서 테스트는 Helm 실행 대신 최종 Pod 리소스의 외부 명령 계약을 대체합니다.
        for name, value in [('render', []), ('chart_path', Path('/chart.tgz'))]:
            patcher = patch.object(deploy, name, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_missing_common_certificate_stops_before_application_writes(self):
        deploy.check_ingress_tls.side_effect = ValueError('공용 TLS 인증서 없음')
        with patch.object(deploy, 'run', self.fake_run), self.assertRaisesRegex(ValueError, '공용 TLS'):
            deploy.deploy(settings(), 'test-context', Path('/chart.tgz'))
        self.assertFalse(any('apply' in args or 'upgrade' in args for args, _ in self.calls))

    def test_missing_required_resources_stop_before_any_apply(self):
        for key, kind in [('IMAGE_PULL_SECRET', 'secret'), ('ODBC_SECRET_NAME', 'secret'),
                          ('AIRFLOW_OIDC_CA_CONFIGMAP', 'configmap')]:
            with self.subTest(key=key), patch.object(deploy, 'run', self.fake_run):
                self.calls.clear()
                self.missing_resources = {(kind, 'missing-resource')}
                with self.assertRaisesRegex(ValueError, '필수 리소스'):
                    deploy.deploy({**settings(), key: 'missing-resource'}, 'test-context', Path('/chart.tgz'))
                self.assertFalse(any('apply' in args or 'upgrade' in args for args, _ in self.calls))

    def test_external_database_uses_final_toleration_override(self):
        """외부 DB는 최종 Helm Pod가 허용하는 전용 노드에서 배포할 수 있습니다."""
        self.node_spec = {'taints': [{'key': 'dedicated', 'value': 'airflow', 'effect': 'NoSchedule'}]}
        self.pod_resources[0]['spec']['template']['spec']['tolerations'] = [
            {'key': 'dedicated', 'value': 'airflow', 'effect': 'NoSchedule'}]
        values = {**settings(), 'POSTGRES_MODE': 'external', 'POSTGRES_HOST': 'postgres.test'}
        override = Path('/environment/override.yaml')
        with patch.object(deploy, 'run', self.fake_run):
            deploy.deploy(values, 'test-context', Path('/chart.tgz'), values_file=override)
        self.assertEqual(deploy.render.call_args.args[-1], override)
        self.assertTrue(any('upgrade' in args for args, _ in self.calls))

    def test_airflow_override_does_not_hide_untolerated_internal_database(self):
        self.node_spec = {'taints': [{'key': 'dedicated', 'value': 'airflow', 'effect': 'NoSchedule'}]}
        self.pod_resources[0]['spec']['template']['spec']['tolerations'] = [
            {'key': 'dedicated', 'operator': 'Exists', 'effect': 'NoSchedule'}]
        with patch.object(deploy, 'run', self.fake_run):
            with self.assertRaisesRegex(ValueError, 'airflow-postgres.*taint'):
                deploy.deploy(settings(), 'test-context', Path('/chart.tgz'))
        self.assertFalse(any('apply' in args for args, _ in self.calls))

    def test_each_component_must_tolerate_its_node_taints(self):
        self.node_spec = {'taints': [{'key': 'dedicated', 'value': 'airflow', 'effect': 'NoSchedule'}]}
        self.pod_resources[0]['spec']['template']['spec']['tolerations'] = [
            {'key': 'dedicated', 'operator': 'Exists', 'effect': 'NoSchedule'}]
        self.pod_resources.append({'kind': 'Job', 'metadata': {'name': 'airflow-migration'}, 'spec': {
            'template': {'spec': {'nodeSelector': {'kubernetes.io/hostname': 'test-node'}}}}})
        values = {**settings(), 'POSTGRES_MODE': 'external', 'POSTGRES_HOST': 'postgres.test'}
        with patch.object(deploy, 'run', self.fake_run):
            with self.assertRaisesRegex(ValueError, 'airflow-migration.*taint'):
                deploy.deploy(values, 'test-context', Path('/chart.tgz'))
        self.assertFalse(any('apply' in args for args, _ in self.calls))

    def test_toleration_key_value_effect_and_exists_match_kubernetes_rules(self):
        taint = {'key': 'dedicated', 'value': 'airflow', 'effect': 'NoExecute'}
        for toleration, expected in [
                ({'key': 'dedicated', 'value': 'airflow', 'effect': 'NoExecute'}, True),
                ({'key': 'dedicated', 'value': 'other'}, False),
                ({'key': 'other', 'value': 'airflow'}, False),
                ({'key': 'dedicated', 'operator': 'Exists'}, True),
                ({'operator': 'Exists', 'effect': 'NoExecute'}, True),
                ({'key': 'dedicated', 'operator': 'Exists', 'effect': 'NoSchedule'}, False),
                ({'key': 'dedicated', 'value': 'airflow', 'tolerationSeconds': 300}, True)]:
            with self.subTest(toleration=toleration):
                self.assertEqual(deploy.tolerates(taint, [toleration]), expected)

    def test_rendered_pods_accepts_json_stream_and_preserves_context(self):
        resources = [*self.pod_resources, {'kind': 'ConfigMap', 'metadata': {'name': 'airflow-config'}}]
        for output in [json.dumps({'kind': 'List', 'items': resources}),
                       '\n'.join(json.dumps(item) for item in resources)]:
            with self.subTest(output=output), patch.object(deploy, 'run', return_value=output) as run:
                pods = deploy.rendered_pods(settings(), 'test-context', '/rendered/airflow.yaml')
                self.assertEqual([name for name, _ in pods], ['airflow-scheduler', 'airflow-postgres'])
                self.assertEqual(run.call_args.args[0][1:3], ['--context', 'test-context'])
                self.assertIn('--dry-run=client', run.call_args.args[0])

    def test_missing_fernet_with_existing_database_or_deployment_stops_before_mutation(self):
        """DB 계정이 정상이어도 기존 설치의 암호화 키를 새로 덮어쓰지 않습니다."""
        values = settings()
        self.existing_secrets['airflow-postgres'] = {
            'data': {'password': base64.b64encode(values['POSTGRES_PASSWORD'].encode()).decode()}}
        for kind, name in [('pvc', 'airflow-postgres'), ('deployment', 'airflow-scheduler'),
                           ('secret', 'airflow-metadata')]:
            with self.subTest(kind=kind):
                self.calls.clear()
                self.existing_resources = {(kind, name): f'{kind}/{name}'}
                if kind == 'secret':
                    self.existing_secrets[name] = {'data': {'connection': 'fixture'}}
                with patch.object(deploy, 'run', self.fake_run):
                    with self.assertRaisesRegex(ValueError, 'Fernet.*복원'):
                        deploy.deploy(values, 'test-context', Path('/chart.tgz'))
                self.assertFalse(any('apply' in args or 'upgrade' in args for args, _ in self.calls))

    def test_restored_fernet_allows_existing_database_and_changed_key_is_rejected(self):
        """원래 키를 복원하면 재배포할 수 있고 다른 키로의 변경은 중단합니다."""
        values = settings()
        self.existing_resources[('pvc', 'airflow-postgres')] = 'pvc/airflow-postgres'
        self.existing_secrets = {
            'airflow-postgres': {'data': {'password': base64.b64encode(values['POSTGRES_PASSWORD'].encode()).decode()}},
            'airflow-fernet': {'data': {'fernet-key': base64.b64encode(values['AIRFLOW_FERNET_KEY'].encode()).decode()}},
        }
        with patch.object(deploy, 'run', self.fake_run):
            deploy.check_cluster_inputs(values, 'test-context')
            with self.assertRaisesRegex(ValueError, '기존 AIRFLOW_FERNET_KEY'):
                deploy.check_cluster_inputs({**values, 'AIRFLOW_FERNET_KEY': 'different-key'}, 'test-context')

    def test_external_database_with_existing_metadata_requires_fernet_restore(self):
        self.existing_secrets['airflow-metadata'] = {'data': {'connection': 'fixture'}}
        values = {**settings(), 'POSTGRES_MODE': 'external', 'POSTGRES_HOST': 'external-postgres'}
        with patch.object(deploy, 'run', self.fake_run):
            with self.assertRaisesRegex(ValueError, 'Fernet.*복원'):
                deploy.deploy(values, 'test-context', Path('/chart.tgz'))
        self.assertFalse(any('apply' in args for args, _ in self.calls))

    def test_untolerated_blocking_taints_stop_before_mutation(self):
        for key, effect in [('dedicated', 'NoSchedule'), ('dedicated', 'NoExecute'),
                            ('node-role.kubernetes.io/control-plane', 'NoExecute')]:
            with self.subTest(key=key, effect=effect):
                self.calls.clear()
                self.node_spec = {'taints': [{'key': key, 'value': 'other', 'effect': effect}]}
                with patch.object(deploy, 'run', self.fake_run):
                    with self.assertRaisesRegex(ValueError, 'taint'):
                        deploy.deploy(settings(), 'test-context', Path('/chart.tgz'))
                self.assertFalse(any('apply' in args for args, _ in self.calls))

    def test_default_control_plane_tolerations_and_soft_taints_are_allowed(self):
        for taint in [{'key': 'node-role.kubernetes.io/control-plane', 'effect': 'NoSchedule'},
                      {'key': 'node-role.kubernetes.io/master', 'effect': 'NoSchedule'},
                      {'key': 'dedicated', 'effect': 'PreferNoSchedule'}]:
            with self.subTest(taint=taint), patch.object(deploy, 'run', self.fake_run):
                self.node_spec = {'taints': [taint]}
                deploy.check_cluster_inputs(settings(), 'test-context')

    def test_deploy_orders_database_hooks_and_rollout_without_helm_wait(self):
        with patch.object(deploy, 'run', self.fake_run), patch.object(deploy, 'render', return_value=[]):
            deploy.deploy(settings(), 'test-context', Path('/chart.tgz'))
        commands = [call[0] for call in self.calls]
        helm = next(index for index, command in enumerate(commands) if command[0] == 'helm')
        database = next(index for index, command in enumerate(commands) if 'statefulset/airflow-postgres' in command)
        restart = next(index for index, command in enumerate(commands) if 'restart' in command)
        self.assertLess(database, helm)
        self.assertLess(helm, restart)
        self.assertNotIn('--wait', commands[helm])
        self.assertNotIn('--atomic', commands[helm])
        self.assertIn('--kube-context', commands[helm])
        for command in commands:
            if command[0] == 'kubectl':
                self.assertIn('--context', command)
                self.assertIn('test-context', command)
            for key in deploy.SECRET_KEYS:
                self.assertNotIn(settings()[key], ' '.join(command))
        secret_apply = next(kwargs for command, kwargs in self.calls if '--server-side' in command)
        self.assertTrue(secret_apply['sensitive'])
        self.assertIn('airflow-runtime', secret_apply['data'])

    def test_new_namespace_is_created_before_secrets_and_application_resources(self):
        """최초 설치는 Namespace를 한 번 생성한 뒤 Secret과 앱을 적용합니다."""
        with patch.object(deploy, 'run', self.fake_run):
            deploy.deploy(settings(), 'test-context', Path('/chart.tgz'))
        creates = [(index, json.loads(kwargs['data'])) for index, (args, kwargs) in enumerate(self.calls)
                   if 'create' in args and '--dry-run=client' not in args]
        self.assertEqual([body for _, body in creates], [
            {'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': settings()['NAMESPACE']}}])
        first_apply = next(index for index, (args, _) in enumerate(self.calls) if 'apply' in args)
        self.assertLess(creates[0][0], first_apply)

    def test_existing_namespace_is_not_reapplied_or_recreated(self):
        """이미 있는 Namespace의 보안 label·annotation과 운영 설정에는 쓰지 않습니다."""
        self.existing_resources[('namespace', settings()['NAMESPACE'])] = 'namespace/airflow'
        with patch.object(deploy, 'run', self.fake_run):
            deploy.deploy(settings(), 'test-context', Path('/chart.tgz'))
        self.assertTrue(any('get' in args and 'namespace' in args for args, _ in self.calls))
        for args, kwargs in self.calls:
            if '--dry-run=client' in args or not any(verb in args for verb in ('apply', 'create', 'patch')):
                continue
            if 'data' in kwargs:
                body = json.loads(kwargs['data'])
                self.assertNotEqual(body.get('kind'), 'Namespace')
                self.assertTrue(all(item.get('kind') != 'Namespace' for item in body.get('items', [])))

    def test_deploy_restarts_only_components_present_in_final_render(self):
        """triggerer가 비활성화돼도 남은 scheduler·API server는 재시작하고 준비를 기다립니다."""
        api_server = deepcopy(self.pod_resources[0])
        api_server['metadata']['name'] = 'airflow-api-server'
        self.pod_resources += [api_server, {'kind': 'Job', 'metadata': {'name': 'airflow-migration'},
                                          'spec': deepcopy(api_server['spec'])}]
        with patch.object(deploy, 'run', self.fake_run):
            deploy.deploy(settings(), 'test-context', Path('/chart.tgz'), values_file=Path('/override.json'))
        commands = [args for args, _ in self.calls]
        restart = next(args for args in commands if 'restart' in args)
        self.assertEqual(restart[restart.index('restart') + 1:],
                         ['deployment/airflow-scheduler', 'deployment/airflow-api-server'])
        waits = [args[args.index('status') + 1] for args in commands if 'rollout' in args and 'status' in args]
        self.assertEqual(waits, ['statefulset/airflow-postgres', 'deployment/airflow-scheduler',
                                 'deployment/airflow-api-server'])
        self.assertEqual(deploy.render.call_args.args[-1], Path('/override.json'))

    def test_deploy_uses_rendered_workload_kind_for_rollout(self):
        self.pod_resources[0]['kind'] = 'StatefulSet'
        with patch.object(deploy, 'run', self.fake_run):
            deploy.deploy(settings(), 'test-context', Path('/chart.tgz'))
        restart = next(args for args, _ in self.calls if 'restart' in args)
        self.assertEqual(restart[restart.index('restart') + 1:], ['statefulset/airflow-scheduler'])

    def test_changed_database_password_stops_before_mutation(self):
        self.changed_key = 'airflow-postgres'
        with patch.object(deploy, 'run', self.fake_run):
            with self.assertRaisesRegex(ValueError, '기존 POSTGRES_PASSWORD'):
                deploy.deploy(settings(), 'test-context', Path('/chart.tgz'))
        self.assertFalse(any('apply' in args for args, _ in self.calls))

    def test_existing_database_without_secret_requires_restore(self):
        def run(args, **kwargs):
            if 'get' in args and 'pvc' in args:
                return 'persistentvolumeclaim/airflow-postgres'
            return self.fake_run(args, **kwargs)
        with patch.object(deploy, 'run', run):
            with self.assertRaisesRegex(ValueError, 'Secret이 없습니다'):
                deploy.deploy(settings(), 'test-context', Path('/chart.tgz'))
        self.assertFalse(any('apply' in args for args, _ in self.calls))

    def test_external_database_never_applies_or_waits_for_internal_postgres(self):
        """외부 DB 모드는 로그 PV와 Helm만 적용하고 기존 DB workload를 건드리지 않습니다."""
        values = {**settings(), 'POSTGRES_MODE': 'external', 'POSTGRES_HOST': 'external-postgres'}
        with patch.object(deploy, 'run', self.fake_run), patch.object(deploy, 'render', return_value=[]):
            deploy.deploy(values, 'test-context', Path('/chart.tgz'))
        commands = [args for args, _ in self.calls]
        self.assertTrue(any('helm' == args[0] for args in commands))
        self.assertFalse(any('statefulset/airflow-postgres' in args for args in commands))
        self.assertFalse(any(any(arg.endswith('/postgres.json') for arg in args) for args in commands))
        self.assertFalse(any('delete' in args for args in commands))

    def test_missing_context_fails_before_kubectl(self):
        with tempfile.TemporaryDirectory() as directory:
            env = Path(directory) / 'k8s.env'
            env.write_text(''.join(f'{key}={value}\n' for key, value in settings().items()))
            result = subprocess.run(['python3', str(SCRIPT), 'deploy', '--env', str(env)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('--context', result.stderr)


class HelmIntegrationTests(unittest.TestCase):
    def test_official_chart_can_disable_triggerer_without_removing_other_components(self):
        path = Path(os.environ.get('AIRFLOW_CHART_FILE', deploy.BASE / 'helm/vendor/airflow-1.22.0.tgz'))
        if not path.is_file() or not shutil.which('helm'):
            self.skipTest('공식 chart archive와 Helm 반입 후 실행 가능')
        with tempfile.TemporaryDirectory() as directory:
            override = Path(directory) / 'override.json'
            override.write_text(json.dumps({'triggerer': {'enabled': False}}))
            deploy.render(settings(), directory, deploy.chart_path(), values_file=override)
            rendered = (Path(directory) / 'airflow.yaml').read_text()
            workloads = re.findall(r'^kind: (?:Deployment|StatefulSet|DaemonSet)\nmetadata:\n  name: (\S+)',
                                   rendered, re.M)
            self.assertEqual(workloads, ['airflow-api-server', 'airflow-dag-processor', 'airflow-scheduler'])

    def test_official_chart_applies_toleration_override_to_components_and_hooks(self):
        path = Path(os.environ.get('AIRFLOW_CHART_FILE', deploy.BASE / 'helm/vendor/airflow-1.22.0.tgz'))
        if not path.is_file() or not shutil.which('helm'):
            self.skipTest('공식 chart archive와 Helm 반입 후 실행 가능')
        with tempfile.TemporaryDirectory() as directory:
            override = Path(directory) / 'override.json'
            override.write_text(json.dumps({'tolerations': [
                {'key': 'dedicated', 'value': 'airflow', 'operator': 'Equal', 'effect': 'NoSchedule'}]}))
            flags = deploy.render(settings(), directory, deploy.chart_path(), values_file=override)
            rendered = (Path(directory) / 'airflow.yaml').read_text()
            self.assertEqual(flags[-1], override)
            self.assertEqual(rendered.count('key: dedicated'), 6)
            self.assertEqual(rendered.count('value: airflow'), 6)
            self.assertNotIn('key: node-role.kubernetes.io/control-plane', rendered)

    def test_official_chart_renders_airflow3_localexecutor_without_extra_claims(self):
        path = Path(os.environ.get('AIRFLOW_CHART_FILE', deploy.BASE / 'helm/vendor/airflow-1.22.0.tgz'))
        if not path.is_file() or not shutil.which('helm'):
            self.skipTest('공식 chart archive와 Helm 반입 후 실행 가능')
        with tempfile.TemporaryDirectory() as directory:
            deploy.render(settings(), directory, deploy.chart_path())
            rendered = (Path(directory) / 'airflow.yaml').read_text()
            self.assertEqual(rendered.count('\nkind: Deployment\n'), 4)
            self.assertNotIn('\nkind: StatefulSet\n', rendered)
            self.assertNotIn('\nkind: PersistentVolumeClaim\n', rendered)
            self.assertIn('executor = LocalExecutor', rendered)
            self.assertIn('dags_are_paused_at_creation = False', rendered)
            self.assertIn('parallelism = 32', rendered)
            self.assertIn('max_active_tasks_per_dag = 16', rendered)
            self.assertIn('max_active_runs_per_dag = 16', rendered)
            self.assertIn('workers = 4', rendered)
            self.assertNotIn('name: scheduler-log-groomer', rendered)
            self.assertNotIn('name: dag-processor-log-groomer', rendered)
            self.assertIn('path: /appdata/airflow/odbc', rendered)
            self.assertIn('mountPath: /usr/local/odbc', rendered)
            self.assertIn('path: /api/v2/monitor/health', rendered)
            self.assertIn('name: airflow-api-jwt', rendered)
            self.assertIn('name: airflow-api-key', rendered)
            self.assertIn('config_file = /opt/airflow/webserver_config.py', rendered)
            self.assertIn('/opt/airflow/bootstrap-user.py', rendered)
            self.assertIn('post-install,post-upgrade', rendered)
            self.assertIn('claimName: airflow-logs', rendered)
            for key in deploy.SECRET_KEYS:
                self.assertNotIn(settings()[key], rendered)


if __name__ == '__main__':
    unittest.main()
