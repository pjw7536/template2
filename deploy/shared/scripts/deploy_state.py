#!/usr/bin/env python3
"""현재 checkout의 배포 정의와 실제 클러스터 상태가 같은지 조회 전용으로 대조하고, 배포 기록을 남긴다.

- check: 앱마다 기존 렌더 명령으로 현재 checkout의 적용 대상을 만들고, 배포 도구와 같은 `kubectl apply`를
  서버 dry-run으로 계산한 결과를 실제 리소스와 비교한다(manifest). 배포 기록·워크로드 상태도 함께 본다. 클러스터·Git을 변경하지 않는다.
- record: 배포가 끝난 뒤 앱 namespace의 ConfigMap `deploy-record-<app>`에 적용 commit·앱 경로 내용 id·
  입력 파일 SHA-256·워크로드 Pod template 해시·이미지를 기록한다. 클러스터에 쓰는 유일한 명령이다.

종료 코드: 0 일치, 1 불일치·이상 발견, 2 판정 불가(렌더·조회 실패, 기록 없음 등).
Secret은 렌더 결과에서 제외하고 값도 조회하지 않는다. 입력 파일은 내용 대신 SHA-256만 기록한다.
"""

import argparse
import datetime
import getpass
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# 다른 도구가 파일 경로로 이 모듈을 읽어도 같은 폴더의 공용 모듈을 찾게 한다.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import app as app_commands  # noqa: E402
import catalog as registry  # noqa: E402
from catalog import ROOT, env_value, read_catalog, resolve_apps  # noqa: E402 (다른 도구가 이 모듈 이름으로 쓰는 공개 함수)

RECORD_LABEL = 'deploy-record'
WORKLOAD_KINDS = 'deployments,statefulsets,daemonsets'
# 실행 결과에 영향이 없는 문서·테스트 변경은 배포 내용 비교에서 제외한다.
IGNORED_SUFFIXES = ('.md',)
IGNORED_PARTS = ('docs', 'tests', '__pycache__')
BAD_WAITING = {'CrashLoopBackOff', 'ImagePullBackOff', 'ErrImagePull', 'CreateContainerConfigError', 'InvalidImageName'}
MAX_LISTED = 20
# 값·일회성 실행·생성 시점 metadata라서 리소스 비교 대상에서 제외한다. CRD는 Helm이 upgrade하지 않는다.
SKIPPED_KINDS = {'Secret', 'Job', 'Pod', 'Namespace', 'CustomResourceDefinition'}
VOLATILE_METADATA = ('managedFields', 'resourceVersion', 'uid', 'generation', 'creationTimestamp', 'selfLink')
VOLATILE_ANNOTATIONS = ('kubectl.kubernetes.io/last-applied-configuration', 'deployment.kubernetes.io/revision',
                        'deprecated.daemonset.template.generation')


class QueryError(Exception):
    """Git·kubectl·렌더 실패를 판정 불가로 구분한다."""


def clip(text, limit):
    """공백에서 잘라 주소·이름이 중간에 끊기지 않게 한다. 끊긴 조각은 별칭 치환이 알아보지 못한다."""
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit + 1].rsplit(None, 1)[0][:limit] + ' …'


def run(command, data=None):
    """명령을 실행하고 표준 출력을 반환한다. 실패하면 stderr를 포함한 QueryError를 낸다."""
    try:
        result = subprocess.run([str(part) for part in command], input=data, capture_output=True, text=True,
                                cwd=ROOT, check=False)
    except OSError as error:
        raise QueryError(f'{command[0]} 실행 불가: {error}') from error
    if result.returncode != 0:
        raise QueryError(f'{" ".join(map(str, command[:4]))} 실패: {clip(result.stderr, 300)}')
    return result.stdout


def app_paths(app):
    """배포 내용 비교 대상 경로(deploy 경로와 앱 소스)를 반환한다."""
    return [app['deployPath'], *app['sourcePaths']]


def relevant(path):
    """문서·테스트를 제외한 실행 관련 파일인지 확인한다."""
    return not path.endswith(IGNORED_SUFFIXES) and not any(part in IGNORED_PARTS for part in path.split('/'))


def content_id(git, paths, revision='HEAD'):
    """경로 아래 실행 관련 파일의 blob id 목록으로 내용 id를 만든다. commit이 달라도 내용이 같으면 같은 값이다."""
    listing = git(['ls-tree', '-r', revision, '--', *paths])
    lines = sorted(line for line in listing.splitlines() if relevant(line.split('\t', 1)[-1]))
    return hashlib.sha256('\n'.join(lines).encode()).hexdigest()


def dirty_paths(git, paths):
    """앱 경로의 미커밋·미추적 실행 파일을 반환한다."""
    status = git(['status', '--porcelain', '--untracked-files=all', '--', *paths])
    return sorted({line[3:].split(' -> ')[-1] for line in status.splitlines() if relevant(line[3:].split(' -> ')[-1])})


def input_key(path):
    """저장소 안의 입력은 루트 기준 상대 경로로, 저장소 밖 입력은 절대 경로로 식별한다."""
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return str(resolved)


def file_digest(path):
    """입력 파일의 SHA-256을 반환하고 없으면 None을 반환한다. 상대 경로는 저장소 루트 기준이다."""
    try:
        return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
    except OSError:
        return None


def git_runner():
    """저장소 루트에서 git을 실행하는 함수를 만든다."""
    return lambda args: run(['git', '-C', str(ROOT), *args])


def kube_runner(context):
    """context를 명시한 kubectl 실행 함수를 만든다. 현재 context에 의존하지 않는다."""
    if not context:
        raise ValueError('KUBE_CONTEXT를 명시하세요.')
    return lambda args, data=None: run(['kubectl', '--context', context, *args], data=data)


def checkout_state(git):
    """비교 기준인 현재 checkout의 HEAD·브랜치를 조회한다. 원격과는 비교하지 않는다."""
    return {'commit': git(['rev-parse', 'HEAD']).strip(), 'branch': git(['rev-parse', '--abbrev-ref', 'HEAD']).strip()}


def decode_stream(text):
    """kubectl JSON 출력(단일 객체·List·연속 객체)을 객체 목록으로 바꾼다."""
    items, decoder = [], json.JSONDecoder()
    while text.strip():
        text = text.lstrip()
        value, consumed = decoder.raw_decode(text)
        items.extend(value.get('items', []) if value.get('kind') == 'List' else [value])
        text = text[consumed:]
    return items


def render_desired(kube, app, context, environ=None):
    """현재 checkout으로 앱의 적용 대상 리소스 목록을 만든다. 렌더 명령은 카탈로그가 선언하며 클러스터를 변경하지 않는다."""
    with tempfile.TemporaryDirectory(prefix='deploy-state-') as directory:
        try:
            files = app_commands.render(app, context, directory, environ)
        except (ValueError, OSError) as error:
            raise QueryError(clip(str(error), 300)) from error
        items = []
        for path in files:
            if path.exists() and path.read_text().strip():
                # YAML·JSON을 추가 패키지 없이 JSON 객체로 바꾼다.
                items.extend(decode_stream(kube(['create', '--dry-run=client', '--validate=false', '-o', 'json', '-f', path])))
        return items


def cluster_scoped_kinds(kube):
    """namespace가 없는 리소스 종류를 조회한다."""
    output = kube(['api-resources', '--namespaced=false', '--no-headers'])
    return {line.split()[-1] for line in output.splitlines() if line.strip()}


def select_desired(items, namespace, cluster_kinds):
    """비교 대상만 남기고 namespace가 비어 있는 리소스에 앱 namespace를 채운다."""
    selected, skipped = [], {}
    for item in items:
        annotations = item.get('metadata', {}).get('annotations') or {}
        if item.get('kind') in SKIPPED_KINDS or 'helm.sh/hook' in annotations:
            key = 'Helm hook' if 'helm.sh/hook' in annotations else item.get('kind')
            skipped[key] = skipped.get(key, 0) + 1
            continue
        if item['kind'] not in cluster_kinds and not item['metadata'].get('namespace'):
            item['metadata']['namespace'] = namespace
        selected.append(item)
    return selected, skipped


def resource_key(item):
    """apiVersion group·kind·namespace·name으로 리소스를 식별한다."""
    group = item.get('apiVersion', '').rpartition('/')[0]
    meta = item['metadata']
    return f'{item["kind"]}{"." + group if group else ""}/{meta.get("namespace", "")}/{meta["name"]}'


def normalize(item):
    """생성 시점·관리 metadata와 status를 지워 선언한 내용만 비교하게 한다."""
    item = json.loads(json.dumps(item))
    item.pop('status', None)
    meta = item.get('metadata', {})
    for key in VOLATILE_METADATA:
        meta.pop(key, None)
    annotations = meta.get('annotations') or {}
    for key in VOLATILE_ANNOTATIONS:
        annotations.pop(key, None)
    if not annotations:
        meta.pop('annotations', None)
    return item


def by_name(items):
    """containers·env·ports처럼 name이 고유한 목록이면 name 기준 사전으로 바꾼다."""
    if not items or not all(isinstance(item, dict) and 'name' in item for item in items):
        return None
    named = {item['name']: item for item in items}
    return named if len(named) == len(items) else None


def differences(before, after, path=''):
    """두 JSON 값의 다른 경로를 나열한다. name 목록은 순서와 무관하게 `[이름]`으로 비교한다."""
    if isinstance(before, dict) and isinstance(after, dict):
        result = []
        for key in sorted(set(before) | set(after)):
            result.extend(differences(before.get(key), after.get(key), f'{path}.{key}' if path else key))
        return result
    if isinstance(before, list) and isinstance(after, list):
        left, right = by_name(before), by_name(after)
        if left is not None and right is not None:
            result = []
            for name in sorted(set(left) | set(right)):
                result.extend(differences(left.get(name), right.get(name), f'{path}[{name}]'))
            return result
    if isinstance(before, list) and isinstance(after, list) and len(before) == len(after):
        result = []
        for index, (left, right) in enumerate(zip(before, after)):
            result.extend(differences(left, right, f'{path}[{index}]'))
        return result
    return [] if before == after else [path]


def dry_run_apply(kube, items):
    """배포 도구와 같은 `kubectl apply`(last-applied 기준 3-way 병합)를 서버 dry-run으로 계산한다.

    server-side apply는 다른 관리자가 적용한 필드를 지우지 못해 목록 필드가 합쳐지므로 사용하지 않는다.
    일괄 실패 시 리소스별로 다시 계산해 오류를 분리한다.
    """
    payload = lambda objects: json.dumps({'apiVersion': 'v1', 'kind': 'List', 'items': objects})
    args = ['apply', '--dry-run=server', '-o', 'json', '-f', '-']
    try:
        return {resource_key(item): item for item in decode_stream(kube(args, data=payload(items)))}, {}
    except QueryError:
        results, errors = {}, {}
        for item in items:
            try:
                for result in decode_stream(kube(args, data=payload([item]))):
                    results[resource_key(result)] = result
            except QueryError as error:
                errors[resource_key(item)] = str(error)
        return results, errors


def live_resources(kube, items):
    """적용 대상과 같은 리소스의 현재 상태를 조회한다. 없는 리소스는 결과에서 빠진다."""
    data = json.dumps({'apiVersion': 'v1', 'kind': 'List', 'items': items})
    return {resource_key(item): item for item in decode_stream(kube(['get', '--ignore-not-found', '-o', 'json', '-f', '-'], data=data))}


def compare_manifests(desired, applied, live, errors):
    """dry-run 적용 결과와 실제 리소스를 비교해 판정 항목을 만든다. 입출력이 없어 단위 테스트로 검증한다."""
    findings = []
    matched = 0
    for item in desired:
        key = resource_key(item)
        if key not in live:
            findings.append(('drift', f'{key} 클러스터에 없음'))
            continue
        if key in errors:
            findings.append(('drift', f'{key} 현재 코드를 적용할 수 없음(변경 불가 필드 등): {errors[key]}'))
            continue
        if key not in applied:
            findings.append(('unknown', f'{key} dry-run 결과 없음'))
            continue
        paths = differences(normalize(live[key]), normalize(applied[key]))
        replicas = [p for p in paths if p == 'spec.replicas']
        others = [p for p in paths if p != 'spec.replicas']
        if others:
            shown = ', '.join(others[:MAX_LISTED]) + (f' 외 {len(others) - MAX_LISTED}개' if len(others) > MAX_LISTED else '')
            findings.append(('drift', f'{key} 현재 코드와 다름: {shown}'))
        if replicas:
            findings.append(('warn', f'{key} replica 수가 코드와 다름(운영 조정일 수 있음)'))
        if not paths:
            matched += 1
    return findings, matched


def manifest_findings(kube, app, context, cluster_kinds, environ=None):
    """한 앱의 리소스 비교를 수행한다. 렌더·조회 실패는 판정 불가로 남긴다."""
    namespace = registry.namespace(app, environ)
    try:
        items = render_desired(kube, app, context, environ)
    except QueryError as error:
        return [('unknown', f'현재 코드 렌더 실패: {error}')]
    desired, skipped = select_desired(items, namespace, cluster_kinds)
    if not desired:
        return [('unknown', '렌더 결과에 비교할 리소스가 없음')]
    applied, errors = dry_run_apply(kube, desired)
    try:
        live = live_resources(kube, desired)
    except QueryError as error:
        return [('unknown', f'실제 리소스 조회 실패: {error}')]
    findings, matched = compare_manifests(desired, applied, live, errors)
    excluded = ', '.join(f'{kind} {count}' for kind, count in sorted(skipped.items()))
    findings.append(('ok' if matched == len(desired) else 'info', f'리소스 {matched}/{len(desired)}개 일치'
                     + (f' (비교 제외: {excluded})' if excluded else '')))
    return findings


def workload_snapshot(kube, namespace, selector=''):
    """namespace(선택 시 label selector)의 워크로드 template 해시·이미지·준비 상태를 조회한다.

    replica 조정은 운영 작업이므로 비교에서 제외하고 Pod template(이미지·env·리소스·재시작 annotation)만 해시한다.
    """
    args = ['-n', namespace, 'get', WORKLOAD_KINDS, '-o', 'json']
    if selector:
        args[3:3] = ['-l', selector]
    workloads = {}
    for item in json.loads(kube(args))['items']:
        spec, status, meta = item.get('spec', {}), item.get('status', {}), item['metadata']
        pod = spec.get('template', {}).get('spec', {})
        images = sorted(c['image'] for c in [*pod.get('initContainers', []), *pod.get('containers', [])])
        if item['kind'] == 'DaemonSet':
            desired, ready = status.get('desiredNumberScheduled', 0), status.get('numberReady', 0)
        else:
            desired, ready = spec.get('replicas', 1), status.get('readyReplicas', 0)
        template = json.dumps(spec.get('template', {}), sort_keys=True, separators=(',', ':'))
        workloads[f'{item["kind"]}/{meta["name"]}'] = {
            'templateHash': hashlib.sha256(template.encode()).hexdigest()[:16],
            'generation': meta.get('generation'), 'observedGeneration': status.get('observedGeneration'),
            'images': images, 'desired': desired, 'ready': ready}
    return workloads


def pod_problems(kube, namespace, selector=''):
    """대기 사유가 장애인 컨테이너를 찾는다."""
    args = ['-n', namespace, 'get', 'pods', '-o', 'json']
    if selector:
        args[3:3] = ['-l', selector]
    problems = []
    for pod in json.loads(kube(args))['items']:
        for container in pod.get('status', {}).get('containerStatuses', []) or []:
            waiting = (container.get('state') or {}).get('waiting') or {}
            if waiting.get('reason') in BAD_WAITING:
                problems.append(f'{pod["metadata"]["name"]}/{container["name"]}: {waiting["reason"]}')
    return problems


def build_record(app_name, app, git, kube, inputs, namespace, now=None, user=None):
    """현재 checkout과 배포 직후 워크로드로 배포 기록을 만든다."""
    paths = app_paths(app)
    selector = app['runtime'].get('selector', '')
    return {
        'app': app_name,
        'namespace': namespace,
        'commit': git(['rev-parse', 'HEAD']).strip(),
        'branch': git(['rev-parse', '--abbrev-ref', 'HEAD']).strip(),
        'contentId': content_id(git, paths),
        'dirtyPaths': dirty_paths(git, paths),
        'inputs': {input_key(path): file_digest(input_key(path)) for path in inputs},
        'workloads': {key: {'templateHash': value['templateHash'], 'images': value['images']}
                      for key, value in workload_snapshot(kube, namespace, selector).items()},
        'appliedAt': now or datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'appliedBy': user or getpass.getuser(),
    }


def record_manifest(record):
    """배포 기록 ConfigMap manifest를 만든다."""
    return {'apiVersion': 'v1', 'kind': 'ConfigMap',
            'metadata': {'name': f'deploy-record-{record["app"]}', 'namespace': record['namespace'],
                         'labels': {RECORD_LABEL: record['app']}},
            'data': {'record.json': json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True)}}


def read_record(kube, app_name):
    """모든 namespace에서 앱의 배포 기록을 찾는다. env로 namespace를 바꾼 설치도 찾는다."""
    items = json.loads(kube(['get', 'configmaps', '-A', '-l', f'{RECORD_LABEL}={app_name}', '-o', 'json']))['items']
    if not items:
        return None
    if len(items) > 1:
        names = ', '.join(f'{i["metadata"]["namespace"]}/{i["metadata"]["name"]}' for i in items)
        raise QueryError(f'배포 기록이 여러 개입니다: {names}')
    return json.loads(items[0]['data']['record.json'])


def compare(app_name, app, record, checkout, current_content, current_dirty, changed_files, workloads, problems,
            input_digests, manifest=()):
    """수집한 사실만으로 판정한다. 입출력이 없어 단위 테스트로 검증한다."""
    findings = []

    def add(level, area, message):
        findings.append({'level': level, 'area': area, 'message': message})

    for level, message in manifest:
        add(level, 'manifest', message)
    if current_dirty:
        add('warn', 'checkout', '앱 경로의 미커밋 변경(비교에 포함됨): ' + ', '.join(current_dirty[:MAX_LISTED]))

    if record is None:
        add('unknown', 'record', '배포 기록 없음: 기록 이전 배포이거나 미배포')
    else:
        if record.get('dirtyPaths'):
            add('warn', 'record', '미커밋 변경을 포함해 배포됨: ' + ', '.join(record['dirtyPaths'][:MAX_LISTED]))
        if record['contentId'] != current_content:
            detail = ', '.join(changed_files[:MAX_LISTED]) if changed_files else '변경 파일 목록 조회 불가(기록 commit이 checkout에 없음)'
            add('drift', 'record', f'마지막 배포 이후 앱 정의가 바뀜(배포 {record["commit"][:12]} → HEAD {checkout["commit"][:12]}): {detail}')
        for path, digest in sorted(record.get('inputs', {}).items()):
            now = input_digests.get(path)
            if now is None:
                add('unknown', 'input', f'배포 입력 파일을 찾을 수 없음: {path}')
            elif now != digest:
                add('drift', 'input', f'배포 후 입력 파일이 바뀜: {path}')
        recorded = record.get('workloads', {})
        for key in sorted(set(recorded) - set(workloads)):
            add('drift', 'workload', f'기록된 워크로드가 없음: {key}')
        for key in sorted(set(workloads) - set(recorded)):
            add('warn', 'workload', f'기록 이후 생긴 워크로드: {key}')
        for key in sorted(set(recorded) & set(workloads)):
            before, after = recorded[key], workloads[key]
            if before['images'] != after['images']:
                add('drift', 'workload', f'{key} 이미지가 기록과 다름: {before["images"]} → {after["images"]}')
            elif before.get('templateHash') != after.get('templateHash'):
                add('drift', 'workload', f'{key} Pod template이 배포 후 변경됨(수동 수정·env 변경·rollout restart 등)')

    if not workloads:
        add('unknown', 'health', f'{app["runtime"]["namespace"]}에 대상 워크로드 없음')
    for key, value in sorted(workloads.items()):
        if value['observedGeneration'] is not None and value['generation'] != value['observedGeneration']:
            add('warn', 'health', f'{key} rollout 반영 중')
        if value['ready'] < value['desired']:
            add('warn', 'health', f'{key} Ready {value["ready"]}/{value["desired"]}')
    for problem in problems:
        add('warn', 'health', problem)

    return {'app': app_name, 'namespace': (record or {}).get('namespace', app['runtime']['namespace']),
            'deployedCommit': (record or {}).get('commit'), 'appliedAt': (record or {}).get('appliedAt'),
            'findings': findings}


def app_environment(app, options):
    """대조에 쓸 환경. `--env app=경로`와 `--vip-backends`를 배포와 같은 환경변수로 바꿔 넣는다."""
    environ = dict(os.environ)
    override = options.get('env')
    if override and app.get('inputs'):
        environ[app['inputs'][0]['variable']] = override
    if options.get('vip_backends'):
        environ['VIP_BACKENDS'] = options['vip_backends']
    return environ


def check_app(app_name, app, git, kube, checkout, options):
    """한 앱의 사실을 수집해 판정한다. 조회 실패는 판정 불가로 기록한다."""
    if app.get('runtime') is None:
        return {'app': app_name, 'namespace': None, 'deployedCommit': None, 'appliedAt': None,
                'findings': [{'level': 'info', 'area': 'record', 'message': '클러스터 워크로드가 없는 설정 전용 앱이라 대조하지 않음'}]}
    paths = app_paths(app)
    try:
        record = read_record(kube, app_name)
        namespace = (record or {}).get('namespace', app['runtime']['namespace'])
        selector = app['runtime'].get('selector', '')
        workloads = workload_snapshot(kube, namespace, selector)
        problems = pod_problems(kube, namespace, selector)
        current_content = content_id(git, paths)
        changed = []
        if record and record['contentId'] != current_content:
            try:
                changed = [p for p in git(['diff', '--name-only', record['commit'], 'HEAD', '--', *paths]).split() if relevant(p)]
            except QueryError:
                changed = []
        digests = {path: file_digest(path) for path in (record or {}).get('inputs', {})}
        manifest = []
        if options['manifest']:
            environ = app_environment(app, {'env': options['envs'].get(app_name), 'vip_backends': options.get('vip_backends')})
            manifest = manifest_findings(kube, app, options['context'], options['cluster_kinds'], environ)
        return compare(app_name, app, record, checkout, current_content, dirty_paths(git, paths), changed,
                       workloads, problems, digests, manifest)
    except QueryError as error:
        return {'app': app_name, 'namespace': app['runtime']['namespace'], 'deployedCommit': None, 'appliedAt': None,
                'findings': [{'level': 'unknown', 'area': 'query', 'message': str(error)}]}


def exit_code(results):
    """불일치·이상이 있으면 1, 판정 불가만 있으면 2, 모두 일치하면 0."""
    levels = {item['level'] for result in results for item in result['findings']}
    if levels & {'drift', 'warn'}:
        return 1
    return 2 if 'unknown' in levels else 0


def render_text(checkout, results):
    """사람과 agent가 읽는 요약을 만든다. 값·Secret은 포함하지 않는다."""
    mark = {'ok': 'OK', 'info': 'INFO', 'drift': 'DRIFT', 'warn': 'WARN', 'unknown': 'UNKNOWN'}
    lines = [f'기준 checkout: {checkout["branch"]} {checkout["commit"][:12]}']
    for result in results:
        deployed = result['deployedCommit'][:12] if result['deployedCommit'] else '기록 없음'
        lines.append(f'\n[{result["app"]}] namespace={result["namespace"]} 배포 기록 commit={deployed}'
                     + (f' 적용={result["appliedAt"]}' if result['appliedAt'] else ''))
        lines.extend(f'  {mark[item["level"]]:<8} {item["area"]:<9} {item["message"]}' for item in result['findings'])
    return '\n'.join(lines)


def parse_envs(values):
    """--env app=경로 목록을 앱별 사전으로 바꾼다."""
    envs = {}
    for value in values:
        name, separator, path = value.partition('=')
        if not separator or not name:
            raise ValueError(f'--env는 app=경로 형식이어야 합니다: {value}')
        if path:
            envs[name] = path
    return envs


def main():
    """record는 배포 직후, check는 언제든 조회 전용으로 실행한다."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    record = sub.add_parser('record', help='배포 직후 배포 기록 ConfigMap 작성')
    record.add_argument('app')
    record.add_argument('--context', required=True)
    record.add_argument('--namespace', help='입력 env의 NAMESPACE보다 우선할 namespace')
    record.add_argument('--input', action='append', default=[], help='배포에 사용한 외부 env·입력 파일. SHA-256만 기록')
    check = sub.add_parser('check', help='현재 checkout과 클러스터 대조(조회 전용)')
    check.add_argument('target', nargs='?', default='all')
    check.add_argument('--context', required=True)
    check.add_argument('--env', action='append', default=[], help='렌더에 사용할 env. app=경로, 반복 가능. 생략하면 배포와 같은 환경변수(예: AIRFLOW_ENV) 또는 기본 파일')
    check.add_argument('--vip-backends', default='', help='공용 ingress 렌더에 전달할 VIP backend. 생략 시 VIP_BACKENDS 환경변수 또는 현재 배치 보존')
    check.add_argument('--skip-manifest', action='store_true', help='리소스 비교를 생략하고 기록·상태만 확인')
    check.add_argument('--json', action='store_true')
    args = parser.parse_args()
    try:
        catalog = read_catalog()
        git, kube = git_runner(), kube_runner(args.context)
        if args.command == 'record':
            if args.app not in catalog['apps']:
                raise ValueError(f'지원하지 않는 앱: {args.app}')
            app = catalog['apps'][args.app]
            if app.get('runtime') is None:
                print(f'배포 기록 생략: {args.app}은 클러스터 워크로드가 없는 설정 전용 앱입니다.')
                return 0
            inputs = [p for p in args.input if p]
            declared = next((value for value in (env_value(path, 'NAMESPACE') for path in inputs) if value), None)
            data = build_record(args.app, app, git, kube, inputs,
                                args.namespace or declared or app['runtime']['namespace'])
            kube(['apply', '-f', '-'], data=json.dumps(record_manifest(data)))
            print(f'배포 기록 저장: {data["namespace"]}/deploy-record-{args.app} commit={data["commit"][:12]}'
                  + (' (미커밋 변경 포함)' if data['dirtyPaths'] else ''))
            return 0
        options = {'manifest': not args.skip_manifest, 'envs': parse_envs(args.env), 'context': args.context,
                   'vip_backends': args.vip_backends,
                   'cluster_kinds': set() if args.skip_manifest else cluster_scoped_kinds(kube)}
        checkout = checkout_state(git)
        results = [check_app(name, catalog['apps'][name], git, kube, checkout, options)
                   for name in resolve_apps(catalog, args.target)]
        code = exit_code(results)
        print(json.dumps({'resultCode': code, 'checkout': checkout, 'apps': results}, ensure_ascii=False, indent=2)
              if args.json else render_text(checkout, results))
        return code
    except (ValueError, KeyError, OSError) as error:
        print(f'오류: {error}', file=sys.stderr)
        return 2
    except QueryError as error:
        print(f'조회 실패: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
