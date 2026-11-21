"""Kustomize에서 마운트할 Keycloak 표시용 mapper JAR를 재현합니다."""

import argparse
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile, ZipInfo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    data = BytesIO()
    with ZipFile(data, 'w') as archive:
        for name in ('META-INF/keycloak-scripts.json', 'etch-display-name.js'):
            archive.writestr(ZipInfo(name), (root / Path(name).name).read_bytes())
    jar = root / 'etch-display-name.jar'
    if args.check:
        if not jar.is_file() or jar.read_bytes() != data.getvalue():
            parser.exit(1, 'Keycloak 표시용 mapper 원본과 JAR가 다릅니다. build.py를 실행하세요.\n')
    else:
        jar.write_bytes(data.getvalue())


if __name__ == '__main__':
    main()
