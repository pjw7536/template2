"""앱과 무관하게 사용하는 공통 배포 모듈·렌더 도구."""

import importlib.util
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]


# env-lib.sh의 PLACEHOLDER_MARKERS와 같은 목록을 유지한다(test_placeholders.py가 대조).
PLACEHOLDER_MARKERS = ('replace-me', 'replace-here', 'change-me', 'example.invalid')
# <token>, <입력 필요>처럼 꺾쇠 한 쌍으로 감싼 자리표시자. 짝이 없는 <·> 문자는 허용한다.
PLACEHOLDER_TOKEN = re.compile(r'<[^<>]+>')


def is_placeholder(value):
    """실제 값으로 교체하지 않은 자리표시자가 값 안에 남아 있는지 확인한다."""
    return any(marker in value for marker in PLACEHOLDER_MARKERS) or bool(PLACEHOLDER_TOKEN.search(value))


def module(name, path):
    """배포 모듈을 명시적인 경로에서 읽는다."""
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def render_json(run, kube, path):
    """kubectl의 YAML 해석을 사용해 추가 Python 패키지 없이 JSON으로 변환한다."""
    source = run(['kubectl', 'kustomize', path])
    stream = run([*kube, 'create', '--dry-run=client', '--validate=false', '-f', '-', '-o', 'json'], data=source)
    # kubectl 버전에 따라 여러 JSON 객체를 연속 출력하거나 List로 묶는다.
    items = []
    decoder = json.JSONDecoder()
    while stream.strip():
        stream = stream.lstrip()
        result, consumed = decoder.raw_decode(stream)
        items.extend(result['items'] if result.get('kind') == 'List' else [result])
        stream = stream[consumed:]
    return items
