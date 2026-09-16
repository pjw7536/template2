"""폴더 구조 검사에서 놓치기 쉬운 경로 회귀를 검증한다."""

import json
import tempfile
import unittest
from pathlib import Path

from apps.tooling.agent import check_app_layout as audit


class AppLayoutTests(unittest.TestCase):
    def test_root_only_allows_owned_folders_and_generated_tools(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('apps', 'data', 'deploy', 'docs', 'local', '.github'):
                (root / name).mkdir()
            self.assertFalse(audit.check_root(root))
            (root / 'node_modules').mkdir()
            self.assertEqual(len(audit.check_root(root)), 1)
            (root / 'package.json').write_text('{}')
            (root / 'docker-compose.yml').write_text('services: {}')
            self.assertEqual(len(audit.check_root(root)), 3)

    def test_current_source_and_historical_reference_are_distinguished(self):
        old = 'apps/' + 'api/manage.py'
        self.assertTrue(audit.check_text('Makefile', old))
        self.assertFalse(audit.check_text('docs/agent/plans/old.md', old))
        self.assertFalse(audit.check_text('Dockerfile', 'apps/portal/api /opt/airflow/dags'))
        self.assertTrue(audit.check_text('Dockerfile', 'COPY ' + 'airflow/' + 'dags /dags'))
        self.assertTrue(audit.check_text('compose.yml', '../../../' + 'airflow/' + 'dags'))
        self.assertFalse(audit.check_text('Makefile', 'deploy/airflow/tests'))

    def test_server_tool_cannot_depend_on_local_directory(self):
        self.assertTrue(audit.check_text('deploy/shared/scripts/run.py', "ROOT / 'local/portal'"))
        self.assertTrue(audit.check_text('deploy/shared/scripts/run.py', "ROOT / 'local' / 'portal'"))
        self.assertFalse(audit.check_text('local/portal/scripts/run.sh', "'local/portal'"))

    def test_catalog_rejects_cross_app_and_outside_source_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'apps.json'
            for source in ['../escape', 'apps/other']:
                path.write_text(json.dumps({'apps': {'portal': {
                    'sourcePaths': [source], 'deployPath': 'deploy/portal', 'localPath': 'local/portal',
                }}, 'groups': {'all': ['portal']}}))
                with self.assertRaises(ValueError):
                    audit.APP_PATHS.read_catalog(path)

    def test_catalog_requires_existing_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = {'apps': {'portal': {'sourcePaths': ['apps/portal'], 'deployPath': 'deploy/portal', 'localPath': None}}}
            self.assertEqual(len(audit.check_catalog(root, catalog)), 2)
            (root / 'apps/portal').mkdir(parents=True)
            (root / 'deploy/portal').mkdir(parents=True)
            self.assertFalse(audit.check_catalog(root, catalog))
