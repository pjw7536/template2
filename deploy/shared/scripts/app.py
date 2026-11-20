#!/usr/bin/env python3
"""카탈로그에 선언한 앱 명령을 실행한다. `make <app>-check|up|smoke|render`의 공통 구현이다.

- check: 입력과 클러스터를 검사하고 변경하지 않는다.
- up: 배포하고, 성공하면 배포 기록을 남긴다.
- render: 현재 checkout의 적용 대상을 `--output` 폴더에 만든다(클러스터 변경 없음).
- smoke: 워크로드 준비 상태와 공개 주소 응답을 조회한다.
- static: 클러스터·실제 입력 없이 저장소 원본만 검사한다.
- command: 실행하지 않고 명령 인자를 JSON으로 출력한다.

입력 파일은 환경변수(예: `AIRFLOW_ENV`) 또는 카탈로그 기본값으로 정한다. 대상 클러스터는 `--context` 또는 `KUBE_CONTEXT`다.
"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

import catalog as registry

ROOT = registry.ROOT
SCRIPTS = Path(__file__).resolve().parent


def execute(argv, environ, run=subprocess.run):
    """저장소 루트에서 실행하고 종료 코드를 돌려준다. 출력은 가리지 않고 그대로 보여 준다."""
    return run(argv, cwd=ROOT, env=environ).returncode


def render(app, context, output, environ=None, run=subprocess.run):
    """렌더 명령을 실행하고 만들어진 파일 경로 목록을 돌려준다. 표준 출력으로 내는 앱은 선언한 이름으로 저장한다."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    argv = registry.command(app, 'render', context, output, environ)
    declared = app.get('render', {})
    result = run(argv, cwd=ROOT, env=registry.child_environment(app, context, environ), capture_output=True, text=True)
    if result.returncode:
        raise ValueError((result.stderr or result.stdout).strip() or '렌더 명령 실패')
    if declared.get('stdout'):
        (output / declared['stdout']).write_text(result.stdout)
        return [output / declared['stdout']]
    return [output / name for name in declared.get('files', [])]


def record(name, context, environ=None, run=subprocess.run):
    """배포 직후 적용 commit·입력 SHA-256·워크로드를 앱 namespace에 기록한다."""
    app = registry.read_catalog()['apps'][name]
    if app.get('runtime') is None:
        return 0
    argv = [sys.executable, str(SCRIPTS / 'deploy_state.py'), 'record', name, '--context', context]
    for path in registry.record_inputs(app, environ):
        argv += ['--input', path]
    return execute(argv, registry.child_environment(app, context, environ), run)


def main(argv=None, run=subprocess.run):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('action', choices=('check', 'up', 'render', 'smoke', 'static', 'record', 'command'))
    parser.add_argument('app')
    parser.add_argument('--context', default=os.environ.get('KUBE_CONTEXT', ''))
    parser.add_argument('--output', help='render 결과를 둘 폴더')
    parser.add_argument('--of', default='up', choices=registry.ACTIONS, help='command가 출력할 명령 종류')
    parser.add_argument('--json', action='store_true', help='smoke 결과를 JSON으로 출력')
    args = parser.parse_args(argv)
    try:
        catalog = registry.read_catalog()
        if args.app not in catalog['apps']:
            raise ValueError(f'apps.json에 없는 앱입니다: {args.app}')
        app = catalog['apps'][args.app]
        context = args.context.strip()
        environ = registry.child_environment(app, context)
        if args.action == 'static':
            for command in registry.static_commands(app):
                result = run(command, cwd=ROOT, env=environ, capture_output=True, text=True)
                if result.returncode:
                    raise ValueError((result.stderr or result.stdout).strip() or f'{" ".join(command)} 실패')
            print(f'서버 원본 검사 통과: {args.app} (실제 입력·클러스터 검사는 make {args.app}-check)')
            return 0
        if not context:
            raise ValueError('KUBE_CONTEXT를 명시하세요.')
        if args.action == 'command':
            print(json.dumps(registry.command(app, args.of, context, args.output or '<out>'), ensure_ascii=False))
            return 0
        if args.action == 'render':
            if not args.output:
                raise ValueError('render에는 --output 폴더가 필요합니다.')
            for path in render(app, context, args.output):
                print(path)
            return 0
        if args.action == 'record':
            return record(args.app, context, run=run)
        if args.action == 'smoke':
            if app.get('runtime') is None:
                print(f'smoke 생략: {args.app}은 클러스터 워크로드가 없는 설정 전용 앱입니다.')
                return 0
            command = [sys.executable, str(SCRIPTS / 'smoke.py'), args.app, '--context', context]
            return execute(command + (['--json'] if args.json else []), environ, run)
        code = execute(registry.command(app, args.action, context), environ, run)
        if code == 0 and args.action == 'up':
            code = record(args.app, context, run=run)
        return code
    except (ValueError, KeyError, OSError) as error:
        print(f'오류: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
