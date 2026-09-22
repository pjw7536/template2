#!/usr/bin/env python3
"""Keycloak 전용 입력 검사·최초 Secret 등록·Kubernetes 배포. DB는 삭제하지 않는다."""

import argparse
import base64
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'deploy/keycloak'
KEYS = ('postgres-password', 'bootstrap-admin-username', 'bootstrap-admin-password', 'keycloak-public-url')
spec = importlib.util.spec_from_file_location('server_up', ROOT / 'deploy/shared/scripts/server-up.py')
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)
routing = server.module('routing', ROOT / 'deploy/shared/ingress/routing.py')


def run(args, data=None, sensitive=False):
    """비밀 입력과 kubectl의 오류 응답을 화면에 노출하지 않는다."""
    result = subprocess.run(list(map(str, args)), input=data, text=True, capture_output=True)
    if result.returncode:
        raise ValueError('비밀 입력 처리 실패. env·인증서·클러스터 권한을 확인하세요.' if sensitive else result.stderr.strip())
    return result.stdout


def read_settings(path):
    """기존 env 검증기를 사용하고 값을 shell로 실행하지 않는다."""
    run(['bash', ROOT / 'deploy/shared/scripts/check-env.sh', 'keycloak', 'prod', 'server', path], sensitive=True)
    values = {}
    for line in Path(path).read_text().splitlines():
        if line.strip() and not line.lstrip().startswith('#'):
            key, _, value = line.partition('=')
            values[key] = value
    return {key: values[key] for key in KEYS}


def secret_if_missing(kube, name, values, secret_type='Opaque'):
    """기존 Secret 불일치는 중단하고, 없을 때만 생성할 입력을 반환한다."""
    current = run([*kube, '-n', 'etch-sso', 'get', 'secret', name, '--ignore-not-found', '-o', 'json'], sensitive=True)
    encoded = {key: base64.b64encode(value.encode()).decode() for key, value in values.items()}
    if current.strip():
        existing = json.loads(current)
        if existing.get('type', 'Opaque') != secret_type or any(existing.get('data', {}).get(key) != value for key, value in encoded.items()):
            raise ValueError(f'{name}: 기존 Secret과 입력이 다릅니다. 기존 값에 맞추거나 별도 Secret 갱신 절차를 먼저 수행하세요.')
        return None
    return {'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': name, 'namespace': 'etch-sso'},
            'type': secret_type, 'data': encoded}


def start(context, env, certs, vip_backends=None, check_only=False):
    """입력을 먼저 검증하고 Keycloak 및 소유 ingress만 재적용한다."""
    if not context.strip():
        raise ValueError('--context를 명시하세요.')
    kube = ['kubectl', '--context', context]
    settings = read_settings(env)
    url = urlsplit(settings['keycloak-public-url'])
    if url.scheme != 'https' or not url.hostname or url.path or url.query or url.fragment:
        raise ValueError('keycloak-public-url은 경로 없는 HTTPS URL이어야 합니다.')
    cert = Path(certs) / 'keycloak-fullchain.crt'
    key = Path(certs) / 'keycloak.key'
    checked = run(['openssl', 'x509', '-in', cert, '-noout', '-checkhost', url.hostname], sensitive=True)
    if 'does match certificate' not in checked:
        raise ValueError('인증서 도메인과 keycloak-public-url이 다릅니다.')
    run(['openssl', 'x509', '-in', cert, '-noout', '-checkend', '0'], sensitive=True)
    public = run(['openssl', 'x509', '-in', cert, '-pubkey', '-noout'], sensitive=True)
    private_public = run(['openssl', 'pkey', '-in', key, '-passin', 'pass:', '-pubout'], sensitive=True)
    if public.strip() != private_public.strip():
        raise ValueError('인증서와 개인키가 일치하지 않습니다.')
    desired = server.render_json(run, kube, BASE / 'k8s')
    hosts = [rule['host'] for item in desired if item['kind'] == 'Ingress' for rule in item['spec'].get('rules', [])]
    if url.hostname not in hosts:
        raise ValueError('공개 URL과 Keycloak Ingress 도메인이 다릅니다. 배포 원본을 먼저 맞추세요.')
    pending = [secret_if_missing(kube, 'keycloak-runtime', settings),
               secret_if_missing(kube, 'keycloak-tls', {'tls.crt': cert.read_text(), 'tls.key': key.read_text()}, 'kubernetes.io/tls')]
    # 기존 DB가 있는 환경에서 Secret만 사라진 경우 임의 비밀번호로 복구하지 않는다.
    if pending[0]:
        pvc = run([*kube, '-n', 'etch-sso', 'get', 'pvc', 'keycloak-postgres-data', '--ignore-not-found', '-o', 'name'])
        if pvc.strip():
            raise ValueError('기존 PVC가 있으나 keycloak-runtime이 없습니다. 실제 DB credential에 맞춰 Secret을 먼저 복원하세요.')
    original = routing.controller(desired)
    current_json = run([*kube, '-n', 'etch-sso', 'get', 'deployment', 'traefik', '--ignore-not-found', '-o', 'json'])
    current = json.loads(current_json) if current_json.strip() else original
    updated = routing.preserve_namespaces(original, current, 'etch-sso')
    ips = routing.vip_backend_ips(vip_backends, current)
    nodes = json.loads(run([*kube, 'get', 'nodes', '-o', 'json']))['items']
    hostname = original['spec']['template']['spec'].get('nodeSelector', {}).get('kubernetes.io/hostname')
    matches = [node for node in nodes if node['metadata'].get('labels', {}).get('kubernetes.io/hostname') == hostname]
    if len(matches) != 1 or not any(c.get('type') == 'Ready' and c.get('status') == 'True' for c in matches[0].get('status', {}).get('conditions', [])):
        raise ValueError('Keycloak 원본에 지정한 worker가 없거나 Ready가 아닙니다.')
    if ips:
        pods = json.loads(run([*kube, 'get', 'pods', '-A', '-o', 'json']))['items']
        updated = routing.place_vip_backends(updated, current, ips, nodes, pods)
    elif current['spec']['template']['spec'].get('nodeSelector', {}) != original['spec']['template']['spec'].get('nodeSelector', {}) or current['spec'].get('replicas', 1) != 1:
        raise ValueError('기존 Traefik 배치와 원본이 다릅니다. 배치 설정을 먼저 확인하세요.')
    desired = [updated if item is original else item for item in desired]
    if check_only:
        print('Keycloak 입력·원본·기존 Secret·worker 검사 통과. 클러스터를 변경하지 않았습니다.')
        return
    run([*kube, 'apply', '-f', '-'], data=json.dumps({'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': 'etch-sso'}}))
    for secret in pending:
        if secret:
            # create만 사용해 검사 이후 다른 운영자가 만든 Secret도 덮어쓰지 않는다.
            run([*kube, 'create', '-f', '-'], data=json.dumps(secret), sensitive=True)
    run([*kube, 'apply', '-f', '-'], data=json.dumps({'apiVersion': 'v1', 'kind': 'List', 'items': desired}))
    for workload in ('statefulset/keycloak-postgres', 'deployment/keycloak', 'deployment/traefik'):
        run([*kube, '-n', 'etch-sso', 'rollout', 'status', workload, '--timeout=600s'])
    print('Keycloak 배포 완료: ' + settings['keycloak-public-url'])
    print('사내 OIDC 연결과 claim 등록은 별도 Job으로 실행하세요.')


def main():
    """앱 전용 파일 경로와 대상 클러스터를 명시적으로 받는다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context', required=True)
    parser.add_argument('--env', type=Path, default=BASE / 'env/prod.env')
    parser.add_argument('--certs', type=Path, default=BASE / 'certs')
    parser.add_argument('--vip-backends')
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    start(args.context, args.env, args.certs, args.vip_backends, args.check_only)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, StopIteration) as error:
        print(f'오류: {error}', file=sys.stderr)
        sys.exit(1)
