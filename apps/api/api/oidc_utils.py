"""OIDC helper utilities for validating id_token-only ADFS responses."""
from __future__ import annotations

import base64
import hashlib
from pathlib import Path
from urllib.parse import urlparse

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from django.conf import settings

ADFS_AUTH_URL = settings.ADFS_AUTH_URL
ADFS_LOGOUT_URL = settings.ADFS_LOGOUT_URL
OIDC_CLIENT_ID = settings.OIDC_CLIENT_ID
ISSUER = settings.OIDC_ISSUER
REDIRECT_URI = settings.OIDC_REDIRECT_URI
CER_PATH = settings.ADFS_CER_PATH  # ADFS 토큰-서명 인증서(.cer, PEM or DER)

# --------------------------
# Certificate / Public key
# --------------------------

def _read_certificate_bytes(path: str | Path) -> bytes:
    try:
        return Path(path).expanduser().resolve(strict=True).read_bytes()
    except FileNotFoundError as exc:
        raise RuntimeError(f"OIDC public certificate not found: {path}") from exc
    except OSError as exc:
        raise RuntimeError(f"Failed to read OIDC certificate: {path}") from exc


def load_x509_cert(path: str | Path) -> x509.Certificate:
    """Load an X.509 certificate from .cer (PEM or DER)."""
    data = _read_certificate_bytes(path)
    try:
        return x509.load_pem_x509_certificate(data, default_backend())
    except ValueError:
        return x509.load_der_x509_certificate(data, default_backend())


def load_public_key_from_cer() -> object:
    """Load an RSA public key from a .cer file (PEM/DER)."""
    cert = load_x509_cert(CER_PATH)
    return cert.public_key()


def compute_cert_thumbprint_x5t(cert: x509.Certificate) -> str:
    """
    ADFS/JOSE 의 x5t(sha1)는 인증서의 DER 바이트를 SHA-1 후 base64url 인코딩.
    반환: base64url(sha1(der))
    """
    der = cert.public_bytes(encoding=x509.Encoding.DER)
    sha1 = hashlib.sha1(der).digest()
    return base64.urlsafe_b64encode(sha1).rstrip(b"=").decode("ascii")


PUB_CERT = load_x509_cert(CER_PATH)   # 전체 인증서 (thumbprint 비교용)
PUB_KEY = PUB_CERT.public_key()       # PyJWT 검증에 사용

# --------------------------
# Redirect safety
# --------------------------

def is_allowed_redirect(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if not parsed.scheme or not parsed.netloc:
        return False

    scheme = parsed.scheme.lower()
    allowed_schemes = {"https"}
    # 개발 환경(HTTP 프록시)에서는 http도 허용
    if getattr(settings, "DJANGO_SECURE", True) is False or getattr(settings, "DEBUG", False):
        allowed_schemes.add("http")

    return scheme in allowed_schemes and parsed.netloc in settings.ALLOWED_REDIRECT_HOSTS

# --------------------------
# State encode/decode
# --------------------------

def _pad(s: str) -> str:
    # urlsafe_b64decode는 패딩이 없으면 실패할 수 있어 보정
    return s + "=" * (-len(s) % 4)

def b64e(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("utf-8")

def b64d(value: str) -> str:
    # 문자열을 반환 (콜백에서 바로 redirect target으로 사용 가능)
    return base64.urlsafe_b64decode(_pad(value)).decode("utf-8")

# --------------------------
# Nonce in session
# --------------------------

def save_nonce(request, nonce: str) -> None:
    request.session["oidc_nonce"] = nonce

def pop_nonce(request) -> str | None:
    return request.session.pop("oidc_nonce", None)

__all__ = [
    "ADFS_AUTH_URL",
    "ADFS_LOGOUT_URL",
    "OIDC_CLIENT_ID",
    "ISSUER",
    "REDIRECT_URI",
    "CER_PATH",
    "PUB_CERT",
    "PUB_KEY",
    "is_allowed_redirect",
    "b64e",
    "b64d",
    "save_nonce",
    "pop_nonce",
    "compute_cert_thumbprint_x5t",
]
