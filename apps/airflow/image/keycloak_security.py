"""Keycloak의 검증된 신원만 FAB에 전달하고 토큰을 로그·세션에 보관하지 않는다."""

import logging
import os
from contextvars import ContextVar

from authlib.oidc.core import UserInfo
from airflow.providers.fab.auth_manager.fab_auth_manager import FabAuthManager
from airflow.providers.fab.auth_manager.security_manager.override import FabAirflowSecurityManagerOverride
from flask import flash, g, session
from airflow.providers.fab.www.views import redirect
from flask_appbuilder import expose
from flask_appbuilder.security.views import AuthOAuthView
from flask_login import login_user
from markupsafe import Markup, escape
from sqlalchemy.exc import SQLAlchemyError
from wtforms.widgets import HiddenInput

from oidc_claims import display_label, user_info
from keycloak_profile import display_names, is_sso_username, save_display_name

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
            user = security_manager.auth_user_oauth(info)
            if user is None:
                raise ValueError('사용자 등록 또는 로그인 실패')
            try:
                save_display_name(security_manager.session, user.id, display_label(claims))
                user.first_name, user.last_name = info['first_name'], info['last_name']
                if not security_manager.update_user(user):
                    log.warning('Keycloak 사용자의 표시 이름을 갱신하지 못했습니다.')
            except SQLAlchemyError:
                security_manager.session.rollback()
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


class KeycloakUserView(FabAirflowSecurityManagerOverride.useroauthmodelview):
    """FAB 사용자 관리 화면에서 읽기 전용 표시값을 보여 줍니다."""

    def _set_username_display(self, widget, usernames):
        names = display_names(usernames)
        args = widget.template_args
        args['formatters_columns'] = {
            **(args.get('formatters_columns') or {}),
            'username': lambda username: escape(names.get(username, username)),
        }

    def _get_list_widget(self, *args, **kwargs):
        widgets = super()._get_list_widget(*args, **kwargs)
        widget = widgets['list']
        rows = widget.template_args['value_columns'] = list(widget.template_args['value_columns'])
        self._set_username_display(widget, [row['username'] for row in rows])
        return widgets

    def _get_show_widget(self, pk, item, *args, **kwargs):
        widgets = super()._get_show_widget(pk, item, *args, **kwargs)
        self._set_username_display(widgets['show'], [item.username])
        return widgets

    def _get_edit_widget(self, form, *args, **kwargs):
        field = getattr(form, 'username', None)
        if field is not None and is_sso_username(field.data):
            name = display_names([field.data]).get(field.data, 'Keycloak 사용자')
            # FAB 편집 폼은 기존 username을 제출하며 화면에는 별도 표시값을 보여 줍니다.
            field.widget = lambda input_field, **options: Markup('{}{}').format(
                name, HiddenInput()(input_field, **options),
            )
        return super()._get_edit_widget(form, *args, **kwargs)


class KeycloakSecurityManager(FabAirflowSecurityManagerOverride):
    """웹 SSO와 기존 DB 계정의 API 인증을 함께 지원한다."""

    authoauthview = KeycloakOAuthView
    useroauthmodelview = KeycloakUserView


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
        if is_sso_username(user.username):
            # FAB 캐시의 동일 사용자를 조회하더라도 감사·실행 API는 기존 이름을 사용합니다.
            user.get_name = lambda: (
                display_names([user.username]).get(user.username, 'Keycloak 사용자')
                if show_profile_name.get() else user.username
            )
        return user
