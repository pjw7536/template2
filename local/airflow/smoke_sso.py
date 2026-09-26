#!/usr/bin/env python3
"""로컬 실제 Keycloak 로그인·역할 회수·API 인증을 검증하고 테스트 역할을 복원한다."""

import base64
from http.cookiejar import CookieJar
import importlib.util
import json
from pathlib import Path
import sys
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'local/shared/scripts'))
from k8s_config import airflow_settings, credentials
from k8s_smoke import LoginForm, LocalCookiePolicy, Client
from k8s import KUBE, run

BASE = 'http://localhost:8080/airflow'


def login(username):
    """브라우저와 같은 authorization code·쿠키·callback 경로를 통과한다."""
    opener = build_opener(HTTPCookieProcessor(CookieJar(policy=LocalCookiePolicy())))
    with opener.open(BASE + '/login/keycloak', timeout=20) as response:
        form = LoginForm()
        form.feed(response.read().decode())
    assert form.action, 'Keycloak 로그인 화면이 없습니다.'
    fields = {**form.fields, 'username': username, 'password': 'dummy-user-change-me', 'credentialId': ''}
    with opener.open(Request(form.action, data=urlencode(fields).encode()), timeout=30) as response:
        assert '/airflow/home' in response.url, 'Airflow 로그인 callback 실패'
        response.read()
    with opener.open(BASE + '/api/v1/dags?limit=1', timeout=20) as response:
        assert response.status == 200
    return opener


def stored_roles():
    """인증 결과는 FAB DB에 저장된 역할을 통해 직접 확인한다."""
    code = ('import json; from airflow.www.app import cached_app; app=cached_app(); '
            'ctx=app.app_context(); ctx.push(); '
            'print(json.dumps({u.username: sorted(r.name for r in u.roles) for u in app.appbuilder.sm.get_all_users()}))')
    output = run([*KUBE, '-n', 'airflow', 'exec', 'deployment/airflow-webserver', '-c', 'webserver',
                  '--', 'python', '-c', code], quiet=True)
    return json.loads(output.strip().splitlines()[-1])


def main():
    """기본 조회와 명시적 승격·회귀를 검사하며 비밀값은 출력하지 않는다."""
    source = ROOT / 'deploy/airflow/k8s/jobs/keycloak-client/setup_client.py'
    spec = importlib.util.spec_from_file_location('airflow_client', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    creds = credentials()
    values = airflow_settings(creds)
    admin = module.KeycloakAdmin('http://localhost:8180', 'portal', 'local-keycloak-admin', 'local-keycloak-admin-change-me')
    identifier, roles = module.configure(admin, values)
    spec = importlib.util.spec_from_file_location('airflow_claims', ROOT / 'apps/airflow/image/oidc_claims.py')
    claims_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(claims_module)
    ids = {}
    for username, expected in [('90000001', {'Viewer', 'Admin'}), ('90000003', {'Viewer', 'User'}), ('90000005', {'Viewer'})]:
        opener = login(username)
        user = admin.request('GET', admin.root + '/users?username=' + username + '&exact=true')[0]
        ids[username] = user['id']
        info = claims_module.user_info({'iss': values['AIRFLOW_OIDC_ISSUER'], 'sub': user['id']},
                                      values['AIRFLOW_OIDC_ISSUER'], 'airflow')
        assert set(stored_roles()[info['username']]) == expected, 'FAB 역할 동기화 실패'
        if expected == {'Viewer'}:
            try:
                opener.open(BASE + '/api/v1/variables?limit=1', timeout=20)
            except HTTPError as error:
                assert error.code == 403
            else:
                raise AssertionError('Viewer가 관리자 자원을 조회할 수 있습니다.')
            try:
                opener.open(Request(BASE + '/api/v1/dags/oidc-permission-test-nonexistent',
                                    data=b'{"is_paused":true}', method='PATCH',
                                    headers={'Content-Type': 'application/json'}), timeout=20)
            except HTTPError as error:
                assert error.code == 403
            else:
                raise AssertionError('Viewer의 DAG 변경 요청이 거부되지 않았습니다.')
        print('PASS Keycloak 로그인·역할: ' + username + ' ' + ','.join(sorted(expected)), flush=True)
    path = admin.root + '/users/' + ids['90000003'] + '/role-mappings/clients/' + identifier
    original = admin.request('GET', path)
    try:
        admin.request('DELETE', path, original)
        login('90000003')
        info = claims_module.user_info({'iss': values['AIRFLOW_OIDC_ISSUER'], 'sub': ids['90000003']},
                                      values['AIRFLOW_OIDC_ISSUER'], 'airflow')
        assert stored_roles()[info['username']] == ['Viewer']
        print('PASS User 회수 후 새 로그인 Viewer 복귀', flush=True)
    finally:
        admin.request('POST', path, original)
        login('90000003')
    auth = base64.b64encode(('airflow:' + creds['AIRFLOW_ADMIN_PASSWORD']).encode()).decode()
    with urlopen(Request(BASE + '/api/v1/dags?limit=1', headers={'Authorization': 'Basic ' + auth}), timeout=20) as response:
        assert response.status == 200
    try:
        urlopen(BASE + '/api/v1/dags?limit=1', timeout=20)
    except HTTPError as error:
        assert error.code in (401, 403)
    else:
        raise AssertionError('익명 API 접근이 허용되었습니다.')
    portal = Client()
    portal.login()
    assert portal.request('http://localhost:8080/api/v1/line-dashboard/airflow/dag-overview')
    print('PASS 익명 접근 거부·기존 Basic API 인증·Portal 실제 Airflow 조회', flush=True)


if __name__ == '__main__':
    main()
