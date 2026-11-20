#!/usr/bin/env python3
"""Portal API·Web 이미지를 빌드해 사내 이미지 저장소에 올린다. registry에 같은 tag가 있으면 건너뛴다.

이미지 이름과 tag는 운영 overlay의 렌더 결과를 그대로 쓴다. 배포가 받을 이미지와 항상 같다.
"""

import argparse
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('portal_up', ROOT / 'deploy/portal/scripts/up.py')
up = importlib.util.module_from_spec(spec)
spec.loader.exec_module(up)
image_registry = up.image_registry
ca_bundle = up.runtime.module('shared_ca_bundle', ROOT / 'deploy/shared/scripts/ca_bundle.py')


def read_build_env(path):
    """빌드 입력을 실행하지 않고 KEY=값으로 읽는다."""
    values = {}
    for line in Path(path).read_text().splitlines():
        if line.strip() and not line.lstrip().startswith('#'):
            key, separator, value = line.partition('=')
            if not separator or key in values:
                raise ValueError(f'build.env 형식 또는 중복 키 오류: {key}')
            values[key] = value
    return values


def publish(context, push_env, address=image_registry.DEFAULT_ADDRESS, buildkit_host=image_registry.DEFAULT_BUILDKIT_HOST):
    """렌더한 API·Web 이미지 중 registry에 없는 것만 빌드해 push한다."""
    if not context.strip():
        raise ValueError('--context를 명시하세요.')
    images = up.rendered_images(['kubectl', '--context', context])
    build_args = read_build_env(up.build_env())
    cadata = ca_bundle.bundle_text() or None
    command = None
    for component in ('api', 'web'):
        reference = images[component, component]
        if not image_registry.split(reference)[0]:
            raise ValueError(f'registry 주소가 없는 이미지입니다: {reference}')
        if image_registry.remote_exists(reference, cadata):
            print(f'registry에 이미 있는 tag라 빌드하지 않았습니다: {reference}')
            continue
        command = command or image_registry.nerdctl(address)
        source = ROOT / up.SOURCES[component]
        declared = image_registry.declared_args(source / 'Dockerfile')
        print(f'이미지 빌드: {reference}', flush=True)
        image_registry.build(up.run, command, reference, source,
                             build_args={key: value for key, value in build_args.items() if key in declared},
                             buildkit_host=buildkit_host)
        image_registry.push(up.run, command, reference, push_env)
        print(f'Portal 이미지 push 완료: {reference}')


def main():
    """대상 context는 overlay 렌더에만 쓰며 클러스터를 변경하지 않는다."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--context', required=True)
    parser.add_argument('--push-env', type=Path, default=ROOT / 'deploy/registry/env/push-initial.env')
    args = parser.parse_args()
    publish(args.context, args.push_env)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError) as error:
        print(f'오류: {error}', file=sys.stderr)
        sys.exit(1)
