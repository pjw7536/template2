"""관리 호스트의 Make 공개 진입점과 Portal Job 스크립트의 판정·입력 전달·중단 동작을 검증한다."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[3]


class OpsCommandsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.bin = Path(self.temp.name)
        self.calls = self.bin / 'calls'
        self.env = {**os.environ, 'PATH': f'{self.bin}:{os.environ["PATH"]}', 'OPS_CALLS': str(self.calls)}

    def executable(self, name, source):
        path = self.bin / name
        path.write_text('#!/usr/bin/env python3\nimport sys, os, json\n' + textwrap.dedent(source))
        path.chmod(0o700)

    def kubectl(self, source):
        self.executable('kubectl', textwrap.dedent('''
            args = sys.argv[1:]
            with open(os.environ["OPS_CALLS"], "a") as log:
                print(json.dumps(args), file=log)
            if args[0] != "kustomize":
                assert args[:2] == ["--context", "ops-fixture"], args
        ''') + textwrap.dedent(source))

    def make(self, target, *args):
        return subprocess.run(['make', '--no-print-directory', '-C', str(ROOT), target, 'KUBE_CONTEXT=ops-fixture', *args],
                              cwd=ROOT, env=self.env, capture_output=True, text=True, timeout=20)

    def portal_job(self, phase, **extra):
        """`portal-up`이 호출하는 방식 그대로 Job 스크립트를 실행한다."""
        return subprocess.run(['bash', 'deploy/portal/scripts/migration-job.sh', phase], cwd=ROOT,
                              env={**self.env, 'KUBE_CONTEXT': 'ops-fixture', **extra}, capture_output=True, text=True, timeout=20)

    def test_make_preserves_json_for_both_nonzero_drift_results(self):
        self.executable('git', '''
            if "rev-parse" in sys.argv:
                print("main" if "--abbrev-ref" in sys.argv else "abc")
        ''')
        self.kubectl('''
            items = []
            if "pods" in args and os.getenv("SICK"):
                items = [{"metadata": {"name": "worker"}, "status": {"containerStatuses": [
                    {"name": "worker", "state": {"waiting": {"reason": "ErrImagePull"}}}]}}]
            assert "get" in args
            print(json.dumps({"items": items}))
        ''')
        for sick, code in [('', 2), ('1', 1)]:
            self.env['SICK'] = sick
            result = self.make('drift-check', 'APP=ftp', 'DRIFT_JSON=1', 'DRIFT_SKIP_MANIFEST=1')
            self.assertNotEqual(result.returncode, 0)
            report = json.loads(result.stdout)
            self.assertEqual(report['resultCode'], code)
            self.assertEqual(report['apps'][0]['app'], 'ftp')
            self.assertIn('record', [item['area'] for item in report['apps'][0]['findings']])

    def preflight_kubectl(self):
        """노드 조회와 정적 렌더만 성공하고 나머지 조회는 빈 결과를 주는 클러스터."""
        self.kubectl('''
            if args[0] == "kustomize":
                print("kind: List")
            elif "--dry-run=client" in args:
                print(json.dumps({"kind": "List", "items": []}))
        ''')

    def test_missing_chart_is_offered_as_an_automatic_step_and_inputs_stay_private(self):
        self.preflight_kubectl()
        env = self.bin / 'airflow-external.env'
        env.write_text('INVALID=fixture-private-value\n')
        result = self.make('ops-preflight', 'APP=airflow', f'AIRFLOW_ENV={env}', f'AIRFLOW_CHART_FILE={self.bin}/missing.tgz')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('[통과] 클러스터 접속', result.stdout)
        self.assertIn('[자동 준비] chart', result.stdout)
        self.assertIn('make airflow-fetch-chart', result.stdout)
        self.assertIn(f'[통과] 입력 AIRFLOW_ENV — {env}', result.stdout)
        self.assertIn('준비 검사 결과: 남은 항목', result.stdout)
        self.assertNotIn('fixture-private-value', result.stdout + result.stderr)
        # 준비 검사는 조회만 한다.
        calls = [json.loads(line) for line in self.calls.read_text().splitlines()]
        self.assertFalse(any(verb in call for call in calls for verb in ('apply', 'patch', 'delete', 'replace')))
        self.assertFalse(any('create' in call and not any(part.startswith('--dry-run') for part in call) for call in calls))

    def test_each_catalog_app_reports_a_missing_selected_input_by_variable_name(self):
        self.preflight_kubectl()
        missing = self.bin / 'missing.env'
        catalog = json.loads((ROOT / 'deploy/shared/apps.json').read_text())
        for name, app in catalog['apps'].items():
            if not app['inputs']:
                continue
            with self.subTest(app=name):
                key = app['inputs'][0]['variable']
                result = self.make('ops-preflight', f'APP={name}', f'{key}={missing}')
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(f'[배포 차단] 입력 {key} — 파일이 없습니다: {missing}', result.stdout)
                self.assertIn('access.md#운영-입력-파일', result.stdout)
                self.assertNotIn('Traceback', result.stderr)

    def test_app_that_needs_another_app_first_is_blocked_with_the_command_to_run(self):
        self.preflight_kubectl()
        result = self.make('ops-preflight', 'APP=minio')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('[배포 차단] 먼저 필요한 앱 ingress', result.stdout)
        self.assertIn('make ops-deploy APP=ingress', result.stdout)
        # 공용 TLS 저장소는 공용 Traefik과 함께 생기므로 host 확인은 그 뒤로 미룬다.
        self.assertNotIn('공용 TLS', result.stdout)

    def test_missing_app_or_context_is_rejected_before_any_lookup(self):
        self.preflight_kubectl()
        for arguments in (('APP=',), ('APP=unknown',)):
            result = self.make('ops-preflight', *arguments)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('[배포 차단] 준비 검사', result.stdout)
        self.assertFalse(self.calls.exists())
        for target in ('deploy-record', 'ops-deploy', 'ops-diagnose', 'server-check'):
            result = self.make(target)
            self.assertNotEqual(result.returncode, 0, target)
        self.assertFalse(self.calls.exists())

    def test_failed_migration_stops_and_preserves_existing_job(self):
        self.kubectl('''
            if args[0] == "kustomize":
                print(args[-1])
            elif "--dry-run=client" in args:
                assert sys.stdin.read().strip().endswith("/migrate")
                print(json.dumps({"kind": "Job", "metadata": {"name": "portal-migrate"}, "spec": {"template": {"spec": {
                    "containers": [{"name": "migrate", "image": "store.test/tailwind/api:auto"}]}}}}))
            elif "create" in args:
                job = json.load(sys.stdin)
                # overlay의 tag auto는 소스 내용으로 정한 tag로 바뀌어 생성된다.
                image = job["spec"]["template"]["spec"]["containers"][0]["image"]
                assert image.startswith("store.test/tailwind/api:") and not image.endswith(":auto"), image
                sys.exit(int(os.getenv("COLLISION", "0")))
            else:
                assert "get" in args and "portal-migrate" in args
                print("/1")
        ''')
        created = lambda: [line for line in self.calls.read_text().splitlines() if '"create", "-f"' in line]
        result = self.portal_job('migrate')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Job 실패: portal-migrate', result.stderr)
        self.assertEqual(len(created()), 1)
        self.env['COLLISION'] = '1'
        result = self.portal_job('migrate')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('Job 실패', result.stderr)
        self.assertEqual(len(created()), 2)

    def test_checks_create_one_named_job_with_selected_phase(self):
        self.kubectl('''
            if args[0] == "kustomize":
                print(args[-1])
            elif "--dry-run=client" in args:
                print(json.dumps({"kind": "Job", "metadata": {}, "spec": {"template": {"spec": {
                    "containers": [{"name": "migrate", "image": "test:1"}]}}}}))
            elif "create" in args:
                job = json.load(sys.stdin)
                assert job["metadata"]["name"] == "access-fixture"
                assert job["spec"]["backoffLimit"] == 0
                container = job["spec"]["template"]["spec"]["containers"][0]
                assert container["args"] == ["manage.py", "check_access_permission_integrity", "--phase", os.environ["PHASE"]]
            else:
                assert "get" in args and "access-fixture" in args
                print("1/")
        ''')
        for phase in ['pre', 'post']:
            self.env['PHASE'] = phase + '-migration'
            result = self.portal_job(f'{phase}-migration', PORTAL_CHECK_JOB='access-fixture')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('Job 완료: access-fixture', result.stdout)


if __name__ == '__main__':
    unittest.main()
