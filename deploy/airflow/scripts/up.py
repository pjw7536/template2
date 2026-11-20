#!/usr/bin/env python3
"""Airflow만 배포하고 필요한 공용 Traefik 연결을 준비한다."""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('airflow_server', ROOT / 'deploy/airflow/scripts/server.py')
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


SEED_DAGS = '''if [ ! -f /seed/.airflow-dags-initialized ] && [ -z "$(ls -A /seed)" ]; then
    cp -R /opt/airflow/dags/. /seed/
    touch /seed/.airflow-dags-initialized
    echo "이미지의 DAG를 공유 폴더로 복사했습니다."
else
    echo "공유 폴더에 파일 또는 준비 표식이 있어 변경하지 않았습니다."
fi
'''


def storage_directories(settings):
    """env에 선언한 Worker 폴더와 컨테이너 실행 계정에 맞는 소유자·권한 목록을 만든다."""
    directories = []
    if settings.get('POSTGRES_MODE', 'internal') == 'internal':
        directories.append((settings['POSTGRES_HOST_PATH'], settings['POSTGRES_UID'], settings['POSTGRES_GID'], '0700'))
    directories.append((settings['LOGS_HOST_PATH'], 50000, 0, '0770'))
    if settings.get('DAGS_HOST_PATH'):
        directories.append((settings['DAGS_HOST_PATH'], 0, 0, '0755'))
    if settings.get('ODBC_HOST_PATH'):
        directories.append((settings['ODBC_HOST_PATH'], 50000, 0, '0750'))
    return directories


def seed_job(settings):
    """비어 있는 DAG 공유 폴더에만 이미지의 DAG와 준비 표식을 복사하는 Job을 만든다."""
    pod = {'restartPolicy': 'Never', 'automountServiceAccountToken': False,
           'nodeSelector': {'kubernetes.io/hostname': settings['NODE_NAME']},
           'containers': [{'name': 'seed', 'image': settings['AIRFLOW_IMAGE_REPOSITORY'] + ':' + settings['AIRFLOW_IMAGE_TAG'],
                           'imagePullPolicy': 'IfNotPresent', 'command': ['sh', '-ec', SEED_DAGS],
                           'securityContext': {'runAsUser': 0, 'runAsGroup': 0, 'runAsNonRoot': False,
                                               'allowPrivilegeEscalation': False},
                           'volumeMounts': [{'name': 'dags', 'mountPath': '/seed'}]}],
           'volumes': [{'name': 'dags', 'hostPath': {'path': settings['DAGS_HOST_PATH'], 'type': 'Directory'}}]}
    if settings['IMAGE_PULL_SECRET']:
        pod['imagePullSecrets'] = [{'name': settings['IMAGE_PULL_SECRET']}]
    return {'apiVersion': 'batch/v1', 'kind': 'Job',
            'metadata': {'generateName': 'airflow-dags-seed-', 'namespace': settings['NAMESPACE'],
                         'labels': {'app.kubernetes.io/name': 'airflow-dags-seed'}},
            'spec': {'backoffLimit': 0, 'activeDeadlineSeconds': 300, 'ttlSecondsAfterFinished': 600,
                     'template': {'spec': pod}}}


def prepare(airflow, host_dirs, settings, context, ca_file, check_only):
    """배포 전에 필요한 namespace·OIDC CA ConfigMap·Worker 폴더·DAG 초기 파일을 준비한다. 기존 것은 바꾸지 않는다.

    check_only이면 아무것도 만들지 않고, 배포 때 만들 ConfigMap 이름 집합을 반환한다.
    """
    run = airflow.run
    kube = ['kubectl', '--context', context]
    namespace = settings['NAMESPACE']
    scoped = [*kube, '-n', namespace]
    exists = run([*kube, 'get', 'namespace', namespace, '--ignore-not-found', '-o', 'name']).strip()
    configmap = settings['AIRFLOW_OIDC_CA_CONFIGMAP']
    missing_ca = bool(configmap) and not (exists and run([*scoped, 'get', 'configmap', configmap, '--ignore-not-found', '-o', 'name']).strip())
    if missing_ca:
        airflow.require(ca_file and Path(ca_file).is_file(),
                        f'OIDC CA ConfigMap {configmap}이 없고 CA 묶음 파일도 없습니다: {ca_file}. '
                        'AIRFLOW_OIDC_CA_FILE에 사내 CA 묶음 PEM을 지정하세요.')
    if check_only:
        if missing_ca:
            print(f'OIDC CA ConfigMap {configmap}은 up에서 {ca_file}로 생성합니다.')
        return {configmap} if missing_ca else set()
    if not exists:
        run([*kube, 'create', '-f', '-'], data=json.dumps({'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': namespace}}))
    if missing_ca:
        run([*kube, 'create', '-f', '-'], data=json.dumps({
            'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': configmap, 'namespace': namespace},
            'data': {'ca.crt': Path(ca_file).read_text()}}))
        print(f'OIDC CA ConfigMap 생성: {namespace}/{configmap}')
    host_dirs.prepare(run, kube, 'airflow-storage-prepare', namespace, settings['NODE_NAME'], settings['POSTGRES_IMAGE'],
                      storage_directories(settings), settings['IMAGE_PULL_SECRET'])
    # 이미 설치된 환경의 DAG 폴더는 운영자가 관리하므로 최초 설치에만 이미지의 DAG를 복사한다.
    installed = exists and run([*scoped, 'get', 'deployment', 'airflow-scheduler', '--ignore-not-found', '-o', 'name']).strip()
    if settings.get('DAGS_HOST_PATH') and not installed:
        created = json.loads(run([*kube, 'create', '-f', '-', '-o', 'json'], data=json.dumps(seed_job(settings))))['metadata']['name']
        print(f'DAG 공유 폴더 확인 대기: {namespace}/job/{created}', flush=True)
        host_dirs.wait_job(run, kube, namespace, created)


def image_change(airflow, settings, context):
    """실행 중인 scheduler 이미지와 배포할 이미지를 비교한 한 줄을 만든다. 업데이트 전에 승인이 필요한지 판단하는 근거다."""
    target = settings['AIRFLOW_IMAGE_REPOSITORY'] + ':' + settings['AIRFLOW_IMAGE_TAG']
    current = airflow.run(['kubectl', '--context', context, '-n', settings['NAMESPACE'], 'get', 'deployment', 'airflow-scheduler',
                           '--ignore-not-found', '-o', 'jsonpath={.spec.template.spec.containers[0].image}']).strip()
    if not current:
        return f'이미지 변경: 최초 설치({target})'
    return '이미지 변경: 없음' if current == target else f'이미지 변경: 있음({current} → {target})'


def main():
    """앱별 env와 context를 받아 DB를 유지하며 배포한다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context', required=True)
    parser.add_argument('--env', type=Path, default=ROOT / 'deploy/airflow/env/k8s.env')
    parser.add_argument('--tls-source')
    parser.add_argument('--check-only', action='store_true')
    parser.add_argument('--ca-file', type=Path, help='OIDC CA ConfigMap이 없을 때 사용할 사내 CA 묶음 PEM')
    args = parser.parse_args()
    airflow = server.module('airflow_deploy', ROOT / 'deploy/airflow/scripts/manage.py')
    airflow.require(args.context.strip(), '--context를 명시하세요.')
    settings = airflow.read_env(args.env)
    airflow.validate(settings)
    host_dirs = server.module('shared_host_dirs', ROOT / 'deploy/shared/scripts/host_dirs.py')
    issuer_host = urlsplit(settings.get('AIRFLOW_OIDC_ISSUER', '')).hostname or ''
    ca_file = args.ca_file or os.environ.get('AIRFLOW_OIDC_CA_FILE') or ROOT / 'deploy/shared/certs' / issuer_host / 'keycloak-ca-bundle.pem'
    chart = airflow.chart_path() if settings['INGRESS_ENABLED'] != 'true' else None

    def check():
        """클러스터를 바꾸지 않는 전체 검사. 배포도 이 검사를 먼저 통과해야 한다."""
        pending = prepare(airflow, host_dirs, settings, args.context, ca_file, check_only=True)
        if chart is None:
            routing = server.module('routing', ROOT / 'deploy/shared/ingress/routing.py')
            server.start(airflow, routing, args.context, args.env, args.tls_source, check_only=True, pending_configmaps=pending)
        else:
            with tempfile.TemporaryDirectory(prefix='airflow-check-') as temporary:
                airflow.render(settings, temporary, chart, pause_new_dags=True)
                airflow.check_cluster_inputs(settings, args.context, Path(temporary) / 'airflow.yaml')
            airflow.check_required_resources(settings, args.context, pending_configmaps=pending)
            print('Airflow 설정·차트·클러스터 버전·노드·기존 비밀값·필수 리소스 검사 통과. 디스크·이미지·접속 확인은 별도입니다.')

    check()
    print(image_change(airflow, settings, args.context), flush=True)
    if args.check_only:
        return
    airflow.require_image_tag(settings)
    prepare(airflow, host_dirs, settings, args.context, ca_file, check_only=False)
    if chart is None:
        routing = server.module('routing', ROOT / 'deploy/shared/ingress/routing.py')
        server.start(airflow, routing, args.context, args.env, args.tls_source)
    else:
        airflow.deploy(settings, args.context, chart, pause_new_dags=True)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, StopIteration) as error:
        print(f'오류: {error}', file=sys.stderr)
        sys.exit(1)
