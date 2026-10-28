#!/usr/bin/env python3
"""기존 Keycloak을 보존하면서 공용 Traefik과 Airflow UI를 재적용한다.

최초 Secret·이미지·디스크는 서버에서 준비한다. 기존 Keycloak 인증값을 갱신하지 않는다.
모든 클러스터 명령은 명시한 context에만 실행하며 Git pull·push는 실행하지 않는다.
"""

import argparse
import base64
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[3]


spec = importlib.util.spec_from_file_location('deploy_runtime', ROOT / 'deploy/shared/scripts/runtime.py')
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)
module = runtime.module
render_json = runtime.render_json


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
    private_key = base64.b64decode(secret['data']['tls.key'], validate=True).decode()
    public = run(['openssl', 'x509', '-pubkey', '-noout'], data=certificate, sensitive=True)
    private_public = run(['openssl', 'pkey', '-passin', 'pass:', '-pubout'], data=private_key, sensitive=True)
    if not public.strip() or public.strip() != private_public.strip():
        raise ValueError('TLS 인증서와 개인키가 일치하지 않습니다.')
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
        # 최종 Pod 설정까지 확인한 뒤 공용 라우팅 변경을 준비한다.
        airflow.check_cluster_inputs(settings, context, Path(temporary) / 'airflow.yaml')
    run = airflow.run
    kube = ['kubectl', '--context', context]
    # 이미 구동 중인 Keycloak 전용 진입점이다. 자격증명 생성과 realm/mapper 변경은 실행하지 않는다.
    if deploy_keycloak:
        for kind, name in [('deployment', 'keycloak'), ('statefulset', 'keycloak-postgres'), ('secret', 'keycloak-runtime'), ('secret', 'keycloak-tls')]:
            run([*kube, '-n', 'etch-sso', 'get', kind, name, '-o', 'name'])
    current = json.loads(run([*kube, '-n', 'etch-sso', 'get', 'deployment', 'traefik', '-o', 'json']))
    if deploy_keycloak:
        desired = render_json(run, kube, ROOT / 'deploy/keycloak/k8s')
        original = routing.controller(desired)
        # 앱·DB는 기존 Worker에 유지하고 VIP 진입점만 여러 Worker로 확장한다.
        source_node = original['spec']['template']['spec'].get('nodeSelector', {})
        live_node = current['spec']['template']['spec'].get('nodeSelector', {})
        ips = routing.vip_backend_ips(vip_backends, current)
        if not ips:
            airflow.require(source_node == live_node and current['spec'].get('replicas', 1) == 1, '저장소와 기존 Traefik의 nodeSelector 또는 replicas가 다릅니다. 서버 배치 설정을 먼저 맞추세요.')
        airflow.require(settings['NODE_NAME'] == source_node.get('kubernetes.io/hostname'), 'Airflow NODE_NAME을 기존 앱 Worker로 유지하세요.')
        updated = routing.preserve_namespaces(original, current, settings['NAMESPACE'])
        if ips:
            nodes = json.loads(run([*kube, 'get', 'nodes', '-o', 'json']))['items']
            pods = json.loads(run([*kube, 'get', 'pods', '-A', '-o', 'json']))['items']
            updated = routing.place_vip_backends(updated, current, ips, nodes, pods)
            print('VIP Backend 배치: ' + ', '.join(ip + ':443' for ip in ips), flush=True)
        version = current['metadata'].get('resourceVersion')
        airflow.require(version, '동시 변경 검사에 필요한 Traefik resourceVersion이 없습니다.')
        updated['metadata']['resourceVersion'] = version
        desired = [updated if item is original else item for item in desired if item['kind'] != 'Namespace']
    else:
        # 단독 배포는 기존 Deployment 전체를 적용하지 않으며 패치의 입력만 먼저 검사한다.
        routing.namespace_patch(current, settings['NAMESPACE'])
    certificate = tls_for_airflow(run, kube, settings, tls_source)
    airflow.check_required_resources(settings, context, pending_tls=certificate)
    if check_only:
        print('설정·차트·기존 리소스·TLS·배치 검사 통과. 클러스터를 변경하지 않았습니다. 실제 포트·VIP 접속은 별도 확인하세요.')
        return
    # Secret 내용은 stdin으로만 전달하고 kubectl 오류가 민감값을 출력하지 않게 한다.
    existing_namespace = run([*kube, 'get', 'namespace', settings['NAMESPACE'], '--ignore-not-found', '-o', 'name'])
    if not existing_namespace.strip():
        # 기존 Namespace의 보안 정책과 운영 metadata는 수정하지 않는다.
        namespace = {'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': settings['NAMESPACE']}}
        run([*kube, 'create', '-f', '-'], data=json.dumps(namespace))
    if certificate:
        run([*kube, 'apply', '--server-side', '--field-manager=airflow-tls', '-f', '-'], data=json.dumps(certificate), sensitive=True)
    if not deploy_keycloak:
        # 사전 검사 중 다른 앱이 연결됐을 수 있으므로 최신 감시 목록에서 패치를 만든다.
        current = json.loads(run([*kube, '-n', 'etch-sso', 'get', 'deployment', 'traefik', '-o', 'json']))
        changes = routing.namespace_patch(current, settings['NAMESPACE'])
    identity = updated if deploy_keycloak else current
    access = {'apiVersion': 'v1', 'kind': 'List', 'items': routing.namespace_access(settings['NAMESPACE'], identity)}
    run([*kube, 'apply', '-f', '-'], data=json.dumps(access))
    print('Airflow 라우팅 권한 준비 완료. 배포 대상과 공용 Traefik을 적용합니다.', flush=True)
    if deploy_keycloak:
        run([*kube, 'apply', '-f', '-'], data=json.dumps({'apiVersion': 'v1', 'kind': 'List', 'items': desired}))
    elif changes:
        run([*kube, '-n', 'etch-sso', 'patch', 'deployment', 'traefik', '--type=json',
             '--patch', json.dumps(changes)])
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
