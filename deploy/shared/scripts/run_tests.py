#!/usr/bin/env python3
"""배포 도구와 배포 문서의 단위 테스트를 한 번에 실행한다. 클러스터에 접속하지 않는다."""

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]


def suites():
    """공용 도구, 앱별 도구, 배포 문서 검사 순서의 (폴더, 파일 패턴) 목록."""
    found = [('deploy/shared/tests', 'test_*.py')]
    found += [(path.relative_to(ROOT).as_posix(), 'test_*.py') for path in sorted(ROOT.glob('deploy/*/tests'))
              if path.is_dir() and path.parent.name != 'shared']
    if (ROOT / 'apps/tooling/tests').is_dir():
        found.append(('apps/tooling/tests', 'test_deploy_guides.py'))
    return found


def main():
    failed = []
    for directory, pattern in suites():
        print(f'==> {directory} ({pattern})', flush=True)
        code = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', directory, '-p', pattern], cwd=ROOT).returncode
        if code:
            failed.append(directory)
    print('배포 테스트 결과: ' + ('모두 통과' if not failed else '실패 ' + ', '.join(failed)))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
