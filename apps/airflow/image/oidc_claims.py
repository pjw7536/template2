"""검증된 Keycloak ID Token을 Airflow 사용자와 내장 역할로 변환한다."""

import hashlib
import json


def display_label(claims):
    """SSO 프로필에서 FAB 이름 필드에 저장할 표시 문자열을 만들고 길이를 제한합니다."""
    display_name = claims.get('display_name')
    login_id = claims.get('loginid')
    name = display_name.strip() if isinstance(display_name, str) else ''
    login = login_id.strip() if isinstance(login_id, str) else ''
    label = f'{name}({login})' if name and login else name or login
    return label[:256]


def user_info(claims, issuer, client_id):
    """신원 형식을 검사하고 조직·다른 client 역할은 권한으로 사용하지 않는다."""
    if claims.get('iss') != issuer or not isinstance(claims.get('sub'), str) or not claims['sub']:
        raise ValueError('OIDC 신원 claim 오류')
    access = claims.get('resource_access', {})
    if not isinstance(access, dict):
        raise ValueError('OIDC 역할 claim 형식 오류')
    client = access.get(client_id, {})
    if not isinstance(client, dict):
        raise ValueError('OIDC client 역할 형식 오류')
    roles = client.get('roles', [])
    if not isinstance(roles, list) or any(not isinstance(role, str) for role in roles):
        raise ValueError('OIDC 역할 배열 형식 오류')
    identity = json.dumps([issuer, claims['sub']], ensure_ascii=True, separators=(',', ':'))
    username = 'kc_' + hashlib.sha256(identity.encode()).hexdigest()
    profile = {}
    for claim, field in [('email', 'email'), ('given_name', 'first_name'), ('family_name', 'last_name')]:
        value = claims.get(claim, '')
        if not isinstance(value, str):
            raise ValueError('OIDC 프로필 claim 형식 오류')
        profile[field] = value
    return {**profile, 'username': username,
            'role_keys': sorted({'Viewer'} | (set(roles) & {'Admin', 'User', 'Viewer'}))}
