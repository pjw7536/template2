"""RAG dummy endpoints used for offsite development."""

from __future__ import annotations

import secrets
from typing import Any, Dict

from fastapi import APIRouter, Body, HTTPException

from adfs_settings import DEFAULT_PERMISSION_GROUPS, INDEX_NAMES
from adfs_stores import rag_store

router = APIRouter()


@router.get("/rag/docs")
async def list_rag_docs() -> Dict[str, Any]:
    """List stored dummy RAG documents."""
    return {
        "count": rag_store.total_count(),
        "indexes": rag_store.index_counts(),
        "docs": rag_store.all_docs(),
    }


@router.get("/rag/index-info")
async def rag_index_info() -> Dict[str, Any]:
    """Provide simple index metadata for external dev without hitting corporate RAG."""
    return {
        "indexes": [
            {"name": name, "docs": rag_store.index_counts().get(name, 0), "permission_groups": DEFAULT_PERMISSION_GROUPS}
            for name in INDEX_NAMES
        ],
        "total": rag_store.total_count(),
    }


@router.post("/rag/insert")
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


@router.post("/rag/delete")
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


@router.post("/rag/search")
async def rag_search(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Return dummy RAG search results shaped like the real service."""
    index_names_raw = payload.get("index_name") or payload.get("index_names")
    if isinstance(index_names_raw, list):
        index_names = [str(item).strip() for item in index_names_raw if str(item).strip()]
    elif isinstance(index_names_raw, str):
        index_names = [item.strip() for item in index_names_raw.split(",") if item.strip()]
    else:
        index_name_value = str(index_names_raw or "").strip()
        index_names = [index_name_value] if index_name_value else []
    if not index_names:
        index_names = [INDEX_NAMES[0]]

    query = str(payload.get("query_text") or "").strip()
    limit_raw = payload.get("num_result_doc") or 5
    try:
        limit = max(1, int(limit_raw))
    except (TypeError, ValueError):
        limit = 5

    permission_groups = payload.get("permission_groups")
    filters = payload.get("filter") if isinstance(payload.get("filter"), dict) else None
    docs: list[dict[str, Any]] = []
    for index_name in index_names:
        docs_for_index = rag_store.search(
            index_name=index_name,
            query=query,
            limit=limit,
            permission_groups=permission_groups if isinstance(permission_groups, list) else None,
            filters=filters,
        )
        pinned_doc = rag_store.index_docs.get(index_name, {}).get("email-1")
        if pinned_doc:
            docs_for_index = [pinned_doc, *[doc for doc in docs_for_index if doc.get("doc_id") != "email-1"]]
        docs.extend(docs_for_index)

    deduped: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()
    for doc in docs:
        key = (doc.get("index_name", ""), doc.get("doc_id", ""))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(doc)
    docs = deduped

    hits = []
    for doc in docs[:limit]:
        hits.append(
            {
                "_id": doc["doc_id"],
                "_index": doc["index_name"],
                "_source": {
                    "doc_id": doc["doc_id"],
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
        "index_name": index_names,
        "query": query,
        "hits": {
            "total": {"value": len(docs)},
            "hits": hits,
        },
    }
