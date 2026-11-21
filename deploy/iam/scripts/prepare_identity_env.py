#!/usr/bin/env python3
"""사내 운영 입력을 배포에 쓰는 앱 env와 Make 인자로 변환합니다."""

import argparse
import fcntl
import os
from pathlib import Path
import re
import stat
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'deploy/shared/scripts'))
from catalog import inputs, read_catalog  # noqa: E402
from image_registry import read_account  # noqa: E402
from runtime import is_placeholder  # noqa: E402

OIDC_KEYS = ('CORP_OIDC_CLIENT_ID', 'CORP_OIDC_CLIENT_SECRET')
KEYCLOAK_OVERRIDES = ('postgres-password', 'bootstrap-admin-username', 'bootstrap-admin-password',
                      'CORP_OIDC_DISCOVERY_URL', 'CORP_OIDC_CLIENT_AUTH_METHOD', 'keycloak-public-url')
IAM_OVERRIDES = ('IAM_PUBLIC_URL', 'KEYCLOAK_TARGET_REALM', 'IAM_STORAGE_NODE', 'IAM_DATA_HOST_PATH')
ADMIN_KEY = 'IAM_PLATFORM_ADMIN_USERNAMES'
APP_OVERRIDES = {
    'HEADLAMP_ENV': ('headlamp', 'headlamp.env', {
        'HEADLAMP_HOST': 'HEADLAMP_HOST',
        'HEADLAMP_IMAGE_PULL_SECRET': 'IMAGE_PULL_SECRET',
        'HEADLAMP_ADMINS': 'HEADLAMP_ADMINS',
        'HEADLAMP_OIDC_CLIENT_ID': 'HEADLAMP_OIDC_CLIENT_ID',
        'HEADLAMP_OIDC_ISSUER_URL': 'HEADLAMP_OIDC_ISSUER_URL',
    }),
    'AIRFLOW_ENV': ('airflow', 'airflow.env', {
        'AIRFLOW_NODE_NAME': 'NODE_NAME',
        'AIRFLOW_IMAGE_PULL_SECRET': 'IMAGE_PULL_SECRET',
        'AIRFLOW_POSTGRES_HOST': 'POSTGRES_HOST',
        'AIRFLOW_POSTGRES_USER': 'POSTGRES_USER',
        'AIRFLOW_POSTGRES_DB': 'POSTGRES_DB',
        'AIRFLOW_POSTGRES_PASSWORD': 'POSTGRES_PASSWORD',
        'AIRFLOW_POSTGRES_MODE': 'POSTGRES_MODE',
        'AIRFLOW_POSTGRES_PORT': 'POSTGRES_PORT',
        'AIRFLOW_POSTGRES_HOST_PATH': 'POSTGRES_HOST_PATH',
        'AIRFLOW_LOGS_HOST_PATH': 'LOGS_HOST_PATH',
        'AIRFLOW_DAGS_HOST_PATH': 'DAGS_HOST_PATH',
        'AIRFLOW_ODBC_HOST_PATH': 'ODBC_HOST_PATH',
        'AIRFLOW_ODBC_SECRET_NAME': 'ODBC_SECRET_NAME',
        'AIRFLOW_ADMIN_USERNAME': 'AIRFLOW_ADMIN_USERNAME',
        'AIRFLOW_ADMIN_EMAIL': 'AIRFLOW_ADMIN_EMAIL',
        'AIRFLOW_ADMIN_PASSWORD': 'AIRFLOW_ADMIN_PASSWORD',
        'AIRFLOW_FERNET_KEY': 'AIRFLOW_FERNET_KEY',
        'AIRFLOW_WEBSERVER_SECRET_KEY': 'AIRFLOW_WEBSERVER_SECRET_KEY',
        'AIRFLOW_WEBSERVER_BASE_URL': 'AIRFLOW_WEBSERVER_BASE_URL',
        'AIRFLOW_AUTH_MODE': 'AIRFLOW_AUTH_MODE',
        'AIRFLOW_OIDC_ISSUER': 'AIRFLOW_OIDC_ISSUER',
        'AIRFLOW_OIDC_BACKCHANNEL_BASE_URL': 'AIRFLOW_OIDC_BACKCHANNEL_BASE_URL',
        'AIRFLOW_OIDC_CLIENT_ID': 'AIRFLOW_OIDC_CLIENT_ID',
        'AIRFLOW_OIDC_CLIENT_SECRET': 'AIRFLOW_OIDC_CLIENT_SECRET',
        'AIRFLOW_TRIGGER_TOKEN': 'AIRFLOW_TRIGGER_TOKEN',
        'AIRFLOW_API_BASE_URL': 'AIRFLOW_API_BASE_URL',
        'AIRFLOW_KNOX_MESSENGER_API_BASE_URL': 'KNOX_MESSENGER_API_BASE_URL',
        'AIRFLOW_KNOX_MESSENGER_AUTHORIZATION': 'KNOX_MESSENGER_AUTHORIZATION',
        'AIRFLOW_KNOX_MESSENGER_SYSTEM_ID': 'KNOX_MESSENGER_SYSTEM_ID',
        'AIRFLOW_FAILURE_ALERT_KNOX_IDS': 'AIRFLOW_FAILURE_ALERT_KNOX_IDS',
        'AIRFLOW_MAIL_API_URL': 'MAIL_API_URL',
        'AIRFLOW_MAIL_API_KEY': 'MAIL_API_KEY',
        'AIRFLOW_MAIL_API_SYSTEM_ID': 'MAIL_API_SYSTEM_ID',
        'AIRFLOW_MAIL_API_KNOX_ID': 'MAIL_API_KNOX_ID',
        'AIRFLOW_FAILURE_ALERT_EMAIL_FROM': 'AIRFLOW_FAILURE_ALERT_EMAIL_FROM',
        'AIRFLOW_FAILURE_ALERT_EMAIL_TO': 'AIRFLOW_FAILURE_ALERT_EMAIL_TO',
    }),
    'PROD_API_ENV_FILE': ('portal', 'portal-api.env', {
        'PORTAL_OIDC_CLIENT_ID': 'OIDC_CLIENT_ID',
        'PORTAL_OIDC_CLIENT_SECRET': 'OIDC_CLIENT_SECRET',
        'PORTAL_OIDC_ISSUER': 'OIDC_ISSUER',
        'PORTAL_OIDC_AUTH_URL': 'OIDC_AUTH_URL',
        'PORTAL_OIDC_TOKEN_URL': 'OIDC_TOKEN_URL',
        'PORTAL_OIDC_JWKS_URL': 'OIDC_JWKS_URL',
        'PORTAL_OIDC_LOGOUT_URL': 'OIDC_LOGOUT_URL',
        'PORTAL_OIDC_REDIRECT_URI': 'OIDC_REDIRECT_URI',
        **{key: key for key in (
            'DJANGO_DB_HOST', 'DJANGO_DB_PORT', 'DJANGO_DB_NAME', 'DJANGO_DB_USER', 'DJANGO_DB_PASSWORD',
            'DJANGO_SECRET_KEY', 'DJANGO_SUPERUSER_SABUN', 'DJANGO_SUPERUSER_USERNAME',
            'DJANGO_SUPERUSER_EMAIL', 'DJANGO_SUPERUSER_PASSWORD', 'MINIO_ACCESS_KEY', 'MINIO_SECRET_KEY',
            'FRONTEND_BASE_URL', 'PUBLIC_API_BASE_URL', 'DJANGO_ALLOWED_HOSTS',
            'MINIO_ENDPOINT', 'MINIO_BUCKET', 'AIRFLOW_BASE_URL', 'AIRFLOW_PUBLIC_BASE_URL',
            'AIRFLOW_USERNAME', 'AIRFLOW_PASSWORD', 'AIRFLOW_TRIGGER_TOKEN',
            'MAIL_API_URL', 'MAIL_API_KEY', 'MAIL_API_SYSTEM_ID', 'MAIL_API_KNOX_ID',
            'KNOX_MESSENGER_API_BASE_URL', 'KNOX_MESSENGER_AUTHORIZATION', 'KNOX_MESSENGER_SYSTEM_ID',
            'OPENWEBUI_URL', 'OPENWEBUI_MODEL', 'OPENWEBUI_API_TOKEN', 'OPENWEBUI_COMMON_HEADERS',
            'RAG_SEARCH_URL', 'RAG_INSERT_URL', 'RAG_DELETE_URL', 'RAG_INDEX_INFO_URL', 'RAG_HEADERS',
            'RAG_INDEX_LIST', 'RAG_INDEX_DEFAULT', 'RAG_INDEX_EMAILS', 'RAG_PERMISSION_GROUPS', 'RAG_PUBLIC_GROUP',
            'L3_SPIDER_MAIL_SENDER', 'L3_SPIDER_MAIL_TARGET_URL', 'EMAIL_POP3_HOST', 'EMAIL_POP3_PORT',
            'EMAIL_POP3_USERNAME', 'EMAIL_POP3_PASSWORD', 'EMAIL_OCR_INTERNAL_TOKEN',
            'DRONE_SOP_POP3_HOST', 'DRONE_SOP_POP3_PORT', 'DRONE_SOP_POP3_USERNAME', 'DRONE_SOP_POP3_PASSWORD',
            'DRONE_SOP_POP3_SUBJECT', 'DRONE_MAIL_SENDER', 'DRONE_JIRA_BASE_URL', 'DRONE_JIRA_USER',
            'DRONE_JIRA_TOKEN', 'DRONE_CTTTM_BASE_URL', 'RACB_REPORT_BASE_URL',
        )},
    }),
    'PROD_WEB_ENV_FILE': ('portal', 'portal-web.env', {
        **{key: key for key in (
            'VITE_MINIO_ENDPOINT', 'VITE_PORTAL_PMX_URL', 'VITE_PORTAL_MOSAIC_URL', 'VITE_PORTAL_CONFLUENCE_URL',
        )},
    }),
    'MINIO_ENV': ('minio', 'minio.env', {
        'MINIO_NODE_NAME': 'NODE_NAME',
        'MINIO_IMAGE_PULL_SECRET': 'IMAGE_PULL_SECRET',
        'MINIO_STORAGE_CLASS_NAME': 'STORAGE_CLASS_NAME',
        'MINIO_VOLUME_NAME': 'VOLUME_NAME',
        'MINIO_STORAGE_SIZE': 'STORAGE_SIZE',
        'MINIO_DATA_HOST_PATH': 'MINIO_DATA_HOST_PATH',
        'MINIO_ROOT_USER': 'MINIO_ROOT_USER',
        'MINIO_ROOT_PASSWORD': 'MINIO_ROOT_PASSWORD',
        'MINIO_BUCKETS': 'MINIO_BUCKETS',
        'MINIO_API_HOST': 'MINIO_API_HOST',
        'MINIO_CONSOLE_HOST': 'MINIO_CONSOLE_HOST',
        'MINIO_BROWSER_REDIRECT_URL': 'MINIO_BROWSER_REDIRECT_URL',
    }),
    'REGISTRY_ENV': ('registry', 'registry.env', {
        'REGISTRY_HOST': 'REGISTRY_HOST',
        'REGISTRY_IMAGE_PULL_SECRET': 'IMAGE_PULL_SECRET',
        'REGISTRY_NODE_NAME': 'NODE_NAME',
        'REGISTRY_DATA_HOST_PATH': 'DATA_HOST_PATH',
        'REGISTRY_STORAGE_SIZE': 'STORAGE_SIZE',
    }),
    'MONITORING_ENV': ('monitoring', 'monitoring.env', {
        'MONITORING_NODE_NAME': 'NODE_NAME',
        'MONITORING_IMAGE_PULL_SECRET': 'IMAGE_PULL_SECRET',
        'MONITORING_DATA_HOST_PATH': 'DATA_HOST_PATH',
        'GRAFANA_HOST': 'GRAFANA_HOST',
        'GRAFANA_SSO_ENABLED': 'GRAFANA_SSO_ENABLED',
        'KEYCLOAK_TARGET_REALM': 'GRAFANA_OIDC_REALM',
        'PROMETHEUS_HOST': 'PROMETHEUS_HOST',
        'ALERTMANAGER_HOST': 'ALERTMANAGER_HOST',
    }),
    'FTP_ENV': ('ftp', 'ftp.env', {
        'FTP_IMAGE': 'FTP_IMAGE',
        'FTP_IMAGE_PULL_SECRET': 'IMAGE_PULL_SECRET',
        'FTP_ALLOW_CONTROL_PLANE': 'FTP_ALLOW_CONTROL_PLANE',
    }),
}
FILE_KEYS = ('KEYCLOAK_SDWTS_CSV', 'KEYCLOAK_USERS_CSV', 'KEYCLOAK_CA_FILE', 'KEYCLOAK_ADMIN_CA_BUNDLE',
             'HEADLAMP_OIDC_CA_FILE', 'AIRFLOW_OIDC_CA_FILE',
             'HEADLAMP_CHART_FILE', 'AIRFLOW_CHART_FILE', 'MONITORING_CHART_FILE')
MAKE_KEYS = ('KUBE_CONTEXT', 'FTP_NODES', 'VIP_BACKENDS', 'AIRFLOW_TLS_SOURCE')
ACCOUNT_FILES = {
    'REGISTRY_PUSH_ENV': ('registry-push.env', {'REGISTRY_USER': 'REGISTRY_USER', 'REGISTRY_PASSWORD': 'REGISTRY_PASSWORD'}),
    'MONITORING_GRAFANA_ENV': ('grafana-initial.env', {'GRAFANA_ADMIN_USER': 'admin-user', 'GRAFANA_ADMIN_PASSWORD': 'admin-password'}),
    'FTP_CREDENTIAL_FILE': ('ftp-account.env', {'FTP_USER': 'FTP_USER', 'FTP_PASS': 'FTP_PASS'}),
}
INPUT_KEYS = {*OIDC_KEYS, *KEYCLOAK_OVERRIDES, *IAM_OVERRIDES, ADMIN_KEY, *FILE_KEYS, *MAKE_KEYS,
              *(key for _, _, overrides in APP_OVERRIDES.values() for key in overrides),
              *(key for _, keys in ACCOUNT_FILES.values() for key in keys)}
ENV_KEY = re.compile(r'[A-Za-z_][A-Za-z0-9_-]*')


def read_env(path, *, private=False):
    """env를 실행하지 않고 읽으며 중복이나 형식 오류에는 값이 아닌 줄 번호를 표시합니다."""
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or (private and (info.st_uid != os.geteuid() or info.st_mode & 0o077)):
        raise ValueError(f'{path.name}은 실행 계정 소유의 일반 파일이며 소유자 전용(예: 0600)이어야 합니다.')
    values = {}
    try:
        lines = path.read_text().splitlines()
    except UnicodeDecodeError:
        raise ValueError(f'{path.name}의 UTF-8 형식을 확인하세요.') from None
    for number, line in enumerate(lines, 1):
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        key, separator, value = line.partition('=')
        if not separator or not ENV_KEY.fullmatch(key) or key in values or '\0' in value:
            raise ValueError(f'{path.name} {number}행의 KEY=값 형식 또는 중복 키를 확인하세요.')
        values[key] = value
    return values


def prepare(identity, keycloak_base, iam_base):
    """운영 입력으로 배포용 env와 기존 배포 명령에 전달할 인자를 준비합니다."""
    identity = identity.resolve()
    checkout_input = ROOT / 'identity.env'
    if identity.is_relative_to(ROOT) and identity != checkout_input:
        raise ValueError('checkout 안의 운영 입력은 프로젝트 루트의 identity.env를 사용하세요.')
    selected = read_env(identity, private=identity != checkout_input)
    if set(selected) - INPUT_KEYS:
        raise ValueError('저장소 루트 identity.env에서 지원하는 키를 확인하세요.')
    oidc = {key: selected.get(key, '') for key in OIDC_KEYS}
    if any(value.strip() for value in oidc.values()):
        for key, value in oidc.items():
            if not value.strip() or is_placeholder(value):
                raise ValueError(f'{identity.name}의 {key}에 발급받은 값을 입력하세요.')
    else:
        oidc.clear()

    output = identity.with_name(identity.name + '.generated')
    result, arguments = {}, {}

    def merge_base(variable, name, base, changes):
        base = Path(base).resolve()
        if base == identity or base.is_relative_to(output):
            raise ValueError('기존 앱 env를 원본으로 사용하세요. identity.env와 생성본은 원본으로 쓸 수 없습니다.')
        values = read_env(base)
        # 값이 같은 경우 원본 경로를 유지해 배포 기록에서 내용 차이가 생기지 않게 합니다.
        if any(values.get(key) != value for key, value in changes.items()):
            result[name] = {**values, **changes}
            arguments[variable] = output / name
        else:
            arguments[variable] = base

    keycloak_changes = {**oidc, **{key: selected[key] for key in KEYCLOAK_OVERRIDES if selected.get(key, '').strip()}}
    iam_changes = {key: selected[key] for key in IAM_OVERRIDES if selected.get(key, '').strip()}
    if ADMIN_KEY in selected:
        iam_changes[ADMIN_KEY] = selected[ADMIN_KEY]

    merge_base('KEYCLOAK_ENV', 'keycloak.env', keycloak_base, keycloak_changes)
    merge_base('IAM_ENV', 'iam.env', iam_base, iam_changes)
    catalog = read_catalog()['apps']
    for variable, (app, name, overrides) in APP_OVERRIDES.items():
        changes = {target: selected[key] for key, target in overrides.items() if selected.get(key, '').strip()}
        if changes:
            merge_base(variable, name, inputs(catalog[app])[variable], changes)

    for key in FILE_KEYS:
        value = selected.get(key, '').strip()
        if value:
            path = (identity.parent / value).resolve()
            if not path.is_file():
                raise ValueError(f'{key}의 파일 경로를 확인하세요.')
            arguments[key] = path
    if 'KEYCLOAK_USERS_CSV' in arguments and 'KEYCLOAK_SDWTS_CSV' not in arguments:
        raise ValueError('KEYCLOAK_USERS_CSV를 쓰려면 KEYCLOAK_SDWTS_CSV도 지정하세요.')
    for key in MAKE_KEYS:
        value = selected.get(key, '').strip()
        if value:
            arguments[key] = value

    for variable, (name, overrides) in ACCOUNT_FILES.items():
        account = {target: selected[key] for key, target in overrides.items() if selected.get(key, '').strip()}
        if account:
            if len(account) != len(overrides) or any(is_placeholder(value) for value in account.values()):
                raise ValueError(f'{"·".join(overrides)}를 모두 입력하세요.')
            result[name] = account
            arguments[variable] = output / name

    output.mkdir(mode=0o700, exist_ok=True)
    metadata = output.lstat()
    if (not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.geteuid()
            or stat.S_IMODE(metadata.st_mode) != 0o700):
        raise ValueError('생성 위치는 실행 계정 소유의 권한 0700 디렉터리여야 합니다.')
    directory_fd = os.open(output, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        fcntl.flock(directory_fd, fcntl.LOCK_EX)
        with tempfile.TemporaryDirectory(dir=output) as directory:
            staging = Path(directory)
            for name, values in result.items():
                path = staging / name
                path.touch(mode=0o600)
                path.write_text(''.join(f'{key}={value}\n' for key, value in values.items()))
            if 'REGISTRY_PUSH_ENV' in arguments:
                read_account(staging / ACCOUNT_FILES['REGISTRY_PUSH_ENV'][0], is_placeholder=is_placeholder)
            for name in result:
                (staging / name).replace(output / name)
    finally:
        os.close(directory_fd)
    return arguments


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--identity-env', required=True, type=Path)
    parser.add_argument('--keycloak-base', required=True, type=Path)
    parser.add_argument('--iam-base', required=True, type=Path)
    args = parser.parse_args()
    try:
        arguments = prepare(args.identity_env, args.keycloak_base, args.iam_base)
    except (OSError, ValueError) as error:
        parser.exit(1, f'사내 운영 입력 준비 실패: {error}\n')
    for key, value in arguments.items():
        print(f'{key}={value}')


if __name__ == '__main__':
    main()
