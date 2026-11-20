"""앱 카탈로그(`deploy/shared/apps.json`)를 읽고 앱별 입력·명령·공개 host를 한 가지 방식으로 정한다.

배포·검사·렌더·기록·대조·진단·보고가 모두 이 모듈로 입력을 정하므로, 같은 환경변수를 주면 같은 파일을 쓴다.
앱을 추가할 때는 카탈로그 항목과 그 앱 폴더만 고친다. 이 모듈과 공용 스크립트는 앱 이름으로 분기하지 않는다.
"""

import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[3]
CATALOG = ROOT / 'deploy/shared/apps.json'
ACTIONS = ('check', 'up', 'render')
PLACEHOLDER = re.compile(r'\{([A-Za-z_][A-Za-z_0-9]*)\}')
BUILTIN = ('context', 'out')


def read_catalog(path=CATALOG):
    """카탈로그를 읽고 구조를 검사한다. 잘못된 항목은 앱 이름과 함께 ValueError로 알린다."""
    catalog = json.loads(Path(path).read_text())
    apps, groups = catalog['apps'], catalog['groups']
    for name, app in apps.items():
        if not name.replace('-', '').isalnum() or not name.islower():
            raise ValueError(f'잘못된 앱 이름: {name}')
        runtime = app.get('runtime')
        if runtime is not None and not (isinstance(runtime, dict) and runtime.get('namespace')):
            raise ValueError(f'apps.json의 {name}.runtime은 namespace를 가진 객체이거나 null(워크로드 없음)이어야 합니다.')
        unknown = [item for item in app.get('dependsOn', []) if item not in apps or item == name]
        if unknown or not app.get('steps'):
            raise ValueError(f'apps.json의 {name}에 dependsOn(등록된 다른 앱)·steps가 필요합니다.')
        variables = [item['variable'] for item in app.get('inputs', [])]
        if len(set(variables)) != len(variables) or any(not item.get('default') for item in app.get('inputs', [])):
            raise ValueError(f'apps.json의 {name}.inputs는 서로 다른 variable과 default를 가져야 합니다.')
        known = {*BUILTIN, *variables, *app.get('options', [])}
        commands = app.get('commands', {})
        for action in ('static', 'check', 'up'):
            if not commands.get(action):
                raise ValueError(f'apps.json의 {name}.commands.{action}이 필요합니다.')
        if any(not argv for argv in commands['static']):
            raise ValueError(f'apps.json의 {name}.commands.static에 빈 명령이 있습니다.')
        for action, command in commands.items():
            for argv in (command if action == 'static' else [command]):
                undeclared = sorted({key for part in argv for key in PLACEHOLDER.findall(part)} - known)
                if undeclared:
                    raise ValueError(f'apps.json의 {name}.commands.{action}이 선언하지 않은 변수를 씁니다: {", ".join(undeclared)}')
        if runtime is not None and not commands.get('render'):
            raise ValueError(f'apps.json의 {name}은 워크로드가 있으므로 commands.render가 필요합니다.')
    for name, members in groups.items():
        if name in apps or not members or len(set(members)) != len(members) or any(member not in apps for member in members):
            raise ValueError(f'잘못된 앱 그룹: {name}')
    if set(groups.get('all', [])) != set(apps):
        raise ValueError('all 그룹은 모든 앱을 포함해야 합니다.')
    return catalog


def resolve_apps(catalog, target):
    """앱 이름 또는 그룹 이름을 앱 목록으로 해석한다."""
    if target in catalog['apps']:
        return [target]
    if target in catalog['groups']:
        return list(catalog['groups'][target])
    raise ValueError(f'지원하지 않는 앱·그룹: {target}')


def inputs(app, environ=None):
    """입력 변수 이름 → 실제 파일 경로. 환경변수가 있으면 그 값을, 없으면 저장소의 기본 파일을 쓴다."""
    environ = os.environ if environ is None else environ
    return {item['variable']: environ.get(item['variable']) or str(ROOT / item['default']) for item in app.get('inputs', [])}


def primary_env(app, environ=None):
    """첫 번째 입력이 앱의 기본 env 파일이다. 입력이 없는 앱은 None."""
    declared = app.get('inputs', [])
    return inputs(app, environ)[declared[0]['variable']] if declared else None


def record_inputs(app, environ=None):
    """배포 기록에 SHA-256을 남길 입력. Secret이 없을 때만 쓰는 초기 계정 파일(`record: false`)은 제외한다."""
    resolved = inputs(app, environ)
    return [resolved[item['variable']] for item in app.get('inputs', []) if item.get('record', True)]


def variables(app, context, out=None, environ=None):
    """명령 인자의 `{이름}`을 채울 값. 선택 변수(options)는 지정하지 않으면 빈 문자열이다."""
    environ = os.environ if environ is None else environ
    values = {'context': context or '', 'out': str(out) if out is not None else ''}
    values.update(inputs(app, environ))
    values.update({name: environ.get(name, '') for name in app.get('options', [])})
    return values


def command(app, action, context, out=None, environ=None):
    """카탈로그의 인자 목록에 값을 채운 실행 명령. 값은 인자로만 전달하고 셸을 거치지 않는다."""
    template = app.get('commands', {}).get(action)
    if not template:
        raise ValueError(f'{action} 명령이 정의되지 않은 앱입니다.')
    values = variables(app, context, out, environ)
    return [PLACEHOLDER.sub(lambda match: values[match[1]], part) for part in template]


def static_commands(app):
    """클러스터·실제 입력 없이 저장소 원본만 검사하는 명령 목록."""
    return [list(argv) for argv in app['commands']['static']]


def child_environment(app, context, environ=None):
    """하위 명령에 넘길 환경. 입력 변수와 KUBE_CONTEXT를 채워, 환경변수로 입력을 받는 도구도 같은 값을 쓴다."""
    environ = dict(os.environ if environ is None else environ)
    environ.update(inputs(app, environ))
    if context:
        environ['KUBE_CONTEXT'] = context
    return environ


def env_value(path, key):
    """env 파일에서 비밀값이 아닌 설정 하나만 읽는다. 파일이 없으면 None."""
    try:
        for line in Path(path).read_text().splitlines():
            name, separator, value = line.partition('=')
            if separator and name.strip() == key:
                return value.strip().strip('"\'')
    except OSError:
        pass
    return None


def namespace(app, environ=None):
    """앱 namespace. 기본 env가 NAMESPACE를 정하면 그 값을, 아니면 카탈로그 값을 쓴다. 워크로드 없는 앱은 None."""
    if app.get('runtime') is None:
        return None
    env = primary_env(app, environ)
    return (env_value(env, 'NAMESPACE') if env else None) or app['runtime']['namespace']


def hosts(app, environ=None):
    """앱이 공용 Traefik으로 공개하는 host 목록. 카탈로그 `hosts`는 기본 env의 키 이름이며 값은 host 또는 URL이다."""
    env = primary_env(app, environ)
    found = []
    for key in app.get('hosts', []):
        value = env_value(env, key) if env else None
        if not value:
            continue
        host = urlsplit(value).hostname if '://' in value else value.split('/')[0].split(':')[0]
        if host and host not in found:
            found.append(host)
    return found
