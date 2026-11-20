"""앱 하나의 배포 입력을 값 노출 없이 검사하고 현장 준비와 재개 지점을 보고한다."""

from functools import partial
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile

from deploy_state import DEFAULT_ENV, read_catalog

OVERLAY = Path('deploy/portal/k8s/overlays/prod')


class InputProblem(Exception):
    """값을 포함하지 않아 담당자에게 그대로 표시할 수 있는 입력 진단."""


def run_check(command, *, data=None):
    """렌더 결과와 하위 도구 오류는 내부에서만 사용한다."""
    return subprocess.run(command, input=data, capture_output=True, text=True, check=True).stdout


def portal_images(context):
    """배포 도구와 같은 렌더로 이미지 자리표시자와 migration·서비스 이미지 일치를 검사한다."""
    from runtime import module
    portal = module('portal_up', 'deploy/portal/scripts/up.py')
    try:
        portal.rendered_images(['kubectl', '--context', context])
    except ValueError as error:
        raise InputProblem(str(error)) from None


def checked(label, remedy, action, *, keys=()):
    """한 항목이 실패해도 독립 검사를 계속하고 공개 입력 키와 복구 방법만 표시한다."""
    try:
        action()
    except subprocess.CalledProcessError as error:
        detail = error.stderr or ''
        mentioned = sorted(set(re.findall(r'[A-Za-z_][A-Za-z_0-9-]*', detail)).intersection(keys))
        if mentioned:
            remedy += ' 확인할 키: ' + ', '.join(mentioned)
        if 'SHA-256' in detail:
            remedy += ' chart.lock.json의 sha256과 반입 파일을 대조하세요.'
    except InputProblem as error:
        remedy += ' ' + str(error)
    except FileNotFoundError as error:
        remedy += f' 필요한 파일 또는 실행 도구: {error.filename}'
    except (KeyError, ValueError, OSError):
        remedy += ' 파일 접근 권한과 렌더 출력 형식을 확인하세요.'
    else:
        print(f'[통과] {label}')
        return True
    print(f'[배포 차단] {label} — {remedy}')
    return False


def check_env(app, env, component, context, directory):
    """배포와 동일한 앱 소유 검사기·렌더러에 실제 입력 경로를 전달한다."""
    if not Path(env).is_file():
        raise InputProblem('선택한 입력 파일이 없습니다.')
    if app in ('portal', 'keycloak'):
        run_check(['bash', 'deploy/shared/scripts/check-env.sh', app, 'prod', component, env])
    elif app == 'ftp':
        run_check([sys.executable, 'deploy/ftp/scripts/up.py', '--render-output', Path(directory) / 'ftp.json',
                   '--env', env, '--context', context])
    else:
        run_check([sys.executable, f'deploy/{app}/scripts/manage.py', 'check', '--env', env])


def declared_keys(path):
    """원본 파일을 읽을 수 있을 때 진단에 사용할 공개 키 이름만 반환한다."""
    try:
        return re.findall(r'^([A-Za-z_][A-Za-z_0-9-]*)=', Path(path).read_text(), re.M)
    except (OSError, UnicodeError):
        return []


def main():
    """관리 호스트의 checkout 루트에서 선택한 앱 하나를 검사한다."""
    app = os.environ.get('APP', '')
    context = os.environ.get('KUBE_CONTEXT', '').strip()
    catalog = read_catalog()
    if app not in catalog['apps'] or os.environ.get('PROFILE', 'prod') != 'prod' or not context:
        print('[배포 차단] apps.json의 앱 하나와 KUBE_CONTEXT를 명시하세요. PROFILE은 prod입니다.')
        return 1

    base = Path(catalog['apps'][app]['deployPath'])
    guide = base / 'README.md'
    retry = ['make', 'ops-preflight', f'APP={app}', 'PROFILE=prod', f'KUBE_CONTEXT={context}']
    results = []
    chart_lock = base / 'helm/chart.lock.json'
    if chart_lock.exists():
        lock = json.loads(chart_lock.read_text())
        key = app.upper() + '_CHART_FILE'
        chart = Path(os.getenv(key) or base / 'helm/vendor' / f'{lock["name"]}-{lock["version"]}.tgz')
        if os.getenv(key):
            retry.append(f'{key}={chart}')
        if not chart.is_file():
            print(f'[배포 차단] {chart} — 담당자가 {chart_lock}의 chart를 반입하거나 {key} 경로를 지정하세요.')
            results.append(False)

    results.append(checked('KUBE_CONTEXT=' + context, '관리 호스트에서 kubeconfig·API 접속·노드 조회 권한을 확인하세요.',
                           partial(run_check, ['kubectl', '--context', context, '--request-timeout=8s', 'get', 'nodes', '-o', 'name'])))
    results.append(checked(f'{base} 배포 원본', f'{guide}의 도구·chart·배포 정의를 확인하세요.',
                           partial(run_check, ['bash', 'deploy/shared/scripts/check-server.sh', app, 'prod'])))
    if app == 'portal':
        results.append(checked(f'{OVERLAY} 및 migrate의 images', 'API·Web·migration overlay를 확인하세요.',
                               partial(portal_images, context)))
        inputs = [('api', 'PROD_API_ENV_FILE', 'deploy/portal/env/prod/api.env'),
                  ('client', 'PROD_API_ENV_FILE', 'deploy/portal/env/prod/api.env'),
                  ('web', 'PROD_WEB_ENV_FILE', 'deploy/portal/env/prod/web.env')]
    else:
        inputs = [('server', catalog['apps'][app]['env']['variable'], DEFAULT_ENV[app])]

    with tempfile.TemporaryDirectory(prefix='ops-preflight-') as directory:
        for component, key, default in inputs:
            env = os.getenv(key) or default
            if Path(env).resolve() != Path(default).resolve() and f'{key}={env}' not in retry:
                retry.append(f'{key}={env}')
            # 하위 도구의 오류에서는 저장소 원본에 선언된 키 이름만 보고한다.
            keys = declared_keys(default)
            results.append(checked(f'{key}={env} ({component})', f'담당자가 {guide}의 실제 입력과 도구를 확인하세요.',
                                   partial(check_env, app, env, component, context, directory), keys=keys))

    if app in ('portal', 'keycloak'):
        source = f'{OVERLAY}/kustomization.yaml images' if app == 'portal' else 'deploy/keycloak/k8s/kustomization.yaml images'
    else:
        image_keys = sorted(key for key in keys if ('REGISTRY' in key or 'IMAGE' in key) and 'SECRET' not in key)
        source = f'{env} ({" / ".join(image_keys)})'
    transport = '반입 이미지의 k8s.io 등록 또는 미러 pull' if app == 'airflow' else '미러 pull'
    print(f'[현장 확인 필요] {source} — Worker 담당자가 배치 노드의 {transport} 가능 여부를 확인하세요.')
    print(f'[현장 확인 필요] {guide} — 앱 담당자가 디스크·서비스 연결과 앱별 선행 조건을 확인하세요.')
    print('재검사: ' + shlex.join(retry))
    return 0 if all(results) else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, KeyError, ValueError):
        print('[배포 차단] checkout의 apps.json·chart.lock.json·입력 파일 형식과 읽기 권한을 확인한 뒤 같은 명령을 실행하세요.')
        sys.exit(1)
