"""사내 이미지 저장소로 이미지를 빌드·push하는 공통 도우미. nerdctl과 BuildKit을 사용한다."""

import hashlib
import os
from pathlib import Path
import re
import shutil
import ssl
import subprocess
from urllib.error import HTTPError
from urllib.request import HTTPSHandler, Request, build_opener

DEFAULT_ADDRESS = '/run/containerd/containerd.sock'
DEFAULT_BUILDKIT_HOST = 'unix:///run/buildkit/buildkitd.sock'
MANIFEST_TYPES = ', '.join(('application/vnd.oci.image.index.v1+json', 'application/vnd.oci.image.manifest.v1+json',
                            'application/vnd.docker.distribution.manifest.list.v2+json',
                            'application/vnd.docker.distribution.manifest.v2+json'))


def privilege(address=DEFAULT_ADDRESS):
    """containerd 소켓에 쓸 수 없는 계정은 비밀번호를 묻지 않는 sudo로 실행한다."""
    return [] if os.geteuid() == 0 or os.access(address, os.W_OK) else ['sudo', '-n']


def nerdctl(address=DEFAULT_ADDRESS, namespace='default'):
    """빌드·push가 같은 containerd namespace를 쓰도록 공통 인자를 붙인 명령을 만든다."""
    if not shutil.which('nerdctl') or not shutil.which('buildctl'):
        raise ValueError('이미지 빌드 도구(nerdctl·buildctl)가 없습니다. make build-tools-install을 실행하세요.')
    return [*privilege(address), 'nerdctl', '--address', address, '--namespace', namespace]


def split(reference):
    """`host/name:tag`를 (host, name, tag)로 나눈다. registry 주소가 없으면 host는 빈 문자열이다."""
    name, separator, tag = reference.rpartition(':')
    if not separator or '/' in tag:
        raise ValueError(f'tag가 있는 이미지 이름이 필요합니다: {reference}')
    host, slash, rest = name.partition('/')
    if slash and ('.' in host or ':' in host or host == 'localhost'):
        return host, rest, tag
    return '', name, tag


def remote_exists(reference, cadata=None, opener=None):
    """registry에 같은 tag가 있는지 익명 조회한다. 같은 tag를 다시 push하지 않기 위한 확인이다."""
    host, name, tag = split(reference)
    if not host:
        return False
    context = ssl.create_default_context()
    if cadata:
        context.load_verify_locations(cadata=cadata)
    opener = opener or build_opener(HTTPSHandler(context=context))
    request = Request(f'https://{host}/v2/{name}/manifests/{tag}', method='HEAD', headers={'Accept': MANIFEST_TYPES})
    try:
        with opener.open(request, timeout=20):
            return True
    except HTTPError as error:
        if error.code == 404:
            return False
        raise ValueError(f'registry 조회 실패(HTTP {error.code}): {host}') from None
    except OSError:
        raise ValueError(f'registry에 연결할 수 없습니다: {host}. DNS·APP VIP·사내 CA 신뢰를 확인하세요.') from None


def read_account(path, is_placeholder=None):
    """push 계정 파일에서 REGISTRY_USER·REGISTRY_PASSWORD만 읽는다. 다른 키·중복·공백·자리표시자는 거부한다."""
    values = {}
    for line in Path(path).read_text().splitlines():
        if line.strip() and not line.lstrip().startswith('#'):
            key, separator, value = line.partition('=')
            if not separator or key not in ('REGISTRY_USER', 'REGISTRY_PASSWORD') or key in values:
                raise ValueError('push 계정 파일에는 REGISTRY_USER와 REGISTRY_PASSWORD를 각각 한 번만 기록하세요.')
            values[key] = value
    user, password = values.get('REGISTRY_USER', ''), values.get('REGISTRY_PASSWORD', '')
    if (not re.fullmatch(r'[A-Za-z0-9._-]+', user) or not password or any(c.isspace() for c in password)
            or (is_placeholder and is_placeholder(password))):
        raise ValueError(f'push 계정 파일의 REGISTRY_USER·REGISTRY_PASSWORD를 확인하세요: {path}')
    return user, password


def push(run, command, reference, account_file):
    """push 계정으로 로그인한 뒤 이미지를 올린다. 비밀번호는 표준 입력으로만 전달한다."""
    host, _, _ = split(reference)
    if not host:
        raise ValueError(f'registry 주소가 없는 이미지는 push할 수 없습니다: {reference}')
    user, password = read_account(account_file)
    run([*command, 'login', '--username', user, '--password-stdin', host], data=password + '\n')
    run([*command, 'push', reference])


def build(run, command, reference, context, dockerfile=None, build_args=None, buildkit_host=DEFAULT_BUILDKIT_HOST, pull=True):
    """한 이미지를 빌드한다. build_args는 Dockerfile이 선언한 ARG만 전달한다."""
    args = [*command, 'build', '--buildkit-host', buildkit_host, '-t', reference]
    if not pull:
        args.append('--pull=false')
    if dockerfile:
        args += ['-f', dockerfile]
    for key, value in sorted((build_args or {}).items()):
        args += ['--build-arg', f'{key}={value}']
    run([*args, context])


def declared_args(dockerfile):
    """Dockerfile의 ARG 이름 집합."""
    return set(re.findall(r'^ARG\s+([A-Za-z_][A-Za-z0-9_]*)', Path(dockerfile).read_text(), re.M))


def source_tag(root, trees, files=(), exclude=()):
    """커밋된 소스 tree와 빌드 입력 파일 내용으로 12자리 tag를 만든다. 소스가 같으면 항상 같은 값이다.

    trees는 저장소 루트 기준 디렉터리, exclude는 각 tree 바로 아래에서 제외할 이름이다.
    """
    digest = hashlib.sha256()
    for tree in trees:
        result = subprocess.run(['git', '-C', str(root), 'ls-tree', 'HEAD', f'{tree}/'], capture_output=True, text=True)
        lines = sorted(line for line in result.stdout.splitlines() if line.rsplit('/', 1)[-1] not in exclude)
        if result.returncode or not lines:
            raise ValueError(f'이미지 tag를 정할 소스가 Git에 없습니다: {tree}. 저장소 전체 checkout에서 실행하거나 tag를 직접 지정하세요.')
        digest.update('\n'.join(lines).encode())
        # 작업 트리로 빌드하므로 커밋되지 않은 변경은 내용까지 tag에 반영해 깨끗한 commit의 tag와 겹치지 않게 한다.
        scope = ['--', tree, *(f':(exclude){tree}/{name}' for name in exclude)]
        digest.update(subprocess.run(['git', '-C', str(root), 'diff', 'HEAD', *scope], capture_output=True).stdout)
        # -z 출력은 한글·공백이 든 경로도 인용하지 않는다.
        untracked = subprocess.run(['git', '-C', str(root), 'ls-files', '--others', '--exclude-standard', '-z', *scope],
                                   capture_output=True).stdout.split(b'\0')
        for name in sorted(filter(None, untracked)):
            target = Path(root) / name.decode('utf-8', 'surrogateescape')
            if target.is_file():
                digest.update(name)
                digest.update(target.read_bytes())
    for path in files:
        digest.update(Path(path).read_bytes())
    return digest.hexdigest()[:12]
