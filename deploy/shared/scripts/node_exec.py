#!/usr/bin/env python3
"""클러스터에 가입한 노드에서 명령을 실행한다. 사내 서버는 노드 사이의 SSH를 쓸 수 없으므로 Kubernetes API로 실행한다.

관리 호스트의 kubeconfig로 대상 노드에 일회성 Job을 띄우고, 그 Pod가 노드의 호스트 namespace에서 root로 명령을 실행한다.
출력은 그대로 보여 주고 Job은 끝난 뒤 10분이 지나면 자동으로 지워진다.

    python3 deploy/shared/scripts/node_exec.py <노드> --context "<context>" --command '<한 줄 명령>'
    python3 deploy/shared/scripts/node_exec.py <노드> --context "<context>" --script <명령 블록을 저장한 파일>
    python3 deploy/shared/scripts/node_exec.py <노드> --context "<context>" --copy <관리 호스트 파일>:<노드의 절대 경로>

- `<노드>`는 `kubectl get nodes`의 NAME이다. 아직 가입하지 않은 노드에는 쓸 수 없다.
- 명령은 bash로 실행한다. root이므로 `sudo`는 붙어 있어도 되고 없어도 된다.
- `--copy`는 `--command`·`--script`보다 먼저 수행한다. 파일 내용이 Job 정의에 담기므로 비밀값이 든 파일에는 쓰지 않는다.
- Make를 거치지 않는다. Make는 값의 `$`를 해석해 명령을 바꾸기 때문이다.

종료 코드: 0 명령 성공, 1 명령 실패·시간 초과·입력 오류.
"""

import argparse
import base64
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
SETTINGS = ROOT / 'deploy/shared/env/node-exec.env'
MAX_COPY_BYTES = 64 * 1024
# nsenter가 있으면 노드의 모든 namespace로 들어가고, 없으면 마운트한 노드 루트로 chroot한다.
WRAPPER = ('if command -v nsenter >/dev/null 2>&1; then exec nsenter -t 1 -m -u -i -n -p -- /bin/bash -c "$0"; '
           'else exec chroot /host /bin/bash -c "$0"; fi')


class NodeError(Exception):
    """노드 명령을 실행할 수 없거나 실패했다."""


def read_settings(path=SETTINGS, environ=None):
    """이미지와 namespace. 같은 이름의 환경변수가 env 파일보다 우선한다."""
    environ = os.environ if environ is None else environ
    values = {}
    for line in Path(path).read_text().splitlines():
        if line.strip() and not line.lstrip().startswith('#'):
            key, _, value = line.partition('=')
            values[key.strip()] = value.strip()
    for key in ('NODE_EXEC_IMAGE', 'NODE_EXEC_NAMESPACE'):
        if environ.get(key):
            values[key] = environ[key]
        if not values.get(key):
            raise NodeError(f'{key}가 필요합니다: {path}')
    return values


def copy_script(source, target):
    """관리 호스트의 파일을 노드의 경로에 쓰는 명령을 만든다."""
    path = PurePosixPath(target)
    if not path.is_absolute() or '..' in path.parts or len(path.parts) < 3:
        raise NodeError(f'--copy의 노드 경로는 폴더 아래의 절대 경로여야 합니다: {target}')
    data = Path(source).read_bytes()
    if len(data) > MAX_COPY_BYTES:
        raise NodeError(f'--copy는 {MAX_COPY_BYTES // 1024}KiB 이하 파일만 보낼 수 있습니다: {source}')
    encoded = base64.b64encode(data).decode()
    # 이미 있는 폴더의 권한은 바꾸지 않는다(install -d -m은 기존 폴더의 권한도 바꾼다).
    return (f"mkdir -p '{path.parent}'\n"
            f"base64 -d > '{path}' <<'NODE_EXEC_COPY'\n{encoded}\nNODE_EXEC_COPY\n"
            f"chmod 0644 '{path}'\necho '파일 배치: {path}'\n")


def build_script(command=None, script=None, copies=()):
    """실행할 bash 스크립트 한 덩어리를 만든다. 실패한 줄에서 멈춘다."""
    parts = ['set -e\n']
    for item in copies:
        source, separator, target = item.partition(':')
        if not separator or not source or not target:
            raise NodeError(f'--copy는 <관리 호스트 파일>:<노드 경로> 형식입니다: {item}')
        parts.append(copy_script(source, target))
    if script:
        parts.append(Path(script).read_text().rstrip('\n') + '\n')
    if command:
        parts.append(command.rstrip('\n') + '\n')
    if len(parts) == 1:
        raise NodeError('--command, --script, --copy 중 하나 이상을 지정하세요.')
    return ''.join(parts)


def job(node, script, image, namespace, timeout):
    """대상 노드에 고정해 호스트 namespace에서 스크립트를 실행하는 Job manifest."""
    pod = {'restartPolicy': 'Never', 'nodeName': node, 'hostPID': True, 'hostNetwork': True, 'hostIPC': True,
           'automountServiceAccountToken': False, 'tolerations': [{'operator': 'Exists'}],
           'containers': [{'name': 'node', 'image': image, 'imagePullPolicy': 'IfNotPresent',
                           'command': ['/bin/sh', '-c', WRAPPER, script],
                           'securityContext': {'privileged': True, 'runAsUser': 0},
                           'volumeMounts': [{'name': 'host', 'mountPath': '/host'}]}],
           'volumes': [{'name': 'host', 'hostPath': {'path': '/'}}]}
    return {'apiVersion': 'batch/v1', 'kind': 'Job',
            'metadata': {'generateName': 'node-exec-', 'namespace': namespace, 'labels': {'app.kubernetes.io/name': 'node-exec'}},
            'spec': {'backoffLimit': 0, 'activeDeadlineSeconds': timeout, 'ttlSecondsAfterFinished': 600,
                     'template': {'metadata': {'labels': {'app.kubernetes.io/name': 'node-exec'}}, 'spec': pod}}}


def kubectl(context):
    """context를 명시한 kubectl 실행 함수. 실패하면 NodeError를 낸다."""
    def run(args, data=None):
        result = subprocess.run(['kubectl', '--context', context, *args], input=data, capture_output=True, text=True)
        if result.returncode:
            raise NodeError(result.stderr.strip() or 'kubectl 실행 실패')
        return result.stdout
    return run


def wait(kube, namespace, name, timeout, interval=3, sleep=time.sleep):
    """Job이 끝날 때까지 기다려 성공 여부를 돌려준다.

    노드 명령이 API server나 containerd를 다시 시작하면 조회가 잠시 실패하므로, 조회 실패는 시간이 남아 있는 동안 다시 시도한다.
    """
    waiting = ''
    for _ in range(max(1, timeout // interval)):
        try:
            status = json.loads(kube(['-n', namespace, 'get', 'job', name, '-o', 'json'])).get('status', {})
            conditions = {item.get('type') for item in status.get('conditions', []) if item.get('status') == 'True'}
            if status.get('succeeded') or 'Complete' in conditions:
                return True
            if status.get('failed') or 'Failed' in conditions:
                return False
            pods = json.loads(kube(['-n', namespace, 'get', 'pods', '-l', f'job-name={name}', '-o', 'json']))['items']
            reasons = [(state.get('state') or {}).get('waiting', {}).get('reason', '')
                       for pod in pods for state in pod.get('status', {}).get('containerStatuses', []) or []]
            waiting = next((reason for reason in reasons if reason in ('ImagePullBackOff', 'ErrImagePull', 'InvalidImageName')), '')
            if waiting:
                raise NodeError(f'노드가 실행 이미지를 받지 못했습니다({waiting}). deploy/shared/env/node-exec.env의 NODE_EXEC_IMAGE와 '
                                '그 노드의 사내 미러 접근을 확인하세요.')
        except (NodeError, ValueError):
            if waiting:
                raise
        sleep(interval)
    raise NodeError(f'노드 명령 대기 시간 초과({timeout}초): {namespace}/job/{name}')


def execute(node, script, context, settings, timeout=600, kube=None, sleep=time.sleep):
    """Job을 만들어 실행하고 (성공 여부, 출력)을 돌려준다."""
    kube = kube or kubectl(context)
    if not kube(['get', 'node', node, '--ignore-not-found', '-o', 'name']).strip():
        raise NodeError(f'클러스터에 없는 노드입니다: {node}. kubectl get nodes의 NAME을 쓰세요. 가입 전 노드에는 이 도구를 쓸 수 없습니다.')
    manifest = json.dumps(job(node, script, settings['NODE_EXEC_IMAGE'], settings['NODE_EXEC_NAMESPACE'], timeout))
    namespace = settings['NODE_EXEC_NAMESPACE']
    name = json.loads(kube(['create', '-f', '-', '-o', 'json'], data=manifest))['metadata']['name']
    succeeded = wait(kube, namespace, name, timeout + 60, sleep=sleep)
    output = ''
    for _ in range(5):
        try:
            output = kube(['-n', namespace, 'logs', f'job/{name}', '--tail=-1'])
            break
        except NodeError:
            sleep(3)
    return succeeded, output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('node')
    parser.add_argument('--context', default=os.environ.get('KUBE_CONTEXT', ''))
    parser.add_argument('--command', help='노드에서 실행할 한 줄 명령')
    parser.add_argument('--script', help='노드에서 실행할 명령 블록을 저장한 관리 호스트의 파일')
    parser.add_argument('--copy', action='append', default=[], help='<관리 호스트 파일>:<노드의 절대 경로>. 반복 가능')
    parser.add_argument('--timeout', type=int, default=600, help='명령 제한 시간(초)')
    args = parser.parse_args(argv)
    try:
        if not args.context.strip():
            raise NodeError('KUBE_CONTEXT를 명시하세요.')
        script = build_script(args.command, args.script, args.copy)
        succeeded, output = execute(args.node, script, args.context.strip(), read_settings(), args.timeout)
    except (NodeError, OSError, ValueError, KeyError) as error:
        print(f'오류: {error}', file=sys.stderr)
        return 1
    sys.stdout.write(output if output.endswith('\n') or not output else output + '\n')
    print(f'노드 명령 {"완료" if succeeded else "실패"}: {args.node}')
    return 0 if succeeded else 1


if __name__ == '__main__':
    sys.exit(main())
