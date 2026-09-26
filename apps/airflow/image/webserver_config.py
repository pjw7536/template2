"""이미지 공통 FAB 설정. 환경별 URL·비밀값은 Secret에서만 읽는다."""

import os
from pathlib import Path
from flask_appbuilder.security.manager import AUTH_DB, AUTH_OAUTH

AUTH_TYPE = AUTH_DB
AUTH_ROLE_PUBLIC = 'Public'
_mode = os.environ.get('AIRFLOW_AUTH_MODE', 'db')
if _mode not in ('db', 'keycloak'):
    raise ValueError('AIRFLOW_AUTH_MODE 설정 오류')
if _mode == 'keycloak':
    from keycloak_security import KeycloakSecurityManager

    AUTH_TYPE = AUTH_OAUTH
    SECURITY_MANAGER_CLASS = KeycloakSecurityManager
    AUTH_USER_REGISTRATION = True
    AUTH_USER_REGISTRATION_ROLE = 'Viewer'
    AUTH_ROLES_SYNC_AT_LOGIN = True
    AUTH_ROLES_MAPPING = {role: [role] for role in ('Viewer', 'User', 'Admin')}
    _issuer = os.environ['AIRFLOW_OIDC_ISSUER'].rstrip('/')
    _backchannel = (os.environ.get('AIRFLOW_OIDC_BACKCHANNEL_BASE_URL') or _issuer).rstrip('/')
    _ca = os.environ.get('AIRFLOW_OIDC_CA_BUNDLE')
    if _ca and not Path(_ca).is_file():
        raise ValueError('OIDC CA bundle 파일이 없습니다.')
    OAUTH_PROVIDERS = [{
        'name': 'keycloak', 'icon': 'fa-key', 'token_key': 'access_token',
        'remote_app': {
            'client_id': os.environ['AIRFLOW_OIDC_CLIENT_ID'],
            'client_secret': os.environ['AIRFLOW_OIDC_CLIENT_SECRET'],
            'authorize_url': _issuer + '/protocol/openid-connect/auth',
            'access_token_url': _backchannel + '/protocol/openid-connect/token',
            'jwks_uri': _backchannel + '/protocol/openid-connect/certs',
            # discovery의 공개 localhost 주소를 Pod에서 호출하지 않도록 메타데이터를 명시한다.
            'issuer': _issuer,
            'id_token_signing_alg_values_supported': ['RS256'],
            'client_kwargs': {'scope': 'openid profile email', 'code_challenge_method': 'S256',
                              'verify': _ca or True, 'timeout': 10},
        },
    }]
