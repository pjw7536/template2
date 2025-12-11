"""FastAPI-based dummy ADFS server that emits id_token-only OIDC responses."""
from __future__ import annotations

import hashlib
import html
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

import jwt
from fastapi import Body, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

app = FastAPI(title="Dummy ADFS", version="2.0.0")

CLIENT_ID = os.getenv("DUMMY_ADFS_CLIENT_ID", "dummy-client")
DEFAULT_EMAIL = os.getenv("DUMMY_ADFS_EMAIL", "dummy.user@example.com")
DEFAULT_NAME = os.getenv("DUMMY_ADFS_NAME", "Dummy User")
DEFAULT_DEPT = os.getenv("DUMMY_ADFS_DEPT", "Development")
DEFAULT_SABUN = os.getenv("DUMMY_ADFS_SABUN", "S000001")
ISSUER = os.getenv("DUMMY_ADFS_ISSUER", "http://localhost:9000/adfs")
PRIVATE_KEY_PATH = Path(os.getenv("DUMMY_ADFS_PRIVATE_KEY_PATH", "dummy_adfs_private.key")).resolve()
LOGOUT_REDIRECT = os.getenv("DUMMY_ADFS_LOGOUT_TARGET", "http://localhost")

try:
    PRIVATE_KEY = PRIVATE_KEY_PATH.read_text(encoding="utf-8")
except OSError as exc:  # pragma: no cover - dev feedback
    raise RuntimeError(f"Failed to read dummy ADFS private key: {PRIVATE_KEY_PATH}") from exc

MAILBOX: Dict[int, Dict[str, Any]] = {}
MAIL_ID_SEQ = 1
DEFAULT_PERMISSION_GROUPS: List[str] = ["rag-public"]
RAG_DOCS: Dict[str, Dict[str, Any]] = {}


def _merge_title_content(title: str, content: str) -> str:
    parts = [piece.strip() for piece in [title or "", content or ""] if piece and piece.strip()]
    return "\n\n".join(parts)


def _store_rag_doc(
    *,
    doc_id: str,
    title: str,
    content: str,
    permission_groups: List[str],
    metadata: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    merged = _merge_title_content(title, content)
    stored = {
        "doc_id": doc_id,
        "title": title,
        "content": content,
        "merge_title_content": merged,
        "permission_groups": permission_groups or list(DEFAULT_PERMISSION_GROUPS),
        "metadata": metadata or {},
    }
    RAG_DOCS[doc_id] = stored
    return stored


def _seed_dummy_state() -> None:
    """Reset dummy mail + RAG stores with predictable data."""
    global MAIL_ID_SEQ
    MAILBOX.clear()
    RAG_DOCS.clear()
    MAIL_ID_SEQ = 1

    now = datetime.now(timezone.utc)
    samples = [
        {
            "subject": "[더미] 생산 라인 점검 알림",
            "sender": "alerts@example.com",
            "recipient": DEFAULT_EMAIL,
            "body_text": "주간 생산 라인 점검 예정입니다. 안전 수칙을 확인해주세요.",
            "received_at": now.isoformat(),
        },
        {
            "subject": "[더미] 장비 교체 일정 안내",
            "sender": "maintenance@example.com",
            "recipient": DEFAULT_EMAIL,
            "body_text": "Etch 장비 교체 작업이 예정되어 있습니다. 관련 문서를 확인해주세요.",
            "received_at": (now - timedelta(hours=4)).isoformat(),
        },
    ]

    for sample in samples:
        mail_id = MAIL_ID_SEQ
        MAIL_ID_SEQ += 1
        entry = {
            "id": mail_id,
            "message_id": f"msg-{mail_id:04d}",
            **sample,
        }
        MAILBOX[mail_id] = entry
        doc_id = f"email-{mail_id}"
        entry["rag_doc_id"] = doc_id
        _store_rag_doc(
            doc_id=doc_id,
            title=entry["subject"],
            content=entry["body_text"],
            permission_groups=list(DEFAULT_PERMISSION_GROUPS),
            metadata={
                "email_id": mail_id,
                "message_id": entry["message_id"],
                "sender": entry["sender"],
                "recipient": entry["recipient"],
                "received_at": entry["received_at"],
            },
        )


_seed_dummy_state()


def _render_login_form(request: Request) -> str:
    params = request.query_params
    email = html.escape(params.get("email") or DEFAULT_EMAIL)
    name = html.escape(params.get("name") or DEFAULT_NAME)
    sabun = html.escape(params.get("sabun") or DEFAULT_SABUN)
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
          <label for="sabun">Sabun (사번)</label>
          <input id="sabun" name="sabun" value="{sabun}" type="text" required />
          <input type="hidden" name="state" value="{state}" />
          <input type="hidden" name="nonce" value="{nonce}" />
          <input type="hidden" name="redirect_uri" value="{redirect_uri}" />
          <input type="hidden" name="client_id" value="{client_id}" />
          <button type="submit">Sign in</button>
        </form>
      </body>
    </html>
    """


def _build_id_token(*, email: str, name: str, sabun: str, nonce: str) -> str:
    now = datetime.now(timezone.utc)
    stable_id = sabun or email
    subject = hashlib.sha256(stable_id.encode("utf-8")).hexdigest()[:32]

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
        "sabun": sabun,
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
    sabun: str = Form(DEFAULT_SABUN),
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
    id_token = _build_id_token(
        email=email or DEFAULT_EMAIL,
        name=name or DEFAULT_NAME,
        sabun=sabun or DEFAULT_SABUN,
        nonce=nonce_value,
    )

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


@app.get("/mail/messages")
async def list_dummy_mail() -> Dict[str, Any]:
    """Return all dummy mail messages for quick manual testing."""
    return {"count": len(MAILBOX), "messages": list(MAILBOX.values())}


@app.post("/mail/messages")
async def create_dummy_mail(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Create a dummy mail entry and optionally register it to the dummy RAG store."""
    global MAIL_ID_SEQ

    subject = str(payload.get("subject") or "로컬 더미 메일").strip()
    sender = str(payload.get("sender") or "sender@example.com").strip()
    recipient = str(payload.get("recipient") or DEFAULT_EMAIL).strip()
    body_text = str(payload.get("body") or payload.get("content") or "본문이 비어 있습니다.").strip()
    message_id = str(payload.get("message_id") or f"msg-{MAIL_ID_SEQ:04d}").strip()
    received_at = str(payload.get("received_at") or datetime.now(timezone.utc).isoformat())
    register_to_rag = bool(payload.get("register_to_rag", True))

    mail_id = MAIL_ID_SEQ
    MAIL_ID_SEQ += 1

    entry = {
        "id": mail_id,
        "message_id": message_id,
        "subject": subject,
        "sender": sender,
        "recipient": recipient,
        "body_text": body_text,
        "received_at": received_at,
    }
    MAILBOX[mail_id] = entry

    if register_to_rag:
        doc_id = f"email-{mail_id}"
        entry["rag_doc_id"] = doc_id
        _store_rag_doc(
            doc_id=doc_id,
            title=subject,
            content=body_text,
            permission_groups=list(DEFAULT_PERMISSION_GROUPS),
            metadata={
                "email_id": mail_id,
                "message_id": message_id,
                "sender": sender,
                "recipient": recipient,
                "received_at": received_at,
            },
        )

    return {"status": "ok", "message": entry}


@app.delete("/mail/messages/{mail_id}")
async def delete_dummy_mail(mail_id: int) -> Dict[str, Any]:
    """Remove a dummy mail entry and its paired RAG doc if present."""
    removed = MAILBOX.pop(mail_id, None)
    doc_id = f"email-{mail_id}"
    rag_removed = RAG_DOCS.pop(doc_id, None)
    return {"status": "ok", "deleted": bool(removed), "docIdRemoved": doc_id if rag_removed else None}


@app.post("/mail/reset")
async def reset_dummy_mail() -> Dict[str, Any]:
    """Reset mailbox and RAG docs to the default seed data."""
    _seed_dummy_state()
    return {"status": "ok", "seeded": len(MAILBOX)}


@app.get("/rag/docs")
async def list_rag_docs() -> Dict[str, Any]:
    """List stored dummy RAG documents."""
    return {"count": len(RAG_DOCS), "docs": list(RAG_DOCS.values())}


@app.post("/rag/insert")
async def rag_insert(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Accept insert requests that mimic the real RAG API and store them in memory."""
    data = payload.get("data")
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="data field is required")

    doc_id = str(data.get("doc_id") or data.get("id") or secrets.token_hex(8))
    title = str(data.get("title") or "").strip()
    content = str(data.get("content") or "").strip()
    permission_groups = data.get("permission_groups") or payload.get("permission_groups") or list(DEFAULT_PERMISSION_GROUPS)
    if not isinstance(permission_groups, list):
        permission_groups = list(DEFAULT_PERMISSION_GROUPS)

    stored = _store_rag_doc(
        doc_id=doc_id,
        title=title,
        content=content,
        permission_groups=[str(item) for item in permission_groups if str(item).strip()],
        metadata={
            "index_name": payload.get("index_name") or "",
            "chunk_factor": payload.get("chunk_factor") or {},
        },
    )

    return {"status": "ok", "doc_id": doc_id, "stored": stored}


@app.post("/rag/delete")
async def rag_delete(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Delete a stored dummy RAG document by doc_id."""
    doc_id = str(payload.get("doc_id") or "").strip()
    if not doc_id:
        raise HTTPException(status_code=400, detail="doc_id is required")

    existed = doc_id in RAG_DOCS
    RAG_DOCS.pop(doc_id, None)
    return {"status": "ok", "doc_id": doc_id, "deleted": existed}


@app.post("/rag/search")
async def rag_search(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Return dummy RAG search results shaped like the real service."""
    query = str(payload.get("query_text") or "").strip()
    limit_raw = payload.get("num_result_doc") or 5
    try:
        limit = max(1, int(limit_raw))
    except (TypeError, ValueError):
        limit = 5

    docs = list(RAG_DOCS.values())
    if query:
        lowered = query.lower()
        docs = [doc for doc in docs if lowered in doc["merge_title_content"].lower()]
        if not docs:
            docs = list(RAG_DOCS.values())

    hits = []
    for doc in docs[:limit]:
        hits.append(
            {
                "_id": doc["doc_id"],
                "_source": {
                    "merge_title_content": doc["merge_title_content"],
                    "title": doc["title"],
                    "content": doc["content"],
                    "permission_groups": doc.get("permission_groups", []),
                    "metadata": doc.get("metadata", {}),
                },
            }
        )

    return {
        "mode": "dummy",
        "query": query,
        "hits": {
            "total": {"value": len(docs)},
            "hits": hits,
        },
    }
