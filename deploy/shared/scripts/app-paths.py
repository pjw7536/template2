#!/usr/bin/env python3
"""공통 앱 목록에서 서버 검사 대상 앱 이름을 조회한다."""

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog as registry  # noqa: E402


def read_catalog(path):
    """카탈로그 구조에 더해 경로 소유권을 검사하고 앱 목록을 반환한다."""
    catalog = registry.read_catalog(path)
    for name, app in catalog['apps'].items():
        # 앱 정의는 deploy/<app>이 소유한다. 여러 앱이 함께 쓰는 공용 구성만 deploy/shared 아래에 둔다.
        if app['deployPath'] != f'deploy/{name}' and not app['deployPath'].startswith('deploy/shared/'):
            raise ValueError(f'잘못된 배포 경로: {name}')
        if app['localPath'] not in (None, f'local/{name}'):
            raise ValueError(f'잘못된 로컬 경로: {name}')
        if app['sourcePaths'] not in ([], [f'apps/{name}']):
            raise ValueError(f'잘못된 소스 경로: {name}')
    return catalog


def main():
    """인자 오류는 경로를 출력하기 전에 중단한다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('app')
    args = parser.parse_args()
    try:
        catalog = read_catalog(Path(__file__).resolve().parents[1] / 'apps.json')
        names = [args.app] if args.app in catalog['apps'] else catalog['groups'].get(args.app)
        if not names:
            raise ValueError('지원하지 않는 서버 앱입니다.')
        print('\n'.join(names))
    except (ValueError, KeyError, TypeError, OSError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
