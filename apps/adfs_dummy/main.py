"""FastAPI-based dummy ADFS/RAG sandbox for external development."""
from __future__ import annotations

import hashlib
import html
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import jwt
from fastapi import Body, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

app = FastAPI(title="Dummy ADFS", version="2.1.0")


def _parse_env_list(name: str, fallback: Sequence[str]) -> List[str]:
    raw = os.getenv(name)
    if not raw:
        return list(fallback)
    parsed: Any = None
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        parsed = None

    if isinstance(parsed, Sequence) and not isinstance(parsed, (str, bytes, bytearray)):
        values = [str(item).strip() for item in parsed if str(item).strip()]
        if values:
            return values

    values = [item.strip() for item in str(raw).split(",") if item.strip()]
    return values or list(fallback)


CLIENT_ID = os.getenv("DUMMY_ADFS_CLIENT_ID", "dummy-client")
DEFAULT_EMAIL = os.getenv("DUMMY_ADFS_EMAIL", "dummy.user@example.com")
DEFAULT_NAME = os.getenv("DUMMY_ADFS_NAME", "Dummy User")
DEFAULT_DEPT = os.getenv("DUMMY_ADFS_DEPT", "Development")
DEFAULT_SABUN = os.getenv("DUMMY_ADFS_SABUN", "S000001")
ISSUER = os.getenv("DUMMY_ADFS_ISSUER", "http://localhost:9000/adfs")
PRIVATE_KEY_PATH = Path(os.getenv("DUMMY_ADFS_PRIVATE_KEY_PATH", "dummy_adfs_private.key")).resolve()
LOGOUT_REDIRECT = os.getenv("DUMMY_ADFS_LOGOUT_TARGET", "http://localhost")
DEFAULT_PERMISSION_GROUPS = _parse_env_list("DUMMY_RAG_PERMISSION_GROUPS", ["rag-public"])

PRIMARY_RAG_INDEX = os.getenv("DUMMY_RAG_INDEX_NAME") or os.getenv("RAG_INDEX_NAME") or "rp-unclassified"
ASSISTANT_RAG_INDEX = os.getenv("DUMMY_ASSISTANT_RAG_INDEX") or os.getenv("ASSISTANT_RAG_INDEX_NAME") or "emails"
EXTRA_RAG_INDEXES = _parse_env_list("DUMMY_RAG_INDEXES", [])

INDEX_NAMES: List[str] = []
for name in [PRIMARY_RAG_INDEX, ASSISTANT_RAG_INDEX, *EXTRA_RAG_INDEXES]:
    if name and name not in INDEX_NAMES:
        INDEX_NAMES.append(name)
if not INDEX_NAMES:
    INDEX_NAMES.append("emails")

MAILBOX_RAG_INDEX = os.getenv("DUMMY_MAIL_RAG_INDEX") or PRIMARY_RAG_INDEX or INDEX_NAMES[0]
if MAILBOX_RAG_INDEX not in INDEX_NAMES:
    INDEX_NAMES.append(MAILBOX_RAG_INDEX)

try:
    PRIVATE_KEY = PRIVATE_KEY_PATH.read_text(encoding="utf-8")
except OSError as exc:  # pragma: no cover - dev feedback
    raise RuntimeError(f"Failed to read dummy ADFS private key: {PRIVATE_KEY_PATH}") from exc


def _merge_title_content(title: str, content: str) -> str:
    parts = [piece.strip() for piece in [title or "", content or ""] if piece and piece.strip()]
    return "\n\n".join(parts)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class RagStore:
    def __init__(self, index_names: List[str], default_permission_groups: List[str]) -> None:
        self.default_permission_groups = list(default_permission_groups)
        self.index_docs: Dict[str, Dict[str, Dict[str, Any]]] = {name: {} for name in index_names}

    def _ensure_index(self, index_name: str) -> Dict[str, Dict[str, Any]]:
        if index_name not in self.index_docs:
            self.index_docs[index_name] = {}
        return self.index_docs[index_name]

    def reset(self) -> None:
        for docs in self.index_docs.values():
            docs.clear()

    def seed_base_docs(self, base_docs: List[Dict[str, Any]]) -> None:
        self.reset()
        for entry in base_docs:
            index_name = entry.get("index_name") or INDEX_NAMES[0]
            self.upsert(
                index_name=index_name,
                doc_id=str(entry.get("doc_id") or secrets.token_hex(8)),
                title=entry.get("title") or "",
                content=entry.get("content") or "",
                permission_groups=entry.get("permission_groups") or self.default_permission_groups,
                metadata=entry.get("metadata") or {},
            )

    def upsert(
        self,
        *,
        index_name: str,
        doc_id: str,
        title: str,
        content: str,
        permission_groups: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        index = self._ensure_index(index_name)
        groups = permission_groups or list(self.default_permission_groups)
        stored = {
            "index_name": index_name,
            "doc_id": doc_id,
            "title": title,
            "content": content,
            "merge_title_content": _merge_title_content(title, content),
            "permission_groups": groups,
            "metadata": metadata or {},
        }
        index[doc_id] = stored
        return stored

    def delete(self, index_name: str, doc_id: str) -> Optional[Dict[str, Any]]:
        return self.index_docs.get(index_name, {}).pop(doc_id, None)

    def _normalize_meta_set(self, value: Any) -> set[str]:
        if isinstance(value, (list, tuple, set)):
            return {str(item).strip() for item in value if str(item).strip()}
        if value is None:
            return set()
        return {str(value).strip()}

    def _apply_filters(self, docs: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        filtered = docs
        dept_codes = filters.get("department_code") or []
        if isinstance(dept_codes, str):
            dept_codes = [dept_codes]
        dept_set = {str(code).strip() for code in dept_codes if str(code).strip()}
        if dept_set:
            filtered = [
                doc
                for doc in filtered
                if dept_set.intersection(self._normalize_meta_set(doc.get("metadata", {}).get("department_code")))
            ]
        return filtered

    def search(
        self,
        *,
        index_name: str,
        query: str,
        limit: int,
        permission_groups: Optional[List[str]],
        filters: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        docs = list(self.index_docs.get(index_name, {}).values())

        if permission_groups:
            allowed = {str(item).strip() for item in permission_groups if str(item).strip()}
            if allowed:
                docs = [doc for doc in docs if set(doc.get("permission_groups", [])) & allowed]

        if filters:
            docs = self._apply_filters(docs, filters)

        if query:
            lowered = query.lower()
            matched = [doc for doc in docs if lowered in doc["merge_title_content"].lower()]
            if matched:
                docs = matched

        docs.sort(key=lambda doc: doc.get("metadata", {}).get("received_at", ""), reverse=True)
        return docs[:limit]

    def all_docs(self) -> List[Dict[str, Any]]:
        all_docs: List[Dict[str, Any]] = []
        for docs in self.index_docs.values():
            all_docs.extend(docs.values())
        return all_docs

    def index_counts(self) -> Dict[str, int]:
        return {index: len(docs) for index, docs in self.index_docs.items()}

    def total_count(self) -> int:
        return sum(self.index_counts().values())


class MailStore:
    def __init__(self, rag_store: RagStore, rag_index: str) -> None:
        self.mailbox: Dict[int, Dict[str, Any]] = {}
        self._seq = 1
        self.rag_store = rag_store
        self.rag_index = rag_index

    def reset(self) -> None:
        self.mailbox.clear()
        self._seq = 1
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
            self.create_mail(register_to_rag=True, **sample)

    def create_mail(
        self,
        *,
        subject: str,
        sender: str,
        recipient: str,
        body_text: str,
        message_id: Optional[str] = None,
        received_at: Optional[str] = None,
        register_to_rag: bool = True,
        permission_groups: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        mail_id = self._seq
        self._seq += 1
        message_id_value = message_id or f"msg-{mail_id:04d}"
        received_at_value = received_at or _now_iso()

        entry = {
            "id": mail_id,
            "message_id": message_id_value,
            "subject": subject,
            "sender": sender,
            "recipient": recipient,
            "body_text": body_text,
            "received_at": received_at_value,
        }
        self.mailbox[mail_id] = entry

        if register_to_rag:
            doc_id = f"email-{mail_id}"
            entry["rag_doc_id"] = doc_id
            rag_metadata = {
                "email_id": mail_id,
                "message_id": message_id_value,
                "sender": sender,
                "recipient": recipient,
                "received_at": received_at_value,
            }
            rag_metadata.update(metadata or {})
            self.rag_store.upsert(
                index_name=self.rag_index,
                doc_id=doc_id,
                title=subject,
                content=body_text,
                permission_groups=permission_groups,
                metadata=rag_metadata,
            )

        return entry

    def delete_mail(self, mail_id: int) -> Dict[str, Any]:
        removed = self.mailbox.pop(mail_id, None)
        rag_removed = None
        if removed and removed.get("rag_doc_id"):
            rag_removed = self.rag_store.delete(self.rag_index, removed["rag_doc_id"])
        return {
            "status": "ok",
            "deleted": bool(removed),
            "docIdRemoved": removed.get("rag_doc_id") if rag_removed else None if removed else None,
        }


rag_store = RagStore(INDEX_NAMES, DEFAULT_PERMISSION_GROUPS)
mail_store = MailStore(rag_store, MAILBOX_RAG_INDEX)

BASE_RAG_DOCS = [
    {
        "index_name": PRIMARY_RAG_INDEX,
        "doc_id": "procedure-change",
        "title": "[더미] 공정 변경 보고 절차",
        "content": "공정 변경 시 보고 대상, 타임라인, 승인 흐름을 정리한 더미 문서입니다.",
        "permission_groups": DEFAULT_PERMISSION_GROUPS,
        "metadata": {"department_code": "FAB-OPS", "source": "dummy-rag"},
    },
    {
        "index_name": ASSISTANT_RAG_INDEX,
        "doc_id": "safety-checklist",
        "title": "[더미] 안전 점검 체크리스트",
        "content": "Etch 설비 점검 시 확인해야 할 항목과 안전 수칙을 정리했습니다.",
        "permission_groups": DEFAULT_PERMISSION_GROUPS,
        "metadata": {"department_code": "SAFETY", "source": "dummy-rag"},
    },
]


def _seed_all() -> None:
    """Reset RAG + mailbox stores for deterministic external dev runs."""
    rag_store.seed_base_docs(BASE_RAG_DOCS)
    mail_store.reset()


_seed_all()


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
    return {"count": len(mail_store.mailbox), "messages": list(mail_store.mailbox.values())}


@app.post("/mail/messages")
async def create_dummy_mail(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Create a dummy mail entry and optionally register it to the dummy RAG store."""
    subject = str(payload.get("subject") or "로컬 더미 메일").strip()
    sender = str(payload.get("sender") or "sender@example.com").strip()
    recipient = str(payload.get("recipient") or DEFAULT_EMAIL).strip()
    body_text = str(payload.get("body") or payload.get("content") or "본문이 비어 있습니다.").strip()
    message_id = str(payload.get("message_id") or "").strip() or None
    received_at = str(payload.get("received_at") or "").strip() or None
    permission_groups = payload.get("permission_groups")
    register_to_rag = bool(payload.get("register_to_rag", True))
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}

    if permission_groups and not isinstance(permission_groups, list):
        permission_groups = None

    entry = mail_store.create_mail(
        subject=subject,
        sender=sender,
        recipient=recipient,
        body_text=body_text,
        message_id=message_id,
        received_at=received_at,
        register_to_rag=register_to_rag,
        permission_groups=permission_groups,
        metadata=metadata,
    )

    return {"status": "ok", "message": entry}


@app.delete("/mail/messages/{mail_id}")
async def delete_dummy_mail(mail_id: int) -> Dict[str, Any]:
    """Remove a dummy mail entry and its paired RAG doc if present."""
    return mail_store.delete_mail(mail_id)


@app.post("/mail/reset")
async def reset_dummy_mail() -> Dict[str, Any]:
    """Reset mailbox and RAG docs to the default seed data."""
    _seed_all()
    return {
        "status": "ok",
        "seeded": {
            "mail": len(mail_store.mailbox),
            "rag": rag_store.total_count(),
            "indexes": rag_store.index_counts(),
        },
    }


@app.get("/rag/docs")
async def list_rag_docs() -> Dict[str, Any]:
    """List stored dummy RAG documents."""
    return {
        "count": rag_store.total_count(),
        "indexes": rag_store.index_counts(),
        "docs": rag_store.all_docs(),
    }


@app.get("/rag/index-info")
async def rag_index_info() -> Dict[str, Any]:
    """Provide simple index metadata for external dev without hitting corporate RAG."""
    return {
        "indexes": [
            {"name": name, "docs": rag_store.index_counts().get(name, 0), "permission_groups": DEFAULT_PERMISSION_GROUPS}
            for name in INDEX_NAMES
        ],
        "total": rag_store.total_count(),
    }


@app.post("/rag/insert")
async def rag_insert(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Accept insert requests that mimic the real RAG API and store them in memory."""
    data = payload.get("data")
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="data field is required")

    index_name = str(payload.get("index_name") or payload.get("target_index") or "").strip()
    if not index_name:
        raise HTTPException(status_code=400, detail="index_name is required")

    doc_id = str(data.get("doc_id") or data.get("id") or secrets.token_hex(8))
    title = str(data.get("title") or "").strip()
    content = str(data.get("content") or "").strip()
    permission_groups = data.get("permission_groups") or payload.get("permission_groups") or list(DEFAULT_PERMISSION_GROUPS)
    if not isinstance(permission_groups, list):
        permission_groups = list(DEFAULT_PERMISSION_GROUPS)

    metadata: Dict[str, Any] = {}
    metadata.update(payload.get("metadata") or {})
    metadata.update(data.get("metadata") or {})
    for key, value in data.items():
        if key in {"doc_id", "id", "title", "content", "permission_groups", "metadata"}:
            continue
        metadata[key] = value
    if payload.get("chunk_factor"):
        metadata["chunk_factor"] = payload["chunk_factor"]
    stored = rag_store.upsert(
        doc_id=doc_id,
        title=title,
        content=content,
        index_name=index_name,
        permission_groups=[str(item) for item in permission_groups if str(item).strip()],
        metadata=metadata,
    )

    return {"status": "ok", "index_name": index_name, "doc_id": doc_id, "stored": stored}


@app.post("/rag/delete")
async def rag_delete(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Delete a stored dummy RAG document by doc_id."""
    index_name = str(payload.get("index_name") or "").strip()
    if not index_name:
        raise HTTPException(status_code=400, detail="index_name is required")
    doc_id = str(payload.get("doc_id") or "").strip()
    if not doc_id:
        raise HTTPException(status_code=400, detail="doc_id is required")

    existed = rag_store.delete(index_name, doc_id)
    return {"status": "ok", "doc_id": doc_id, "index_name": index_name, "deleted": bool(existed)}


@app.post("/rag/search")
async def rag_search(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Return dummy RAG search results shaped like the real service."""
    index_name = str(payload.get("index_name") or "").strip() or INDEX_NAMES[0]
    query = str(payload.get("query_text") or "").strip()
    limit_raw = payload.get("num_result_doc") or 5
    try:
        limit = max(1, int(limit_raw))
    except (TypeError, ValueError):
        limit = 5

    permission_groups = payload.get("permission_groups")
    filters = payload.get("filter") if isinstance(payload.get("filter"), dict) else None
    docs = rag_store.search(
        index_name=index_name,
        query=query,
        limit=limit,
        permission_groups=permission_groups if isinstance(permission_groups, list) else None,
        filters=filters,
    )

    hits = []
    for doc in docs[:limit]:
        hits.append(
            {
                "_id": doc["doc_id"],
                "_index": doc["index_name"],
                "_source": {
                    "merge_title_content": doc["merge_title_content"],
                    "title": doc["title"],
                    "content": doc["content"],
                    "permission_groups": doc.get("permission_groups", []),
                    "metadata": doc.get("metadata", {}),
                },
                "_score": 1.0,
            }
        )

    return {
        "mode": "dummy",
        "index_name": index_name,
        "query": query,
        "hits": {
            "total": {"value": len(docs)},
            "hits": hits,
        },
    }
