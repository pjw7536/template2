#!/usr/bin/env python3
"""고정 kube-prometheus-stack의 설정 검사·렌더·배포. Python 표준 라이브러리만 사용한다."""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.request import urlopen

BASE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('shared_tls', BASE.parent / 'shared/ingress/tls.py')
tls = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tls)

LOCK = json.loads((BASE / 'helm/chart.lock.json').read_text())
ENV_KEYS = frozenset(('NAMESPACE', 'NODE_NAME', 'DATA_HOST_PATH', 'DOCKER_REGISTRY', 'QUAY_REGISTRY', 'GHCR_REGISTRY', 'K8S_REGISTRY', 'IMAGE_PULL_SECRET', 'GRAFANA_ADMIN_SECRET', 'INGRESS_ENABLED', 'INGRESS_HOST', 'INGRESS_TLS_SECRET'))
VOLUMES = {'prometheus': ('20Gi', 'prometheus-monitoring-prometheus-db-prometheus-monitoring-prometheus-0'),
           'alertmanager': ('2Gi', 'alertmanager-monitoring-alertmanager-db-alertmanager-monitoring-alertmanager-0'),
           'grafana': ('5Gi', 'monitoring-grafana')}
STORAGE_OWNERS = {'prometheus': (1000, 2000), 'alertmanager': (1000, 2000), 'grafana': (472, 472)}


def require(condition, message):
    """실제 입력값을 노출하지 않고 오류를 보고한다."""
    if not condition:
        raise ValueError(message)


def run(args, data=None):
    """셸 확장 없이 명령을 실행하며 자격증명은 취급하지 않는다."""
    result = subprocess.run(list(map(str, args)), input=data, capture_output=True, text=True)
    require(result.returncode == 0, f'{Path(args[0]).name} 실행 실패: {result.stderr.strip()}')
    return result.stdout


def read_env(path):
    """dotenv를 실행하지 않고 중복·형식을 검사한다."""
    result = {}
    for line in Path(path).read_text().splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        key, separator, value = line.partition('=')
        require(separator and re.fullmatch('[A-Z_][A-Z0-9_]*', key) and key not in result, 'env 형식 또는 중복 키 오류')
        result[key] = value
    return result


def validate(settings, example=False):
    """서버별 경로와 registry·리소스 이름을 검증한다."""
    require(settings.keys() == ENV_KEYS, 'env 키가 설정 계약과 다릅니다.')
    for key, value in settings.items():
        if key in ('IMAGE_PULL_SECRET', 'INGRESS_HOST', 'INGRESS_TLS_SECRET') and not value:
            continue
        require(value and not any(c.isspace() for c in value), f'값 형식 오류: {key}')
        require(example or ('replace-me' not in value and 'example.invalid' not in value), f'실제 값 필요: {key}')
    for key in ('NAMESPACE', 'NODE_NAME', 'GRAFANA_ADMIN_SECRET', 'IMAGE_PULL_SECRET', 'INGRESS_TLS_SECRET'):
        if settings[key]:
            require(len(settings[key]) <= 63 and re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', settings[key]), f'리소스 이름 오류: {key}')
    require(settings['NAMESPACE'] not in ('default', 'kube-system', 'etch-sso', 'tailwind-internal'), 'Monitoring 전용 namespace를 지정하세요.')
    path = settings['DATA_HOST_PATH']
    require(path.startswith('/') and path != '/' and '..' not in path.split('/') and not path.endswith('/'), 'DATA_HOST_PATH는 전용 절대 경로여야 합니다.')
    for key in ('DOCKER_REGISTRY', 'QUAY_REGISTRY', 'GHCR_REGISTRY', 'K8S_REGISTRY'):
        require(re.fullmatch(r'[a-zA-Z0-9.-]+(?::[0-9]+)?(?:/[a-zA-Z0-9._-]+)*', settings[key]), f'registry 경로 오류: {key}')
    require(settings['INGRESS_ENABLED'] in ('true', 'false'), 'INGRESS_ENABLED는 true 또는 false여야 합니다.')
    if settings['INGRESS_ENABLED'] == 'true':
        host = settings['INGRESS_HOST']
        label = r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?'
        require(len(host) <= 253 and re.fullmatch(rf'{label}(?:\.{label})+', host), 'INGRESS_HOST에는 경로·scheme 없는 DNS 이름이 필요합니다.')


def version(value):
    """도구의 major·minor·patch를 추출한다."""
    match = re.search(r'(\d+)\.(\d+)\.(\d+)', value)
    require(match, '도구 버전을 확인할 수 없습니다.')
    return tuple(map(int, match.groups()))


def chart_path():
    """로컬 chart checksum과 Helm 버전을 확인한다. 자동 다운로드하지 않는다."""
    path = Path(os.environ.get('MONITORING_CHART_FILE', BASE / f'helm/vendor/kube-prometheus-stack-{LOCK["version"]}.tgz'))
    require(path.is_file(), 'Helm chart 준비 필요: fetch-chart 또는 MONITORING_CHART_FILE을 사용하세요.')
    require(hashlib.sha256(path.read_bytes()).hexdigest() == LOCK['sha256'], 'chart SHA-256 불일치')
    require(shutil.which('helm'), 'Helm 실행 파일 준비 필요')
    require(version(run(['helm', 'version', '--short'])) >= version(LOCK['helmVersion']), 'Helm 버전이 요구사항보다 낮습니다.')
    return path.resolve()


def values(settings):
    """서버 배치·Secret 참조·upstream별 mirror를 Helm에 전달한다."""
    node = {'kubernetes.io/hostname': settings['NODE_NAME']}
    registries = dict(zip(('docker', 'quay', 'ghcr', 'k8s'), (settings[k] for k in ('DOCKER_REGISTRY', 'QUAY_REGISTRY', 'GHCR_REGISTRY', 'K8S_REGISTRY'))))
    image = lambda name: {'registry': registries[name]}
    pull = [{'name': settings['IMAGE_PULL_SECRET']}] if settings['IMAGE_PULL_SECRET'] else []
    result = {
        'global': {'imagePullSecrets': pull},
        'grafana': {'nodeSelector': node, 'image': image('docker'), 'imagePullSecrets': pull,
                    'sidecar': {'image': image('quay')}, 'admin': {'existingSecret': settings['GRAFANA_ADMIN_SECRET']}},
        'prometheusOperator': {'nodeSelector': node, 'image': image('quay'),
            'prometheusConfigReloader': {'image': image('quay')},
            'admissionWebhooks': {'patch': {'image': image('ghcr'), 'nodeSelector': node},
                                  'deployment': {'image': image('quay'), 'nodeSelector': node}}},
        'kube-state-metrics': {'nodeSelector': node, 'image': image('k8s')},
        'prometheus-node-exporter': {'image': image('quay')},
    }
    dashboard = (BASE / 'dashboards/servers-overview.json').read_text()
    # chart의 tpl 처리 후에도 Grafana 범례의 이중 중괄호를 그대로 전달한다.
    dashboard_template = dashboard.replace('{{', '{{"{{"}}')
    dashboard_configmap = '{{ include "grafana.fullname" . }}-servers-overview'
    result['grafana'].update({
        'extraObjects': [{
            'apiVersion': 'v1', 'kind': 'ConfigMap',
            'metadata': {'name': dashboard_configmap, 'namespace': '{{ include "grafana.namespace" . }}',
                         'labels': {'grafana_dashboard': '1'}},
            'data': {'servers-overview.json': dashboard_template},
        }],
        'extraConfigmapMounts': [{
            'name': 'servers-overview-home', 'configMap': dashboard_configmap,
            'mountPath': '/etc/grafana/servers-overview', 'readOnly': True,
        }],
        'podAnnotations': {'checksum/servers-overview': hashlib.sha256(dashboard.encode()).hexdigest()},
        'grafana.ini': {'dashboards': {
            'default_home_dashboard_path': '/etc/grafana/servers-overview/servers-overview.json',
        }},
    })
    for component in ('prometheus', 'alertmanager'):
        storage = {'volumeClaimTemplate': {'spec': {
            'storageClassName': '', 'accessModes': ['ReadWriteOnce'],
            'volumeName': f'{settings["NAMESPACE"]}-monitoring-{component}',
            'resources': {'requests': {'storage': VOLUMES[component][0]}}}}}
        result[component] = {component + 'Spec': {'nodeSelector': node, 'image': image('quay'),
                           'imagePullSecrets': pull, 'storageSpec' if component == 'prometheus' else 'storage': storage}}
    if settings['INGRESS_ENABLED'] == 'true':
        host = settings['INGRESS_HOST']
        annotations = {'traefik.ingress.kubernetes.io/router.entrypoints': 'websecure',
                       'traefik.ingress.kubernetes.io/router.tls': 'true'}
        for component in VOLUMES:
            path = '/' + component
            ingress = {'enabled': True, 'ingressClassName': 'traefik', 'annotations': dict(annotations),
                       'hosts': [host], 'tls': [],
                       'pathType': 'Prefix'}
            if component == 'grafana':
                ingress['path'] = path
                result[component]['grafana.ini']['server'] = {
                    'root_url': f'https://{host}{path}/', 'serve_from_sub_path': True}
            else:
                ingress['paths'] = [path]
                result[component][component + 'Spec'].update(
                    externalUrl=f'https://{host}{path}', routePrefix=path)
            result[component]['ingress'] = ingress
    return result


def rendered_components(content):
    """고정 chart의 최상위 리소스 헤더만 읽어 활성 서비스와 실제 이름을 찾는다."""
    result = {}
    for document in re.split(r'^---[ \t]*(?:#.*)?$', content, flags=re.M):
        kind = re.search(r'^kind:[ \t]*([A-Za-z]+)[ \t]*$', document, re.M)
        if not kind:
            continue
        kind = kind[1]
        component = {'Prometheus': 'prometheus', 'Alertmanager': 'alertmanager'}.get(kind)
        grafana_source = re.search(
            r'^# Source: kube-prometheus-stack/charts/grafana/templates/(?:deployment|statefulset)\.yaml[ \t]*$',
            document, re.M)
        if grafana_source:
            require(kind in ('Deployment', 'StatefulSet'), 'Grafana 렌더의 workload 종류가 고정 chart 계약과 다릅니다.')
            component = 'grafana'
        if component is None:
            continue
        require(component not in result, '최종 렌더에 같은 Monitoring 서비스가 중복됐습니다.')
        metadata = re.search(r'^metadata:[ \t]*\n(.*?)(?=^[^\s#]|\Z)', document, re.M | re.S)
        require(metadata, 'Monitoring 렌더의 최상위 metadata가 없습니다.')
        fields = {}
        for key in ('name', 'namespace'):
            matches = re.findall(r'^  ' + key + r':[ \t]*([^\n]+)$', metadata[1], re.M)
            require(len(matches) <= 1 and (key != 'name' or matches), 'Monitoring 렌더의 metadata 이름이 없거나 중복됐습니다.')
            if matches:
                value = matches[0].strip()
                if value[:1] in ('"', "'") and value[-1:] == value[:1]:
                    value = value[1:-1]
                require(len(value) <= 253 and re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', value),
                        'Monitoring 렌더의 metadata 이름 형식이 올바르지 않습니다.')
                fields[key] = value
        result[component] = fields
    return result


def storage(settings, components=None):
    """단일 worker에 고정한 Retain local PV를 생성한다."""
    namespace = settings['NAMESPACE']
    if components is None:
        components = {name: {'name': 'monitoring-' + name} for name in VOLUMES}
    items = []
    for component, (size, claim) in VOLUMES.items():
        if component not in components:
            continue
        resource = components[component]
        target_namespace = resource.get('namespace', namespace)
        if component in ('prometheus', 'alertmanager'):
            workload = component + '-' + resource['name']
            claim = f'{workload}-db-{workload}-0'
        name = f'{namespace}-monitoring-{component}'
        items.append({'apiVersion': 'v1', 'kind': 'PersistentVolume', 'metadata': {'name': name}, 'spec': {
            'capacity': {'storage': size}, 'volumeMode': 'Filesystem', 'accessModes': ['ReadWriteOnce'],
            'persistentVolumeReclaimPolicy': 'Retain', 'storageClassName': '',
            'claimRef': {'namespace': target_namespace, 'name': claim},
            'local': {'path': settings['DATA_HOST_PATH'] + '/' + component},
            'nodeAffinity': {'required': {'nodeSelectorTerms': [{'matchExpressions': [
                {'key': 'kubernetes.io/hostname', 'operator': 'In', 'values': [settings['NODE_NAME']]}]}]}}}})
        if component == 'grafana':
            items.append({'apiVersion': 'v1', 'kind': 'PersistentVolumeClaim',
                'metadata': {'name': claim, 'namespace': target_namespace}, 'spec': {
                    'storageClassName': '', 'volumeName': name, 'accessModes': ['ReadWriteOnce'],
                    'resources': {'requests': {'storage': size}}}})
    return {'apiVersion': 'v1', 'kind': 'List', 'items': items}


def storage_job(settings, components, existing=()):
    """활성 서비스의 없는 폴더만 만들고 기존 폴더와 하위 파일 권한은 보존한다."""
    if not components:
        return None
    script = '''storage_root=$1
check_directory() {
    storage_path="$storage_root/$1"
    if [ -L "$storage_path" ] || { [ -e "$storage_path" ] && [ ! -d "$storage_path" ]; }; then
        printf '저장 경로가 디렉터리가 아니거나 심볼릭 링크입니다: %s\\n' "$storage_path" >&2
        exit 1
    fi
    if [ "$2" = existing ] && [ ! -d "$storage_path" ]; then
        printf '기존 PV의 저장 폴더가 없습니다. 디스크 마운트와 데이터를 확인하세요: %s\\n' "$storage_path" >&2
        exit 1
    fi
}
prepare_directory() {
    storage_path="$storage_root/$1"
    if [ ! -d "$storage_path" ]; then
        mkdir -m 0700 "$storage_path"
        chown "$2:$3" "$storage_path"
        chmod 0770 "$storage_path"
    fi
}
'''
    active = [name for name in VOLUMES if name in components]
    # 모든 기존 경로를 확인한 뒤 새 폴더 생성을 시작한다.
    script += '\n'.join(f'check_directory {name} {"existing" if name in existing else "new"}' for name in active) + '\n'
    script += '\n'.join(f'prepare_directory {name} {STORAGE_OWNERS[name][0]} {STORAGE_OWNERS[name][1]}' for name in active)
    pod = {'restartPolicy': 'Never', 'automountServiceAccountToken': False,
           'nodeSelector': {'kubernetes.io/hostname': settings['NODE_NAME']},
           'containers': [{'name': 'prepare', 'image': settings['DOCKER_REGISTRY'] + '/library/busybox:1.37.0',
                           'imagePullPolicy': 'IfNotPresent',
                           'command': ['/bin/sh', '-ec', script, 'monitoring-storage-prepare', '/data'],
                           'securityContext': {'runAsUser': 0, 'runAsGroup': 0, 'runAsNonRoot': False,
                                               'allowPrivilegeEscalation': False, 'readOnlyRootFilesystem': True,
                                               'capabilities': {'drop': ['ALL'], 'add': ['CHOWN', 'FOWNER', 'DAC_OVERRIDE']}},
                           'volumeMounts': [{'name': 'data', 'mountPath': '/data'}],
                           'resources': {'requests': {'cpu': '10m', 'memory': '16Mi'},
                                         'limits': {'cpu': '100m', 'memory': '64Mi'}}}],
           'volumes': [{'name': 'data', 'hostPath': {'path': settings['DATA_HOST_PATH'],
                       'type': 'Directory' if existing else 'DirectoryOrCreate'}}]}
    if settings['IMAGE_PULL_SECRET']:
        pod['imagePullSecrets'] = [{'name': settings['IMAGE_PULL_SECRET']}]
    return {'apiVersion': 'batch/v1', 'kind': 'Job',
            'metadata': {'generateName': 'monitoring-storage-prepare-', 'namespace': settings['NAMESPACE'],
                         'labels': {'app.kubernetes.io/name': 'monitoring-storage-prepare'}},
            'spec': {'backoffLimit': 0, 'activeDeadlineSeconds': 240, 'ttlSecondsAfterFinished': 600,
                     'template': {'spec': pod}}}


def prepare_storage(kube, settings, components, resources):
    """기존 PV의 위치를 확인하고 폴더 준비 Job 성공 후에만 배포를 계속한다."""
    if not components:
        return
    existing = set()
    for volume in resources['items']:
        if volume['kind'] != 'PersistentVolume':
            continue
        name = volume['metadata']['name']
        raw = run([*kube, 'get', 'pv', name, '--ignore-not-found', '-o', 'json'])
        if not raw.strip():
            continue
        current = json.loads(raw)['spec']
        expected = volume['spec']
        require(current.get('local') == expected['local'] and current.get('nodeAffinity') == expected['nodeAffinity'],
                '기존 Monitoring PV의 경로·노드가 다릅니다. 기존 DATA_HOST_PATH·NODE_NAME을 유지하세요.')
        reference = current.get('claimRef', {})
        require(not reference or all(reference.get(key) == expected['claimRef'][key] for key in ('namespace', 'name')),
                '기존 Monitoring PV가 다른 PVC에 예약되어 있습니다. 저장소 연결을 확인하세요.')
        existing.add(name.rsplit('-monitoring-', 1)[-1])
    manifest = json.dumps(storage_job(settings, components, existing))
    run([*kube, 'create', '--dry-run=server', '-f', '-'], data=manifest)
    job = json.loads(run([*kube, 'create', '-f', '-', '-o', 'json'], data=manifest))
    name = job['metadata']['name']
    print(f'Monitoring 저장 폴더 준비 대기: job/{name}. 실패 시 해당 Job의 Pod Events와 로그를 확인하세요.', flush=True)
    run([*kube, '-n', settings['NAMESPACE'], 'wait', '--for=condition=complete', f'job/{name}', '--timeout=300s'])


def render(settings, directory, chart, values_file=None):
    """공식 chart를 렌더하고 Operator가 생성할 이미지까지 목록으로 기록한다."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    overlay = directory / 'values.json'
    overlay.write_text(json.dumps(values(settings), indent=2) + '\n')
    flags = ['-n', settings['NAMESPACE'], '-f', BASE / 'helm/values.yaml', '-f', overlay]
    if values_file:
        flags += ['-f', values_file]
    run(['helm', 'lint', chart, *flags])
    content = run(['helm', 'template', 'monitoring', chart, '--include-crds', '--kube-version', LOCK['kubernetesVersion'], *flags])
    images = set(re.findall(r'^[ \t]*image:[ \t]*["\']?([^\s"\']+)', content, re.M))
    images.update(re.findall(r'--prometheus-config-reloader=([^\s"\']+)', content))
    components = rendered_components(content)
    job = storage_job(settings, components)
    if job:
        images.add(job['spec']['template']['spec']['containers'][0]['image'])
    prefixes = tuple(settings[key] + '/' for key in ('DOCKER_REGISTRY', 'QUAY_REGISTRY', 'GHCR_REGISTRY', 'K8S_REGISTRY'))
    require(images and all(item.startswith(prefixes) for item in images), '미러를 거치지 않는 렌더 이미지가 있습니다. values의 모든 이미지 설정을 확인하세요.')
    (directory / 'monitoring.yaml').write_text(content)
    (directory / 'images.txt').write_text('\n'.join(sorted(images)) + '\n')
    (directory / 'storage.json').write_text(json.dumps(storage(settings, components), indent=2) + '\n')
    return flags


def ingress_hosts(settings, content):
    """최종 렌더에 남은 공용 Traefik Ingress의 호스트를 찾는다."""
    hosts = set()
    for document in re.split(r'^---[ \t]*(?:#.*)?$', content, flags=re.M):
        if not re.search(r'^kind: Ingress\s*$', document, re.M):
            continue
        if not re.search(r"^  ingressClassName: [\"']?traefik[\"']?\s*$", document, re.M):
            continue
        namespace = re.search(r'^  namespace: ([^\n]+)', document, re.M)
        require(not namespace or namespace[1].strip(' \"\'') == settings['NAMESPACE'],
                '공용 Monitoring Ingress는 지정한 NAMESPACE에 있어야 합니다.')
        found = re.findall(r'^[ \t]+(?:-[ \t]+)?host: ([^\n]+)', document, re.M)
        require(found, '공용 Monitoring Ingress에는 도메인이 필요합니다.')
        hosts.update(host.strip(' \"\'') for host in found)
    return hosts


def connect_ingress(settings, context, content, dry_run=False):
    """TLS와 권한을 검사하고 기존 VIP·앱을 보존하며 감시 namespace만 추가한다."""
    hosts = ingress_hosts(settings, content)
    if not hosts:
        return
    kube = ['kubectl', '--context', context]
    namespace = settings['NAMESPACE']
    current = json.loads(run([*kube, '-n', 'etch-sso', 'get', 'deployment', 'traefik', '-o', 'json']))
    for host in sorted(hosts):
        tls.check(kube, host, current)
    spec = importlib.util.spec_from_file_location('monitoring_routing', BASE.parent / 'shared/ingress/routing.py')
    routing = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(routing)
    changes = routing.namespace_patch(current, namespace)
    access = {'apiVersion': 'v1', 'kind': 'List', 'items': routing.namespace_access(namespace, current)}
    extra = ['--dry-run=server'] if dry_run else []
    run([*kube, 'apply', '-f', '-', *extra], data=json.dumps(access))
    if changes:
        run([*kube, '-n', 'etch-sso', 'patch', 'deployment', 'traefik', '--type=json',
             '--patch', json.dumps(changes), *extra])
    if not dry_run:
        run([*kube, '-n', 'etch-sso', 'rollout', 'status', 'deployment/traefik', '--timeout=300s'])


def deploy(settings, context, chart, values_file=None):
    """기존 Operator 충돌·서버 입력 확인 후 저장 폴더·PV·Helm release를 준비한다."""
    require(context and context.strip(), 'deploy에는 --context를 명시하세요.')
    kube = ['kubectl', '--context', context]
    namespace = settings['NAMESPACE']
    with tempfile.TemporaryDirectory(prefix='monitoring-deploy-') as directory:
        flags = render(settings, directory, chart, values_file)
        content = (Path(directory) / 'monitoring.yaml').read_text()
        components = rendered_components(content)
        actual = json.loads(run([*kube, 'version', '-o', 'json']))['serverVersion']['gitVersion']
        require(version(actual) >= version(LOCK['kubernetesVersion']), 'Kubernetes 버전이 chart 요구사항보다 낮습니다.')
        releases = json.loads(run(['helm', 'list', '--kube-context', context, '-n', namespace, '--all', '-o', 'json']))
        release = next((item for item in releases if item['name'] == 'monitoring'), None)
        if release:
            require(release['chart'] == 'kube-prometheus-stack-' + LOCK['version'], '기존 chart 버전이 다릅니다. CRD upgrade 절차를 먼저 검토하세요.')
        else:
            existing = run([*kube, 'get', 'crd', 'prometheuses.monitoring.coreos.com', '--ignore-not-found', '-o', 'name'])
            require(not existing.strip(), '기존 Prometheus Operator CRD가 있습니다. 공용 Monitoring 사용 여부를 먼저 확인하세요.')
        nodes = json.loads(run([*kube, 'get', 'nodes', '-l', 'kubernetes.io/hostname=' + settings['NODE_NAME'], '-o', 'json']))['items']
        require(len(nodes) == 1, 'NODE_NAME에 대응하는 노드가 정확히 하나여야 합니다.')
        node = nodes[0]
        require(not node['spec'].get('unschedulable') and any(c['type'] == 'Ready' and c['status'] == 'True' for c in node['status']['conditions']), '대상 worker가 Ready·스케줄 가능 상태여야 합니다.')
        require(not any(t.get('effect') in ('NoSchedule', 'NoExecute') for t in node['spec'].get('taints', [])), '대상 worker의 차단 taint를 확인하세요.')
        # 비활성 Grafana에는 관리자 Secret을 요구하지 않으며 값 대신 키 이름만 조회한다.
        if 'grafana' in components:
            grafana_namespace = components['grafana'].get('namespace', namespace)
            keys = run([*kube, '-n', grafana_namespace, 'get', 'secret', settings['GRAFANA_ADMIN_SECRET'],
                        '-o', 'go-template={{range $k, $v := .data}}{{printf "%s\\n" $k}}{{end}}']).splitlines()
            require({'admin-user', 'admin-password'} <= set(keys), 'Grafana Secret에 admin-user·admin-password 키가 필요합니다.')
        if settings['IMAGE_PULL_SECRET']:
            run([*kube, '-n', namespace, 'get', 'secret', settings['IMAGE_PULL_SECRET'], '-o', 'name'])
        connect_ingress(settings, context, content, dry_run=True)
        resources = json.loads((Path(directory) / 'storage.json').read_text())
        prepare_storage(kube, settings, components, resources)
        if resources['items']:
            run([*kube, 'apply', '-f', Path(directory) / 'storage.json'])
        run(['helm', 'upgrade', '--install', 'monitoring', chart, '--kube-context', context, '--wait', '--timeout', '15m', *flags])
        for component in ('prometheus', 'alertmanager'):
            if component not in components:
                continue
            resource = components[component]
            target_namespace = resource.get('namespace', namespace)
            workload = 'statefulset/' + component + '-' + resource['name']
            # Operator가 비동기로 만드는 StatefulSet의 생성부터 기다립니다.
            run([*kube, '-n', target_namespace, 'wait', '--for=create', workload, '--timeout=600s'])
            run([*kube, '-n', target_namespace, 'rollout', 'status', workload, '--timeout=600s'])
        # Helm 실행 중 연결된 다른 앱을 보존하도록 최신 Deployment에서 패치를 계산한다.
        connect_ingress(settings, context, content)
    print('Monitoring 배포 완료. 활성화한 서비스의 접속·수집 상태를 확인하세요.')


def main():
    """다운로드와 검사·렌더·배포를 명시적으로 분리한다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('fetch-chart', 'check', 'render', 'deploy'))
    parser.add_argument('--env', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--context')
    parser.add_argument('--values', type=Path, help='환경별 비밀값 없는 Helm override')
    args = parser.parse_args()
    if args.command == 'fetch-chart':
        with urlopen(LOCK['url'], timeout=60) as response:
            content = response.read()
        require(hashlib.sha256(content).hexdigest() == LOCK['sha256'], '다운로드 chart SHA-256 불일치')
        target = BASE / f'helm/vendor/kube-prometheus-stack-{LOCK["version"]}.tgz'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        print('고정 chart 다운로드·SHA-256 검사 통과')
        return
    example = args.command == 'check' and args.env is None
    settings = read_env(args.env or BASE / 'env/k8s.env')
    validate(settings, example)
    chart = chart_path()
    if args.command == 'deploy':
        deploy(settings, args.context, chart, args.values)
    elif args.command == 'render':
        require(args.output, 'render에는 --output이 필요합니다.')
        render(settings, args.output, chart, args.values)
        print('렌더 완료. images.txt의 모든 이미지를 사내 미러에서 확인하세요.')
    else:
        with tempfile.TemporaryDirectory(prefix='monitoring-check-') as directory:
            render(settings, directory, chart, args.values)
        print('Monitoring Helm 원본 검사 통과' + (' (저장소 env 정적 검사; 실제 서버 검사는 별도)' if example else ' (실제 설정; 클러스터 적용 없음)'))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError) as error:
        print(f'오류: {error}', file=sys.stderr)
        sys.exit(1)
