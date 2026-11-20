"""앱 사이에서 서로 맞아야 하는 저장소 기본 env 값이 어긋나지 않았는지 검사한다. 값은 출력하지 않는다."""

import importlib.util
from pathlib import Path
import re
import unittest
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[3]


def read_env(relative):
    """`키=값` 줄만 읽는다. 값을 셸로 해석하지 않는다."""
    values = {}
    for line in (ROOT / relative).read_text().splitlines():
        found = re.match(r'^([A-Za-z_][\w-]*)=(.*)$', line)
        if found:
            values[found[1]] = found[2]
    return values


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PortalAirflowContractTests(unittest.TestCase):
    def setUp(self):
        self.portal = read_env('deploy/portal/env/prod/api.env')
        self.airflow = read_env('deploy/airflow/env/k8s.env')

    def test_portal_calls_airflow_with_the_airflow_admin_account(self):
        # Portal은 Airflow 관리자 계정으로 토큰을 받는다. 한쪽만 바꾸면 Portal의 Airflow 호출이 401이 된다.
        self.assertEqual(self.portal['AIRFLOW_USERNAME'], self.airflow['AIRFLOW_ADMIN_USERNAME'])
        self.assertTrue(self.portal['AIRFLOW_PASSWORD'] == self.airflow['AIRFLOW_ADMIN_PASSWORD'],
                        'Portal의 AIRFLOW_PASSWORD와 Airflow의 AIRFLOW_ADMIN_PASSWORD가 다릅니다.')

    def test_airflow_and_portal_share_the_trigger_token(self):
        self.assertTrue(self.portal['AIRFLOW_TRIGGER_TOKEN'] == self.airflow['AIRFLOW_TRIGGER_TOKEN'],
                        'Portal과 Airflow의 AIRFLOW_TRIGGER_TOKEN이 다릅니다.')

    def test_portal_accepts_the_host_airflow_calls(self):
        # Airflow는 클러스터 내부 주소로 Portal API를 호출한다. Django가 그 Host를 허용하지 않으면 400이 된다.
        host = urlsplit(self.airflow['AIRFLOW_API_BASE_URL']).hostname
        self.assertIn(host, self.portal['DJANGO_ALLOWED_HOSTS'].split(','))


class InitialAccountTests(unittest.TestCase):
    def test_initial_account_files_pass_each_tool_validation(self):
        ftp = load('ftp_up', 'deploy/ftp/scripts/up.py')
        account = ftp.read_credentials(ROOT / 'deploy/ftp/env/initial-account.env')
        self.assertEqual(set(account), {'FTP_USER', 'FTP_PASS'})
        monitoring = load('monitoring_manage', 'deploy/monitoring/scripts/manage.py')
        grafana = monitoring.read_account(ROOT / 'deploy/monitoring/env/grafana-initial.env')
        self.assertEqual(set(grafana), {'admin-user', 'admin-password'})
        airflow = load('airflow_manage', 'deploy/airflow/scripts/manage.py')
        airflow.validate(airflow.read_env(airflow.DEFAULT_ENV))


if __name__ == '__main__':
    unittest.main()
