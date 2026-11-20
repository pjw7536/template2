"""Worker의 앱 전용 저장 폴더를 일회성 Job으로 준비한다. 기존 폴더·파일 권한은 바꾸지 않는다."""

import json
from pathlib import PurePosixPath
import time

SCRIPT = '''prepare() {
    target="$1"
    if [ -L "$target" ] || { [ -e "$target" ] && [ ! -d "$target" ]; }; then
        printf '저장 경로가 디렉터리가 아니거나 심볼릭 링크입니다: %s\\n' "$5" >&2
        exit 1
    fi
    if [ ! -d "$target" ]; then
        mkdir -m 0700 "$target"
        chown "$2:$3" "$target"
        chmod "$4" "$target"
        printf '폴더 생성: %s\\n' "$5"
    fi
}
'''


def job(name, namespace, node, image, directories, pull_secret=''):
    """없는 폴더만 만드는 Job manifest를 만든다. directories는 (절대 경로, uid, gid, mode) 목록이다."""
    volumes, mounts, lines = [], [], []
    for index, (path, uid, gid, mode) in enumerate(directories):
        target = PurePosixPath(path)
        if not target.is_absolute() or len(target.parts) < 3 or '..' in target.parts:
            raise ValueError(f'앱 전용 절대 경로가 필요합니다: {path}')
        # 부모만 마운트해 대상 폴더의 생성 여부와 권한을 Job이 직접 판단한다.
        volumes.append({'name': f'parent-{index}', 'hostPath': {'path': str(target.parent), 'type': 'DirectoryOrCreate'}})
        mounts.append({'name': f'parent-{index}', 'mountPath': f'/host/{index}'})
        lines.append(f"prepare '/host/{index}/{target.name}' {int(uid)} {int(gid)} {mode} '{target}'")
    pod = {'restartPolicy': 'Never', 'automountServiceAccountToken': False,
           'nodeSelector': {'kubernetes.io/hostname': node},
           'tolerations': [{'operator': 'Exists'}],
           'containers': [{'name': 'prepare', 'image': image, 'imagePullPolicy': 'IfNotPresent',
                           'command': ['/bin/sh', '-ec', SCRIPT + '\n'.join(lines)],
                           'securityContext': {'runAsUser': 0, 'runAsGroup': 0, 'runAsNonRoot': False,
                                               'allowPrivilegeEscalation': False,
                                               'capabilities': {'drop': ['ALL'], 'add': ['CHOWN', 'FOWNER', 'DAC_OVERRIDE']}},
                           'volumeMounts': mounts,
                           'resources': {'requests': {'cpu': '10m', 'memory': '16Mi'},
                                         'limits': {'cpu': '100m', 'memory': '64Mi'}}}],
           'volumes': volumes}
    if pull_secret:
        pod['imagePullSecrets'] = [{'name': pull_secret}]
    return {'apiVersion': 'batch/v1', 'kind': 'Job',
            'metadata': {'generateName': f'{name}-', 'namespace': namespace,
                         'labels': {'app.kubernetes.io/name': name}},
            'spec': {'backoffLimit': 0, 'activeDeadlineSeconds': 240, 'ttlSecondsAfterFinished': 600,
                     'template': {'spec': pod}}}


def prepare(run, kube, name, namespace, node, image, directories, pull_secret='', dry_run=False):
    """Job을 만들고 완료를 기다린다. dry_run이면 서버 검증만 하고 클러스터를 바꾸지 않는다."""
    if not directories:
        return None
    manifest = json.dumps(job(name, namespace, node, image, directories, pull_secret))
    run([*kube, 'create', '--dry-run=server', '-f', '-'], data=manifest)
    if dry_run:
        return None
    created = json.loads(run([*kube, 'create', '-f', '-', '-o', 'json'], data=manifest))['metadata']['name']
    print(f'저장 폴더 준비 대기: {namespace}/job/{created}', flush=True)
    wait_job(run, kube, namespace, created)
    return created


def wait_job(run, kube, namespace, name, timeout=300, interval=3, sleep=time.sleep):
    """Job의 완료 또는 실패 중 먼저 오는 쪽을 기다린다. 실패하면 Pod 로그 끝을 오류에 담아 바로 중단한다."""
    scoped = [*kube, '-n', namespace]
    for _ in range(max(1, timeout // interval)):
        current = json.loads(run([*scoped, 'get', 'job', name, '-o', 'json']))
        status = current.get('status', {})
        conditions = {item.get('type') for item in status.get('conditions', []) if item.get('status') == 'True'}
        if status.get('succeeded') or 'Complete' in conditions:
            return
        # 재시도하지 않는 Job은 첫 실패로, 재시도하는 Job은 Failed 조건(재시도 소진·기한 초과)으로 판단한다.
        retries = current.get('spec', {}).get('backoffLimit', 0)
        if 'Failed' in conditions or (status.get('failed') and not retries and not status.get('active')):
            try:
                detail = run([*scoped, 'logs', f'job/{name}', '--tail=20']).strip()
            except ValueError:
                detail = ''
            raise ValueError(f'Job 실패: {namespace}/{name}. ' + (detail or f'kubectl -n {namespace} describe job/{name}으로 원인을 확인하세요.'))
        sleep(interval)
    raise ValueError(f'Job 대기 시간 초과: {namespace}/{name}. 이미지 pull·노드 배치를 kubectl -n {namespace} describe job/{name}으로 확인하세요.')
