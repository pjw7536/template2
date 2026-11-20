#!/usr/bin/env python3
"""앱 하나를 배포하기 전에 준비 상태를 조회하고, 저장소 도구로 끝낼 수 있는 준비는 요청하면 실행한다.

확인 항목은 카탈로그(`deploy/shared/apps.json`)에서 나온다: 클러스터 접속, 저장소 원본, 먼저 필요한 앱, 입력 파일,
chart, 사내 CA 묶음, 이미지 빌드 도구, 공개 host의 공용 TLS 등록과 DNS.

출력의 각 줄은 다음 중 하나로 시작한다.
- `[통과]` 준비됨
- `[자동 준비]` 표시한 명령으로 준비할 수 있음. `--prepare`를 주면 그 명령을 실행한다.
- `[배포 차단]` 저장소 도구로 해결할 수 없음. 필요한 것과 접근 경로 표의 행을 알려 준다.
- `[안내]` 배포를 막지 않는 남은 일(DNS 등록 등)

종료 코드: 0 배포 가능, 1 `[배포 차단]` 또는 실행하지 않은 `[자동 준비]`가 있음.
값은 출력하지 않는다. 입력 파일의 내용 검사는 `make <app>-check`가 한다.
"""

import argparse
import json
import os
from pathlib import Path
import shlex
import socket
import subprocess
import sys

import ca_bundle
import catalog as registry
from runtime import module

ROOT = registry.ROOT
CERTS = ROOT / 'deploy/shared/certs'
ACCESS = 'deploy/shared/docs/infrastructure/access.md'
INGRESS_NAMESPACE = 'etch-sso'
tls = module('shared_tls', ROOT / 'deploy/shared/ingress/tls.py')

OK, ACTION, BLOCKED, INFO = 'ok', 'action', 'blocked', 'info'
LABEL = {OK: '통과', ACTION: '자동 준비', BLOCKED: '배포 차단', INFO: '안내'}


def item(name, state, detail, command=None, reference=None):
    """확인 결과 한 건. command는 저장소 루트에서 실행하는 인자 목록이다."""
    return {'item': name, 'state': state, 'detail': detail, 'command': command, 'reference': reference}


def run_quiet(argv, data=None, environ=None):
    """명령을 실행해 (성공 여부, 출력)을 돌려준다. 실행 파일이 없으면 실패로 본다."""
    try:
        result = subprocess.run([str(part) for part in argv], input=data, capture_output=True, text=True, cwd=ROOT, env=environ)
    except OSError as error:
        return False, str(error)
    return result.returncode == 0, (result.stdout if result.returncode == 0 else result.stderr or result.stdout)


def resolves(host):
    """관리 호스트에서 host가 DNS로 조회되는지 본다."""
    try:
        socket.getaddrinfo(host, 443)
        return True
    except OSError:
        return False


def certificate_files(host, validate=None, directory=CERTS):
    """`deploy/shared/certs/<사이트>/`에서 host를 SAN에 가진 인증서·개인키 쌍을 찾는다. 없으면 None."""
    validate = validate or tls.validate
    for folder in sorted(path for path in Path(directory).glob('*') if path.is_dir()):
        cert, key = folder / 'fullchain.crt', folder / 'private.key'
        if not (cert.is_file() and key.is_file()):
            continue
        try:
            validate(host, cert.read_text(), key.read_text())
        except (ValueError, OSError):
            continue
        return cert, key
    return None


def check_cluster(kube):
    ok, _ = run_quiet([*kube, '--request-timeout=8s', 'get', 'nodes', '-o', 'name'])
    if ok:
        return item('클러스터 접속', OK, 'API 접속과 노드 조회 가능')
    return item('클러스터 접속', BLOCKED, 'KUBE_CONTEXT의 kubeconfig·API 주소·노드 조회 권한을 확인해야 합니다.', reference=f'{ACCESS}#kubernetes-api')


def check_source(name):
    ok, output = run_quiet([sys.executable, 'deploy/shared/scripts/app.py', 'static', name])
    if ok:
        return item('저장소 원본', OK, '배포 정의 정적 검사 통과')
    return item('저장소 원본', BLOCKED, '저장소의 배포 정의가 검사를 통과하지 못했습니다. 저장소 수정이 필요합니다: '
                + (output.strip().splitlines() or ['원인 출력 없음'])[-1])


def check_depends(catalog, app, kube):
    found = []
    for dependency in app.get('dependsOn', []):
        target = catalog['apps'][dependency]
        if target.get('runtime') is None:
            continue
        selector = target['runtime'].get('selector')
        argv = [*kube, '-n', registry.namespace(target), 'get', 'deployments,statefulsets,daemonsets', '-o', 'name', '--ignore-not-found']
        ok, output = run_quiet(argv + (['-l', selector] if selector else []))
        if ok and output.strip():
            found.append(item(f'먼저 필요한 앱 {dependency}', OK, '워크로드 있음'))
        else:
            found.append(item(f'먼저 필요한 앱 {dependency}', BLOCKED, f'{dependency}를 먼저 배포해야 합니다.',
                              command=['make', 'ops-deploy', f'APP={dependency}']))
    return found


def check_inputs(app):
    found = []
    for variable, path in registry.inputs(app).items():
        if Path(path).is_file():
            found.append(item(f'입력 {variable}', OK, registry_path(path)))
        else:
            found.append(item(f'입력 {variable}', BLOCKED, f'파일이 없습니다: {registry_path(path)}. 경로를 {variable}로 지정하거나 파일을 준비해야 합니다.',
                              reference=f'{ACCESS}#운영-입력-파일'))
    return found


def registry_path(path):
    """저장소 안의 경로는 루트 기준으로 줄여 보여 준다."""
    try:
        return Path(path).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def check_chart(name, app):
    lock_path = app.get('chart')
    if not lock_path:
        return []
    lock = json.loads((ROOT / lock_path).read_text())
    variable = name.upper() + '_CHART_FILE'
    chart = Path(os.environ.get(variable) or ROOT / Path(lock_path).parent / 'vendor' / f'{lock["name"]}-{lock["version"]}.tgz')
    if chart.is_file():
        return [item('chart', OK, registry_path(chart))]
    return [item('chart', ACTION, f'{registry_path(chart)}가 없습니다. 사내 미러에서 받습니다.', command=['make', f'{name}-fetch-chart'],
                 reference=f'{ACCESS}#파일-반입')]


def check_ca_bundle(catalog, app):
    owner = app.get('caBundle')
    if not owner:
        return []
    hosts = registry.hosts(catalog['apps'][owner])
    if not hosts:
        return [item('사내 CA 묶음', BLOCKED, f'{owner}의 공개 주소를 env에서 읽지 못했습니다.')]
    if ca_bundle.bundle_path(hosts[0]).is_file():
        return [item('사내 CA 묶음', OK, registry_path(ca_bundle.bundle_path(hosts[0])))]
    if ca_bundle.bundle_text():
        return [item('사내 CA 묶음', ACTION, 'CA 폴더의 파일로 묶음을 만듭니다.', command=['make', 'ca-bundle', f'CA_HOST={hosts[0]}'])]
    return [item('사내 CA 묶음', BLOCKED, 'deploy/shared/certs/ca/에 사내 Root·Issuing CA 파일이 필요합니다.', reference=f'{ACCESS}#인증서-발급')]


def check_build_tools(app):
    if not app.get('buildsImage'):
        return []
    ok, _ = run_quiet(['make', '--no-print-directory', 'build-tools-check'])
    if ok:
        return [item('이미지 빌드 도구', OK, 'nerdctl·BuildKit 사용 가능')]
    return [item('이미지 빌드 도구', ACTION, 'nerdctl·BuildKit을 설치합니다(비밀번호 없는 sudo 필요).', command=['make', 'build-tools-install'],
                 reference=f'{ACCESS}#관리-호스트-sudo')]


def check_hosts(app, kube, context, registered=None, lookup=resolves, find=certificate_files):
    """공개 host마다 공용 TLS 등록과 DNS를 본다. registered(host)는 등록돼 있으면 True를 돌려준다."""
    def default_registered(host):
        try:
            tls.prepare(kube, host)
            return True
        except (ValueError, OSError):
            return False

    registered = registered or default_registered
    found = []
    for host in registry.hosts(app):
        if registered(host):
            found.append(item(f'공용 TLS {host}', OK, '등록됨'))
        else:
            files = find(host)
            if files:
                command = ['make', 'ingress-tls-up', f'KUBE_CONTEXT={context}', f'TLS_HOST={host}',
                           f'TLS_CERT_FILE={files[0]}', f'TLS_KEY_FILE={files[1]}']
                found.append(item(f'공용 TLS {host}', ACTION, f'{registry_path(files[0].parent)}의 인증서를 등록합니다.', command=command))
            else:
                found.append(item(f'공용 TLS {host}', BLOCKED,
                                  f'{host}를 SAN에 가진 fullchain.crt·private.key를 deploy/shared/certs/<사이트>/에 두어야 합니다.',
                                  reference=f'{ACCESS}#인증서-발급'))
        if lookup(host):
            found.append(item(f'DNS {host}', OK, '조회됨'))
        else:
            found.append(item(f'DNS {host}', INFO, 'DNS에 없습니다. 배포는 진행하고 smoke는 APP VIP로 확인합니다. 등록이 남았습니다.',
                              reference=f'{ACCESS}#dns'))
    return found


def check_app(name, context):
    """앱의 입력·클러스터 검사(`make <app>-check`)를 실행한다. 클러스터를 바꾸지 않는다."""
    # make를 거치면 실패 원인 대신 make의 오류 줄이 마지막에 남으므로 같은 명령을 직접 실행한다.
    ok, output = run_quiet([sys.executable, 'deploy/shared/scripts/app.py', 'check', name, '--context', context])
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    tail = lines[-1] if lines else '출력 없음'
    if ok:
        return item('앱 검사', OK, tail)
    return item('앱 검사', BLOCKED, f'make {name}-check 실패: {tail}')


def collect(name, catalog, context):
    """한 앱의 확인 결과 목록. 클러스터에 닿지 않으면 클러스터가 필요한 확인은 건너뛴다."""
    app = catalog['apps'][name]
    kube = ['kubectl', '--context', context]
    cluster = check_cluster(kube)
    chart = check_chart(name, app)
    # chart로 렌더하는 앱의 정적 검사는 chart가 있어야 한다. 없으면 받은 뒤에 검사한다.
    source = (item('저장소 원본', INFO, 'chart를 받은 뒤 검사합니다.') if any(entry['state'] != OK for entry in chart)
              else check_source(name))
    results = [cluster, source, *check_inputs(app), *chart, *check_ca_bundle(catalog, app), *check_build_tools(app)]
    if cluster['state'] == OK:
        depends = check_depends(catalog, app, kube)
        results += depends
        # 공용 TLS 저장소는 공용 Traefik과 함께 생긴다. 먼저 필요한 앱이 없으면 host 확인은 그 뒤에 한다.
        if all(entry['state'] == OK for entry in depends):
            results += check_hosts(app, kube, context)
    # 앱 자체 검사는 준비가 끝난 뒤에만 의미가 있다. 남은 준비가 있으면 그 뒤에 실행한다(ops-deploy의 첫 단계이기도 하다).
    if not blocking(results):
        results.append(check_app(name, context))
    else:
        results.append(item('앱 검사', INFO, f'위 항목을 준비한 뒤 make {name}-check로 확인합니다.'))
    return results


def prepare(results, execute=None):
    """`[자동 준비]` 명령을 실행한다. 성공하면 통과로, 실패하면 배포 차단으로 바꾼다."""
    execute = execute or run_quiet
    for entry in results:
        if entry['state'] != ACTION:
            continue
        print(f'==> {shlex.join(entry["command"])}', file=sys.stderr, flush=True)
        ok, output = execute(entry['command'])
        tail = (output.strip().splitlines() or [''])[-1]
        entry['state'] = OK if ok else BLOCKED
        entry['detail'] = f'준비 완료: {tail}' if ok else f'자동 준비 실패: {tail}'
    return results


def evaluate(name, catalog, context, run_prepare=False):
    """준비 상태를 조회하고, 요청하면 자동 준비를 실행한 뒤 다시 조회한다.

    자동 준비가 모두 성공하면 그 결과에 의존하던 확인(정적 검사·host 등록·앱 검사)을 새로 평가한다.
    실패한 준비가 있으면 실패 사유를 보존하려고 다시 조회하지 않는다.
    """
    results = collect(name, catalog, context)
    if run_prepare and any(entry['state'] == ACTION for entry in results):
        prepare(results)
        if not any(entry['state'] == BLOCKED and entry['detail'].startswith('자동 준비 실패') for entry in results):
            results = collect(name, catalog, context)
    return results


def render(results):
    lines = []
    for entry in results:
        line = f'[{LABEL[entry["state"]]}] {entry["item"]} — {entry["detail"]}'
        if entry['command'] and entry['state'] != OK:
            line += f' 명령: {shlex.join(entry["command"])}'
        if entry['reference'] and entry['state'] != OK:
            line += f' 볼 곳: {entry["reference"]}'
        lines.append(line)
    return lines


def blocking(results):
    """배포를 막는 항목만 고른다."""
    return [entry for entry in results if entry['state'] in (ACTION, BLOCKED)]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('app')
    parser.add_argument('--context', default=os.environ.get('KUBE_CONTEXT', ''))
    parser.add_argument('--prepare', action='store_true', help='[자동 준비] 명령을 실행')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    try:
        catalog = registry.read_catalog()
        if args.app not in catalog['apps'] or not args.context.strip():
            raise ValueError('apps.json의 앱 하나와 KUBE_CONTEXT를 명시하세요.')
        results = evaluate(args.app, catalog, args.context.strip(), args.prepare)
    except (ValueError, KeyError, OSError) as error:
        print(f'[배포 차단] 준비 검사 — {error}', file=sys.stderr if args.json else sys.stdout)
        return 1
    blocked = blocking(results)
    if args.json:
        print(json.dumps({'app': args.app, 'ready': not blocked, 'items': results}, ensure_ascii=False, indent=2))
    else:
        print('\n'.join(render(results)))
        print(f'준비 검사 결과: {"배포 가능" if not blocked else f"남은 항목 {len(blocked)}건"} ({args.app})')
    return 1 if blocked else 0


if __name__ == '__main__':
    sys.exit(main())
