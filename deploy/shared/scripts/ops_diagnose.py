#!/usr/bin/env python3
"""앱 하나의 장애 상태를 한 번에 모아 보여 준다(조회 전용).

워크로드 준비 상태, Pod 상태와 대기 사유, PVC, 최근 Warning 이벤트, 문제가 있는 Pod의 로그 끝, smoke 결과를 모으고
배포 가이드 `장애 조회` 표에서 볼 행을 알려 준다. 고치지는 않는다.

종료 코드: 0 이상 없음, 1 이상 있음, 2 조회 불가.
출력에는 서버명·주소가 그대로 나오므로 외부로 전달하려면 `make -s ops-redact`를 거친다.
"""

import argparse
import functools
import json
import os
import sys

import catalog as registry
import deploy_state as state
import smoke as smoke_checks

LOG_LINES = 20
MAX_LOG_PODS = 3
# 관찰한 상태 → 배포 가이드(deploy/README.md) `장애 조회` 표의 증상 칸. test_ops_tools.py가 표와 대조한다.
GUIDE_ROWS = {
    'node': 'Node NotReady',
    'pending': 'Pending, PVC Pending',
    'image': 'ImagePullBackOff',
    'crash': 'CrashLoopBackOff',
    'route': '404 / 503',
    'tls': 'TLS 오류',
    'dns': 'smoke의 `DNS 조회 실패`',
}


def pod_rows(pods):
    """Pod마다 상태·노드·재시작 수·대기 사유를 정리한다."""
    rows = []
    for pod in pods:
        statuses = pod.get('status', {}).get('containerStatuses', []) or []
        waiting = sorted({(c.get('state') or {}).get('waiting', {}).get('reason', '') for c in statuses} - {''})
        ready = bool(statuses) and all(c.get('ready') for c in statuses)
        phase = pod.get('status', {}).get('phase', 'Unknown')
        rows.append({'name': pod['metadata']['name'], 'phase': phase, 'node': pod['spec'].get('nodeName', '미배치'),
                     'restarts': sum(c.get('restartCount', 0) for c in statuses), 'waiting': waiting,
                     'healthy': phase == 'Succeeded' or (phase == 'Running' and ready)})
    return rows


def guide_rows(pods, claims, nodes, checks):
    """관찰한 상태에 해당하는 가이드 표의 행 이름을 고른다."""
    found = []
    reasons = {reason for pod in pods for reason in pod['waiting']}
    placed = {pod['node'] for pod in pods}
    if any(name in placed and not ready for name, ready in nodes.items()):
        found.append(GUIDE_ROWS['node'])
    if any(pod['phase'] == 'Pending' and not pod['waiting'] for pod in pods) or any(phase != 'Bound' for phase in claims.values()):
        found.append(GUIDE_ROWS['pending'])
    if reasons & {'ImagePullBackOff', 'ErrImagePull', 'InvalidImageName'}:
        found.append(GUIDE_ROWS['image'])
    if 'CrashLoopBackOff' in reasons or any(pod['restarts'] >= 3 for pod in pods):
        found.append(GUIDE_ROWS['crash'])
    details = ' | '.join(item['detail'] for item in checks if not item['ok'])
    if ' 404' in details or ' 503' in details or ' 502' in details:
        found.append(GUIDE_ROWS['route'])
    if 'TLS 검증 실패' in details:
        found.append(GUIDE_ROWS['tls'])
    if 'DNS 조회 실패' in details:
        found.append(GUIDE_ROWS['dns'])
    return found


def diagnose(app_name, app, kube, namespace, checker=smoke_checks.smoke):
    """한 앱의 진단 줄 목록과 이상 건수를 만든다."""
    selector = app['runtime'].get('selector', '')
    label = ['-l', selector] if selector else []
    lines = [f'# 진단: {app_name} (namespace {namespace})', '']
    if not kube(['get', 'namespace', namespace, '--ignore-not-found', '-o', 'name']).strip():
        lines += ['namespace가 없습니다. 설치되지 않은 앱입니다.', f'볼 곳: deploy/{app_name}/README.md의 `A. 최초 설치`']
        return lines, 1
    nodes = {node['metadata']['name']: any(c['type'] == 'Ready' and c['status'] == 'True' for c in node['status'].get('conditions', []))
             for node in json.loads(kube(['get', 'nodes', '-o', 'json']))['items']}
    pods = pod_rows(json.loads(kube(['-n', namespace, 'get', 'pods', '-o', 'json', *label]))['items'])
    claims = {item['metadata']['name']: item.get('status', {}).get('phase', 'Unknown')
              for item in json.loads(kube(['-n', namespace, 'get', 'pvc', '-o', 'json']))['items']}
    checks = checker(app_name, app, kube, namespace)
    lines.append('## smoke')
    lines += [f'[{"통과" if item["ok"] else "실패"}] {item["kind"]} {item["target"]} — {item["detail"]}' for item in checks]
    lines += ['', '## Pod']
    lines += [f'{"정상" if pod["healthy"] else "이상"} {pod["name"]} {pod["phase"]} 노드={pod["node"]}'
              f'({"Ready" if nodes.get(pod["node"]) else "NotReady 또는 미배치"}) 재시작={pod["restarts"]}'
              + (f' 대기={",".join(pod["waiting"])}' if pod['waiting'] else '') for pod in pods] or ['Pod 없음']
    if claims:
        lines += ['', '## PVC'] + [f'{name} {phase}' for name, phase in sorted(claims.items())]
    events = json.loads(kube(['-n', namespace, 'get', 'events', '--field-selector', 'type=Warning', '-o', 'json']))['items']
    grouped = {}
    for event in events:
        key = (event.get('reason', ''), event.get('involvedObject', {}).get('kind', ''), event.get('involvedObject', {}).get('name', ''))
        entry = grouped.setdefault(key, {'count': 0, 'message': state.clip(event.get('message', ''), 200)})
        entry['count'] += event.get('count') or 1
    lines += ['', '## 최근 Warning 이벤트(상위 5)']
    lines += [f'{reason} {kind}/{name} x{entry["count"]}: {entry["message"]}'
              for (reason, kind, name), entry in sorted(grouped.items(), key=lambda item: -item[1]['count'])[:5]] or ['없음']
    troubled = [pod for pod in pods if not pod['healthy'] or pod['restarts']][:MAX_LOG_PODS]
    for pod in troubled:
        lines += ['', f'## 로그 끝 {LOG_LINES}줄: {pod["name"]}']
        for extra in ([], ['--previous']) if pod['restarts'] else ([],):
            try:
                output = kube(['-n', namespace, 'logs', pod['name'], '--all-containers', f'--tail={LOG_LINES}', *extra]).rstrip()
            except state.QueryError:
                output = ''
            if output:
                lines += [('(재시작 전)' if extra else '(현재)'), output]
    rows = guide_rows(pods, claims, nodes, checks)
    problems = sum(1 for item in checks if not item['ok']) + sum(1 for pod in pods if not pod['healthy'])
    lines += ['', '## 볼 곳']
    if rows:
        lines += [f'- deploy/README.md `장애 조회` 표의 행: {row}' for row in rows]
    if problems:
        lines.append(f'- deploy/{app_name}/README.md의 `문제 해결과 멈춤 조건`')
    else:
        lines.append('- 이상 없음')
    return lines, problems


def main():
    """앱 하나를 진단하고 마지막 줄에 결과를 한 줄로 요약한다."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('app')
    parser.add_argument('--context', required=True)
    args = parser.parse_args()
    try:
        catalog = state.read_catalog()
        if args.app not in catalog['apps']:
            raise ValueError('apps.json의 앱 하나를 지정하세요.')
        app = catalog['apps'][args.app]
        if app.get('runtime') is None:
            raise ValueError(f'{args.app}은 클러스터 워크로드가 없는 설정 전용 앱입니다. make {args.app}-check로 확인하세요.')
        # 배포와 같은 env 변수(예: AIRFLOW_ENV)를 지정했으면 그 파일의 NAMESPACE를 따른다. smoke 입력도 같은 환경변수를 쓴다.
        checker = functools.partial(smoke_checks.smoke, connect=os.environ.get('SMOKE_CONNECT') or None,
                                    ca_file=os.environ.get('SMOKE_CA_FILE') or None, vip=smoke_checks.app_vip())
        lines, problems = diagnose(args.app, app, state.kube_runner(args.context), registry.namespace(app), checker)
    except (ValueError, KeyError, OSError, state.QueryError) as error:
        print(f'진단 결과: 조회 불가 — {error}', file=sys.stderr)
        return 2
    print('\n'.join(lines))
    print(f'\n진단 결과: {"정상" if not problems else f"이상 {problems}건"}')
    return 0 if not problems else 1


if __name__ == '__main__':
    sys.exit(main())
