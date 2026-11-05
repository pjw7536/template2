"""전체 서버 대시보드의 자동 공급과 실제 PromQL 계산을 검증한다."""

import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
import textwrap
import unittest

BASE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('monitoring_dashboard_manage', BASE / 'scripts/manage.py')
manage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(manage)
BOARD = json.loads((BASE / 'dashboards/servers-overview.json').read_text())
PROMTOOL = os.environ.get('PROMTOOL_COMMAND') or shutil.which('promtool')


class DashboardTests(unittest.TestCase):
    """차트 공급 결과와 사용자에게 보이는 데이터 의미를 검증한다."""

    @unittest.skipUnless(shutil.which('helm'), 'Helm 설치 후 실행 가능')
    def test_chart_provisions_dashboard_and_home_without_extra_downloads(self):
        """기존 대시보드와 하위 경로를 유지하며 JSON을 손상 없이 공급한다."""
        data = manage.read_env(BASE / 'env/k8s.env')
        with tempfile.TemporaryDirectory() as directory:
            manage.render(data, directory, manage.chart_path())
            rendered = (Path(directory) / 'monitoring.yaml').read_text()
        document = next(doc for doc in re.split(r'^---', rendered, flags=re.M)
                        if 'monitoring-grafana-servers-overview' in doc and 'kind: ConfigMap' in doc)
        match = re.search(r'^  servers-overview.json: \|[-+]?\n((?:    .*\n)+)', document, re.M)
        self.assertIsNotNone(match)
        self.assertEqual(json.loads(textwrap.dedent(match[1])), BOARD)
        self.assertIn('grafana_dashboard: "1"', document)
        self.assertIn('default_home_dashboard_path = /etc/grafana/servers-overview/servers-overview.json', rendered)
        self.assertIn('root_url = https://etch.samsungds.net/grafana/', rendered)
        self.assertIn('name: monitoring-k8s-resources-cluster', rendered)
        self.assertNotIn('download-dashboards', rendered)

    @unittest.skipUnless(PROMTOOL, 'promtool 또는 PROMTOOL_COMMAND 지정 후 실행 가능')
    def test_promql_resource_totals_filters_and_collection_failure(self):
        """중복 수집·가상 장치·마운트·서버 누락과 수집 중단을 계산한다."""
        fixture = json.loads((BASE / 'tests/fixtures/server-metrics.json').read_text())
        panels = {panel['id']: panel for panel in BOARD['panels']}
        expressions = []
        for case in fixture['checks']:
            target = next(t for t in panels[case['panel']]['targets'] if t['refId'] == case['ref'])
            expression = target['expr'].replace('${node:regex}', case['node'])
            expression = expression.replace('${interface:regex}', '.*').replace('$__rate_interval', '5m')
            expressions.append({
                'expr': expression, 'eval_time': case['eval_time'],
                'exp_samples': [{'labels': '{node="' + node + '"}' if node else '{}', 'value': value}
                                for node, value in case['expected'].items()],
            })
        tests = {'rule_files': [], 'evaluation_interval': '1m', 'fuzzy_compare': True,
                 'tests': [{'name': '전체 서버 추세·누락·필터', 'interval': '1m',
                            'input_series': fixture['input_series'], 'promql_expr_test': expressions}]}
        result = subprocess.run([*shlex.split(PROMTOOL), 'test', 'rules', '/dev/stdin'],
                                input=json.dumps(tests), text=True, capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
