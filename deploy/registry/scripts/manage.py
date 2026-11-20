#!/usr/bin/env python3
"""사내 이미지 저장소(Zot)를 다른 앱과 독립적으로 검사·렌더·배포한다."""

import argparse
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

BASE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('shared_runtime', BASE.parent / 'shared/scripts/runtime.py')
RUNTIME = importlib.util.module_from_spec(spec)
spec.loader.exec_module(RUNTIME)
spec = importlib.util.spec_from_file_location('registry_routing', BASE.parent / 'shared/ingress/routing.py')
routing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(routing)
tls = RUNTIME.module('shared_tls', BASE.parent / 'shared/ingress/tls.py')
host_dirs = RUNTIME.module('shared_host_dirs', BASE.parent / 'shared/scripts/host_dirs.py')
image_registry = RUNTIME.module('shared_image_registry', BASE.parent / 'shared/scripts/image_registry.py')

NAMESPACE = 'registry'
VOLUME = 'registry-data'
AUTH_SECRET = 'registry-htpasswd'
ENV_KEYS = frozenset(('NODE_NAME', 'REGISTRY_IMAGE', 'PREPARE_IMAGE', 'IMAGE_PULL_SECRET', 'REGISTRY_HOST',
                      'DATA_HOST_PATH', 'STORAGE_SIZE'))
# Zot 컨테이너의 실행 계정. 저장 폴더 소유자와 같아야 한다.
DATA_OWNER = (1000, 1000, '0750')
LABEL = r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?'


def require(condition, message):
    """설정 키와 복구 방법을 포함한 오류로 중단한다."""
    if not condition:
        raise ValueError(message)


def run(args, data=None):
    """셸 확장 없이 실행하고 실패하면 표준 오류를 보고한다."""
    result = subprocess.run(list(map(str, args)), input=data, capture_output=True, text=True)
    require(result.returncode == 0, result.stderr.strip() or f'{args[0]} 실행 실패')
    return result.stdout


def settings(path, example=False):
    """env를 실행하지 않고 키 계약·이름·경로·이미지 형식을 검사한다."""
    result = {}
    for line in Path(path).read_text().splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        key, separator, value = line.partition('=')
        require(separator and key in ENV_KEYS and key not in result, 'registry env 키 누락·중복·오타를 확인하세요.')
        result[key] = value
    require(result.keys() == ENV_KEYS, 'registry env 키가 설정 계약과 다릅니다.')
    for key, value in result.items():
        require(key == 'IMAGE_PULL_SECRET' or value, f'필수 설정 누락: {key}')
        require(not any(c.isspace() for c in value) and (example or not RUNTIME.is_placeholder(value)),
                f'실제 값 또는 형식 확인 필요: {key}')
    for key in ('NODE_NAME', 'IMAGE_PULL_SECRET'):
        require(not result[key] or (len(result[key]) <= 253 and re.fullmatch(rf'{LABEL}(?:\.{LABEL})*', result[key])),
                f'Kubernetes 이름 오류: {key}')
    require(len(result['REGISTRY_HOST']) <= 253 and re.fullmatch(rf'{LABEL}(?:\.{LABEL})+', result['REGISTRY_HOST']),
            'REGISTRY_HOST에는 포트·scheme 없는 DNS 이름이 필요합니다.')
    path = Path(result['DATA_HOST_PATH'])
    require(path.is_absolute() and len(path.parts) >= 3 and '..' not in path.parts and not result['DATA_HOST_PATH'].endswith('/'),
            'DATA_HOST_PATH에는 이미지 저장 전용 절대 디렉터리를 지정하세요.')
    require(re.fullmatch(r'[1-9][0-9]*(Gi|Ti)', result['STORAGE_SIZE']), 'STORAGE_SIZE에는 Gi 또는 Ti 용량이 필요합니다.')
    for key in ('REGISTRY_IMAGE', 'PREPARE_IMAGE'):
        image = result[key]
        require(re.fullmatch(r'[a-zA-Z0-9._:/@-]+', image) and
                (':' in image.rsplit('/', 1)[-1] or '@sha256:' in image) and not image.endswith(':latest'),
                f'{key}에는 고정 tag 또는 digest 이미지가 필요합니다.')
    return result


def push_account(path):
    """push 계정 파일에서 사용자와 비밀번호만 읽는다. 이미지 push 도구와 같은 해석기를 쓴다."""
    return image_registry.read_account(path, RUNTIME.is_placeholder)


def htpasswd_line(user, password):
    """Zot이 읽는 bcrypt htpasswd 한 줄을 만든다. htpasswd가 없으면 Python crypt를 사용한다."""
    if shutil.which('htpasswd'):
        return run(['htpasswd', '-niB', user], data=password + '\n').strip()
    try:
        import crypt
        hashed = crypt.crypt(password, crypt.mksalt(crypt.METHOD_BLOWFISH))
    except (ImportError, AttributeError, OSError):
        hashed = None
    require(hashed and hashed.startswith('$2'),
            'bcrypt htpasswd를 만들 수 없습니다. 관리 호스트에 apache2-utils(htpasswd)를 설치하세요.')
    return f'{user}:{hashed}'


def auth_secret(kube, push_env):
    """push 계정 Secret이 없을 때만 계정 파일로 만들 manifest를 반환한다. 기존 Secret은 바꾸지 않는다."""
    found = run([*kube, '-n', NAMESPACE, 'get', 'secret', AUTH_SECRET, '--ignore-not-found', '-o', 'name'])
    if found.strip():
        return None
    require(push_env and Path(push_env).is_file(),
            f'Secret {AUTH_SECRET}이 없습니다. REGISTRY_PUSH_ENV에 push 계정 파일을 지정하세요.')
    return {'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': AUTH_SECRET, 'namespace': NAMESPACE},
            'type': 'Opaque', 'stringData': {'htpasswd': htpasswd_line(*push_account(push_env)) + '\n'}}


def static_volume(values):
    """이미지 데이터를 지정 Worker에 고정하고 PVC 삭제 후에도 보존한다."""
    return {'apiVersion': 'v1', 'kind': 'PersistentVolume',
            'metadata': {'name': VOLUME, 'labels': {'app.kubernetes.io/name': 'registry'}},
            'spec': {'capacity': {'storage': values['STORAGE_SIZE']}, 'volumeMode': 'Filesystem',
                     'accessModes': ['ReadWriteOnce'], 'persistentVolumeReclaimPolicy': 'Retain',
                     'storageClassName': '', 'claimRef': {'namespace': NAMESPACE, 'name': VOLUME},
                     'local': {'path': values['DATA_HOST_PATH']},
                     'nodeAffinity': {'required': {'nodeSelectorTerms': [{'matchExpressions': [
                         {'key': 'kubernetes.io/hostname', 'operator': 'In', 'values': [values['NODE_NAME']]}]}]}}}}


def manifests(values):
    """공통 JSON 원본에 이미지·배치·용량·host 입력을 적용한다."""
    items = deepcopy(json.loads((BASE / 'k8s/stack.json').read_text())['items'])
    for item in items:
        item['metadata']['namespace'] = NAMESPACE
        if item['kind'] == 'Deployment':
            pod = item['spec']['template']['spec']
            pod['nodeSelector'] = {'kubernetes.io/hostname': values['NODE_NAME']}
            pod['containers'][0]['image'] = values['REGISTRY_IMAGE']
            if values['IMAGE_PULL_SECRET']:
                pod['imagePullSecrets'] = [{'name': values['IMAGE_PULL_SECRET']}]
        elif item['kind'] == 'PersistentVolumeClaim':
            item['spec']['resources']['requests']['storage'] = values['STORAGE_SIZE']
        elif item['kind'] == 'Ingress':
            item['spec']['rules'][0]['host'] = values['REGISTRY_HOST']
    return [static_volume(values), *items]


def apply(kube, items, dry_run=False):
    """리소스를 명령 인자 대신 stdin으로 전달한다."""
    run([*kube, 'apply', '-f', '-', *(['--dry-run=server'] if dry_run else [])],
        data=json.dumps({'apiVersion': 'v1', 'kind': 'List', 'items': items}))


def check_node(kube, name):
    """대상 Worker가 Ready이고 일반 Pod를 받을 수 있는지 확인한다."""
    nodes = json.loads(run([*kube, 'get', 'nodes', '-l', 'kubernetes.io/hostname=' + name, '-o', 'json']))['items']
    require(len(nodes) == 1 and not nodes[0]['spec'].get('unschedulable') and
            any(item['type'] == 'Ready' and item['status'] == 'True' for item in nodes[0]['status']['conditions']),
            'registry 대상 노드의 hostname·Ready·스케줄 가능 상태를 확인하세요.')
    require(not any(item.get('effect') in ('NoSchedule', 'NoExecute') for item in nodes[0]['spec'].get('taints', [])),
            'registry 대상 Worker의 차단 taint를 확인하세요.')


def volume_plan(kube, values):
    """기존 PV는 경로·노드·예약 PVC를 검사해 재사용하고, 없을 때만 생성 대상으로 반환한다."""
    raw = run([*kube, 'get', 'pv', VOLUME, '--ignore-not-found', '-o', 'json'])
    if not raw.strip():
        return static_volume(values)
    current = json.loads(raw)
    expected = static_volume(values)['spec']
    spec = current['spec']
    reference = spec.get('claimRef', {})
    require(current.get('status', {}).get('phase', 'Available') in ('Available', 'Bound') and
            not current['metadata'].get('deletionTimestamp'),
            '기존 registry PV가 Released·Failed 또는 삭제 중입니다. 이미지 데이터를 먼저 확인하세요.')
    require(reference.get('namespace') == NAMESPACE and reference.get('name') == VOLUME,
            '기존 registry PV가 다른 PVC에 예약되어 있습니다.')
    require(spec.get('local', {}).get('path') == values['DATA_HOST_PATH'] and spec.get('nodeAffinity') == expected['nodeAffinity'],
            '기존 PV 경로·노드와 DATA_HOST_PATH·NODE_NAME이 다릅니다. env를 기존 데이터에 맞추세요.')
    return None


def routing_plan(kube, host):
    """공용 TLS와 기존 controller 감시 범위를 확인해 연결 변경을 계산한다."""
    current = json.loads(run([*kube, '-n', 'etch-sso', 'get', 'deployment', 'traefik', '-o', 'json']))
    tls.check(kube, host, current)
    return routing.namespace_access(NAMESPACE, current), routing.namespace_patch(current, NAMESPACE)


def connect(kube, access, changes, dry_run=False):
    """라우팅 권한과 namespace 감시 인자만 갱신한다."""
    apply(kube, access, dry_run=dry_run)
    if changes:
        run([*kube, '-n', 'etch-sso', 'patch', 'deployment', 'traefik', '--type=json',
             '--patch', json.dumps(changes), *(['--dry-run=server'] if dry_run else [])])
        if not dry_run:
            run([*kube, '-n', 'etch-sso', 'rollout', 'status', 'deployment/traefik', '--timeout=300s'])


def deploy(values, context, check_only=False, push_env=None):
    """노드·저장소·Secret·라우팅을 검사하고 registry를 배포한다. 없는 namespace·계정 Secret·저장 폴더는 직접 만든다."""
    require(context and context.strip(), '운영 context를 명시하세요.')
    kube = ['kubectl', '--context', context]
    check_node(kube, values['NODE_NAME'])
    pending = volume_plan(kube, values)
    access, changes = routing_plan(kube, values['REGISTRY_HOST'])
    namespace_exists = run([*kube, 'get', 'namespace', NAMESPACE, '--ignore-not-found', '-o', 'name']).strip()
    secret = auth_secret(kube, push_env) if namespace_exists else None
    if not namespace_exists:
        require(push_env and Path(push_env).is_file(), 'REGISTRY_PUSH_ENV에 push 계정 파일을 지정하세요.')
        push_account(push_env)
    if namespace_exists:
        if values['IMAGE_PULL_SECRET']:
            found = run([*kube, '-n', NAMESPACE, 'get', 'secret', values['IMAGE_PULL_SECRET'], '--ignore-not-found', '-o', 'name'])
            require(found.strip(), f'registry namespace에 Secret {values["IMAGE_PULL_SECRET"]}을 먼저 만드세요.')
        connect(kube, access, changes, dry_run=True)
    if pending:
        run([*kube, 'create', '--dry-run=server', '-f', '-'], data=json.dumps(pending))
    if check_only:
        if pending:
            print(f'신규 정적 PV·저장 폴더 생성 예정: {VOLUME} ({values["DATA_HOST_PATH"]})')
        if not namespace_exists:
            print('registry namespace와 push 계정 Secret은 up에서 생성합니다.')
        elif secret:
            print(f'Secret {AUTH_SECRET}은 up에서 push 계정 파일로 생성합니다.')
        print('registry 입력·노드·저장소·라우팅 검사 통과. 클러스터를 변경하지 않았습니다.')
        return
    if not namespace_exists:
        run([*kube, 'create', '-f', '-'], data=json.dumps(
            {'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': NAMESPACE}}))
        require(not values['IMAGE_PULL_SECRET'],
                f'registry namespace를 만들었습니다. Secret {values["IMAGE_PULL_SECRET"]}을 만든 뒤 up을 다시 실행하세요.')
        secret = auth_secret(kube, push_env)
    if secret:
        # create만 사용해 검사 이후 다른 운영자가 만든 Secret을 덮어쓰지 않는다.
        run([*kube, 'create', '-f', '-'], data=json.dumps(secret))
        print(f'push 계정 Secret 생성: {NAMESPACE}/{AUTH_SECRET}')
    if pending:
        # 새 PV일 때만 폴더를 준비한다. 기존 PV의 폴더와 이미지 데이터는 건드리지 않는다.
        host_dirs.prepare(run, kube, 'registry-storage-prepare', NAMESPACE, values['NODE_NAME'], values['PREPARE_IMAGE'],
                          [(values['DATA_HOST_PATH'], *DATA_OWNER)], values['IMAGE_PULL_SECRET'])
        run([*kube, 'create', '-f', '-'], data=json.dumps(pending))
    items = manifests(values)
    apply(kube, [item for item in items if item['kind'] not in ('PersistentVolume', 'Ingress')])
    run([*kube, '-n', NAMESPACE, 'rollout', 'restart', 'deployment/registry'])
    print('registry 기동 대기: 실패하면 Pod Events·로그와 저장 폴더 권한을 확인하세요.', flush=True)
    run([*kube, '-n', NAMESPACE, 'rollout', 'status', 'deployment/registry', '--timeout=300s'])
    # rollout 대기 중 다른 앱이 Traefik을 바꿨을 수 있으므로 최신 상태에서 패치를 다시 계산한다.
    access, changes = routing_plan(kube, values['REGISTRY_HOST'])
    connect(kube, access, changes)
    apply(kube, [item for item in items if item['kind'] == 'Ingress'])
    print(f'registry 배포 완료: https://{values["REGISTRY_HOST"]}/v2/')


def rotate_account(context, push_env):
    """push 계정 Secret을 계정 파일의 계정으로 바꾸고 registry를 다시 시작한다. 이미지 데이터는 건드리지 않는다."""
    require(context and context.strip(), '운영 context를 명시하세요.')
    kube = ['kubectl', '--context', context]
    found = run([*kube, '-n', NAMESPACE, 'get', 'deployment', 'registry', '--ignore-not-found', '-o', 'name'])
    require(found.strip(), 'registry가 설치돼 있지 않습니다. 계정은 registry-up이 처음 만듭니다.')
    require(push_env and Path(push_env).is_file(), 'REGISTRY_PUSH_ENV에 새 push 계정 파일을 지정하세요.')
    user, password = push_account(push_env)
    apply(kube, [{'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': AUTH_SECRET, 'namespace': NAMESPACE},
                  'type': 'Opaque', 'stringData': {'htpasswd': htpasswd_line(user, password) + '\n'}}])
    run([*kube, '-n', NAMESPACE, 'rollout', 'restart', 'deployment/registry'])
    run([*kube, '-n', NAMESPACE, 'rollout', 'status', 'deployment/registry', '--timeout=300s'])
    print(f'push 계정 교체 완료: {NAMESPACE}/{AUTH_SECRET} (계정 {user}). 이미지 push에는 같은 계정 파일을 사용하세요.')


def main():
    """정적 검사와 context를 사용하는 운영 검사를 구분한다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('check', 'render', 'up', 'rotate-account'))
    parser.add_argument('--env', type=Path)
    parser.add_argument('--context', default='')
    parser.add_argument('--push-env', type=Path, default=BASE / 'env/push-initial.env',
                        help='Secret이 없을 때만 사용하는 push 계정 파일')
    args = parser.parse_args()
    if args.action == 'rotate-account':
        rotate_account(args.context, args.push_env)
        return
    values = settings(args.env or BASE / 'env/k8s.env', example=args.action == 'check' and args.env is None)
    if args.action == 'render':
        print(json.dumps({'apiVersion': 'v1', 'kind': 'List', 'items': manifests(values)}, indent=2))
    elif args.action == 'up' or args.context:
        deploy(values, args.context, check_only=args.action == 'check', push_env=args.push_env)
    else:
        manifests(values)
        print('registry 원본·env 검사 통과. 클러스터 적용·이미지 다운로드 검사는 별도입니다.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError) as error:
        print(f'registry 실행 실패: {error}', file=sys.stderr)
        print('진단: kubectl --context <운영 context> -n registry get pods,pvc; '
              'kubectl --context <운영 context> -n registry logs deployment/registry', file=sys.stderr)
        sys.exit(1)
