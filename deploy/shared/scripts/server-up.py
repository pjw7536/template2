#!/usr/bin/env python3
"""기존 Keycloak을 보존하면서 공용 Traefik과 Airflow UI를 재적용한다.

최초 Secret·이미지·디스크는 서버에서 준비한다. 기존 Keycloak 인증값을 갱신하지 않는다.
모든 클러스터 명령은 명시한 context에만 실행하며 Git pull·push는 실행하지 않는다.
"""

import argparse
import base64
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[3]


def module(name, path):
    """선택 checkout에 포함된 배포 모듈을 명시적인 경로에서 읽는다."""
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def render_json(run, kube, path):
    """kubectl의 YAML 해석을 사용해 호스트의 추가 Python 패키지 없이 JSON으로 변환한다."""
    source = run(['kubectl', 'kustomize', path])
    stream = run([*kube, 'create', '--dry-run=client', '--validate=false', '-f', '-', '-o', 'json'], data=source)
    # kubectl 버전에 따라 여러 JSON 객체를 연속 출력하거나 List로 묶는다.
    items = []
    decoder = json.JSONDecoder()
    while stream.strip():
        stream = stream.lstrip()
        result, consumed = decoder.raw_decode(stream)
        items.extend(result['items'] if result.get('kind') == 'List' else [result])
        stream = stream[consumed:]
    return items


def tls_for_airflow(run, kube, settings, source):
    """기존 TLS Secret을 유지하고 명시한 원본에서만 새 namespace로 복사한다."""
    namespace = settings['NAMESPACE']
    name = settings['INGRESS_TLS_SECRET']
    current = run([*kube, '-n', namespace, 'get', 'secret', name, '--ignore-not-found', '-o', 'json'], sensitive=True)
    create = not current.strip()
    if create:
        if not source or len(source.split('/')) != 2 or not all(source.split('/')):
            raise ValueError('Airflow TLS Secret이 없습니다. --tls-source namespace/secret을 지정하거나 해당 namespace에 인증서를 먼저 등록하세요.')
        source_namespace, source_name = source.split('/')
        current = run([*kube, '-n', source_namespace, 'get', 'secret', source_name, '-o', 'json'], sensitive=True)
    secret = json.loads(current)
    if secret.get('type') != 'kubernetes.io/tls' or not all(secret.get('data', {}).get(key) for key in ('tls.crt', 'tls.key')):
        raise ValueError('지정 Secret에 Kubernetes TLS 인증서·키가 없습니다.')
    certificate = base64.b64decode(secret['data']['tls.crt'], validate=True).decode()
    host = urlsplit(settings['AIRFLOW_WEBSERVER_BASE_URL']).hostname
    checked = run(['openssl', 'x509', '-noout', '-checkhost', host], data=certificate, sensitive=True)
    if 'does match certificate' not in checked:
        raise ValueError('TLS 인증서가 Airflow 공개 URL의 도메인과 일치하지 않습니다.')
    run(['openssl', 'x509', '-noout', '-checkend', '0'], data=certificate, sensitive=True)
    if not create:
        return None
    return {'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': name, 'namespace': namespace},
            'type': 'kubernetes.io/tls', 'data': {key: secret['data'][key] for key in ('tls.crt', 'tls.key')}}


def start(airflow, routing, context, env, tls_source=None, vip_backends=None, check_only=False, deploy_keycloak=True):
    """모든 입력을 검사한 후 namespace 권한 → 기존 스택 → Airflow 순서로 실행한다."""
    airflow.require(context, '--context를 명시하세요.')
    settings = airflow.read_env(env)
    airflow.validate(settings)
    airflow.require(settings['INGRESS_ENABLED'] == 'true' and settings['INGRESS_CLASS_NAME'] == 'traefik', 'server-up은 INGRESS_ENABLED=true, INGRESS_CLASS_NAME=traefik이 필요합니다.')
    airflow.require(settings['NAMESPACE'] != 'etch-sso', 'Airflow는 기존 Keycloak과 별도의 namespace를 사용하세요.')
    airflow.require(urlsplit(settings['AIRFLOW_WEBSERVER_BASE_URL']).scheme == 'https', 'server-up의 Airflow 공개 URL은 HTTPS여야 합니다.')
    chart = airflow.chart_path()
    with tempfile.TemporaryDirectory(prefix='server-up-check-') as temporary:
        airflow.render(settings, temporary, chart, pause_new_dags=True)
    # 라우팅을 변경하기 전에 Airflow 자체의 배포 입력도 검사한다.
    airflow.check_cluster_inputs(settings, context)
    run = airflow.run
    kube = ['kubectl', '--context', context]
    # 이미 구동 중인 Keycloak 전용 진입점이다. 자격증명 생성과 realm/mapper 변경은 실행하지 않는다.
    if deploy_keycloak:
        for kind, name in [('deployment', 'keycloak'), ('statefulset', 'keycloak-postgres'), ('secret', 'keycloak-runtime'), ('secret', 'keycloak-tls')]:
            run([*kube, '-n', 'etch-sso', 'get', kind, name, '-o', 'name'])
    current = json.loads(run([*kube, '-n', 'etch-sso', 'get', 'deployment', 'traefik', '-o', 'json']))
    # 앱별 Airflow 배포는 기존 controller에 감시 namespace만 추가한다.
    if deploy_keycloak:
        desired = render_json(run, kube, ROOT / 'deploy/keycloak/k8s')
    else:
        controller = deepcopy(current)
        controller.pop('status', None)
        for field in ('managedFields', 'resourceVersion', 'uid', 'generation', 'creationTimestamp'):
            controller['metadata'].pop(field, None)
        controller['metadata'].get('annotations', {}).pop('kubectl.kubernetes.io/last-applied-configuration', None)
        desired = [controller]
    original = routing.controller(desired)
    # 앱·DB는 기존 Worker에 유지하고 VIP 진입점만 여러 Worker로 확장한다.
    source_node = original['spec']['template']['spec'].get('nodeSelector', {})
    live_node = current['spec']['template']['spec'].get('nodeSelector', {})
    ips = routing.vip_backend_ips(vip_backends, current)
    if not ips and deploy_keycloak:
        airflow.require(source_node == live_node and current['spec'].get('replicas', 1) == 1, '저장소와 기존 Traefik의 nodeSelector 또는 replicas가 다릅니다. 서버 배치 설정을 먼저 맞추세요.')
    if deploy_keycloak:
        airflow.require(settings['NODE_NAME'] == source_node.get('kubernetes.io/hostname'), 'Airflow NODE_NAME을 기존 앱 Worker로 유지하세요.')
    updated = routing.preserve_namespaces(original, current, settings['NAMESPACE'])
    if ips and deploy_keycloak:
        nodes = json.loads(run([*kube, 'get', 'nodes', '-o', 'json']))['items']
        pods = json.loads(run([*kube, 'get', 'pods', '-A', '-o', 'json']))['items']
        updated = routing.place_vip_backends(updated, current, ips, nodes, pods)
        print('VIP Backend 배치: ' + ', '.join(ip + ':443' for ip in ips), flush=True)
    desired = [updated if item is original else item for item in desired]
    certificate = tls_for_airflow(run, kube, settings, tls_source)
    if check_only:
        print('설정·차트·기존 리소스·TLS·배치 검사 통과. 클러스터를 변경하지 않았습니다. 실제 포트·VIP 접속은 별도 확인하세요.')
        return
    # Secret 내용은 stdin으로만 전달하고 kubectl 오류가 민감값을 출력하지 않게 한다.
    namespace = {'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': settings['NAMESPACE']}}
    run([*kube, 'apply', '-f', '-'], data=json.dumps(namespace))
    if certificate:
        run([*kube, 'apply', '--server-side', '--field-manager=airflow-tls', '-f', '-'], data=json.dumps(certificate), sensitive=True)
    access = {'apiVersion': 'v1', 'kind': 'List', 'items': routing.namespace_access(settings['NAMESPACE'], updated)}
    run([*kube, 'apply', '-f', '-'], data=json.dumps(access))
    print('Airflow 라우팅 권한 준비 완료. 배포 대상과 공용 Traefik을 적용합니다.', flush=True)
    run([*kube, 'apply', '-f', '-'], data=json.dumps({'apiVersion': 'v1', 'kind': 'List', 'items': desired}))
    workloads = [('statefulset', 'keycloak-postgres'), ('deployment', 'keycloak')] if deploy_keycloak else []
    for kind, name in [*workloads, ('deployment', 'traefik')]:
        run([*kube, '-n', 'etch-sso', 'rollout', 'status', f'{kind}/{name}', '--timeout=600s'])
    print('배포 대상 준비 완료. 신규 DAG를 일시정지한 Airflow를 배포합니다.', flush=True)
    airflow.deploy(settings, context, chart, pause_new_dags=True)
    print('Airflow 기동 완료. Airflow URL: ' + settings['AIRFLOW_WEBSERVER_BASE_URL'])
    print('기존 DB에서 복원한 DAG의 활성 상태는 유지됩니다. Portal 연동 전 업무 DAG를 실행하지 마세요.')


def main():
    """실행에 필요한 앱 파일과 명시적 context를 확인한다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context', required=True)
    parser.add_argument('--airflow-env', type=Path, default=ROOT / 'deploy/airflow/env/k8s.env')
    parser.add_argument('--tls-source', help='Airflow TLS Secret 최초 등록에 사용할 기존 namespace/secret')
    parser.add_argument('--vip-backends', help='443으로 연결된 Worker IPv4 목록. 쉼표로 구분하며 이후 생략하면 기존 목록 유지')
    parser.add_argument('--check-only', action='store_true', help='입력과 기존 클러스터를 조회·검사하고 적용하지 않음')
    args = parser.parse_args()
    airflow = module('airflow_deploy', ROOT / 'deploy/airflow/scripts/manage.py')
    routing = module('shared_routing', ROOT / 'deploy/shared/ingress/routing.py')
    start(airflow, routing, args.context, args.airflow_env, args.tls_source, args.vip_backends, args.check_only)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, StopIteration) as error:
        print(f'오류: {error}', file=sys.stderr)
        sys.exit(1)
