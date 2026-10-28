#!/usr/bin/env python3
"""공용 MinIO를 Portal과 독립적으로 검사·렌더·배포한다."""

import argparse
import base64
from copy import deepcopy
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys

BASE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('shared_tls', BASE.parent / 'shared/ingress/tls.py')
tls = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tls)
spec = importlib.util.spec_from_file_location('minio_routing', BASE.parent / 'shared/ingress/routing.py')
routing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(routing)

NAMESPACE = 'minio'
SECRET_KEYS = ('MINIO_ROOT_USER', 'MINIO_ROOT_PASSWORD', 'MINIO_BROWSER_REDIRECT_URL',
               'MINIO_SERVER_URL', 'MINIO_BUCKETS')
ENV_KEYS = set(SECRET_KEYS) | {'NODE_NAME', 'MINIO_IMAGE', 'MINIO_CLIENT_IMAGE', 'IMAGE_PULL_SECRET',
                             'STORAGE_CLASS_NAME', 'VOLUME_NAME', 'STORAGE_SIZE', 'MINIO_DATA_HOST_PATH',
                             'INGRESS_HOST', 'INGRESS_TLS_SECRET'}


def require(condition, message):
    """민감한 입력 대신 설정 키와 복구 방법을 보고한다."""
    if not condition:
        raise ValueError(message)


def run(args, data=None, sensitive=False):
    """셸 확장 없이 실행하고 Secret 처리 오류의 본문은 숨긴다."""
    result = subprocess.run(list(map(str, args)), input=data, capture_output=True, text=True)
    require(result.returncode == 0, 'Secret 처리 실패: 입력과 권한을 확인하세요.' if sensitive
            else result.stderr.strip() or f'{args[0]} 실행 실패')
    return result.stdout


def settings(path, example=False):
    """env를 실행하지 않고 중복·알 수 없는 키와 운영 주소를 검사한다."""
    result = {}
    for line in Path(path).read_text().splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        key, separator, value = line.partition('=')
        require(separator and key in ENV_KEYS and key not in result, 'MinIO env 키 누락·중복·오타를 확인하세요.')
        result[key] = value
    result.setdefault('MINIO_DATA_HOST_PATH', '/data/minio')
    require(result.keys() == ENV_KEYS, 'MinIO env 키가 설정 계약과 다릅니다.')
    optional = {'IMAGE_PULL_SECRET', 'STORAGE_CLASS_NAME', 'VOLUME_NAME', 'MINIO_BUCKETS', 'INGRESS_TLS_SECRET'}
    for key, value in result.items():
        require(key in optional or value, f'필수 설정 누락: {key}')
        require(not any(c.isspace() for c in value) and
                (example or not any(s in value for s in ('replace-me', 'example.invalid', '<', '>'))),
                f'실제 값 또는 형식 확인 필요: {key}')
    label = r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?'
    for key in ('NODE_NAME', 'IMAGE_PULL_SECRET', 'STORAGE_CLASS_NAME', 'VOLUME_NAME', 'INGRESS_TLS_SECRET'):
        require(not result[key] or (len(result[key]) <= 253 and re.fullmatch(rf'{label}(?:\.{label})*', result[key])),
                f'Kubernetes 이름 오류: {key}')
    require(re.fullmatch(rf'{label}(?:\.{label})+', result['INGRESS_HOST']), 'INGRESS_HOST에는 DNS 이름이 필요합니다.')
    require(re.fullmatch(r'[1-9][0-9]*(Gi|Ti)', result['STORAGE_SIZE']), 'STORAGE_SIZE에는 Gi 또는 Ti 용량이 필요합니다.')
    path = result['MINIO_DATA_HOST_PATH']
    require(path.startswith('/') and path != '/' and '..' not in path.split('/') and not path.endswith('/'),
            'MINIO_DATA_HOST_PATH에는 데이터 전용 절대 디렉터리를 지정하세요.')
    for key in ('MINIO_IMAGE', 'MINIO_CLIENT_IMAGE'):
        require(re.fullmatch(r'[a-zA-Z0-9._:/@-]+', result[key]) and
                (':' in result[key].rsplit('/', 1)[-1] or '@sha256:' in result[key]) and not result[key].endswith(':latest'),
                f'고정 tag 또는 digest 이미지가 필요합니다: {key}')
    expected = f'https://{result["INGRESS_HOST"]}/minio-console/'
    require(result['MINIO_BROWSER_REDIRECT_URL'] == expected, '콘솔 공개 주소는 HTTPS host와 /minio-console/ 경로가 일치해야 합니다.')
    require(result['MINIO_SERVER_URL'] == 'http://minio:9000', '내부 S3 주소는 http://minio:9000을 사용하세요.')
    require(not result['MINIO_BUCKETS'] or all(re.fullmatch(r'[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]', name)
                                            for name in result['MINIO_BUCKETS'].split(',')), 'MINIO_BUCKETS에는 쉼표로 구분한 버킷 이름이 필요합니다.')
    return result


def volume_name(values):
    """운영자가 지정한 PV 이름을 우선하고 신규 설치 기본값을 제공한다."""
    return values['VOLUME_NAME'] or 'minio-data-pv'


def static_volume(values):
    """정적 볼륨을 해당 Worker와 MinIO PVC에 예약하고 삭제 후에도 데이터를 보존한다."""
    return {'apiVersion': 'v1', 'kind': 'PersistentVolume',
            'metadata': {'name': volume_name(values), 'labels': {'app.kubernetes.io/name': 'minio'}},
            'spec': {'capacity': {'storage': values['STORAGE_SIZE']}, 'volumeMode': 'Filesystem',
                     'accessModes': ['ReadWriteOnce'], 'persistentVolumeReclaimPolicy': 'Retain',
                     'storageClassName': '', 'claimRef': {'namespace': NAMESPACE, 'name': 'minio-data'},
                     'local': {'path': values['MINIO_DATA_HOST_PATH']},
                     'nodeAffinity': {'required': {'nodeSelectorTerms': [{'matchExpressions': [
                         {'key': 'kubernetes.io/hostname', 'operator': 'In', 'values': [values['NODE_NAME']]}]}]}}}}


def storage_bytes(value):
    """기존 PV/PVC 용량을 단위의 표기 차이에 의존하지 않고 비교한다."""
    match = re.fullmatch(r'([0-9]+(?:\.[0-9]+)?)([KMGTPE]i|[kMGTPE]|m|[eE][+-]?[0-9]+)?', value)
    require(match, 'PV/PVC의 용량 표기를 확인하세요.')
    number, unit = match.groups()
    factors = {'': Decimal(1), 'm': Decimal('0.001')}
    factors.update({name + 'i': Decimal(1024) ** index for index, name in enumerate('KMGTPE', 1)})
    factors.update({name: Decimal(1000) ** index for index, name in enumerate('kMGTPE', 1)})
    factor = Decimal(10) ** int(unit[1:]) if unit and re.fullmatch(r'[eE][+-]?[0-9]+', unit) else factors[unit or '']
    return Decimal(number) * factor


def storage_plan(kube, values, node, claim):
    """기존 연결과 데이터를 검사하고 누락된 정적 PV만 생성 대상으로 반환한다."""
    effective = dict(values)
    if claim:
        require(not claim.get('metadata', {}).get('deletionTimestamp') and claim.get('status', {}).get('phase') != 'Lost',
                '기존 MinIO PVC가 삭제 중이거나 Lost 상태입니다. 기존 저장소를 먼저 복구하세요.')
        require(claim['spec'].get('storageClassName', '') == values['STORAGE_CLASS_NAME'],
                '기존 PVC의 StorageClass를 변경할 수 없습니다. 기존 볼륨 설정을 유지하세요.')
        requested = claim['spec'].get('resources', {}).get('requests', {}).get('storage')
        require(not requested or storage_bytes(requested) == storage_bytes(values['STORAGE_SIZE']),
                '기존 PVC 용량은 자동 변경하지 않습니다. STORAGE_SIZE를 기존 요청 용량에 맞추세요.')
        require(not claim['spec'].get('selector'), '기존 PVC의 selector가 있습니다. 저장소 연결을 먼저 확인하세요.')
    if values['STORAGE_CLASS_NAME']:
        run([*kube, 'get', 'storageclass', values['STORAGE_CLASS_NAME'], '-o', 'name'])
        return effective, None
    bound = claim['spec'].get('volumeName', '') if claim else ''
    require(not bound or not values['VOLUME_NAME'] or bound == values['VOLUME_NAME'],
            '기존 PVC의 volumeName과 VOLUME_NAME이 다릅니다. 기존 연결을 유지하세요.')
    effective['VOLUME_NAME'] = bound or volume_name(values)
    raw = run([*kube, 'get', 'pv', effective['VOLUME_NAME'], '--ignore-not-found', '-o', 'json'])
    if not raw.strip():
        annotations = claim.get('metadata', {}).get('annotations', {}) if claim else {}
        require(not claim or (claim.get('status', {}).get('phase') != 'Bound'
                              and annotations.get('pv.kubernetes.io/bind-completed') != 'yes'),
                '기존 PVC에 연결됐던 PV가 없습니다. 새 빈 볼륨을 만들지 않고 중단합니다. 기존 PV를 복구하세요.')
        return effective, static_volume(effective)
    current = json.loads(raw)
    spec = current['spec']
    require(not current.get('metadata', {}).get('deletionTimestamp') and
            current.get('status', {}).get('phase', 'Pending') in ('Pending', 'Available', 'Bound'),
            '기존 PV가 Released·Failed 또는 삭제 중입니다. 데이터와 PVC 연결을 먼저 복구하세요.')
    reference = spec.get('claimRef', {})
    require(not reference or (reference.get('namespace') == NAMESPACE and reference.get('name') == 'minio-data'
                             and (not reference.get('uid') or claim and reference['uid'] == claim['metadata']['uid'])),
            '기존 PV가 다른 PVC 또는 이전 PVC UID에 예약되어 있습니다. 기존 데이터를 먼저 확인하세요.')
    require(current.get('status', {}).get('phase') != 'Bound' or
            claim and bound == effective['VOLUME_NAME'] and reference.get('uid') == claim['metadata']['uid'],
            'Bound PV와 현재 MinIO PVC의 연결이 다릅니다. 기존 저장소를 먼저 확인하세요.')
    require(not spec.get('storageClassName') and spec.get('volumeMode', 'Filesystem') == 'Filesystem'
            and 'ReadWriteOnce' in spec.get('accessModes', [])
            and storage_bytes(spec.get('capacity', {}).get('storage', '0')) >= storage_bytes(values['STORAGE_SIZE']),
            '기존 PV의 StorageClass·volumeMode·accessModes·용량이 MinIO 설정과 맞지 않습니다.')
    require(spec.get('local', {}).get('path') == values['MINIO_DATA_HOST_PATH'],
            '기존 PV 경로와 MINIO_DATA_HOST_PATH가 다릅니다. env를 기존 데이터 경로에 맞추세요.')
    required = spec.get('nodeAffinity', {}).get('required')
    require(required and routing.node_matches({'affinity': {'nodeAffinity': {
        'requiredDuringSchedulingIgnoredDuringExecution': required}}}, node),
        '기존 local PV의 nodeAffinity와 NODE_NAME이 다릅니다. 기존 Worker를 유지하세요.')
    return effective, None


def storage_job(values, create_directory=True):
    """대상 Worker의 지정 디렉터리만 만들며 기존 파일·소유권·권한은 변경하지 않는다."""
    pod = {'restartPolicy': 'Never', 'automountServiceAccountToken': False,
           'nodeSelector': {'kubernetes.io/hostname': values['NODE_NAME']},
           'containers': [{'name': 'prepare', 'image': values['MINIO_CLIENT_IMAGE'], 'imagePullPolicy': 'IfNotPresent',
                           'command': ['/bin/sh', '-ec', 'test -d /data\ntest -w /data\nprintf "MinIO storage directory ready\\n"'],
                           'volumeMounts': [{'name': 'data', 'mountPath': '/data'}],
                           'securityContext': {'runAsUser': 0, 'allowPrivilegeEscalation': False,
                                               'readOnlyRootFilesystem': True, 'capabilities': {'drop': ['ALL']}},
                           'resources': {'requests': {'cpu': '10m', 'memory': '16Mi'},
                                         'limits': {'cpu': '100m', 'memory': '64Mi'}}}],
           'volumes': [{'name': 'data', 'hostPath': {'path': values['MINIO_DATA_HOST_PATH'],
                       'type': 'DirectoryOrCreate' if create_directory else 'Directory'}}]}
    if values['IMAGE_PULL_SECRET']:
        pod['imagePullSecrets'] = [{'name': values['IMAGE_PULL_SECRET']}]
    return {'apiVersion': 'batch/v1', 'kind': 'Job',
            'metadata': {'generateName': 'minio-storage-prepare-', 'namespace': NAMESPACE,
                         'labels': {'app.kubernetes.io/name': 'minio-storage-prepare'}},
            'spec': {'backoffLimit': 0, 'activeDeadlineSeconds': 240, 'ttlSecondsAfterFinished': 600,
                     'template': {'spec': pod}}}


def prepare_storage(kube, values, pending):
    """폴더 준비에 성공한 뒤 신규 PV를 create만 사용해 등록한다."""
    job = json.loads(run([*kube, 'create', '-f', '-', '-o', 'json'],
                         data=json.dumps(storage_job(values, create_directory=pending is not None))))
    name = job['metadata']['name']
    print(f'MinIO 저장 폴더 준비 대기: job/{name}. 실패 시 해당 Job의 Pod Events와 로그를 확인하세요.', flush=True)
    run([*kube, '-n', NAMESPACE, 'wait', '--for=condition=complete', f'job/{name}', '--timeout=300s'])
    if pending:
        run([*kube, 'create', '-f', '-'], data=json.dumps(pending))


def manifests(values):
    """공통 JSON 원본에 서버별 이미지·배치·저장소·Ingress 입력을 적용한다."""
    items = deepcopy(json.loads((BASE / 'k8s/base/stack.json').read_text())['items'])
    items += deepcopy(json.loads((BASE / 'k8s/ingress.json').read_text())['items'])
    for item in items:
        item['metadata']['namespace'] = NAMESPACE
        if item['kind'] in ('Deployment', 'Job'):
            spec = item['spec']['template']['spec']
            spec['nodeSelector'] = {'kubernetes.io/hostname': values['NODE_NAME']}
            spec['containers'][0]['image'] = values['MINIO_IMAGE' if item['kind'] == 'Deployment' else 'MINIO_CLIENT_IMAGE']
            if values['IMAGE_PULL_SECRET']:
                spec['imagePullSecrets'] = [{'name': values['IMAGE_PULL_SECRET']}]
        elif item['kind'] == 'PersistentVolumeClaim':
            item['spec'].update(storageClassName=values['STORAGE_CLASS_NAME'])
            item['spec']['resources']['requests']['storage'] = values['STORAGE_SIZE']
            if values['VOLUME_NAME'] or not values['STORAGE_CLASS_NAME']:
                item['spec']['volumeName'] = volume_name(values)
        elif item['kind'] == 'Ingress':
            item['spec']['rules'][0]['host'] = values['INGRESS_HOST']
    return ([static_volume(values)] if not values['STORAGE_CLASS_NAME'] else []) + items


def apply(kube, items, sensitive=False, dry_run=False):
    """리소스와 비밀값을 명령 인자 대신 stdin으로 전달한다."""
    run([*kube, 'apply', '-f', '-', *(['--dry-run=server'] if dry_run else [])],
        data=json.dumps({'apiVersion': 'v1', 'kind': 'List', 'items': items}), sensitive=sensitive)


def routing_plan(kube, values):
    """공용 middleware·TLS·controller를 검사하고 기존 감시 범위를 보존한다."""
    current = json.loads(run([*kube, '-n', 'etch-sso', 'get', 'deployment', 'traefik', '-o', 'json']))
    tls.check(kube, values['INGRESS_HOST'], current)
    pod = current['spec']['template']['spec']
    controller = next(item for item in pod['containers'] if item['name'] == 'traefik')
    require('--providers.file.directory=/etc/traefik/dynamic' in controller.get('args', []),
            '공용 middleware가 필요합니다. make ingress-check/ingress-up을 먼저 실행하세요.')
    mount = next((item for item in controller.get('volumeMounts', []) if item['mountPath'] == '/etc/traefik/dynamic'), None)
    volume = next((item for item in pod.get('volumes', []) if mount and item['name'] == mount['name']), None)
    sources = volume.get('projected', {}).get('sources', []) if volume else []
    config_name = next((source['configMap']['name'] for source in sources if 'configMap' in source), None)
    require(config_name, '공용 middleware ConfigMap 마운트를 확인하세요.')
    config = json.loads(run([*kube, '-n', 'etch-sso', 'get', 'configmap', config_name, '-o', 'json']))
    paths = '\n'.join(config.get('data', {}).values())
    require('minio-api:' in paths and 'minio-console:' in paths, '공용 middleware가 오래됐습니다. make ingress-up을 먼저 실행하세요.')
    return routing.namespace_access(NAMESPACE, current), routing.namespace_patch(current, NAMESPACE)


def connect(kube, access, changes, dry_run=False):
    """라우팅 권한과 namespace 감시 인자만 갱신한다."""
    apply(kube, access, dry_run=dry_run)
    if changes:
        run([*kube, '-n', 'etch-sso', 'patch', 'deployment', 'traefik', '--type=json',
             '--patch', json.dumps(changes), *(['--dry-run=server'] if dry_run else [])])
    if not dry_run:
        run([*kube, '-n', 'etch-sso', 'rollout', 'status', 'deployment/traefik', '--timeout=300s'])


def deploy(values, context, check_only=False, allow_legacy=False):
    """기존 Portal 설치·스토리지·라우팅을 검사하고 폴더·PV를 준비한 뒤 독립 MinIO를 배포한다."""
    require(context and context.strip(), '운영 context를 명시하세요.')
    kube = ['kubectl', '--context', context]
    for kind, name in (('deployment', 'minio'), ('pvc', 'minio-data')):
        legacy = run([*kube, '-n', 'tailwind-internal', 'get', kind, name, '--ignore-not-found', '-o', 'name'])
        require(not legacy.strip() or allow_legacy, '기존 tailwind-internal MinIO가 있습니다. 데이터·설정을 보존하고 deploy/minio/README.md의 이전 절차를 먼저 확인하세요.')
    node = json.loads(run([*kube, 'get', 'nodes', '-l', 'kubernetes.io/hostname=' + values['NODE_NAME'], '-o', 'json']))['items']
    require(len(node) == 1 and not node[0]['spec'].get('unschedulable') and
            any(item['type'] == 'Ready' and item['status'] == 'True' for item in node[0]['status']['conditions']),
            'MinIO 대상 노드의 hostname·Ready·스케줄 가능 상태를 확인하세요.')
    require(not any(item.get('effect') in ('NoSchedule', 'NoExecute') for item in node[0]['spec'].get('taints', [])),
            'MinIO 대상 Worker의 차단 taint를 확인하세요.')
    if values['IMAGE_PULL_SECRET']:
        run([*kube, '-n', NAMESPACE, 'get', 'secret', values['IMAGE_PULL_SECRET'], '-o', 'name'])
    claim_raw = run([*kube, '-n', NAMESPACE, 'get', 'pvc', 'minio-data', '--ignore-not-found', '-o', 'json'])
    claim = json.loads(claim_raw) if claim_raw.strip() else None
    values, pending = storage_plan(kube, values, node[0], claim)
    items = manifests(values)
    access, changes = routing_plan(kube, values)
    namespace_exists = run([*kube, 'get', 'namespace', NAMESPACE, '--ignore-not-found', '-o', 'name']).strip()
    if namespace_exists:
        connect(kube, access, changes, dry_run=True)
        if not values['STORAGE_CLASS_NAME']:
            run([*kube, 'create', '--dry-run=server', '-f', '-'],
                data=json.dumps(storage_job(values, create_directory=pending is not None)))
    if pending:
        run([*kube, 'create', '--dry-run=server', '-f', '-'], data=json.dumps(pending))
    if check_only:
        if pending:
            print('신규 정적 PV 생성 예정: ' + pending['metadata']['name'])
        print('MinIO 입력·노드·저장소·TLS·라우팅 검사 통과. 클러스터를 변경하지 않았습니다. '
              '폴더 준비·image pull·볼륨 결합은 up에서 확인합니다.')
        if not namespace_exists:
            print('minio namespace는 up에서 생성하며 namespace 권한과 Job admission 검사를 이어서 수행합니다.')
        return
    if not namespace_exists:
        run([*kube, 'create', '-f', '-'], data=json.dumps(
            {'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': NAMESPACE}}))
        connect(kube, access, changes, dry_run=True)
        if not values['STORAGE_CLASS_NAME']:
            run([*kube, 'create', '--dry-run=server', '-f', '-'],
                data=json.dumps(storage_job(values, create_directory=pending is not None)))
    if not values['STORAGE_CLASS_NAME']:
        prepare_storage(kube, values, pending)
    secret = {'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': 'minio-env', 'namespace': NAMESPACE},
              'type': 'Opaque', 'data': {key: base64.b64encode(values[key].encode()).decode() for key in SECRET_KEYS}}
    apply(kube, [secret], sensitive=True)
    previous = run([*kube, '-n', NAMESPACE, 'get', 'deployment', 'minio', '--ignore-not-found', '-o', 'name'])
    apply(kube, [item for item in items if item['kind'] not in ('Ingress', 'Job', 'PersistentVolume')])
    if previous.strip():
        run([*kube, '-n', NAMESPACE, 'rollout', 'restart', 'deployment/minio'])
    print('MinIO 기동 대기: 실패하면 Pod Events와 PVC 상태를 확인하세요.', flush=True)
    run([*kube, '-n', NAMESPACE, 'rollout', 'status', 'deployment/minio', '--timeout=300s'])
    existing = run([*kube, '-n', NAMESPACE, 'get', 'job', 'minio-init', '--ignore-not-found', '-o', 'name'])
    if not existing.strip():
        apply(kube, [item for item in items if item['kind'] == 'Job'])
    run([*kube, '-n', NAMESPACE, 'wait', '--for=condition=complete', 'job/minio-init', '--timeout=300s'])
    access, changes = routing_plan(kube, values)
    connect(kube, access, changes)
    apply(kube, [item for item in items if item['kind'] == 'Ingress'])
    print('공용 MinIO 배포 완료: ' + values['MINIO_BROWSER_REDIRECT_URL'])


def main():
    """정적 검사와 context를 사용하는 운영 검사를 구분한다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('check', 'render', 'up'))
    parser.add_argument('--env', type=Path)
    parser.add_argument('--context', default='')
    parser.add_argument('--allow-legacy', action='store_true', help='백업·기존 Ingress 전환을 준비한 수동 이전에만 사용')
    args = parser.parse_args()
    values = settings(args.env or BASE / 'env/prod.env', example=args.action == 'check' and args.env is None)
    if args.action == 'render':
        print(json.dumps({'apiVersion': 'v1', 'kind': 'List', 'items': manifests(values)}, indent=2))
    elif args.action == 'up' or args.context:
        deploy(values, args.context, check_only=args.action == 'check', allow_legacy=args.allow_legacy)
    else:
        manifests(values)
        print('공용 MinIO 원본·env 검사 통과. 클러스터 적용·이미지 다운로드 검사는 별도입니다.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError) as error:
        print(f'MinIO 실행 실패: {error}', file=sys.stderr)
        print('진단: kubectl --context <운영 context> -n minio get pods,pvc; '
              'kubectl --context <운영 context> -n minio describe pods -l app.kubernetes.io/name=minio', file=sys.stderr)
        sys.exit(1)
