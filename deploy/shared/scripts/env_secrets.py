"""일반 env에 인접한 Git 제외 비밀값 파일을 데이터로 병합한다."""

from pathlib import Path
import re


def merge_secrets(path, values):
    """실제 .env만 병합하며 알 수 없는 키와 중복 키를 거부한다."""
    path = Path(path)
    secret_path = path.with_suffix('.secrets.env')
    if path.suffix != '.env' or path.name.endswith('.secrets.env') or not secret_path.exists():
        return values
    result = dict(values)
    seen = set()
    for number, line in enumerate(secret_path.read_text().splitlines(), 1):
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        key, separator, value = line.partition('=')
        if not separator or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_-]*', key):
            raise ValueError(f'비밀값 파일 형식 오류: {secret_path}:{number}')
        if key not in values or key in seen:
            raise ValueError(f'알 수 없거나 중복된 비밀값 키: {key}')
        seen.add(key)
        result[key] = value
    return result
