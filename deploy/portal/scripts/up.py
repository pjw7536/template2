#!/usr/bin/env python3
"""Portal의 입력 검사·Secret 등록·migration·앱 적용·공용 Traefik 연결을 한 번에 수행한다.

API 이미지가 바뀌었거나 처음 설치할 때만 migration을 실행한다. 실행 중인 API가 있으면 migration 동안
API를 중지하고 끝난 뒤 원래 replica 수로 되돌린다. DB·PVC·namespace는 삭제하지 않는다.
overlay의 이미지 tag `auto`는 `apps/portal` 소스 내용으로 정한 tag로 바꾼다. 배포·migration·대조가 같은 렌더를 쓴다.
"""

import argparse
import datetime
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'deploy/portal'
OVERLAY = BASE / 'k8s/overlays/prod'
NAMESPACE = 'tailwind-internal'
WORKLOADS = ('deployment/api', 'deployment/web', 'deployment/edge-nginx')
# migration 동안 API를 0으로 줄이기 전의 replica 수. 실패 뒤 재실행이 이 값으로 복원한다.
REPLICAS_ANNOTATION = 'deploy.etch/replicas-before-migration'
spec = importlib.util.spec_from_file_location('deploy_runtime', ROOT / 'deploy/shared/scripts/runtime.py')
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)
image_registry = runtime.module('shared_image_registry', ROOT / 'deploy/shared/scripts/image_registry.py')
# overlay의 이 tag는 소스 내용으로 정한 tag로 바뀐다. 이미지 이름의 마지막 요소가 소스 폴더를 정한다.
AUTO_TAG = 'auto'
SOURCES = {'api': 'apps/portal/api', 'web': 'apps/portal/web'}


def run(args, data=None, env=None):
    """셸 확장 없이 실행하고 실패하면 표준 오류를 오류 메시지로 전달한다."""
    result = subprocess.run(list(map(str, args)), input=data, text=True, capture_output=True, cwd=ROOT,
                            env={**os.environ, **(env or {})})
    if result.returncode:
        raise ValueError((result.stderr or result.stdout).strip() or f'{args[0]} 실행 실패')
    return result.stdout


def build_env():
    """이미지 빌드 입력 파일. tag 계산과 빌드가 같은 파일을 쓴다."""
    return Path(os.environ.get('PORTAL_BUILD_ENV') or BASE / 'env/prod/build.env')


def image_tag(component):
    """`PORTAL_IMAGE_TAG`를 지정하지 않으면 해당 소스 tree와 build.env 내용으로 tag를 정한다."""
    return os.environ.get('PORTAL_IMAGE_TAG', '').strip() or image_registry.source_tag(ROOT, [SOURCES[component]], [build_env()])


def render(kube, overlay):
    """overlay를 렌더하고 tag `auto`인 Portal 이미지를 실제 tag로 바꾼 리소스 목록을 반환한다."""
    items = runtime.render_json(run, kube, overlay)
    for item in items:
        pod = item.get('spec', {}).get('template', {}).get('spec', {})
        for container in pod.get('initContainers', []) + pod.get('containers', []):
            repository, _, tag = container['image'].rpartition(':')
            component = repository.rsplit('/', 1)[-1].removeprefix('portal-')
            if tag == AUTO_TAG and component in SOURCES:
                container['image'] = f'{repository}:{image_tag(component)}'
    return items


def rendered_images(kube):
    """앱·migration overlay의 컨테이너 이미지를 모으고 자리표시자와 API 이미지 불일치를 막는다."""
    images = {}
    for overlay in (OVERLAY, OVERLAY / 'migrate'):
        for item in render(kube, overlay):
            if item['kind'] not in ('Deployment', 'Job'):
                continue
            pod = item['spec']['template']['spec']
            for container in pod.get('initContainers', []) + pod['containers']:
                if runtime.is_placeholder(container['image']):
                    raise ValueError(f'{overlay.relative_to(ROOT)}/kustomization.yaml images의 자리표시자를 교체하세요.')
                images[item['metadata']['name'], container['name']] = container['image']
    if images['api', 'api'] != images['portal-migrate', 'migrate']:
        raise ValueError('prod와 prod/migrate의 images에서 portal-api 버전을 일치시키세요.')
    return images


def job_state(kube, name):
    """Job의 상태를 없음·완료·실패·진행 중으로 구분한다."""
    raw = run([*kube, '-n', NAMESPACE, 'get', 'job', name, '--ignore-not-found', '-o', 'json'])
    if not raw.strip():
        return 'absent'
    status = json.loads(raw).get('status', {})
    if status.get('succeeded'):
        return 'complete'
    return 'failed' if status.get('failed') else 'active'


def plan(kube, images):
    """실제 API Deployment와 비교해 migration 실행 여부와 API 중지 필요 여부를 정한다."""
    raw = run([*kube, '-n', NAMESPACE, 'get', 'deployment', 'api', '--ignore-not-found', '-o', 'json'])
    live = json.loads(raw) if raw.strip() else None
    current = None
    replicas = 0
    interrupted = False
    if live:
        current = next(c['image'] for c in live['spec']['template']['spec']['containers'] if c['name'] == 'api')
        replicas = live['spec'].get('replicas', 1)
        saved = (live.get('metadata', {}).get('annotations') or {}).get(REPLICAS_ANNOTATION, '')
        if saved.isdigit():
            # 이전 실행이 API를 멈춘 채 끝났다. 기록한 수로 복원하고 migration을 이어서 한다.
            replicas, interrupted = int(saved), True
    migrate = live is None or interrupted or current != images['api', 'api']
    selector = ','.join(f'{key}={value}' for key, value in sorted((live or {}).get('spec', {}).get('selector', {}).get('matchLabels', {}).items()))
    return {'installed': live is not None, 'migrate': migrate, 'replicas': replicas, 'interrupted': interrupted, 'selector': selector,
            'maintenance': migrate and live is not None and replicas > 0}


def wait_stopped(scoped, selector):
    """API Pod가 실제로 사라질 때까지 기다린다. replica 0의 rollout status는 종료 중인 Pod를 기다리지 않는다."""
    if not selector:
        return
    try:
        run([*scoped, 'wait', '--for=delete', 'pod', '-l', selector, '--timeout=300s'])
    except ValueError as error:
        if 'no matching resources' not in str(error):
            raise


def start(context, api_env, web_env, check_only=False, force_migrate=False, now=None, retry_failed=False):
    """검사를 모두 통과한 뒤에만 클러스터를 변경한다."""
    if not context.strip():
        raise ValueError('--context를 명시하세요.')
    kube = ['kubectl', '--context', context]
    scoped = [*kube, '-n', NAMESPACE]
    for component, path in (('api', api_env), ('client', api_env), ('web', web_env)):
        run(['bash', ROOT / 'deploy/shared/scripts/check-env.sh', 'portal', 'prod', component, path])
    images = rendered_images(kube)
    run([*kube, 'get', 'nodes', '-o', 'name'])
    namespace_exists = run([*kube, 'get', 'namespace', NAMESPACE, '--ignore-not-found', '-o', 'name']).strip()
    steps = plan(kube, images) if namespace_exists else {'installed': False, 'migrate': True, 'replicas': 0, 'maintenance': False,
                                                        'interrupted': False, 'selector': ''}
    steps['migrate'] = steps['migrate'] or force_migrate
    steps['maintenance'] = steps['migrate'] and steps['installed'] and steps['replicas'] > 0
    previous = job_state(kube, 'portal-migrate') if namespace_exists else 'absent'
    if steps['migrate'] and previous == 'active':
        raise ValueError(f'이전 portal-migrate Job이 진행 중입니다. kubectl --context {context} -n {NAMESPACE} logs job/portal-migrate로 '
                         '끝나기를 확인한 뒤 다시 실행하세요.')
    if steps['migrate'] and previous == 'failed' and not retry_failed:
        raise ValueError(f'이전 portal-migrate Job이 실패 상태입니다. kubectl --context {context} -n {NAMESPACE} logs job/portal-migrate로 '
                         '원인을 해결한 뒤 PORTAL_RETRY_MIGRATE=1을 붙여 다시 실행하세요. 실패한 Job을 지우고 migration을 다시 실행합니다.')
    if check_only:
        print('Portal 입력·이미지·기존 Job 검사 통과. 클러스터를 변경하지 않았습니다.')
        print('migration: ' + ('실행 예정' + (f'(API {steps["replicas"]}개를 중지한 뒤 실행하고 복원)' if steps['maintenance'] else '')
                               if steps['migrate'] else 'API 이미지가 같아 생략'))
        return
    run([*kube, 'apply', '-f', OVERLAY / 'namespace.yaml'])
    for component, path in (('api', api_env), ('web', web_env)):
        run(['bash', ROOT / 'deploy/shared/scripts/apply-env.sh', 'portal', 'prod', component, path], env={'KUBE_CONTEXT': context})
    print('Secret 등록 완료: api-env, web-env', flush=True)
    if steps['migrate']:
        stamp = (now or datetime.datetime.now(datetime.timezone.utc)).strftime('%Y%m%d%H%M%S')
        job = lambda phase, name=None: run(['bash', BASE / 'scripts/migration-job.sh', phase],
                                           env={'KUBE_CONTEXT': context, **({'PORTAL_CHECK_JOB': name} if name else {})})
        # 이전 실행이 migration 도중 끝났으면 DB 상태를 알 수 없으므로 실패해도 API를 자동으로 되돌리지 않는다.
        resumed = steps['interrupted'] or previous == 'failed'
        migrating = False
        try:
            if steps['maintenance']:
                print(f'API 중지: migration 동안 replica {steps["replicas"]} → 0', flush=True)
                run([*scoped, 'annotate', 'deployment/api', f'{REPLICAS_ANNOTATION}={steps["replicas"]}', '--overwrite'])
                run([*scoped, 'scale', 'deployment/api', '--replicas=0'])
                wait_stopped(scoped, steps['selector'])
            if steps['installed']:
                job('pre-migration', f'portal-precheck-{stamp}')
            if previous in ('complete', 'failed'):
                # 끝난 이전 실행 기록만 지운다(실패 Job은 재시도를 명시했을 때만 여기까지 온다). DB·PVC는 건드리지 않는다.
                run([*scoped, 'delete', 'job', 'portal-migrate', '--wait=true'])
            migrating = True
            job('migrate')
            job('post-migration', f'portal-postcheck-{stamp}')
        except ValueError as error:
            if steps['maintenance'] and not migrating and not resumed:
                # migration을 시작하기 전에 멈췄으므로 DB는 그대로다. 서비스를 원래대로 되돌린다.
                run([*scoped, 'scale', 'deployment/api', f'--replicas={steps["replicas"]}'])
                run([*scoped, 'annotate', 'deployment/api', f'{REPLICAS_ANNOTATION}-'])
                raise ValueError(f'migration 전 단계 실패: {error}. DB는 바뀌지 않았고 API를 replica {steps["replicas"]}(으)로 되돌렸습니다. '
                                 '원인을 해결한 뒤 같은 명령을 다시 실행하세요.') from None
            stopped = f' API는 중지 상태입니다(이전 replica {steps["replicas"]}).' if steps['maintenance'] else ''
            raise ValueError(f'migration 단계 실패: {error}.{stopped} 원인을 해결한 뒤 PORTAL_RETRY_MIGRATE=1을 붙여 '
                             '같은 명령을 다시 실행하면 이어서 진행하고 API를 원래 수로 복원합니다.') from None
        print('migration과 사후 검사 완료', flush=True)
    run([*kube, 'apply', '-f', '-'], data=json.dumps({'apiVersion': 'v1', 'kind': 'List', 'items': render(kube, OVERLAY)}))
    if steps['maintenance']:
        # 중지했던 API는 원래 수로 되돌리면 새 Pod가 뜬다. 기록은 복원 뒤 지운다.
        run([*scoped, 'scale', 'deployment/api', f'--replicas={steps["replicas"]}'])
        run([*scoped, 'annotate', 'deployment/api', f'{REPLICAS_ANNOTATION}-'])
    if steps['installed']:
        # Secret 변경은 Pod에 자동 반영되지 않으므로 기존 설치는 배포마다 다시 시작한다.
        run([*scoped, 'rollout', 'restart', *(WORKLOADS[1:] if steps['maintenance'] else WORKLOADS)])
    for workload in WORKLOADS:
        run([*scoped, 'rollout', 'status', workload, '--timeout=10m'])
    run([sys.executable, ROOT / 'deploy/shared/ingress/manage.py', 'connect', '--context', context, '--app', 'portal'])
    print('Portal 배포 완료. 배포 후 확인 절차에서 로그인·파일 송수신을 검증하세요.')


def main():
    """운영 env 두 개와 대상 context를 명시적으로 받는다."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--context', required=True)
    parser.add_argument('--api-env', type=Path, default=BASE / 'env/prod/api.env')
    parser.add_argument('--web-env', type=Path, default=BASE / 'env/prod/web.env')
    parser.add_argument('--check-only', action='store_true')
    parser.add_argument('--migrate', action='store_true', default=os.environ.get('PORTAL_MIGRATE') == '1',
                        help='API 이미지가 같아도 migration을 실행. PORTAL_MIGRATE=1과 같음')
    parser.add_argument('--retry-failed', action='store_true', default=os.environ.get('PORTAL_RETRY_MIGRATE') == '1',
                        help='실패한 이전 portal-migrate Job을 지우고 다시 실행. PORTAL_RETRY_MIGRATE=1과 같음')
    parser.add_argument('--render', choices=('app', 'migrate'), help='적용 대상 JSON만 출력하고 클러스터는 변경하지 않음')
    args = parser.parse_args()
    if args.render:
        items = render(['kubectl', '--context', args.context], OVERLAY if args.render == 'app' else OVERLAY / 'migrate')
        # migration overlay는 Job 하나이므로 그 객체만 출력해 이름·명령을 바꾸기 쉽게 한다.
        print(json.dumps(items[0] if args.render == 'migrate' and len(items) == 1
                         else {'apiVersion': 'v1', 'kind': 'List', 'items': items}))
        return
    start(args.context, args.api_env, args.web_env, args.check_only, args.migrate, retry_failed=args.retry_failed)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, StopIteration) as error:
        print(f'오류: {error}', file=sys.stderr)
        sys.exit(1)
