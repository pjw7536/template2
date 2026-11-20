"""Airflow DAG 폴더를 연결한 임시 Pod 안에서 실행되어, 표준 입력으로 받은 tar를 폴더에 맞춘다.

`dags.py`가 이 파일 내용을 `python3 -c`로 전달한다. Airflow 이미지의 표준 라이브러리만 사용한다.
- 저장소에 있는 파일: 폴더에 없으면 추가, 내용이 다르면 덮어쓰기, 같으면 그대로 둔다.
- 폴더에만 있는 파일: 지우지 않고 목록으로만 알린다.
- 파일마다 같은 폴더의 고유 임시 파일에 쓴 뒤 이름을 바꿔, Airflow가 쓰는 도중의 파일을 읽지 않게 한다.

사용법: python3 -c <이 파일 내용> <DAG 폴더> check|apply  (표준 입력: tar)
결과는 표준 출력 마지막 줄의 JSON이다.
"""

import io
import json
import os
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

TEMP_SUFFIX = '.dags-sync.tmp'
SKIPPED_DIRS = {'__pycache__'}


def ignored(relative):
    """Python 캐시와 이 도구의 임시 파일은 비교하지 않는다."""
    parts = PurePosixPath(relative).parts
    return any(part in SKIPPED_DIRS for part in parts) or relative.endswith(('.pyc', TEMP_SUFFIX))


def read_archive(data):
    """tar의 일반 파일만 상대 경로와 내용으로 읽는다. 절대 경로·상위 경로·링크는 거부한다."""
    files = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:') as archive:
        for member in archive.getmembers():
            path = PurePosixPath(member.name)
            if not path.parts or path.is_absolute() or '..' in path.parts:
                raise ValueError(f'허용하지 않는 경로: {member.name}')
            if member.isdir():
                continue
            if not member.isfile():
                raise ValueError(f'일반 파일이 아닙니다: {member.name}')
            relative = path.as_posix().removeprefix('./')
            if not ignored(relative):
                files[relative] = archive.extractfile(member).read()
    return files


def current_files(target):
    """폴더의 일반 파일을 상대 경로 목록으로 읽는다. 링크는 따라가지 않는다."""
    found = set()
    for directory, names, filenames in os.walk(target):
        names[:] = [name for name in names if name not in SKIPPED_DIRS]
        for name in filenames:
            path = Path(directory) / name
            relative = path.relative_to(target).as_posix()
            if path.is_file() and not path.is_symlink() and not ignored(relative):
                found.add(relative)
    return found


def plan(files, target):
    """추가·덮어쓰기·같음·폴더에만 있음으로 나눈다."""
    existing = current_files(target)
    result = {'added': [], 'updated': [], 'unchanged': [], 'serverOnly': sorted(existing - set(files))}
    for relative in sorted(files):
        path = destination(target, relative)
        if relative not in existing:
            result['added'].append(relative)
        elif path.read_bytes() != files[relative]:
            result['updated'].append(relative)
        else:
            result['unchanged'].append(relative)
    return result


def destination(target, relative):
    """대상 경로의 링크와 파일·폴더 충돌을 검사한다."""
    path = Path(target)
    parts = PurePosixPath(relative).parts
    for part in parts[:-1]:
        path /= part
        if path.is_symlink() or (path.exists() and not path.is_dir()):
            raise ValueError(f'DAG 하위 폴더로 쓸 수 없습니다: {path}')
    path /= parts[-1]
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError(f'DAG 파일로 쓸 수 없습니다: {path}')
    return path


def apply(files, target, result):
    """추가·덮어쓸 파일만 임시 이름으로 쓰고 이름을 바꿔 반영한다."""
    for relative in [*result['added'], *result['updated']]:
        path = destination(target, relative)
        path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        handle = tempfile.NamedTemporaryFile(dir=path.parent, suffix=TEMP_SUFFIX, delete=False)
        temporary = Path(handle.name)
        try:
            with handle:
                handle.write(files[relative])
                handle.flush()
                os.fsync(handle.fileno())
            temporary.chmod(0o644)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def main(argv):
    target, mode = argv[1], argv[2]
    if mode not in ('check', 'apply'):
        raise ValueError('모드는 check 또는 apply여야 합니다.')
    if not Path(target).is_dir():
        raise ValueError(f'DAG 폴더가 없습니다: {target}')
    files = read_archive(sys.stdin.buffer.read())
    if not files:
        raise ValueError('보낼 DAG 파일이 없습니다.')
    result = plan(files, target)
    if mode == 'apply':
        apply(files, target, result)
    print(json.dumps({'mode': mode, **result}, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main(sys.argv)
    except (OSError, ValueError, tarfile.TarError) as error:
        print(f'오류: {error}', file=sys.stderr)
        sys.exit(1)
