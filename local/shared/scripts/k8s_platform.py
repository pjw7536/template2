#!/usr/bin/env python3
"""Portal 없이 deploy의 platform 앱을 로컬 kind에서 실행·검사합니다."""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from urllib.request import urlopen

from k8s import (KIND, KUBE, airflow_up, apply, build, cluster_up, database_up, ftp_up,
                 keycloak_secrets, load_images, minio_secrets, monitoring_up, resources, rollout, run, wait_job)
from k8s_config import (ROOT, RUNTIME, airflow_settings, credentials, module,
                        monitoring_settings, prepare, settings)

spec = importlib.util.spec_from_file_location('local_headlamp_oidc', ROOT / 'local/headlamp/local_oidc.py')
headlamp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(headlamp)
PLATFORM = tuple(json.loads((ROOT / 'deploy/shared/apps.json').read_text())['groups']['platform'])

WORKLOADS = (
    ('tailwind-local', 'deployment/keycloak'),
    ('tailwind-local', 'deployment/minio'),
    ('tailwind-local', 'deployment/traefik'),
    ('etch-ftp', 'daemonset/ftp'),
    ('airflow', 'deployment/airflow-scheduler'),
    ('airflow', 'deployment/airflow-webserver'),
    ('airflow', 'deployment/airflow-triggerer'),
    ('headlamp', 'deployment/headlamp'),
    ('monitoring', 'deployment/monitoring-grafana'),
    ('monitoring', 'deployment/monitoring-operator'),
    ('monitoring', 'deployment/monitoring-kube-state-metrics'),
    ('monitoring', 'daemonset/monitoring-prometheus-node-exporter'),
    ('monitoring', 'statefulset/prometheus-monitoring-prometheus'),
    ('monitoring', 'statefulset/alertmanager-monitoring-alertmanager'),
)


def charts(fetch=False):
    """고정 chart가 없을 때만 공식 외부 경로에서 받고 동일 checksum으로 검증합니다."""
    for app in ('airflow', 'monitoring', 'headlamp'):
        deploy = module(app)
        lock = deploy.LOCK
        path = Path(os.environ.get(app.upper() + '_CHART_FILE',
                    ROOT / f'deploy/{app}/helm/vendor/{lock["name"]}-{lock["version"]}.tgz'))
        if fetch and not path.exists():
            url = lock['url']
            if app == 'headlamp':
                url = ('https://github.com/kubernetes-sigs/headlamp/releases/download/'
                       f'headlamp-helm-{lock["version"]}/headlamp-{lock["version"]}.tgz')
            print(f'공식 chart 준비: {app} {lock["version"]}', flush=True)
            with urlopen(url, timeout=120) as response:
                data = response.read()
            if hashlib.sha256(data).hexdigest() != lock['sha256']:
                raise ValueError(f'{app} chart SHA-256 불일치')
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        if not path.exists():
            raise ValueError(f'{app} chart가 없습니다. make dev-platform 또는 {app.upper()}_CHART_FILE을 사용하세요.')
        if hashlib.sha256(path.read_bytes()).hexdigest() != lock['sha256']:
            raise ValueError(f'{app} chart SHA-256 불일치')


def checks():
    """Portal 소스·env·클러스터 접근 없이 6개 앱의 배포 입력을 검사합니다."""
    for command in ('docker', 'kubectl', 'helm', 'openssl', KIND):
        if not shutil.which(command):
            raise ValueError(f'필수 도구가 없습니다: {command}')
    if set(PLATFORM) != {'keycloak', 'airflow', 'ftp', 'monitoring', 'headlamp', 'minio'}:
        raise ValueError('platform 앱 목록이 변경되었습니다. 로컬 실행·검사 지원을 함께 갱신하세요.')
    settings()
    charts()
    resources('local/shared/k8s/platform')
    resources('local/ftp/k8s')
    headlamp.render()
    for app, values in [('airflow', airflow_settings(credentials())), ('monitoring', monitoring_settings())]:
        deploy = module(app)
        deploy.validate(values)
        with tempfile.TemporaryDirectory() as directory:
            flags = {'values_file': ROOT / f'local/{app}/helm/values.yaml'}
            if app == 'airflow':
                flags['pause_new_dags'] = True
            deploy.render(values, directory, deploy.chart_path(), **flags)
    print('PASS platform 6개 앱 Kustomize·Helm·env 검사 (클러스터 변경 없음)', flush=True)


def preload():
    """선택 스택의 공개 기반 이미지만 Docker 캐시에서 반입합니다."""
    items = resources('local/shared/k8s/platform') + resources('local/ftp/k8s') + headlamp.render()
    images = set()
    def collect(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key == 'image' and isinstance(item, str):
                    images.add(item)
                else:
                    collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)
    collect(items)
    for image in sorted(images):
        print('기반 이미지 확인·반입: ' + image, flush=True)
        if subprocess.run(['docker', 'image', 'inspect', image], capture_output=True).returncode:
            run(['docker', 'pull', image])
        load_images([image])


def storage_check():
    """재시작으로 끊어진 worker bind mount는 데이터 복구 안내와 함께 중단합니다."""
    if subprocess.run([KIND, 'get', 'nodes', '--name', 'tailwind-local'], capture_output=True).returncode:
        return
    for name in ('minio', 'airflow', 'monitoring'):
        result = subprocess.run(['docker', 'exec', 'tailwind-local-worker', 'test', '-d',
                                 '/data/local-runtime/' + name], capture_output=True)
        if result.returncode:
            raise ValueError('worker 데이터 마운트를 확인하세요. 기존 환경은 docker restart tailwind-local-worker 후 재시도하세요. 데이터는 삭제하지 않습니다.')


def stack_up(creds):
    """기반·Keycloak·MinIO를 준비하며 완료한 기존 초기화 Job은 유지합니다."""
    keycloak_secrets(creds)
    minio_secrets()
    items = resources('local/shared/k8s/platform')
    apply([item for item in items if item['kind'] != 'Job'])
    for name in ('keycloak', 'minio', 'traefik'):
        rollout('tailwind-local', 'deployment/' + name)
    existing = run([*KUBE, '-n', 'tailwind-local', 'get', 'job', 'minio-init', '--ignore-not-found', '-o', 'name'], quiet=True)
    if not existing.strip():
        apply([item for item in items if item['kind'] == 'Job'])
    wait_job('minio-init')


def health():
    """선택 앱의 workload 준비 상태만 확인하고 Portal 상태는 요구하지 않습니다."""
    for namespace, workload in WORKLOADS:
        rollout(namespace, workload)
    print('PASS platform workload 준비 상태', flush=True)


def status():
    """플랫폼 주소와 자격증명 위치를 표시합니다."""
    for namespace in dict.fromkeys(namespace for namespace, _ in WORKLOADS):
        run([*KUBE, '-n', namespace, 'get',
             *[workload for owner, workload in WORKLOADS if owner == namespace]])
    print('Keycloak: http://localhost:8180\nAirflow: http://localhost:8080/airflow\n'
          'Headlamp: ' + headlamp.URL + '\nMinIO: http://localhost:8080/minio-console/\n'
          f'FTP: localhost:{settings()["LOCAL_FTP_PORT"]}\nGrafana: make k8s-grafana\nPrometheus: make k8s-prometheus\n'
          'Headlamp 계정: platform-admin (관리자) / platform-viewer (권한 없음)\n'
          '비밀번호: local/shared/runtime/credentials.env\n로컬 CA: local/shared/runtime/headlamp-tls/ca.crt')


def main():
    """명시한 로컬 context에서만 플랫폼 실행·갱신·검사를 수행합니다."""
    os.environ['PATH'] = str(ROOT / '.tools/bin') + os.pathsep + os.environ['PATH']
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('check', 'up', 'rebuild', 'status', 'smoke'))
    parser.add_argument('--app', choices=PLATFORM, default='keycloak')
    args = parser.parse_args()
    if args.action == 'check':
        checks()
    elif args.action in ('up', 'rebuild'):
        charts(fetch=True)
        checks()
        info = json.loads(run(['docker', 'info', '--format', '{{json .}}'], quiet=True))
        if info['MemTotal'] < 10 * 1024**3 or shutil.disk_usage(ROOT).free < 15 * 1024**3:
            raise ValueError('Docker 메모리 10GiB·디스크 여유 15GiB 이상이 필요합니다.')
        if not (RUNTIME / 'credentials.env').exists() and subprocess.run(
                ['docker', 'volume', 'inspect', 'tailwind-local-db_postgres_data'], capture_output=True).returncode == 0:
            raise ValueError('기존 DB volume의 credentials.env 백업을 복원하세요. 자격증명을 재생성하지 않습니다.')
        config = settings()
        creds = prepare(config, include_portal=False)
        # 신규 환경은 cluster_up이 마운트를 만들고 기존 환경은 사전 확인합니다.
        if 'tailwind-local' in run([KIND, 'get', 'clusters'], quiet=True).splitlines():
            storage_check()
        cluster_up(config)
        database_up(include_portal=False)
        if args.action == 'up':
            preload()
            stack_up(creds)
            headlamp.up(creds)
            build('airflow')
            airflow_up(creds)
            ftp_up(creds)
            monitoring_up(creds)
            health()
            status()
        elif args.app == 'airflow':
            build('airflow')
            airflow_up(creds)
        elif args.app == 'headlamp':
            headlamp.up(creds)
        elif args.app == 'ftp':
            ftp_up(creds)
        elif args.app == 'monitoring':
            monitoring_up(creds)
        else:
            preload()
            stack_up(creds)
            headlamp.up(creds)
    elif args.action == 'status':
        status()
    else:
        health()
        run([sys.executable, ROOT / 'local/shared/scripts/k8s_platform_smoke.py'])


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, OSError, subprocess.CalledProcessError) as error:
        sys.exit(f'로컬 platform 작업 실패: {error}')
