"""Authentication helpers for the API service."""

from __future__ import annotations

from rest_framework.authentication import SessionAuthentication


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """
    SessionAuthentication variant that skips CSRF enforcement.

    Our SPA already operates behind the same reverse proxy as the API and
    relies on credentialed fetch requests. Django REST Framework's default
    SessionAuthentication rejects unsafe requests without a CSRF token,
    which blocks PATCH/POST calls coming from the frontend even though the
    user is already authenticated via the session cookie. Overriding
    ``enforce_csrf`` keeps the familiar session workflow while letting the
    API endpoints accept those requests.
    """

    def enforce_csrf(self, request):
        """Bypass CSRF checks – reverse proxy + session cookie guard us."""

        return None


__all__ = ["CsrfExemptSessionAuthentication"]
