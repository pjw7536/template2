"""Airflow UI를 공용 Traefik에 연결하고 Airflow를 배포한다.

공용 Traefik은 감시 namespace만 패치하고 배치·다른 앱의 연결은 바꾸지 않는다.
모든 클러스터 명령은 명시한 context에만 실행한다.
"""

import importlib.util
import json
from pathlib import Path
import tempfile
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[3]


spec = importlib.util.spec_from_file_location('deploy_runtime', ROOT / 'deploy/shared/scripts/runtime.py')
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)
module = runtime.module


tls = module('shared_tls', ROOT / 'deploy/shared/ingress/tls.py')


def tls_for_airflow(kube, settings, source):
    """공개 host의 인증서를 공용 TLS 저장소에서 확인하며 앱 namespace에는 복제하지 않는다."""
    host = urlsplit(settings['AIRFLOW_WEBSERVER_BASE_URL']).hostname
    return tls.prepare(kube, host, source=source)


def start(airflow, routing, context, env, tls_source=None, check_only=False, pending_configmaps=()):
    """모든 입력을 검사한 뒤 namespace 권한 → 공용 Traefik 감시 범위 → Airflow 순서로 적용한다."""
    airflow.require(context, '--context를 명시하세요.')
    settings = airflow.read_env(env)
    airflow.validate(settings)
    airflow.require(settings['INGRESS_ENABLED'] == 'true' and settings['INGRESS_CLASS_NAME'] == 'traefik',
                    '공용 Traefik 연결에는 INGRESS_ENABLED=true, INGRESS_CLASS_NAME=traefik이 필요합니다.')
    airflow.require(settings['NAMESPACE'] != 'etch-sso', 'Airflow는 Keycloak과 별도의 namespace를 사용하세요.')
    airflow.require(urlsplit(settings['AIRFLOW_WEBSERVER_BASE_URL']).scheme == 'https', 'Airflow 공개 URL은 HTTPS여야 합니다.')
    chart = airflow.chart_path()
    with tempfile.TemporaryDirectory(prefix='airflow-check-') as temporary:
        airflow.render(settings, temporary, chart, pause_new_dags=True)
        # 최종 Pod 설정까지 확인한 뒤 공용 라우팅 변경을 준비한다.
        airflow.check_cluster_inputs(settings, context, Path(temporary) / 'airflow.yaml')
    run = airflow.run
    kube = ['kubectl', '--context', context]
    current = json.loads(run([*kube, '-n', 'etch-sso', 'get', 'deployment', 'traefik', '-o', 'json']))
    # 공용 Deployment 전체를 적용하지 않으며 패치의 입력만 먼저 검사한다.
    routing.namespace_patch(current, settings['NAMESPACE'])
    certificate = tls_for_airflow(kube, settings, tls_source)
    tls.check_mount(current)
    airflow.check_required_resources(settings, context, pending_configmaps=pending_configmaps)
    if check_only:
        print('설정·차트·기존 리소스·TLS·배치 검사 통과. 클러스터를 변경하지 않았습니다. 실제 포트·VIP 접속은 별도 확인하세요.')
        return
    existing_namespace = run([*kube, 'get', 'namespace', settings['NAMESPACE'], '--ignore-not-found', '-o', 'name'])
    if not existing_namespace.strip():
        # 이미 있는 Namespace의 보안 정책과 운영 metadata는 수정하지 않는다.
        namespace = {'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': settings['NAMESPACE']}}
        run([*kube, 'create', '-f', '-'], data=json.dumps(namespace))
    if tls_source:
        tls.save(kube, certificate, restart=True)
    # 사전 검사 중 다른 앱이 연결됐을 수 있으므로 최신 감시 목록에서 패치를 만든다.
    current = json.loads(run([*kube, '-n', 'etch-sso', 'get', 'deployment', 'traefik', '-o', 'json']))
    changes = routing.namespace_patch(current, settings['NAMESPACE'])
    access = {'apiVersion': 'v1', 'kind': 'List', 'items': routing.namespace_access(settings['NAMESPACE'], current)}
    run([*kube, 'apply', '-f', '-'], data=json.dumps(access))
    print('Airflow 라우팅 권한 준비 완료. 공용 Traefik의 감시 범위를 확인합니다.', flush=True)
    if changes:
        run([*kube, '-n', 'etch-sso', 'patch', 'deployment', 'traefik', '--type=json',
             '--patch', json.dumps(changes)])
    run([*kube, '-n', 'etch-sso', 'rollout', 'status', 'deployment/traefik', '--timeout=600s'])
    print('공용 Traefik 준비 완료. 신규 DAG를 일시정지한 Airflow를 배포합니다.', flush=True)
    airflow.deploy(settings, context, chart, pause_new_dags=True)
    print('Airflow 기동 완료. Airflow URL: ' + settings['AIRFLOW_WEBSERVER_BASE_URL'])
    print('DB에 이미 등록된 DAG의 활성 상태는 유지됩니다. Portal 연동 전 업무 DAG를 실행하지 마세요.')
