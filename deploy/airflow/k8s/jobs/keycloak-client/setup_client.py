#!/usr/bin/env python3
"""기존 realm에 Airflow 전용 client·역할·mapper를 멱등 등록한다.

관리자 입력은 환경변수로만 받고 서버 env의 client secret은 출력하지 않는다.
"""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import ssl
from urllib.error import HTTPError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen


class KeycloakAdmin:
    """관리자 API 요청에서 비밀값·응답 본문이 오류 출력에 섞이지 않게 한다."""

    def __init__(self, base_url, realm, username, password, ca_bundle=None):
        self.base = base_url.rstrip('/')
        parsed = urlsplit(self.base)
        if parsed.scheme != 'https' and not (parsed.scheme == 'http' and parsed.hostname in ('localhost', '127.0.0.1')):
            raise ValueError('관리자 API는 HTTPS 또는 로컬 port-forward 주소를 사용하세요.')
        self.context = ssl.create_default_context(cafile=ca_bundle or None)
        self.token = None
        body = urlencode({'grant_type': 'password', 'client_id': 'admin-cli',
                          'username': username, 'password': password}).encode()
        self.token = self.request('POST', '/realms/master/protocol/openid-connect/token', body=body,
                                  content_type='application/x-www-form-urlencoded')['access_token']
        self.root = '/admin/realms/' + quote(realm, safe='')

    def request(self, method, path, payload=None, body=None, content_type='application/json'):
        """응답 내용은 호출자에게만 반환하고 오류에는 HTTP 상태만 남긴다."""
        headers = {'Content-Type': content_type}
        if self.token:
            headers['Authorization'] = 'Bearer ' + self.token
        if payload is not None:
            body = json.dumps(payload).encode()
        try:
            with urlopen(Request(self.base + path, data=body, headers=headers, method=method),
                         timeout=20, context=self.context) as response:
                data = response.read()
                return json.loads(data) if data else None
        except HTTPError as error:
            raise ValueError(f'Keycloak 관리자 API 실패: HTTP {error.code}') from None


def client_definition(settings):
    """웹 전용 client와 검증할 ID Token의 전용 역할 claim을 구성한다."""
    client_id = settings['AIRFLOW_OIDC_CLIENT_ID']
    return {
        'clientId': client_id, 'name': 'Airflow', 'protocol': 'openid-connect', 'enabled': True,
        'publicClient': False, 'clientAuthenticatorType': 'client-secret',
        'standardFlowEnabled': True, 'implicitFlowEnabled': False, 'directAccessGrantsEnabled': False,
        'serviceAccountsEnabled': False, 'fullScopeAllowed': False,
        'redirectUris': [settings['AIRFLOW_WEBSERVER_BASE_URL'].rstrip('/') + '/oauth-authorized/keycloak'],
        'webOrigins': [], 'defaultClientScopes': ['profile', 'email'], 'optionalClientScopes': [],
        'attributes': {'pkce.code.challenge.method': 'S256', 'id.token.signed.response.alg': 'RS256'},
    }


def configure(admin, settings):
    """기존 secret·사용자 역할은 보존하며 Airflow client의 소유 설정만 갱신한다."""
    definition = client_definition(settings)
    found = admin.request('GET', admin.root + '/clients?' + urlencode({'clientId': definition['clientId']}))
    found = [item for item in found if item['clientId'] == definition['clientId']]
    if len(found) > 1:
        raise ValueError('같은 client ID가 여러 개입니다.')
    if not found:
        admin.request('POST', admin.root + '/clients', {**definition, 'secret': settings['AIRFLOW_OIDC_CLIENT_SECRET']})
        found = admin.request('GET', admin.root + '/clients?' + urlencode({'clientId': definition['clientId']}))
    current = found[0]
    path = admin.root + '/clients/' + current['id']
    stored = admin.request('GET', path + '/client-secret')['value']
    if stored != settings['AIRFLOW_OIDC_CLIENT_SECRET']:
        raise ValueError('기존 Airflow client secret과 env가 다릅니다. 기존 secret을 env에 복원하세요.')
    definition['attributes'] = {**current.get('attributes', {}), **definition['attributes']}
    # 목록 응답에 가려진 secret이 포함되어도 기존 비밀값을 덮어쓰지 않는다.
    update = {key: value for key, value in current.items() if key != 'secret'}
    admin.request('PUT', path, {**update, **definition})
    roles = {item['name']: item for item in admin.request('GET', path + '/roles')}
    for name in ('Viewer', 'User', 'Admin'):
        if name not in roles:
            admin.request('POST', path + '/roles', {'name': name})
    roles = {item['name']: item for item in admin.request('GET', path + '/roles')}
    admin.request('POST', path + '/scope-mappings/clients/' + current['id'],
                  [roles[name] for name in ('Viewer', 'User', 'Admin')])
    mapper = {'name': 'airflow-client-roles', 'protocol': 'openid-connect',
              'protocolMapper': 'oidc-usermodel-client-role-mapper',
              'config': {'usermodel.clientRoleMapping.clientId': definition['clientId'],
                         'claim.name': 'resource_access.' + definition['clientId'] + '.roles',
                         'jsonType.label': 'String', 'multivalued': 'true',
                         'id.token.claim': 'true', 'access.token.claim': 'true', 'userinfo.token.claim': 'false'}}
    existing = admin.request('GET', path + '/protocol-mappers/models')
    own = next((item for item in existing if item['name'] == mapper['name']), None)
    if own:
        admin.request('PUT', path + '/protocol-mappers/models/' + own['id'], {**mapper, 'id': own['id']})
    else:
        admin.request('POST', path + '/protocol-mappers/models', mapper)
    return current['id'], roles


def main():
    """운영자는 대상 env와 관리자 URL을 명시하며 사용자 역할은 별도로 부여한다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env', required=True, type=Path)
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[3] / 'scripts/manage.py'
    spec = importlib.util.spec_from_file_location('airflow_deploy', source)
    deploy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(deploy)
    settings = deploy.read_env(args.env)
    deploy.validate(settings)
    if settings['AIRFLOW_AUTH_MODE'] != 'keycloak':
        raise ValueError('client 등록에는 AIRFLOW_AUTH_MODE=keycloak이 필요합니다.')
    realm = urlsplit(settings['AIRFLOW_OIDC_ISSUER']).path.rstrip('/').split('/')[-1]
    admin = KeycloakAdmin(os.environ['KEYCLOAK_ADMIN_URL'], realm,
                          os.environ['KEYCLOAK_ADMIN_USERNAME'], os.environ['KEYCLOAK_ADMIN_PASSWORD'],
                          os.environ.get('KEYCLOAK_ADMIN_CA_BUNDLE'))
    configure(admin, settings)
    print('Airflow client·역할·mapper 등록 완료. 기존 secret과 사용자 역할은 보존했습니다.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError):
        raise SystemExit('Airflow client 등록 실패. 관리자 접속·입력·기존 client secret 일치를 확인하세요.')
