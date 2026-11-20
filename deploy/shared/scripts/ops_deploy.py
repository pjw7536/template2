#!/usr/bin/env python3
"""앱 하나의 배포 단계(apps.json `steps`)를 순서대로 실행하고 배포 상태 대조까지 수행한다.

각 단계는 루트 Makefile 타깃이다. 첫 실패에서 멈추고 마지막 줄에 JSON 요약을 출력한다.
종료 코드: 0 모든 단계 성공·대조 일치, 1 단계 실패 또는 대조 불일치.
"""

import argparse
import json
import subprocess
import sys

from deploy_state import ROOT, read_catalog


def deploy(app_name, catalog, context, run=subprocess.run):
    """단계별 결과와 최종 대조 코드를 담은 요약을 만든다."""
    app = catalog['apps'][app_name]
    summary = {'app': app_name, 'steps': [], 'failedStep': None, 'driftResultCode': None}
    for target in app['steps']:
        print(f'==> make {target}', flush=True)
        code = run(['make', '--no-print-directory', target, f'KUBE_CONTEXT={context}'], cwd=ROOT).returncode
        summary['steps'].append({'target': target, 'ok': code == 0})
        if code:
            summary['failedStep'] = target
            return summary
    print('==> make drift-check', flush=True)
    result = run(['make', '--no-print-directory', 'drift-check', f'APP={app_name}', f'KUBE_CONTEXT={context}', 'DRIFT_JSON=1'],
                 cwd=ROOT, capture_output=True, text=True)
    try:
        summary['driftResultCode'] = json.loads(result.stdout)['resultCode']
    except (ValueError, KeyError, TypeError):
        summary['driftResultCode'] = 2
    return summary


def main():
    """앱 하나만 받는다. 의존 앱은 배포하지 않고 이름만 알려 준다."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('app')
    parser.add_argument('--context', required=True)
    args = parser.parse_args()
    catalog = read_catalog()
    if args.app not in catalog['apps'] or not args.context.strip():
        print('오류: apps.json의 앱 하나와 KUBE_CONTEXT를 명시하세요.', file=sys.stderr)
        return 1
    depends = catalog['apps'][args.app]['dependsOn']
    if depends:
        print('먼저 배포돼 있어야 하는 앱: ' + ', '.join(depends), flush=True)
    summary = deploy(args.app, catalog, args.context)
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if not summary['failedStep'] and summary['driftResultCode'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
