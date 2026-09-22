"""공용 Traefik의 앱별 권한과 기존 namespace 감시 범위를 보존한다."""

from copy import deepcopy
from ipaddress import IPv4Address

PREFIX = '--providers.kubernetesingress.namespaces='
VIP_BACKENDS = 'deploy.tailwind.local/vip-backends'


def vip_backend_ips(requested, current):
    """명시한 IP 또는 이전 적용 annotation을 읽고 중복·형식을 검사한다."""
    raw = requested or current.get('metadata', {}).get('annotations', {}).get(VIP_BACKENDS, '')
    if not raw:
        return []
    ips = [str(IPv4Address(value.strip())) for value in raw.split(',')]
    if len(ips) < 2 or len(ips) != len(set(ips)):
        raise ValueError('VIP Backend는 서로 다른 Worker IPv4 주소를 두 개 이상 지정하세요.')
    return sorted(ips)


def place_vip_backends(desired, current, ips, nodes, pods):
    """확인한 Backend마다 Traefik 하나를 배치한다. 입력을 수정하지 않는다.

    알 수 없는 IP·사용 불가능한 노드·기존 진입점 제거·Pod 포트 충돌은 ValueError로 차단한다.
    노드 OS 프로세스의 포트 점유는 Kubernetes 조회로 확인할 수 없어 서버 점검이 필요하다.
    """
    selected = []
    for ip in ips:
        matches = [node for node in nodes if any(address.get('type') == 'InternalIP' and address.get('address') == ip
                   for address in node.get('status', {}).get('addresses', []))]
        if len(matches) != 1:
            raise ValueError(f'VIP Backend {ip}: InternalIP가 일치하는 Node가 정확히 하나여야 합니다.')
        node = matches[0]
        spec, status = node.get('spec', {}), node.get('status', {})
        if spec.get('unschedulable') or not any(c.get('type') == 'Ready' and c.get('status') == 'True' for c in status.get('conditions', [])):
            raise ValueError(f'VIP Backend {ip}: Ready이며 스케줄 가능한 Worker가 필요합니다.')
        if any(taint.get('effect') in ('NoSchedule', 'NoExecute') for taint in spec.get('taints', [])):
            raise ValueError(f'VIP Backend {ip}: 스케줄링을 차단하는 taint를 먼저 확인하세요.')
        if not node['metadata'].get('labels', {}).get('kubernetes.io/hostname'):
            raise ValueError(f'VIP Backend {ip}: hostname label이 없습니다.')
        selected.append(node)
    names = [node['metadata']['name'] for node in selected]
    hostnames = [node['metadata']['labels']['kubernetes.io/hostname'] for node in selected]
    if len(set(names)) != len(ips) or len(set(hostnames)) != len(ips):
        raise ValueError('VIP Backend가 서로 다른 Worker·hostname으로 매핑되어야 합니다.')
    # 현재 직결 DNS의 진입점과 이전 VIP Backend를 묵시적으로 제거하지 않는다.
    for deployment in (desired, current):
        hostname = deployment['spec']['template']['spec'].get('nodeSelector', {}).get('kubernetes.io/hostname')
        if hostname and hostname not in hostnames:
            raise ValueError('VIP Backend에 기존 Traefik Worker를 포함해야 합니다.')
    previous = vip_backend_ips('', current)
    if not set(previous) <= set(ips):
        raise ValueError('기존 VIP Backend 제거는 LB 전환을 포함한 별도 절차가 필요합니다.')
    for pod in pods:
        if pod.get('status', {}).get('phase') in ('Succeeded', 'Failed') or pod.get('spec', {}).get('nodeName') not in names:
            continue
        metadata = pod.get('metadata', {})
        if metadata.get('namespace') == desired['metadata']['namespace'] and metadata.get('labels', {}).get('app.kubernetes.io/name') == 'traefik':
            continue
        spec = pod['spec']
        for container in spec.get('containers', []) + spec.get('initContainers', []):
            for port in container.get('ports', []):
                number = port.get('hostPort') or (port.get('containerPort') if spec.get('hostNetwork') else None)
                if number in (80, 443) and port.get('protocol', 'TCP') == 'TCP':
                    raise ValueError(f"VIP Worker의 {number} 포트를 사용하는 Pod가 있습니다: {metadata.get('namespace')}/{metadata.get('name')}")
    result = deepcopy(desired)
    result['metadata'].setdefault('annotations', {})[VIP_BACKENDS] = ','.join(ips)
    result['spec']['replicas'] = len(names)
    result['spec']['strategy'] = {'type': 'RollingUpdate', 'rollingUpdate': {'maxSurge': 0, 'maxUnavailable': 1}}
    spec = result['spec']['template']['spec']
    spec.pop('nodeSelector', None)
    spec['affinity'] = {
        'nodeAffinity': {'requiredDuringSchedulingIgnoredDuringExecution': {'nodeSelectorTerms': [
            {'matchFields': [{'key': 'metadata.name', 'operator': 'In', 'values': sorted(names)}]}]}},
        'podAntiAffinity': {'requiredDuringSchedulingIgnoredDuringExecution': [
            {'labelSelector': {'matchLabels': result['spec']['selector']['matchLabels']}, 'topologyKey': 'kubernetes.io/hostname'}]},
    }
    return result


def controller(items):
    """기존 리소스 이름을 사용하는 Traefik Deployment 하나를 찾는다."""
    matches = [item for item in items if item['kind'] == 'Deployment' and item['metadata']['name'] == 'traefik']
    if len(matches) != 1:
        raise ValueError('Traefik Deployment가 정확히 하나여야 합니다.')
    return matches[0]


def preserve_namespaces(desired, current, namespace):
    """현재 감시 범위를 좁히지 않고 앱 namespace를 추가한다."""
    result = deepcopy(desired)
    target = next(item for item in result['spec']['template']['spec']['containers'] if item['name'] == 'traefik')
    running = next(item for item in current['spec']['template']['spec']['containers'] if item['name'] == 'traefik')
    existing = [arg for arg in running.get('args', []) if arg.startswith(PREFIX)]
    if len(existing) > 1:
        raise ValueError('Traefik namespace 인자가 중복되어 있습니다.')
    args = target['args']
    defaults = next((arg[len(PREFIX):].split(',') for arg in args if arg.startswith(PREFIX)), [])
    # namespace 인자가 없거나 비어 있으면 이미 전체 namespace를 감시하는 상태다.
    if not existing or existing[0] == PREFIX:
        target['args'] = [arg for arg in args if not arg.startswith(PREFIX)]
        return result
    watched = list(dict.fromkeys([*existing[0][len(PREFIX):].split(','), *defaults, namespace]))
    target['args'] = [arg for arg in args if not arg.startswith(PREFIX)]
    target['args'].insert(2, PREFIX + ','.join(watched))
    return result


def namespace_access(namespace, deployment):
    """지정 앱의 라우팅 리소스에만 접근하는 Role과 RoleBinding을 만든다."""
    metadata = {'name': 'shared-traefik', 'namespace': namespace}
    rules = [
        {'apiGroups': [''], 'resources': ['services', 'endpoints', 'secrets'], 'verbs': ['get', 'list', 'watch']},
        {'apiGroups': ['discovery.k8s.io'], 'resources': ['endpointslices'], 'verbs': ['get', 'list', 'watch']},
        {'apiGroups': ['networking.k8s.io'], 'resources': ['ingresses', 'ingresses/status'], 'verbs': ['get', 'list', 'watch', 'update']},
        {'apiGroups': [''], 'resources': ['events'], 'verbs': ['create', 'patch', 'update']},
    ]
    return [
        {'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'Role', 'metadata': metadata, 'rules': rules},
        {'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'RoleBinding', 'metadata': metadata,
         'roleRef': {'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'Role', 'name': 'shared-traefik'},
         'subjects': [{'kind': 'ServiceAccount', 'name': deployment['spec']['template']['spec']['serviceAccountName'], 'namespace': deployment['metadata']['namespace']}]},
    ]
