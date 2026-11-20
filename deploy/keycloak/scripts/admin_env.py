#!/usr/bin/env python3
"""Keycloak env의 관리자 계정을 관리 API 도구의 환경변수로 넘겨 명령을 실행한다.

주소·계정·비밀번호를 하나도 지정하지 않았을 때만 env 파일의 값으로 채운다. 값은 출력하지 않는다.
"""

import argparse
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[3]
# 관리 API 도구가 읽는 환경변수와 Keycloak env 키의 대응.
SOURCES = {'KEYCLOAK_ADMIN_URL': 'keycloak-public-url', 'KEYCLOAK_ADMIN_USERNAME': 'bootstrap-admin-username',
           'KEYCLOAK_ADMIN_PASSWORD': 'bootstrap-admin-password'}


def admin_environment(env_file, current):
    """관리자 접속 변수가 하나도 없을 때만 env 파일의 값으로 모두 채운다.

    주소·계정·비밀번호 중 하나라도 직접 지정했거나 client secret 인증을 쓰면 아무것도 채우지 않는다.
    일부만 채우면 직접 지정한 주소로 운영 계정을 보내거나 운영 주소에 다른 계정을 쓰게 된다.
    """
    result = dict(current)
    if any(result.get(name) for name in (*SOURCES, 'KEYCLOAK_ADMIN_CLIENT_SECRET')):
        return result
    values = {}
    for line in Path(env_file).read_text().splitlines():
        if line.strip() and not line.lstrip().startswith('#'):
            key, _, value = line.partition('=')
            values[key.strip()] = value.strip()
    for name, key in SOURCES.items():
        if not values.get(key):
            raise ValueError(f'Keycloak env에 {key}가 필요합니다: {env_file}')
        result[name] = values[key]
    result.setdefault('KEYCLOAK_ADMIN_REALM', 'master')
    # 사내 CA 묶음이 준비돼 있으면 도구별 CA 변수에 같은 파일을 전달한다.
    bundle = ROOT / 'deploy/shared/certs' / (urlsplit(result['KEYCLOAK_ADMIN_URL']).hostname or '') / 'keycloak-ca-bundle.pem'
    if bundle.is_file():
        for name in ('KEYCLOAK_CA_FILE', 'KEYCLOAK_ADMIN_CA_BUNDLE'):
            result.setdefault(name, str(bundle))
    return result


def main():
    """`admin_env.py --env <파일> -- <명령...>` 형식으로 실행한다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env', type=Path, default=ROOT / 'deploy/keycloak/env/prod.env')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command:
        parser.error('실행할 명령을 지정하세요.')
    try:
        environment = admin_environment(args.env, os.environ)
    except (OSError, ValueError) as error:
        print(f'오류: {error}', file=sys.stderr)
        return 1
    os.execvpe(command[0], command, environment)


if __name__ == '__main__':
    sys.exit(main())
