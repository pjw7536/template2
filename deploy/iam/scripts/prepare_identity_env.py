#!/usr/bin/env python3
"""공용 인증 입력을 기존 Keycloak·Etch Members 운영 env 사본에 합칩니다."""

import argparse
import fcntl
import os
from pathlib import Path
import re
import stat
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'deploy/shared/scripts'))
from runtime import is_placeholder  # noqa: E402

OIDC_KEYS = ('CORP_OIDC_CLIENT_ID', 'CORP_OIDC_CLIENT_SECRET')
ADMIN_KEY = 'IAM_PLATFORM_ADMIN_USERNAMES'
ENV_KEY = re.compile(r'[A-Za-z_][A-Za-z0-9_-]*')


def read_env(path):
    """env를 실행하지 않고 읽으며 중복이나 형식 오류에는 값이 아닌 줄 번호를 표시합니다."""
    values = {}
    try:
        lines = path.read_text().splitlines()
    except UnicodeDecodeError:
        raise ValueError(f'{path.name}의 UTF-8 형식을 확인하세요.') from None
    for number, line in enumerate(lines, 1):
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        key, separator, value = line.partition('=')
        if not separator or not ENV_KEY.fullmatch(key) or key in values or '\0' in value:
            raise ValueError(f'{path.name} {number}행의 KEY=값 형식 또는 중복 키를 확인하세요.')
        values[key] = value
    return values


def prepare(identity, keycloak_base, iam_base):
    """모든 입력을 검사하고 비공개 임시 파일 두 개를 준비한 뒤 고정 경로에 교체합니다."""
    identity = identity.resolve()
    if identity.is_relative_to(ROOT):
        raise ValueError('인증 운영 입력은 checkout 밖에 두세요.')
    metadata = identity.stat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o077:
        raise ValueError('identity.env는 그룹·다른 사용자 권한이 없는 일반 파일이어야 합니다(예: 0600).')
    selected = read_env(identity)
    if set(selected) - {*OIDC_KEYS, ADMIN_KEY}:
        raise ValueError('identity.env에는 사내 OIDC client ID·secret과 IAM 관리자 EPID 키만 사용할 수 있습니다.')
    for key in OIDC_KEYS:
        value = selected.get(key, '')
        if not value.strip() or is_placeholder(value):
            raise ValueError(f'identity.env의 {key}에 발급받은 값을 입력하세요.')

    output = identity.with_name(identity.name + '.generated')
    bases = {'keycloak.env': keycloak_base.resolve(), 'iam.env': iam_base.resolve()}
    result = {}
    for name, base in bases.items():
        if base == identity or base.is_relative_to(output):
            raise ValueError('기존 앱 env를 원본으로 사용하세요. identity.env와 생성본은 원본으로 쓸 수 없습니다.')
        result[name] = read_env(base)
    result['keycloak.env'].update({key: selected[key] for key in OIDC_KEYS})
    if ADMIN_KEY in selected:
        result['iam.env'][ADMIN_KEY] = selected[ADMIN_KEY]

    output.mkdir(mode=0o700, exist_ok=True)
    metadata = output.lstat()
    if (not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.geteuid()
            or stat.S_IMODE(metadata.st_mode) != 0o700):
        raise ValueError('생성 위치는 실행 계정 소유의 권한 0700 디렉터리여야 합니다.')
    directory_fd = os.open(output, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        fcntl.flock(directory_fd, fcntl.LOCK_EX)
        with tempfile.TemporaryDirectory(dir=output) as directory:
            staging = Path(directory)
            for name, values in result.items():
                path = staging / name
                path.touch(mode=0o600)
                path.write_text(''.join(f'{key}={value}\n' for key, value in values.items()))
            for name in result:
                (staging / name).replace(output / name)
    finally:
        os.close(directory_fd)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--identity-env', required=True, type=Path)
    parser.add_argument('--keycloak-base', required=True, type=Path)
    parser.add_argument('--iam-base', required=True, type=Path)
    args = parser.parse_args()
    try:
        output = prepare(args.identity_env, args.keycloak_base, args.iam_base)
    except (OSError, ValueError) as error:
        parser.exit(1, f'인증 운영 입력 준비 실패: {error}\n')
    print(f'KEYCLOAK_ENV={output / "keycloak.env"}')
    print(f'IAM_ENV={output / "iam.env"}')


if __name__ == '__main__':
    main()
