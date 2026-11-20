#!/usr/bin/env python3
"""사내 서버 상태를 고정 양식으로 모으고 서버명·IP·사내 도메인을 별칭으로 바꿔 출력한다(조회 전용).

- report: 클러스터·노드·공용 진입점·앱별 상태를 Markdown으로 만든다. 외부로 전달하는 것은 이 출력뿐이다.
- redact: 표준 입력의 임의 텍스트를 같은 별칭 규칙으로 바꾼다. 추가 확인 결과를 보고서에 붙일 때 쓴다.

별칭 표는 `deploy/shared/docs/infrastructure/aliases.json`이다. 표에 없는 노드·IPv4·사내 도메인은
`N-미등록-n`, `IP-미등록-n`, `HOST-미등록-n`으로 바꾸고 실제 값은 표준 오류에만 알린다.
Secret·env 값, Pod IP, 사용자 계정은 수집하지 않는다.
"""

import argparse
import datetime
import json
from pathlib import Path
import re
import socket
import ssl
import subprocess
import sys

import ca_bundle
import deploy_state as state
import smoke as smoke_checks

ALIASES = state.ROOT / 'deploy/shared/docs/infrastructure/aliases.json'
LAYOUT_VERSION = 1
# 문장 끝의 마침표가 뒤따라도 주소로 본다. 뒤에 숫자가 더 이어질 때만 주소가 아니다.
IPV4 = re.compile(r'(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?!\d)(?!\.\d)')
TIMEOUT = 8


class Redactor:
    """별칭 표의 실제 값을 별칭으로 바꾸고 표에 없는 값은 번호를 붙인 자리표시로 바꾼다."""

    def __init__(self, table):
        self.table = table
        self.version = table['version']
        self.literals = {}
        for alias, item in table['nodes'].items():
            self.literals[item['name']] = alias
            self.literals[item['ip']] = alias
        for alias, item in table['addresses'].items():
            self.literals[item['ip']] = alias
        self.domains = {item['value']: alias for alias, item in table['domains'].items()}
        self.suffix = min(self.domains, key=len)
        # 별칭 표의 `otherSuffixes`: 위 접미사 밖의 사내 도메인. 그 아래의 host는 이름 전체를 가린다.
        self.other_suffixes = list(table.get('otherSuffixes', []))
        self.unmapped = {}

    def register_nodes(self, names):
        """클러스터에는 있지만 표에 없는 노드 이름에 임시 별칭을 준다."""
        for name in sorted(names):
            if name not in self.literals:
                self.literals[name] = self._unknown('N', name)

    def _unknown(self, kind, value):
        key = (kind, value)
        if key not in self.unmapped:
            self.unmapped[key] = f'{kind}-미등록-{sum(1 for item in self.unmapped if item[0] == kind) + 1}'
        return self.unmapped[key]

    def text(self, value):
        """긴 값부터 바꾼다. 주소는 숫자 경계, 이름은 뒤 경계가 맞을 때만 바꿔 다른 값의 일부를 별칭으로 만들지 않는다."""
        for literal in sorted(self.literals, key=len, reverse=True):
            if IPV4.fullmatch(literal):
                pattern = r'(?<![\d.])' + re.escape(literal) + r'(?![\d.]*\d)'
            else:
                # Pod 이름처럼 노드 이름이 뒤에 붙는 경우가 있어 앞 경계는 두지 않는다.
                pattern = re.escape(literal) + r'(?![A-Za-z0-9])'
            value = re.sub(pattern, self.literals[literal], value, flags=re.IGNORECASE)
        for domain in sorted(self.domains, key=len, reverse=True):
            if domain != self.suffix:
                value = re.sub(re.escape(domain), self.domains[domain], value, flags=re.IGNORECASE)
        # 표에 없는 사내 host는 이름 전체를 가린다.
        pattern = re.compile(r'(?:[A-Za-z0-9-]+\.)+' + re.escape(self.suffix), re.IGNORECASE)
        value = pattern.sub(lambda match: self._unknown('HOST', match[0].lower()), value)
        value = re.sub(re.escape(self.suffix), self.domains[self.suffix], value, flags=re.IGNORECASE)
        for suffix in self.other_suffixes:
            other = re.compile(r'(?:[A-Za-z0-9-]+\.)*' + re.escape(suffix), re.IGNORECASE)
            value = other.sub(lambda match: self._unknown('HOST', match[0].lower()), value)
        return IPV4.sub(lambda match: self._unknown('IP', match[0]), value)

    def short(self, value, limit):
        """치환한 뒤에 자른다. 먼저 자르면 주소·이름의 일부가 남을 수 있다."""
        return self.text(str(value))[:limit]


def command_version(command):
    """관리 호스트 도구의 버전 한 줄을 조회한다."""
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=15)
        return (result.stdout or result.stderr).strip().splitlines()[0] if result.returncode == 0 else '실행 실패'
    except (OSError, subprocess.TimeoutExpired, IndexError):
        return '없음'


def attempt(errors, label, action, default=None):
    """조회 하나의 실패를 보고서의 `확인하지 못한 항목`으로 남기고 계속한다."""
    try:
        return action()
    except (state.QueryError, ValueError, KeyError, OSError, IndexError) as error:
        errors.append(f'{label}: {error}')
        return default


def quantity(value):
    """Kubernetes 메모리 수량을 GiB로 바꾼다."""
    units = {'Ki': 2 ** 10, 'Mi': 2 ** 20, 'Gi': 2 ** 30, 'Ti': 2 ** 40}
    for unit, factor in units.items():
        if str(value).endswith(unit):
            return f'{int(value[:-2]) * factor / 2 ** 30:.0f}GiB'
    return str(value)


def gib(value):
    return '조회 불가' if value is None else f'{value / 2 ** 30:.0f}GiB'


def table(headers, rows):
    """Markdown 표를 만든다. 셀의 세로선과 줄바꿈은 표를 깨지 않게 바꾼다."""
    clean = lambda cell: str(cell).replace('|', '/').replace('\n', ' ')
    lines = ['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join('---' for _ in headers) + ' |']
    lines.extend('| ' + ' | '.join(clean(cell) for cell in row) + ' |' for row in rows)
    return lines if rows else ['없음']


def node_rows(kube, nodes, errors):
    """노드별 준비 상태·버전·자원·디스크 여유를 모은다."""
    rows = []
    for node in nodes:
        name, status, labels = node['metadata']['name'], node['status'], node['metadata'].get('labels', {})
        ready = next((c['status'] for c in status.get('conditions', []) if c['type'] == 'Ready'), 'Unknown')
        info = status.get('nodeInfo', {})
        roles = sorted(key.rpartition('/')[2] for key in labels if key.startswith('node-role.kubernetes.io/')) or ['worker']
        taints = ', '.join(f'{t["key"]}:{t.get("effect", "")}' for t in node['spec'].get('taints', [])) or '-'
        summary = attempt(errors, f'{name} 디스크 조회',
                          lambda: json.loads(kube(['get', '--raw', f'/api/v1/nodes/{name}/proxy/stats/summary'])), {})
        filesystem = (summary.get('node') or {}).get('fs') or {}
        rows.append([name, '·'.join(roles), ready, '불가' if node['spec'].get('unschedulable') else '가능',
                     info.get('kubeletVersion', ''), info.get('osImage', ''), info.get('kernelVersion', ''),
                     info.get('containerRuntimeVersion', ''), status.get('capacity', {}).get('cpu', ''),
                     quantity(status.get('capacity', {}).get('memory', '')),
                     f'{gib(filesystem.get("availableBytes"))} / {gib(filesystem.get("capacityBytes"))}', taints,
                     labels.get('etch.io/ftp-enabled', '-')])
    return rows


def cluster_rows(kube, nodes, errors):
    """클러스터 공통 구성의 적용 여부를 모은다."""
    ready = sum(1 for node in nodes if any(c['type'] == 'Ready' and c['status'] == 'True' for c in node['status'].get('conditions', [])))
    version = attempt(errors, 'API server 버전', lambda: json.loads(kube(['version', '-o', 'json']))['serverVersion']['gitVersion'], '조회 불가')
    names = lambda kind: attempt(errors, f'{kind} 조회', lambda: ', '.join(
        item['metadata']['name'] for item in json.loads(kube(['get', kind, '-o', 'json']))['items']) or '없음', '조회 불가')
    metrics = attempt(errors, 'metrics API', lambda: next(
        (c['status'] for c in json.loads(kube(['get', 'apiservice', 'v1beta1.metrics.k8s.io', '-o', 'json']))['status']['conditions']
         if c['type'] == 'Available'), 'Unknown'), '미설치 또는 조회 불가')
    servers = attempt(errors, 'kube-apiserver Pod', lambda: json.loads(
        kube(['-n', 'kube-system', 'get', 'pods', '-l', 'component=kube-apiserver', '-o', 'json']))['items'], [])
    oidc = sorted({arg for pod in servers for container in pod['spec']['containers']
                   for arg in container.get('command', []) + container.get('args', []) if arg.startswith('--oidc-')})
    return [['API server 버전', version], ['노드 Ready', f'{ready}/{len(nodes)}'], ['metrics API Available', metrics],
            ['StorageClass', names('storageclass')], ['IngressClass', names('ingressclass')],
            ['API server OIDC 인자', ', '.join(oidc) if oidc else ('설정 없음' if servers else '조회 불가')]]


def endpoint(host, cadata, connect=None):
    """host의 DNS 결과와 HTTPS 인증서 검증·만료일을 확인한다."""
    try:
        addresses = sorted({item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)})
        dns = ', '.join(addresses)
    except OSError:
        addresses, dns = [], 'DNS 조회 실패'
    target = connect or (addresses[0] if addresses else None)
    if not target:
        return dns, '연결 대상 없음'
    context = ssl.create_default_context()
    if cadata:
        context.load_verify_locations(cadata=cadata)
    try:
        with socket.create_connection((target, 443), timeout=TIMEOUT) as raw, context.wrap_socket(raw, server_hostname=host) as secured:
            return dns, '검증 통과, 만료 ' + secured.getpeercert().get('notAfter', '알 수 없음')
    except ssl.SSLError as error:
        return dns, 'TLS 검증 실패: ' + (getattr(error, 'verify_message', '') or getattr(error, 'reason', '') or type(error).__name__)
    except OSError as error:
        return dns, f'연결 실패: {type(error).__name__}'


def ingress_section(kube, cadata, vip, errors):
    """공용 Traefik의 배치와 감시 범위, APP VIP 연결을 모은다."""
    scoped = ['-n', 'etch-sso']
    deployment = attempt(errors, '공용 Traefik 조회', lambda: json.loads(kube([*scoped, 'get', 'deployment', 'traefik', '-o', 'json'])))
    if not deployment:
        return [['공용 Traefik', '없음 또는 조회 불가']]
    container = next(c for c in deployment['spec']['template']['spec']['containers'] if c['name'] == 'traefik')
    watched = next((arg.split('=', 1)[1] for arg in container.get('args', []) if arg.startswith('--providers.kubernetesingress.namespaces')), '전체')
    pods = attempt(errors, 'Traefik Pod 조회', lambda: json.loads(
        kube([*scoped, 'get', 'pods', '-l', 'app.kubernetes.io/name=traefik', '-o', 'json']))['items'], [])
    placed = ', '.join(sorted(f'{pod["spec"].get("nodeName", "미배치")}({pod["status"].get("phase", "")})' for pod in pods)) or '없음'
    rows = [['Ready', f'{deployment.get("status", {}).get("readyReplicas", 0)}/{deployment["spec"].get("replicas", 1)}'],
            ['이미지', container['image']], ['배치 노드', placed], ['감시 namespace', watched]]
    if vip:
        rows.append([f'APP VIP 443 연결({vip})', smoke_checks.tcp_check(vip, 443)['detail']])
    return rows


def app_section(name, app, kube, git, checkout, options, cadata, vip, errors, redactor):
    """한 앱의 배포 기록·대조·워크로드·저장소·공개 주소 상태를 모은다."""
    lines = [f'### {name}', '']
    result = state.check_app(name, app, git, kube, checkout, options) if options else None
    namespace = (result or {}).get('namespace') or app['runtime']['namespace']
    selector = app['runtime'].get('selector', '')
    exists = attempt(errors, f'{name} namespace 조회',
                     lambda: bool(kube(['get', 'namespace', namespace, '--ignore-not-found', '-o', 'name']).strip()), False)
    rows = [['namespace', f'{namespace} ({"있음" if exists else "없음"})']]
    if result:
        code = state.exit_code([result])
        rows.append(['배포 기록', f'commit {result["deployedCommit"][:12]}, 적용 {result["appliedAt"]}' if result['deployedCommit'] else '없음'])
        rows.append(['대조 판정', {0: '0 일치', 1: '1 불일치·경고', 2: '2 판정 불가'}[code]])
    lines += table(['항목', '값'], rows) + ['']
    if result:
        findings = [item for item in result['findings'] if item['level'] != 'ok']
        lines += ['대조 근거:'] + ([f'- {item["level"].upper()} {item["area"]}: {item["message"]}' for item in findings] or ['- 없음']) + ['']
    if not exists:
        return lines
    workloads = attempt(errors, f'{name} 워크로드 조회', lambda: state.workload_snapshot(kube, namespace, selector), {})
    lines += ['워크로드:'] + table(['이름', 'Ready', '이미지'], [
        [key, f'{value["ready"]}/{value["desired"]}', ', '.join(value['images'])] for key, value in sorted(workloads.items())]) + ['']
    label = ['-l', selector] if selector else []
    pods = attempt(errors, f'{name} Pod 조회', lambda: json.loads(kube(['-n', namespace, 'get', 'pods', '-o', 'json', *label]))['items'], [])
    placement = {}
    for pod in pods:
        entry = placement.setdefault(pod['spec'].get('nodeName', '미배치'), {'count': 0, 'restarts': 0, 'phases': set()})
        entry['count'] += 1
        entry['phases'].add(pod['status'].get('phase', 'Unknown'))
        entry['restarts'] += sum(c.get('restartCount', 0) for c in pod['status'].get('containerStatuses', []) or [])
    lines += ['Pod 배치:'] + table(['노드', 'Pod 수', '상태', '재시작 합계'], [
        [node, entry['count'], '·'.join(sorted(entry['phases'])), entry['restarts']] for node, entry in sorted(placement.items())]) + ['']
    claims = attempt(errors, f'{name} PVC 조회', lambda: json.loads(kube(['-n', namespace, 'get', 'pvc', '-o', 'json']))['items'], [])
    volumes = {item['metadata']['name']: item for item in attempt(
        errors, 'PV 조회', lambda: json.loads(kube(['get', 'pv', '-o', 'json']))['items'], [])}
    storage = []
    for claim in claims:
        volume = volumes.get(claim['spec'].get('volumeName', ''), {}).get('spec', {})
        terms = volume.get('nodeAffinity', {}).get('required', {}).get('nodeSelectorTerms', [])
        nodes = ', '.join(value for term in terms for expression in term.get('matchExpressions', []) for value in expression.get('values', []))
        storage.append([claim['metadata']['name'], claim['status'].get('phase', ''), claim['status'].get('capacity', {}).get('storage', ''),
                        (volume.get('local') or volume.get('hostPath') or {}).get('path', volume.get('storageClassName', '') or '-'), nodes or '-'])
    lines += ['저장소:'] + table(['PVC', '상태', '용량', '경로·StorageClass', '노드'], storage) + ['']
    ingresses = attempt(errors, f'{name} Ingress 조회', lambda: json.loads(kube(['-n', namespace, 'get', 'ingress', '-o', 'json']))['items'], [])
    hosts = sorted({rule['host'] for item in ingresses for rule in item['spec'].get('rules', []) if rule.get('host')})
    settings = app.get('smoke', {})
    address_rows = []
    for host in hosts:
        dns, certificate = endpoint(host, cadata, vip if vip else None)
        http = smoke_checks.http_check(host, settings.get('paths'), settings.get('accept', []), None, None,
                                       lambda h, p, c, f: fetch_status(h, p, cadata))
        fallback = ''
        if not http['ok'] and vip:
            via = smoke_checks.http_check(host, settings.get('paths'), settings.get('accept', []), None, None,
                                          lambda h, p, c, f: fetch_status(h, p, cadata, vip))
            fallback = f' / APP VIP 직접: {via["detail"]}'
        address_rows.append([host, dns, certificate, http['detail'] + fallback])
    lines += ['공개 주소:'] + table(['host', 'DNS 결과', '인증서(APP VIP 기준)' if vip else '인증서', 'HTTPS 응답'], address_rows) + ['']
    ports = [smoke_checks.tcp_check(address, port) for address, port in smoke_checks.host_ports(pods, settings.get('hostPorts'))]
    if ports:
        lines += ['hostPort:'] + table(['대상', '결과'], [[item['target'], item['detail']] for item in ports]) + ['']
    events = attempt(errors, f'{name} 이벤트 조회', lambda: json.loads(
        kube(['-n', namespace, 'get', 'events', '--field-selector', 'type=Warning', '-o', 'json']))['items'], [])
    grouped = {}
    for event in events:
        key = (event.get('reason', ''), event.get('involvedObject', {}).get('kind', ''), event.get('involvedObject', {}).get('name', ''))
        entry = grouped.setdefault(key, {'count': 0, 'message': redactor.short(event.get('message', ''), 160)})
        entry['count'] += event.get('count') or 1
    top = sorted(grouped.items(), key=lambda item: -item[1]['count'])[:5]
    lines += ['최근 Warning 이벤트(상위 5):'] + table(['사유', '대상', '횟수', '메시지'], [
        [reason, f'{kind}/{target}', entry['count'], entry['message']] for (reason, kind, target), entry in top]) + ['']
    return lines


def fetch_status(host, path, cadata, connect=None):
    """smoke와 같은 요청 함수로 HTTPS 상태 코드를 얻는다. 사내 CA 폴더는 그 함수가 신뢰 목록에 더한다."""
    return smoke_checks.request_status(host, path, connect)


def build(target, context, aliases, skip_drift=False, now=None):
    """보고서 원문(별칭 적용 전)과 조회 실패 목록을 만든다."""
    catalog = state.read_catalog()
    names = state.resolve_apps(catalog, target)
    git, kube = state.git_runner(), state.kube_runner(context)
    errors = []
    checkout = state.checkout_state(git)
    dirty = attempt(errors, 'checkout 변경 조회', lambda: len(git(['status', '--porcelain']).splitlines()), '조회 불가')
    nodes = attempt(errors, '노드 조회', lambda: json.loads(kube(['get', 'nodes', '-o', 'json']))['items'], [])
    aliases.register_nodes(node['metadata']['name'] for node in nodes)
    vip = next((item['ip'] for alias, item in aliases.table['addresses'].items() if alias == 'VIP-APP'), None)
    cadata = ca_bundle.bundle_text() or None
    options = None
    if not skip_drift:
        options = {'manifest': True, 'envs': {}, 'context': context, 'vip_backends': '',
                   'cluster_kinds': attempt(errors, 'API 리소스 조회', lambda: state.cluster_scoped_kinds(kube), set())}
    stamp = (now or datetime.datetime.now(datetime.timezone.utc)).strftime('%Y-%m-%dT%H:%MZ')
    lines = ['# 서버 상태 보고', '',
             f'- 양식 버전: {LAYOUT_VERSION} / 별칭 표 버전: {aliases.version}',
             f'- 생성 시각(UTC): {stamp}',
             f'- checkout: {checkout["branch"]} {checkout["commit"][:12]}, 미커밋 변경 {dirty}건',
             f'- 대상 앱: {", ".join(names)}',
             f'- 도구: {command_version(["kubectl", "version", "--client"])} / '
             f'{command_version(["helm", "version", "--short"])} / Python {sys.version.split()[0]}',
             f'- 사내 CA 묶음: {"있음" if cadata else "없음(공개 CA만 신뢰)"}', '',
             '## 1. 클러스터', '', *table(['항목', '값'], cluster_rows(kube, nodes, errors)), '',
             '## 2. 노드', '',
             *table(['노드', '역할', 'Ready', '스케줄', 'kubelet', 'OS', '커널', '런타임', 'CPU', '메모리', '디스크 여유/전체', 'taint', 'FTP 라벨'],
                    node_rows(kube, nodes, errors)), '',
             '## 3. 공용 진입점', '', *table(['항목', '값'], ingress_section(kube, cadata, vip, errors)), '',
             '## 4. 앱별 상태', '']
    for name in names:
        lines += app_section(name, catalog['apps'][name], kube, git, checkout, options, cadata, vip, errors, aliases)
    lines += ['## 5. 확인하지 못한 항목', '', *([f'- {aliases.short(item, 300)}' for item in errors] or ['- 없음']), '']
    return '\n'.join(lines)


def load_aliases(path=ALIASES):
    """별칭 표를 읽어 치환기를 만든다."""
    return Redactor(json.loads(Path(path).read_text()))


def finish(text, aliases):
    """별칭을 적용하고 표에 없는 값의 안내를 붙인다. 실제 값은 표준 오류에만 쓴다."""
    text = aliases.text(text)
    if aliases.unmapped:
        text += '\n## 6. 별칭 미등록 값\n\n' + '\n'.join(f'- {alias}' for alias in sorted(aliases.unmapped.values())) + \
                '\n\n실제 값은 사내 서버의 표준 오류에만 표시했습니다. 별칭 표에 등록한 뒤 다시 생성하면 이 절이 사라집니다.\n'
        print('별칭 미등록 값(외부로 보내지 말 것). aliases.json에 등록하세요:', file=sys.stderr)
        for (kind, value), alias in sorted(aliases.unmapped.items(), key=lambda item: item[1]):
            print(f'  {alias} = {value}', file=sys.stderr)
    return text


def main():
    """report는 앱·그룹 하나를, redact는 표준 입력을 받는다."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('target', nargs='?', default='all', help='앱·그룹 이름 또는 redact')
    parser.add_argument('--context', default='')
    parser.add_argument('--output', type=Path, help='보고서를 저장할 파일. 생략하면 표준 출력')
    parser.add_argument('--skip-drift', action='store_true', help='리소스 대조를 생략하고 상태만 수집')
    args = parser.parse_args()
    try:
        aliases = load_aliases()
        if args.target == 'redact':
            sys.stdout.write(finish(sys.stdin.read(), aliases))
            return 0
        text = finish(build(args.target, args.context, aliases, args.skip_drift), aliases)
    except (ValueError, KeyError, OSError, state.QueryError) as error:
        print(f'보고서 생성 실패: {error}', file=sys.stderr)
        return 2
    if args.output:
        args.output.write_text(text)
        print(f'보고서 저장: {args.output}')
    else:
        sys.stdout.write(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
