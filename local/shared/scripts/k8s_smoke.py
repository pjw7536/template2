#!/usr/bin/env python3
"""실행 중인 로컬 앱의 인증·외부계·파일·배치·모니터링 통합 경로를 검사합니다.

테스트 전용 대화·메일·파일·DAG 실행을 만들며 기존 데이터나 활성 DAG 상태는 초기화하지 않습니다.
"""

import base64
from contextlib import contextmanager
import ftplib
from html.parser import HTMLParser
from http.cookiejar import CookieJar, DefaultCookiePolicy
import io
import json
import socket
import subprocess
import time
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen
import uuid
import zlib

from k8s import DB, KUBE, apply, run, wait_job
from k8s_config import ROOT, credentials, settings

PORTAL = 'http://localhost:8080'


class LocalCookiePolicy(DefaultCookiePolicy):
    """브라우저의 localhost Secure cookie 예외만 재현합니다.

    근거: https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie
    """

    def return_ok_secure(self, cookie, request):
        if urlsplit(request.full_url).hostname == 'localhost':
            return True
        return super().return_ok_secure(cookie, request)


class LoginForm(HTMLParser):
    """Keycloak 로그인 form의 action과 hidden 입력을 읽습니다."""

    def __init__(self):
        super().__init__()
        self.action = None
        self.fields = {}

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == 'form' and values.get('id') == 'kc-form-login':
            self.action = values['action']
        if tag == 'input' and values.get('type') == 'hidden' and values.get('name'):
            self.fields[values['name']] = values.get('value', '')


class Client:
    """브라우저와 같은 세션 쿠키·CSRF 경로로 Portal API를 호출합니다."""

    def __init__(self):
        self.cookies = CookieJar(policy=LocalCookiePolicy())
        self.opener = build_opener(HTTPCookieProcessor(self.cookies))

    def request(self, url, payload=None, headers=None, raw=False):
        headers = dict(headers or {})
        body = None
        if payload is not None:
            body = json.dumps(payload).encode()
            headers.update({'Content-Type': 'application/json', 'Referer': PORTAL + '/'})
            for cookie in self.cookies:
                if cookie.name == 'csrftoken':
                    headers['X-CSRFToken'] = cookie.value
        with self.opener.open(Request(url, data=body, headers=headers), timeout=120) as response:
            text = response.read().decode()
            return text if raw else json.loads(text)

    def login(self):
        form = LoginForm()
        form.feed(self.request(PORTAL + '/api/v1/auth/login', raw=True))
        if not form.action:
            raise AssertionError('Keycloak 로그인 form을 찾지 못했습니다.')
        fields = {**form.fields, 'username': 'dummy.user', 'password': 'dummy-user-change-me', 'credentialId': ''}
        with self.opener.open(Request(form.action, data=urlencode(fields).encode()), timeout=60) as response:
            response.read()
        user = self.request(PORTAL + '/api/v1/auth/me')
        assert user.get('id'), '인증된 Portal 사용자 없음'
        print('PASS Keycloak 로그인·Portal 사용자 확인', flush=True)


@contextmanager
def forward(namespace, service, remote):
    """임시 port-forward를 종료 시 반드시 정리합니다."""
    with socket.socket() as connection:
        connection.bind(('127.0.0.1', 0))
        port = connection.getsockname()[1]
    process = subprocess.Popen([*KUBE, '-n', namespace, 'port-forward', 'svc/' + service, f'{port}:{remote}'],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            if process.poll() is not None:
                raise RuntimeError(f'port-forward 실패: {namespace}/{service}')
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=1):
                    break
            except OSError:
                time.sleep(0.5)
        else:
            raise RuntimeError(f'port-forward 대기 초과: {service}')
        yield f'http://127.0.0.1:{port}'
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def chat_and_mail(client, marker):
    """Portal 세션으로 대화·메일 조회, Pod mock으로 실제 RAG·메일 연결을 검증합니다."""
    indexes = client.request(PORTAL + '/api/v1/assistant/rag-indexes')
    assert indexes, 'RAG 인덱스 응답이 비었습니다.'
    conversation = client.request(PORTAL + '/api/v1/assistant/conversations', {'name': marker})
    conversation = conversation.get('conversation', conversation)
    payload = {'action': 'send', 'conversationId': conversation['id'], 'clientRequestId': marker,
               'profileKey': 'portal-default', 'appContextKey': 'assistant:openwebui:portal',
               'message': {'clientId': marker, 'content': '로컬 통합 검증입니다.'}, 'toolInputs': {}}
    stream = client.request(PORTAL + '/api/v1/assistant/turns/stream', payload, raw=True)
    assert 'event: run.completed' in stream and 'event: run.failed' not in stream, '챗 완료 이벤트 누락'
    inbox = client.request(PORTAL + '/api/v1/emails/inbox/')
    assert inbox, '메일 목록 응답이 비었습니다.'
    with forward('tailwind-local', 'adfs', 9000) as mock:
        client.request(mock + '/rag/insert', {'index_name': 'rp-unclassified',
                       'data': {'doc_id': marker, 'title': marker, 'content': marker}})
        result = client.request(mock + '/rag/search', {'index_name': 'rp-unclassified', 'query_text': marker})
        assert marker in json.dumps(result), 'RAG 문서 검색 실패'
        sent = client.request(mock + '/mail/send', {'title': marker, 'content': marker, 'recipient': 'dummy.user@example.com'})
        assert sent['sent'] == 1, 'mock 메일 발송 실패'
    print('PASS Portal 챗 스트리밍·RAG 검색·메일 조회/발송', flush=True)


def minio(marker):
    """같은 앱 자격증명으로 MinIO에 객체를 쓰고 읽습니다."""
    name = 'local-minio-smoke'
    run([*KUBE, '-n', 'tailwind-local', 'delete', 'job', name, '--ignore-not-found'], quiet=True)
    command = ('set -eu; mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null; '
               f'printf %s {marker} > /tmp/probe; mc cp /tmp/probe local/profile/{marker} >/dev/null; '
               f'test "$(mc cat local/profile/{marker})" = {marker}; mc rm local/profile/{marker} >/dev/null')
    apply([{'apiVersion': 'batch/v1', 'kind': 'Job', 'metadata': {'name': name, 'namespace': 'tailwind-local'},
            'spec': {'backoffLimit': 0, 'template': {'spec': {'restartPolicy': 'Never', 'containers': [
                {'name': 'probe', 'image': settings()['LOCAL_MINIO_CLIENT_IMAGE'], 'imagePullPolicy': 'IfNotPresent', 'command': ['/bin/sh', '-c', command],
                 'envFrom': [{'secretRef': {'name': 'minio-env'}}]}]}}}}])
    wait_job(name)
    print('PASS MinIO 객체 저장·다운로드', flush=True)


def ftp_file(client, creds, marker):
    """FTP 업로드 파일을 API가 실제로 적재하는지 검사합니다."""
    config = settings()
    row = [''] * 50
    row[0], row[6], row[10] = marker, 'K8SSMOKE', 'process'
    for index in (8, 25, 26, 29, 30, 32, 40, 43):
        row[index] = '0'
    content = zlib.compress('\x03'.join(row).encode())
    name = '000000000_' + marker + '.csv.deflate'
    with ftplib.FTP() as ftp:
        ftp.connect('127.0.0.1', int(config['LOCAL_FTP_PORT']), timeout=20)
        ftp.login('ftpuser', creds['FTP_PASS'])
        ftp.cwd('data_movement')
        for folder in ('m_tkin_prevent', 'incoming'):
            try:
                ftp.mkd(folder)
            except ftplib.error_perm:
                pass
            ftp.cwd(folder)
        ftp.storbinary('STOR ' + name, io.BytesIO(content))
        downloaded = io.BytesIO()
        ftp.retrbinary('RETR ' + name, downloaded.write)
        assert downloaded.getvalue() == content, 'FTP 다운로드 내용 불일치'
    # 파일 안정화 시간을 실제 업로드 후 기다려 기존 loader 계약을 유지합니다.
    time.sleep(62)
    url = PORTAL + '/api/v1/data-movement/m_tkin_prevent/load/'
    headers = {'Authorization': 'Bearer ' + creds['AIRFLOW_TRIGGER_TOKEN']}
    preview = client.request(url, {'limit': 1, 'dryRun': True}, headers)
    assert any(item['fileName'] == name for item in preview['outcomes']), '검증 파일이 우선 선택되지 않았습니다.'
    result = client.request(url, {'limit': 1}, headers)
    assert result['successCount'] == 1 and result['outcomes'][0]['fileName'] == name, 'FTP 파일 적재 실패'
    count = run([*DB, 'exec', '-T', 'postgres', 'psql', '-U', 'postgres', '-d', 'dashboard', '-Atc',
                 f"SELECT count(*) FROM m_tkin_prevent WHERE operator_name = '{marker}'"], quiet=True)
    assert count.strip() == '1', '적재한 PostgreSQL 행 없음'
    print('PASS FTP passive 업로드·다운로드 → API 파일 처리 → PostgreSQL 적재', flush=True)


def airflow(client, creds, marker):
    """기존 활성 상태를 복원하면서 Portal API를 호출하는 DAG를 실제 실행합니다."""
    # 기존 public facade로 실제 Outbox 작업을 넣고 Django 명령은 Compose api에서만 실행합니다.
    code = ('from api.emails.services import enqueue_email_outbox; '
            'enqueue_email_outbox(email=None, action="DELETE", payload=' +
            repr({'rag_doc_id': marker, 'index_name': 'rp-unclassified', 'permission_groups': ['rag-public']}) + ')')
    run(['docker', 'compose', '--project-name', 'tailwind-k8s-check', '--env-file', ROOT / 'local/shared/runtime/db.env',
         '-f', ROOT / 'local/shared/compose/k8s-check.yml', 'run', '--rm', '-T', 'api', 'shell', '-c', code], quiet=True)
    auth = base64.b64encode(('airflow:' + creds['AIRFLOW_ADMIN_PASSWORD']).encode()).decode()
    headers = {'Authorization': 'Basic ' + auth}
    imports = client.request(PORTAL + '/airflow/api/v1/importErrors', headers=headers)
    assert imports['total_entries'] == 0, 'Airflow DAG import 오류가 있습니다.'
    base = PORTAL + '/airflow/api/v1/dags/email_outbox_process'
    original = client.request(base, headers=headers)
    # Airflow의 JSON 수정 요청은 Basic 인증을 사용합니다.
    def pause(value):
        request = Request(base, data=json.dumps({'is_paused': value}).encode(), method='PATCH',
                          headers={**headers, 'Content-Type': 'application/json'})
        with urlopen(request, timeout=30) as response:
            response.read()
    try:
        pause(False)
        client.request(base + '/dagRuns', {'dag_run_id': marker, 'conf': {}}, headers)
        for _ in range(120):
            state = client.request(base + '/dagRuns/' + marker, headers=headers)['state']
            if state == 'success':
                break
            assert state != 'failed', 'Airflow 대표 DAG 실패'
            time.sleep(3)
        else:
            raise AssertionError('Airflow 대표 DAG 대기 초과')
    finally:
        pause(original['is_paused'])
    overview = client.request(PORTAL + '/api/v1/line-dashboard/airflow/dag-overview')
    assert overview, 'Portal Airflow 조회 응답 없음'
    with forward('tailwind-local', 'adfs', 9000) as mock:
        docs = client.request(mock + '/rag/docs')['docs']
        assert all(item.get('doc_id') != marker for item in docs), 'Outbox의 RAG 삭제가 처리되지 않았습니다.'
    print('PASS Airflow DAG → Portal API → RAG Outbox 처리·Portal DAG 조회', flush=True)


def monitoring(client):
    """Grafana health와 Prometheus의 실제 수집 표본을 확인합니다."""
    with forward('monitoring', 'monitoring-grafana', 80) as grafana:
        assert client.request(grafana + '/api/health')['database'] == 'ok'
    with forward('monitoring', 'monitoring-prometheus', 9090) as prometheus:
        for _ in range(40):
            targets = client.request(prometheus + '/api/v1/targets')['data']['activeTargets']
            jobs = {item['labels'].get('job') for item in targets if item['health'] == 'up'}
            if any('kube-state-metrics' in (job or '') for job in jobs) and 'kubelet' in jobs:
                break
            time.sleep(3)
        else:
            raise AssertionError('주요 Kubernetes 수집 대상이 UP이 아닙니다.')
    print('PASS Grafana DB·Prometheus Kubernetes 지표 수집', flush=True)


def main():
    """대표 사용자 흐름을 순서대로 실행하고 실패 시 0이 아닌 종료 코드를 반환합니다."""
    creds = credentials()
    marker = 'k8s-smoke-' + uuid.uuid4().hex[:12]
    client = Client()
    client.login()
    chat_and_mail(client, marker)
    minio(marker)
    ftp_file(client, creds, marker)
    airflow(client, creds, marker)
    monitoring(client)
    client.request(PORTAL + '/api/v1/auth/logout', {})
    try:
        client.request(PORTAL + '/api/v1/auth/me')
    except HTTPError as error:
        assert error.code == 401
    else:
        raise AssertionError('로그아웃 후 세션이 유지됩니다.')
    print('PASS 로그아웃 — 전체 대표 통합 시나리오 통과', flush=True)


if __name__ == '__main__':
    main()
