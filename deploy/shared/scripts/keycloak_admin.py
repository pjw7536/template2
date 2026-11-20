"""Keycloak 관리 REST API를 표준 라이브러리로 호출하는 최소 client. 접속 정보는 환경변수로 받는다."""

import json
import os
import ssl
from urllib.error import HTTPError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPSHandler, Request, build_opener


class AdminError(ValueError):
    """값을 포함하지 않는 관리 API 오류."""


class Admin:
    """관리자 토큰을 받아 대상 realm의 관리 API를 호출한다."""

    def __init__(self, url, username, password, realm, admin_realm='master', ca_file=None, opener=None):
        self.url, self.realm = url.rstrip('/'), realm
        if urlsplit(self.url).scheme != 'https':
            raise AdminError('KEYCLOAK_ADMIN_URL에는 HTTPS 주소를 지정하세요.')
        self.opener = opener or build_opener(HTTPSHandler(context=ssl.create_default_context(cafile=ca_file or None)))
        token = self._send('POST', f'/realms/{quote(admin_realm, safe="")}/protocol/openid-connect/token',
                           form={'grant_type': 'password', 'client_id': 'admin-cli', 'username': username, 'password': password})
        if not isinstance(token, dict) or not token.get('access_token'):
            raise AdminError('관리자 토큰을 발급받지 못했습니다.')
        self.token = token['access_token']

    @classmethod
    def from_environment(cls, realm, environment=os.environ):
        """KEYCLOAK_ADMIN_URL·USERNAME·PASSWORD와 선택 REALM·CA 변수로 접속한다."""
        missing = [name for name in ('KEYCLOAK_ADMIN_URL', 'KEYCLOAK_ADMIN_USERNAME', 'KEYCLOAK_ADMIN_PASSWORD') if not environment.get(name)]
        if missing:
            raise AdminError('관리자 접속 환경변수가 필요합니다: ' + ', '.join(missing))
        return cls(environment['KEYCLOAK_ADMIN_URL'], environment['KEYCLOAK_ADMIN_USERNAME'],
                   environment['KEYCLOAK_ADMIN_PASSWORD'], realm, environment.get('KEYCLOAK_ADMIN_REALM', 'master'),
                   environment.get('KEYCLOAK_CA_FILE') or environment.get('KEYCLOAK_ADMIN_CA_BUNDLE'))

    def _send(self, method, path, data=None, form=None):
        headers = {'Accept': 'application/json'}
        body = None
        if form is not None:
            body, headers['Content-Type'] = urlencode(form).encode(), 'application/x-www-form-urlencoded'
        elif data is not None:
            body, headers['Content-Type'] = json.dumps(data).encode(), 'application/json'
        if getattr(self, 'token', None):
            headers['Authorization'] = 'Bearer ' + self.token
        try:
            with self.opener.open(Request(self.url + path, data=body, headers=headers, method=method), timeout=30) as response:
                raw = response.read()
        except HTTPError as error:
            raise AdminError(f'Keycloak {method} 요청 실패 (HTTP {error.code}). 관리자 권한과 입력을 확인하세요.') from None
        except OSError:
            raise AdminError('Keycloak 연결 실패. 주소·DNS·CA 묶음을 확인하세요.') from None
        return json.loads(raw) if raw else None

    def call(self, method, path, data=None, query=None):
        """대상 realm 안의 관리 API를 호출한다."""
        url = f'/admin/realms/{quote(self.realm, safe="")}/{path}'
        return self._send(method, url + ('?' + urlencode(query) if query else ''), data)
