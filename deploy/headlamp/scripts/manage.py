#!/usr/bin/env python3
"""고정 chart로 Headlamp를 검사·배포하고 조회용 접속을 제공한다."""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import urllib.request

APP = Path(__file__).resolve().parents[1]
LOCK = json.loads((APP / 'helm/chart.lock.json').read_text())


def run(command, **kwargs):
    """명령 실패를 즉시 전달한다."""
    return subprocess.run(command, check=True, text=True, **kwargs)


def settings(path, example=False):
    """env를 실행하지 않고 제한된 설정만 읽는다."""
    result = {}
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        key, separator, value = line.partition('=')
        if not separator or key not in {'HEADLAMP_REGISTRY', 'IMAGE_PULL_SECRET', 'HEADLAMP_HOST', 'HEADLAMP_TLS_SECRET'} or key in result:
            raise ValueError('알 수 없거나 중복된 env 항목입니다.')
        result[key] = value
    registry = result.get('HEADLAMP_REGISTRY', '')
    if not re.fullmatch(r'[a-z0-9][a-z0-9.:-]*(/[a-z0-9._-]+)*', registry):
        raise ValueError('HEADLAMP_REGISTRY에 scheme 없는 registry 경로가 필요합니다.')
    if not example and '.invalid' in registry:
        raise ValueError('예시 registry를 실제 미러 주소로 변경하세요.')
    secret = result.get('IMAGE_PULL_SECRET', '')
    if secret and not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', secret):
        raise ValueError('IMAGE_PULL_SECRET 이름이 올바르지 않습니다.')
    values = {'image': {'registry': registry}, 'imagePullSecrets': [{'name': secret}] if secret else []}
    host = result.get('HEADLAMP_HOST', '')
    tls = result.get('HEADLAMP_TLS_SECRET', '')
    if bool(host) != bool(tls):
        raise ValueError('HEADLAMP_HOST와 HEADLAMP_TLS_SECRET을 함께 입력하세요.')
    if host:
        label = r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?'
        if len(host) > 253 or not re.fullmatch(rf'{label}(?:\.{label})+', host):
            raise ValueError('HEADLAMP_HOST에는 경로·scheme 없는 DNS 이름을 입력하세요.')
        if len(tls) > 253 or not re.fullmatch(rf'{label}(?:\.{label})*', tls):
            raise ValueError('HEADLAMP_TLS_SECRET 이름이 올바르지 않습니다.')
        values['config'] = {'baseURL': '/headlamp'}
        values['ingress'] = {
            'enabled': True, 'ingressClassName': 'traefik',
            'annotations': {'traefik.ingress.kubernetes.io/router.entrypoints': 'websecure',
                            'traefik.ingress.kubernetes.io/router.tls': 'true'},
            'hosts': [{'host': host, 'paths': [{'path': '/headlamp', 'type': 'Prefix'}]}],
            'tls': [{'hosts': [host], 'secretName': tls}],
        }
    return values


def ingress_plan(context, values):
    """TLS와 기존 controller를 확인하고 namespace 추가 변경만 준비한다."""
    kubectl = ['kubectl', '--context', context]
    secret = values['ingress']['tls'][0]['secretName']
    # kubectl 출력은 타입·키 이름으로 제한해 개인키·인증서 내용을 노출하지 않는다.
    summary = run(kubectl + ['-n', 'headlamp', 'get', 'secret', secret, '-o',
                  'go-template={{.type}}{{range $key, $value := .data}} {{$key}}{{end}}'],
                  capture_output=True).stdout.split()
    if not summary or summary[0] != 'kubernetes.io/tls' or not {'tls.crt', 'tls.key'} <= set(summary[1:]):
        raise ValueError('headlamp namespace에 tls.crt·tls.key가 있는 TLS Secret을 먼저 등록하세요.')
    current = json.loads(run(kubectl + ['-n', 'etch-sso', 'get', 'deployment', 'traefik', '-o', 'json'],
                             capture_output=True).stdout)
    spec = importlib.util.spec_from_file_location('routing', APP.parent / 'shared/ingress/routing.py')
    routing = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(routing)
    desired = routing.preserve_namespaces(current, current, 'headlamp')
    patch = [{'op': 'test', 'path': '/metadata/resourceVersion', 'value': current['metadata']['resourceVersion']}]
    for index, container in enumerate(current['spec']['template']['spec']['containers']):
        if container['name'] == 'traefik':
            args = desired['spec']['template']['spec']['containers'][index]['args']
            if args != container['args']:
                patch.append({'op': 'replace', 'path': f'/spec/template/spec/containers/{index}/args', 'value': args})
    access = {'apiVersion': 'v1', 'kind': 'List', 'items': routing.namespace_access('headlamp', current)}
    return access, patch


def connect_ingress(context, access, patch, dry_run=False):
    """앱 namespace 권한을 먼저 준비한 뒤 기존 Traefik 감시 범위를 확장한다."""
    kubectl = ['kubectl', '--context', context]
    extra = ['--dry-run=server'] if dry_run else []
    run(kubectl + ['apply', '-f', '-', *extra], input=json.dumps(access))
    if len(patch) > 1:
        run(kubectl + ['-n', 'etch-sso', 'patch', 'deployment', 'traefik', '--type=json',
                       '--patch', json.dumps(patch), *extra])
    if not dry_run:
        run(kubectl + ['-n', 'etch-sso', 'rollout', 'status', 'deployment/traefik', '--timeout=300s'])


def chart_path():
    """외부 전달 chart 또는 기본 반입 경로를 반환한다."""
    return Path(os.environ.get('HEADLAMP_CHART_FILE', APP / f"helm/vendor/headlamp-{LOCK['version']}.tgz"))


def verify_chart(path):
    """손상되거나 버전이 다른 chart를 사용하지 않는다."""
    if hashlib.sha256(path.read_bytes()).hexdigest() != LOCK['sha256']:
        raise ValueError('Headlamp chart SHA-256 불일치')


def main():
    """검사는 오프라인으로 수행하고 클러스터 작업은 명시한 context만 사용한다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['fetch-chart', 'check', 'render', 'deploy', 'ui'])
    parser.add_argument('--env', type=Path)
    parser.add_argument('--context', default='')
    args = parser.parse_args()
    try:
        if args.action in {'deploy', 'ui'} and not args.context.strip():
            raise ValueError('KUBE_CONTEXT를 명시하세요.')
        kubectl = ['kubectl', '--context', args.context, '-n', 'headlamp']
        if args.action == 'ui':
            run(kubectl + ['rollout', 'status', 'deployment/headlamp', '--timeout=180s'])
            deployment = json.loads(run(kubectl + ['get', 'deployment', 'headlamp', '-o', 'json'], capture_output=True).stdout)
            base = '/headlamp/' if any('-base-url=/headlamp' in c.get('args', [])
                                      for c in deployment['spec']['template']['spec']['containers']) else '/'
            print(f'http://localhost:4466{base} 로그인용 조회 token (요청 유효기간 1시간):', flush=True)
            run(kubectl + ['create', 'token', 'headlamp-viewer', '--duration=1h'])
            run(kubectl + ['port-forward', '--address', '127.0.0.1', 'svc/headlamp', '4466:80'])
            return
        chart = chart_path()
        if args.action == 'fetch-chart':
            chart.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory() as directory:
                downloaded = Path(directory) / 'chart.tgz'
                urllib.request.urlretrieve(LOCK['url'], downloaded)
                verify_chart(downloaded)
                chart.write_bytes(downloaded.read_bytes())
            print(f'chart 준비 완료: {chart}')
            return
        env = args.env or APP / 'env/k8s.env.example'
        if args.action == 'deploy' and args.env is None:
            raise ValueError('배포에는 실제 --env 파일이 필요합니다.')
        values = settings(env, example=args.env is None)
        verify_chart(chart)
        helm = os.environ.get('HELM_BIN', 'helm')
        with tempfile.TemporaryDirectory() as directory:
            override = Path(directory) / 'values.json'
            override.write_text(json.dumps(values))
            options = ['--namespace', 'headlamp', '-f', str(APP / 'helm/values.yaml'), '-f', str(override)]
            rendered = run([helm, 'template', 'headlamp', str(chart), *options], capture_output=True).stdout
            if args.action == 'render':
                print(rendered, end='')
            elif args.action == 'check':
                print('서버 원본 검사 통과: headlamp/prod (실제 image pull·접속 검사는 별도)')
            else:
                if values.get('ingress', {}).get('enabled'):
                    access, patch = ingress_plan(args.context, values)
                    connect_ingress(args.context, access, patch, dry_run=True)
                # 검사를 통과한 chart와 설정으로만 설치하며 context를 자동 선택하지 않습니다.
                run([helm, 'upgrade', '--install', 'headlamp', str(chart), *options,
                     '--kube-context', args.context, '--create-namespace', '--wait', '--timeout', '5m'])
                if values.get('ingress', {}).get('enabled'):
                    # Helm 실행 중의 변경을 재조회해 최신 namespace 목록을 보존한다.
                    access, patch = ingress_plan(args.context, values)
                    connect_ingress(args.context, access, patch)
                    host = values['ingress']['hosts'][0]['host']
                    print(f'접속 주소: https://{host}/headlamp/')
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        detail = error.stderr if isinstance(error, subprocess.CalledProcessError) and error.stderr else str(error)
        parser.exit(1, f'Headlamp 실행 실패: {detail}\n')


if __name__ == '__main__':
    main()
