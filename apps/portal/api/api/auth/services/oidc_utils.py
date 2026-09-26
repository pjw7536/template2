"""Keycloak callback의 복귀 주소를 허용 목록으로 검사합니다."""
from urllib.parse import urlparse
from django.conf import settings


def is_allowed_redirect(url: str) -> bool:
    """리다이렉트 대상 URL이 허용 목록에 속하는지 검사합니다.

    입력:
    - url: 리다이렉트 대상 URL

    반환:
    - bool: 허용 여부

    부작용:
    - 없음

    오류:
    - 없음(파싱 실패 시 False)
    """

    # -----------------------------------------------------------------------------
    # 1) URL 파싱
    # -----------------------------------------------------------------------------
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if not parsed.scheme or not parsed.netloc:
        return False

    # -----------------------------------------------------------------------------
    # 2) 허용 스킴 결정
    # -----------------------------------------------------------------------------
    scheme = parsed.scheme.lower()
    allowed_schemes = {"https"}
    # 개발 환경(HTTP 프록시)에서는 http도 허용
    if getattr(settings, "DJANGO_SECURE", True) is False or getattr(settings, "DEBUG", False):
        allowed_schemes.add("http")

    # -----------------------------------------------------------------------------
    # 3) 허용 호스트/스킴 검사
    # -----------------------------------------------------------------------------
    return scheme in allowed_schemes and parsed.netloc in settings.ALLOWED_REDIRECT_HOSTS
