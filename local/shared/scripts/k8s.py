#!/usr/bin/env python3
"""로컬 전체 앱의 검사·빌드·배포·종료를 명시한 kind context에서 수행합니다.

Secret은 stdin과 사용자 전용 파일로만 전달하고 기존 Docker DB와 데이터는 수정하지 않습니다.
"""

import argparse
import base64
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen

import yaml

from k8s_config import (CLUSTER, CONTEXT, IMAGES, NAMESPACES, ROOT, RUNTIME, WORKER,
                        airflow_settings, credentials, kind_config, module, monitoring_settings,
                        prepare, read_env, settings, write_private)

KIND = os.environ.get('KIND_BIN', str(ROOT / '.tools/bin/kind'))
KUBE = ['kubectl', '--context', CONTEXT]
DB = ['docker', 'compose', '--project-name', 'tailwind-local-db', '--env-file', str(RUNTIME / 'db.env'),
      '-f', str(ROOT / 'local/shared/compose/k8s-db.yml')]


def run(args, data=None, quiet=False, sensitive=False):
    """명령은 셸 없이 실행하고 민감한 입력의 실패 출력은 숨깁니다."""
    result = subprocess.run(list(map(str, args)), input=data, text=True, capture_output=True, cwd=ROOT)
    if result.returncode:
        detail = '민감한 입력의 출력은 생략합니다.' if sensitive else result.stderr[-6000:]
        raise RuntimeError(f'{Path(args[0]).name} 실패: {detail}')
    if not quiet and result.stdout.strip():
        print(result.stdout.strip(), flush=True)
    return result.stdout


def apply(items, sensitive=False):
    """메모리의 Kubernetes 객체를 파일에 남기지 않고 적용합니다."""
    run([*KUBE, 'apply', '-f', '-'], data=json.dumps({'apiVersion': 'v1', 'kind': 'List', 'items': items}), sensitive=sensitive)


def secret(namespace, name, values):
    """폐기된 설정 키도 제거하며 Secret 값은 stdin으로만 전달합니다."""
    data = {key: base64.b64encode(value.encode()).decode() for key, value in values.items()}
    existing = run([*KUBE, '-n', namespace, 'get', 'secret', name,
                    '--ignore-not-found', '-o', 'name'], quiet=True)
    if existing.strip():
        # JSON Patch의 add는 기존 data 객체 전체를 교체하므로 이전 키가 남지 않습니다.
        run([*KUBE, '-n', namespace, 'patch', 'secret', name, '--type=json', '--patch-file=/dev/stdin'],
            data=json.dumps([{'op': 'add', 'path': '/data', 'value': data}]), sensitive=True)
    else:
        apply([{'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': name, 'namespace': namespace},
                'type': 'Opaque', 'data': data}], sensitive=True)


def resources(relative):
    """저장소 원본 overlay를 렌더합니다."""
    result = [item for item in yaml.safe_load_all(run(['kubectl', 'kustomize', ROOT / relative], quiet=True)) if item]
    config = settings()
    replacements = {'minio/minio:latest': config['LOCAL_MINIO_IMAGE'], 'minio/mc:latest': config['LOCAL_MINIO_CLIENT_IMAGE']}
    def replace(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key == 'image' and isinstance(item, str):
                    value[key] = replacements.get(item, item)
                else:
                    replace(item)
        elif isinstance(value, list):
            for item in value:
                replace(item)
    replace(result)
    return result


def rollout(namespace, workload):
    """정해진 시간 안에 준비되지 않은 앱을 실패로 처리합니다."""
    run([*KUBE, '-n', namespace, 'rollout', 'status', workload, '--timeout=600s'])


def wait_job(name):
    """Job 실패 원인을 확인할 수 있도록 상태와 로그를 남깁니다."""
    try:
        run([*KUBE, '-n', 'tailwind-local', 'wait', '--for=condition=complete', f'job/{name}', '--timeout=600s'])
    except RuntimeError:
        run([*KUBE, '-n', 'tailwind-local', 'logs', f'job/{name}', '--all-containers', '--tail=60'])
        raise


def checks(config):
    """클러스터나 실제 env를 변경하지 않고 원본·도구·스토리지를 검사합니다."""
    for command in ('docker', 'kubectl', 'helm', KIND):
        if not shutil.which(command):
            raise ValueError(f'필수 도구가 없습니다: {command}')
    info = json.loads(run(['docker', 'info', '--format', '{{json .}}'], quiet=True))
    if info['MemTotal'] < 10 * 1024**3:
        raise ValueError('전체 앱 실행에는 Docker 메모리 10GiB 이상이 필요합니다.')
    if shutil.disk_usage(ROOT).free < 15 * 1024**3:
        raise ValueError('이미지·데이터용 디스크 여유 공간 15GiB 이상이 필요합니다.')
    resources('local/shared/k8s')
    resources('local/portal/k8s/migrate')
    resources('local/ftp/k8s')
    for app, values in [('airflow', airflow_settings(credentials())), ('monitoring', monitoring_settings())]:
        deploy = module(app)
        deploy.validate(values)
        with tempfile.TemporaryDirectory(prefix=f'local-{app}-check-') as directory:
            options = {'values_file': ROOT / f'local/{app}/helm/values.yaml'}
            if app == 'airflow':
                options['pause_new_dags'] = True
            deploy.render(values, directory, deploy.chart_path(), **options)
    print('전체 로컬 Kustomize·Helm·도구 검사 통과', flush=True)


def cluster_up(config):
    """클러스터를 준비하고 기존 클러스터의 마운트·포트 변경은 자동 삭제하지 않습니다."""
    existing = run([KIND, 'get', 'clusters'], quiet=True).splitlines()
    wanted = json.dumps(kind_config(config), sort_keys=True)
    applied = RUNTIME / 'applied-kind.json'
    if CLUSTER in existing:
        if not applied.exists() or applied.read_text() != wanted:
            raise ValueError('kind 설정이 바뀌었습니다. make k8s-down 후 재실행하세요. 데이터는 보존됩니다.')
    else:
        for port in (8080, 8443, 8180, int(config['LOCAL_FTP_PORT']),
                     *range(int(config['LOCAL_FTP_PASSIVE_START']), int(config['LOCAL_FTP_PASSIVE_START']) + 4)):
            with socket.socket() as connection:
                try:
                    connection.bind(('127.0.0.1', port))
                except OSError as error:
                    raise ValueError(f'로컬 포트 {port}가 사용 중입니다.') from error
        run([KIND, 'create', 'cluster', '--name', CLUSTER, '--config', RUNTIME / 'kind.json', '--wait', '180s'])
        write_private(applied, wanted)
    run([*KUBE, 'wait', '--for=condition=Ready', 'nodes', '--all', '--timeout=180s'])
    # 소유권 조정은 새 런타임 디렉터리의 최상위에만 적용합니다.
    run(['docker', 'exec', WORKER, 'chown', '50000:0', '/data/local-runtime/airflow/logs'])
    run(['docker', 'exec', WORKER, 'chmod', '0770', '/data/local-runtime/airflow/logs'])
    for name, owner in [('prometheus', '1000:2000'), ('alertmanager', '1000:2000'), ('grafana', '472:472')]:
        run(['docker', 'exec', WORKER, 'chown', owner, f'/data/local-runtime/monitoring/{name}'])
        run(['docker', 'exec', WORKER, 'chmod', '0770', f'/data/local-runtime/monitoring/{name}'])
    apply([{'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': name}} for name in NAMESPACES])
    run([*KUBE, 'apply', '-f', ROOT / 'local/airflow/k8s/ingress-access.yaml'])


def database_up():
    """새 Compose DB만 실행하고 현재 주소를 namespace별 Service에 연결합니다."""
    run([*DB, 'up', '-d', '--wait'], sensitive=True)
    # 새 인증용 DB도 기존 DB를 삭제하지 않고 최종 API env의 이름으로 준비합니다.
    run(['bash', ROOT / 'local/portal/scripts/build-local-api-env.sh', RUNTIME / 'api.env'], sensitive=True)
    api_env = read_env(RUNTIME / 'api.env')
    run([*DB, 'exec', '-T', 'postgres', 'psql', '-U', 'postgres', '-d', 'postgres',
         '-v', 'ON_ERROR_STOP=1', '-v', 'portal_db=' + api_env['DJANGO_DB_NAME'],
         '-v', 'portal_owner=' + api_env['DJANGO_DB_USER']], data=r"""
SELECT format('CREATE DATABASE %I OWNER %I', :'portal_db', :'portal_owner')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'portal_db')
\gexec
""", sensitive=True)
    run([*DB, 'exec', '-T', 'postgres', 'psql', '-U', 'postgres', '-d', api_env['DJANGO_DB_NAME'],
         '-v', 'ON_ERROR_STOP=1', '-c', 'CREATE EXTENSION IF NOT EXISTS pg_trgm'], sensitive=True)
    identifier = run([*DB, 'ps', '-q', 'postgres'], quiet=True).strip()
    address = run(['docker', 'inspect', '--format', '{{(index .NetworkSettings.Networks "kind").IPAddress}}', identifier], quiet=True).strip()
    if not address:
        raise ValueError('kind 네트워크의 DB 주소가 없습니다.')
    for namespace in ('tailwind-local', 'airflow'):
        apply([{'apiVersion': 'v1', 'kind': 'Service', 'metadata': {'name': 'external-postgres', 'namespace': namespace},
                'spec': {'ports': [{'name': 'postgres', 'port': 5432, 'targetPort': 5432}]}},
               {'apiVersion': 'discovery.k8s.io/v1', 'kind': 'EndpointSlice',
                'metadata': {'name': 'external-postgres', 'namespace': namespace,
                             'labels': {'kubernetes.io/service-name': 'external-postgres'}},
                'addressType': 'IPv4', 'ports': [{'name': 'postgres', 'protocol': 'TCP', 'port': 5432}],
                'endpoints': [{'addresses': [address]}]}])


def build(app):
    """선택한 소스만 이미지로 만들고 kind 노드에 반입합니다."""
    print(f'이미지 빌드·반입: {app}', flush=True)
    sources = {'portal': [('tailwind-api:k8s-local', 'apps/portal/api'), ('tailwind-web:k8s-local', 'apps/portal/web')],
               'mock': [('tailwind-adfs:k8s-local', 'local/adfs_dummy')],
               'airflow': [('tailwind-airflow:2.11.0-local', 'apps/airflow')]}
    # 로컬 공개 이미지에는 데스크톱 전용 credential helper를 요구하지 않습니다.
    with tempfile.TemporaryDirectory(prefix='local-docker-') as directory:
        Path(directory, 'config.json').write_text('{"auths":{}}')
        for image, source in sources[app]:
            args = ['docker', '--config', directory, 'build', '-t', image]
            if app == 'airflow':
                args += ['-f', ROOT / 'apps/airflow/image/Dockerfile']
            run([*args, ROOT / source])
    load_images(IMAGES[app])


def load_images(images):
    """Docker의 다중 플랫폼 manifest도 현재 PC 플랫폼만 반입합니다."""
    platform = run(['docker', 'version', '--format', '{{.Server.Os}}/{{.Server.Arch}}'], quiet=True).strip()
    nodes = run([KIND, 'get', 'nodes', '--name', CLUSTER], quiet=True).splitlines()
    with tempfile.TemporaryDirectory(prefix='local-image-') as directory:
        for image in images:
            archive = Path(directory) / 'image.tar'
            run(['docker', 'image', 'save', '-o', archive, image])
            for node in nodes:
                with archive.open('rb') as source:
                    result = subprocess.run(['docker', 'exec', '--privileged', '-i', node, 'ctr', '--namespace=k8s.io',
                                             'images', 'import', '--platform', platform, '--digests', '--snapshotter=overlayfs', '-'],
                                            stdin=source, capture_output=True)
                if result.returncode:
                    raise RuntimeError(f'{node} 이미지 반입 실패: {result.stderr.decode()[-2000:]}')


def preload_runtime_images():
    """Docker에 준비된 기반 이미지를 재사용하고 없는 이미지만 내려받습니다."""
    images = set()
    def collect(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key == 'image' and isinstance(item, str) and not item.startswith('tailwind-'):
                    images.add(item)
                else:
                    collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)
    collect(resources('local/shared/k8s'))
    collect(resources('local/ftp/k8s'))
    for image in sorted(images):
        print(f'기반 이미지 확인·반입: {image}', flush=True)
        inspected = subprocess.run(['docker', 'image', 'inspect', image], capture_output=True)
        if inspected.returncode:
            run(['docker', 'pull', image])
        load_images([image])


def portal_secrets(creds):
    """기동과 env 갱신이 같은 최종 API 설정을 사용합니다."""
    run(['bash', ROOT / 'local/portal/scripts/build-local-api-env.sh', RUNTIME / 'api.env'], sensitive=True)
    for name, values in [('api-env', read_env(RUNTIME / 'api.env')),
                         ('web-env', read_env(ROOT / 'local/portal/env/web.env')),
                         ('minio-env', read_env(ROOT / 'local/portal/env/minio.env'))]:
        secret('tailwind-local', name, values)


def keycloak_secrets(creds):
    """로컬 Keycloak이 사용하는 기존 Secret 이름과 입력을 유지합니다."""
    secret('tailwind-local', 'local-runtime', {
        'keycloak-db-password': creds['KEYCLOAK_DB_PASSWORD'],
        'keycloak-admin-username': 'local-keycloak-admin',
        'keycloak-admin-password': 'local-keycloak-admin-change-me'})


def local_stack_up(creds, restart_mock=False):
    """앱별 원본을 집계하여 의존 서비스·migration·Portal 순서로 실행합니다."""
    portal_secrets(creds)
    keycloak_secrets(creds)
    items = resources('local/shared/k8s')
    app_names = {'api', 'web', 'edge-nginx'}
    initial = [item for item in items if not (item['kind'] == 'Deployment' and item['metadata']['name'] in app_names)]
    run([*KUBE, '-n', 'tailwind-local', 'delete', 'job', 'minio-init', '--ignore-not-found'])
    apply(initial)
    if restart_mock:
        run([*KUBE, '-n', 'tailwind-local', 'rollout', 'restart', 'deployment/adfs'])
    for name in ('adfs', 'minio', 'keycloak', 'traefik'):
        rollout('tailwind-local', 'deployment/' + name)
    wait_job('minio-init')
    for job_name, command in [('portal-migrate', ['migrate', '--noinput']),
                              ('portal-seed', ['seed_dev_data'])]:
        job = resources('local/portal/k8s/migrate')[0]
        job['metadata']['name'] = job_name
        job['spec']['template']['spec']['containers'][0]['args'] = ['manage.py', *command]
        run([*KUBE, '-n', 'tailwind-local', 'delete', 'job', job_name, '--ignore-not-found'])
        apply([job])
        wait_job(job_name)
    apply([item for item in items if item['kind'] == 'Deployment' and item['metadata']['name'] in app_names])
    run([*KUBE, '-n', 'tailwind-local', 'rollout', 'restart', *['deployment/' + name for name in sorted(app_names)]])
    for name in (*sorted(app_names), 'headlamp'):
        rollout('tailwind-local', 'deployment/' + name)


def airflow_up(creds):
    """공통 Helm 배포로 외부 DB를 사용하는 Airflow를 실행합니다."""
    deploy = module('airflow')
    values = airflow_settings(creds)
    deploy.validate(values)
    deploy.deploy(values, CONTEXT, deploy.chart_path(), pause_new_dags=True,
                  values_file=ROOT / 'local/airflow/helm/values.yaml')


def dependency_up(app):
    """선택한 Keycloak·mock 원본만 적용하고 해당 Deployment를 갱신합니다."""
    directory, name = {'keycloak': ('local/keycloak/k8s', 'keycloak'),
                       'mock': ('local/adfs_dummy/k8s', 'adfs')}[app]
    apply(resources(directory))
    run([*KUBE, '-n', 'tailwind-local', 'rollout', 'restart', 'deployment/' + name])
    rollout('tailwind-local', 'deployment/' + name)


def ftp_up(creds):
    """worker의 호스트 포트와 API 공유 디렉터리를 사용하는 FTP를 실행합니다."""
    secret('etch-ftp', 'ftp-credentials', {'FTP_USER': 'ftpuser', 'FTP_PASS': creds['FTP_PASS']})
    items = resources('local/ftp/k8s')
    start = int(settings()['LOCAL_FTP_PASSIVE_START'])
    container = next(item for item in items if item['kind'] == 'DaemonSet')['spec']['template']['spec']['containers'][0]
    for env in container['env']:
        if env['name'] in ('PASV_MIN_PORT', 'PASV_MAX_PORT'):
            env['value'] = str(start + (3 if env['name'] == 'PASV_MAX_PORT' else 0))
    for offset, port in enumerate(container['ports'][1:]):
        port['containerPort'] = port['hostPort'] = start + offset
    apply(items)
    rollout('etch-ftp', 'daemonset/ftp')


def monitoring_up(creds):
    """공통 Helm 배포와 로컬 values로 모니터링을 실행합니다."""
    secret('monitoring', 'monitoring-grafana-admin', {'admin-user': 'admin', 'admin-password': creds['GRAFANA_PASSWORD']})
    deploy = module('monitoring')
    values = monitoring_settings()
    deploy.validate(values)
    deploy.deploy(values, CONTEXT, deploy.chart_path(), values_file=ROOT / 'local/monitoring/helm/values.yaml')


def health():
    """공개 진입점과 모든 namespace의 Pod 준비 상태를 확인합니다."""
    for namespace in NAMESPACES:
        pods = json.loads(run([*KUBE, '-n', namespace, 'get', 'pods', '-o', 'json'], quiet=True))['items']
        if not pods:
            raise RuntimeError(f'{namespace}에 실행 중인 앱이 없습니다.')
        for pod in pods:
            if pod['metadata'].get('deletionTimestamp') or pod['status']['phase'] == 'Succeeded':
                continue
            if not any(c['type'] == 'Ready' and c['status'] == 'True' for c in pod['status'].get('conditions', [])):
                raise RuntimeError(f'준비되지 않은 Pod: {namespace}/{pod["metadata"]["name"]}')
    for address in ('http://localhost:8080/api/v1/health/',
                    'http://localhost:8180/realms/portal/.well-known/openid-configuration',
                    'http://localhost:8080/airflow/health'):
        for attempt in range(30):
            try:
                with urlopen(address, timeout=5) as response:
                    if response.status == 200:
                        break
            except OSError:
                if attempt == 29:
                    raise
                time.sleep(2)
    print('전체 앱 준비 상태·공개 진입점 정상', flush=True)


def status():
    """계정 비밀번호 대신 접속 주소와 자격증명 파일 위치를 안내합니다."""
    for namespace in NAMESPACES:
        run([*KUBE, '-n', namespace, 'get', 'pods,pvc'])
    print('Portal: http://localhost:8080\nKeycloak: http://localhost:8180\nAirflow: http://localhost:8080/airflow\n'
          f'FTP: localhost:{settings()["LOCAL_FTP_PORT"]} (passive 시작 {settings()["LOCAL_FTP_PASSIVE_START"]})\nGrafana: make k8s-grafana\nPrometheus: make k8s-prometheus\n'
          'Portal 사용자: 90000001 / dummy-user-change-me\n'
          'Airflow: airflow, Grafana: admin, FTP: ftpuser — 비밀번호: local/shared/runtime/credentials.env')


def main():
    """검사·실행·갱신·종료 명령을 처리합니다."""
    os.environ['PATH'] = str(ROOT / '.tools/bin') + os.pathsep + os.environ['PATH']
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('check', 'up', 'rebuild', 'down', 'status', 'health', 'smoke', 'grafana', 'prometheus'))
    parser.add_argument('--app', choices=('portal', 'mock', 'airflow', 'ftp', 'monitoring', 'keycloak'), default='portal')
    args = parser.parse_args()
    config = settings()
    if args.command == 'check':
        checks(config)
    elif args.command in ('up', 'rebuild'):
        checks(config)
        if not (RUNTIME / 'credentials.env').exists():
            existing_db = subprocess.run(['docker', 'volume', 'inspect', 'tailwind-local-db_postgres_data'], capture_output=True)
            if existing_db.returncode == 0:
                raise ValueError('기존 DB volume이 있습니다. 백업한 local/shared/runtime/credentials.env를 복구하세요. 키를 새로 만들지 않습니다.')
        creds = prepare(config)
        cluster_up(config)
        database_up()
        if args.command == 'up':
            for app in ('portal', 'mock', 'airflow'):
                build(app)
            preload_runtime_images()
            local_stack_up(creds, restart_mock=True)
            airflow_up(creds)
            ftp_up(creds)
            monitoring_up(creds)
            health()
            status()
        else:
            if args.app in IMAGES:
                build(args.app)
            if args.app == 'portal':
                local_stack_up(creds)
            elif args.app == 'airflow':
                airflow_up(creds)
            elif args.app == 'ftp':
                ftp_up(creds)
            elif args.app == 'monitoring':
                monitoring_up(creds)
            else:
                dependency_up(args.app)
    elif args.command == 'down':
        # workload가 DB에 쓰기를 마친 뒤 종료하며 volume과 호스트 데이터는 남깁니다.
        run([KIND, 'delete', 'cluster', '--name', CLUSTER])
        if (RUNTIME / 'db.env').exists():
            run([*DB, 'down'])
    elif args.command == 'status':
        status()
    elif args.command == 'health':
        health()
    elif args.command == 'smoke':
        health()
        run([sys.executable, ROOT / 'local/shared/scripts/k8s_smoke.py'])
    else:
        target, port = ('monitoring-grafana', '3000:80') if args.command == 'grafana' else ('monitoring-prometheus', '9090:9090')
        subprocess.run([*KUBE, '-n', 'monitoring', 'port-forward', 'svc/' + target, port], check=True)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, OSError, subprocess.CalledProcessError) as error:
        print(f'로컬 Kubernetes 작업 실패: {error}\n상태 확인: make k8s-status', file=sys.stderr)
        sys.exit(1)
