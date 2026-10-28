#!/usr/bin/env python3
"""앱과 독립적으로 공용 Traefik을 준비하고 Portal 감시 범위를 연결한다."""

import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

BASE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('deploy_runtime', BASE.parent / 'scripts/runtime.py')
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)
routing = runtime.module('ingress_routing', BASE / 'routing.py')
NAMESPACE = 'etch-sso'


def run(args, data=None):
    """공용 리소스 명령의 실패를 적용 단계로 전달한다."""
    result = subprocess.run(list(map(str, args)), input=data, text=True, capture_output=True)
    if result.returncode:
        raise ValueError(result.stderr.strip() or '공용 Ingress 명령이 실패했습니다.')
    return result.stdout


def kubectl(context):
    """빈 context를 거부하고 모든 클러스터 호출에 명시적으로 전달한다."""
    if not context.strip():
        raise ValueError('KUBE_CONTEXT를 명시하세요.')
    return ['kubectl', '--context', context]


def prepare(context, vip_backends=None):
    """공통 원본과 현행 배치를 합성하며 이 단계에서는 클러스터를 변경하지 않는다."""
    kube = kubectl(context)
    items = runtime.render_json(run, kube, BASE)
    original = routing.controller(items)
    raw = run([*kube, '-n', NAMESPACE, 'get', 'deployment', 'traefik', '--ignore-not-found', '-o', 'json'])
    current = json.loads(raw) if raw.strip() else None
    nodes = json.loads(run([*kube, 'get', 'nodes', '-o', 'json']))['items']
    pods = json.loads(run([*kube, 'get', 'pods', '-A', '-o', 'json']))['items']
    updated = routing.plan_controller(original, current, vip_backends, nodes, pods)
    return [updated if item is original else item for item in items]


def start(context, vip_backends=None, check_only=False):
    """모든 검사를 마친 뒤 공용 리소스만 적용하고 Traefik 기동을 확인한다."""
    kube = kubectl(context)
    items = prepare(context, vip_backends)
    if check_only:
        print('공용 Ingress 원본·배치 검사 통과. 클러스터를 변경하지 않았습니다.')
        return
    existing_namespace = run([*kube, 'get', 'namespace', NAMESPACE, '--ignore-not-found', '-o', 'name'])
    if not existing_namespace.strip():
        # 기존 namespace의 보안 label·annotation과 다른 운영 설정은 갱신하지 않는다.
        run([*kube, 'create', '-f', '-'], data=json.dumps(
            {'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': NAMESPACE}}))
    run([*kube, 'apply', '-f', '-'], data=json.dumps({'apiVersion': 'v1', 'kind': 'List', 'items': items}))
    run([*kube, '-n', NAMESPACE, 'rollout', 'status', 'deployment/traefik', '--timeout=600s'])
    print('공용 Ingress 준비 완료. VIP·HTTPS 접속은 별도로 확인하세요.')


def check_portal_access(kube, current):
    """Portal overlay가 준비한 기존 권한과 controller의 연결을 확인한다."""
    namespace, name = 'tailwind-internal', 'portal-traefik'
    role = json.loads(run([*kube, '-n', namespace, 'get', 'role', name, '-o', 'json']))
    binding = json.loads(run([*kube, '-n', namespace, 'get', 'rolebinding', name, '-o', 'json']))
    reference = {'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'Role', 'name': name}
    subject = {'kind': 'ServiceAccount', 'name': current['spec']['template']['spec']['serviceAccountName'],
               'namespace': current['metadata']['namespace']}
    if binding.get('roleRef') != reference or not any(all(item.get(key) == value for key, value in subject.items())
                                                   for item in binding.get('subjects', [])):
        raise ValueError('Portal RoleBinding이 공용 Traefik ServiceAccount와 연결되지 않았습니다.')
    required, _ = routing.namespace_access(namespace, current)
    for rule in required['rules']:
        for group in rule['apiGroups']:
            for resource in rule['resources']:
                verbs = set()
                for actual in role.get('rules', []):
                    if (group in actual.get('apiGroups', []) or '*' in actual.get('apiGroups', [])) and (
                            resource in actual.get('resources', []) or '*' in actual.get('resources', [])):
                        if actual.get('resourceNames'):
                            continue
                        verbs.update(actual.get('verbs', []))
                if '*' not in verbs and not set(rule['verbs']) <= verbs:
                    raise ValueError('Portal 라우팅 권한이 부족합니다. Portal overlay를 먼저 적용하세요.')


def connect(context, app):
    """기존 Portal 권한을 확인한 뒤 감시 목록만 낙관적 잠금으로 확장한다."""
    kube = kubectl(context)
    if app != 'portal':
        raise ValueError('후속 Ingress 연결은 APP=portal을 지정하세요.')
    current = json.loads(run([*kube, '-n', NAMESPACE, 'get', 'deployment', 'traefik', '-o', 'json']))
    check_portal_access(kube, current)
    patch = routing.namespace_patch(current, 'tailwind-internal')
    if not patch:
        print('Portal namespace를 이미 감시합니다. 변경하지 않았습니다.')
        return
    run([*kube, '-n', NAMESPACE, 'patch', 'deployment', 'traefik', '--type=json',
         '--patch', json.dumps(patch)])
    run([*kube, '-n', NAMESPACE, 'rollout', 'status', 'deployment/traefik', '--timeout=300s'])
    print('Portal Ingress 연결 완료. 기존 앱과 Portal 접속을 확인하세요.')


def main():
    """공용 준비와 앱 연결을 분리하며 모든 실행에 context를 요구한다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['check', 'up', 'connect'])
    parser.add_argument('--context', required=True)
    parser.add_argument('--vip-backends')
    parser.add_argument('--app', default='')
    args = parser.parse_args()
    if args.action == 'connect':
        if args.vip_backends:
            parser.error('connect는 VIP 배치를 변경하지 않습니다.')
        connect(args.context, args.app)
    else:
        start(args.context, args.vip_backends, check_only=args.action == 'check')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, StopIteration) as error:
        print(f'오류: {error}', file=sys.stderr)
        sys.exit(1)
