"""공용 Traefik의 앱별 권한과 기존 namespace 감시 범위를 보존한다."""

from copy import deepcopy
from ipaddress import IPv4Address

PREFIX = '--providers.kubernetesingress.namespaces='
VIP_BACKENDS = 'deploy.tailwind.local/vip-backends'


def plan_controller(desired, current, requested, nodes, pods):
    """현재 감시·배치를 보존하고 실제 적용할 controller의 노드 수용 여부를 검사한다."""
    previous = current if current is not None else desired
    updated = preserve_namespaces(desired, previous, desired['metadata']['namespace'])
    if current is not None:
        for metadata in ('labels', 'annotations'):
            updated['metadata'][metadata] = {**deepcopy(current['metadata'].get(metadata, {})),
                                             **updated['metadata'].get(metadata, {})}
        updated['metadata'].get('annotations', {}).pop('kubectl.kubernetes.io/last-applied-configuration', None)
        version = current['metadata'].get('resourceVersion')
        if not version:
            raise ValueError('동시 변경 검사에 필요한 resourceVersion이 없습니다.')
        updated['metadata']['resourceVersion'] = version
        for key in ('replicas', 'strategy'):
            if key in current['spec']:
                updated['spec'][key] = deepcopy(current['spec'][key])
        target, live = updated['spec']['template'], current['spec']['template']
        # 보존한 affinity·topology selector가 참조하는 운영 label도 함께 유지한다.
        for metadata in ('labels', 'annotations'):
            merged = {**deepcopy(live.get('metadata', {}).get(metadata, {})),
                      **target.get('metadata', {}).get(metadata, {})}
            if merged:
                target.setdefault('metadata', {})[metadata] = merged
        for key in ('nodeSelector', 'affinity', 'tolerations', 'topologySpreadConstraints'):
            if key in live['spec']:
                target['spec'][key] = deepcopy(live['spec'][key])
            else:
                target['spec'].pop(key, None)
    ips = vip_backend_ips(requested, previous)
    if requested:
        updated = place_vip_backends(updated, previous, ips, nodes, pods)
    validate_placement(updated, nodes, pods, ips)
    return updated


def tolerates(taint, tolerations):
    """기존 Pod의 toleration이 스케줄링 차단 taint를 허용하는지 확인한다."""
    for item in tolerations:
        if item.get('effect') and item['effect'] != taint['effect']:
            continue
        if item.get('operator', 'Equal') == 'Exists':
            if not item.get('key') or item['key'] == taint['key']:
                return True
        elif item.get('key') == taint['key'] and item.get('value', '') == taint.get('value', ''):
            return True
    return False


def requirement_matches(requirement, values, field=False):
    """필수 node affinity의 Kubernetes 연산자를 해석하며 지원하지 않는 조건은 거부한다."""
    key, operator = requirement['key'], requirement['operator']
    expected = requirement.get('values', [])
    if field and (key != 'metadata.name' or operator not in ('In', 'NotIn') or len(expected) != 1):
        raise ValueError('required nodeAffinity matchFields는 metadata.name의 In·NotIn과 노드 이름 하나만 지원합니다.')
    if operator == 'In':
        return key in values and values[key] in expected
    if operator == 'NotIn':
        return key not in values or values[key] not in expected
    if operator == 'Exists':
        return key in values
    if operator == 'DoesNotExist':
        return key not in values
    if operator in ('Gt', 'Lt'):
        if len(expected) != 1:
            raise ValueError('required nodeAffinity Gt·Lt에는 정수 기준값 하나가 필요합니다.')
        try:
            threshold = int(expected[0])
        except (ValueError, TypeError):
            raise ValueError('required nodeAffinity Gt·Lt 기준값은 정수여야 합니다.') from None
        try:
            actual = int(values[key])
        except (KeyError, ValueError, TypeError):
            return False
        return actual > threshold if operator == 'Gt' else actual < threshold
    raise ValueError('지원하지 않는 required nodeAffinity 연산자입니다: ' + operator)


def node_matches(pod_settings, node):
    """nodeSelector와 필수 nodeAffinity의 AND·OR 조건을 실제 노드에 적용한다."""
    labels = node['metadata'].get('labels', {})
    if any(labels.get(key) != value for key, value in pod_settings.get('nodeSelector', {}).items()):
        return False
    affinity = pod_settings.get('affinity', {}).get('nodeAffinity', {})
    required = affinity.get('requiredDuringSchedulingIgnoredDuringExecution')
    if required is None:
        return True
    terms = []
    for term in required.get('nodeSelectorTerms', []):
        expressions = [requirement_matches(rule, labels) for rule in term.get('matchExpressions', [])]
        fields = [requirement_matches(rule, {'metadata.name': node['metadata']['name']}, field=True)
                  for rule in term.get('matchFields', [])]
        # 비어 있는 NodeSelectorTerm은 Kubernetes에서도 어떤 노드와도 일치하지 않는다.
        terms.append(bool(expressions or fields) and all(expressions + fields))
    return any(terms)


def eligible_nodes(deployment, nodes, pods):
    """정상 후보만 남겨 한 노드의 장애·포트 점유가 다른 정상 후보를 막지 않게 한다."""
    settings = deployment['spec']['template']['spec']
    result = []
    for node in nodes:
        if not node_matches(settings, node):
            continue
        status, spec = node.get('status', {}), node.get('spec', {})
        if (spec.get('unschedulable')
                or not any(item.get('type') == 'Ready' and item.get('status') == 'True'
                           for item in status.get('conditions', []))
                or any(taint.get('effect') in ('NoSchedule', 'NoExecute')
                       and not tolerates(taint, settings.get('tolerations', [])) for taint in spec.get('taints', []))):
            continue
        try:
            check_host_ports(deployment, {node['metadata']['name']}, pods)
        except ValueError:
            continue
        result.append(node)
    return result


def validate_placement(deployment, nodes, pods, ips=()):
    """hostPort를 공유할 수 없는 replica와 기록된 VIP의 실제 배치 범위를 검증한다."""
    replicas = deployment['spec'].get('replicas', 1)
    eligible = eligible_nodes(deployment, nodes, pods)
    if not isinstance(replicas, int) or replicas < 1 or len(eligible) < replicas:
        raise ValueError('Traefik replica 수만큼 Ready·배치 조건·80/443 포트를 만족하는 서로 다른 Worker가 필요합니다.')
    if not ips:
        return
    names = {node['metadata']['name'] for node in eligible}
    backends = []
    for ip in ips:
        matches = [node for node in nodes if any(address.get('type') == 'InternalIP' and address.get('address') == ip
                   for address in node.get('status', {}).get('addresses', []))]
        if len(matches) != 1 or matches[0]['metadata']['name'] not in names:
            raise ValueError(f'VIP Backend {ip}: 현재 배치 조건과 정상 Worker·80/443 포트를 확인하세요.')
        backends.append(matches[0])
    hostnames = [node['metadata'].get('labels', {}).get('kubernetes.io/hostname') for node in backends]
    if (len({node['metadata']['name'] for node in backends}) != len(ips)
            or not all(hostnames) or len(set(hostnames)) != len(ips)):
        raise ValueError('VIP Backend는 서로 다른 Worker·hostname으로 매핑되어야 합니다.')
    # 후보가 replica보다 많으면 기록된 Backend를 비운 채 다른 노드에만 배치될 수 있다.
    if replicas != len(eligible):
        raise ValueError('기록된 VIP Backend마다 배치할 수 있도록 replica 수와 필수 nodeAffinity 범위를 맞추세요. VIP_BACKENDS를 명시하면 배치를 다시 계산합니다.')


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
    check_host_ports(desired, names, pods)
    result = deepcopy(desired)
    result['metadata'].setdefault('annotations', {})[VIP_BACKENDS] = ','.join(ips)
    result['spec']['replicas'] = len(names)
    result['spec']['strategy'] = {'type': 'RollingUpdate', 'rollingUpdate': {'maxSurge': 0, 'maxUnavailable': 1}}
    spec = result['spec']['template']['spec']
    spec.pop('nodeSelector', None)
    spec['affinity'] = {
        'nodeAffinity': {'requiredDuringSchedulingIgnoredDuringExecution': {'nodeSelectorTerms': [
            {'matchFields': [{'key': 'metadata.name', 'operator': 'In', 'values': [name]}]}
            for name in sorted(names)]}},
        'podAntiAffinity': {'requiredDuringSchedulingIgnoredDuringExecution': [
            {'labelSelector': {'matchLabels': result['spec']['selector']['matchLabels']}, 'topologyKey': 'kubernetes.io/hostname'}]},
    }
    return result


def check_host_ports(deployment, names, pods):
    """선택 노드에서 공용 controller 이외 Pod의 선언된 80/443 충돌을 거부한다."""
    for pod in pods:
        if pod.get('status', {}).get('phase') in ('Succeeded', 'Failed') or pod.get('spec', {}).get('nodeName') not in names:
            continue
        metadata = pod.get('metadata', {})
        if metadata.get('namespace') == deployment['metadata']['namespace'] and metadata.get('labels', {}).get('app.kubernetes.io/name') == 'traefik':
            continue
        spec = pod['spec']
        for container in spec.get('containers', []) + spec.get('initContainers', []):
            for port in container.get('ports', []):
                number = port.get('hostPort') or (port.get('containerPort') if spec.get('hostNetwork') else None)
                if number in (80, 443) and port.get('protocol', 'TCP') == 'TCP':
                    raise ValueError(f"VIP Worker의 {number} 포트를 사용하는 Pod가 있습니다: {metadata.get('namespace')}/{metadata.get('name')}")


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


def namespace_patch(current, namespace):
    """동시 변경을 검사하며 기존 controller의 감시 인자만 확장한다."""
    containers = current['spec']['template']['spec']['containers']
    matches = [(index, item) for index, item in enumerate(containers) if item['name'] == 'traefik']
    if len(matches) != 1:
        raise ValueError('이름이 traefik인 컨테이너가 정확히 하나여야 합니다.')
    index, running = matches[0]
    existing = [arg for arg in running.get('args', []) if arg.startswith(PREFIX)]
    if len(existing) > 1:
        raise ValueError('Traefik namespace 인자가 중복되어 있습니다.')
    if not existing or existing[0] == PREFIX or namespace in existing[0][len(PREFIX):].split(','):
        return []
    version = current['metadata'].get('resourceVersion')
    if not version:
        raise ValueError('동시 변경 검사에 필요한 resourceVersion이 없습니다.')
    desired = preserve_namespaces(current, current, namespace)
    return [
        {'op': 'test', 'path': '/metadata/resourceVersion', 'value': version},
        {'op': 'replace', 'path': f'/spec/template/spec/containers/{index}/args',
         'value': desired['spec']['template']['spec']['containers'][index]['args']},
    ]
