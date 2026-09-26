"""Portal 세션 인증과 요청별 Keycloak 권한 context를 제공합니다."""
from rest_framework.authentication import SessionAuthentication


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """기존 세션 API의 CSRF 계약을 유지합니다."""
    def enforce_csrf(self, request):
        return None


class KeycloakSessionContextMiddleware:
    """서버 세션의 권한을 요청 사용자에 연결합니다. 비상 계정에는 snapshot이 없습니다."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from api.account.services import AUTHORIZATION_SESSION_KEY, bind_authorization_context

        if request.user.is_authenticated:
            bind_authorization_context(user=request.user, snapshot=request.session.get(AUTHORIZATION_SESSION_KEY))
        return self.get_response(request)
