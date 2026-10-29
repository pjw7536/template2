#!/usr/bin/env python3
"""Portal 없이 플랫폼 6개 앱의 실제 로그인·권한·저장·task·지표를 검사합니다."""

import base64
import ftplib
from http.cookiejar import CookieJar
import io
import json
import socket
import ssl
import time
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, HTTPSHandler, Request, build_opener, urlopen
import uuid

from k8s_config import credentials, settings
from k8s_platform import headlamp
from k8s_smoke import Client, LoginForm, LocalCookiePolicy, minio, monitoring


def request(url, payload=None, headers=None, method=None):
    """인증값·응답 본문은 출력하지 않고 HTTP·JSON 계약을 확인합니다."""
    body = None if payload is None else json.dumps(payload).encode()
    with urlopen(Request(url, data=body, method=method,
                         headers={'Content-Type': 'application/json', **(headers or {})}), timeout=30) as response:
        return json.load(response)


def ftp(creds, marker):
    """고유 파일을 passive FTP로 왕복한 후 해당 파일만 삭제합니다."""
    content = ('로컬 FTP 검사: ' + marker).encode()
    with ftplib.FTP() as client:
        client.connect('127.0.0.1', int(settings()['LOCAL_FTP_PORT']), timeout=20)
        client.login('ftpuser', creds['FTP_PASS'])
        client.cwd('data_movement')
        try:
            client.storbinary('STOR ' + marker, io.BytesIO(content))
            received = io.BytesIO()
            client.retrbinary('RETR ' + marker, received.write)
            assert received.getvalue() == content, 'FTP 왕복 내용 불일치'
        finally:
            client.delete(marker)
    print('PASS FTP passive 업로드·다운로드·검사 파일 정리', flush=True)


def airflow(creds, marker):
    """SSO와 Basic API를 확인하고 독립 DAG를 실행한 뒤 원래 pause 상태를 복원합니다."""
    base = 'http://localhost:8080/airflow'
    opener = build_opener(HTTPCookieProcessor(CookieJar(policy=LocalCookiePolicy())))
    with opener.open(base + '/login/keycloak', timeout=30) as response:
        form = LoginForm()
        form.feed(response.read().decode())
    assert form.action, 'Airflow Keycloak 로그인 화면 누락'
    fields = {**form.fields, 'username': '90000001', 'password': 'dummy-user-change-me', 'credentialId': ''}
    with opener.open(Request(form.action, data=urlencode(fields).encode()), timeout=30) as response:
        assert '/airflow/home' in response.url, 'Airflow 로그인 callback 실패'
    auth = base64.b64encode(('airflow:' + creds['AIRFLOW_ADMIN_PASSWORD']).encode()).decode()
    headers = {'Authorization': 'Basic ' + auth}
    errors = request(base + '/api/v1/importErrors', headers=headers)
    assert errors['total_entries'] == 0, 'Airflow DAG import 오류'
    dag = base + '/api/v1/dags/local_platform_smoke'
    for attempt in range(60):
        try:
            original = request(dag, headers=headers)
            break
        except HTTPError as error:
            if error.code != 404 or attempt == 59:
                raise
            time.sleep(2)
    try:
        request(dag, {'is_paused': False}, headers, 'PATCH')
        request(dag + '/dagRuns', {'dag_run_id': marker}, headers)
        for _ in range(90):
            state = request(dag + '/dagRuns/' + marker, headers=headers)['state']
            if state == 'success':
                break
            assert state != 'failed', '로컬 독립 DAG 실행 실패'
            time.sleep(2)
        else:
            raise AssertionError('로컬 독립 DAG 대기 초과')
    finally:
        request(dag, {'is_paused': original['is_paused']}, headers, 'PATCH')
    print('PASS Keycloak → Airflow SSO·Basic API·LocalExecutor DAG 실행·DB 연결', flush=True)


def headlamp_login(username, password):
    """Headlamp의 실제 code+PKCE callback과 쿠키로 Kubernetes 권한을 확인합니다."""
    jar = CookieJar()
    context = ssl.create_default_context(cafile=str(headlamp.CA))
    opener = build_opener(HTTPCookieProcessor(jar), HTTPSHandler(context=context))
    with opener.open(headlamp.URL + 'oidc?cluster=main', timeout=30) as response:
        form = LoginForm()
        form.feed(response.read().decode())
    assert form.action, 'Headlamp Keycloak 로그인 form 누락'
    fields = {**form.fields, 'username': username, 'password': password, 'credentialId': ''}
    with opener.open(Request(form.action, data=urlencode(fields).encode()), timeout=30) as response:
        response.read()
        assert '/headlamp/auth?cluster=main' in response.url, 'Headlamp OIDC callback 실패'
    # 실제 사용자 쿠키를 Headlamp 프록시로 전달해 API server OIDC와 RBAC까지 검사합니다.
    target = headlamp.URL + 'clusters/main/api/v1/namespaces'
    if username == 'platform-admin':
        with opener.open(target, timeout=30) as response:
            assert json.load(response)['items'], 'Headlamp 관리자 namespace 조회 실패'
    else:
        try:
            opener.open(target, timeout=30)
        except HTTPError as error:
            assert error.code == 403, '미승격 사용자의 요청은 인증 성공 후 RBAC로 거부되어야 합니다.'
        else:
            raise AssertionError('미승격 사용자에게 namespace 조회 권한이 부여되었습니다.')


def headlamp_sso(creds):
    """호스트 DNS를 바꾸지 않고 Python 검사에서만 .localhost를 loopback으로 해석합니다."""
    original = socket.getaddrinfo
    def local_lookup(host, *args, **kwargs):
        return original('127.0.0.1' if host == 'sso.localhost' else host, *args, **kwargs)
    with patch('socket.getaddrinfo', side_effect=local_lookup):
        headlamp_login('platform-admin', creds['HEADLAMP_ADMIN_PASSWORD'])
        headlamp_login('platform-viewer', creds['HEADLAMP_VIEWER_PASSWORD'])
    print('PASS Headlamp HTTPS·Keycloak PKCE 로그인·API server OIDC·관리자/미승격 RBAC', flush=True)


def main():
    """각 앱의 실동작을 검증하며 Portal 로그인·env·API는 호출하지 않습니다."""
    creds = credentials()
    marker = 'platform-smoke-' + uuid.uuid4().hex[:12]
    headlamp_sso(creds)
    minio(marker)
    ftp(creds, marker)
    airflow(creds, marker)
    monitoring(Client())
    print('PASS Portal을 제외한 platform 6개 앱 실제 통합 검사 완료', flush=True)


if __name__ == '__main__':
    try:
        main()
    except HTTPError as error:
        raise SystemExit(f'platform smoke HTTP 실패: {error.code}') from None
