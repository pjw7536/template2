"""선택 checkout에서 앱과 무관하게 사용하는 배포 모듈·렌더 도구."""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def module(name, path):
    """선택 checkout에 포함된 배포 모듈을 명시적인 경로에서 읽는다."""
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
