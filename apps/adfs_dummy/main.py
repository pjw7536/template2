"""FastAPI-based dummy ADFS server that emits id_token-only OIDC responses."""
from __future__ import annotations

import hashlib
import html
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict

import jwt
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

app = FastAPI(title="Dummy ADFS", version="2.0.0")

CLIENT_ID = os.getenv("DUMMY_ADFS_CLIENT_ID", "dummy-client")
DEFAULT_EMAIL = os.getenv("DUMMY_ADFS_EMAIL", "dummy.user@example.com")
DEFAULT_NAME = os.getenv("DUMMY_ADFS_NAME", "Dummy User")
DEFAULT_DEPT = os.getenv("DUMMY_ADFS_DEPT", "Development")
ISSUER = os.getenv("DUMMY_ADFS_ISSUER", "http://localhost:9000/adfs")
PRIVATE_KEY_PATH = Path(os.getenv("DUMMY_ADFS_PRIVATE_KEY_PATH", "dummy_adfs_private.key")).resolve()
LOGOUT_REDIRECT = os.getenv("DUMMY_ADFS_LOGOUT_TARGET", "http://localhost")

try:
    PRIVATE_KEY = PRIVATE_KEY_PATH.read_text(encoding="utf-8")
except OSError as exc:  # pragma: no cover - dev feedback
    raise RuntimeError(f"Failed to read dummy ADFS private key: {PRIVATE_KEY_PATH}") from exc


def _render_login_form(request: Request) -> str:
    params = request.query_params
    email = html.escape(params.get("email") or DEFAULT_EMAIL)
    name = html.escape(params.get("name") or DEFAULT_NAME)
    state = html.escape(params.get("state") or "")
    nonce = html.escape(params.get("nonce") or secrets.token_urlsafe(16))
    redirect_uri = html.escape(params.get("redirect_uri") or "")
    client_id = html.escape(params.get("client_id") or "")

    return f"""
    <html>
      <head>
        <title>Dummy ADFS Login</title>
        <style>
          body {{ font-family: sans-serif; padding: 2rem; background: #f5f5f5; }}
          form {{ max-width: 360px; margin: auto; padding: 1.5rem; background: white; border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); }}
          label {{ display: block; font-weight: 600; margin-bottom: 0.25rem; }}
          input {{ width: 100%; padding: 0.5rem; margin-bottom: 1rem; border-radius: 8px; border: 1px solid #d4d4d8; }}
          button {{ width: 100%; padding: 0.75rem; background: #2563eb; color: white; font-weight: 600; border: none; border-radius: 8px; cursor: pointer; }}
          button:hover {{ background: #1d4ed8; }}
          .hint {{ margin-top: 1rem; font-size: 0.85rem; color: #4b5563; text-align: center; }}
        </style>
      </head>
      <body>
        <form method="post" action="/authorize">
          <h1>Dummy ADFS</h1>
          <p class="hint">입력값을 조정한 뒤 "Sign in"을 누르면 콜백으로 리다이렉트합니다.</p>
          <label for="email">Email</label>
          <input id="email" name="email" value="{email}" type="email" required />
          <label for="name">Display name</label>
          <input id="name" name="name" value="{name}" type="text" required />
          <input type="hidden" name="state" value="{state}" />
          <input type="hidden" name="nonce" value="{nonce}" />
          <input type="hidden" name="redirect_uri" value="{redirect_uri}" />
          <input type="hidden" name="client_id" value="{client_id}" />
          <button type="submit">Sign in</button>
        </form>
      </body>
    </html>
    """


def _build_id_token(*, email: str, name: str, nonce: str) -> str:
    now = datetime.now(timezone.utc)
    subject = hashlib.sha256(email.encode("utf-8")).hexdigest()[:32]

    payload = {
        "aud": CLIENT_ID,
        "iss": ISSUER,
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
        "nonce": nonce,
        "mail": email,
        "email": email,
        "userid": email,
        "upn": email,
        "username": name,
        "name": name,
        "deptname": DEFAULT_DEPT,
        "jti": secrets.token_hex(16),
    }

    return jwt.encode(payload, PRIVATE_KEY, algorithm="RS256")


@app.get("/authorize", response_class=HTMLResponse)
async def authorize_form(request: Request) -> HTMLResponse:
    redirect_uri = request.query_params.get("redirect_uri")
    if not redirect_uri:
        raise HTTPException(status_code=400, detail="missing redirect_uri")
    if CLIENT_ID and request.query_params.get("client_id") not in {"", CLIENT_ID}:
        raise HTTPException(status_code=400, detail="invalid_client")
    return HTMLResponse(_render_login_form(request))


@app.post("/authorize")
async def authorize(
    email: str = Form(DEFAULT_EMAIL),
    name: str = Form(DEFAULT_NAME),
    state: str = Form(""),
    nonce: str = Form(""),
    redirect_uri: str = Form(...),
    client_id: str = Form(""),
) -> HTMLResponse:
    if CLIENT_ID and client_id and client_id != CLIENT_ID:
        raise HTTPException(status_code=400, detail="invalid_client")
    if not redirect_uri:
        raise HTTPException(status_code=400, detail="missing_redirect")

    nonce_value = nonce or secrets.token_urlsafe(16)
    id_token = _build_id_token(email=email or DEFAULT_EMAIL, name=name or DEFAULT_NAME, nonce=nonce_value)

    html_body = f"""
    <html>
      <head>
        <title>ADFS redirect</title>
      </head>
      <body>
        <form id="callback-form" method="post" action="{html.escape(redirect_uri)}">
          <input type="hidden" name="id_token" value="{html.escape(id_token)}" />
          <input type="hidden" name="state" value="{html.escape(state)}" />
        </form>
        <script>document.getElementById('callback-form').submit();</script>
      </body>
    </html>
    """
    return HTMLResponse(content=html_body)


@app.get("/logout")
async def logout() -> RedirectResponse:
    target = LOGOUT_REDIRECT or "/"
    return RedirectResponse(url=target, status_code=302)


@app.get("/.well-known/openid-configuration")
async def openid_config(request: Request) -> Dict[str, Any]:
    base = str(request.url.replace(path="", query="", fragment=""))[:-1]
    return {
        "issuer": ISSUER,
        "authorization_endpoint": f"{base}/authorize",
        "token_endpoint": f"{base}/token",
        "userinfo_endpoint": f"{base}/userinfo",
        "response_types_supported": ["id_token"],
        "grant_types_supported": ["implicit"],
        "scopes_supported": ["openid", "profile", "email"],
    }
