"""
Django settings for the REST API backend
- 가독성 향상
- 환경변수 헬퍼 추가 (bool/int/list)
- 운영/개발 환경에 따른 보안 옵션 안전화
- DB 설정 정리 (SQLite/MySQL 모두 지원)
- CORS/CSRF/프록시(HTTPS) 관련 옵션 명시적 구성
- OIDC(SSO) 설정 가시성 및 더미 로그인 플래그
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable


# ==============================
# 환경변수 파서 유틸 (읽기 쉬움 & 안전)
# ==============================
def env(key: str, default: str | None = None) -> str | None:
    """문자열 환경변수 읽기 (없으면 default)"""
    return os.environ.get(key, default)


def env_bool(key: str, default: bool = False) -> bool:
    """불리언 환경변수 파싱: 1/true/yes/on → True"""
    value = os.environ.get(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(key: str, default: int | None = None) -> int | None:
    """정수 환경변수 파싱 (실패 시 default)"""
    value = os.environ.get(key)
    if value is None:
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


def env_list(key: str, default: str | Iterable[str] = "", sep: str = ",") -> list[str]:
    """
    쉼표 구분 리스트 파싱 (공백과 빈 문자열 제거)
    예: "a, b, ,c" -> ["a","b","c"]
    """
    if isinstance(default, str):
        raw = os.environ.get(key, default)
        items = [s.strip() for s in raw.split(sep)]
    else:
        items = [s.strip() for s in default]  # 이미 리스트/튜플인 경우
    return [s for s in items if s]


# ============
# 기본 경로 등
# ============
BASE_DIR = Path(__file__).resolve().parent.parent

# ⚠ 개발 키는 반드시 운영에서 교체
SECRET_KEY = env("DJANGO_SECRET_KEY", "insecure-development-key")

# DEBUG는 운영에서 False 권장
DEBUG = env_bool("DJANGO_DEBUG", False)

# 예: "example.com, api.example.com, localhost, 127.0.0.1"
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,api")

# 외부에서 접근 가능한 API 기본 prefix/URL (예: "/api" 혹은 "https://api.example.com")
PUBLIC_API_BASE_URL = env("PUBLIC_API_BASE_URL") or env("DJANGO_PUBLIC_API_BASE_URL") or ""
if isinstance(PUBLIC_API_BASE_URL, str):
    PUBLIC_API_BASE_URL = PUBLIC_API_BASE_URL.strip()
    if PUBLIC_API_BASE_URL and PUBLIC_API_BASE_URL != "/":
        PUBLIC_API_BASE_URL = PUBLIC_API_BASE_URL.rstrip("/")
    elif PUBLIC_API_BASE_URL == "/":
        PUBLIC_API_BASE_URL = ""
else:
    PUBLIC_API_BASE_URL = ""


# ============
# 애플리케이션
# ============
INSTALLED_APPS = [
    # Django 기본
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # 서드파티
    "rest_framework",
    "corsheaders",
    "drf_spectacular",
    "drf_spectacular_sidecar",
    # 로컬 앱
    "api",
]


# =========
# 미들웨어
# =========
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",  # CORS는 CommonMiddleware 보다 먼저
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # 사용자 활동 로깅 (커스텀)
    "api.middleware.ActivityLoggingMiddleware",
]


# =========
# URL/WSGI
# =========
ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],  # 필요 시 템플릿 디렉터리 추가
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# =====
# DB 설정 (PostgreSQL 전용)
#  - 컨테이너 네트워크 기준 기본값: HOST=postgres, DB=appdb, USER=airflow, PASSWORD=airflow
#  - 필요 시 환경변수로 덮어쓰기 가능
# =====
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DJANGO_DB_NAME") or env("DB_NAME") or "appdb",
        "USER": env("DJANGO_DB_USER") or env("DB_USER") or "airflow",
        "PASSWORD": env("DJANGO_DB_PASSWORD") or env("DB_PASSWORD") or "airflow",
        "HOST": env("DJANGO_DB_HOST") or env("DB_HOST") or "airflow-postgres",
        "PORT": env("DJANGO_DB_PORT") or env("DB_PORT") or "5432",
        # 연결 재사용(초): 운영 60~300 권장
        "CONN_MAX_AGE": env_int("DJANGO_DB_CONN_MAX_AGE", 60) or 0
    }
}


# ===========================
# 비밀번호 검증 (기본 정책 유지)
# ===========================
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# =======
# 국제화 등
# =======
LANGUAGE_CODE = "en-us"
TIME_ZONE = env("DJANGO_TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True


# ========
# 정적 파일
# ========
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ==================
# Django REST Framework
# ==================
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "api.auth.authentication.CsrfExemptSessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}


# =====================
# OpenAPI / Swagger UI
# =====================
SPECTACULAR_SETTINGS = {
    "TITLE": "Template2 API",
    "DESCRIPTION": "자동 생성된 OpenAPI 스키마",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SWAGGER_UI_SETTINGS": {
        "persistAuthorization": True,
    },
}


# ==========================
# CORS / CSRF 신뢰 도메인
#  - 개발: 모든 오리진 허용 (DEBUG=True)
#  - 운영: 환경변수 목록만 허용
# ==========================
FRONTEND_BASE_URL = env("FRONTEND_BASE_URL", "http://localhost")

CORS_ALLOW_ALL_ORIGINS = DEBUG

# 운영 시 명시 리스트 사용 권장 (쉼표 구분)
CORS_ALLOWED_ORIGINS = env_list(
    "DJANGO_CORS_ALLOWED_ORIGINS",
    FRONTEND_BASE_URL,  # 기본 프론트 URL 1개라도 허용
)

CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = env_list(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    FRONTEND_BASE_URL,
)


# ======================
# 인증 백엔드 및 로그인 URL
# ======================
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
]

LOGIN_URL = "/auth/google/authenticate/"
LOGIN_REDIRECT_URL = env("DJANGO_LOGIN_REDIRECT_URL", "/")
LOGOUT_REDIRECT_URL = env("DJANGO_LOGOUT_REDIRECT_URL", "/")


# ===========
# Google OAuth (SSO)
#  - 실제 IdP 연결 여부를 플래그로 파악
# ===========
GOOGLE_OAUTH_CLIENT_ID = env("GOOGLE_CLIENT_ID") or env("GOOGLE_OAUTH_CLIENT_ID")
GOOGLE_OAUTH_CLIENT_SECRET = env("GOOGLE_CLIENT_SECRET") or env("GOOGLE_OAUTH_CLIENT_SECRET")
GOOGLE_OAUTH_SCOPE = env("GOOGLE_OAUTH_SCOPE", "openid email profile")
GOOGLE_OAUTH_PROMPT = env("GOOGLE_OAUTH_PROMPT", "consent")
GOOGLE_OAUTH_ACCESS_TYPE = env("GOOGLE_OAUTH_ACCESS_TYPE", "offline")
GOOGLE_OAUTH_AUTH_ENDPOINT = env(
    "GOOGLE_OAUTH_AUTH_ENDPOINT",
    "https://accounts.google.com/o/oauth2/v2/auth",
)
GOOGLE_OAUTH_TOKEN_ENDPOINT = env(
    "GOOGLE_OAUTH_TOKEN_ENDPOINT",
    "https://oauth2.googleapis.com/token",
)
GOOGLE_OAUTH_USERINFO_ENDPOINT = env(
    "GOOGLE_OAUTH_USERINFO_ENDPOINT",
    "https://openidconnect.googleapis.com/v1/userinfo",
)
GOOGLE_OAUTH_REDIRECT_URI = env("GOOGLE_OAUTH_REDIRECT_URI")

# 실제 프로바이더가 구성되었는지
GOOGLE_OIDC_CONFIGURED = bool(GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET)

# 기존 코드에서 사용하는 플래그 이름 유지
OIDC_PROVIDER_CONFIGURED = GOOGLE_OIDC_CONFIGURED


# ===============================
# 프록시/HTTPS 및 운영 보안 기본값
#  - 리버스 프록시(X-Forwarded-Proto) 뒤에서 HTTPS 신뢰
#  - 운영에서 Secure 쿠키/리다이렉트 강화
# ===============================
USE_X_FORWARDED_HOST = env_bool("USE_X_FORWARDED_HOST", True)

# 프록시가 HTTPS 헤더를 넘기는 환경(Nginx/Caddy)에서는 아래 헤더 신뢰
if env_bool("DJANGO_USE_PROXY_SSL_HEADER", True):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# 운영 보안 스위치 (DEBUG=False일 때 기본 True 권장)
DJANGO_SECURE = env_bool("DJANGO_SECURE", not DEBUG)
if DJANGO_SECURE:
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", False)  # 필요 시 프록시 레벨에서 처리 권장
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = env_int("SECURE_HSTS_SECONDS", 0) or 0  # 프록시/HSTS 구성에 맞춰 단계적 적용
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", False)
    SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", False)
    SECURE_REFERRER_POLICY = env("SECURE_REFERRER_POLICY", "same-origin")
    # X-Frame-Options는 기본 미들웨어에서 DENY


# =========
# 로깅 설정
#  - DEBUG 시 콘솔에 상세 로그 출력
# =========
if DEBUG:
    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "handlers": {
            "console": {"class": "logging.StreamHandler"},
        },
        "root": {"handlers": ["console"], "level": "DEBUG"},
    }
