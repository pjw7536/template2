"""운영 자동화 도구(폴더 준비·관리자 인증·smoke·일괄 배포·상태 보고)의 계약을 검증한다."""

import importlib.util
import json
from pathlib import Path
import re
import socket
import ssl
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / 'deploy/shared/scripts'
sys.path.insert(0, str(SCRIPTS))

import app as app_commands  # noqa: E402
import ca_bundle  # noqa: E402
import catalog as registry  # noqa: E402
import deploy_state as state  # noqa: E402
import host_dirs  # noqa: E402
import image_registry  # noqa: E402
import ops_deploy  # noqa: E402
import ops_diagnose  # noqa: E402
import ops_preflight  # noqa: E402
import ops_report  # noqa: E402
import smoke  # noqa: E402

SPEC = importlib.util.spec_from_file_location('admin_env', ROOT / 'deploy/keycloak/scripts/admin_env.py')
admin_env = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(admin_env)
INFRA = ROOT / 'deploy/shared/docs/infrastructure'
IPV4 = re.compile(r'(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])')


class HostDirectoryTests(unittest.TestCase):
    def test_job_creates_only_missing_leaf_under_mounted_parent(self):
        job = host_dirs.job('demo-prepare', 'demo', 'worker-a', 'mirror/busybox:1', [('/appdata/demo/db', 999, 999, '0700')], 'pull')
        pod = job['spec']['template']['spec']
        self.assertEqual(pod['nodeSelector'], {'kubernetes.io/hostname': 'worker-a'})
        self.assertEqual(pod['volumes'][0]['hostPath'], {'path': '/appdata/demo', 'type': 'DirectoryOrCreate'})
        self.assertEqual(pod['imagePullSecrets'], [{'name': 'pull'}])
        script = pod['containers'][0]['command'][2]
        self.assertIn("prepare '/host/0/db' 999 999 0700 '/appdata/demo/db'", script)
        self.assertIn('if [ ! -d "$target" ]', script)
        self.assertNotIn('rm ', script)

    def test_rejects_shallow_or_relative_paths(self):
        for path in ('/appdata', 'relative/dir', '/appdata/../etc'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                host_dirs.job('demo', 'demo', 'node', 'image:1', [(path, 0, 0, '0700')])

    def test_dry_run_validates_without_creating(self):
        calls = []
        run = lambda args, data=None: calls.append(args) or ''
        host_dirs.prepare(run, ['kubectl'], 'demo', 'demo', 'node', 'image:1', [('/appdata/demo', 0, 0, '0700')], dry_run=True)
        self.assertEqual(len(calls), 1)
        self.assertIn('--dry-run=server', calls[0])


    def test_wait_job_returns_on_success_and_fails_fast_with_log_tail(self):
        states = iter([{'status': {}}, {'status': {'succeeded': 1}}])
        sleeps = []
        host_dirs.wait_job(lambda args, data=None: json.dumps(next(states)), ['kubectl'], 'demo', 'job-x', sleep=sleeps.append)
        self.assertEqual(len(sleeps), 1)

        def failing(args, data=None):
            return '저장 경로가 디렉터리가 아닙니다' if 'logs' in args else json.dumps({'status': {'failed': 1}})

        with self.assertRaisesRegex(ValueError, 'Job 실패: demo/job-x. 저장 경로가 디렉터리가 아닙니다'):
            host_dirs.wait_job(failing, ['kubectl'], 'demo', 'job-x', sleep=sleeps.append)
        self.assertEqual(len(sleeps), 1)
        with self.assertRaisesRegex(ValueError, '대기 시간 초과'):
            host_dirs.wait_job(lambda args, data=None: '{}', ['kubectl'], 'demo', 'job-x', timeout=6, interval=3, sleep=sleeps.append)

    def test_wait_job_with_retries_waits_for_the_failed_condition(self):
        # 재시도하는 Job(minio-init)은 Pod 실패 한 번으로 끝내지 않고 Failed 조건(재시도 소진·기한 초과)에서 멈춘다.
        retrying = {'spec': {'backoffLimit': 6}, 'status': {'failed': 1, 'active': 1}}
        failed = {'spec': {'backoffLimit': 6}, 'status': {'failed': 7, 'conditions': [{'type': 'Failed', 'status': 'True'}]}}
        states = iter([retrying, failed])
        sleeps = []

        def run(args, data=None):
            return 'mc: 연결 실패' if 'logs' in args else json.dumps(next(states))

        with self.assertRaisesRegex(ValueError, 'Job 실패: demo/init. mc: 연결 실패'):
            host_dirs.wait_job(run, ['kubectl'], 'demo', 'init', sleep=sleeps.append)
        self.assertEqual(len(sleeps), 1)
        done = {'spec': {'backoffLimit': 6}, 'status': {'conditions': [{'type': 'Complete', 'status': 'True'}]}}
        host_dirs.wait_job(lambda args, data=None: json.dumps(done), ['kubectl'], 'demo', 'init', sleep=sleeps.append)
        self.assertEqual(len(sleeps), 1)


class AdminEnvironmentTests(unittest.TestCase):
    def test_fills_all_admin_variables_only_when_none_is_given(self):
        with tempfile.TemporaryDirectory() as directory:
            env = Path(directory) / 'prod.env'
            env.write_text('# 주석\nbootstrap-admin-username=admin\nbootstrap-admin-password=from-file\n'
                           'keycloak-public-url=https://sso.example.test\n')
            filled = admin_env.admin_environment(env, {'KEYCLOAK_ADMIN_REALM': 'ops'})
            self.assertEqual(filled['KEYCLOAK_ADMIN_URL'], 'https://sso.example.test')
            self.assertEqual(filled['KEYCLOAK_ADMIN_USERNAME'], 'admin')
            self.assertEqual(filled['KEYCLOAK_ADMIN_PASSWORD'], 'from-file')
            self.assertEqual(filled['KEYCLOAK_ADMIN_REALM'], 'ops')
            self.assertEqual(admin_env.admin_environment(env, {})['KEYCLOAK_ADMIN_REALM'], 'master')
            # 하나라도 직접 지정하면 운영 계정을 섞지 않는다.
            for explicit in ({'KEYCLOAK_ADMIN_PASSWORD': 'explicit'}, {'KEYCLOAK_ADMIN_URL': 'https://127.0.0.1:8443'},
                             {'KEYCLOAK_ADMIN_CLIENT_SECRET': 'secret'}):
                self.assertEqual(admin_env.admin_environment(env, explicit), explicit)
            env.write_text('keycloak-public-url=https://sso.example.test\n')
            with self.assertRaisesRegex(ValueError, 'bootstrap-admin-username'):
                admin_env.admin_environment(env, {})


class CaBundleTests(unittest.TestCase):
    def test_bundle_reads_pem_and_der(self):
        pem = ('-----BEGIN CERTIFICATE-----\nMIIBAA==\n-----END CERTIFICATE-----\n')
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / 'b-root.crt').write_text(pem)
            (Path(directory) / 'a-issuing.crt').write_bytes(ssl.PEM_cert_to_DER_cert(pem))
            (Path(directory) / 'note.txt').write_text('무시')
            self.assertEqual(ca_bundle.bundle_text(directory).count('BEGIN CERTIFICATE'), 2)
            self.assertEqual(ca_bundle.bundle_text(Path(directory) / 'missing'), '')

    def test_rebuild_reflects_replaced_ca_while_ensure_keeps_existing_bundle(self):
        pem = '-----BEGIN CERTIFICATE-----\n{}\n-----END CERTIFICATE-----\n'
        with tempfile.TemporaryDirectory() as directory:
            folder, target = Path(directory) / 'ca', Path(directory) / 'bundle.pem'
            folder.mkdir()
            (folder / 'root.crt').write_text(pem.format('MIIBAA=='))
            with patch.object(ca_bundle, 'bundle_path', return_value=target):
                self.assertEqual(ca_bundle.ensure('sso.test', folder), target)
                (folder / 'root.crt').write_text(pem.format('MIIBBB=='))
                ca_bundle.ensure('sso.test', folder)
                self.assertIn('MIIBAA==', target.read_text())
                ca_bundle.rebuild('sso.test', folder)
                self.assertIn('MIIBBB==', target.read_text())
                (folder / 'root.crt').unlink()
                self.assertEqual(ca_bundle.rebuild('sso.test', folder), target)
                self.assertIn('MIIBBB==', target.read_text())


class SmokeTests(unittest.TestCase):
    def test_http_check_tries_paths_until_accepted(self):
        statuses = {'/api/health': 404, '/-/healthy': 200}
        result = smoke.http_check('host.test', ['/api/health', '/-/healthy'], [], fetch=lambda h, p, c, f: statuses[p])
        self.assertTrue(result['ok'])
        self.assertEqual(result['detail'], '/-/healthy 200')
        self.assertTrue(smoke.http_check('host.test', ['/v2/'], [401], fetch=lambda *a: 401)['ok'])
        self.assertFalse(smoke.http_check('host.test', ['/'], [], fetch=lambda *a: 503)['ok'])

    def test_http_check_reports_dns_and_tls_separately(self):
        def dns(*args):
            raise socket.gaierror()
        def tls(*args):
            raise ssl.SSLError('bad')
        self.assertEqual(smoke.http_check('h.test', ['/'], [], fetch=dns)['detail'], 'DNS 조회 실패')
        self.assertIn('TLS 검증 실패', smoke.http_check('h.test', ['/'], [], fetch=tls)['detail'])

    def test_smoke_combines_workloads_ingress_hosts_and_host_ports(self):
        def kube(args, data=None):
            if 'ingress' in args:
                return json.dumps({'items': [{'spec': {'rules': [{'host': 'app.test'}]}}]})
            if 'pods' in args:
                return json.dumps({'items': [{'metadata': {'name': 'p'}, 'status': {'phase': 'Running', 'hostIP': '192.0.2.5'},
                                              'spec': {'containers': [{'name': 'c', 'ports': [{'hostPort': 6380}]}]}}]})
            return json.dumps({'items': [{'kind': 'Deployment', 'metadata': {'name': 'app', 'generation': 1},
                                          'spec': {'replicas': 1, 'template': {'spec': {'containers': [{'image': 'i:1'}]}}},
                                          'status': {'readyReplicas': 1, 'observedGeneration': 1}}]})
        app = {'runtime': {'namespace': 'demo'}, 'smoke': {'paths': ['/health']}}
        checks = smoke.smoke('demo', app, kube, 'demo', fetch=lambda h, p, c, f: 200,
                             tcp=lambda address, port: {'kind': 'tcp', 'target': f'{address}:{port}', 'ok': True, 'detail': '연결 성공'})
        self.assertEqual([(item['kind'], item['ok']) for item in checks], [('workload', True), ('http', True), ('tcp', True)])
        self.assertEqual(checks[2]['target'], '192.0.2.5:6380')

    def test_missing_dns_falls_back_to_app_vip_and_passes_when_service_answers(self):
        app = {'runtime': {'namespace': 'demo'}, 'smoke': {'paths': ['/health']}}

        def kube(args, data=None):
            if 'ingress' in args:
                return json.dumps({'items': [{'spec': {'rules': [{'host': 'demo.test'}]}}]})
            if 'pods' in args:
                return json.dumps({'items': []})
            return json.dumps({'items': [{'kind': 'Deployment', 'metadata': {'name': 'web', 'generation': 1},
                                          'spec': {'replicas': 1, 'template': {'spec': {'containers': [{'image': 'web:1'}]}}},
                                          'status': {'readyReplicas': 1, 'observedGeneration': 1}}]})

        def fetch(host, path, connect, ca_file):
            if connect is None:
                raise socket.gaierror()
            return 200 if connect == '192.0.2.9' else 503

        checks = smoke.smoke('demo', app, kube, 'demo', fetch=fetch, vip='192.0.2.9')
        http = next(item for item in checks if item['kind'] == 'http')
        self.assertTrue(http['ok'] and http['dnsMissing'])
        self.assertIn('DNS 미등록', http['detail'])
        failing = smoke.smoke('demo', app, kube, 'demo', fetch=fetch, vip='192.0.2.10')
        self.assertFalse(next(item for item in failing if item['kind'] == 'http')['ok'])
        # VIP를 모르면 기존처럼 DNS 실패로 남긴다.
        unknown = smoke.smoke('demo', app, kube, 'demo', fetch=fetch)
        self.assertEqual(next(item for item in unknown if item['kind'] == 'http')['detail'], 'DNS 조회 실패')

    def test_host_ports_can_be_limited_to_always_listening_ports(self):
        pods = [{'status': {'phase': 'Running', 'hostIP': '192.0.2.5'}, 'spec': {'containers': [{'ports': [
            {'name': 'ftp', 'hostPort': 6380}, {'name': 'passive-0', 'hostPort': 8076}]}]}}]
        self.assertEqual(smoke.host_ports(pods), [('192.0.2.5', 6380), ('192.0.2.5', 8076)])
        self.assertEqual(smoke.host_ports(pods, ['ftp']), [('192.0.2.5', 6380)])
        self.assertEqual(state.read_catalog()['apps']['ftp']['smoke']['hostPorts'], ['ftp'])


# 변경 전 Makefile이 앱마다 실행하던 명령. 디스패처가 같은 인자를 만드는지 고정한다.
EXPECTED_COMMANDS = {
    ('ingress', 'check'): 'deploy/shared/ingress/manage.py check --context ctx --vip-backends ',
    ('ingress', 'up'): 'deploy/shared/ingress/manage.py up --context ctx --vip-backends ',
    ('keycloak', 'check'): 'deploy/keycloak/scripts/up.py --context ctx --env R/deploy/keycloak/env/prod.env --check-only',
    ('keycloak', 'up'): 'deploy/keycloak/scripts/up.py --context ctx --env R/deploy/keycloak/env/prod.env',
    ('minio', 'check'): 'deploy/minio/scripts/manage.py check --env R/deploy/minio/env/prod.env --context ctx',
    ('minio', 'up'): 'deploy/minio/scripts/manage.py up --env R/deploy/minio/env/prod.env --context ctx',
    ('registry', 'check'): 'deploy/registry/scripts/manage.py check --env R/deploy/registry/env/k8s.env --context ctx '
                           '--push-env R/deploy/registry/env/push-initial.env',
    ('registry', 'up'): 'deploy/registry/scripts/manage.py up --env R/deploy/registry/env/k8s.env --context ctx '
                        '--push-env R/deploy/registry/env/push-initial.env',
    ('airflow', 'check'): 'deploy/airflow/scripts/up.py --context ctx --env R/deploy/airflow/env/k8s.env --tls-source  --check-only',
    ('airflow', 'up'): 'deploy/airflow/scripts/up.py --context ctx --env R/deploy/airflow/env/k8s.env --tls-source ',
    ('monitoring', 'check'): 'deploy/monitoring/scripts/manage.py check --env R/deploy/monitoring/env/k8s.env',
    ('monitoring', 'up'): 'deploy/monitoring/scripts/manage.py deploy --context ctx --env R/deploy/monitoring/env/k8s.env '
                          '--grafana-env R/deploy/monitoring/env/grafana-initial.env',
    ('headlamp', 'check'): 'deploy/headlamp/scripts/manage.py check --env R/deploy/headlamp/env/k8s.env',
    ('headlamp', 'up'): 'deploy/headlamp/scripts/manage.py deploy --context ctx --env R/deploy/headlamp/env/k8s.env',
    ('ftp', 'check'): 'deploy/ftp/scripts/up.py --check-only',
    ('ftp', 'up'): 'deploy/ftp/scripts/up.py',
    ('portal', 'check'): 'deploy/portal/scripts/up.py --context ctx --api-env R/deploy/portal/env/prod/api.env '
                         '--web-env R/deploy/portal/env/prod/web.env --check-only',
    ('portal', 'up'): 'deploy/portal/scripts/up.py --context ctx --api-env R/deploy/portal/env/prod/api.env '
                      '--web-env R/deploy/portal/env/prod/web.env',
}


def make_targets():
    """Makefile의 명시적 타깃과, 패턴 규칙이 카탈로그의 앱마다 제공하는 타깃."""
    text = (ROOT / 'Makefile').read_text()
    targets = set(re.findall(r'^([A-Za-z0-9_.-]+):(?!=)', text, re.M))
    for suffix in re.findall(r'^%-([a-z]+):', text, re.M):
        targets.update(f'{name}-{suffix}' for name in registry.read_catalog()['apps'])
    return targets


class CatalogTests(unittest.TestCase):
    def test_every_app_declares_steps_that_exist_and_known_dependencies(self):
        catalog = registry.read_catalog()
        targets = make_targets()
        for name, app in catalog['apps'].items():
            with self.subTest(app=name):
                self.assertTrue(set(app['steps']) <= targets, f'Makefile에 없는 단계: {set(app["steps"]) - targets}')
                required = ('check', 'up', 'smoke') if app['runtime'] else ('check', 'up')
                for suffix in required:
                    self.assertIn(f'{name}-{suffix}', targets)
                    self.assertIn(f'{name}-{suffix}', app['steps'])
                self.assertTrue(set(app['dependsOn']) <= set(catalog['apps']) - {name})
                for path in registry.inputs(app, {}).values():
                    self.assertTrue(Path(path).is_file(), f'기본 입력 파일 없음: {path}')
                for command in registry.static_commands(app):
                    for part in command:
                        if part.startswith(('deploy/', 'apps/')):
                            self.assertTrue((ROOT / part).exists(), f'정적 검사 대상 없음: {part}')

    def test_check_runs_before_any_step_that_changes_the_cluster(self):
        # 이미지 빌드·Keycloak client 등록 같은 변경 단계가 검사보다 먼저 실행되지 않는다.
        for name, app in registry.read_catalog()['apps'].items():
            self.assertEqual(app['steps'][0], f'{name}-check', name)

    def test_dispatcher_builds_the_same_commands_the_makefile_used(self):
        catalog = registry.read_catalog()
        for (name, action), expected in EXPECTED_COMMANDS.items():
            with self.subTest(app=name, action=action):
                command = registry.command(catalog['apps'][name], action, 'ctx', environ={})
                self.assertEqual(command[0], 'python3')
                self.assertEqual(' '.join(command[1:]).replace(str(ROOT), 'R'), expected)

    def test_environment_variables_select_inputs_for_every_tool(self):
        app = registry.read_catalog()['apps']['portal']
        environ = {'PROD_API_ENV_FILE': '/outside/api.env'}
        command = registry.command(app, 'up', 'ctx', environ=environ)
        self.assertEqual(command[command.index('--api-env') + 1], '/outside/api.env')
        self.assertEqual(registry.primary_env(app, environ), '/outside/api.env')
        self.assertEqual(registry.record_inputs(app, environ), ['/outside/api.env', str(ROOT / 'deploy/portal/env/prod/web.env')])
        child = registry.child_environment(app, 'ctx', environ)
        self.assertEqual((child['KUBE_CONTEXT'], child['PROD_API_ENV_FILE']), ('ctx', '/outside/api.env'))

    def test_initial_account_files_are_not_recorded_as_deploy_inputs(self):
        # Secret이 없을 때만 쓰는 초기 계정 파일을 기록하면, 나중에 파일만 바뀌어도 불일치로 보인다.
        apps = registry.read_catalog()['apps']
        self.assertEqual(registry.record_inputs(apps['registry'], {}), [str(ROOT / 'deploy/registry/env/k8s.env')])
        self.assertEqual(registry.record_inputs(apps['ftp'], {}), [str(ROOT / 'deploy/ftp/env/prod.env')])

    def test_drift_renders_airflow_with_the_flag_deploy_uses(self):
        # airflow-up은 신규 DAG를 일시정지로 배포한다. 대조 렌더가 다르면 정상 배포도 항상 불일치가 된다.
        render = registry.command(registry.read_catalog()['apps']['airflow'], 'render', 'ctx', '/out', environ={})
        self.assertIn('--pause-new-dags', render)
        for script in ('deploy/airflow/scripts/up.py', 'deploy/airflow/scripts/server.py'):
            self.assertIn('pause_new_dags=True', (ROOT / script).read_text(), script)

    def test_hosts_come_from_the_selected_env_as_host_or_url(self):
        with tempfile.TemporaryDirectory() as directory:
            env = Path(directory) / 'demo.env'
            env.write_text('WEB_URL=https://web.demo.test/path\nAPI_HOST=api.demo.test\nEMPTY=\n')
            app = {'inputs': [{'variable': 'DEMO_ENV', 'default': 'unused'}], 'hosts': ['WEB_URL', 'API_HOST', 'EMPTY', 'MISSING']}
            self.assertEqual(registry.hosts(app, {'DEMO_ENV': str(env)}), ['web.demo.test', 'api.demo.test'])

    def test_catalog_rejects_undeclared_command_variables_and_missing_render(self):
        base = json.loads((ROOT / 'deploy/shared/apps.json').read_text())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'apps.json'
            broken = json.loads(json.dumps(base))
            broken['apps']['minio']['commands']['up'].append('{UNDECLARED}')
            path.write_text(json.dumps(broken))
            with self.assertRaisesRegex(ValueError, 'UNDECLARED'):
                registry.read_catalog(path)
            broken = json.loads(json.dumps(base))
            del broken['apps']['minio']['commands']['render']
            path.write_text(json.dumps(broken))
            with self.assertRaisesRegex(ValueError, 'commands.render'):
                registry.read_catalog(path)

    def test_no_shared_tool_branches_on_an_app_name(self):
        # 앱을 추가할 때 공용 도구를 고치지 않도록, 카탈로그를 읽는 도구에는 앱 이름 문자열을 두지 않는다.
        names = [name for name in registry.read_catalog()['apps'] if name != 'ingress']
        for script in ('catalog.py', 'app.py', 'deploy_state.py', 'ops_deploy.py', 'ops_preflight.py', 'ops_diagnose.py', 'smoke.py'):
            code = re.sub(r'"""(?:.|\n)*?"""|#.*', '', (SCRIPTS / script).read_text())
            found = [name for name in names if re.search(rf"['\"/]{name}['\"/]", code)]
            self.assertEqual(found, [], f'{script}: 앱 이름 분기')


class AppDispatcherTests(unittest.TestCase):
    def result(self, code=0, stdout=''):
        return type('Result', (), {'returncode': code, 'stdout': stdout, 'stderr': ''})()

    def test_up_records_the_deploy_only_after_success(self):
        for code, recorded in ((0, True), (1, False)):
            calls = []

            def run(argv, **kwargs):
                calls.append(list(map(str, argv)))
                return self.result(code if 'record' not in argv else 0)

            self.assertEqual(app_commands.main(['up', 'minio', '--context', 'ctx'], run=run), code)
            self.assertEqual(any('record' in call for call in calls), recorded)
            if recorded:
                record = next(call for call in calls if 'record' in call)
                self.assertEqual(record[record.index('--input') + 1], str(ROOT / 'deploy/minio/env/prod.env'))

    def test_check_never_records_and_missing_context_stops_before_running(self):
        calls = []
        run = lambda argv, **kwargs: calls.append(argv) or self.result()
        self.assertEqual(app_commands.main(['check', 'minio', '--context', 'ctx'], run=run), 0)
        self.assertEqual(len(calls), 1)
        calls.clear()
        with patch.dict('os.environ', {'KUBE_CONTEXT': ''}):
            self.assertEqual(app_commands.main(['up', 'minio', '--context', ''], run=run), 1)
        self.assertEqual(calls, [])

    def test_unknown_app_is_rejected(self):
        self.assertEqual(app_commands.main(['up', 'unknown', '--context', 'ctx'], run=lambda *a, **k: self.result()), 1)

    def test_render_saves_stdout_or_returns_declared_files(self):
        with tempfile.TemporaryDirectory() as directory:
            run = lambda argv, **kwargs: self.result(stdout='{"kind": "List", "items": []}')
            apps = registry.read_catalog()['apps']
            files = app_commands.render(apps['minio'], 'ctx', directory, {}, run)
            self.assertEqual([path.name for path in files], ['minio.json'])
            self.assertIn('"List"', files[0].read_text())
            files = app_commands.render(apps['airflow'], 'ctx', directory, {}, run)
            self.assertEqual([path.relative_to(directory).as_posix() for path in files],
                             ['airflow/airflow.yaml', 'airflow/storage.json', 'airflow/postgres.json'])

    def test_settings_only_app_has_no_smoke_or_record(self):
        calls = []
        run = lambda argv, **kwargs: calls.append(argv) or self.result()
        self.assertEqual(app_commands.main(['smoke', 'iam', '--context', 'ctx'], run=run), 0)
        self.assertEqual(app_commands.record('iam', 'ctx', {}, run), 0)
        self.assertEqual(calls, [])


class PreflightTests(unittest.TestCase):
    def test_registered_host_passes_and_missing_dns_does_not_block(self):
        with tempfile.TemporaryDirectory() as directory:
            env = Path(directory) / 'demo.env'
            env.write_text('WEB_HOST=web.demo.test\n')
            app = {'inputs': [{'variable': 'DEMO_ENV', 'default': 'unused'}], 'hosts': ['WEB_HOST']}
            with patch.dict('os.environ', {'DEMO_ENV': str(env)}):
                found = ops_preflight.check_hosts(app, ['kubectl'], 'ctx', registered=lambda host: True, lookup=lambda host: False)
        self.assertEqual([entry['state'] for entry in found], [ops_preflight.OK, ops_preflight.INFO])
        self.assertEqual(ops_preflight.blocking(found), [])
        self.assertIn('#dns', found[1]['reference'])

    def test_unregistered_host_with_matching_files_becomes_a_register_command(self):
        with tempfile.TemporaryDirectory() as directory:
            env = Path(directory) / 'demo.env'
            env.write_text('WEB_HOST=web.demo.test\n')
            app = {'inputs': [{'variable': 'DEMO_ENV', 'default': 'unused'}], 'hosts': ['WEB_HOST']}
            files = (Path(directory) / 'site/fullchain.crt', Path(directory) / 'site/private.key')
            with patch.dict('os.environ', {'DEMO_ENV': str(env)}):
                ready = ops_preflight.check_hosts(app, ['kubectl'], 'ctx', registered=lambda host: False,
                                                  lookup=lambda host: True, find=lambda host: files)
                missing = ops_preflight.check_hosts(app, ['kubectl'], 'ctx', registered=lambda host: False,
                                                    lookup=lambda host: True, find=lambda host: None)
        self.assertEqual(ready[0]['state'], ops_preflight.ACTION)
        self.assertEqual(ready[0]['command'][:4], ['make', 'ingress-tls-up', 'KUBE_CONTEXT=ctx', 'TLS_HOST=web.demo.test'])
        self.assertEqual(missing[0]['state'], ops_preflight.BLOCKED)
        self.assertIn('#인증서-발급', missing[0]['reference'])

    def test_certificate_files_are_matched_by_host(self):
        with tempfile.TemporaryDirectory() as directory:
            for site in ('a.test', 'b.test'):
                (Path(directory) / site).mkdir()
                (Path(directory) / site / 'fullchain.crt').write_text(site)
                (Path(directory) / site / 'private.key').write_text('key')
            (Path(directory) / 'ca').mkdir()

            def validate(host, certificate, key):
                if certificate != 'b.test':
                    raise ValueError('다른 인증서')

            found = ops_preflight.certificate_files('x.b.test', validate, directory)
            self.assertEqual(found[0].parent.name, 'b.test')
            self.assertIsNone(ops_preflight.certificate_files('x.b.test', lambda *a: (_ for _ in ()).throw(ValueError()), directory))

    def test_prepare_runs_actions_and_turns_failures_into_blockers(self):
        results = [ops_preflight.item('chart', ops_preflight.ACTION, '없음', command=['make', 'demo-fetch-chart']),
                   ops_preflight.item('공용 TLS', ops_preflight.ACTION, '등록', command=['make', 'ingress-tls-up']),
                   ops_preflight.item('DNS', ops_preflight.INFO, '없음')]
        executed = []

        def execute(command):
            executed.append(command)
            return ('fetch-chart' in command[1], 'chart 준비 완료' if 'fetch-chart' in command[1] else '오류: 인증서와 공개 도메인이 다릅니다.')

        with patch('builtins.print'):
            ops_preflight.prepare(results, execute)
        self.assertEqual(len(executed), 2)
        self.assertEqual([entry['state'] for entry in results], [ops_preflight.OK, ops_preflight.BLOCKED, ops_preflight.INFO])
        self.assertIn('공개 도메인이 다릅니다', results[1]['detail'])
        self.assertEqual(len(ops_preflight.blocking(results)), 1)

    def test_successful_preparation_is_followed_by_a_fresh_evaluation(self):
        # chart를 받은 뒤에야 할 수 있는 검사(정적 검사·앱 검사)가 준비 뒤에 다시 평가된다.
        first = [ops_preflight.item('저장소 원본', ops_preflight.INFO, 'chart를 받은 뒤 검사합니다.'),
                 ops_preflight.item('chart', ops_preflight.ACTION, '없음', command=['make', 'demo-fetch-chart'])]
        second = [ops_preflight.item('저장소 원본', ops_preflight.OK, '통과'), ops_preflight.item('chart', ops_preflight.OK, '있음'),
                  ops_preflight.item('앱 검사', ops_preflight.OK, '통과')]
        with patch.object(ops_preflight, 'collect', side_effect=[first, second]) as collect, \
                patch.object(ops_preflight, 'run_quiet', return_value=(True, 'chart 준비 완료')), patch('builtins.print'):
            results = ops_preflight.evaluate('demo', {}, 'ctx', run_prepare=True)
        self.assertEqual(collect.call_count, 2)
        self.assertEqual(ops_preflight.blocking(results), [])

    def test_failed_preparation_keeps_its_reason_and_is_not_reevaluated(self):
        first = [ops_preflight.item('chart', ops_preflight.ACTION, '없음', command=['make', 'demo-fetch-chart'])]
        with patch.object(ops_preflight, 'collect', return_value=first) as collect, \
                patch.object(ops_preflight, 'run_quiet', return_value=(False, '오류: 미러에 chart가 없습니다')), patch('builtins.print'):
            results = ops_preflight.evaluate('demo', {}, 'ctx', run_prepare=True)
        self.assertEqual(collect.call_count, 1)
        self.assertIn('자동 준비 실패: 오류: 미러에 chart가 없습니다', results[0]['detail'])
        # 조회만 요청하면 준비 명령을 실행하지 않는다.
        with patch.object(ops_preflight, 'collect', return_value=[ops_preflight.item('chart', ops_preflight.ACTION, '없음', command=['x'])]), \
                patch.object(ops_preflight, 'run_quiet') as execute:
            ops_preflight.evaluate('demo', {}, 'ctx')
        execute.assert_not_called()

    def test_app_check_failure_reports_the_tool_error_not_the_make_error(self):
        output = '검사 시작\n오류: keycloak-runtime: 기존 Secret과 입력이 다릅니다.\n\n'
        with patch.object(ops_preflight, 'run_quiet', return_value=(False, output)) as execute:
            entry = ops_preflight.check_app('keycloak', 'ctx')
        self.assertEqual(entry['state'], ops_preflight.BLOCKED)
        self.assertIn('기존 Secret과 입력이 다릅니다', entry['detail'])
        self.assertNotIn('make', execute.call_args.args[0][0])

    def test_references_point_to_sections_of_the_access_table(self):
        access = (ROOT / ops_preflight.ACCESS).read_text()
        slugs = {re.sub(r'[^\w\- ]', '', heading.strip().lower()).replace(' ', '-') for heading in re.findall(r'(?m)^#+\s+(.*)$', access)}
        source = (SCRIPTS / 'ops_preflight.py').read_text()
        for anchor in re.findall(r"\{ACCESS\}#([^'\"]+)", source):
            self.assertIn(anchor, slugs, f'접근 경로 표에 없는 절: {anchor}')


class DeployStateInputTests(unittest.TestCase):
    def test_inputs_inside_checkout_are_recorded_relative_to_root(self):
        inside = state.ROOT / 'deploy/keycloak/env/prod.env'
        self.assertEqual(state.input_key(inside), 'deploy/keycloak/env/prod.env')
        self.assertEqual(state.file_digest('deploy/keycloak/env/prod.env'), state.file_digest(inside))
        with tempfile.NamedTemporaryFile() as outside:
            self.assertEqual(state.input_key(outside.name), str(Path(outside.name).resolve()))


    def test_record_uses_namespace_declared_in_input_env(self):
        with tempfile.TemporaryDirectory() as directory:
            env = Path(directory) / 'k8s.env'
            env.write_text('NAMESPACE=airflow-prod\nNODE_NAME=worker\n')
            applied = []

            def kube(args, data=None):
                if 'apply' in args:
                    applied.append(json.loads(data))
                return json.dumps({'items': []})

            git = lambda args: 'a' * 40 + '\n' if args[0] == 'rev-parse' else ''
            with patch.object(state, 'git_runner', return_value=git), patch.object(state, 'kube_runner', return_value=kube), \
                    patch.object(sys, 'argv', ['deploy_state.py', 'record', 'airflow', '--context', 'ctx', '--input', str(env)]):
                self.assertEqual(state.main(), 0)
            self.assertEqual(applied[0]['metadata']['namespace'], 'airflow-prod')


class OpsDeployTests(unittest.TestCase):
    def test_stops_at_first_failed_step_without_drift_check(self):
        catalog = {'apps': {'demo': {'steps': ['demo-check', 'demo-up', 'demo-smoke'], 'dependsOn': [], 'runtime': {'namespace': 'demo'}}}}
        calls = []

        def run(command, **kwargs):
            calls.append(command)
            return type('Result', (), {'returncode': 1 if 'demo-up' in command else 0, 'stdout': '{"resultCode": 0}'})()

        summary = ops_deploy.deploy('demo', catalog, 'ctx', run)
        self.assertEqual(summary['failedStep'], 'demo-up')
        self.assertEqual([step['target'] for step in summary['steps']], ['demo-check', 'demo-up'])
        self.assertFalse(any('drift-check' in call for call in calls))
        self.assertTrue(all('KUBE_CONTEXT=ctx' in call for call in calls))

    def test_reports_drift_result_after_all_steps(self):
        catalog = {'apps': {'demo': {'steps': ['demo-up'], 'dependsOn': [], 'runtime': {'namespace': 'demo'}}}}
        run = lambda command, **kwargs: type('Result', (), {'returncode': 0, 'stdout': '{"resultCode": 1}'})()
        self.assertEqual(ops_deploy.deploy('demo', catalog, 'ctx', run)['driftResultCode'], 1)

    def test_settings_only_app_skips_drift_check(self):
        catalog = {'apps': {'demo': {'steps': ['demo-check', 'demo-up'], 'dependsOn': [], 'runtime': None}}}
        calls = []
        run = lambda command, **kwargs: calls.append(command) or type('Result', (), {'returncode': 0, 'stdout': ''})()
        summary = ops_deploy.deploy('demo', catalog, 'ctx', run)
        self.assertEqual((summary['failedStep'], summary['driftResultCode']), (None, 0))
        self.assertFalse(any('drift-check' in call for call in calls))

    def test_blocked_preflight_stops_before_any_step_and_lists_what_is_needed(self):
        blocked = ops_preflight.item('공용 TLS demo.test', ops_preflight.BLOCKED, '인증서 파일 필요', reference='access.md#인증서-발급')
        pending = ops_preflight.item('DNS demo.test', ops_preflight.INFO, 'DNS에 없습니다.', reference='access.md#dns')
        output = []
        with patch.object(ops_deploy.preflight, 'evaluate', return_value=[blocked, pending]), \
                patch.object(ops_deploy, 'deploy') as deploy, patch('builtins.print', side_effect=lambda *a, **k: output.append(a[0])):
            code = ops_deploy.main(['keycloak', '--context', 'ctx'])
        deploy.assert_not_called()
        summary = json.loads(output[-1])
        self.assertEqual((code, summary['failedStep']), (1, 'preflight'))
        self.assertEqual(summary['blocked'][0]['reference'], 'access.md#인증서-발급')
        self.assertEqual(summary['pending'][0]['item'], 'DNS demo.test')

    def test_ready_preflight_runs_steps_and_keeps_pending_items_in_summary(self):
        pending = ops_preflight.item('DNS demo.test', ops_preflight.INFO, 'DNS에 없습니다.')
        done = {'app': 'keycloak', 'blocked': [], 'pending': [], 'steps': [], 'failedStep': None, 'driftResultCode': 0}
        output = []
        with patch.object(ops_deploy.preflight, 'evaluate', return_value=[pending]), \
                patch.object(ops_deploy, 'deploy', return_value=done), patch('builtins.print', side_effect=lambda *a, **k: output.append(a[0])):
            code = ops_deploy.main(['keycloak', '--context', 'ctx'])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output[-1])['pending'][0]['item'], 'DNS demo.test')


class ReportRedactionTests(unittest.TestCase):
    def setUp(self):
        self.table = json.loads((INFRA / 'aliases.json').read_text())

    def test_alias_table_covers_every_address_and_node_in_infrastructure_docs(self):
        known = {item['ip'] for group in ('nodes', 'addresses') for item in self.table[group].values()}
        documented = set()
        for name in ('servers.md', 'network.md', 'services.md', 'operations.md', 'repositories.md', 'pending.md'):
            documented |= set(IPV4.findall((INFRA / name).read_text()))
        self.assertEqual(documented - known, set(), '별칭 표에 없는 문서의 IP')
        servers = (INFRA / 'servers.md').read_text()
        for alias, node in self.table['nodes'].items():
            self.assertIn(f'`{node["name"]}` | `{node["ip"]}`', servers, f'{alias}: 서버 목록과 다른 이름·IP')
        aliases = [alias for group in ('nodes', 'addresses', 'domains') for alias in self.table[group]]
        self.assertEqual(len(aliases), len(set(aliases)))

    def test_redaction_leaves_no_real_value_and_numbers_unknown_ones(self):
        redactor = ops_report.Redactor(self.table)
        redactor.register_nodes(['khplane01w09', 'new-worker-7'])
        raw = ('kube-apiserver-khplane01w06 on 10.172.40.84, vip 10.172.26.150:443, https://sso.etch.samsungds.net/realms/etch '
               'image repository.samsungds.net/proxy/keycloak:26.7.1 api https://apigw.samsungds.net/x new-worker-7 198.51.100.9 v1.36.0')
        text = redactor.text(raw)
        self.assertEqual(text, 'kube-apiserver-N-CP1 on N-CP1, vip VIP-APP:443, https://sso.ZONE-A/realms/etch '
                               'image MIRROR-A/proxy/keycloak:26.7.1 api https://HOST-미등록-1/x N-미등록-1 IP-미등록-1 v1.36.0')
        self.assertIsNone(IPV4.search(text))
        self.assertNotIn('samsungds', text)
        self.assertEqual(redactor.text('198.51.100.9 again'), 'IP-미등록-1 again')
        # 등록된 값으로 시작하는 다른 주소·이름을 별칭으로 만들지 않고, 대소문자가 달라도 가린다.
        self.assertEqual(redactor.text('10.172.40.870'), 'IP-미등록-2')
        self.assertEqual(redactor.text('10.172.40.87:443 10.172.40.87.'), 'N-W1:443 N-W1.')
        self.assertEqual(redactor.text('KHPLANEW01 SSO.ETCH.SAMSUNGDS.NET'), 'N-M1 SSO.ZONE-A')
        self.assertNotIn('172', redactor.short('timeout dialing 10.172.40.87:10250 after wait', 24))

    def test_report_output_contains_no_address_node_name_or_domain(self):
        nodes = [{'metadata': {'name': item['name'], 'labels': {'node-role.kubernetes.io/control-plane': ''}},
                  'spec': {}, 'status': {'conditions': [{'type': 'Ready', 'status': 'True'}], 'capacity': {'cpu': '8', 'memory': '16384Ki'},
                                         'addresses': [{'type': 'InternalIP', 'address': item['ip']}],
                                         'nodeInfo': {'kubeletVersion': 'v1.36.0', 'osImage': 'Ubuntu 22.04.2 LTS'}}}
                 for item in self.table['nodes'].values()]

        def kube(args, data=None):
            if args[:2] == ['get', 'nodes']:
                return json.dumps({'items': nodes})
            if 'version' in args:
                return json.dumps({'serverVersion': {'gitVersion': 'v1.36.0'}})
            if '--raw' in args:
                raise state.QueryError('dial tcp 10.172.40.84:10250: i/o timeout')
            if 'namespace' in args:
                return 'namespace/etch-sso'
            if 'ingress' in args:
                return json.dumps({'items': [{'spec': {'rules': [{'host': 'sso.etch.samsungds.net'}]}}]})
            if 'traefik' in args and 'deployment' in args:
                return json.dumps({'spec': {'replicas': 1, 'template': {'spec': {'containers': [{
                    'name': 'traefik', 'image': 'repository.samsungds.net/proxy/traefik:v3',
                    'args': ['--providers.kubernetesingress.namespaces=etch-sso,minio']}]}}}, 'status': {'readyReplicas': 1}})
            if 'pods' in args:
                return json.dumps({'items': [{'metadata': {'name': 'keycloak-0'}, 'spec': {'nodeName': 'khplane01w09', 'containers': []},
                                              'status': {'phase': 'Running', 'podIP': '10.244.1.7', 'hostIP': '10.172.40.87'}}]})
            if 'events' in args:
                return json.dumps({'items': [{'reason': 'FailedMount', 'count': 3, 'involvedObject': {'kind': 'Pod', 'name': 'keycloak-0'},
                                              'message': 'node khplane01w09 (10.172.40.87) mount failed'}]})
            return json.dumps({'items': []})

        git = lambda args: {'rev-parse': 'a' * 40 + '\n'}.get(args[0], '')
        redactor = ops_report.Redactor(self.table)
        with patch.object(state, 'git_runner', return_value=git), patch.object(state, 'kube_runner', return_value=kube), \
                patch.object(ops_report, 'endpoint', return_value=('10.172.26.150', '검증 통과, 만료 Jan  1 00:00:00 2027 GMT')), \
                patch.object(ops_report, 'fetch_status', return_value=200), \
                patch.object(ops_report.smoke_checks, 'tcp_check', return_value={'detail': '연결 성공', 'target': 'x', 'ok': True}), \
                patch.object(ops_report, 'command_version', return_value='v1'):
            text = ops_report.finish(ops_report.build('keycloak', 'ctx', redactor, skip_drift=True), redactor)
        self.assertIsNone(IPV4.search(text), text)
        for item in self.table['nodes'].values():
            self.assertNotIn(item['name'], text)
        self.assertNotIn('samsungds', text)
        for expected in ('## 1. 클러스터', '## 2. 노드', '## 3. 공용 진입점', '## 4. 앱별 상태', '### keycloak',
                         '## 5. 확인하지 못한 항목', 'N-CP1', 'N-W1', 'sso.ZONE-A', 'VIP-APP', 'MIRROR-A/proxy/traefik:v3'):
            self.assertIn(expected, text)
        self.assertNotIn('별칭 미등록', text)


class DiagnoseTests(unittest.TestCase):
    APP = {'runtime': {'namespace': 'demo'}, 'smoke': {'paths': ['/health']}}

    def kube(self, pods, namespace=True, claims=(), logs='boom'):
        def run(args, data=None):
            if 'namespace' in args:
                return 'namespace/demo' if namespace else ''
            if 'nodes' in args:
                return json.dumps({'items': [{'metadata': {'name': 'worker-a'}, 'status': {'conditions': [{'type': 'Ready', 'status': 'True'}]}}]})
            if 'pods' in args:
                return json.dumps({'items': pods})
            if 'pvc' in args:
                return json.dumps({'items': [{'metadata': {'name': name}, 'status': {'phase': phase}} for name, phase in claims]})
            if 'events' in args:
                return json.dumps({'items': [{'reason': 'BackOff', 'count': 4, 'involvedObject': {'kind': 'Pod', 'name': 'app-1'}, 'message': 'Back-off restarting'}]})
            if 'logs' in args:
                return logs
            return json.dumps({'items': []})
        return run

    def pod(self, waiting=None, ready=True, restarts=0, phase='Running'):
        state_ = {'waiting': {'reason': waiting}} if waiting else {'running': {}}
        return {'metadata': {'name': 'app-1'}, 'spec': {'nodeName': 'worker-a'},
                'status': {'phase': phase, 'containerStatuses': [{'name': 'c', 'ready': ready, 'restartCount': restarts, 'state': state_}]}}

    def test_healthy_app_reports_no_problem(self):
        checks = lambda *args: [{'kind': 'http', 'target': 'h', 'ok': True, 'detail': '/health 200'}]
        lines, problems = ops_diagnose.diagnose('demo', self.APP, self.kube([self.pod()]), 'demo', checks)
        self.assertEqual(problems, 0)
        self.assertIn('- 이상 없음', lines)
        self.assertFalse(any(line.startswith('## 로그') for line in lines))

    def test_failing_pod_collects_logs_and_points_to_guide_rows(self):
        checks = lambda *args: [{'kind': 'http', 'target': 'h', 'ok': False, 'detail': '정상 응답 없음: /health 503'},
                                {'kind': 'http', 'target': 'g', 'ok': False, 'detail': 'DNS 조회 실패'}]
        pods = [self.pod(waiting='CrashLoopBackOff', ready=False, restarts=5)]
        lines, problems = ops_diagnose.diagnose('demo', self.APP, self.kube(pods, claims=[('data', 'Pending')]), 'demo', checks)
        text = '\n'.join(lines)
        self.assertEqual(problems, 3)
        for row in ('CrashLoopBackOff', '404 / 503', 'Pending, PVC Pending', 'smoke의 `DNS 조회 실패`'):
            self.assertIn(f'표의 행: {row}', text)
        self.assertIn('## 로그 끝 20줄: app-1', text)
        self.assertIn('(재시작 전)', text)
        self.assertIn('deploy/demo/README.md의 `문제 해결과 멈춤 조건`', text)
        self.assertIn('BackOff Pod/app-1 x4', text)

    def test_missing_namespace_means_not_installed(self):
        lines, problems = ops_diagnose.diagnose('demo', self.APP, self.kube([], namespace=False), 'demo', lambda *a: [])
        self.assertEqual(problems, 1)
        self.assertIn('A. 최초 설치', lines[-1])

    def test_guide_row_names_exist_in_common_troubleshooting_table(self):
        table = (ROOT / 'deploy/README.md').read_text().split('## 장애 조회')[1]
        for row in ops_diagnose.GUIDE_ROWS.values():
            self.assertIn(f'| {row} |', table, f'배포 가이드 장애 조회 표에 없는 행: {row}')
        self.assertIn('make ops-diagnose APP=<app> KUBE_CONTEXT="<context>"', table)


class ImageRegistryTests(unittest.TestCase):
    def test_split_distinguishes_registry_host_from_local_name(self):
        self.assertEqual(image_registry.split('store.test/tailwind/api:abc'), ('store.test', 'tailwind/api', 'abc'))
        self.assertEqual(image_registry.split('localhost:5000/app:1'), ('localhost:5000', 'app', '1'))
        self.assertEqual(image_registry.split('airflow:3.3.2-x'), ('', 'airflow', '3.3.2-x'))
        with self.assertRaises(ValueError):
            image_registry.split('store.test/app')

    def test_remote_exists_maps_200_and_404_and_reports_other_errors(self):
        from urllib.error import HTTPError

        class Opener:
            def __init__(self, code):
                self.code, self.requests = code, []

            def open(self, request, timeout=None):
                self.requests.append(request)
                if self.code != 200:
                    raise HTTPError(request.full_url, self.code, 'x', {}, None)
                return tempfile.TemporaryFile()

        found = Opener(200)
        self.assertTrue(image_registry.remote_exists('store.test/tailwind/api:abc', opener=found))
        self.assertEqual(found.requests[0].full_url, 'https://store.test/v2/tailwind/api/manifests/abc')
        self.assertEqual(found.requests[0].get_method(), 'HEAD')
        self.assertFalse(image_registry.remote_exists('store.test/tailwind/api:abc', opener=Opener(404)))
        with self.assertRaisesRegex(ValueError, 'HTTP 500'):
            image_registry.remote_exists('store.test/tailwind/api:abc', opener=Opener(500))
        self.assertFalse(image_registry.remote_exists('airflow:1'))

    def test_push_logs_in_with_stdin_password_then_pushes(self):
        with tempfile.TemporaryDirectory() as directory:
            account = Path(directory) / 'push.env'
            account.write_text('# 계정\nREGISTRY_USER=publisher\nREGISTRY_PASSWORD=push-secret\n')
            calls = []
            image_registry.push(lambda args, data=None: calls.append((args, data)), ['nerdctl'], 'store.test/app:1', account)
            self.assertEqual(calls[0], (['nerdctl', 'login', '--username', 'publisher', '--password-stdin', 'store.test'], 'push-secret\n'))
            self.assertEqual(calls[1], (['nerdctl', 'push', 'store.test/app:1'], None))
            self.assertFalse(any('push-secret' in ' '.join(args) for args, _ in calls))
            with self.assertRaises(ValueError):
                image_registry.push(lambda *a, **k: None, ['nerdctl'], 'app:1', account)

    def test_build_passes_only_given_args_and_context_last(self):
        calls = []
        image_registry.build(lambda args, data=None: calls.append(args), ['nerdctl'], 'store.test/app:1', '/src',
                             build_args={'B': '2', 'A': '1'}, buildkit_host='unix:///bk.sock')
        self.assertEqual(calls[0], ['nerdctl', 'build', '--buildkit-host', 'unix:///bk.sock', '-t', 'store.test/app:1',
                                    '--build-arg', 'A=1', '--build-arg', 'B=2', '/src'])

    def test_source_tag_is_stable_and_changes_with_inputs(self):
        with tempfile.NamedTemporaryFile() as first, tempfile.NamedTemporaryFile() as second:
            second.write(b'x'); second.flush()
            base = image_registry.source_tag(ROOT, ['deploy/shared/scripts'], [first.name])
            self.assertEqual(base, image_registry.source_tag(ROOT, ['deploy/shared/scripts'], [first.name]))
            self.assertRegex(base, r'^[0-9a-f]{12}$')
            self.assertNotEqual(base, image_registry.source_tag(ROOT, ['deploy/shared/scripts'], [second.name]))
            self.assertNotEqual(base, image_registry.source_tag(ROOT, ['deploy/shared/scripts'], [first.name], exclude=('runtime.py',)))
        with self.assertRaisesRegex(ValueError, 'Git에 없습니다'):
            image_registry.source_tag(ROOT, ['no/such/tree'])

    def test_build_tools_script_reports_missing_tools_without_changes(self):
        import subprocess
        script = SCRIPTS / 'build-tools.sh'
        self.assertEqual(subprocess.run(['bash', '-n', script]).returncode, 0)
        with tempfile.TemporaryDirectory() as empty:
            result = subprocess.run(['/bin/bash', script, 'check'], capture_output=True, text=True,
                                    env={'PATH': empty + ':/usr/bin:/bin', 'HOME': empty})
        if '[없음] nerdctl' in result.stdout:
            self.assertEqual(result.returncode, 1)
            self.assertIn('make build-tools-install', result.stdout)
        self.assertEqual(subprocess.run(['bash', script, 'unknown'], capture_output=True).returncode, 2)

    def test_build_tools_check_reads_buildkit_worker_labels_with_any_spacing(self):
        # buildctl은 이름과 값 사이를 탭으로 맞춰 출력한다. 공백 한 칸만 기대하면 정상 worker도 실패로 판정해
        # 준비 검사가 이미지를 빌드하는 앱의 배포를 막는다.
        import subprocess
        script = SCRIPTS / 'build-tools.sh'

        def check(separator, executor='containerd', namespace='default'):
            with tempfile.TemporaryDirectory() as directory:
                tools = Path(directory)
                labels = (f'ID:{separator}abc\\nLabels:\\n'
                          f'\\torg.mobyproject.buildkit.worker.containerd.namespace:{separator}{namespace}\\n'
                          f'\\torg.mobyproject.buildkit.worker.executor:{separator}{executor}\\n'
                          f'\\torg.mobyproject.buildkit.worker.snapshotter:{separator}overlayfs\\n')
                sources = {'sudo': '[ "$1" = -n ] && shift\nexec "$@"\n',
                           'nerdctl': 'echo "nerdctl version 2"\n', 'buildkitd': 'echo "buildkitd v0"\n',
                           'buildctl': f'case "$*" in *workers*) printf "{labels}";; *) echo "buildctl v0";; esac\n'}
                for name, body in sources.items():
                    (tools / name).write_text('#!/bin/sh\n' + body)
                    (tools / name).chmod(0o700)
                return subprocess.run(['/bin/bash', script, 'check'], capture_output=True, text=True,
                                      env={'PATH': f'{directory}:/usr/bin:/bin', 'HOME': directory})

        for separator in ('\\t', '\\t\\t', ' ', '   '):
            with self.subTest(separator=separator):
                result = check(separator)
                self.assertEqual(result.returncode, 0, result.stdout)
                self.assertIn('빌드 도구 준비 완료', result.stdout)
        # containerd worker가 아니거나 namespace가 다르면 여전히 실패한다. 이름이 앞부분만 같은 값도 통과시키지 않는다.
        for kwargs in ({'executor': 'oci'}, {'namespace': 'k8s.io'}, {'namespace': 'default2'}, {'executor': 'containerd-other'}):
            with self.subTest(**kwargs):
                result = check('\\t', **kwargs)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn('BuildKit worker가 containerd(default)가 아닙니다', result.stdout)


class PortalImageTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('portal_image', ROOT / 'deploy/portal/scripts/image.py')
        self.image = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.image)

    def test_builds_and_pushes_only_images_missing_from_registry(self):
        images = {('api', 'api'): 'store.test/tailwind/api:t1', ('web', 'web'): 'store.test/tailwind/web:t2'}
        calls, built = [], []
        registry = self.image.image_registry
        with patch.object(self.image.up, 'rendered_images', return_value=images), \
                patch.object(registry, 'remote_exists', side_effect=lambda ref, cadata=None: ref.endswith(':t1')), \
                patch.object(registry, 'nerdctl', return_value=['nerdctl']), \
                patch.object(registry, 'build', side_effect=lambda run, command, ref, source, **kw: built.append((ref, source, kw['build_args']))), \
                patch.object(registry, 'push', side_effect=lambda run, command, ref, account: calls.append(ref)):
            self.image.publish('ctx', Path('/push.env'))
        self.assertEqual(calls, ['store.test/tailwind/web:t2'])
        reference, source, args = built[0]
        self.assertEqual(source, ROOT / 'apps/portal/web')
        # Web Dockerfile이 선언한 ARG만 전달한다.
        self.assertIn('NPM_REGISTRY', args)
        self.assertNotIn('PYTHON_BASE_IMAGE', args)

    def test_build_env_covers_every_mirror_argument_of_both_dockerfiles(self):
        values = self.image.read_build_env(ROOT / 'deploy/portal/env/prod/build.env')
        declared = set()
        for source in self.image.up.SOURCES.values():
            declared |= self.image.image_registry.declared_args(ROOT / source / 'Dockerfile')
        self.assertEqual(set(values) - declared, set(), 'Dockerfile에 없는 build.env 키')
        self.assertEqual(declared - set(values), set(), 'build.env에 없는 Dockerfile ARG')


if __name__ == '__main__':
    unittest.main()
