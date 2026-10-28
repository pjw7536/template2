#!/usr/bin/env python3
"""공용 Traefik 인증서를 검증·등록하며 앱별 Secret 복제를 없앤다."""

import argparse
import base64
import copy
import json
from pathlib import Path
import re
import subprocess
import sys

NAMESPACE = 'etch-sso'
SECRET = 'traefik-tls'
DIRECTORY = '/etc/traefik/dynamic'


def run(args, data=None):
    """인증서와 개인키는 stdin으로만 전달하고 실패 응답의 민감값을 숨긴다."""
    result = subprocess.run(list(map(str, args)), input=data, text=True, capture_output=True)
    if result.returncode:
        raise ValueError('공용 TLS 처리 실패. 인증서·개인키·클러스터 권한 또는 동시 변경을 확인하세요.')
    return result.stdout


def validate(host, certificate, private_key):
    """DNS 호스트, 만료 여부, 인증서와 개인키의 일치를 확인한다."""
    label = r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?'
    if len(host) > 253 or not re.fullmatch(rf'{label}(?:\.{label})+', host):
        raise ValueError('TLS_HOST에는 scheme·경로 없는 DNS 이름을 입력하세요.')
    result = run(['openssl', 'x509', '-noout', '-checkhost', host], data=certificate)
    if 'does match certificate' not in result:
        raise ValueError('인증서와 공개 도메인이 다릅니다.')
    run(['openssl', 'x509', '-noout', '-checkend', '0'], data=certificate)
    public = run(['openssl', 'x509', '-pubkey', '-noout'], data=certificate)
    private_public = run(['openssl', 'pkey', '-passin', 'pass:', '-pubout'], data=private_key)
    if not public.strip() or public.strip() != private_public.strip():
        raise ValueError('인증서와 개인키가 일치하지 않습니다.')


def configuration(data):
    """동일 Secret의 모든 PEM 쌍을 SNI 인증서 목록으로 만든다."""
    hosts = sorted(key[:-4] for key in data if key.endswith('.crt'))
    expected = {f'{host}.{suffix}' for host in hosts for suffix in ('crt', 'key')}
    if not hosts or set(data) - {'tls.yaml'} != expected:
        raise ValueError('공용 TLS Secret의 인증서·개인키 쌍을 확인하세요.')
    return json.dumps({'tls': {'certificates': [
        {'certFile': f'{DIRECTORY}/{host}.crt', 'keyFile': f'{DIRECTORY}/{host}.key'}
        for host in hosts]}}, sort_keys=True)


def decode(value):
    """잘못된 Secret 인코딩에서도 원문을 노출하지 않는다."""
    try:
        return base64.b64decode(value, validate=True).decode()
    except (ValueError, UnicodeError):
        raise ValueError('공용 TLS Secret의 PEM 인코딩을 확인하세요.') from None


def prepare(kube, host, cert=None, key=None, source=None):
    """공용 인증서를 검사하거나 명시한 원본을 병합한다. 클러스터를 변경하지 않는다."""
    raw = run([*kube, '-n', NAMESPACE, 'get', 'secret', SECRET, '--ignore-not-found', '-o', 'json'])
    current = json.loads(raw) if raw.strip() else None
    if current and current.get('type', 'Opaque') != 'Opaque':
        raise ValueError('공용 traefik-tls Secret은 Opaque 타입이어야 합니다.')
    if source and (cert or key) or bool(cert) != bool(key):
        raise ValueError('TLS_CERT_FILE·TLS_KEY_FILE 쌍 또는 TLS_SOURCE 하나를 지정하세요.')
    data = copy.deepcopy(current.get('data', {})) if current else {}
    importing = bool(source or cert)
    if source:
        parts = source.split('/')
        if len(parts) != 2 or not all(parts):
            raise ValueError('TLS_SOURCE는 namespace/secret 형식이어야 합니다.')
        original = json.loads(run([*kube, '-n', parts[0], 'get', 'secret', parts[1], '-o', 'json']))
        if original.get('type') != 'kubernetes.io/tls' or not all(original.get('data', {}).get(k) for k in ('tls.crt', 'tls.key')):
            raise ValueError('원본 TLS Secret에 tls.crt·tls.key가 필요합니다.')
        certificate, private_key = (decode(original['data'][k]) for k in ('tls.crt', 'tls.key'))
    elif cert:
        certificate, private_key = Path(cert).read_text(), Path(key).read_text()
    else:
        if not all(data.get(f'{host}.{suffix}') for suffix in ('crt', 'key')):
            raise ValueError(f'{host}: 공용 TLS 인증서가 없습니다. make ingress-tls-up으로 먼저 등록하세요.')
        certificate, private_key = (decode(data[f'{host}.{suffix}']) for suffix in ('crt', 'key'))
    validate(host, certificate, private_key)
    if importing:
        for suffix, value in (('crt', certificate), ('key', private_key)):
            data[f'{host}.{suffix}'] = base64.b64encode(value.encode()).decode()
    config = configuration(data)
    if not importing:
        if decode(data.get('tls.yaml', '')) != config:
            raise ValueError('공용 TLS 설정이 PEM 목록과 다릅니다. ingress-tls-up으로 다시 등록하세요.')
        return None
    data['tls.yaml'] = base64.b64encode(config.encode()).decode()
    if current and current.get('data') == data:
        return None
    secret = copy.deepcopy(current) if current else {
        'apiVersion': 'v1', 'kind': 'Secret', 'type': 'Opaque',
        'metadata': {'name': SECRET, 'namespace': NAMESPACE}}
    if current and not current.get('metadata', {}).get('resourceVersion'):
        raise ValueError('공용 TLS Secret에 동시 변경 검사용 resourceVersion이 없습니다.')
    secret['data'] = data
    return secret


def check_mount(current):
    """현재 Traefik이 공용 Secret을 file provider 경로로 읽는지 확인한다."""
    pod = current['spec']['template']['spec']
    container = next(item for item in pod['containers'] if item['name'] == 'traefik')
    mounts = {item['name'] for item in container.get('volumeMounts', [])
              if item.get('mountPath') == DIRECTORY and not item.get('subPath')}
    sources = [source for volume in pod.get('volumes', []) if volume['name'] in mounts
               for source in volume.get('projected', {}).get('sources', [])]
    if (f'--providers.file.directory={DIRECTORY}' not in container.get('args', [])
            or not any(source.get('secret', {}).get('name') == SECRET for source in sources)):
        raise ValueError('공용 TLS 마운트가 없습니다. make ingress-up을 먼저 실행하세요.')


def check(kube, host, current):
    """앱 배포 전에 공용 인증서와 controller 연결을 모두 검사한다."""
    prepare(kube, host)
    check_mount(current)


def save(kube, pending, restart=True):
    """최초 생성 또는 낙관적 잠금으로 갱신하고 선택적으로 인증서를 다시 읽는다."""
    if pending:
        operation = 'replace' if pending['metadata'].get('resourceVersion') else 'create'
        run([*kube, operation, '-f', '-'], data=json.dumps(pending))
    if restart:
        reload_controller(kube)


def reload_controller(kube):
    """Secret 볼륨의 갱신 감지에 의존하지 않고 기존 controller를 다시 시작한다."""
    # 동일 입력의 재시도도 이전 rollout 실패를 복구할 수 있도록 다시 읽는다.
    current = run([*kube, '-n', NAMESPACE, 'get', 'deployment', 'traefik', '--ignore-not-found', '-o', 'name'])
    if current.strip():
        run([*kube, '-n', NAMESPACE, 'rollout', 'restart', 'deployment/traefik'])
        run([*kube, '-n', NAMESPACE, 'rollout', 'status', 'deployment/traefik', '--timeout=600s'])


def main():
    """공용 등록은 앱 env 없이 명시한 context와 호스트만 사용한다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context', required=True)
    parser.add_argument('--host', required=True)
    parser.add_argument('--cert')
    parser.add_argument('--key')
    parser.add_argument('--source')
    args = parser.parse_args()
    if not args.context.strip() or not (args.cert or args.source):
        raise ValueError('KUBE_CONTEXT와 인증서 파일 쌍 또는 TLS_SOURCE를 지정하세요.')
    kube = ['kubectl', '--context', args.context]
    pending = prepare(kube, args.host, args.cert, args.key, args.source)
    namespace = run([*kube, 'get', 'namespace', NAMESPACE, '--ignore-not-found', '-o', 'name'])
    if not namespace.strip():
        run([*kube, 'create', 'namespace', NAMESPACE])
    save(kube, pending)
    print(f'공용 TLS 등록 완료: {args.host}. 인증서 원본 Secret과 앱 namespace는 변경하지 않았습니다.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, StopIteration) as error:
        print(f'오류: {error}', file=sys.stderr)
        sys.exit(1)
