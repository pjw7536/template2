"""FastAPI 기반 더미 ADFS(OIDC) 제공자."""
from __future__ import annotations

import hashlib
import html
import os
import secrets
from typing import Dict
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from fastapi import FastAPI, Form, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

app = FastAPI(title="Dummy ADFS", version="1.0.0")

CLIENT_ID = os.getenv("DUMMY_ADFS_CLIENT_ID", "dummy-client")
CLIENT_SECRET = os.getenv("DUMMY_ADFS_CLIENT_SECRET", "dummy-secret")
DEFAULT_EMAIL = os.getenv("DUMMY_ADFS_EMAIL", "dummy.user@example.com")
DEFAULT_NAME = os.getenv("DUMMY_ADFS_NAME", "Dummy User")
_DEFAULT_NAME_PARTS = [part for part in DEFAULT_NAME.split() if part] or ["Dummy", "User"]
DEFAULT_GIVEN = os.getenv("DUMMY_ADFS_GIVEN_NAME", _DEFAULT_NAME_PARTS[0])
DEFAULT_FAMILY = os.getenv(
    "DUMMY_ADFS_FAMILY_NAME",
    _DEFAULT_NAME_PARTS[1] if len(_DEFAULT_NAME_PARTS) > 1 else "",
)

_AUTH_CODES: Dict[str, Dict[str, str]] = {}
_ACCESS_TOKENS: Dict[str, Dict[str, str]] = {}


def _append_params(url: str, params: Dict[str, str]) -> str:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.update({k: v for k, v in params.items() if v is not None})
    new_query = urlencode(query)
    return urlunparse(parsed._replace(query=new_query))


def _render_login_form(request: Request) -> str:
    params = request.query_params
    email = html.escape(params.get("email") or DEFAULT_EMAIL)
    name = html.escape(params.get("name") or DEFAULT_NAME)
    state = html.escape(params.get("state") or "")
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
          <input type="hidden" name="redirect_uri" value="{redirect_uri}" />
          <input type="hidden" name="client_id" value="{client_id}" />
          <button type="submit">Sign in</button>
        </form>
      </body>
    </html>
    """


@app.get("/authorize", response_class=HTMLResponse)
async def authorize_form(request: Request) -> HTMLResponse:
    """간단한 로그인 폼 렌더링."""

    redirect_uri = request.query_params.get("redirect_uri")
    if not redirect_uri:
        raise HTTPException(status_code=400, detail="missing redirect_uri")
    return HTMLResponse(_render_login_form(request))


@app.post("/authorize")
async def authorize(
    email: str = Form(DEFAULT_EMAIL),
    name: str = Form(DEFAULT_NAME),
    state: str = Form(""),
    redirect_uri: str = Form(...),
    client_id: str = Form(""),
) -> RedirectResponse:
    """사용자 입력을 받아 authorization code 발급."""

    expected_client = CLIENT_ID
    if expected_client and client_id and client_id != expected_client:
        raise HTTPException(status_code=400, detail="invalid_client")

    code = secrets.token_urlsafe(32)
    raw_name = name or DEFAULT_NAME
    parts = [part for part in raw_name.split() if part]
    given = parts[0] if parts else DEFAULT_GIVEN
    family = parts[1] if len(parts) > 1 else DEFAULT_FAMILY
    profile = {
        "email": email or DEFAULT_EMAIL,
        "name": raw_name,
        "given_name": given,
        "family_name": family,
    }
    _AUTH_CODES[code] = profile

    params = {"code": code, "state": state or None}
    redirect_target = _append_params(redirect_uri, params)
    return RedirectResponse(url=redirect_target, status_code=302)


@app.post("/token")
async def token(
    grant_type: str = Form("authorization_code"),
    code: str = Form(...),
    client_id: str = Form(""),
    client_secret: str = Form(""),
) -> Dict[str, str]:
    """authorization code를 access token으로 교환."""

    if grant_type != "authorization_code":
        raise HTTPException(status_code=400, detail="unsupported_grant_type")

    expected_client = CLIENT_ID
    if expected_client and client_id and client_id != expected_client:
        raise HTTPException(status_code=400, detail="invalid_client")

    expected_secret = CLIENT_SECRET
    if expected_secret and client_secret and client_secret != expected_secret:
        raise HTTPException(status_code=400, detail="invalid_client_secret")

    profile = _AUTH_CODES.pop(code, None)
    if not profile:
        raise HTTPException(status_code=400, detail="invalid_grant")

    access_token = secrets.token_urlsafe(32)
    refresh_token = secrets.token_urlsafe(32)
    _ACCESS_TOKENS[access_token] = profile

    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": 3600,
        "refresh_token": refresh_token,
        "id_token": secrets.token_urlsafe(48),
    }


@app.get("/userinfo")
async def userinfo(authorization: str = Header("")) -> Dict[str, str]:
    """Bearer 토큰을 검증하고 사용자 정보를 반환."""

    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing_token")

    token = authorization.split(" ", 1)[1]
    profile = _ACCESS_TOKENS.get(token)
    if not profile:
        raise HTTPException(status_code=401, detail="invalid_token")

    email = profile.get("email", DEFAULT_EMAIL)
    name = profile.get("name", DEFAULT_NAME)
    given = profile.get("given_name", DEFAULT_GIVEN)
    family = profile.get("family_name", DEFAULT_FAMILY)
    subject = hashlib.sha256(email.encode("utf-8")).hexdigest()[:32]

    return {
        "sub": subject,
        "email": email,
        "name": name,
        "given_name": given,
        "family_name": family,
    }


@app.get("/.well-known/openid-configuration")
async def openid_config(request: Request) -> Dict[str, str]:
    """기본 OIDC discovery 문서 제공."""

    base = str(request.url.replace(path="", query="", fragment=""))[:-1]
    return {
        "issuer": base,
        "authorization_endpoint": f"{base}/authorize",
        "token_endpoint": f"{base}/token",
        "userinfo_endpoint": f"{base}/userinfo",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "scopes_supported": ["openid", "profile", "email"],
    }


if __name__ == "__main__":
    port = int(os.getenv("PORT", "9000"))
    uvicorn_kwargs = {
        "app": "main:app",
        "host": "0.0.0.0",
        "port": port,
        "reload": bool(os.getenv("RELOAD", "")),
    }

    # FastAPI 앱을 직접 실행할 때 uvicorn을 동적으로 import 합니다.
    import uvicorn  # type: ignore

    uvicorn.run(**uvicorn_kwargs)
