"""OIDC helper utilities for validating id_token-only ADFS responses."""
from __future__ import annotations

import base64
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
CER_PATH = settings.ADFS_CER_PATH


def _read_certificate_bytes(path: str | Path) -> bytes:
    try:
        return Path(path).expanduser().resolve(strict=True).read_bytes()
    except FileNotFoundError as exc:  # pragma: no cover - helpful error context
        raise RuntimeError(f"OIDC public certificate not found: {path}") from exc
    except OSError as exc:  # pragma: no cover
        raise RuntimeError(f"Failed to read OIDC certificate: {path}") from exc


def load_public_key_from_cer() -> object:
    """Load an RSA public key from a .cer (PEM or DER) file."""

    data = _read_certificate_bytes(CER_PATH)
    try:
        cert = x509.load_pem_x509_certificate(data, default_backend())
    except ValueError:
        cert = x509.load_der_x509_certificate(data, default_backend())
    return cert.public_key()


PUB_KEY = load_public_key_from_cer()


def is_allowed_redirect(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if not parsed.scheme or not parsed.netloc:
        return False
    # HTTPS 강제 및 등록된 호스트만 허용
    return parsed.scheme.lower() == "https" and parsed.netloc in settings.ALLOWED_REDIRECT_HOSTS


def b64e(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("utf-8")


def b64d(value: str) -> str:
    return base64.urlsafe_b64decode(value.encode("utf-8")).decode("utf-8")


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
    "PUB_KEY",
    "is_allowed_redirect",
    "b64e",
    "b64d",
    "save_nonce",
    "pop_nonce",
]
