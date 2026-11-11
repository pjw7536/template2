#!/usr/bin/env python3
"""Airflow 단일 서버 설정 검증·렌더·배포 도구. Python 표준 라이브러리만 사용한다.

정적 검사와 렌더는 클러스터를 변경하지 않는다. deploy만 명시한 context에 적용한다.
설정은 코드로 실행하지 않으며 Secret은 Helm values와 렌더 결과에 포함하지 않는다.
"""

import argparse
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import quote, urlsplit

BASE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('shared_tls', BASE.parent / 'shared/ingress/tls.py')
tls = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tls)
spec = importlib.util.spec_from_file_location('shared_runtime', BASE.parent / 'shared/scripts/runtime.py')
RUNTIME = importlib.util.module_from_spec(spec)
spec.loader.exec_module(RUNTIME)
LOCK = json.loads((BASE / 'helm/chart.lock.json').read_text())
ENV_KEYS = frozenset(('NAMESPACE', 'POSTGRES_MODE', 'POSTGRES_HOST', 'POSTGRES_PORT', 'POSTGRES_USER', 'POSTGRES_DB', 'NODE_NAME', 'POSTGRES_HOST_PATH', 'LOGS_HOST_PATH', 'POSTGRES_STORAGE_SIZE', 'LOGS_STORAGE_SIZE', 'POSTGRES_IMAGE', 'POSTGRES_UID', 'POSTGRES_GID', 'AIRFLOW_IMAGE_REPOSITORY', 'AIRFLOW_IMAGE_TAG', 'IMAGE_PULL_SECRET', 'ODBC_HOST_PATH', 'ODBC_SECRET_NAME', 'INGRESS_ENABLED', 'INGRESS_CLASS_NAME', 'INGRESS_TLS_SECRET', 'AIRFLOW_WEBSERVER_BASE_URL', 'AIRFLOW_API_BASE_URL', 'AIRFLOW_ADMIN_USERNAME', 'AIRFLOW_ADMIN_EMAIL', 'POSTGRES_PASSWORD', 'AIRFLOW_ADMIN_PASSWORD', 'AIRFLOW_FERNET_KEY', 'AIRFLOW_WEBSERVER_SECRET_KEY', 'AIRFLOW_TRIGGER_TOKEN', 'KNOX_MESSENGER_API_BASE_URL', 'KNOX_MESSENGER_AUTHORIZATION', 'KNOX_MESSENGER_SYSTEM_ID', 'AIRFLOW_FAILURE_ALERT_KNOX_IDS'))
OIDC_KEYS = ('AIRFLOW_AUTH_MODE', 'AIRFLOW_OIDC_ISSUER', 'AIRFLOW_OIDC_CLIENT_ID',
             'AIRFLOW_OIDC_CLIENT_SECRET', 'AIRFLOW_OIDC_BACKCHANNEL_BASE_URL',
             'AIRFLOW_OIDC_CA_BUNDLE', 'AIRFLOW_OIDC_CA_CONFIGMAP', 'AIRFLOW_OIDC_ALLOW_HTTP')
MAIL_DEFAULTS = {'MAIL_API_URL': '', 'MAIL_API_KEY': '', 'MAIL_API_SYSTEM_ID': 'plane',
                 'MAIL_API_KNOX_ID': '', 'AIRFLOW_FAILURE_ALERT_EMAIL_FROM': '',
                 'AIRFLOW_FAILURE_ALERT_EMAIL_TO': ''}
ENV_KEYS = ENV_KEYS | frozenset(OIDC_KEYS) | frozenset(MAIL_DEFAULTS)
DEFAULT_ENV = BASE / 'env/k8s.env'
DEFAULT_CONTAINERD_ADDRESS = '/run/containerd/containerd.sock'
DEFAULT_BUILDKIT_HOST = 'unix:///run/buildkit/buildkitd.sock'
RUNTIME_KEYS = (
    'AIRFLOW_API_BASE_URL', 'AIRFLOW_TRIGGER_TOKEN', 'KNOX_MESSENGER_API_BASE_URL',
    'KNOX_MESSENGER_AUTHORIZATION', 'KNOX_MESSENGER_SYSTEM_ID', 'AIRFLOW_FAILURE_ALERT_KNOX_IDS',
)
RUNTIME_KEYS += tuple(key for key in OIDC_KEYS if key != 'AIRFLOW_OIDC_CA_CONFIGMAP')
RUNTIME_KEYS += tuple(MAIL_DEFAULTS)
SECRET_KEYS = ('POSTGRES_PASSWORD', 'AIRFLOW_ADMIN_PASSWORD', 'AIRFLOW_FERNET_KEY',
               'AIRFLOW_WEBSERVER_SECRET_KEY', 'AIRFLOW_TRIGGER_TOKEN')
DB_DEFAULTS = {'POSTGRES_MODE': 'internal', 'POSTGRES_HOST': 'airflow-postgres',
               'POSTGRES_PORT': '5432', 'POSTGRES_USER': 'airflow', 'POSTGRES_DB': 'airflow'}


def require(condition, message):
    """입력값을 출력하지 않고 설정 항목만 표시해 중단한다."""
    if not condition:
        raise ValueError(message)


def read_env(path):
    """KEY=값을 데이터로 읽는다. 중복과 알 수 없는 키는 오타로 처리한다."""
    values = {}
    for number, line in enumerate(Path(path).read_text().splitlines(), 1):
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        key, separator, value = line.partition('=')
        require(separator and re.fullmatch(r'[A-Z][A-Z0-9_]*', key), f'설정 형식 오류: 줄 {number}')
        require(key not in values, f'중복 설정: {key}')
        values[key] = value
    return values


def validate(values, example=False):
    """서버 경로·버전·URL·비밀값을 검증하고 배포 시 예시값을 거부한다."""
    # 공용 Traefik은 앱별 TLS Secret을 쓰지 않으므로 다른 controller를 쓸 때만 입력한다.
    values.setdefault('INGRESS_TLS_SECRET', '')
    for key, default in {**DB_DEFAULTS, **MAIL_DEFAULTS}.items():
        values.setdefault(key, default)
    require(values['POSTGRES_MODE'] in ('internal', 'external'), 'POSTGRES_MODE는 internal 또는 external이어야 합니다.')
    require(re.fullmatch(r'[a-zA-Z0-9.-]+', values['POSTGRES_HOST']), 'POSTGRES_HOST 형식 오류')
    require(values['POSTGRES_PORT'].isdigit() and 0 < int(values['POSTGRES_PORT']) < 65536, 'POSTGRES_PORT 형식 오류')
    for key in ('POSTGRES_USER', 'POSTGRES_DB'):
        require(re.fullmatch(r'[a-zA-Z_][a-zA-Z0-9_]*', values[key]), f'{key} 형식 오류')
    if values['POSTGRES_MODE'] == 'internal':
        require(all(values[key] == default for key, default in DB_DEFAULTS.items()), '내부 PostgreSQL 연결 설정은 기본값을 유지하세요.')
    require(values.keys() == ENV_KEYS, 'k8s.env 설정 키가 계약과 다릅니다. 누락·오타를 확인하세요.')
    optional = {'IMAGE_PULL_SECRET', 'ODBC_HOST_PATH', 'ODBC_SECRET_NAME', 'INGRESS_CLASS_NAME', 'INGRESS_TLS_SECRET', *RUNTIME_KEYS[2:], *OIDC_KEYS}
    for key, value in values.items():
        if key not in optional:
            require(bool(value.strip()), f'필수 설정 누락: {key}')
        if not example and value:
            require(not RUNTIME.is_placeholder(value), f'실제 값으로 교체하세요: {key}')
        # Helm은 일부 문자열을 템플릿으로 평가하므로 설정 입력의 템플릿 실행을 막는다.
        require('{{' not in value and '}}' not in value, f'템플릿 표현식 금지: {key}')
    validate_oidc(values)
    for key in ('NAMESPACE', 'AIRFLOW_OIDC_CA_CONFIGMAP', 'NODE_NAME', 'IMAGE_PULL_SECRET', 'ODBC_SECRET_NAME', 'INGRESS_CLASS_NAME', 'INGRESS_TLS_SECRET'):
        require(not values[key] or (len(values[key]) <= 253 and re.fullmatch(r'[a-z0-9]([a-z0-9.-]*[a-z0-9])?', values[key])), f'Kubernetes 이름 형식 오류: {key}')
    require(len(values['NAMESPACE']) <= 40 and '.' not in values['NAMESPACE'], 'NAMESPACE는 40자 이하 DNS label이어야 합니다.')
    paths = []
    for key in ('POSTGRES_HOST_PATH', 'LOGS_HOST_PATH'):
        path = Path(values[key])
        require(path.is_absolute() and len(path.parts) >= 4 and '..' not in path.parts, f'명시적인 절대 디렉터리 필요: {key}')
        paths.append(path)
    require(not (values['ODBC_HOST_PATH'] and values['ODBC_SECRET_NAME']), 'ODBC_HOST_PATH와 ODBC_SECRET_NAME은 하나만 지정하세요.')
    if values['ODBC_HOST_PATH']:
        odbc = Path(values['ODBC_HOST_PATH'])
        require(odbc.is_absolute() and len(odbc.parts) >= 4 and '..' not in odbc.parts, 'ODBC_HOST_PATH는 명시적인 절대 디렉터리여야 합니다.')
        require(all(odbc != path and odbc not in path.parents and path not in odbc.parents for path in paths), 'ODBC와 DB·로그 경로는 서로 겹치면 안 됩니다.')
    require(paths[0] != paths[1] and paths[0] not in paths[1].parents and paths[1] not in paths[0].parents, 'DB와 로그 경로는 서로 겹치면 안 됩니다.')
    for key in ('POSTGRES_STORAGE_SIZE', 'LOGS_STORAGE_SIZE'):
        require(re.fullmatch(r'[1-9][0-9]*(Gi|Ti)', values[key]), f'Gi 또는 Ti 용량 필요: {key}')
    for key in ('POSTGRES_UID', 'POSTGRES_GID'):
        require(values[key].isdigit() and int(values[key]) > 0, f'양수 UID/GID 필요: {key}')
    require(re.search(r':16(?:[.-][a-zA-Z0-9_.-]+)?(?:@sha256:[a-f0-9]{64})?$', values['POSTGRES_IMAGE']), 'POSTGRES_IMAGE는 PostgreSQL 16 태그를 지정하세요.')
    require(re.fullmatch(r'[a-zA-Z0-9./:_-]+', values['AIRFLOW_IMAGE_REPOSITORY']), 'AIRFLOW_IMAGE_REPOSITORY 형식 오류')
    require(re.fullmatch(r'3\.3\.2-[a-zA-Z0-9_.-]+', values['AIRFLOW_IMAGE_TAG']), 'AIRFLOW_IMAGE_TAG는 3.3.2-으로 시작하는 고유 태그가 필요합니다.')
    require(values['INGRESS_ENABLED'] in ('true', 'false'), 'INGRESS_ENABLED는 true 또는 false여야 합니다.')
    for key in ('AIRFLOW_WEBSERVER_BASE_URL', 'AIRFLOW_API_BASE_URL', 'KNOX_MESSENGER_API_BASE_URL', 'MAIL_API_URL'):
        if not values[key]:
            continue
        url = urlsplit(values[key])
        require(url.scheme in ('http', 'https') and url.hostname and not url.username and not url.password
                and (key == 'MAIL_API_URL' or not url.query) and not url.fragment
                and not any(c.isspace() for c in values[key]), f'HTTP(S) URL 형식 오류: {key}')
        if key == 'AIRFLOW_WEBSERVER_BASE_URL':
            require(url.path in ('', '/', '/airflow'), '공개 URL은 루트 경로를 사용합니다. 로컬 개발에서는 /airflow를 사용할 수 있습니다.')
    if values['INGRESS_ENABLED'] == 'true':
        require(values['INGRESS_CLASS_NAME'], 'Ingress 사용 시 INGRESS_CLASS_NAME이 필요합니다.')
        if urlsplit(values['AIRFLOW_WEBSERVER_BASE_URL']).scheme == 'https' and values['INGRESS_CLASS_NAME'] != 'traefik':
            require(values['INGRESS_TLS_SECRET'], 'HTTPS Ingress에는 INGRESS_TLS_SECRET이 필요합니다.')
    require('@' in values['AIRFLOW_ADMIN_EMAIL'], 'AIRFLOW_ADMIN_EMAIL 형식 오류')
    receivers = [item.strip() for item in values['AIRFLOW_FAILURE_ALERT_EMAIL_TO'].split(',') if item.strip()]
    if receivers:
        for key in ('MAIL_API_URL', 'MAIL_API_KEY', 'MAIL_API_SYSTEM_ID', 'MAIL_API_KNOX_ID', 'AIRFLOW_FAILURE_ALERT_EMAIL_FROM'):
            require(values[key].strip(), f'메일 실패 알림 필수 설정 누락: {key}')
        for address in [values['AIRFLOW_FAILURE_ALERT_EMAIL_FROM'], *receivers]:
            require(re.fullmatch(r'[^\s@,<>]+@[^\s@,<>]+\.[^\s@,<>]+', address), '메일 실패 알림 이메일 형식 오류')
    if not example:
        for key in SECRET_KEYS:
            require(len(values[key]) >= 20, f'20자 이상 비밀값 필요: {key}')
        if values['AIRFLOW_AUTH_MODE'] == 'keycloak':
            # Keycloak client 등록과 로그인에 자리표시자 secret이 쓰이지 않도록 길이를 확인한다.
            require(len(values['AIRFLOW_OIDC_CLIENT_SECRET']) >= 20, '20자 이상 비밀값 필요: AIRFLOW_OIDC_CLIENT_SECRET')
        try:
            decoded = base64.b64decode(values['AIRFLOW_FERNET_KEY'], altchars=b'-_', validate=True)
        except ValueError:
            decoded = b''
        require(len(decoded) == 32, 'AIRFLOW_FERNET_KEY는 32바이트 URL-safe base64 키여야 합니다.')


def validate_oidc(values):
    """운영 HTTPS와 명시적인 로컬 HTTP 예외, CA 마운트 계약을 검사한다."""
    require(values['AIRFLOW_AUTH_MODE'] in ('db', 'keycloak'), 'AIRFLOW_AUTH_MODE는 db 또는 keycloak이어야 합니다.')
    require(values['AIRFLOW_OIDC_ALLOW_HTTP'] in ('true', 'false'), 'AIRFLOW_OIDC_ALLOW_HTTP 형식 오류')
    if values['AIRFLOW_AUTH_MODE'] == 'db':
        return
    for key in ('AIRFLOW_OIDC_ISSUER', 'AIRFLOW_OIDC_CLIENT_ID', 'AIRFLOW_OIDC_CLIENT_SECRET'):
        require(values[key].strip(), f'필수 OIDC 설정 누락: {key}')
    require(re.fullmatch(r'[a-zA-Z0-9_-]+', values['AIRFLOW_OIDC_CLIENT_ID']), 'OIDC client ID 형식 오류')
    local = values['AIRFLOW_OIDC_ALLOW_HTTP'] == 'true'
    public = urlsplit(values['AIRFLOW_WEBSERVER_BASE_URL'])
    require(not local or public.hostname in ('localhost', '127.0.0.1'), 'OIDC HTTP 예외는 localhost 개발 환경에서만 허용합니다.')
    require(local or public.scheme == 'https', '운영 OIDC callback은 HTTPS여야 합니다.')
    for key in ('AIRFLOW_OIDC_ISSUER', 'AIRFLOW_OIDC_BACKCHANNEL_BASE_URL'):
        if not values[key]:
            continue
        url = urlsplit(values[key])
        require(url.scheme in (('http', 'https') if local else ('https',)) and url.hostname
                and not url.username and not url.password and not url.query and not url.fragment
                and re.fullmatch(r'/realms/[a-zA-Z0-9_.-]+/?', url.path)
                and not any(c.isspace() for c in values[key]), f'OIDC realm URL 형식 오류: {key}')
    ca, configmap = values['AIRFLOW_OIDC_CA_BUNDLE'], values['AIRFLOW_OIDC_CA_CONFIGMAP']
    require(bool(ca) == bool(configmap), 'OIDC CA bundle과 ConfigMap을 함께 지정하세요.')
    require(not ca or ca == '/etc/airflow/oidc-ca/ca.crt', 'OIDC CA bundle 경로는 /etc/airflow/oidc-ca/ca.crt입니다.')


def run(args, *, data=None, sensitive=False):
    """셸 해석 없이 실행하고 Secret 관련 오류 출력은 숨긴다."""
    result = subprocess.run([str(arg) for arg in args], input=data, capture_output=True, text=True)
    if result.returncode:
        detail = '민감값 보호를 위해 출력을 생략합니다.' if sensitive else result.stderr.strip()
        raise ValueError(f'{Path(args[0]).name} 실행 실패: {detail}')
    return result.stdout


def version_tuple(value):
    """도구 버전 문자열의 주요 세 숫자를 추출한다."""
    match = re.search(r'v?(\d+)\.(\d+)\.(\d+)', value)
    require(match, '도구 버전을 확인할 수 없습니다.')
    return tuple(map(int, match.groups()))


def chart_path():
    """명시한 로컬 chart 또는 기본 캐시의 고정된 checksum을 확인한다."""
    path = Path(os.environ.get('AIRFLOW_CHART_FILE', BASE / f'helm/vendor/airflow-{LOCK["version"]}.tgz'))
    require(path.is_file(), 'Helm chart 준비 필요: fetch-chart 또는 AIRFLOW_CHART_FILE을 사용하세요.')
    require(hashlib.sha256(path.read_bytes()).hexdigest() == LOCK['sha256'], 'Helm chart SHA-256 불일치')
    require(shutil.which('helm'), 'Helm 실행 파일 준비 필요: Helm >= ' + LOCK['helmVersion'])
    require(version_tuple(run(['helm', 'version', '--short'])) >= version_tuple(LOCK['helmVersion']), 'Helm 버전이 요구사항보다 낮습니다.')
    return path.resolve()


def substitute(value, settings):
    """JSON 문자열 자리표시자를 치환하며 숫자 필드의 타입을 유지한다."""
    if isinstance(value, dict):
        return {key: substitute(item, settings) for key, item in value.items()}
    if isinstance(value, list):
        return [substitute(item, settings) for item in value]
    if isinstance(value, str):
        if value in ('__POSTGRES_UID__', '__POSTGRES_GID__'):
            return int(settings[value[2:-2]])
        return re.sub(r'__([A-Z_]+)__', lambda match: settings[match[1]], value)
    return value


def manifests(settings):
    """별도 관리하는 DB와 스토리지의 Kubernetes List를 구성한다."""
    result = {}
    for name, path in [('storage', 'storage/volumes.json'), ('postgres', 'postgres/stack.json')]:
        result[name] = substitute(json.loads((BASE / 'k8s' / path).read_text()), settings)
    if settings['IMAGE_PULL_SECRET']:
        result['postgres']['items'][1]['spec']['template']['spec']['imagePullSecrets'] = [{'name': settings['IMAGE_PULL_SECRET']}]
    if settings.get('POSTGRES_MODE', 'internal') == 'external':
        result['postgres']['items'] = []
        result['storage']['items'] = [item for item in result['storage']['items']
                                      if not item['metadata']['name'].endswith('airflow-postgres')]
    return result


def helm_values(settings, pause_new_dags=False):
    """Secret 참조와 서버별 공개 설정만 Helm에 전달한다."""
    result = {
        'defaultAirflowRepository': settings['AIRFLOW_IMAGE_REPOSITORY'],
        'defaultAirflowTag': settings['AIRFLOW_IMAGE_TAG'],
        'nodeSelector': {'kubernetes.io/hostname': settings['NODE_NAME']},
        'config': {
            'api': {'base_url': settings['AIRFLOW_WEBSERVER_BASE_URL']},
            'core': {'execution_api_server_url': (
                f'http://airflow-api-server.{settings["NAMESPACE"]}.svc.cluster.local:8080'
                f'{urlsplit(settings["AIRFLOW_WEBSERVER_BASE_URL"]).path.rstrip("/")}/execution/'
            )},
        },
        'imagePullSecrets': [{'name': settings['IMAGE_PULL_SECRET']}] if settings['IMAGE_PULL_SECRET'] else [],
    }
    if pause_new_dags:
        result['config']['core']['dags_are_paused_at_creation'] = 'True'
    if settings['ODBC_HOST_PATH']:
        # 기존 디렉터리 전체를 유지한다. 없는 경로를 빈 디렉터리로 자동 생성하지 않는다.
        result['volumes'] = [{'name': 'odbc', 'hostPath': {'path': settings['ODBC_HOST_PATH'], 'type': 'Directory'}}]
        result['volumeMounts'] = [{'name': 'odbc', 'mountPath': '/usr/local/odbc', 'readOnly': True}]
    elif settings['ODBC_SECRET_NAME']:
        result['volumes'] = [{'name': 'odbc', 'secret': {'secretName': settings['ODBC_SECRET_NAME']}}]
        result['volumeMounts'] = [{'name': 'odbc', 'mountPath': '/usr/local/odbc', 'readOnly': True}]
    if settings['AIRFLOW_OIDC_CA_CONFIGMAP']:
        result.setdefault('volumes', []).append({'name': 'oidc-ca', 'configMap': {'name': settings['AIRFLOW_OIDC_CA_CONFIGMAP']}})
        result.setdefault('volumeMounts', []).append({'name': 'oidc-ca', 'mountPath': '/etc/airflow/oidc-ca', 'readOnly': True})
    if settings['INGRESS_ENABLED'] == 'true':
        url = urlsplit(settings['AIRFLOW_WEBSERVER_BASE_URL'])
        separate_tls = settings['INGRESS_CLASS_NAME'] != 'traefik'
        annotations = {}
        if settings['INGRESS_CLASS_NAME'] == 'traefik':
            annotations['traefik.ingress.kubernetes.io/router.entrypoints'] = 'websecure' if url.scheme == 'https' else 'web'
            if url.scheme == 'https':
                annotations['traefik.ingress.kubernetes.io/router.tls'] = 'true'
        result['ingress'] = {'apiServer': {
            'annotations': annotations,
            'enabled': True, 'path': url.path.rstrip('/') or '/', 'pathType': 'Prefix',
            'ingressClassName': settings['INGRESS_CLASS_NAME'],
            'hosts': [{'name': url.hostname, 'tls': {
                'enabled': url.scheme == 'https' and separate_tls,
                'secretName': settings.get('INGRESS_TLS_SECRET', '') if separate_tls else '',
            }}],
        }}
    return result


def secret_manifest(settings):
    """Kubernetes에 stdin으로만 전달할 Secret을 생성한다."""
    def secret(name, data):
        return {'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': name, 'namespace': settings['NAMESPACE']}, 'type': 'Opaque', 'data': {key: base64.b64encode(value.encode()).decode() for key, value in data.items()}}
    password = quote(settings['POSTGRES_PASSWORD'], safe='')
    db = {key: settings.get(key, default) for key, default in DB_DEFAULTS.items()}
    return {'apiVersion': 'v1', 'kind': 'List', 'items': [
        secret('airflow-postgres', {'password': settings['POSTGRES_PASSWORD']}),
        secret('airflow-metadata', {'connection': f'postgresql://{db["POSTGRES_USER"]}:{password}@{db["POSTGRES_HOST"]}:{db["POSTGRES_PORT"]}/{db["POSTGRES_DB"]}'}),
        secret('airflow-fernet', {'fernet-key': settings['AIRFLOW_FERNET_KEY']}),
        secret('airflow-webserver-key', {'webserver-secret-key': settings['AIRFLOW_WEBSERVER_SECRET_KEY']}),
        secret('airflow-api-jwt', {'jwt-secret': settings['AIRFLOW_WEBSERVER_SECRET_KEY']}),
        secret('airflow-api-key', {'api-secret-key': settings['AIRFLOW_WEBSERVER_SECRET_KEY']}),
        secret('airflow-admin', {'username': settings['AIRFLOW_ADMIN_USERNAME'], 'password': settings['AIRFLOW_ADMIN_PASSWORD'], 'email': settings['AIRFLOW_ADMIN_EMAIL']}),
        secret('airflow-runtime', {key: settings[key] for key in RUNTIME_KEYS}),
    ]}


def render(settings, directory, chart, pause_new_dags=False, values_file=None):
    """공개 설정과 manifest를 렌더하고 공식 차트 schema를 검사한다."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    values = directory / 'values.json'
    values.write_text(json.dumps(helm_values(settings, pause_new_dags), indent=2) + '\n')
    flags = ['-n', settings['NAMESPACE'], '-f', BASE / 'helm/values.yaml', '-f', values]
    if values_file:
        flags += ['-f', values_file]
    run(['helm', 'lint', chart, *flags])
    content = run(['helm', 'template', 'airflow', chart, '--kube-version', LOCK['kubernetesVersion'], *flags])
    (directory / 'airflow.yaml').write_text(content)
    for name, manifest in manifests(settings).items():
        (directory / f'{name}.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return flags


def rendered_resources(context, rendered):
    """최종 Helm 렌더를 클러스터에 적용하지 않고 JSON 리소스로 읽는다."""
    stream = run(['kubectl', '--context', context, 'create', '--dry-run=client', '--validate=false',
                  '-f', rendered, '-o', 'json'], sensitive=True)
    resources = []
    decoder = json.JSONDecoder()
    while stream.strip():
        stream = stream.lstrip()
        item, consumed = decoder.raw_decode(stream)
        resources.extend(item['items'] if item.get('kind') == 'List' else [item])
        stream = stream[consumed:]
    require(resources, 'Airflow 최종 렌더에서 리소스를 읽을 수 없습니다.')
    return resources


def rendered_workloads(context, rendered):
    """최종 chart에 존재하며 재시작과 준비 대기를 지원하는 workload만 선택한다."""
    return [f'{item["kind"].lower()}/{item["metadata"]["name"]}'
            for item in rendered_resources(context, rendered)
            if item['kind'] in ('Deployment', 'StatefulSet', 'DaemonSet')]


def rendered_pods(settings, context, rendered):
    """최종 Helm 렌더와 별도 PostgreSQL 원본에서 실제 Pod 설정을 읽는다."""
    resources = rendered_resources(context, rendered)
    resources.extend(manifests(settings)['postgres']['items'])
    pods = []
    for item in resources:
        if item['kind'] in ('Deployment', 'StatefulSet', 'DaemonSet', 'Job'):
            pods.append((item['metadata']['name'], item['spec']['template']['spec']))
        elif item['kind'] == 'Pod':
            pods.append((item['metadata']['name'], item['spec']))
        elif item['kind'] == 'CronJob':
            pods.append((item['metadata']['name'], item['spec']['jobTemplate']['spec']['template']['spec']))
    require(pods, 'Airflow 최종 렌더에 검사할 Pod 설정이 없습니다.')
    return pods


def tolerates(taint, tolerations):
    """Kubernetes의 effect·operator·key·value 규칙으로 taint 허용 여부를 판단한다."""
    return any(
        (not item.get('effect') or item['effect'] == taint['effect'])
        and ((item.get('operator', 'Equal') == 'Exists' and (not item.get('key') or item['key'] == taint['key']))
             or (item.get('operator', 'Equal') == 'Equal' and item.get('key') == taint['key']
                 and item.get('value', '') == taint.get('value', '')))
        for item in tolerations)


def check_pod_taints(settings, context, rendered, default_nodes):
    """override를 포함한 각 Pod의 배치 대상 노드와 toleration을 함께 확인한다."""
    default_selector = (('kubernetes.io/hostname', settings['NODE_NAME']),)
    cached = {default_selector: default_nodes}
    for name, spec in rendered_pods(settings, context, rendered):
        selector = tuple(sorted(spec.get('nodeSelector', {}).items()))
        if selector not in cached:
            args = ['kubectl', '--context', context, 'get', 'nodes', '-o', 'json']
            if selector:
                args += ['-l', ','.join(f'{key}={value}' for key, value in selector)]
            cached[selector] = json.loads(run(args))['items']
        candidates = [node for node in cached[selector] if not node['spec'].get('unschedulable')
                      and any(c['type'] == 'Ready' and c['status'] == 'True' for c in node['status']['conditions'])
                      and (not spec.get('nodeName') or node['metadata']['name'] == spec['nodeName'])]
        require(candidates, f'{name}: 최종 nodeSelector에 맞는 Ready·스케줄 가능 노드가 없습니다.')
        require(any(all(tolerates(taint, spec.get('tolerations', []))
                        for taint in node['spec'].get('taints', []) if taint.get('effect') in ('NoSchedule', 'NoExecute'))
                    for node in candidates), f'{name}: 대상 노드에 Pod가 허용하지 않는 차단 taint가 있습니다.')


def check_required_resources(settings, context, pending_tls=None):
    """공용 리소스 변경 전에 외부 입력을 확인하며 검증된 생성 예정 TLS만 허용한다."""
    kube = ['kubectl', '--context', context]
    scoped = [*kube, '-n', settings['NAMESPACE']]
    if settings['AIRFLOW_OIDC_CA_CONFIGMAP']:
        run([*scoped, 'get', 'configmap', settings['AIRFLOW_OIDC_CA_CONFIGMAP'], '-o', 'name'])
    for key, resource in [('IMAGE_PULL_SECRET', 'secret'), ('ODBC_SECRET_NAME', 'secret'),
                          ('INGRESS_TLS_SECRET', 'secret'), ('INGRESS_CLASS_NAME', 'ingressclass')]:
        if not settings.get(key) or (key.startswith('INGRESS_') and settings['INGRESS_ENABLED'] != 'true'):
            continue
        if key == 'INGRESS_TLS_SECRET' and settings['INGRESS_CLASS_NAME'] == 'traefik':
            continue
        if key == 'INGRESS_TLS_SECRET' and pending_tls and pending_tls.get('metadata') == {
                'name': settings[key], 'namespace': settings['NAMESPACE']}:
            continue
        run([*(kube if resource == 'ingressclass' else scoped), 'get', resource, settings[key], '-o', 'name'])


def check_cluster_inputs(settings, context, rendered=None):
    """배포 전 버전·최종 Pod 배치·기존 DB와 Fernet 키를 읽기 전용으로 검사한다."""
    require(context and context.strip(), '대상 context를 명시하세요.')
    kube = ['kubectl', '--context', context]
    namespace = settings['NAMESPACE']
    scoped = [*kube, '-n', namespace]
    version = json.loads(run([*kube, 'version', '-o', 'json']))['serverVersion']['gitVersion']
    require(version_tuple(version) >= version_tuple(LOCK['kubernetesVersion']), 'Kubernetes 버전이 chart 요구사항보다 낮습니다.')
    nodes = json.loads(run([*kube, 'get', 'nodes', '-l', f'kubernetes.io/hostname={settings["NODE_NAME"]}', '-o', 'json']))['items']
    require(len(nodes) == 1, 'NODE_NAME에 대응하는 Kubernetes 노드는 정확히 하나여야 합니다.')
    require(not nodes[0]['spec'].get('unschedulable') and any(c['type'] == 'Ready' and c['status'] == 'True' for c in nodes[0]['status']['conditions']), '대상 노드가 Ready 상태가 아니거나 cordon 상태입니다.')
    if rendered is None:
        with tempfile.TemporaryDirectory(prefix='airflow-preflight-') as temporary:
            render(settings, temporary, chart_path())
            check_pod_taints(settings, context, Path(temporary) / 'airflow.yaml', nodes)
    else:
        check_pod_taints(settings, context, rendered, nodes)
    for name, key, setting in [('airflow-postgres', 'password', 'POSTGRES_PASSWORD'), ('airflow-fernet', 'fernet-key', 'AIRFLOW_FERNET_KEY')]:
        current = run([*scoped, 'get', 'secret', name, '--ignore-not-found', '-o', 'json'], sensitive=True)
        if current.strip():
            stored = base64.b64decode(json.loads(current)['data'][key]).decode()
            require(stored == settings[setting], f'기존 {setting}과 다릅니다. 키 교체·DB 비밀번호 변경은 별도 절차가 필요합니다.')
        elif name == 'airflow-postgres' and settings.get('POSTGRES_MODE', 'internal') == 'internal':
            pvc = run([*scoped, 'get', 'pvc', 'airflow-postgres', '--ignore-not-found', '-o', 'name'])
            require(not pvc.strip(), '기존 DB PVC가 있으나 airflow-postgres Secret이 없습니다. 실제 DB 비밀번호로 Secret을 먼저 복원하세요.')
        elif name == 'airflow-fernet':
            # 기존 설치 흔적이 있으면 env의 키를 새로 적용하지 않고 원래 Secret 복원을 요구한다.
            for kind, resource in [('pvc', 'airflow-postgres'), ('secret', 'airflow-metadata'),
                                   ('deployment', 'airflow-scheduler'), ('deployment', 'airflow-webserver'),
                                   ('deployment', 'airflow-triggerer'), ('deployment', 'airflow-api-server'), ('deployment', 'airflow-dag-processor')]:
                existing = run([*scoped, 'get', kind, resource, '--ignore-not-found', '-o', 'name'],
                               sensitive=kind == 'secret')
                require(not existing.strip(), '기존 Airflow 설치의 Fernet Secret이 없습니다. 원래 암호화 키로 airflow-fernet Secret을 먼저 복원하세요.')


def check_ingress_tls(settings, context):
    """단독 Helm 배포에서도 공용 HTTPS 인증서와 controller 연결을 먼저 검사한다."""
    kube = ['kubectl', '--context', context]
    if settings['INGRESS_ENABLED'] == 'true' and settings['INGRESS_CLASS_NAME'] == 'traefik':
        host = urlsplit(settings['AIRFLOW_WEBSERVER_BASE_URL'])
        if host.scheme == 'https':
            current = json.loads(run([*kube, '-n', 'etch-sso', 'get', 'deployment', 'traefik', '-o', 'json']))
            tls.check(kube, host.hostname, current)


def deploy(settings, context, chart, pause_new_dags=False, values_file=None):
    """노드와 기존 Secret을 확인한 뒤 DB → Helm hook → Pod 순서로 배포한다."""
    kube = ['kubectl', '--context', context]
    namespace = settings['NAMESPACE']
    scoped = [*kube, '-n', namespace]
    with tempfile.TemporaryDirectory(prefix='airflow-deploy-') as temporary:
        flags = render(settings, temporary, chart, pause_new_dags, values_file)
        check_cluster_inputs(settings, context, Path(temporary) / 'airflow.yaml')
        check_required_resources(settings, context)
        check_ingress_tls(settings, context)
        workloads = rendered_workloads(context, Path(temporary) / 'airflow.yaml')
        existing_namespace = run([*kube, 'get', 'namespace', namespace, '--ignore-not-found', '-o', 'name'])
        if not existing_namespace.strip():
            # 기존 Namespace의 보안 정책과 운영 metadata는 수정하지 않는다.
            run([*kube, 'create', '-f', '-'], data=json.dumps({'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': namespace}}))
        run([*scoped, 'apply', '--server-side', '--field-manager=airflow-deploy', '-f', '-'], data=json.dumps(secret_manifest(settings)), sensitive=True)
        print('Secret 확인 완료. 스토리지와 PostgreSQL을 적용합니다.', flush=True)
        run([*kube, 'apply', '-f', Path(temporary) / 'storage.json'])
        if settings.get('POSTGRES_MODE', 'internal') == 'internal':
            run([*kube, 'apply', '-f', Path(temporary) / 'postgres.json'])
            run([*scoped, 'rollout', 'status', 'statefulset/airflow-postgres', '--timeout=600s'])
        print('PostgreSQL 준비 완료. Airflow migration과 관리자 생성 hook을 실행합니다.', flush=True)
        # post-install migration hook은 --wait와 함께 사용하면 Pod의 DB 대기와 교착한다.
        run(['helm', 'upgrade', '--install', 'airflow', chart, '--kube-context', context, '--timeout', '10m', *flags])
        # envFrom Secret 변경은 자동 rollout되지 않으므로 배포마다 명시적으로 재시작한다.
        if workloads:
            run([*scoped, 'rollout', 'restart', *workloads])
        for workload in workloads:
            run([*scoped, 'rollout', 'status', workload, '--timeout=600s'])
    print('Airflow 배포 완료. DAG 활성 상태와 기존 scheduler의 중복 실행 여부를 확인하세요.')


def image_build_command(builder, namespace, address, buildkit_host):
    """빌더 연결과 로컬 의존성 이미지 재사용 조건을 확인하고 빌드 명령을 반환한다."""
    require(builder in ('auto', 'nerdctl', 'docker'), '지원하는 빌더는 auto, nerdctl, docker입니다.')
    if builder == 'auto':
        builder = 'nerdctl' if shutil.which('nerdctl') else 'docker'
    require(shutil.which(builder),
            f'이미지 빌더 {builder} 실행 파일을 찾을 수 없습니다. '
            'containerd에는 nerdctl·BuildKit을 준비하거나 --builder docker로 Docker를 사용하세요. '
            '준비 절차: deploy/airflow/docs/02-artifacts.md')
    if builder == 'docker':
        try:
            run(['docker', 'info'])
        except ValueError:
            raise ValueError('Docker daemon에 연결할 수 없습니다. 같은 계정에서 docker info로 '
                             'daemon 실행·접속 설정·소켓 권한을 확인하세요.') from None
        return ['docker', 'build']

    require(re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]*', namespace), 'containerd namespace 형식 오류')
    require(address.strip() and buildkit_host.strip(), 'containerd 주소와 BuildKit 주소를 지정하세요.')
    require(shutil.which('buildctl'), 'BuildKit의 buildctl 실행 파일을 준비하세요. 준비 절차: deploy/airflow/docs/02-artifacts.md')
    command = ['nerdctl', '--address', address, '--namespace', namespace]
    try:
        run([*command, 'info'])
    except ValueError:
        raise ValueError('containerd에 연결할 수 없습니다. nerdctl info로 '
                         'containerd 실행·주소·소켓 권한을 확인하세요.') from None
    try:
        workers = json.loads(run(['buildctl', '--addr', buildkit_host, 'debug', 'workers',
                                  '--format', '{{json .}}']))
    except ValueError:
        raise ValueError('BuildKit worker를 조회할 수 없습니다. buildkitd 실행·주소·소켓 권한과 '
                         'buildctl debug workers 출력을 확인하세요.') from None
    # OCI worker나 다른 namespace는 첫 단계의 로컬 이미지를 다음 단계에서 읽을 수 없습니다.
    require(isinstance(workers, list) and workers and all(
        isinstance(worker, dict) and isinstance(worker.get('labels'), dict)
        and worker['labels'].get('org.mobyproject.buildkit.worker.executor') == 'containerd'
        and worker['labels'].get('org.mobyproject.buildkit.worker.containerd.namespace') == namespace
        for worker in workers),
        'BuildKit은 선택한 containerd namespace와 같은 containerd worker만 사용해야 합니다. '
        '[worker.oci] enabled=false와 [worker.containerd] enabled=true, namespace를 확인하세요. '
        '준비 절차: deploy/airflow/docs/02-artifacts.md')
    return [*command, 'build', '--buildkit-host', buildkit_host, '--pull=false']


def build_image(settings, path, *, builder='auto', containerd_namespace='default',
                containerd_address=DEFAULT_CONTAINERD_ADDRESS, buildkit_host=DEFAULT_BUILDKIT_HOST):
    """기존 의존성 Dockerfile에 DAG를 추가하며 이미지는 자동 push하지 않는다."""
    build = read_env(path)
    require(build.keys() == {'APT_DEBIAN_CODENAME', 'APT_DEBIAN_ARCH', 'BIGDATAQUERY_ODBC_DEB_URL', 'INSTALL_BIGDATAQUERY_PYTHON', 'PIP_INDEX_URL', 'APT_DEBIAN_REPOSITORY', 'PIP_TRUSTED_HOST', 'INSTALL_BIGDATAQUERY_ODBC', 'AIRFLOW_BASE_IMAGE', 'PIP_EXTRA_INDEX_URL'}, 'build.env 설정 키가 계약과 다릅니다.')
    require(re.search(r':3\.3\.2-python3\.12(?:@sha256:[a-f0-9]{64})?$', build['AIRFLOW_BASE_IMAGE']), '기본 이미지는 Airflow 3.3.2 Python 3.12이어야 합니다.')
    for key in ('INSTALL_BIGDATAQUERY_PYTHON', 'INSTALL_BIGDATAQUERY_ODBC'):
        require(build[key] in ('true', 'false'), f'true 또는 false 필요: {key}')
    require(build['INSTALL_BIGDATAQUERY_ODBC'] != 'true' or build['BIGDATAQUERY_ODBC_DEB_URL'], 'ODBC 설치에는 BIGDATAQUERY_ODBC_DEB_URL이 필요합니다.')
    root = BASE.parents[1]
    source = root / 'apps/airflow'
    require(all((source / name).exists() for name in ('image/Dockerfile.dependencies', 'image/Dockerfile', 'image/bootstrap-user.py', 'image/webserver_config.py', 'image/keycloak_security.py', 'image/oidc_claims.py', 'dags', 'plugins')),
            '이미지 빌드 소스(apps/airflow)가 없습니다. 저장소 전체 checkout에서 실행하세요.')
    command = image_build_command(builder, containerd_namespace, containerd_address, buildkit_host)
    final = settings['AIRFLOW_IMAGE_REPOSITORY'] + ':' + settings['AIRFLOW_IMAGE_TAG']
    dependency = final + '-dependencies'
    # 의존성 빌드 context에는 Dockerfile만 보내 로컬 로그·DSN·env 전송을 피한다.
    with tempfile.TemporaryDirectory(prefix='airflow-build-') as temporary:
        shutil.copyfile(source / 'image/Dockerfile.dependencies', Path(temporary) / 'Dockerfile')
        args = [*command, '-t', dependency]
        for key, value in build.items():
            args += ['--build-arg', f'{key}={value}']
        run([*args, temporary])
    run([*command, '-f', source / 'image/Dockerfile', '--build-arg', f'AIRFLOW_DEPENDENCY_IMAGE={dependency}', '-t', final, source])
    print('Airflow 이미지 빌드 완료. registry push 또는 단일 노드 이미지 반입을 진행하세요.')


def main():
    """독립 실행 명령을 처리하며 기본 검사는 추적 중인 env의 구조를 확인한다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('init-secrets', 'fetch-chart', 'build-image', 'check', 'render', 'deploy'))
    parser.add_argument('--env', type=Path, help='실제 k8s.env 경로. check는 생략하면 저장소 env 구조만 검사')
    parser.add_argument('--pause-new-dags', action='store_true', help='Portal 연결 전 UI 기동용: 신규 DAG를 일시정지로 생성')
    parser.add_argument('--build-env', type=Path, help='build.env 경로. build-image에 필수')
    parser.add_argument('--builder', choices=('auto', 'nerdctl', 'docker'), default='auto',
                        help='이미지 빌더. auto는 nerdctl 우선, 없으면 Docker 사용')
    parser.add_argument('--containerd-namespace', default='default', help='nerdctl·BuildKit의 공통 namespace')
    parser.add_argument('--containerd-address', default=DEFAULT_CONTAINERD_ADDRESS, help='nerdctl의 containerd 소켓 주소')
    parser.add_argument('--buildkit-host', default=DEFAULT_BUILDKIT_HOST, help='nerdctl·buildctl의 공통 BuildKit 주소')
    parser.add_argument('--output', type=Path, help='render 출력 디렉터리')
    parser.add_argument('--context', help='deploy 대상 kubectl context, 필수')
    parser.add_argument('--values', type=Path, help='환경별 비밀값 없는 Helm override')
    args = parser.parse_args()
    if args.command == 'init-secrets':
        target = args.env or DEFAULT_ENV
        require(target.suffix == '.env', '.env 경로를 지정하세요.')
        exists = target.exists()
        if exists:
            current = read_env(target)
            require(all(not current.get(key) for key in SECRET_KEYS), '기존 env에 키가 있습니다. 다시 생성하지 않습니다.')
            content = target.read_text()
        else:
            content = DEFAULT_ENV.read_text()
        generated = {}
        # Portal trigger token은 Portal에서 받은 값을 넣으므로 생성 대상에서 제외한다.
        for key in (name for name in SECRET_KEYS if name != 'AIRFLOW_TRIGGER_TOKEN'):
            generated[key] = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode() if key == 'AIRFLOW_FERNET_KEY' else secrets.token_urlsafe(32)
        generated['AIRFLOW_TRIGGER_TOKEN'] = ''
        lines = []
        for line in content.splitlines():
            key = line.partition('=')[0]
            lines.append(f'{key}={generated.pop(key)}' if key in generated else line)
        lines.extend(f'{key}={value}' for key, value in generated.items())
        # 기존 일반 설정은 보존하고 생성값은 같은 env에 저장합니다.
        if exists:
            target.write_text('\n'.join(lines) + '\n')
            target.chmod(0o600)
        else:
            with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as output:
                output.write('\n'.join(lines) + '\n')
        print('env 초기 키 생성 완료. 같은 파일의 서버 정보와 Portal trigger token을 확인하세요.')
        return
    if args.command == 'fetch-chart':
        require(shutil.which('helm'), 'Helm 실행 파일 준비 필요: Helm >= ' + LOCK['helmVersion'])
        require(version_tuple(run(['helm', 'version', '--short'])) >= version_tuple(LOCK['helmVersion']), 'Helm 버전이 요구사항보다 낮습니다.')
        filename = f'{LOCK["name"]}-{LOCK["version"]}.tgz'
        # 미러 index의 실제 패키지 경로를 사용하고 검증 전에는 기존 캐시를 덮어쓰지 않습니다.
        with tempfile.TemporaryDirectory(prefix='airflow-chart-') as temporary:
            run(['helm', 'pull', LOCK['name'], '--repo', LOCK['repository'],
                 '--version', LOCK['version'], '--destination', temporary])
            content = (Path(temporary) / filename).read_bytes()
        require(hashlib.sha256(content).hexdigest() == LOCK['sha256'], '다운로드 chart SHA-256 불일치')
        directory = BASE / 'helm/vendor'
        directory.mkdir(parents=True, exist_ok=True)
        (directory / filename).write_bytes(content)
        print('사내 Helm 미러 chart 다운로드·SHA-256 검사 완료')
        return
    example = args.command == 'check' and args.env is None
    settings = read_env(args.env or DEFAULT_ENV)
    validate(settings, example=example)
    if args.command == 'build-image':
        require(args.build_env, 'build-image에는 --build-env를 명시하세요.')
        build_image(settings, args.build_env, builder=args.builder, containerd_namespace=args.containerd_namespace,
                    containerd_address=args.containerd_address, buildkit_host=args.buildkit_host)
    elif args.command == 'deploy':
        require(args.context, 'deploy에는 --context를 명시하세요.')
        deploy(settings, args.context, chart_path(), args.pause_new_dags, args.values)
    elif args.command == 'render':
        require(args.output, 'render에는 --output 디렉터리가 필요합니다.')
        render(settings, args.output, chart_path(), args.pause_new_dags, args.values)
        print('렌더 완료: Secret 값은 출력 파일에 포함하지 않았습니다.')
    else:
        with tempfile.TemporaryDirectory(prefix='airflow-check-') as temporary:
            render(settings, temporary, chart_path(), args.pause_new_dags, args.values)
        print('Airflow Helm·PostgreSQL 원본 검사 통과' + (' (저장소 env 정적 검사; 실제 서버 준비 검사는 별도)' if example else ' (실제 설정; 클러스터 적용 없음)'))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError) as error:
        print(f'오류: {error}', file=sys.stderr)
        sys.exit(1)
