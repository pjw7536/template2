#!/usr/bin/env python3
"""앱 소유 경로와 현재 파일의 이전 소스 경로 참조를 검사한다."""

import importlib.util
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location('app_paths', ROOT / 'deploy/shared/scripts/app-paths.py')
APP_PATHS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(APP_PATHS)
OLD_PORTAL = re.compile(r'\bapps/' + r'(?:api|web)(?:/|\b)')
OLD_AIRFLOW = re.compile(r'(?<!apps/)(?<!opt/)(?<!deploy/)(?<!\w)airflow/' + r'(?:dags|plugins|tests|Dockerfile)(?:/|\b)')


def check_text(path, content):
    """역사 기록을 제외하고 실제 사용 파일의 경로 위반을 찾는다."""
    if path.startswith('docs/agent/plans/'):
        return []
    findings = []
    if OLD_PORTAL.search(content) or OLD_AIRFLOW.search(content):
        findings.append(f'{path}: 이전 소스 경로 참조')
    if path.startswith('deploy/') and '/scripts/' in path and path.endswith(('.py', '.sh')):
        if re.search(r'''(?:["']local/[a-z_]+(?:/|["'])|/\s*["']local["'])''', content):
            findings.append(f'{path}: 서버 실행 도구가 local 경로 참조')
    return findings


def check_catalog(root, catalog):
    """전체 개발 checkout에서 앱 목록이 실제 디렉터리와 일치하는지 검사한다."""
    findings = []
    for app in catalog['apps'].values():
        paths = [app['deployPath'], *app['sourcePaths']]
        if app['localPath']:
            paths.append(app['localPath'])
        for path in paths:
            if not (root / path).is_dir():
                findings.append(f'{path}: 앱 목록의 디렉터리 누락')
    for path in ('apps/' + 'api', 'apps/' + 'web', 'deploy/airflow/image'):
        if (root / path).exists():
            findings.append(f'{path}: 이전 소스 원본이 남아 있음')
    # 실행 서비스가 아닌 tooling·공통 도구·mock만 앱 목록 밖에서 허용합니다.
    owned = {'apps': {'apps/tooling'}, 'deploy': {'deploy/shared'},
             'local': {'local/shared', 'local/adfs_dummy'}}
    for app in catalog['apps'].values():
        owned['apps'].update(app['sourcePaths'])
        owned['deploy'].add(app['deployPath'])
        if app['localPath']:
            owned['local'].add(app['localPath'])
    for area, allowed in owned.items():
        parent = root / area
        if not parent.is_dir():
            continue
        for directory in parent.iterdir():
            if directory.is_dir() and not directory.name.startswith('.') and directory.name != '__pycache__':
                relative = directory.relative_to(root).as_posix()
                if relative not in allowed:
                    findings.append(f'{relative}: 앱 목록에 없는 소유 디렉터리')
    return findings


def check_root(root):
    """생성물과 숨김 도구를 제외한 최상위 관리 폴더를 제한한다."""
    allowed = {'apps', 'data', 'deploy', 'docs', 'local', '__pycache__'}
    findings = [f'{path.name}: 허용되지 않은 최상위 관리 폴더'
            for path in root.iterdir()
            if path.is_dir() and not path.name.startswith('.') and path.name not in allowed]
    forbidden = [root / 'package.json', root / 'package-lock.json', *root.glob('docker-compose*.yml'), *root.glob('docker-compose*.yaml')]
    findings.extend(f'{path.name}: 루트 대신 소유 프로젝트에서 관리해야 합니다.' for path in forbidden if path.exists())
    return findings


def main():
    """Git 관리 대상 파일만 읽고 위반이 있으면 실패 상태를 반환한다."""
    catalog = APP_PATHS.read_catalog(ROOT / 'deploy/shared/apps.json')
    findings = check_catalog(ROOT, catalog) + check_root(ROOT)
    paths = subprocess.check_output(['git', 'ls-files', '-co', '--exclude-standard', '-z'], cwd=ROOT).decode().split('\0')
    for path in sorted(set(paths) - {''}):
        source = ROOT / path
        if not source.is_file():
            continue
        try:
            findings.extend(check_text(path, source.read_text()))
        except UnicodeError:
            continue
    print('\n'.join(findings) if findings else 'OK: 앱 소유 경로·서버 의존·이전 소스 경로 검사')
    return int(bool(findings))


if __name__ == '__main__':
    raise SystemExit(main())
