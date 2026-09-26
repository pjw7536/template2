"""한 PC의 kind 실행 입력과 생성 설정을 관리합니다.

공통 배포 원본은 deploy에서 읽고, 생성 파일과 비밀값은 local/shared/runtime에만 씁니다.
"""

import base64
import importlib.util
import json
import os
from pathlib import Path
import secrets

ROOT = Path(__file__).resolve().parents[3]
RUNTIME = ROOT / 'local/shared/runtime'
CLUSTER = 'tailwind-local'
CONTEXT = 'kind-' + CLUSTER
WORKER = CLUSTER + '-worker'
NAMESPACES = ('tailwind-local', 'airflow', 'etch-ftp', 'monitoring')
IMAGES = {'portal': ['tailwind-api:k8s-local', 'tailwind-web:k8s-local'],
          'mock': ['tailwind-adfs:k8s-local'], 'airflow': ['tailwind-airflow:2.11.0-local']}


def read_env(path):
    """dotenv를 실행하지 않고 읽으며 중복 키를 거부합니다."""
    values = {}
    for line in Path(path).read_text().splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        key, separator, value = line.partition('=')
        if not separator or key in values:
            raise ValueError(f'env 형식 또는 중복 키 오류: {path}')
        values[key] = value
    return values


def write_private(path, text):
    """생성 파일을 사용자 전용 권한으로 기록합니다."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), 'w') as output:
        output.write(text)


def write_env(path, values):
    """셸 치환 없이 읽을 수 있는 env 파일을 기록합니다."""
    if any('\n' in str(value) or '\r' in str(value) for value in values.values()):
        raise ValueError('env 값에는 줄바꿈을 사용할 수 없습니다.')
    write_private(path, ''.join(f'{key}={value}\n' for key, value in sorted(values.items())))


def module(app):
    """앱이 소유한 공통 배포 도구를 불러옵니다."""
    spec = importlib.util.spec_from_file_location(app + '_deploy', ROOT / f'deploy/{app}/scripts/manage.py')
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def settings():
    """공개 기본값에 사용자 로컬 설정과 명시한 환경변수를 반영합니다."""
    result = read_env(ROOT / 'local/shared/env/k8s.env.example')
    custom = ROOT / 'local/shared/env/k8s.env'
    if custom.exists():
        overrides = read_env(custom)
        if overrides.keys() - result.keys():
            raise ValueError('local/shared/env/k8s.env에 알 수 없는 키가 있습니다.')
        result.update(overrides)
    result.update({key: os.environ[key] for key in result if key in os.environ})
    for key in result:
        if key.endswith('_HOST_PATH'):
            result[key] = str((ROOT / result[key]).resolve())
    for key in ('LOCAL_DB_PORT', 'LOCAL_FTP_PORT', 'LOCAL_FTP_PASSIVE_START'):
        maximum = 65532 if key == 'LOCAL_FTP_PASSIVE_START' else 65535
        if not result[key].isdigit() or not 1024 <= int(result[key]) <= maximum:
            raise ValueError(f'{key}의 포트 범위를 확인하세요.')
    runtime = Path(result['LOCAL_RUNTIME_DATA_HOST_PATH'])
    if runtime == ROOT or len(runtime.parts) < 3:
        raise ValueError('런타임 데이터는 전용 하위 디렉터리를 사용하세요.')
    for key, value in result.items():
        if key.endswith('_HOST_PATH') and key != 'LOCAL_RUNTIME_DATA_HOST_PATH':
            path = Path(value)
            if path == runtime or path in runtime.parents or runtime in path.parents:
                raise ValueError('런타임 데이터와 업무 원본 경로는 서로 겹치면 안 됩니다.')
    return result


def credentials(create=False):
    """기존 자격증명을 재사용하며 명시한 초기화 때만 생성합니다."""
    path = RUNTIME / 'credentials.env'
    keys = ('POSTGRES_PASSWORD', 'PORTAL_DB_PASSWORD', 'AIRFLOW_DB_PASSWORD', 'KEYCLOAK_DB_PASSWORD',
            'AIRFLOW_ADMIN_PASSWORD', 'AIRFLOW_WEBSERVER_SECRET_KEY', 'AIRFLOW_TRIGGER_TOKEN',
            'GRAFANA_PASSWORD', 'FTP_PASS', 'AIRFLOW_OIDC_CLIENT_SECRET')
    if path.exists():
        result = read_env(path)
        expected = {*keys, 'AIRFLOW_FERNET_KEY'}
        if set(result) == expected - {'AIRFLOW_OIDC_CLIENT_SECRET'}:
            result['AIRFLOW_OIDC_CLIENT_SECRET'] = secrets.token_urlsafe(32) if create else 'local-render-only-0123456789'
            if create:
                write_env(path, result)
                path.chmod(0o600)
        if set(result) != expected:
            raise ValueError('기존 credentials.env 키를 확인하세요. 자동으로 교체하지 않습니다.')
        return result
    if not create:
        # 렌더·검사는 실제 자격증명을 생성하거나 출력하지 않습니다.
        return {**{key: 'local-render-only-0123456789' for key in keys},
                'AIRFLOW_FERNET_KEY': base64.urlsafe_b64encode(b'x' * 32).decode()}
    result = {key: secrets.token_urlsafe(32) for key in keys}
    result['AIRFLOW_FERNET_KEY'] = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
    path.parent.mkdir(parents=True, exist_ok=True)
    # 동시에 초기화해도 기존 키를 덮어쓰지 않습니다.
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as output:
        output.write(''.join(f'{key}={value}\n' for key, value in sorted(result.items())))
    return result


def kind_config(config):
    """호스트 포트와 영속 경로를 가진 재현 가능한 kind 설정을 만듭니다."""
    mappings = lambda pairs: [{'containerPort': container, 'hostPort': host, 'listenAddress': '127.0.0.1',
                              'protocol': 'TCP'} for container, host in pairs]
    mounts = [('LOCAL_RUNTIME_DATA_HOST_PATH', '/data/local-runtime'),
              ('DATA_MOVEMENT_HOST_PATH', '/data/data_movement'),
              ('L3_SPIDER_DATA_HOST_PATH', '/data/l3_spider/daily_anomaly'),
              ('TTTM_SPIDER_DATA_HOST_PATH', '/data/tttm_spider'),
              ('PM_COMPARISON_DATA_HOST_PATH', '/data/pm_spider')]
    return {'kind': 'Cluster', 'apiVersion': 'kind.x-k8s.io/v1alpha4', 'name': CLUSTER,
            'nodes': [{'role': 'control-plane', 'extraPortMappings': mappings([(30080, 8080), (30443, 8443), (30180, 8180)])},
                      {'role': 'worker', 'labels': {'etch.io/ftp-enabled': 'true'},
                       'extraPortMappings': mappings([(6380, int(config['LOCAL_FTP_PORT'])),
                           *[(p, p) for p in range(int(config['LOCAL_FTP_PASSIVE_START']), int(config['LOCAL_FTP_PASSIVE_START']) + 4)]]),
                       'extraMounts': [{'hostPath': config[key], 'containerPath': target,
                                        'readOnly': key not in ('LOCAL_RUNTIME_DATA_HOST_PATH', 'DATA_MOVEMENT_HOST_PATH')}
                                       for key, target in mounts]}]}


def airflow_settings(creds):
    """서버 공통 env 계약에 로컬 외부 DB·라우팅 입력을 적용합니다."""
    result = module('airflow').read_env(ROOT / 'deploy/airflow/env/k8s.env')
    result.update(NAMESPACE='airflow', NODE_NAME=WORKER, POSTGRES_MODE='external',
                  POSTGRES_HOST='external-postgres', POSTGRES_IMAGE='postgres:16',
                  POSTGRES_HOST_PATH='/data/local-runtime/unused-postgres',
                  LOGS_HOST_PATH='/data/local-runtime/airflow/logs', ODBC_HOST_PATH='',
                  AIRFLOW_IMAGE_REPOSITORY='tailwind-airflow', AIRFLOW_IMAGE_TAG='2.11.0-local',
                  AIRFLOW_ADMIN_EMAIL='airflow@localhost.test', INGRESS_ENABLED='true', INGRESS_CLASS_NAME='traefik',
                  AIRFLOW_API_BASE_URL='http://api.tailwind-local.svc.cluster.local:8000',
                  POSTGRES_PASSWORD=creds['AIRFLOW_DB_PASSWORD'],
                  KNOX_MESSENGER_API_BASE_URL='', KNOX_MESSENGER_AUTHORIZATION='',
                  KNOX_MESSENGER_SYSTEM_ID='', AIRFLOW_FAILURE_ALERT_KNOX_IDS='')
    result.update(AIRFLOW_AUTH_MODE='keycloak', AIRFLOW_OIDC_ISSUER='http://localhost:8180/realms/portal',
                  AIRFLOW_OIDC_CLIENT_ID='airflow', AIRFLOW_OIDC_CLIENT_SECRET=creds['AIRFLOW_OIDC_CLIENT_SECRET'],
                  AIRFLOW_OIDC_BACKCHANNEL_BASE_URL='http://keycloak.tailwind-local.svc.cluster.local:8080/realms/portal',
                  AIRFLOW_OIDC_ALLOW_HTTP='true', AIRFLOW_OIDC_CA_BUNDLE='', AIRFLOW_OIDC_CA_CONFIGMAP='',
                  AIRFLOW_WEBSERVER_BASE_URL='http://localhost:8080/airflow')
    for key in ('AIRFLOW_ADMIN_PASSWORD', 'AIRFLOW_WEBSERVER_SECRET_KEY', 'AIRFLOW_FERNET_KEY', 'AIRFLOW_TRIGGER_TOKEN'):
        result[key] = creds[key]
    return result


def monitoring_settings():
    """사내 registry 기본값을 가져오지 않는 로컬 모니터링 입력입니다."""
    return dict(NAMESPACE='monitoring', NODE_NAME=WORKER, DATA_HOST_PATH='/data/local-runtime/monitoring',
                DOCKER_REGISTRY='docker.io', QUAY_REGISTRY='quay.io', GHCR_REGISTRY='ghcr.io',
                K8S_REGISTRY='registry.k8s.io', IMAGE_PULL_SECRET='', GRAFANA_ADMIN_SECRET='monitoring-grafana-admin')


def api_overrides(creds):
    """공통 local API 설정에 최종 적용할 실행 연결값입니다."""
    return dict(DJANGO_DB_PASSWORD=creds['PORTAL_DB_PASSWORD'],
                AIRFLOW_BASE_URL='http://airflow-webserver.airflow.svc.cluster.local:8080/airflow',
                AIRFLOW_USERNAME='airflow', AIRFLOW_PASSWORD=creds['AIRFLOW_ADMIN_PASSWORD'],
                AIRFLOW_TRIGGER_TOKEN=creds['AIRFLOW_TRIGGER_TOKEN'],
                KNOX_MESSENGER_API_BASE_URL='', KNOX_MESSENGER_AUTHORIZATION='',
                GUNICORN_WORKERS='2')


def prepare(config):
    """초기 설정과 런타임 디렉터리를 준비하되 기존 데이터를 초기화하지 않습니다."""
    creds = credentials(create=True)
    RUNTIME.mkdir(parents=True, exist_ok=True)
    os.chmod(RUNTIME, 0o700)
    for key, value in config.items():
        if key.endswith('_HOST_PATH'):
            Path(value).mkdir(parents=True, exist_ok=True)
    base = Path(config['LOCAL_RUNTIME_DATA_HOST_PATH'])
    for sub in ('api', 'minio', 'airflow/logs', 'monitoring/prometheus', 'monitoring/alertmanager', 'monitoring/grafana'):
        (base / sub).mkdir(parents=True, exist_ok=True)
    write_env(RUNTIME / 'db.env', {**{key: creds[key] for key in ('POSTGRES_PASSWORD', 'PORTAL_DB_PASSWORD', 'AIRFLOW_DB_PASSWORD', 'KEYCLOAK_DB_PASSWORD')},
                                 'LOCAL_DB_PORT': config['LOCAL_DB_PORT']})
    write_env(RUNTIME / 'api-overrides.env', api_overrides(creds))
    write_env(RUNTIME / 'airflow.env', airflow_settings(creds))
    write_env(RUNTIME / 'monitoring.env', monitoring_settings())
    write_private(RUNTIME / 'kind.json', json.dumps(kind_config(config), indent=2) + '\n')
    return creds
