"""관리 호스트의 Make 공개 진입점에서 판정·입력 전달·중단 동작을 검증한다."""

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

    def test_missing_chart_passes_context_and_keeps_external_input_private(self):
        self.kubectl('assert "nodes" in args')
        env = self.bin / 'airflow external.env'
        env.write_text('INVALID=fixture-private-value\n')
        result = self.make('ops-preflight', 'APP=airflow', f'AIRFLOW_ENV={env}',
                           f'AIRFLOW_CHART_FILE={self.bin}/missing.tgz')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('[통과] KUBE_CONTEXT=ops-fixture', result.stdout)
        self.assertIn('missing.tgz', result.stdout)
        self.assertIn('chart.lock.json', result.stdout)
        self.assertIn(str(env), result.stdout.split('재검사:')[1])
        self.assertNotIn('fixture-private-value', result.stdout + result.stderr)
        self.assertEqual(len(self.calls.read_text().splitlines()), 1)

    def test_each_catalog_app_checks_the_selected_external_file(self):
        self.kubectl('''
            if args[0] == "kustomize":
                print("kind: List")
            elif "--dry-run=client" in args:
                print(json.dumps({"kind": "List", "items": []}))
            else:
                assert "get" in args and "nodes" in args
        ''')
        missing = self.bin / 'missing.env'
        catalog = json.loads((ROOT / 'deploy/shared/apps.json').read_text())
        for app in catalog['apps']:
            with self.subTest(app=app):
                key = 'PROD_API_ENV_FILE' if app == 'portal' else app.upper() + '_ENV'
                result = self.make('ops-preflight', f'APP={app}', f'{key}={missing}')
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(f'[배포 차단] {key}={missing}', result.stdout)
                self.assertIn('재검사:', result.stdout)
                self.assertNotIn('Traceback', result.stderr)

    def test_portal_rendered_images_are_checked(self):
        self.kubectl('''
            if args[0] == "kustomize":
                print(args[-1])
            elif "create" in args:
                assert "--dry-run=client" in args
                migration = sys.stdin.read().strip().endswith("/migrate")
                name, container = ("portal-migrate", "migrate") if migration else ("api", "api")
                image = os.environ["TEST_IMAGE"] if migration else "mirror.test/api:1"
                print(json.dumps({"kind": "Job" if migration else "Deployment", "metadata": {"name": name},
                    "spec": {"template": {"spec": {"containers": [{"name": container, "image": image}]}}}}))
            else:
                assert "nodes" in args
        ''')
        for image, expectation in [('example.invalid/api:replace-me', '자리표시자'),
                                   ('mirror.test/api:2', '버전을 일치'), ('mirror.test/api:1', '[통과] deploy/portal/k8s/overlays/prod')]:
            self.env['TEST_IMAGE'] = image
            result = self.make('ops-preflight', 'APP=portal', f'PROD_API_ENV_FILE={self.bin}/absent')
            self.assertIn(expectation, result.stdout)
            self.assertIn('[배포 차단] PROD_API_ENV_FILE=', result.stdout)

    def test_failed_migration_stops_and_preserves_existing_job(self):
        self.kubectl('''
            if "create" in args:
                assert "-k" in args and args[-1].endswith("/migrate")
                sys.exit(int(os.getenv("COLLISION", "0")))
            assert "get" in args and "portal-migrate" in args
            print("/1")
        ''')
        result = self.make('portal-migrate')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Job 실패: portal-migrate', result.stderr)
        self.assertEqual(len(self.calls.read_text().splitlines()), 2)
        self.env['COLLISION'] = '1'
        result = self.make('portal-migrate')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(self.calls.read_text().splitlines()), 3)

    def test_checks_create_one_named_job_with_selected_phase(self):
        self.kubectl('''
            if "--dry-run=client" in args:
                print(json.dumps({"metadata": {}, "spec": {"template": {"spec": {
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
            result = self.make(f'portal-{phase}check', 'PORTAL_CHECK_JOB=access-fixture')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('Job 완료: access-fixture', result.stdout)


if __name__ == '__main__':
    unittest.main()
