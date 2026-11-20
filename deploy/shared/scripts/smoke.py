#!/usr/bin/env python3
"""배포한 앱 하나의 워크로드 준비 상태와 공개 주소 응답을 조회 전용으로 확인한다.

- workload: 앱 namespace의 Deployment·StatefulSet·DaemonSet이 모두 Ready인지 본다.
- http: 앱 namespace의 Ingress host마다 apps.json `smoke.paths`를 순서대로 요청해 하나라도 정상 응답인지 본다.
- tcp: hostPort를 여는 Pod는 노드 주소의 포트 연결을 본다(FTP).

종료 코드: 0 모두 통과, 1 실패 있음, 2 조회 불가. 로그인·파일 송수신 같은 사용자 기능은 확인하지 않는다.
"""

import argparse
import http.client
import json
import os
import socket
import ssl
import sys

import ca_bundle
from deploy_state import QueryError, env_value, kube_runner, pod_problems, read_catalog, workload_snapshot

TIMEOUT = 8


def request_status(host, path, connect=None, ca_file=None):
    """HTTPS GET의 상태 코드를 반환한다. connect를 주면 DNS 대신 그 주소로 접속하고 SNI·검증은 host로 한다.

    시스템 신뢰 목록에 저장소의 사내 CA 폴더(deploy/shared/certs/ca)와 지정한 CA 파일을 더해 검증한다.
    """
    context = ssl.create_default_context(cafile=ca_file or None)
    shared = ca_bundle.bundle_text()
    if shared:
        context.load_verify_locations(cadata=shared)
    raw = socket.create_connection((connect or host, 443), timeout=TIMEOUT)
    try:
        with context.wrap_socket(raw, server_hostname=host) as secured:
            connection = http.client.HTTPSConnection(host, timeout=TIMEOUT, context=context)
            connection.sock = secured
            connection.request('GET', path, headers={'Host': host, 'Accept': '*/*', 'Connection': 'close'})
            return connection.getresponse().status
    finally:
        raw.close()


def http_check(host, paths, accept, connect=None, ca_file=None, fetch=request_status):
    """후보 경로 중 하나라도 2xx·3xx 또는 허용한 상태를 돌려주면 통과로 본다."""
    seen = []
    for path in paths or ['/']:
        try:
            status = fetch(host, path, connect, ca_file)
        except socket.gaierror:
            return {'kind': 'http', 'target': host, 'ok': False, 'detail': 'DNS 조회 실패'}
        except ssl.SSLError as error:
            return {'kind': 'http', 'target': host, 'ok': False, 'detail': f'TLS 검증 실패: {getattr(error, "verify_message", "") or getattr(error, "reason", "") or type(error).__name__}'}
        except (OSError, http.client.HTTPException) as error:
            return {'kind': 'http', 'target': host, 'ok': False, 'detail': f'연결 실패: {type(error).__name__}'}
        seen.append(f'{path} {status}')
        if 200 <= status < 400 or status in accept:
            return {'kind': 'http', 'target': host, 'ok': True, 'detail': seen[-1]}
    return {'kind': 'http', 'target': host, 'ok': False, 'detail': '정상 응답 없음: ' + ', '.join(seen)}


def tcp_check(address, port):
    """노드 주소의 hostPort에 TCP 연결이 되는지 확인한다."""
    try:
        socket.create_connection((address, port), timeout=TIMEOUT).close()
        return {'kind': 'tcp', 'target': f'{address}:{port}', 'ok': True, 'detail': '연결 성공'}
    except OSError as error:
        return {'kind': 'tcp', 'target': f'{address}:{port}', 'ok': False, 'detail': f'연결 실패: {type(error).__name__}'}


def host_ports(pods, names=None):
    """Running Pod가 여는 (노드 주소, hostPort) 목록을 만든다. names를 주면 그 이름의 포트만 본다.

    FTP passive 포트처럼 요청이 있을 때만 열리는 포트는 apps.json `smoke.hostPorts`에서 빼 오탐을 막는다.
    """
    result = set()
    for pod in pods:
        address = pod.get('status', {}).get('hostIP')
        if pod.get('status', {}).get('phase') != 'Running' or not address:
            continue
        for container in pod['spec']['containers']:
            for port in container.get('ports', []):
                if port.get('hostPort') and port.get('protocol', 'TCP') == 'TCP' and (names is None or port.get('name') in names):
                    result.add((address, port['hostPort']))
    return sorted(result)


def smoke(app_name, app, kube, namespace, connect=None, ca_file=None, fetch=request_status, tcp=tcp_check):
    """한 앱의 확인 결과 목록을 만든다."""
    selector = app['runtime'].get('selector', '')
    checks = []
    workloads = workload_snapshot(kube, namespace, selector)
    if not workloads:
        checks.append({'kind': 'workload', 'target': namespace, 'ok': False, 'detail': '대상 워크로드 없음'})
    for key, value in sorted(workloads.items()):
        checks.append({'kind': 'workload', 'target': key, 'ok': value['ready'] >= value['desired'] > 0,
                       'detail': f'Ready {value["ready"]}/{value["desired"]}'})
    for problem in pod_problems(kube, namespace, selector):
        checks.append({'kind': 'workload', 'target': namespace, 'ok': False, 'detail': problem})
    settings = app.get('smoke', {})
    ingresses = json.loads(kube(['-n', namespace, 'get', 'ingress', '-o', 'json']))['items']
    hosts = sorted({rule['host'] for item in ingresses for rule in item['spec'].get('rules', []) if rule.get('host')})
    for host in hosts:
        checks.append(http_check(host, settings.get('paths'), settings.get('accept', []), connect, ca_file, fetch))
    pods = json.loads(kube(['-n', namespace, 'get', 'pods', '-o', 'json', *(['-l', selector] if selector else [])]))['items']
    for address, port in host_ports(pods, settings.get('hostPorts')):
        checks.append(tcp(address, port))
    return checks


def main():
    """앱 하나를 확인하고 사람·agent가 읽는 줄 또는 JSON을 출력한다."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('app')
    parser.add_argument('--context', required=True)
    parser.add_argument('--env', default='', help='NAMESPACE를 바꾼 설치의 env 파일')
    parser.add_argument('--connect', default=os.environ.get('SMOKE_CONNECT', ''), help='DNS 등록 전 대신 접속할 주소(APP VIP 등)')
    parser.add_argument('--ca-file', default=os.environ.get('SMOKE_CA_FILE', ''), help='사내 CA 묶음 PEM')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    try:
        catalog = read_catalog()
        if args.app not in catalog['apps']:
            raise ValueError(f'지원하지 않는 앱: {args.app}')
        app = catalog['apps'][args.app]
        namespace = (env_value(args.env, 'NAMESPACE') if args.env else None) or app['runtime']['namespace']
        checks = smoke(args.app, app, kube_runner(args.context), namespace, args.connect or None, args.ca_file or None)
    except (ValueError, KeyError, OSError, QueryError) as error:
        print(f'smoke 조회 불가: {error}', file=sys.stderr)
        return 2
    code = 0 if all(item['ok'] for item in checks) else 1
    if args.json:
        print(json.dumps({'resultCode': code, 'app': args.app, 'namespace': namespace, 'checks': checks}, ensure_ascii=False, indent=2))
    else:
        for item in checks:
            print(f'[{"통과" if item["ok"] else "실패"}] {item["kind"]} {item["target"]} — {item["detail"]}')
        print(f'smoke {"통과" if code == 0 else "실패"}: {args.app}')
    return code


if __name__ == '__main__':
    sys.exit(main())
