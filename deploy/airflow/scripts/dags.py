#!/usr/bin/env python3
"""관리 호스트 checkout의 `apps/airflow/dags`를 Airflow Worker의 DAG 폴더(`DAGS_HOST_PATH`)에 맞춘다.

노드에 접속하지 않는다. 실행 중인 scheduler 이미지로 `NODE_NAME` Worker에 임시 Pod를 띄워 DAG 폴더를 연결하고,
`kubectl exec`로 DAG 묶음을 보내 Pod 안에서 비교·반영한 뒤 Pod를 지운다.
- 저장소와 같은 이름의 파일은 덮어쓰고(내용이 같으면 그대로), 저장소에만 있는 파일은 추가한다.
- 폴더에만 있는 파일은 지우지 않고 목록으로만 보여 준다.
- `--check`는 폴더를 읽기 전용으로 연결해 바뀔 목록만 보여 준다.
"""

import argparse
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
SOURCE = ROOT / 'apps/airflow/dags'
POD_SCRIPT = Path(__file__).with_name('dags_sync_pod.py')
MOUNT = '/dags'
READY_TIMEOUT = '180s'
MAX_LISTED = 30


def load_manage():
    spec = importlib.util.spec_from_file_location('airflow_manage', BASE / 'scripts/manage.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(args, data=None):
    """명령을 실행하고 표준 출력을 문자열로 반환한다. 입력은 바이트로 전달한다."""
    result = subprocess.run([str(arg) for arg in args], input=data, capture_output=True)
    if result.returncode:
        raise ValueError(f'{" ".join(map(str, args[:5]))} 실패: {result.stderr.decode(errors="replace").strip()[-500:]}')
    return result.stdout.decode()


def archive(source):
    """DAG 폴더를 tar로 묶는다. Python 캐시는 빼고, 소유자·시각을 고정해 같은 내용이면 같은 묶음이 된다."""
    files = sorted(path for path in Path(source).rglob('*')
                   if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc')
    if not files:
        raise ValueError(f'보낼 DAG 파일이 없습니다: {source}. 저장소 전체 checkout에서 실행하세요.')
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w', format=tarfile.PAX_FORMAT) as bundle:
        for path in files:
            info = tarfile.TarInfo(path.relative_to(source).as_posix())
            content = path.read_bytes()
            info.size, info.mode, info.mtime = len(content), 0o644, 0
            bundle.addfile(info, io.BytesIO(content))
    return buffer.getvalue()


def pod_manifest(settings, image, apply):
    """DAG 폴더를 연결하고 대기만 하는 임시 Pod. 폴더가 root 소유이므로 root로 실행한다."""
    pod = {'restartPolicy': 'Never', 'automountServiceAccountToken': False, 'activeDeadlineSeconds': 900,
           'terminationGracePeriodSeconds': 0,
           'nodeSelector': {'kubernetes.io/hostname': settings['NODE_NAME']},
           'containers': [{'name': 'sync', 'image': image, 'imagePullPolicy': 'IfNotPresent', 'command': ['sleep', '600'],
                           'securityContext': {'runAsUser': 0, 'runAsGroup': 0, 'runAsNonRoot': False,
                                               'allowPrivilegeEscalation': False},
                           'volumeMounts': [{'name': 'dags', 'mountPath': MOUNT, 'readOnly': not apply}]}],
           'volumes': [{'name': 'dags', 'hostPath': {'path': settings['DAGS_HOST_PATH'], 'type': 'Directory'}}]}
    if settings.get('IMAGE_PULL_SECRET'):
        pod['imagePullSecrets'] = [{'name': settings['IMAGE_PULL_SECRET']}]
    return {'apiVersion': 'v1', 'kind': 'Pod',
            'metadata': {'generateName': 'airflow-dags-sync-', 'namespace': settings['NAMESPACE'],
                         'labels': {'app.kubernetes.io/name': 'airflow-dags-sync'}},
            'spec': pod}


def sync(settings, context, apply, source=SOURCE, runner=run):
    """임시 Pod로 DAG 폴더를 비교하거나 반영하고 결과를 반환한다. Pod는 성공·실패와 관계없이 지운다."""
    if not context or not context.strip():
        raise ValueError('KUBE_CONTEXT를 명시하세요.')
    bundle = archive(source)
    scoped = ['kubectl', '--context', context, '-n', settings['NAMESPACE']]
    image = runner([*scoped, 'get', 'deployment', 'airflow-scheduler', '--ignore-not-found',
                    '-o', 'jsonpath={.spec.template.spec.containers[0].image}']).strip()
    if not image:
        raise ValueError('airflow-scheduler가 없어 사용할 이미지를 정할 수 없습니다. 먼저 make ops-deploy APP=airflow로 배포하세요.')
    manifest = json.dumps(pod_manifest(settings, image, apply)).encode()
    name = runner([*scoped, 'create', '-f', '-', '-o', 'jsonpath={.metadata.name}'], data=manifest).strip()
    try:
        runner([*scoped, 'wait', '--for=condition=Ready', f'pod/{name}', f'--timeout={READY_TIMEOUT}'])
        output = runner([*scoped, 'exec', '-i', name, '--', 'python3', '-c', POD_SCRIPT.read_text(), MOUNT,
                         'apply' if apply else 'check'], data=bundle)
    finally:
        runner([*scoped, 'delete', 'pod', name, '--ignore-not-found', '--wait=false'])
    return json.loads(output.strip().splitlines()[-1])


def listed(names):
    shown = ', '.join(names[:MAX_LISTED])
    return shown + (f' 외 {len(names) - MAX_LISTED}개' if len(names) > MAX_LISTED else '')


def report(result):
    """사람과 운영 agent가 읽는 결과 줄. 마지막 줄이 성공 문구다."""
    apply = result['mode'] == 'apply'
    lines = []
    for key, label in (('added', '추가' if apply else '추가 예정'), ('updated', '덮어씀' if apply else '덮어쓸 예정'),
                       ('serverOnly', '폴더에만 있음(유지)')):
        if result[key]:
            lines.append(f'{label}: {listed(result[key])}')
    counts = (f'추가 {len(result["added"])} · 덮어씀 {len(result["updated"])} · 같음 {len(result["unchanged"])}'
              f' · 폴더에만 있음 {len(result["serverOnly"])}')
    lines.append(f'DAG 폴더 동기화 완료: {counts}' if apply else f'DAG 폴더 검사 완료(폴더는 바꾸지 않음): {counts}')
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--env', type=Path, required=True, help='Airflow env 경로')
    parser.add_argument('--context', required=True, help='대상 kubectl context')
    parser.add_argument('--check', action='store_true', help='폴더를 바꾸지 않고 바뀔 목록만 보여 준다')
    args = parser.parse_args()
    manage = load_manage()
    settings = manage.read_env(args.env)
    manage.validate(settings)
    print(report(sync(settings, args.context, apply=not args.check)))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as error:
        print(f'오류: {error}', file=sys.stderr)
        sys.exit(1)
