#!/usr/bin/env python3
"""명시한 클러스터와 Worker에 FTP를 검사하거나 배포한다."""

import argparse
import base64
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import sys

BASE = Path(__file__).resolve().parents[1]
LABEL = 'etch.io/ftp-enabled'
NAMESPACE = 'etch-ftp'


def run(args, *, data=None, sensitive=False):
    """Secret은 표준입력으로 전달하며 민감한 명령의 오류 본문을 숨긴다."""
    result = subprocess.run(list(map(str, args)), input=data, text=True, capture_output=True)
    if result.returncode:
        detail = 'Secret 처리 실패: context·권한·기존 Secret을 확인하세요.' if sensitive else result.stderr.strip()
        raise ValueError(detail or '명령 실행 실패')
    return result.stdout


def read_credentials(path):
    """두 개의 credential 키만 읽고 셸 치환이나 따옴표 해석을 하지 않는다."""
    if not path.is_file() or path.stat().st_mode & 0o077:
        raise ValueError('FTP_CREDENTIAL_FILE은 소유자만 접근 가능한 파일이어야 합니다. chmod 600을 적용하세요.')
    values = {}
    for line in path.read_text().split('\n'):
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        key, separator, value = line.partition('=')
        if not separator or key not in ('FTP_USER', 'FTP_PASS') or key in values:
            raise ValueError('계정 파일에는 FTP_USER와 FTP_PASS를 각각 한 번만 KEY=value로 기록하세요.')
        values[key] = value
    if not re.fullmatch(r'[a-zA-Z0-9_-]+', values.get('FTP_USER', '')):
        raise ValueError('FTP_USER는 영문·숫자·밑줄·하이픈만 허용합니다.')
    password = values.get('FTP_PASS', '')
    if not password or any(char in password for char in ('\r', '\n', '\\', '\x00')):
        raise ValueError('FTP_PASS는 필수이며 줄바꿈·역슬래시·NUL을 허용하지 않습니다.')
    return values


def check_nodes(nodes, names):
    """기존 배치 범위를 빠뜨리지 않고 실행 가능한 Linux Worker만 선택한다."""
    by_name = {node['metadata']['name']: node for node in nodes}
    labeled = {name for name, node in by_name.items()
               if node['metadata'].get('labels', {}).get(LABEL) == 'true'}
    extra = labeled - set(names)
    if extra:
        raise ValueError('기존 FTP 노드도 FTP_NODES에 포함하세요: ' + ', '.join(sorted(extra)))
    for name in names:
        node = by_name.get(name)
        if not node:
            raise ValueError('존재하지 않는 노드: ' + name)
        labels = node['metadata'].get('labels', {})
        spec = node.get('spec', {})
        ready = any(item.get('type') == 'Ready' and item.get('status') == 'True'
                    for item in node.get('status', {}).get('conditions', []))
        if labels.get('kubernetes.io/os') != 'linux' or any(
                key in labels for key in ('node-role.kubernetes.io/control-plane', 'node-role.kubernetes.io/master')):
            raise ValueError('Linux Worker를 선택하세요: ' + name)
        if not ready or spec.get('unschedulable') or any(
                item.get('effect') in ('NoSchedule', 'NoExecute') for item in spec.get('taints', [])):
            raise ValueError('Ready·cordon·taint 상태를 확인하세요: ' + name)
        addresses = [item['address'] for item in node.get('status', {}).get('addresses', [])
                     if item['type'] == 'InternalIP']
        if not addresses or ipaddress.ip_address(addresses[0]).version != 4:
            raise ValueError('IPv4 InternalIP가 필요합니다: ' + name)
        print(f'대상: {name} / {addresses[0]}:6380 / /data/data_movement')


def start(context, nodes, credential_file, check_only=False):
    """모든 입력을 검사한 뒤 기존 계정을 보존하면서 원본 스택을 적용한다."""
    if not context.strip() or not nodes.strip() or not credential_file:
        raise ValueError('KUBE_CONTEXT, FTP_NODES, FTP_CREDENTIAL_FILE을 모두 명시하세요.')
    names = nodes.split(',')
    if any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', name) for name in names) or len(names) != len(set(names)):
        raise ValueError('FTP_NODES는 공백·중복 없이 쉼표로 구분한 노드 이름 목록이어야 합니다.')
    credentials = read_credentials(Path(credential_file))
    kube = ['kubectl', '--context', context]
    source = run(['kubectl', 'kustomize', BASE / 'k8s'])
    all_nodes = json.loads(run([*kube, 'get', 'nodes', '-o', 'json']))['items']
    check_nodes(all_nodes, names)
    current = run([*kube, '-n', NAMESPACE, 'get', 'secret', 'ftp-credentials',
                   '--ignore-not-found', '-o', 'json'], sensitive=True)
    encoded = {key: base64.b64encode(value.encode()).decode() for key, value in credentials.items()}
    if current.strip():
        existing = json.loads(current)
        if any(existing.get('data', {}).get(key) != value for key, value in encoded.items()):
            raise ValueError('기존 FTP Secret과 계정 파일이 다릅니다. 기존 계정 파일을 사용하세요. 자동 변경하지 않습니다.')
    print('context: ' + context)
    if check_only:
        print('입력·노드·기존 Secret·원본 렌더 검사 통과. 디스크·포트·FTP 전송은 별도 확인하세요.')
        return
    namespace = {'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': NAMESPACE}}
    run([*kube, 'apply', '-f', '-'], data=json.dumps(namespace))
    if not current.strip():
        secret = {'apiVersion': 'v1', 'kind': 'Secret', 'type': 'Opaque',
                  'metadata': {'name': 'ftp-credentials', 'namespace': NAMESPACE}, 'data': encoded}
        # 검사 이후 다른 운영자가 만든 Secret도 덮어쓰지 않는다.
        run([*kube, 'create', '-f', '-'], data=json.dumps(secret), sensitive=True)
    run([*kube, 'label', 'node', *names, LABEL + '=true', '--overwrite'])
    run([*kube, 'apply', '-f', '-'], data=source)
    run([*kube, '-n', NAMESPACE, 'rollout', 'status', 'daemonset/ftp', '--timeout=300s'])
    print(run([*kube, '-n', NAMESPACE, 'get', 'pods', '-l', 'app=ftp', '-o', 'wide']))
    print('FTP 배포 완료. 각 노드 IP의 6380 포트에서 업로드·다운로드를 확인하세요.')


def main():
    """Make가 전달한 환경변수 또는 직접 지정한 옵션을 읽는다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context', default=os.environ.get('KUBE_CONTEXT', ''))
    parser.add_argument('--nodes', default=os.environ.get('FTP_NODES', ''))
    parser.add_argument('--credentials', default=os.environ.get('FTP_CREDENTIAL_FILE', ''))
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    start(args.context, args.nodes, args.credentials, args.check_only)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError) as error:
        print(f'오류: {error}', file=sys.stderr)
        sys.exit(1)
