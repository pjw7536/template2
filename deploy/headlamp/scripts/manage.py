#!/usr/bin/env python3
"""고정 chart로 Headlamp를 검사·배포하고 조회용 접속을 제공한다."""

import argparse
import hashlib
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
        if not separator or key not in {'HEADLAMP_REGISTRY', 'IMAGE_PULL_SECRET'} or key in result:
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
    return {'image': {'registry': registry}, 'imagePullSecrets': [{'name': secret}] if secret else []}


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
            print('http://localhost:4466 로그인용 조회 token (요청 유효기간 1시간):', flush=True)
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
                # 검사를 통과한 chart와 설정으로만 설치하며 context를 자동 선택하지 않습니다.
                run([helm, 'upgrade', '--install', 'headlamp', str(chart), *options,
                     '--kube-context', args.context, '--create-namespace', '--wait', '--timeout', '5m'])
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        detail = error.stderr if isinstance(error, subprocess.CalledProcessError) and error.stderr else str(error)
        parser.exit(1, f'Headlamp 실행 실패: {detail}\n')


if __name__ == '__main__':
    main()
