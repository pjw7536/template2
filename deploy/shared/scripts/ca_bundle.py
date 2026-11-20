#!/usr/bin/env python3
"""`deploy/shared/certs/ca`의 사내 CA 인증서로 OIDC·HTTPS 검증용 PEM 묶음을 만든다. 외부 도구 없이 PEM·DER을 모두 읽는다."""

import argparse
from pathlib import Path
import ssl
import sys

ROOT = Path(__file__).resolve().parents[3]
CA_DIR = ROOT / 'deploy/shared/certs/ca'
PEM_HEADER = b'-----BEGIN CERTIFICATE-----'


def bundle_text(directory=CA_DIR):
    """폴더의 `.crt`·`.pem` 인증서를 이름순으로 이어 붙인 PEM을 반환한다. 파일이 없으면 빈 문자열이다."""
    parts = []
    for path in sorted(Path(directory).glob('*')):
        if path.suffix not in ('.crt', '.pem', '.cer') or not path.is_file():
            continue
        raw = path.read_bytes()
        text = raw.decode() if PEM_HEADER in raw else ssl.DER_cert_to_PEM_cert(raw)
        parts.append(text.strip() + '\n')
    return ''.join(parts)


def bundle_path(host):
    """host의 CA 묶음 기본 경로."""
    return ROOT / 'deploy/shared/certs' / host / 'keycloak-ca-bundle.pem'


def ensure(host, directory=CA_DIR):
    """묶음 파일이 있으면 그대로 쓰고, 없으면 CA 폴더로 만든다. 만들 수 없으면 None을 반환한다."""
    target = bundle_path(host)
    if target.is_file():
        return target
    text = bundle_text(directory)
    if not text:
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)
    return target


def rebuild(host, directory=CA_DIR):
    """CA 폴더의 현재 파일로 묶음을 다시 쓴다. CA를 교체한 뒤 쓴다. 폴더가 비어 있으면 기존 묶음을 그대로 둔다."""
    text = bundle_text(directory)
    target = bundle_path(host)
    if not text:
        return target if target.is_file() else None
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)
    return target


def main():
    """`ca_bundle.py <host>`로 묶음을 CA 폴더의 현재 내용으로 다시 만들고 경로를 출력한다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('host')
    args = parser.parse_args()
    target = rebuild(args.host)
    if target is None:
        print(f'CA 인증서가 없습니다. {CA_DIR.relative_to(ROOT)}에 사내 Root·Issuing CA 파일을 두세요.', file=sys.stderr)
        return 1
    print(f'CA 묶음 준비 완료: {target.relative_to(ROOT)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
