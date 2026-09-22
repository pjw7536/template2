#!/usr/bin/env python3
"""공통 앱 목록에서 서버 checkout 경로와 검사 앱 이름을 조회한다."""

import argparse
import json
from pathlib import Path


def read_catalog(path):
    """경로 소유권과 그룹 구성을 검사하고 앱 목록을 반환한다."""
    catalog = json.loads(path.read_text())
    apps, groups = catalog['apps'], catalog['groups']
    for name, app in apps.items():
        if not name.replace('-', '').isalnum() or not name.islower():
            raise ValueError(f'잘못된 앱 이름: {name}')
        if app['deployPath'] != f'deploy/{name}':
            raise ValueError(f'잘못된 배포 경로: {name}')
        if app['localPath'] not in (None, f'local/{name}'):
            raise ValueError(f'잘못된 로컬 경로: {name}')
        if app['sourcePaths'] not in ([], [f'apps/{name}']):
            raise ValueError(f'잘못된 소스 경로: {name}')
    for name, members in groups.items():
        if name in apps or not members or len(set(members)) != len(members) or any(member not in apps for member in members):
            raise ValueError(f'잘못된 앱 그룹: {name}')
    if set(groups['all']) != set(apps):
        raise ValueError('all 그룹은 모든 앱을 포함해야 합니다.')
    return catalog


def main():
    """인자 오류는 경로를 출력하기 전에 중단한다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('app')
    parser.add_argument('--with-source', action='store_true')
    parser.add_argument('--names', action='store_true')
    args = parser.parse_args()
    try:
        catalog = read_catalog(Path(__file__).resolve().parents[1] / 'apps.json')
        names = [args.app] if args.app in catalog['apps'] else catalog['groups'].get(args.app)
        if not names:
            raise ValueError('지원하지 않는 서버 앱입니다.')
        paths = ['deploy/shared', 'docs']
        for name in names:
            app = catalog['apps'][name]
            paths.append(app['deployPath'])
            if args.with_source:
                paths.extend(app['sourcePaths'])
        print('\n'.join(names if args.names else paths))
    except (ValueError, KeyError, TypeError, OSError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
