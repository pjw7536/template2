#!/usr/bin/env python3
"""앱 하나를 준비 검사 → 배포 단계(apps.json `steps`) → 배포 상태 대조 순서로 끝까지 진행한다.

- 준비 검사: `ops_preflight.py`의 항목을 조회하고, 저장소 도구로 끝낼 수 있는 준비(chart 받기·CA 묶음·빌드 도구·공용 TLS 등록)를 실행한다.
  저장소 도구로 해결할 수 없는 항목이 남으면 배포 단계를 시작하지 않고 `blocked`에 담아 멈춘다.
- 배포 단계: 루트 Makefile 타깃을 순서대로 실행한다. 검사(`<app>-check`)가 클러스터를 바꾸는 단계보다 먼저다.
- 대조: 현재 checkout과 클러스터를 비교한다.

마지막 줄에 JSON 요약을 출력한다. `failedStep`이 null이고 `driftResultCode`가 0이면 성공이다.
종료 코드: 0 성공, 1 준비 검사에서 막힘·단계 실패·대조 불일치.
"""

import argparse
import json
import subprocess
import sys

import catalog as registry
import ops_preflight as preflight

ROOT = registry.ROOT


def deploy(app_name, catalog, context, run=subprocess.run):
    """단계별 결과와 최종 대조 코드를 담은 요약을 만든다."""
    app = catalog['apps'][app_name]
    summary = {'app': app_name, 'blocked': [], 'pending': [], 'steps': [], 'failedStep': None, 'driftResultCode': None}
    for target in app['steps']:
        print(f'==> make {target}', flush=True)
        code = run(['make', '--no-print-directory', target, f'KUBE_CONTEXT={context}'], cwd=ROOT).returncode
        summary['steps'].append({'target': target, 'ok': code == 0})
        if code:
            summary['failedStep'] = target
            return summary
    if app.get('runtime') is None:
        # 클러스터 워크로드가 없는 설정 전용 앱은 대조할 리소스가 없다.
        summary['driftResultCode'] = 0
        return summary
    print('==> make drift-check', flush=True)
    result = run(['make', '--no-print-directory', 'drift-check', f'APP={app_name}', f'KUBE_CONTEXT={context}', 'DRIFT_JSON=1'],
                 cwd=ROOT, capture_output=True, text=True)
    try:
        summary['driftResultCode'] = json.loads(result.stdout)['resultCode']
    except (ValueError, KeyError, TypeError):
        summary['driftResultCode'] = 2
    return summary


def ready(app_name, catalog, context):
    """준비 검사를 실행하고 (막힌 항목, 배포를 막지 않는 남은 일)을 돌려준다."""
    print(f'==> 준비 검사: {app_name}', flush=True)
    results = preflight.evaluate(app_name, catalog, context, run_prepare=True)
    print('\n'.join(preflight.render(results)), flush=True)
    brief = lambda entry: {key: entry[key] for key in ('item', 'detail', 'command', 'reference') if entry.get(key)}
    return ([brief(entry) for entry in preflight.blocking(results)],
            [brief(entry) for entry in results if entry['state'] == preflight.INFO])


def main(argv=None):
    """앱 하나만 받는다. 먼저 필요한 앱은 배포하지 않고 준비 검사에서 알려 준다."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('app')
    parser.add_argument('--context', required=True)
    parser.add_argument('--skip-preflight', action='store_true', help='준비 검사를 생략하고 배포 단계부터 실행')
    args = parser.parse_args(argv)
    catalog = registry.read_catalog()
    if args.app not in catalog['apps'] or not args.context.strip():
        print('오류: apps.json의 앱 하나와 KUBE_CONTEXT를 명시하세요.', file=sys.stderr)
        return 1
    blocked, pending = ([], []) if args.skip_preflight else ready(args.app, catalog, args.context)
    if blocked:
        summary = {'app': args.app, 'blocked': blocked, 'pending': pending, 'steps': [], 'failedStep': 'preflight',
                   'driftResultCode': None}
    else:
        summary = deploy(args.app, catalog, args.context)
        summary['pending'] = pending
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if not summary['failedStep'] and summary['driftResultCode'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
