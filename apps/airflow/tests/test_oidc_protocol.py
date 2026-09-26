"""실제 Authlib callback 경로에서 서명·issuer·audience·nonce·state 거부를 검증한다.

Airflow 이미지의 의존성이 필요하므로 호스트에서는 생략하고 이미지 안에서 실행한다.
"""

import importlib.util
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

HAS_AUTHLIB = importlib.util.find_spec('authlib') is not None


@unittest.skipUnless(HAS_AUTHLIB, 'Airflow 이미지 안에서 실행하는 OIDC 프로토콜 검사')
class OidcProtocolTests(unittest.TestCase):
    def setUp(self):
        from authlib.integrations.flask_client import OAuth
        from authlib.jose import JsonWebKey
        from cryptography.hazmat.primitives.asymmetric import rsa
        from flask import Flask
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'image'))
        from keycloak_security import KeycloakOAuthView
        self.env = patch.dict(os.environ, {'AIRFLOW_OIDC_ISSUER': 'https://sso.test/realms/main',
                                         'AIRFLOW_OIDC_CLIENT_ID': 'airflow'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        from cryptography.hazmat.primitives import serialization
        self.pem = self.key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                          serialization.NoEncryption())
        public = self.key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        jwk = JsonWebKey.import_key(public, {'kid': 'test-key'}).as_dict()
        self.app = Flask(__name__)
        self.app.secret_key = 'test-session-key'
        oauth = OAuth(self.app)
        self.remote = oauth.register('keycloak', client_id='airflow', client_secret='test-client-secret',
                                     authorize_url='https://sso.test/auth', access_token_url='https://sso.test/token',
                                     issuer='https://sso.test/realms/main', jwks_uri='https://sso.test/certs',
                                     id_token_signing_alg_values_supported=['RS256'],
                                     client_kwargs={'scope': 'openid profile email', 'code_challenge_method': 'S256'})
        self.remote.fetch_jwk_set = Mock(return_value={'keys': [jwk]})
        self.register = Mock(return_value=object())
        view = KeycloakOAuthView()
        view.appbuilder = SimpleNamespace(sm=SimpleNamespace(oauth_remotes={'keycloak': self.remote},
                                                              auth_user_oauth=self.register),
                                          get_url_for_index='/success', get_url_for_login='/login')
        self.app.add_url_rule('/start', endpoint='start', view_func=lambda: self.remote.authorize_redirect('http://localhost/callback'))
        self.app.add_url_rule('/callback', endpoint='callback', view_func=lambda: view.oauth_authorized('keycloak'))
        self.client = self.app.test_client()
        self.login = patch('keycloak_security.login_user')
        self.login.start()
        self.addCleanup(self.login.stop)

    def callback(self, overrides=None, bad_state=False, bad_signature=False, no_id_token=False):
        from authlib.jose import jwt
        query = parse_qs(urlsplit(self.client.get('/start').location).query)
        now = int(time.time())
        claims = {'iss': 'https://sso.test/realms/main', 'sub': 'subject', 'aud': 'airflow',
                  'iat': now, 'exp': now + 300, 'nonce': query['nonce'][0], **(overrides or {})}
        pem = self.pem
        if bad_signature:
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.hazmat.primitives import serialization
            pem = rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
                serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        token = {'access_token': 'test-token', 'token_type': 'Bearer'}
        if not no_id_token:
            token['id_token'] = jwt.encode({'alg': 'RS256', 'kid': 'test-key'}, claims, pem).decode()
        self.remote.fetch_access_token = Mock(return_value=token)
        state = 'invalid' if bad_state else query['state'][0]
        return self.client.get('/callback', query_string={'code': 'test-code', 'state': state})

    def test_valid_token_registers_default_viewer(self):
        self.assertEqual(self.callback().location, '/success')
        self.assertEqual(self.register.call_args.args[0]['role_keys'], ['Viewer'])

    def test_invalid_tokens_never_register(self):
        cases = [dict(overrides={'iss': 'https://wrong.test'}), dict(overrides={'aud': 'portal'}),
                 dict(overrides={'exp': int(time.time()) - 600}), dict(overrides={'nonce': 'wrong'}),
                 dict(overrides={'nonce_supported': False}), dict(bad_state=True),
                 dict(bad_signature=True), dict(no_id_token=True)]
        for case in cases:
            with self.subTest(case=case):
                self.register.reset_mock()
                self.assertEqual(self.callback(**case).location, '/login')
                self.register.assert_not_called()
