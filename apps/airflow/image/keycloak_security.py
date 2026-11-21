"""Keycloak의 검증된 신원만 FAB에 전달하고 토큰을 로그·세션에 보관하지 않는다."""

import logging
import os
import re
from contextvars import ContextVar

from authlib.oidc.core import UserInfo
from airflow.providers.fab.auth_manager.fab_auth_manager import FabAuthManager
from airflow.providers.fab.auth_manager.security_manager.override import FabAirflowSecurityManagerOverride
from flask import flash, g, session
from airflow.providers.fab.www.views import redirect
from flask_appbuilder import expose
from flask_appbuilder.security.views import AuthOAuthView
from flask_login import login_user

from oidc_claims import display_label, user_info

log = logging.getLogger(__name__)
show_profile_name = ContextVar('show_profile_name', default=False)


class KeycloakOAuthView(AuthOAuthView):
    """Authlib의 state·nonce·ID Token 검증 뒤에만 사용자를 등록한다."""

    @expose('/oauth-authorized/<provider>')
    def oauth_authorized(self, provider):
        """상위 FAB callback의 토큰 debug 로그와 쿠키 내 토큰 저장을 피한다."""
        try:
            if provider != 'keycloak':
                raise ValueError('지원하지 않는 인증 제공자')
            remote = self.appbuilder.sm.oauth_remotes[provider]
            token = remote.authorize_access_token()
            # UserInfo는 nonce를 포함한 Authlib ID Token 검증 경로에서만 만들어진다.
            claims = token.get('userinfo')
            if not isinstance(claims, UserInfo) or not claims.get('nonce') or claims.get('nonce_supported') is False:
                raise ValueError('검증된 OIDC ID Token이 필요합니다.')
            info = user_info(claims, os.environ['AIRFLOW_OIDC_ISSUER'].rstrip('/'),
                             os.environ['AIRFLOW_OIDC_CLIENT_ID'])
            security_manager = self.appbuilder.sm
            label = display_label(claims)
            if label:
                info.update(first_name=label, last_name='')
            user = security_manager.auth_user_oauth(info)
            if user is None:
                raise ValueError('사용자 등록 또는 로그인 실패')
            if label and (user.first_name != label or user.last_name):
                user.first_name, user.last_name = label, ''
                if not security_manager.update_user(user):
                    log.warning('Keycloak 사용자의 표시 이름을 갱신하지 못했습니다.')
            login_user(user)
            # FAB의 redirect가 Airflow UI·API용 HttpOnly JWT 쿠키를 발급한다.
            g.user = user
            session.modified = True
            return redirect(self.appbuilder.get_url_for_index)
        except Exception:
            # 외부 오류 문자열에는 code·토큰이 섞일 수 있으므로 상세 값을 기록하지 않는다.
            log.warning('Keycloak 로그인 검증 또는 사용자 등록 실패')
            flash('Keycloak 로그인에 실패했습니다. 다시 로그인해 주세요.', 'warning')
            return redirect(self.appbuilder.get_url_for_login)


class KeycloakSecurityManager(FabAirflowSecurityManagerOverride):
    """웹 SSO와 기존 DB 계정의 API 인증을 함께 지원한다."""

    authoauthview = KeycloakOAuthView


class ProfileNameMiddleware:
    """UI 사용자 메뉴 API 요청에만 표시 이름을 사용합니다."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['method'] != 'GET' or not scope['path'].endswith('/ui/auth/me'):
            return await self.app(scope, receive, send)
        token = show_profile_name.set(True)
        try:
            return await self.app(scope, receive, send)
        finally:
            show_profile_name.reset(token)


class KeycloakAuthManager(FabAuthManager):
    """FAB API에 표시 이름을 제공하고 DB username과 사용자 ID는 유지합니다."""

    def get_fastapi_middlewares(self):
        return [*super().get_fastapi_middlewares(), (ProfileNameMiddleware, {})]

    def deserialize_user(self, token):
        user = super().deserialize_user(token)
        if re.fullmatch(r'kc_[0-9a-f]{64}', user.username or '') and user.first_name and not user.last_name:
            # FAB 캐시의 동일 사용자를 조회하더라도 감사·실행 API는 기존 이름을 사용합니다.
            user.get_name = lambda: user.first_name if show_profile_name.get() else user.username
        return user
