"""Grafana SSO의 Keycloak client와 조직을 준비합니다."""

from base64 import b64decode, b64encode
import hashlib
import json
import os
from pathlib import Path
import re
from select import select
import subprocess
import sys
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit
from urllib.request import Request, build_opener

DEPLOY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(DEPLOY / 'keycloak/scripts'))
sys.path.insert(0, str(DEPLOY / 'shared/scripts'))
from admin_env import admin_environment  # noqa: E402
from access_apply import Apply as AccessApply, load_catalog  # noqa: E402
from catalog import env_value  # noqa: E402
from init_sdwt import Admin, NoRedirect, SetupError, mapper_equal, one, segment, user_mapper  # noqa: E402

CLIENT_ID = 'grafana'
OIDC_SECRET = 'monitoring-grafana-oidc'
OIDC_REVISION = 'etch/grafana-sso-revision'
OPERATIONS_GROUP = 'grafana-operations-viewers'
BUSINESS_GROUP = 'grafana-business-viewers'
BUSINESS_ORG = 'Etch-Business'
GROUPS = (OPERATIONS_GROUP, BUSINESS_GROUP)


class GrafanaAdminAuthError(ValueError):
    """Grafana 서버 관리자 인증에 실패했습니다."""


def issuer(keycloak_env, realm):
    origin = (env_value(keycloak_env, 'keycloak-public-url') or '').rstrip('/')
    address = urlsplit(origin)
    if (not address.hostname or address.scheme != 'https' or address.path or address.query or address.fragment
            or address.username is not None):
        raise ValueError('KEYCLOAK_ENV의 keycloak-public-url에는 HTTPS origin이 필요합니다.')
    return f'{origin}/realms/{realm}'


def oauth_config(issuer_url):
    oidc = issuer_url + '/protocol/openid-connect'
    return {
        'enabled': True, 'name': 'Etch SSO', 'allow_sign_up': True, 'client_id': CLIENT_ID,
        'scopes': 'openid profile email', 'auth_url': oidc + '/auth', 'token_url': oidc + '/token',
        'api_url': oidc + '/userinfo', 'jwk_set_url': oidc + '/certs', 'validate_id_token': True,
        'use_pkce': True, 'use_refresh_token': True, 'allow_assign_grafana_admin': False,
        'login_attribute_path': 'preferred_username',
        'name_attribute_path': "((display_name && loginid) && join('', [display_name, '(', loginid, ')'])) || display_name || loginid",
        'allowed_groups': ' '.join(f'/{group}' for group in GROUPS),
        'groups_attribute_path': 'groups',
        'org_attribute_path': 'groups',
        'org_mapping': f'/{OPERATIONS_GROUP}:1:Viewer /{BUSINESS_GROUP}:{BUSINESS_ORG}:Viewer',
        'role_attribute_strict': True, 'skip_org_role_sync': False,
    }


def reconcile_keycloak(api, origin):
    """기존 client secret과 그룹 멤버십을 보존하며 관리 대상 설정을 반영합니다."""
    definition = {
        'clientId': CLIENT_ID, 'name': 'Grafana', 'protocol': 'openid-connect',
        'enabled': True, 'publicClient': False, 'clientAuthenticatorType': 'client-secret',
        'standardFlowEnabled': True, 'implicitFlowEnabled': False, 'directAccessGrantsEnabled': False,
        'serviceAccountsEnabled': False, 'fullScopeAllowed': False, 'redirectUris': [origin + '/login/generic_oauth'],
        'rootUrl': origin, 'webOrigins': [], 'attributes': {'pkce.code.challenge.method': 'S256'},
    }

    def find_client():
        return one(api.call('GET', 'clients', query={'clientId': CLIENT_ID}), 'clientId', CLIENT_ID)

    current = find_client()
    if current is None:
        api.call('POST', 'clients', definition)
        current = find_client()
    client = f"clients/{segment(current['id'])}"
    current = api.call('GET', client)
    attributes = {**(current.get('attributes') or {}), **definition['attributes']}
    desired = {**definition, 'attributes': attributes}
    if any(current.get(key) != value for key, value in desired.items()):
        api.call('PUT', client, {**current, **desired})

    scopes = {scope['name']: scope['id'] for scope in api.call('GET', 'client-scopes')}
    assigned = {scope['name'] for scope in api.call('GET', client + '/default-client-scopes')}
    for name in sorted({'profile', 'email', 'basic'} - assigned):
        api.call('PUT', f"{client}/default-client-scopes/{segment(scopes[name])}")

    path = client + '/protocol-mappers/models'
    existing = api.call('GET', path)
    groups_mapper = {'name': 'grafana-groups', 'protocol': 'openid-connect',
                     'protocolMapper': 'oidc-group-membership-mapper', 'consentRequired': False,
                     'config': {'claim.name': 'groups', 'full.path': 'true', 'id.token.claim': 'true',
                                'access.token.claim': 'true', 'userinfo.token.claim': 'true'}}
    for mapper in (groups_mapper, user_mapper('display_name'), user_mapper('loginid')):
        old = one(existing, 'name', mapper['name'])
        if old is None:
            api.call('POST', path, mapper)
        elif not mapper_equal(old, mapper):
            api.call('PUT', f"{path}/{segment(old['id'])}", {**old, **mapper})
    for name in GROUPS:
        groups = api.pages('groups', search=name, exact='true', populateHierarchy='false')
        if one(groups, 'path', f'/{name}') is None:
            api.call('POST', 'groups', {'name': name})

    credential = api.call('GET', client + '/client-secret')
    if not isinstance(credential, dict) or not credential.get('value'):
        raise ValueError('Grafana OIDC client secret을 읽을 수 없습니다.')
    return credential['value']


def ensure_oidc(run, kube, namespace, settings, keycloak_env):
    os.environ.update(admin_environment(keycloak_env, os.environ))
    try:
        api = Admin(settings.get('GRAFANA_OIDC_REALM', 'etch'))
        secret = reconcile_keycloak(api, f"https://{settings['GRAFANA_HOST']}")
    except SetupError as error:
        raise ValueError(str(error)) from None
    scoped = [*kube, '-n', namespace]
    current = run([*scoped, 'get', 'secret', OIDC_SECRET, '--ignore-not-found', '-o', 'json'])
    encoded = b64encode(secret.encode()).decode()
    revision = hashlib.sha256(secret.encode()).hexdigest()
    if current and json.loads(current).get('data', {}).get('client-secret') == encoded:
        return api, revision
    run([*scoped, 'apply', '--server-side', '--field-manager=monitoring-oidc', '-f', '-'],
        data=json.dumps({'apiVersion': 'v1', 'kind': 'Secret', 'type': 'Opaque',
                         'metadata': {'name': OIDC_SECRET, 'namespace': namespace},
                         'data': {'client-secret': encoded}}))
    return api, revision


def publish_members_catalog(api):
    """기존 Members의 카탈로그를 갱신합니다. 최초 IAM 설치도 같은 원본을 읽습니다."""
    if not api.call('GET', 'groups', query={'search': 'iam', 'exact': 'true'}):
        return
    access = AccessApply(api, load_catalog(DEPLOY / 'keycloak/access/catalog.json'))
    access.inspect()
    access.apply_catalog()


def ensure_business_org(url, account):
    """업무 조직을 이름으로 조회하고 없는 경우에만 생성합니다."""
    auth = b64encode(f"{account['admin-user']}:{account['admin-password']}".encode()).decode()
    opener = build_opener(NoRedirect())

    def request(path, data=None):
        req = Request(url + path, data=json.dumps(data).encode() if data else None,
                      headers={'Authorization': 'Basic ' + auth, 'Content-Type': 'application/json'})
        try:
            with opener.open(req, timeout=15) as response:
                return json.load(response)
        except HTTPError as error:
            if error.code == 404 and data is None:
                return None
            if error.code == 409 and data:
                return None
            if error.code in (401, 403):
                raise GrafanaAdminAuthError('Grafana 현재 서버 관리자 계정이 필요합니다. MONITORING_GRAFANA_ENV를 확인하세요.') from None
            raise ValueError(f'Grafana 조직 관리 API 응답 오류 (HTTP {error.code})') from None

    path = '/api/orgs/name/' + quote(BUSINESS_ORG, safe='')
    org = request(path)
    if org is None:
        request('/api/orgs', {'name': BUSINESS_ORG})
        org = request(path)
    if not org or org.get('id', 0) <= 1:
        raise ValueError('Grafana 업무 조직은 운영 조직(ID 1)과 다른 조직이어야 합니다.')
    return org['id']


def prepare_business_org(run, kube, namespace, name, admin_secret, account_file, read_account):
    """관리 호스트의 loopback으로 연결해 조직을 준비합니다."""
    scoped = [*kube, '-n', namespace]
    credentials = json.loads(run([*scoped, 'get', 'secret', admin_secret, '-o', 'json']))['data']
    account = {key: b64decode(credentials[key]).decode() for key in ('admin-user', 'admin-password')}
    command = [*scoped, 'port-forward', '--address=127.0.0.1', f'service/{name}', ':80']
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) as process:
        try:
            ready, _, _ = select([process.stdout], [], [], 15)
            line = process.stdout.readline() if ready else ''
            match = re.match(r'Forwarding from 127\.0\.0\.1:(\d+) -> \d+', line)
            if not match:
                raise ValueError('Grafana 조직 등록용 Kubernetes 포트 포워딩을 열 수 없습니다.')
            url = f'http://127.0.0.1:{match[1]}'
            try:
                return ensure_business_org(url, account)
            except GrafanaAdminAuthError:
                # Grafana DB의 비밀번호가 바뀐 경우 현재 관리 계정 파일로 다시 시도합니다.
                if not account_file or not Path(account_file).is_file():
                    raise
                return ensure_business_org(url, read_account(account_file))
        finally:
            process.terminate()
